"""Public settings must have a real, observable runtime consumer."""

from __future__ import annotations

import sys
import types
import unittest
import inspect
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

if "tomli_w" not in sys.modules:
    tomli_w = types.ModuleType("tomli_w")
    tomli_w.dump = lambda *_args, **_kwargs: None
    sys.modules["tomli_w"] = tomli_w

import agent.config as config


# Keep this table as the single inventory of documented public local settings.
PUBLIC_SETTINGS = {
    "theme": "agent.ui.theme.theme_for_preference",
    "tools.max_results": "agent.tools.search_tools.grep_search",
    "tools.shell_timeout": "agent.tools.shell_tool.shell_execute",
    "context.summarize_after": "agent.graph.routing.needs_compaction",
    "context.loop_max_retries": "agent.loop_detector.is_looping",
    "rag.auto_index": "agent.rag.indexer.index_workspace_if_enabled",
    "rag.chunk_size": "agent.rag.indexer.index_workspace",
    "hitl.enabled": "agent.safety.requires_approval",
    "hitl.auto_approve_safe": "agent.safety.requires_approval",
    "safety.mode": "agent.safety.requires_approval",
    "safety.blocked_commands": "agent.tools.shell_tool.shell_execute",
    "orchestration.enabled": "agent.graph.nodes.planner_node",
    "orchestration.max_workers": "agent.orchestration.coordinator.Coordinator.run",
}


@contextmanager
def configured(**values):
    with patch.object(config.settings, "config", {**config.DEFAULT_CONFIG, **values}):
        yield


class ConfigCoverageTests(unittest.TestCase):
    def test_effective_settings_report_covers_every_public_setting(self):
        self.assertTrue(
            hasattr(config, "effective_settings_report"),
            "configuration coverage needs an effective settings report",
        )
        report = config.effective_settings_report()
        self.assertEqual(set(PUBLIC_SETTINGS), set(report))
        for key, consumer in PUBLIC_SETTINGS.items():
            with self.subTest(key=key):
                self.assertEqual(consumer, report[key]["consumer"])
                self.assertEqual(config.settings.get(key), report[key]["value"])

    def test_theme_preference_changes_console_theme(self):
        from agent.ui import theme as tui

        with configured(theme="default"):
            default_theme = tui.theme_for_preference()
        with configured(theme="high-contrast"):
            contrast_theme = tui.theme_for_preference()
        self.assertIs(default_theme, tui.COMPASS_THEME)
        self.assertIs(contrast_theme, tui.HIGH_CONTRAST_THEME)

    def test_tool_result_limit_caps_grep_results(self):
        from agent.tools.search_tools import grep_search

        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "one.txt").write_text("needle\n", encoding="utf-8")
            (root / "two.txt").write_text("needle\n", encoding="utf-8")
            run_config = {"configurable": {"workspace_context": {
                "root": directory, "execution_target": "local",
            }}}
            with configured(**{"tools.max_results": 1}):
                result = grep_search.invoke(
                    {"query": "needle", "max_results": 50}, config=run_config
                )
        self.assertIn("Found 1 match", result)

    def test_shell_timeout_uses_configured_default(self):
        from agent.tools.shell_tool import shell_execute

        with TemporaryDirectory() as directory, configured(**{"tools.shell_timeout": 7}):
            run_config = {"configurable": {"workspace_context": {
                "root": directory, "execution_target": "local",
            }}}
            completed = SimpleNamespace(returncode=0, stdout="ok", stderr="")
            with patch("agent.tools.shell_tool.subprocess.run", return_value=completed) as run:
                shell_execute.invoke({"command": "echo ok"}, config=run_config)
        self.assertEqual(run.call_args.kwargs["timeout"], 7)

    def test_compaction_and_loop_limits_change_graph_decisions(self):
        from agent.graph.routing import needs_compaction
        from agent.loop_detector import is_looping
        from langchain_core.messages import AIMessage

        messages = [object(), object()]
        repeated = [
            AIMessage(content="", tool_calls=[{"id": str(i), "name": "read_file", "args": {"path": "a.py"}}])
            for i in range(3)
        ]
        with configured(**{"context.summarize_after": 1, "context.loop_max_retries": 4}):
            self.assertTrue(needs_compaction({"messages": messages}))
            self.assertFalse(is_looping({"messages": repeated}))

    def test_rag_chunk_size_and_auto_index_change_indexing_behavior(self):
        from agent.rag.indexer import index_workspace, index_workspace_if_enabled

        class Store:
            def __init__(self):
                self.documents = []

            def add_documents(self, *, documents):
                self.documents.extend(documents)

        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "document.txt").write_text("word " * 100, encoding="utf-8")
            store = Store()
            with configured(**{"rag.chunk_size": 80}), patch(
                "agent.rag.indexer.get_vector_store", return_value=store
            ), patch("agent.rag.indexer.delete_chunks_by_filter", return_value=0):
                index_workspace(directory, project_id="project", context_version="content:test")
            self.assertTrue(store.documents)
            self.assertTrue(all(len(item.page_content) <= 80 for item in store.documents))

        indexed = []

        provider_config = {
            "execution_target": "web",
            "embedding_provider": "openai",
            "embedding_model": "text-embedding-3-small",
            "embedding_api_key": "secret",
        }

        def record(path, *, project_id, context_version, provider_config=None):
            indexed.append((path, project_id, context_version, provider_config))
        with configured(**{"rag.auto_index": False}):
            self.assertIsNone(index_workspace_if_enabled("workspace", "project", "content", record))
        with configured(**{"rag.auto_index": True}):
            index_workspace_if_enabled(
                "workspace",
                "project",
                "content",
                record,
                provider_config=provider_config,
            )
        self.assertEqual(
            indexed, [("workspace", "project", "content", provider_config)]
        )

    def test_auto_index_accepts_the_retrieval_embedding_config(self):
        from agent.rag import indexer

        self.assertIn(
            "provider_config",
            inspect.signature(indexer.index_workspace_if_enabled).parameters,
        )

    def test_hitl_and_safety_settings_change_policy_and_shell_blocking(self):
        from agent.safety import requires_approval
        from agent.tools.shell_tool import _is_blocked

        with configured(**{"hitl.enabled": False}):
            self.assertFalse(requires_approval("edit_file", {}, []))
        with configured(**{"hitl.auto_approve_safe": False}):
            self.assertTrue(requires_approval("read_file", {}, []))
        with configured(**{"safety.mode": "strict"}):
            self.assertTrue(requires_approval("read_file", {}, []))
        with configured(**{"safety.blocked_commands": "dangerous-tool"}):
            self.assertTrue(_is_blocked("dangerous-tool --now"))


