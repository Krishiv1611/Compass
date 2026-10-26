"""Tests for LiteLLM Universal Router and self-healing engine."""

import unittest
from unittest.mock import MagicMock, patch

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import tool

from agent.llm_router import LiteLLMChatModel, get_fast_router
from agent.llm import llm
from backend.services.provider_credentials import validate_provider, validate_provider_model


class LiteLLMRouterTests(unittest.TestCase):
    """Test suite for LiteLLM Universal Router integration."""

    def test_router_initialization_defaults_to_gemini_flash(self):
        router = get_fast_router()
        self.assertEqual(router.model, "gemini/gemini-3.8-flash")
        self.assertEqual(router._llm_type, "litellm")

    def test_mock_generation_offline(self):
        router = LiteLLMChatModel(model="gemini/gemini-3.8-flash", api_key="mock_key")
        result = router.invoke([HumanMessage(content="Test prompt")])
        self.assertIsInstance(result, AIMessage)
        self.assertIn("gemini/gemini-3.8-flash", result.content)

    def test_bind_tools_formatting(self):
        router = get_fast_router()

        @tool
        def sample_tool(query: str) -> str:
            """Sample search tool."""
            return query

        bound = router.bind_tools([sample_tool])
        self.assertTrue(hasattr(bound, "bound_tools") or hasattr(bound, "kwargs"))

    def test_factory_resolves_litellm_provider(self):
        model = llm(provider="litellm", model="gemini/gemini-2.0-flash", api_key="mock_key")
        self.assertIsInstance(model, LiteLLMChatModel)
        self.assertEqual(model.model, "gemini/gemini-2.0-flash")

    def test_provider_credential_validation(self):
        self.assertEqual(validate_provider("litellm"), "litellm")
        prov, model = validate_provider_model("litellm", "gemini/gemini-2.0-flash")
        self.assertEqual(prov, "litellm")
        self.assertEqual(model, "gemini/gemini-2.0-flash")

        # OpenRouter free models and :free suffix validation
        prov_or, model_free = validate_provider_model("openrouter", "openrouter/free")
        self.assertEqual(prov_or, "openrouter")
        self.assertEqual(model_free, "openrouter/free")

        prov_or2, model_r1_free = validate_provider_model("openrouter", "deepseek/deepseek-r1:free")
        self.assertEqual(prov_or2, "openrouter")
        self.assertEqual(model_r1_free, "deepseek/deepseek-r1:free")

    def test_router_execution_models_fallback_cascade(self):
        router = LiteLLMChatModel(model="deepseek/deepseek-r1", api_key="mock_key")
        execution_chain = router._get_execution_models()
        self.assertEqual(execution_chain[0], "deepseek/deepseek-r1")
        self.assertIn("deepseek/deepseek-r1:free", execution_chain)
        self.assertIn("openrouter/free", execution_chain)

    def test_router_execution_models_with_openrouter_free(self):
        router = LiteLLMChatModel(model="openrouter/free", api_key="mock_key")
        execution_chain = router._get_execution_models()
        self.assertEqual(execution_chain[0], "openrouter/free")
        # Ensure free fallbacks are included
        self.assertTrue(any(":free" in m for m in execution_chain))


class SelfHealingLoopTests(unittest.TestCase):
    """Test suite for self-healing error recovery loop in executor node."""

    def test_self_healing_context_injection_on_tool_failure(self):
        from agent.graph.nodes import build_self_healing_prompt

        messages = [
            HumanMessage(content="Run the build"),
            AIMessage(content="Calling build tool", tool_calls=[{"id": "call_1", "name": "build", "args": {}}]),
            ToolMessage(content="Error: Command failed with exit code 1: TS2304 Cannot find name 'foo'", tool_call_id="call_1"),
        ]

        prompt = build_self_healing_prompt(messages)
        self.assertIsNotNone(prompt)
        self.assertIn("SELF-HEALING RECOVERY MODE ACTIVE", prompt)
        self.assertIn("TS2304 Cannot find name 'foo'", prompt)

    def test_self_healing_ignores_successful_tools(self):
        from agent.graph.nodes import build_self_healing_prompt

        messages = [
            HumanMessage(content="List files"),
            AIMessage(content="Calling list", tool_calls=[{"id": "call_1", "name": "list", "args": {}}]),
            ToolMessage(content="package.json\nsrc\ntsconfig.json", tool_call_id="call_1"),
        ]

        prompt = build_self_healing_prompt(messages)
        self.assertIsNone(prompt)


class VisualQAToolTests(unittest.TestCase):
    """Test suite for Playwright visual QA tool and registry."""

    def test_visual_qa_registered_in_tool_registry(self):
        from agent.graph.tools_registry import TOOL_REGISTRY
        spec = TOOL_REGISTRY.get("visual_qa_verify")
        self.assertIsNotNone(spec)
        self.assertEqual(spec.policy.risk, "safe")
        self.assertFalse(spec.policy.mutates_workspace)
        self.assertTrue(spec.policy.web_allowed)
        self.assertTrue(spec.policy.worker_allowed)

    def test_visual_qa_validates_url(self):
        from agent.tools.visual_qa_tool import visual_qa_verify
        res = visual_qa_verify.invoke({"url": "invalid-url"})
        self.assertIn("Error: URL must begin with http:// or https://", res)

    def test_visual_qa_standby_diagnostic_fallback(self):
        from agent.tools.visual_qa_tool import visual_qa_verify
        # When neither E2B nor local playwright is available, provides clear diagnostic instructions
        res = visual_qa_verify.invoke({"url": "http://localhost:5173"})
        self.assertTrue(
            "Visual QA" in res or "PASS" in res or "Playwright" in res,
            f"Expected diagnostic or QA status, got: {res}"
        )


if __name__ == "__main__":
    unittest.main()
