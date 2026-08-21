"""Cross-check public documentation against the registered Compass runtime."""

from __future__ import annotations

import ast
import asyncio
import os
import re
import subprocess
import sys
import unittest
import warnings
import zipfile
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from xml.etree import ElementTree


ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
DEPLOYMENT = ROOT / "DEPLOYMENT.md"
ARCHITECTURE = ROOT / "docs" / "COMPASS_ARCHITECTURE.md"
WORKFLOW = ROOT / "langgraph_workflow.md"
ROADMAP = ROOT / "roadmap.md"
REPORT = ROOT / "Compass_Product_and_Technical_Report.docx"


def _section(text: str, heading: str) -> str:
    match = re.search(
        rf"^(?P<marks>##+) {re.escape(heading)}\s*$\n(.*?)(?=^(?P=marks) |\Z)",
        text,
        flags=re.MULTILINE | re.DOTALL,
    )
    if not match:
        raise AssertionError(f"Missing README section: {heading}")
    return match.group(2)


def _environment_consumers() -> dict[str, set[str]]:
    """Map env keys to executable settings/call sites (never Compose interpolation)."""
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", DeprecationWarning)
        from backend.config import Settings

    consumers: dict[str, set[str]] = {}
    for name, field in Settings.model_fields.items():
        consumers.setdefault(name.upper(), set()).add(f"backend.config.Settings.{name}")
        alias = field.validation_alias
        for choice in getattr(alias, "choices", ()):
            if isinstance(choice, str) and re.fullmatch(r"[A-Z][A-Z0-9_]*", choice):
                consumers.setdefault(choice, set()).add(f"backend.config.Settings.{name}")

    class EnvVisitor(ast.NodeVisitor):
        def __init__(self, module: str) -> None:
            self.module = module
            self.scope: list[str] = []

        def _record(self, key: object) -> None:
            if isinstance(key, ast.Constant) and isinstance(key.value, str):
                if re.fullmatch(r"[A-Z][A-Z0-9_]*", key.value):
                    owner = ".".join((self.module, *self.scope))
                    consumers.setdefault(key.value, set()).add(owner)

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            self.scope.append(node.name)
            self.generic_visit(node)
            self.scope.pop()

        visit_AsyncFunctionDef = visit_FunctionDef

        def visit_Call(self, node: ast.Call) -> None:
            func = node.func
            is_getenv = (
                isinstance(func, ast.Attribute)
                and isinstance(func.value, ast.Name)
                and func.value.id == "os"
                and func.attr == "getenv"
            )
            is_environ_get = (
                isinstance(func, ast.Attribute)
                and func.attr == "get"
                and isinstance(func.value, ast.Attribute)
                and isinstance(func.value.value, ast.Name)
                and func.value.value.id == "os"
                and func.value.attr == "environ"
            )
            if (is_getenv or is_environ_get) and node.args:
                self._record(node.args[0])
            self.generic_visit(node)

        def visit_Subscript(self, node: ast.Subscript) -> None:
            value = node.value
            if (
                isinstance(value, ast.Attribute)
                and isinstance(value.value, ast.Name)
                and value.value.id == "os"
                and value.attr == "environ"
            ):
                self._record(node.slice)
            self.generic_visit(node)

    for source in (*ROOT.glob("agent/**/*.py"), *ROOT.glob("backend/**/*.py")):
        module = ".".join(source.relative_to(ROOT).with_suffix("").parts)
        EnvVisitor(module).visit(ast.parse(source.read_text(encoding="utf-8-sig")))

    frontend_client = ROOT / "frontend" / "src" / "api" / "client.ts"
    for key in re.findall(
        r"import\.meta\.env\.([A-Z][A-Z0-9_]*)",
        frontend_client.read_text(encoding="utf-8"),
    ):
        consumers.setdefault(key, set()).add("frontend.src.api.client")
    return consumers


def _documented_environment_keys(text: str) -> set[str]:
    return set(re.findall(r"`([A-Z][A-Z0-9]*_[A-Z0-9_]+)(?:=[^`]*)?`", text))


def _documented_api_bases(text: str) -> set[str]:
    values = set(re.findall(r"`(/(?:api/[a-z-]+|health|ready))`", text))
    return {value.rstrip("/") for value in values}


def _report_text() -> str:
    with zipfile.ZipFile(REPORT) as archive:
        document_xml = archive.read("word/document.xml")
    root = ElementTree.fromstring(document_xml)
    return "\n".join(text for text in root.itertext() if text.strip())


