"""Local run metadata and token accounting."""

from typing import Any, Optional

from langchain_core.runnables import RunnableConfig
from pydantic import BaseModel, Field


class TokenUsageSummary(BaseModel):
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    total_tokens: int = 0
    per_node_breakdown: dict[str, dict[str, int]] = Field(default_factory=dict)
    estimated_cost_usd: float | None = None


class TokenTracker:
    def __init__(self):
        self.summary = TokenUsageSummary()

    def record(self, node_name: str, usage_metadata: dict) -> None:
        if not usage_metadata:
            return
        prompt = usage_metadata.get("input_tokens", usage_metadata.get("prompt_tokens", 0))
        completion = usage_metadata.get("output_tokens", usage_metadata.get("completion_tokens", 0))
        total = usage_metadata.get("total_tokens", prompt + completion)
        self.summary.total_prompt_tokens += prompt
        self.summary.total_completion_tokens += completion
        self.summary.total_tokens += total
        bucket = self.summary.per_node_breakdown.setdefault(
            node_name,
            {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        )
        bucket["prompt_tokens"] += prompt
        bucket["completion_tokens"] += completion
        bucket["total_tokens"] += total

    def get_session_summary(self) -> TokenUsageSummary:
        return self.summary

    def estimate_cost(self, model_name: str) -> float | None:
        if "free" in model_name.lower():
            self.summary.estimated_cost_usd = 0.0
            return 0.0
        pricing = {
            "openai/gpt-4o": (5.0, 15.0),
            "openai/gpt-4o-mini": (0.15, 0.60),
            "anthropic/claude-3.5-sonnet": (3.0, 15.0),
            "anthropic/claude-3-haiku": (0.25, 1.25),
            "google/gemini-1.5-pro": (3.5, 10.5),
            "google/gemini-1.5-flash": (0.075, 0.30),
        }
        rates = next(
            (value for key, value in pricing.items() if key in model_name.lower()),
            None,
        )
        if rates is None:
            return None
        cost = (
            self.summary.total_prompt_tokens / 1_000_000 * rates[0]
            + self.summary.total_completion_tokens / 1_000_000 * rates[1]
        )
        self.summary.estimated_cost_usd = round(cost, 6)
        return cost


def get_run_config(
    thread_id: str,
    user_id: Optional[str] = None,
    session_metadata: Optional[dict[str, Any]] = None,
) -> RunnableConfig:
    """Build the LangGraph configuration used for thread persistence and nodes."""
    metadata = dict(session_metadata or {})
    metadata["thread_id"] = thread_id
    configurable: dict[str, Any] = {"thread_id": thread_id}
    if user_id:
        metadata["user_id"] = user_id
        configurable["user_id"] = user_id
    return {
        "configurable": configurable,
        "metadata": metadata,
        "tags": ["compass-agent", f"thread:{thread_id}"],
    }
