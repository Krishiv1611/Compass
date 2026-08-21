"""Run the Compass verification scopes with one summarized command."""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / "frontend"
SCOPES = ("python", "frontend", "compose", "docs", "all")


@dataclass(frozen=True, slots=True)
class Check:
    scope: str
    name: str
    args: tuple[str, ...]
    cwd: Path
    timeout: int


@dataclass(frozen=True, slots=True)
class CheckResult:
    check: Check
    exit_code: int
    duration_seconds: float
    timed_out: bool = False

    @property
    def passed(self) -> bool:
        return self.exit_code == 0 and not self.timed_out


def _command(name: str) -> str:
    """Resolve Windows command shims while retaining array execution."""
    return shutil.which(name) or name


def _check_catalog() -> tuple[Check, ...]:
    python = sys.executable
    npm = _command("npm")
    npx = _command("npx")
    docker = _command("docker")
    script = str(Path(__file__).resolve())
    return (
        Check(
            "python",
            "python tests",
            (python, "-m", "unittest", "discover", "-s", "tests", "-v"),
            ROOT,
            600,
        ),
        Check(
            "python",
            "migration heads",
            (python, script, "--migration-head"),
            ROOT,
            30,
        ),
        Check(
            "frontend",
            "frontend tests",
            (npm, "test", "--", "--run"),
            FRONTEND,
            300,
        ),
        Check(
            "frontend",
            "frontend typecheck",
            (npx, "tsc", "-b", "--pretty", "false"),
            FRONTEND,
            180,
        ),
        Check(
            "frontend",
            "frontend lint",
            (npm, "run", "lint"),
            FRONTEND,
            180,
        ),
        Check(
            "frontend",
            "frontend build",
            (npm, "run", "build"),
            FRONTEND,
            300,
        ),
        Check(
            "compose",
            "development compose",
            (
                docker,
                "compose",
                "-f",
                "docker-compose.yml",
                "config",
                "--no-interpolate",
            ),
            ROOT,
            60,
        ),
        Check(
            "compose",
            "production compose",
            (
                docker,
                "compose",
                "-f",
                "docker-compose.prod.yml",
                "config",
                "--no-interpolate",
            ),
            ROOT,
            60,
        ),
        Check(
            "docs",
            "documentation truth",
            (python, "-m", "unittest", "tests.test_documentation_truth", "-v"),
            ROOT,
            120,
        ),
        Check(
            "docs",
            "workflow freshness",
            (python, "tools/render_workflow.py", "--check"),
            ROOT,
            30,
        ),
    )


def checks_for_scope(scope: str) -> tuple[Check, ...]:
    if scope not in SCOPES:
        raise ValueError(f"Unknown verification scope: {scope}")
    catalog = _check_catalog()
    return catalog if scope == "all" else tuple(
        check for check in catalog if check.scope == scope
    )


def run_check(check: Check) -> CheckResult:
    """Run one bounded argument array and return a summary record."""
    command_text = subprocess.list2cmdline(list(check.args))
    print(f"\n[{check.scope}] {check.name}", flush=True)
    print(f"command: {command_text}", flush=True)
    print(f"cwd: {check.cwd}", flush=True)
    print(f"timeout: {check.timeout}s", flush=True)
    started = time.perf_counter()
    try:
        completed = subprocess.run(
            list(check.args),
            cwd=check.cwd,
            timeout=check.timeout,
            shell=False,
            check=False,
        )
        exit_code = int(completed.returncode)
        timed_out = False
    except subprocess.TimeoutExpired:
        exit_code = 124
        timed_out = True
    except OSError as exc:
        print(f"launch error: {type(exc).__name__}: {exc}", flush=True)
        exit_code = 127
        timed_out = False
    duration = time.perf_counter() - started
    status = "TIMEOUT" if timed_out else ("PASS" if exit_code == 0 else "FAIL")
    print(
        f"result: {status} | exit={exit_code} | duration={duration:.2f}s",
        flush=True,
    )
    return CheckResult(check, exit_code, duration, timed_out)


def migration_head_check() -> int:
    """Return success only when the migration graph has exactly one head."""
    from alembic.config import Config
    from alembic.script import ScriptDirectory

    config = Config(str(ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(ROOT / "backend" / "alembic"))
    heads = ScriptDirectory.from_config(config).get_heads()
    if len(heads) != 1:
        print(f"Expected one Alembic head, found {len(heads)}: {', '.join(heads)}")
        return 1
    print(f"Alembic head: {heads[0]}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--scope", choices=SCOPES, default="all")
    parser.add_argument("--migration-head", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    if args.migration_head:
        return migration_head_check()

    checks = checks_for_scope(args.scope)
    results = [run_check(check) for check in checks]
    print("\nVerification summary")
    print("====================")
    for result in results:
        status = "PASS" if result.passed else "FAIL"
        suffix = " (timeout)" if result.timed_out else ""
        print(
            f"{status:4}  {result.check.scope:8}  {result.check.name}  "
            f"exit={result.exit_code}  {result.duration_seconds:.2f}s{suffix}"
        )
    failures = [result for result in results if not result.passed]
    if failures:
        print(f"\nFAILED: {len(failures)} of {len(results)} checks")
        return 1
    print(f"\nPASS: {len(results)} checks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
