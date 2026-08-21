"""Reachability checks for Compass's intentionally small runtime surface."""

from __future__ import annotations

import ast
import json
import re
import unittest
import subprocess
import sys
import tomllib
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Annotated, TypedDict

from langchain_core.messages import AIMessage, BaseMessage
from langgraph.graph import END, START, StateGraph
from langgraph.graph.message import add_messages

from agent.graph import workflow
from agent.graph.tool_node import CompassToolNode
from agent.graph.tools_registry import TOOL_REGISTRY
from agent.runtime.events import StreamEventType
from agent.tools.registry import build_builtin_registry
from agent.ui.commands import build_registry
from agent.workspace import WorkspaceContext
from backend.main import app


ROOT = Path(__file__).resolve().parents[1]
CLEAN_GENERATED = ROOT / "tools" / "clean_generated.py"

# These modules are reached by framework registration rather than ordinary imports.
DYNAMIC_ENTRYPOINT_ALLOWLIST = frozenset(
    {
        "agent.graph.workflow",
        "agent.ui.commands",
        "backend.routers.auth",
        "backend.routers.chat",
        "backend.routers.checkpoints",
        "backend.routers.github",
        "backend.routers.memory",
        "backend.routers.runs",
        "backend.routers.sessions",
        "backend.routers.settings",
        "backend.routers.skills",
        "backend.routers.tools",
        "backend.routers.uploads",
        "backend.routers.workspaces",
    }
)

FRONTEND_ROOT = ROOT / "frontend"
FRONTEND_SOURCE_SUFFIXES = frozenset({".ts", ".tsx", ".js", ".jsx"})
IMPORT_SPECIFIER = re.compile(
    r"(?:from\s*|import\s*\()\s*[\"']([^\"']+)[\"']"
)


def _frontend_sources(*, production_only: bool = False) -> list[Path]:
    return sorted(
        path
        for path in FRONTEND_ROOT.rglob("*")
        if path.is_file()
        and path.suffix in FRONTEND_SOURCE_SUFFIXES
        and (not production_only or ".test." not in path.name)
        and "node_modules" not in path.parts
        and "dist" not in path.parts
    )


def _frontend_imports() -> set[str]:
    imports = set()
    for path in _frontend_sources():
        imports.update(IMPORT_SPECIFIER.findall(path.read_text(encoding="utf-8")))
    return imports


def _package_name(specifier: str) -> str | None:
    if specifier.startswith((".", "@/")):
        return None
    if specifier.startswith("@"):
        return "/".join(specifier.split("/")[:2])
    return specifier.split("/", 1)[0]


def _stream_event_references(paths: list[Path]) -> set[str]:
    references = set()
    for path in paths:
        tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Attribute)
                and isinstance(node.value, ast.Name)
                and node.value.id == "StreamEventType"
            ):
                references.add(node.attr)
    return references


