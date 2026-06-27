import os
from langchain_core.tools import tool
from tavily import TavilyClient
@tool
def web_search(query: str, max_results: int = 5) -> str:
    """Search the web for current information.

    Uses Tavily Search if TAVILY_API_KEY is configured and the tavily library
    is installed, otherwise falls back to DuckDuckGo Search.

    Args:
        query: The search query.
        max_results: Max search results to return (default 5).
    """
    # 1. Try Tavily Search if key is configured
    api_key = os.getenv("TAVILY_API_KEY")
    if api_key:
        try:
            
            tavily = TavilyClient(api_key=api_key)
            response = tavily.search(query=query, max_results=max_results)
            results = response.get("results", [])
            if results:
                formatted = []
                for r in results:
                    formatted.append(
                        f"Title: {r.get('title', 'N/A')}\n"
                        f"URL: {r.get('url', 'N/A')}\n"
                        f"Snippet: {r.get('content', 'N/A')}\n"
                    )
                return "Web search results (via Tavily):\n\n" + "\n".join(formatted)
        except ImportError:
            pass
        except Exception:
            pass
    try:
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
        if not results:
            return f"No results found for '{query}'"

        formatted = []
        for r in results:
            formatted.append(
                f"Title: {r.get('title', 'N/A')}\n"
                f"URL: {r.get('href', 'N/A')}\n"
                f"Snippet: {r.get('body', 'N/A')}\n"
            )
        return "Web search results (via DuckDuckGo):\n\n" + "\n".join(formatted)
    except Exception as e:
        return f"Error performing web search: {e}"
