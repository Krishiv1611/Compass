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
        self.assertEqual(router.model, "gemini/gemini-2.0-flash")
        self.assertEqual(router._llm_type, "litellm")

    def test_mock_generation_offline(self):
        router = LiteLLMChatModel(model="gemini/gemini-2.0-flash", api_key="mock_key")
        result = router.invoke([HumanMessage(content="Test prompt")])
        self.assertIsInstance(result, AIMessage)
        self.assertIn("gemini/gemini-2.0-flash", result.content)

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


class SelfHealingLoopTests(unittest.TestCase):
    """Test suite for self-healing error recovery loop in executor node."""

    def test_self_healing_context_injection_on_tool_failure(self):
        from agent.graph.nodes import call_model

        state = {
            "messages": [
                HumanMessage(content="Run the build"),
                AIMessage(content="Calling build tool", tool_calls=[{"id": "call_1", "name": "build", "args": {}}]),
                ToolMessage(content="Error: Command failed with exit code 1: TS2304 Cannot find name 'foo'", tool_call_id="call_1"),
            ],
            "mode": "edit",
        }

        # Mock turn context and executor invocation to capture injected system message
        captured_messages = []

        class MockExecutor:
            def bind_tools(self, tools):
                return self

            async def ainvoke(self, messages):
                captured_messages.extend(messages)
                return AIMessage(content="I have diagnosed the error and fixed the missing name.")

        mock_config = {
            "configurable": {
                "workspace_context": {"execution_target": "web"},
            }
        }

        async def mock_invoke(node, m, msgs):
            return await m.ainvoke(msgs)

        with patch("agent.graph.nodes._model_for_turn", return_value=MockExecutor()), \
             patch("agent.graph.nodes.get_turn_context", return_value=None), \
             patch("agent.graph.nodes._invoke_model", side_effect=mock_invoke), \
             patch("agent.mcp.get_mcp_tools", return_value=[]):
            import asyncio
            response = asyncio.run(call_model(state, mock_config))

        self.assertIn("messages", response)
        # Check that captured messages contain the self-healing instruction
        system_content = captured_messages[0].content
        self.assertIn("SELF-HEALING RECOVERY MODE ACTIVE", system_content)
        self.assertIn("TS2304 Cannot find name 'foo'", system_content)


if __name__ == "__main__":
    unittest.main()
