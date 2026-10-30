"""Compass E2B Cloud Sandbox Adapter.

Provides zero-hardware-cost cloud Linux microVMs via E2B's Free Tier
(100 hours/month free compute, 150ms startup time, isolated Firecracker microVMs).
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from dataclasses import dataclass
from typing import Callable, Optional

logger = logging.getLogger(__name__)


@dataclass
class CommandResult:
    stdout: str
    stderr: str
    exit_code: int
    duration_ms: float

    @property
    def success(self) -> bool:
        return self.exit_code == 0


class E2BCloudSandbox:
    """Manages an ephemeral, isolated cloud microVM via E2B Free Tier."""

    def __init__(
        self,
        api_key: Optional[str] = None,
        template: Optional[str] = None,
        timeout_seconds: int = 300,
    ):
        self.api_key = api_key or os.environ.get("E2B_API_KEY")
        self.template = template
        self.timeout_seconds = timeout_seconds
        self._sandbox = None
        self._is_mock = False

    @property
    def is_configured(self) -> bool:
        """Return True if an E2B API key is available."""
        return bool(self.api_key and self.api_key.strip())

    @property
    def sandbox_id(self) -> Optional[str]:
        if self._sandbox:
            return getattr(self._sandbox, "sandbox_id", None)
        return "mock-sandbox" if self._is_mock else None

    async def start(self) -> bool:
        """Boot the remote E2B microVM."""
        if not self.is_configured:
            logger.info(
                "E2B_API_KEY not configured. Running in sandbox fallback mode. "
                "Get a free 100 hr/mo key at https://e2b.dev"
            )
            self._is_mock = True
            return True

        try:
            from e2b import AsyncSandbox

            kwargs = {}
            if self.api_key:
                kwargs["api_key"] = self.api_key
            if self.template:
                kwargs["template"] = self.template

            self._sandbox = await AsyncSandbox.create(**kwargs)
            logger.info("E2B Cloud Sandbox booted successfully: %s", self._sandbox.sandbox_id)
            return True
        except Exception as exc:
            logger.warning("Failed to boot E2B sandbox (%s). Falling back to mock.", exc)
            self._is_mock = True
            return False

    async def run_command(
        self,
        cmd: str,
        cwd: Optional[str] = None,
        on_stdout: Optional[Callable[[str], None]] = None,
        on_stderr: Optional[Callable[[str], None]] = None,
        timeout: float = 60.0,
    ) -> CommandResult:
        """Execute a shell command inside the remote microVM."""
        start_time = time.perf_counter()

        if self._is_mock or not self._sandbox:
            # Real local execution runner for local/offline environments
            target_cwd = cwd or os.getcwd()
            try:
                import subprocess

                def _run_sync():
                    return subprocess.run(
                        cmd,
                        cwd=target_cwd,
                        shell=True,
                        capture_output=True,
                        text=True,
                        timeout=timeout,
                    )

                proc = await asyncio.to_thread(_run_sync)
                stdout_str = proc.stdout or ""
                stderr_str = proc.stderr or ""
                duration = (time.perf_counter() - start_time) * 1000

                if on_stdout and stdout_str:
                    on_stdout(stdout_str)
                if on_stderr and stderr_str:
                    on_stderr(stderr_str)

                return CommandResult(
                    stdout=stdout_str,
                    stderr=stderr_str,
                    exit_code=proc.returncode if proc.returncode is not None else 0,
                    duration_ms=duration,
                )
            except Exception as exc:
                duration = (time.perf_counter() - start_time) * 1000
                err_msg = f"Local command error: {exc}"
                if on_stderr:
                    on_stderr(err_msg)
                return CommandResult(
                    stdout="",
                    stderr=err_msg,
                    exit_code=1,
                    duration_ms=duration,
                )

        try:
            execution = await self._sandbox.commands.run(
                cmd=cmd,
                cwd=cwd or "/home/user",
                on_stdout=on_stdout,
                on_stderr=on_stderr,
                timeout=timeout,
            )
            duration = (time.perf_counter() - start_time) * 1000
            return CommandResult(
                stdout=execution.stdout or "",
                stderr=execution.stderr or "",
                exit_code=execution.exit_code or 0,
                duration_ms=duration,
            )
        except Exception as exc:
            duration = (time.perf_counter() - start_time) * 1000
            err_msg = str(exc)
            if on_stderr:
                on_stderr(err_msg + "\n")
            return CommandResult(
                stdout="",
                stderr=err_msg,
                exit_code=1,
                duration_ms=duration,
            )

    async def write_file(self, path: str, content: str) -> bool:
        """Write a file to the remote microVM filesystem or local disk."""
        if self._is_mock or not self._sandbox:
            try:
                parent = os.path.dirname(os.path.abspath(path))
                if parent:
                    os.makedirs(parent, exist_ok=True)
                with open(path, "w", encoding="utf-8") as f:
                    f.write(content)
                return True
            except Exception as exc:
                logger.warning("Local write_file failed for %s: %s", path, exc)
                return False

        try:
            await self._sandbox.files.write(path, content)
            return True
        except Exception as exc:
            logger.error("Failed to write remote file %s: %s", path, exc)
            return False

    async def read_file(self, path: str) -> str:
        """Read a file from the remote microVM filesystem or local disk."""
        if self._is_mock or not self._sandbox:
            try:
                if not os.path.exists(path):
                    return ""
                with open(path, "r", encoding="utf-8") as f:
                    return f.read()
            except Exception as exc:
                logger.warning("Local read_file failed for %s: %s", path, exc)
                return ""

        try:
            return await self._sandbox.files.read(path)
        except Exception as exc:
            logger.error("Failed to read remote file %s: %s", path, exc)
            return ""

    async def run_visual_verification(
        self,
        url: str,
        output_image: str = "/tmp/progress.png",
    ) -> dict:
        """Execute headless Playwright visual QA inside the remote VM."""
        script = f"""
import asyncio
from playwright.async_api import async_playwright

async def verify():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        errors = []
        page.on("pageerror", lambda err: errors.append(str(err)))
        page.on("console", lambda msg: errors.append(msg.text) if msg.type == "error" else None)
        try:
            await page.goto("{url}", timeout=15000)
            await page.wait_for_load_state("networkidle", timeout=10000)
            await page.screenshot(path="{output_image}", full_page=True)
            print(f"VERIFIED: {{len(errors)}} errors")
        except Exception as e:
            print(f"FAILED: {{e}}")
        finally:
            await browser.close()

asyncio.run(verify())
"""
        await self.write_file("/tmp/verify_qa.py", script)
        cmd_res = await self.run_command("python /tmp/verify_qa.py", timeout=30.0)
        return {
            "success": cmd_res.success,
            "stdout": cmd_res.stdout,
            "errors": cmd_res.stderr,
            "screenshot_path": output_image if cmd_res.success else None,
        }

    async def close(self) -> None:
        """Terminate and release the remote cloud microVM."""
        if self._sandbox:
            try:
                await self._sandbox.kill()
                logger.info("E2B Cloud Sandbox terminated.")
            except Exception as exc:
                logger.debug("Error while terminating E2B sandbox: %s", exc)
            finally:
                self._sandbox = None
        self._is_mock = False

    async def __aenter__(self) -> E2BCloudSandbox:
        await self.start()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb) -> None:
        await self.close()