class ConfigAsyncCoverageTests(unittest.IsolatedAsyncioTestCase):
    async def test_orchestration_settings_gate_planner_and_concurrency(self):
        from agent.graph import nodes
        from agent.orchestration.coordinator import Coordinator
        from agent.orchestration.models import AgentArtifact, AgentTask, ExecutionPlan, TaskStatus

        response = SimpleNamespace(content="1. Plan")
        plan = SimpleNamespace(model_dump=lambda **_kwargs: {"tasks": []})
        with configured(**{"orchestration.enabled": False}), patch.object(
            nodes, "_invoke_model", AsyncMock(return_value=response)
        ), patch.object(nodes, "_model_for_turn", return_value=object()), patch.object(
            nodes, "create_execution_plan", AsyncMock(return_value=plan)
        ), patch.object(nodes, "render_execution_plan", return_value="workers"), patch.object(
            nodes, "is_fallback_plan", return_value=False
        ), patch("agent.skills.skill_registry.get_skill_names_descriptions", return_value=""):
            update = await nodes.planner_node({"messages": []}, {"configurable": {}})
        self.assertFalse(update["orchestration_enabled"])

        active = 0
        maximum = 0

        class Worker:
            async def run(self, task, _context, _cancel_event):
                nonlocal active, maximum
                active += 1
                maximum = max(maximum, active)
                await __import__("asyncio").sleep(0)
                active -= 1
                return AgentArtifact(task_id=task.id, status=TaskStatus.COMPLETED)

        execution_plan = ExecutionPlan(tasks=[
            AgentTask(id="one", title="one", objective="one", kind="analysis", allowed_tools=["read_file"], success_criteria=["done"]),
            AgentTask(id="two", title="two", objective="two", kind="analysis", allowed_tools=["read_file"], success_criteria=["done"]),
        ])
        with configured(**{"orchestration.max_workers": 1}):
            await Coordinator(Worker()).run(execution_plan, {}, __import__("asyncio").Event())
        self.assertEqual(maximum, 1)



if __name__ == "__main__":
    unittest.main()