class DocumentationTruthTests(unittest.TestCase):
    """Each test names a public claim that can drift from working code."""

    @classmethod
    def setUpClass(cls) -> None:
        os.environ.setdefault(
            "DB_URI", "postgresql://compass:compass@127.0.0.1:5432/compass"
        )

    def test_every_readme_slash_command_is_registered(self):
        # Break caught: README advertises a command the TUI cannot dispatch.
        from agent.ui.commands import build_registry
        from agent.ui.tui import SLASH_COMMANDS

        section = _section(README.read_text(encoding="utf-8"), "Terminal UI")
        documented = set(re.findall(r"`(/[a-z][a-z-]*)`", section))
        registry_commands = {
            line.split(maxsplit=1)[0]
            for line in build_registry().help_text().splitlines()
        }
        self.assertTrue(documented, "Terminal UI section must list its public commands")
        self.assertEqual(
            set(), documented - (set(SLASH_COMMANDS) | registry_commands)
        )

    def test_documented_environment_keys_have_runtime_consumers(self):
        # Break caught: setup instructions expose a no-op or misspelled variable.
        docs = "\n".join(
            (README.read_text(encoding="utf-8"), DEPLOYMENT.read_text(encoding="utf-8"))
        )
        documented = _documented_environment_keys(docs)
        self.assertTrue(documented)
        consumers = _environment_consumers()
        self.assertEqual(set(), documented - consumers.keys())
        self.assertTrue(all(consumers[key] for key in documented))

    def test_documented_router_bases_are_registered(self):
        # Break caught: a documented API base has no live FastAPI route.
        from backend.main import app

        registered_paths = {path.rstrip("/") for path in app.openapi()["paths"]}
        registered_bases = {"/health", "/ready"}
        for path in registered_paths:
            match = re.match(r"(/api/[a-z-]+)", path)
            if match:
                registered_bases.add(match.group(1))
        docs = "\n".join(
            (README.read_text(encoding="utf-8"), DEPLOYMENT.read_text(encoding="utf-8"))
        )
        documented = _documented_api_bases(docs)
        self.assertIn("/ready", documented)
        self.assertEqual(set(), documented - registered_bases)

    def test_workflow_document_is_generated_from_registered_builder(self):
        # Break caught: a graph node or edge changes without regenerating the diagram.
        from tools.render_workflow import render_document

        self.assertEqual(render_document(), WORKFLOW.read_text(encoding="utf-8"))

    def test_workflow_mermaid_edges_and_router_table_match_builder_independently(self):
        # Break caught: renderer drops an edge/router while still producing a fresh file.
        from agent.graph.workflow import builder

        text = WORKFLOW.read_text(encoding="utf-8")
        mermaid = re.search(r"```mermaid\n(.*?)\n```", text, re.DOTALL).group(1)
        actual_edges = set()
        for source, arrow, label, target in re.findall(
            r"^\s*node_([a-zA-Z0-9_]+)\s+(-\.->|-->)"
            r"(?:\|([^|]+)\|)?\s+node_([a-zA-Z0-9_]+)\s*$",
            mermaid,
            re.MULTILINE,
        ):
            actual_edges.add((source, target, label, arrow == "-.->"))

        expected_edges = {
            (str(source).strip("_"), str(target).strip("_"), "", False)
            for source, target in builder.edges
        }
        expected_dynamic = set()
        for source, branches in builder.branches.items():
            for branch_name, branch in branches.items():
                if branch.ends:
                    expected_edges.update(
                        (
                            str(source).strip("_"),
                            str(target).strip("_"),
                            str(outcome),
                            True,
                        )
                        for outcome, target in branch.ends.items()
                    )
                else:
                    route = getattr(branch.path, "name", None) or str(branch_name)
                    expected_dynamic.add((str(source), str(route)))

        table = _section(text, "Registered descriptor")
        actual_dynamic = set(
            re.findall(r"^\| `([^`]+)` \| `([^`]+)` \|$", table, re.MULTILINE)
        )
        self.assertEqual(expected_edges, actual_edges)
        self.assertEqual(expected_dynamic, actual_dynamic)

    def test_workflow_renderer_is_offline_and_covers_every_registered_node(self):
        # Break caught: rendering starts runtime services or silently omits a node.
        result = subprocess.run(
            [sys.executable, "tools/render_workflow.py", "--stdout"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            timeout=20,
            check=False,
            env={**os.environ, "DB_URI": "postgresql://offline.invalid/never-connect"},
        )
        self.assertEqual(0, result.returncode, result.stderr)
        from agent.graph.workflow import builder

        for node in builder.nodes:
            self.assertRegex(result.stdout, rf"\b{re.escape(node)}\b")

    def test_compaction_claim_matches_routing_threshold_and_consumer(self):
        from agent.config import DEFAULT_CONFIG, PUBLIC_SETTING_CONSUMERS
        from agent.graph.routing import needs_compaction

        self.assertEqual(10, DEFAULT_CONFIG["context.summarize_after"])
        self.assertEqual(
            "agent.graph.routing.needs_compaction",
            PUBLIC_SETTING_CONSUMERS["context.summarize_after"],
        )
        with patch("agent.graph.routing.settings.get", return_value=2):
            self.assertFalse(needs_compaction({"messages": [1, 2]}))
            self.assertTrue(needs_compaction({"messages": [1, 2, 3]}))
            self.assertFalse(
                needs_compaction({"messages": [1, 2, 3], "pending_tool_calls": [1]})
            )
        readme = README.read_text(encoding="utf-8")
        self.assertIn("`context.summarize_after`", readme)
        self.assertRegex(readme, r"`context\.summarize_after`[^\n]*`10`")

    def test_vite_and_nginx_proxy_claims_match_checked_in_configuration(self):
        vite = (ROOT / "frontend" / "vite.config.ts").read_text(encoding="utf-8")
        self.assertRegex(vite, r'"/api"\s*:\s*\{')
        self.assertRegex(vite, r'target\s*:\s*"http://localhost:8000"')
        self.assertRegex(vite, r"ws\s*:\s*true")
        nginx = (ROOT / "frontend" / "nginx.conf").read_text(encoding="utf-8")
        self.assertRegex(nginx, r"location\s+/api/")
        self.assertIn("proxy_set_header Upgrade", nginx)
        readme = README.read_text(encoding="utf-8")
        self.assertNotIn("Vite development does not define a proxy", readme)
        self.assertIn("Vite development proxies `/api`", readme)

    def test_schedule_claim_matches_handler_result_and_side_effects(self):
        from agent.ui.commands.models import CommandContext
        from agent.ui.commands.system import schedule

        context = CommandContext(None, None, {}, None, None, {})
        result = asyncio.run(schedule("tomorrow", context))
        self.assertTrue(result.consumed)
        self.assertEqual("unavailable", result.status)
        self.assertEqual({}, result.state_updates)
        self.assertIn("no task was created", result.message.casefold())
        self.assertRegex(
            README.read_text(encoding="utf-8").casefold(),
            r"/schedule[^\n]*unavailable[^\n]*does not create",
        )
        self.assertIn(
            "/schedule` reports unavailable and creates nothing",
            ROADMAP.read_text(encoding="utf-8"),
        )

    def test_refresh_claims_match_token_cookie_rotation_and_frontend_storage(self):
        from fastapi import Response
        from backend.auth.jwt import create_refresh_token, decode_token
        from backend.routers.auth import _browser_tokens
        from backend.schemas.auth import TokenResponse

        token = create_refresh_token("truth-user", refresh_version=7)
        payload = decode_token(token)
        self.assertEqual("refresh", payload["type"])
        self.assertEqual(7, payload["rv"])
        response = Response()
        browser = _browser_tokens(
            response,
            TokenResponse(access_token="access", refresh_token=token, expires_in=60),
        )
        cookie = response.headers["set-cookie"].casefold()
        self.assertIn("httponly", cookie)
        self.assertIn("path=/api/auth", cookie)
        self.assertNotIn("refresh_token", browser.model_dump())

        auth_source = (ROOT / "backend" / "routers" / "auth.py").read_text(encoding="utf-8")
        self.assertIn("User.refresh_version == refresh_version", auth_source)
        self.assertIn("refresh_version=User.refresh_version + 1", auth_source)
        client = (ROOT / "frontend" / "src" / "api" / "client.ts").read_text(encoding="utf-8")
        self.assertRegex(client, r"let accessToken: string \| null = null")
        self.assertNotRegex(client, r"localStorage|sessionStorage")

        readme_deploy = README.read_text(encoding="utf-8") + DEPLOYMENT.read_text(encoding="utf-8")
        for claim in ("rotating, single-use HttpOnly cookie", "Access tokens stay in browser memory"):
            self.assertIn(claim.casefold(), readme_deploy.casefold())

    def test_report_artifact_contains_generator_claims_backed_by_code(self):
        generator = ROOT / "tools" / "build_compass_report.py"
        module = ast.parse(generator.read_text(encoding="utf-8"))
        assignment = next(
            node
            for node in module.body
            if isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Name) and target.id == "REPORT_TRUTH_CLAIMS" for target in node.targets)
        )
        REPORT_TRUTH_CLAIMS = ast.literal_eval(assignment.value)

        report = re.sub(r"\s+", " ", _report_text())
        self.assertEqual({"workflow", "refresh"}, set(REPORT_TRUTH_CLAIMS))
        for claim in REPORT_TRUTH_CLAIMS.values():
            self.assertIn(re.sub(r"\s+", " ", claim), report)

    def test_docs_and_report_do_not_make_known_stale_claims(self):
        # Break caught: removed or unavailable technology is presented as shipped.
        corpus = "\n".join(
            (
                README.read_text(encoding="utf-8"),
                DEPLOYMENT.read_text(encoding="utf-8"),
                ARCHITECTURE.read_text(encoding="utf-8"),
                WORKFLOW.read_text(encoding="utf-8"),
                ROADMAP.read_text(encoding="utf-8"),
                _report_text(),
            )
        )
        lowered = corpus.casefold()
        for stale_term in ("nemo guardrails", "chromadb", "chroma vector"):
            if stale_term in lowered:
                self.fail(f"stale shipped-capability claim remains: {stale_term}")
        self.assertNotRegex(lowered, r"scheduler (?:is )?(?:available|enabled|working)")
        self.assertNotRegex(lowered, r"mcp_servers\.json|mcp\.json")

