import os
import logging
from typing import Optional, Dict, Any
from pydantic import BaseModel
from langchain_core.runnables import RunnableConfig

from agent.config import settings

logger = logging.getLogger(__name__)


class TokenUsageSummary(BaseModel):
    """Aggregated token usage for a session."""
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    total_tokens: int = 0
    per_node_breakdown: Dict[str, Dict[str, int]] = {}
    estimated_cost_usd: Optional[float] = None


class TokenTracker:
    """Tracks cumulative token usage across all LLM calls in a session."""
    
    def __init__(self):
        self.summary = TokenUsageSummary()

    def record(self, node_name: str, usage_metadata: dict) -> None:
        """Record token usage from a single LLM invocation."""
        if not usage_metadata:
            return
            
        prompt = usage_metadata.get("input_tokens", usage_metadata.get("prompt_tokens", 0))
        completion = usage_metadata.get("output_tokens", usage_metadata.get("completion_tokens", 0))
        total = usage_metadata.get("total_tokens", prompt + completion)

        self.summary.total_prompt_tokens += prompt
        self.summary.total_completion_tokens += completion
        self.summary.total_tokens += total

        if node_name not in self.summary.per_node_breakdown:
            self.summary.per_node_breakdown[node_name] = {
                "prompt_tokens": 0,
                "completion_tokens": 0,
                "total_tokens": 0
            }

        self.summary.per_node_breakdown[node_name]["prompt_tokens"] += prompt
        self.summary.per_node_breakdown[node_name]["completion_tokens"] += completion
        self.summary.per_node_breakdown[node_name]["total_tokens"] += total

    def get_session_summary(self) -> TokenUsageSummary:
        """Return total + per-node breakdown."""
        return self.summary

    def estimate_cost(self, model_name: str) -> Optional[float]:
        """
        Rough cost estimate based on known model pricing.
        Values are per 1M tokens.
        """
        # Very rough approximation for free models
        if "free" in model_name.lower():
            self.summary.estimated_cost_usd = 0.0
            return 0.0
            
        pricing_per_1m = {
            "openai/gpt-4o": {"prompt": 5.0, "completion": 15.0},
            "openai/gpt-4o-mini": {"prompt": 0.15, "completion": 0.60},
            "anthropic/claude-3.5-sonnet": {"prompt": 3.0, "completion": 15.0},
            "anthropic/claude-3-haiku": {"prompt": 0.25, "completion": 1.25},
            "google/gemini-1.5-pro": {"prompt": 3.5, "completion": 10.5},
            "google/gemini-1.5-flash": {"prompt": 0.075, "completion": 0.30},
        }

        # Check for partial matches (e.g. anthropic/claude-3.5-sonnet matches anthropic/claude-3.5-sonnet-20241022)
        matched_pricing = None
        for key, rates in pricing_per_1m.items():
            if key in model_name.lower():
                matched_pricing = rates
                break

        if not matched_pricing:
            return None

        prompt_cost = (self.summary.total_prompt_tokens / 1_000_000) * matched_pricing["prompt"]
        completion_cost = (self.summary.total_completion_tokens / 1_000_000) * matched_pricing["completion"]
        
        total_cost = prompt_cost + completion_cost
        self.summary.estimated_cost_usd = round(total_cost, 6)
        return total_cost


def configure_tracing() -> None:
    """Configure LangSmith tracing from environment variables."""
    enabled = settings.get("llmops.tracing_enabled", True)
    
    if not enabled:
        os.environ["LANGCHAIN_TRACING_V2"] = "false"
        return

    # Check if API key is provided
    api_key = os.environ.get("LANGCHAIN_API_KEY")
    if not api_key:
        logger.info("LangSmith tracing is enabled in config but LANGCHAIN_API_KEY is not set. Tracing will be disabled.")
        os.environ["LANGCHAIN_TRACING_V2"] = "false"
        return

    # Enable tracing
    os.environ["LANGCHAIN_TRACING_V2"] = "true"
    
    # Set project name if not already set
    if "LANGCHAIN_PROJECT" not in os.environ:
        project_name = settings.get("llmops.project_name", "compass")
        os.environ["LANGCHAIN_PROJECT"] = project_name
        
    logger.info(f"LangSmith tracing enabled for project: {os.environ.get('LANGCHAIN_PROJECT')}")


def get_run_config(
    thread_id: str,
    user_id: Optional[str] = None,
    session_metadata: Optional[Dict[str, Any]] = None,
) -> RunnableConfig:
    """Build a RunnableConfig with LangSmith metadata."""
    metadata = session_metadata or {}
    
    # Ensure thread_id is at the top level for LangSmith UI mapping
    metadata["thread_id"] = thread_id
    
    if user_id:
        metadata["user_id"] = user_id

    # The configurable dict is used by LangGraph for checkpointer routing
    configurable = {"thread_id": thread_id}
    
    if user_id:
        configurable["user_id"] = user_id

    return {
        "configurable": configurable,
        "metadata": metadata,
        "tags": ["compass-agent", f"thread:{thread_id}"]
    }


def is_tracing_active() -> bool:
    """Check if LangSmith tracing is configured and active."""
    return os.environ.get("LANGCHAIN_TRACING_V2", "").lower() == "true"