def _python_import_roots() -> set[str]:
    imports = set()
    for path in [*ROOT.glob("agent/**/*.py"), *ROOT.glob("backend/**/*.py"), ROOT / "main.py"]:
        tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imports.update(alias.name.split(".", 1)[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imports.add(node.module.split(".", 1)[0])
    return imports


def _python_import_name(requirement: str) -> str:
    distribution = requirement.split("[", 1)[0].lower()
    aliases = {
        "beautifulsoup4": "bs4",
        "duckduckgo-search": "duckduckgo_search",
        "email-validator": "email_validator",
        "python-dotenv": "dotenv",
        "python-jose": "jose",
    }
    return aliases.get(distribution, distribution.replace("-", "_"))


class ReachabilityTests(unittest.TestCase):
    def test_reachability_report_covers_event_frontend_and_dependency_surfaces(self):
        """Static reporting names possible cleanup work without authorizing deletion."""
        event_producers = _stream_event_references([ROOT / "agent/runtime/runner.py"])
        event_consumers = _stream_event_references(
            [
                ROOT / "agent/ui/tui.py",
                ROOT / "agent/runtime/artifacts.py",
                ROOT / "backend/services/run_persistence.py",
            ]
        )
        self.assertTrue({"TOOL_CALL", "TOOL_RESULT", "DONE"}.issubset(event_producers))
        self.assertTrue({"TOOL_CALL", "TOOL_RESULT", "DONE"}.issubset(event_consumers))

        frontend_imports = _frontend_imports()
        api_consumers = [
            path.relative_to(FRONTEND_ROOT).as_posix()
            for path in _frontend_sources(production_only=True)
            if "@/api" in path.read_text(encoding="utf-8")
        ]
        self.assertIn("axios", frontend_imports)
        self.assertIn("src/pages/ChatPage.tsx", api_consumers)

        package_manifest = json.loads(
            (FRONTEND_ROOT / "package.json").read_text(encoding="utf-8")
        )
        declared_frontend_packages = set(package_manifest["dependencies"]) | set(
            package_manifest["devDependencies"]
        )
        imported_frontend_packages = {
            package
            for specifier in frontend_imports
            if (package := _package_name(specifier)) is not None
        }
        self.assertIn("react", declared_frontend_packages)
        self.assertIn("react", imported_frontend_packages)

        python_manifest = tomllib.loads(
            (ROOT / "pyproject.toml").read_text(encoding="utf-8")
        )
        declared_python_packages = set(python_manifest["project"]["dependencies"])
        python_imports = _python_import_roots()
        self.assertIn("fastapi", declared_python_packages)
        self.assertIn("fastapi", python_imports)

        report = {
            "runtime_event_values_without_producer_or_consumer": sorted(
                event.name
                for event in StreamEventType
                if event.name not in event_producers | event_consumers
            ),
            "runtime_event_values_produced_without_consumer": sorted(
                event for event in event_producers if event not in event_consumers
            ),
            "rpc_relay_remnants_pending_review": [
                "agent.runtime.events.StreamEventType.RPC_CALL",
                "backend.schemas.chat.WsClientMessage tool_result input",
                "backend.routers.chat tool_result WebSocket branch",
                "backend.ws.hub pending_calls and resolve_call",
            ],
            "frontend_api_call_sites": sorted(api_consumers),
            "frontend_declared_packages_without_source_import": sorted(
                declared_frontend_packages - imported_frontend_packages
            ),
            "python_declared_packages_without_source_import": sorted(
                requirement
                for requirement in declared_python_packages
                if _python_import_name(requirement) not in python_imports
            ),
            "unreferenced_generated_primitives": [
                "frontend/src/components/ui/card.tsx",
                "frontend/src/components/ui/separator.tsx",
            ],
        }
        print("Reachability report only; no additional deletion is approved:")
        print(json.dumps(report, indent=2, sort_keys=True))
        self.assertIn(
            "RPC_CALL", report["runtime_event_values_without_producer_or_consumer"]
        )

    def test_registered_graph_commands_and_routers_are_live_entrypoints(self):
        """Known framework-discovered entrypoints stay registered and callable."""
        expected_nodes = {
            "context_injector",
            "planner",
            "executor",
            "check_safety",
            "tools",
            "evaluator",
            "verification_hooks",
            "coordinator",
        }
        self.assertTrue(expected_nodes.issubset(workflow.builder.nodes))

        commands = build_registry()._commands
        self.assertTrue(
            {"/route", "/model", "/doctor", "/undo", "/agents"}.issubset(commands)
        )
        self.assertTrue(all(callable(command.handler) for command in commands.values()))

        included_routers = [
            route
            for route in app.router.routes
            if hasattr(route, "effective_route_contexts")
        ]
        paths = {
            context.path
            for router in included_routers
            for context in router.effective_route_contexts()
        }
        self.assertTrue(
            {
                "/api/auth/register",
                "/api/sessions/{session_id}",
                "/api/skills",
                "/api/workspaces/",
            }.issubset(paths)
        )
        self.assertIn("agent.graph.workflow", DYNAMIC_ENTRYPOINT_ALLOWLIST)

    def test_tool_execution_replacements_are_active_before_dead_modules_are_removed(self):
        """A regression to the retired relay must not replace either active executor."""
        tools_node = workflow.builder.nodes["tools"].runnable.afunc

        self.assertIsInstance(tools_node, CompassToolNode)
        self.assertIn("shell_execute", {tool.name for tool in TOOL_REGISTRY.tools_for("tui")})
        self.assertNotIn("shell_execute", {tool.name for tool in TOOL_REGISTRY.tools_for("web")})
        self.assertFalse((ROOT / "agent/graph/remote_tool_node.py").exists())
        self.assertFalse((ROOT / "agent/ui/relay.py").exists())

    def run_cleaner(self, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(CLEAN_GENERATED), *args],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_generated_cleanup_dry_run_reports_only_exact_allowlisted_paths(self):
        """Broad workspace cleanup must not leak protected descendants into its plan."""
        with TemporaryDirectory() as folder:
            workspace = Path(folder)
            for relative in (
                "__pycache__/module.pyc",
                "nested/module.pyc",
                ".pytest_cache/state",
                "frontend/dist/assets/app.js",
                "frontend/.vite/deps/cache.json",
                "run.log",
                ".venv/lib/keep.pyc",
                ".venv.pre-a-plus/lib/keep.pyc",
                "node_modules/pkg/cache.pyc",
                ".cache/keep.pyc",
                ".compass/worker.log",
            ):
                path = workspace / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("generated", encoding="utf-8")

            result = self.run_cleaner("--dry-run", "--workspace", str(workspace))

            self.assertEqual(result.returncode, 0, result.stderr)
            reported = {
                line.removeprefix("- ")
                for line in result.stdout.splitlines()
                if line.startswith("- ")
            }
            self.assertEqual(
                reported,
                {
                    ".pytest_cache",
                    "__pycache__",
                    "frontend/.vite",
                    "frontend/dist",
                    "nested/module.pyc",
                    "run.log",
                },
            )

    def test_generated_cleanup_apply_requires_an_explicit_workspace(self):
        """Apply mode cannot silently infer a deletion root from the current directory."""
        result = self.run_cleaner("--apply")

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("--workspace", result.stderr)

    def test_generated_cleanup_apply_removes_allowlisted_paths_and_preserves_boundaries(self):
        """Applying the generated plan must leave protected descendants intact."""
        with TemporaryDirectory() as folder:
            workspace = Path(folder)
            generated = workspace / "frontend" / "dist" / "app.js"
            protected = workspace / ".venv" / "lib" / "keep.pyc"
            generated.parent.mkdir(parents=True)
            protected.parent.mkdir(parents=True)
            generated.write_text("generated", encoding="utf-8")
            protected.write_text("keep", encoding="utf-8")

            result = self.run_cleaner("--apply", "--workspace", str(workspace))

            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertFalse((workspace / "frontend" / "dist").exists())
            self.assertTrue(protected.exists())


class ToolExecutionReplacementTests(unittest.IsolatedAsyncioTestCase):
    class _ToolState(TypedDict):
        messages: Annotated[list[BaseMessage], add_messages]

    async def _invoke_read(
        self,
        *,
        execution_target: str,
        root: Path,
        path: str,
        workspace_id: str | None = None,
    ) -> str:
        context = WorkspaceContext(
            root=root,
            execution_target="web" if execution_target == "web" else "local",
            workspace_id=workspace_id,
            project_id="test-project",
        )
        builder = StateGraph(self._ToolState)
        builder.add_node("tools", CompassToolNode(build_builtin_registry()))
        builder.add_edge(START, "tools")
        builder.add_edge("tools", END)
        result = await builder.compile().ainvoke(
            {
                "messages": [
                    AIMessage(
                        content="",
                        tool_calls=[
                            {
                                "id": "read-1",
                                "name": "read_file",
                                "args": {"path": path},
                            }
                        ],
                    )
                ]
            },
            {
                "configurable": {
                    "execution_target": execution_target,
                    "workspace_context": context.to_config(),
                }
            },
        )
        return str(result["messages"][-1].content)

    async def test_tui_executes_tools_directly_in_its_local_workspace(self):
        """TUI tool calls execute through the registered local tool node, not a relay."""
        with TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "local.txt").write_text("local tool result", encoding="utf-8")

            content = await self._invoke_read(
                execution_target="tui", root=root, path="local.txt"
            )

        self.assertIn("local tool result", content)

    async def test_web_executes_permitted_tools_only_inside_its_owned_workspace(self):
        """Web calls retain allowed reads while rejecting both escaped paths and shell access."""
        with TemporaryDirectory() as parent:
            parent_root = Path(parent)
            owned = parent_root / "owned"
            outside = parent_root / "outside"
            owned.mkdir()
            outside.mkdir()
            (owned / "allowed.txt").write_text("owned workspace", encoding="utf-8")
            (outside / "secret.txt").write_text("outside workspace", encoding="utf-8")

            allowed = await self._invoke_read(
                execution_target="web",
                root=owned,
                path="allowed.txt",
                workspace_id="owned-workspace",
            )
            escaped = await self._invoke_read(
                execution_target="web",
                root=owned,
                path="../outside/secret.txt",
                workspace_id="owned-workspace",
            )

            context = WorkspaceContext(
                root=owned,
                execution_target="web",
                workspace_id="owned-workspace",
                project_id="test-project",
            )
            builder = StateGraph(self._ToolState)
            builder.add_node("tools", CompassToolNode(build_builtin_registry()))
            builder.add_edge(START, "tools")
            builder.add_edge("tools", END)
            result = await builder.compile().ainvoke(
                {
                    "messages": [
                        AIMessage(
                            content="",
                            tool_calls=[
                                {
                                    "id": "shell-1",
                                    "name": "shell_execute",
                                    "args": {"command": "echo must-not-run"},
                                }
                            ],
                        )
                    ]
                },
                {
                    "configurable": {
                        "execution_target": "web",
                        "workspace_context": context.to_config(),
                    }
                },
            )

        shell_result = str(result["messages"][-1].content)
        self.assertIn("owned workspace", allowed)
        self.assertIn("Access denied", escaped)
        self.assertIn("not a valid tool", shell_result)


if __name__ == "__main__":
    unittest.main()
