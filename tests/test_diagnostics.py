import json
import unittest

from langchain_core.messages import HumanMessage

from agent.runtime.diagnostics import capability_report, route_report, timing_report
from agent.runtime.metrics import MetricsSnapshot, SpanSnapshot


class CapabilityReportTests(unittest.TestCase):
    def test_reports_effective_capabilities_without_serializing_secrets(self):
        config = {
            "configurable": {
                "llm_provider": "openai",
                "model": "gpt-4o-mini",
                "api_key": "provider-secret",
                "database_url": "postgresql://secret@localhost/compass",
                "embedding_provider": "openai",
                "embedding_model": "text-embedding-3-small",
                "embedding_api_key": "embedding-secret",
                "mcp_servers": [{"name": "local"}],
                "custom_tools.enabled": True,
                "custom_tools.approved_paths": ["tools"],
                "shell_enabled": True,
                "permission_profile": "review",
            }
        }

        report = capability_report(config)

        self.assertTrue(report["provider"]["credential_configured"])
        self.assertEqual(report["provider"]["name"], "openai")
        self.assertEqual(report["permission_profile"], "review")
        self.assertTrue(all(item["available"] for item in report["capabilities"].values()))
        serialized = json.dumps(report)
        self.assertNotIn("provider-secret", serialized)
        self.assertNotIn("embedding-secret", serialized)
        self.assertNotIn("postgresql", serialized)

    def test_unavailable_list_matches_disabled_runtime_features(self):
        report = capability_report({
            "llm_provider": "anthropic",
            "model": "claude-test",
            "has_llm_api_key": False,
            "database_enabled": False,
            "embeddings_enabled": False,
            "mcp_enabled": False,
            "custom_tools.enabled": False,
            "shell_enabled": False,
        })

        self.assertEqual(
            set(report["unavailable"]),
            {"provider", "database", "embeddings", "mcp", "custom_tools", "shell"},
        )


class RouteReportTests(unittest.TestCase):
    def test_greeting_names_direct_chat(self):
        report = route_report({"mode": "ask", "messages": [HumanMessage(content="hello")]})
        self.assertEqual(report["route"], "direct-chat")
        self.assertEqual(report["entry_node"], "direct_chat")

    def test_complex_edit_names_context_then_planner(self):
        report = route_report({
            "mode": "edit",
            "messages": [HumanMessage(content="Redesign authentication across the codebase")],
        })
        self.assertEqual(report["route"], "context-planner")
        self.assertEqual(report["path"], ["context_injector", "planner", "executor"])


class TimingReportTests(unittest.TestCase):
    def test_groups_spans_and_marks_unknown_cost_unavailable(self):
        metrics = MetricsSnapshot(
            spans={
                "executor.model": SpanSnapshot(calls=1, duration_ms=120),
                "context.prepare": SpanSnapshot(calls=1, duration_ms=12),
                "tools.execute": SpanSnapshot(calls=2, duration_ms=30),
                "approval.wait": SpanSnapshot(calls=1, duration_ms=40),
                "persistence.events": SpanSnapshot(calls=1, duration_ms=8),
            },
            calls_by_node={"executor": 1},
            total_input_tokens=10,
            total_output_tokens=5,
            total_tokens=15,
            estimated_cost_usd=None,
            tags={"provider": "openai", "model": "unknown", "mcp_cache": "hit"},
        )

        report = timing_report(metrics)

        self.assertEqual(report["categories"]["provider_wait_ms"], 120)
        self.assertEqual(report["categories"]["local_compute_ms"], 12)
        self.assertEqual(report["categories"]["tool_time_ms"], 30)
        self.assertEqual(report["categories"]["approval_wait_ms"], 40)
        self.assertEqual(report["categories"]["persistence_ms"], 8)
        self.assertEqual(report["cost"], {"status": "unavailable", "estimated_usd": None})
        self.assertEqual(report["cache"], {"mcp": "hit"})


if __name__ == "__main__":
    unittest.main()
