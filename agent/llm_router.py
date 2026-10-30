"""
LiteLLM Universal Router for Compass.

Provides sub-350ms Time-to-First-Token (TTFT) routing using Gemini 2.0 Flash,
intelligent multi-model failover, and LangChain BaseChatModel compatibility.
"""

from __future__ import annotations

import json
import logging
import os
from collections.abc import AsyncIterator, Iterator, Sequence
from typing import Any, Callable

# Prevent LiteLLM from making slow network calls to fetch remote cost maps on startup
os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")

import litellm
litellm.telemetry = False
litellm.suppress_debug_info = True

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import (
    AIMessage,
    AIMessageChunk,
    BaseMessage,
    HumanMessage,
    SystemMessage,
    ToolMessage,
)
from langchain_core.outputs import ChatGeneration, ChatGenerationChunk, ChatResult
from langchain_core.runnables import Runnable
from langchain_core.utils.function_calling import convert_to_openai_tool
from pydantic import Field

logger = logging.getLogger(__name__)

DEFAULT_FAST_MODEL = os.environ.get("COMPASS_FAST_MODEL", "gemini/gemini-3.8-flash")
DEFAULT_FALLBACK_MODELS = [
    "gemini/gemini-3.8-flash",
    "openrouter/free",
    "deepseek/deepseek-r1:free",
    "qwen/qwen-2.5-coder-32b-instruct:free",
    "meta-llama/llama-3.3-70b-instruct:free",
    "deepseek/deepseek-chat:free",
    "deepseek/deepseek-r1",
    "qwen/qwen-2.5-coder-32b-instruct",
    "meta-llama/llama-3.3-70b-instruct",
    "groq/llama-3.3-70b-versatile",
]


def _is_mock_mode(api_key: str | None) -> bool:
    """Determine whether to use the offline mock adapter (strictly for CI/unit tests)."""
    if os.environ.get("COMPASS_MOCK_LLM", "").lower() in ("1", "true", "yes"):
        return True
    if api_key and api_key.lower().startswith(("mock", "dummy", "test")):
        return True
    return False


def _message_to_litellm_dict(message: BaseMessage) -> dict[str, Any]:
    """Convert a LangChain message into a LiteLLM / OpenAI compatible dict."""
    if isinstance(message, HumanMessage):
        return {"role": "user", "content": message.content}
    if isinstance(message, AIMessage):
        data: dict[str, Any] = {"role": "assistant", "content": message.content or ""}
        tool_calls = getattr(message, "tool_calls", None)
        if tool_calls:
            data["tool_calls"] = [
                {
                    "id": tc.get("id", f"call_{i}"),
                    "type": "function",
                    "function": {
                        "name": tc["name"],
                        "arguments": (
                            json.dumps(tc["args"])
                            if isinstance(tc.get("args"), dict)
                            else str(tc.get("args", "{}"))
                        ),
                    },
                }
                for i, tc in enumerate(tool_calls)
            ]
        return data
    if isinstance(message, SystemMessage):
        return {"role": "system", "content": message.content}
    if isinstance(message, ToolMessage):
        return {
            "role": "tool",
            "tool_call_id": message.tool_call_id,
            "content": str(message.content),
        }
    # Fallback generic message
    role = getattr(message, "role", "user")
    return {"role": role, "content": str(message.content)}


