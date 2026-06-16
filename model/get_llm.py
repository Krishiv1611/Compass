"""
Compass — LLM Configuration.

Provides a role-based LLM factory with a MODELS registry.
Each agent role gets its own LLM instance, independently swappable.

Usage:
    from model.get_llm import llm, MODELS

    planner  = llm("planner")
    executor = llm("executor")

    # Swap a model later:
    MODELS["planner"] = "deepseek/deepseek-r1:free"
"""

import os

from dotenv import load_dotenv
from langchain_openrouter import ChatOpenRouter

load_dotenv()

# ─── Model Registry ─────────────────────────────────────────────────────────────
# Each agent role maps to an OpenRouter model name.
# Change any entry independently without touching other code.
MODELS: dict[str, str] = {
    "planner":    "google/gemma-4-31b-it:free",
    "executor":   "google/gemma-4-31b-it:free",
    "recovery":   "google/gemma-4-31b-it:free",
    "summarizer": "google/gemma-4-31b-it:free",
}


def llm(role: str = "executor") -> ChatOpenRouter:
    """
    Get an LLM instance for a specific agent role.

    Args:
        role: One of 'planner', 'executor', 'recovery', 'summarizer'.
              Defaults to 'executor' for backward compatibility.

    Returns:
        A ChatOpenRouter instance configured for the given role.
    """
    model_name = MODELS.get(role, MODELS["executor"])
    return ChatOpenRouter(
        api_key=os.getenv("OPENROUTER_API_KEY"),
        model=model_name,
    )