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
from pathlib import Path
from typing import Any

from langchain_openrouter import ChatOpenRouter
from langchain_core.globals import set_llm_cache

from agent.config import settings

_llm_cache_initialized = False

def _init_llm_cache():
    global _llm_cache_initialized
    if _llm_cache_initialized:
        return
    _llm_cache_initialized = True

    _redis_url = os.getenv("COMPASS_REDIS_URL", "redis://localhost:6379")
    try:
        import asyncio
        import concurrent.futures
        import redis
        from langchain_core.caches import InMemoryCache
        from langchain_redis import RedisCache

        def _ping_redis():
            client = redis.Redis.from_url(
                _redis_url, socket_timeout=0.5, socket_connect_timeout=0.3
            )
            return client.ping()

        # Run the blocking ping in a thread to avoid blocking the async event loop
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_ping_redis)
            future.result(timeout=1.0)

        set_llm_cache(RedisCache(redis_url=_redis_url, ttl=3600))
        print(f"[LLM] Redis cache enabled ({_redis_url})")
    except Exception as e:
        from langchain_core.caches import InMemoryCache

        # Don't print the warning if there's no REDIS URL specifically configured to avoid spam
        if "COMPASS_REDIS_URL" in os.environ:
            print(f"[LLM] Warning: Failed to connect to Redis, using in-memory cache. ({e})")
        set_llm_cache(InMemoryCache())


def _get_model_name(role: str) -> str:
    """Helper to fetch the current model name for a role."""
    key = f"model.{role}"
    # Fallback to executor if role not found
    return settings.get(
        key, settings.get("model.executor", "google/gemma-4-31b-it:free")
    )


def llm(role: str = "executor", api_key: str | None = None, provider: str | None = None, model: str | None = None) -> Any:
    """
    Get an LLM instance for a specific agent role.

    Args:
        role: One of 'planner', 'executor', 'recovery', 'summarizer',
              'guardrails', 'evaluator'.
              Defaults to 'executor' for backward compatibility.
        api_key: Optional API key provided directly (overrides settings).
        provider: Optional provider name (overrides settings).
        model: Optional model name (overrides settings).

    Returns:
        A Langchain ChatModel instance configured for the given role.
    """
    _init_llm_cache()
    
    if not provider:
        provider = settings.get("llm_provider", "openrouter")
    provider = provider.lower()
    
    if model:
        model_name = model
    else:
        model_name = _get_model_name(role)
    
    if not api_key:
        api_key = settings.get("llm_api_key") or settings.get("api_key")
    
    if provider == "openai":
        if not api_key:
            api_key = os.environ.get("OPENAI_API_KEY")
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(api_key=api_key, model=model_name)
        
    elif provider == "anthropic":
        if not api_key:
            api_key = os.environ.get("ANTHROPIC_API_KEY")
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(api_key=api_key, model_name=model_name)
        
    elif provider == "groq":
        if not api_key:
            api_key = os.environ.get("GROQ_API_KEY")
        from langchain_groq import ChatGroq
        return ChatGroq(api_key=api_key, model_name=model_name)
        
    elif provider == "gemini":
        if not api_key:
            api_key = os.environ.get("GOOGLE_API_KEY")
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(google_api_key=api_key, model=model_name)
        
    # Default to openrouter
    if not api_key:
        api_key = os.environ.get("OPENROUTER_API_KEY")
    from langchain_openrouter import ChatOpenRouter
    return ChatOpenRouter(api_key=api_key, model=model_name)

