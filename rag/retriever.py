import os
from typing import Optional

from dotenv import load_dotenv
from langchain_chroma import Chroma
from langchain_core.tools import tool
from langchain_openai import OpenAIEmbeddings

load_dotenv()

# Embedding configuration matching indexer.py and memory_tool.py
_embeddings = OpenAIEmbeddings(
    model="nvidia/llama-nemotron-embed-vl-1b-v2:free",
    base_url="https://openrouter.ai/api/v1",
    api_key=os.environ.get("OPENROUTER_API_KEY", ""),
    check_embedding_ctx_length=False,
    chunk_size=16
)

# Configuration
WORKSPACE_DIR = os.getcwd()
CHROMA_PERSIST_DIR = os.path.join(WORKSPACE_DIR, ".compass", "chroma")

_vector_store: Optional[Chroma] = None

def get_vector_store() -> Optional[Chroma]:
    """Lazy initialization of the vector store."""
    global _vector_store
    if _vector_store is None:
        if not os.path.exists(CHROMA_PERSIST_DIR):
            return None
        try:
            _vector_store = Chroma(
                collection_name="compass_workspace",
                embedding_function=_embeddings,
                persist_directory=CHROMA_PERSIST_DIR
            )
        except Exception as e:
            print(f"Error initializing vector store: {e}")
            return None
    return _vector_store

@tool
def codebase_search(query: str, limit: int = 5) -> str:
    """
    Search the local codebase semantically for relevant code snippets or text.
    
    Use this tool when you need to find where a specific concept, function, class, 
    or feature is implemented in the project, but you don't know the exact file path or keyword.
    This performs a vector similarity search across all indexed files.
    
    Args:
        query: A natural language description of what you are looking for.
        limit: Max number of chunks to return (default 5).
    """
    vstore = get_vector_store()
    if vstore is None:
        return "Error: Codebase index not found in .compass/chroma. Please run the indexer first."
        
    try:
        results = vstore.similarity_search(query, k=limit)
        
        if not results:
            return f"No relevant code found for query: '{query}'"
            
        formatted_results = []
        for i, doc in enumerate(results, 1):
            source = doc.metadata.get("source", "Unknown Source")
            
            # Convert absolute path to relative path for cleaner output
            if source.startswith(WORKSPACE_DIR):
                source = os.path.relpath(source, WORKSPACE_DIR)
                
            formatted_results.append(f"--- Result {i} | Source: {source} ---\n{doc.page_content}\n")
            
        return "\n".join(formatted_results)
    
    except Exception as e:
        return f"Error performing semantic search: {str(e)}"