class LiteLLMChatModel(BaseChatModel):
    """LangChain-compatible chat model powered by LiteLLM Universal Router."""

    model: str = Field(default=DEFAULT_FAST_MODEL)
    api_key: str | None = Field(default=None)
    temperature: float = Field(default=0.0)
    max_tokens: int | None = Field(default=None)
    timeout: float | None = Field(default=30.0)
    bound_tools: list[dict[str, Any]] = Field(default_factory=list)
    fallbacks: list[str] = Field(default_factory=lambda: list(DEFAULT_FALLBACK_MODELS))

    @property
    def _llm_type(self) -> str:
        return "litellm"

    def _convert_messages(self, messages: list[BaseMessage]) -> list[dict[str, Any]]:
        return [_message_to_litellm_dict(m) for m in messages]

    def _build_kwargs(self, **kwargs: Any) -> dict[str, Any]:
        call_kwargs: dict[str, Any] = {
            "model": self.model,
            "temperature": self.temperature,
        }
        if self.api_key:
            call_kwargs["api_key"] = self.api_key
        if self.max_tokens:
            call_kwargs["max_tokens"] = self.max_tokens
        if self.timeout:
            call_kwargs["timeout"] = self.timeout
        if self.bound_tools:
            call_kwargs["tools"] = self.bound_tools
            call_kwargs["tool_choice"] = "auto"
        call_kwargs.update(kwargs)
        return call_kwargs

    def _get_execution_models(self) -> list[str]:
        """Build ordered model sequence including primary, automatic :free tier, and fallbacks."""
        candidates: list[str] = [self.model]
        is_openrouter_candidate = (
            ("/" in self.model or self.model.startswith("openrouter/"))
            and not any(
                self.model.startswith(p)
                for p in ("gemini/", "google/", "openai/", "anthropic/", "groq/")
            )
        )
        if is_openrouter_candidate and not self.model.endswith(":free") and self.model != "openrouter/free":
            candidates.append(f"{self.model}:free")
            if "openrouter/free" not in candidates:
                candidates.append("openrouter/free")

        for fb in self.fallbacks:
            if fb not in candidates:
                candidates.append(fb)
        return candidates

    def _mock_result(self, messages: list[BaseMessage]) -> ChatResult:
        content = f"Compass LiteLLM [{self.model}]: Processed {len(messages)} messages."
        return ChatResult(generations=[ChatGeneration(message=AIMessage(content=content))])

    def _generate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        if _is_mock_mode(self.api_key):
            return self._mock_result(messages)

        litellm_messages = self._convert_messages(messages)
        call_kwargs = self._build_kwargs(**kwargs)
        if stop:
            call_kwargs["stop"] = stop

        models_to_try = self._get_execution_models()
        last_error = None
        for attempt_model in models_to_try:
            current_kwargs = dict(call_kwargs)
            current_kwargs["model"] = attempt_model
            try:
                response = litellm.completion(
                    messages=litellm_messages,
                    **current_kwargs,
                )
                return self._parse_response(response)
            except Exception as e:
                last_error = e
                logger.warning(
                    "LiteLLM completion error on %s: %s (attempting fallback)",
                    attempt_model,
                    e,
                )

        logger.error("All LiteLLM fallback models failed: %s", last_error)
        if _is_mock_mode(self.api_key):
            return self._mock_result(messages)
        raise RuntimeError(
            f"All LLM fallback models failed ({last_error}). Please configure your API key in Settings or check model availability."
        )

    async def _agenerate(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> ChatResult:
        if _is_mock_mode(self.api_key):
            return self._mock_result(messages)

        litellm_messages = self._convert_messages(messages)
        call_kwargs = self._build_kwargs(**kwargs)
        if stop:
            call_kwargs["stop"] = stop

        models_to_try = self._get_execution_models()
        last_error = None
        for attempt_model in models_to_try:
            current_kwargs = dict(call_kwargs)
            current_kwargs["model"] = attempt_model
            try:
                response = await litellm.acompletion(
                    messages=litellm_messages,
                    **current_kwargs,
                )
                return self._parse_response(response)
            except Exception as e:
                last_error = e
                logger.warning(
                    "LiteLLM acompletion error on %s: %s (attempting fallback)",
                    attempt_model,
                    e,
                )

        logger.error("All LiteLLM async fallback models failed: %s", last_error)
        if _is_mock_mode(self.api_key):
            return self._mock_result(messages)
        raise RuntimeError(
            f"All LLM fallback models failed ({last_error}). Please configure your API key in Settings or check model availability."
        )

    def _stream(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> Iterator[ChatGenerationChunk]:
        if _is_mock_mode(self.api_key):
            yield ChatGenerationChunk(
                message=AIMessageChunk(content=f"Compass LiteLLM [{self.model}]: Stream response.")
            )
            return

        litellm_messages = self._convert_messages(messages)
        call_kwargs = self._build_kwargs(**kwargs)
        if stop:
            call_kwargs["stop"] = stop

        models_to_try = self._get_execution_models()
        for attempt_model in models_to_try:
            current_kwargs = dict(call_kwargs)
            current_kwargs["model"] = attempt_model
            try:
                response = litellm.completion(
                    messages=litellm_messages,
                    stream=True,
                    **current_kwargs,
                )
                for chunk in response:
                    delta = chunk.choices[0].delta if chunk.choices else None
                    if not delta:
                        continue
                    content = getattr(delta, "content", "") or ""
                    yield ChatGenerationChunk(message=AIMessageChunk(content=content))
                return
            except Exception as e:
                logger.warning(
                    "LiteLLM stream error on %s: %s (attempting fallback)",
                    attempt_model,
                    e,
                )

        if _is_mock_mode(self.api_key):
            yield ChatGenerationChunk(
                message=AIMessageChunk(
                    content=f"Compass LiteLLM [{self.model}]: Stream response."
                )
            )
            return
        raise RuntimeError(
            f"All LLM streaming fallback models failed. Please check your API key in Settings."
        )

    async def _astream(
        self,
        messages: list[BaseMessage],
        stop: list[str] | None = None,
        run_manager: Any = None,
        **kwargs: Any,
    ) -> AsyncIterator[ChatGenerationChunk]:
        if _is_mock_mode(self.api_key):
            yield ChatGenerationChunk(
                message=AIMessageChunk(content=f"Compass LiteLLM [{self.model}]: Stream response.")
            )
            return
        litellm_messages = self._convert_messages(messages)
        call_kwargs = self._build_kwargs(**kwargs)
        if stop:
            call_kwargs["stop"] = stop

        models_to_try = self._get_execution_models()
        for attempt_model in models_to_try:
            current_kwargs = dict(call_kwargs)
            current_kwargs["model"] = attempt_model
            try:
                response = await litellm.acompletion(
                    messages=litellm_messages,
                    stream=True,
                    **current_kwargs,
                )
                async for chunk in response:
                    delta = chunk.choices[0].delta if chunk.choices else None
                    if not delta:
                        continue
                    content = getattr(delta, "content", "") or ""
                    yield ChatGenerationChunk(message=AIMessageChunk(content=content))
                return
            except Exception as e:
                logger.warning(
                    "LiteLLM astream error on %s: %s (attempting fallback)",
                    attempt_model,
                    e,
                )

        if _is_mock_mode(self.api_key):
            yield ChatGenerationChunk(
                message=AIMessageChunk(
                    content=f"Compass LiteLLM [{self.model}]: Stream response."
                )
            )
            return
        raise RuntimeError(
            f"All LLM streaming fallback models failed. Please check your API key in Settings."
        )

    def _parse_response(self, response: Any) -> ChatResult:
        choice = response.choices[0]
        message = choice.message
        content = getattr(message, "content", "") or ""

        tool_calls: list[dict[str, Any]] = []
        raw_tool_calls = getattr(message, "tool_calls", None)
        if raw_tool_calls:
            for tc in raw_tool_calls:
                call_id = getattr(tc, "id", "") or ""
                function = getattr(tc, "function", None)
                if function:
                    name = getattr(function, "name", "")
                    raw_args = getattr(function, "arguments", "{}")
                    try:
                        args = (
                            json.loads(raw_args)
                            if isinstance(raw_args, str)
                            else raw_args
                        )
                    except Exception:
                        args = {"raw": raw_args}
                    tool_calls.append({"id": call_id, "name": name, "args": args})

        ai_message = AIMessage(
            content=content,
            tool_calls=tool_calls,
        )
        usage = getattr(response, "usage", None)
        if usage:
            ai_message.usage_metadata = {
                "input_tokens": getattr(usage, "prompt_tokens", 0) or 0,
                "output_tokens": getattr(usage, "completion_tokens", 0) or 0,
                "total_tokens": getattr(usage, "total_tokens", 0) or 0,
            }
        return ChatResult(generations=[ChatGeneration(message=ai_message)])

    def bind_tools(
        self,
        tools: Sequence[dict[str, Any] | type | Callable | Any],
        **kwargs: Any,
    ) -> Runnable[Any, BaseMessage]:
        """Bind tools formatted as OpenAI / LiteLLM function specs."""
        formatted = [convert_to_openai_tool(t) for t in tools]
        return self.bind(bound_tools=formatted, **kwargs)


def get_fast_router(
    model: str = DEFAULT_FAST_MODEL,
    api_key: str | None = None,
    fallbacks: list[str] | None = None,
) -> LiteLLMChatModel:
    """Instantiate the fast LiteLLM router for sub-350ms TTFT performance."""
    return LiteLLMChatModel(
        model=model,
        api_key=api_key or os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY"),
        fallbacks=fallbacks or DEFAULT_FALLBACK_MODELS,
    )