class VerificationCommandTests(unittest.TestCase):
    def test_all_scope_contains_every_required_gate(self):
        # Break caught: the one-command gate silently stops running a required scope.
        from tools.verify import checks_for_scope

        checks = checks_for_scope("all")
        scopes = {check.scope for check in checks}
        self.assertEqual({"python", "frontend", "compose", "docs"}, scopes)
        names = {check.name for check in checks}
        self.assertTrue(
            {
                "python tests",
                "migration heads",
                "frontend tests",
                "frontend typecheck",
                "frontend lint",
                "frontend build",
                "development compose",
                "production compose",
                "documentation truth",
                "workflow freshness",
            }.issubset(names)
        )
        compose_checks = [check for check in checks if check.scope == "compose"]
        self.assertTrue(compose_checks)
        self.assertTrue(
            all("--no-interpolate" in check.args for check in compose_checks),
            "Compose verification must not print interpolated environment secrets",
        )

    def test_runner_uses_argument_array_workspace_cwd_and_timeout(self):
        # Break caught: shell interpolation or an unbounded child process is introduced.
        from tools.verify import Check, run_check

        check = Check(
            scope="docs",
            name="example",
            args=(sys.executable, "-c", "print('ok')"),
            cwd=ROOT,
            timeout=7,
        )
        with patch(
            "tools.verify.subprocess.run",
            return_value=SimpleNamespace(returncode=0),
        ) as run:
            result = run_check(check)

        self.assertEqual(0, result.exit_code)
        positional, keyword = run.call_args
        self.assertIsInstance(positional[0], list)
        self.assertEqual(list(check.args), positional[0])
        self.assertEqual(ROOT, keyword["cwd"])
        self.assertEqual(7, keyword["timeout"])
        self.assertEqual(os.environ, keyword["env"])
        self.assertIs(False, keyword["shell"])
        self.assertIs(False, keyword["check"])

    def test_python_scope_supplies_only_the_test_database_setting(self):
        # Break caught: a clean checkout needs a developer .env merely to
        # import backend test modules.
        from tools.verify import checks_for_scope

        python_test = next(
            check for check in checks_for_scope("python") if check.name == "python tests"
        )
        self.assertEqual(
            (("DB_URI", "postgresql://compass:change-me@127.0.0.1:5432/compass"),),
            python_test.environment,
        )

    def test_runner_reports_timeout_as_failure(self):
        # Break caught: a timed-out child crashes the orchestrator without a summary.
        from tools.verify import Check, run_check

        check = Check("python", "slow", (sys.executable, "-V"), ROOT, 1)
        with patch(
            "tools.verify.subprocess.run",
            side_effect=subprocess.TimeoutExpired(list(check.args), check.timeout),
        ):
            result = run_check(check)

        self.assertEqual(124, result.exit_code)
        self.assertTrue(result.timed_out)


if __name__ == "__main__":
    unittest.main()
