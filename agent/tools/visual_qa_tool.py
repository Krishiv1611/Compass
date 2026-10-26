"""Visual QA and Playwright headless verification tool for Compass."""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

from langchain_core.tools import tool

logger = logging.getLogger(__name__)


def _run_local_playwright(url: str, output_path: str, wait_selector: str = "") -> dict[str, Any]:
    """Execute local Playwright verification if installed on the host."""
    try:
        from playwright.sync_api import sync_playwright  # type: ignore
    except ImportError:
        return {
            "status": "unavailable",
            "message": (
                "Playwright is in standby mode. To enable headless visual QA on your machine, "
                "install playwright ('pip install playwright && playwright install chromium') "
                "or set E2B_API_KEY for isolated cloud verification."
            ),
        }

    errors: list[str] = []
    try:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            page = browser.new_page()
            page.on("pageerror", lambda err: errors.append(f"PageError: {err}"))
            page.on(
                "console",
                lambda msg: errors.append(f"ConsoleError: {msg.text}")
                if msg.type == "error"
                else None,
            )
            page.goto(url, timeout=15000)
            if wait_selector:
                page.wait_for_selector(wait_selector, timeout=5000)
            else:
                page.wait_for_load_state("networkidle", timeout=10000)
            page.screenshot(path=output_path, full_page=True)
            browser.close()

        return {
            "status": "success",
            "screenshot_path": output_path,
            "errors": errors,
            "error_count": len(errors),
        }
    except Exception as exc:
        logger.error("Local Playwright verification failed: %s", exc)
        return {
            "status": "error",
            "error": str(exc),
            "errors": errors,
        }


def _run_e2b_playwright(url: str, output_image: str = "/tmp/progress.png") -> dict[str, Any]:
    """Execute remote Playwright verification inside E2B Cloud Sandbox."""
    try:
        from agent.sandbox.e2b_adapter import E2BCloudSandbox

        sandbox = E2BCloudSandbox()
        loop = asyncio.new_event_loop()
        try:
            result = loop.run_until_complete(sandbox.run_visual_verification(url, output_image))
            return {
                "status": "success" if result.get("success") else "error",
                "screenshot_path": result.get("screenshot_path"),
                "output": result.get("stdout"),
                "errors": [result.get("errors")] if result.get("errors") else [],
            }
        finally:
            loop.close()
    except Exception as exc:
        logger.warning("E2B Playwright verification failed: %s", exc)
        return {"status": "error", "error": str(exc)}


@tool
def visual_qa_verify(url: str, wait_selector: str = "") -> str:
    """Verify a web application UI, capture a visual screenshot, and inspect for JavaScript runtime errors.

    Args:
        url: The web application URL to verify (e.g. http://localhost:5173).
        wait_selector: Optional CSS selector to wait for before taking the screenshot.
    """
    if not url.startswith(("http://", "https://")):
        return f"Error: URL must begin with http:// or https://, got {url}"

    # Priority 1: E2B Cloud Sandbox if configured
    if os.environ.get("E2B_API_KEY"):
        res = _run_e2b_playwright(url)
        if res.get("status") == "success":
            return (
                f"Visual QA Verification (Remote E2B Cloud Sandbox):\n"
                f"URL: {url}\n"
                f"Status: PASS\n"
                f"Screenshot: {res.get('screenshot_path')}\n"
                f"Detected Errors: {len(res.get('errors', []))}"
            )

    # Priority 2: Local Playwright verification
    screenshot_dir = os.path.join(os.getcwd(), ".compass", "visual_qa")
    screenshot_file = os.path.join(screenshot_dir, "progress.png")
    local_res = _run_local_playwright(url, screenshot_file, wait_selector)

    if local_res.get("status") == "success":
        err_list = local_res.get("errors", [])
        err_msg = "\n- ".join(err_list) if err_list else "None"
        return (
            f"Visual QA Verification (Local Playwright):\n"
            f"URL: {url}\n"
            f"Status: PASS\n"
            f"Screenshot saved to: {local_res.get('screenshot_path')}\n"
            f"Console/Page Errors ({len(err_list)}):\n- {err_msg}"
        )
    elif local_res.get("status") == "unavailable":
        return f"Visual QA (Standby): {local_res.get('message')}"
    else:
        return f"Visual QA Verification Failed: {local_res.get('error')}"
