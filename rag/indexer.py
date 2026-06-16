"""
Compass RAG — Codebase Indexer.

Traverses the workspace, chunks source files with code-aware splitting,
and indexes them into a local ChromaDB vector store for semantic search.

Features:
  - Incremental indexing: only re-indexes files that have changed (by mtime).
  - Stale cleanup: removes chunks for deleted or renamed files.
  - Duplicate prevention: deletes old chunks before re-indexing modified files.
"""

import json
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

from dotenv import load_dotenv
from langchain_chroma import Chroma
from langchain_core.documents import Document
from langchain_openai import OpenAIEmbeddings

from rag.chunker import chunk_file

load_dotenv()

# Embedding configuration mirroring memory_tool
_embeddings = OpenAIEmbeddings(
    model="nvidia/llama-nemotron-embed-vl-1b-v2:free",
    base_url="https://openrouter.ai/api/v1",
    api_key=os.environ.get("OPENROUTER_API_KEY", ""),
    check_embedding_ctx_length=False,
    chunk_size=16
)

# Configuration
WORKSPACE_DIR = os.getcwd()  # Default to cwd
CHROMA_PERSIST_DIR = os.path.join(WORKSPACE_DIR, ".compass", "chroma")
INDEX_STATE_FILE = os.path.join(WORKSPACE_DIR, ".compass", "index_state.json")

# Directories to ignore during traversal
IGNORE_DIRS = {".git", ".venv", "venv", "__pycache__", ".compass", "node_modules", ".antigravitycli"}


@dataclass
class IndexStats:
    """Statistics from an indexing run."""
    files_scanned: int = 0
    files_indexed: int = 0
    files_skipped: int = 0
    files_removed: int = 0
    chunks_added: int = 0
    chunks_removed: int = 0
    elapsed_seconds: float = 0.0
    errors: List[str] = field(default_factory=list)


def load_index_state() -> dict:
    """Load the index state holding file modification timestamps."""
    if os.path.exists(INDEX_STATE_FILE):
        try:
            with open(INDEX_STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            print(f"Error loading index state: {e}")
            return {}
    return {}


def save_index_state(state: dict):
    """Save the index state."""
    os.makedirs(os.path.dirname(INDEX_STATE_FILE), exist_ok=True)
    with open(INDEX_STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=4)


def is_text_file(filepath: str) -> bool:
    """Basic check if a file is likely to be text-based."""
    valid_extensions = {
        ".py", ".js", ".ts", ".jsx", ".tsx", ".md", ".txt", ".html", ".css",
        ".json", ".yml", ".yaml", ".toml", ".ini", ".c", ".cpp", ".h", ".hpp",
        ".java", ".go", ".rs", ".rb", ".php", ".sh", ".bash", ".zsh", ".cs",
        ".env", ".cfg", ".conf", ".xml", ".sql", ".graphql", ".proto",
    }
    _, ext = os.path.splitext(filepath)
    return ext.lower() in valid_extensions


def _delete_chunks_by_source(vector_store: Chroma, source_path: str) -> int:
    """
    Delete all chunks from ChromaDB that have a matching 'source' metadata field.
    Returns the number of chunks deleted.
    """
    try:
        # Query for document IDs matching this source
        results = vector_store.get(where={"source": source_path})
        ids = results.get("ids", [])
        if ids:
            vector_store.delete(ids=ids)
            return len(ids)
    except Exception:
        pass
    return 0


def index_workspace(workspace_path: str = WORKSPACE_DIR) -> IndexStats:
    """
    Traverse the workspace, chunk modified files, and index them into ChromaDB.

    Returns an IndexStats dataclass with detailed statistics about the run.
    """
    start_time = time.time()
    stats = IndexStats()

    state = load_index_state()
    new_state = {}

    documents_to_index: List[Document] = []
    modified_files: List[str] = []  # files that need re-indexing

    # ── Phase 1: Traverse and collect changed files ─────────────────────────
    for root, dirs, files in os.walk(workspace_path):
        # Modify dirs in-place to ignore specified directories
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]

        for file in files:
            filepath = os.path.join(root, file)

            if not is_text_file(filepath):
                continue

            stats.files_scanned += 1

            try:
                mtime = os.path.getmtime(filepath)

                # Check for incremental updates
                if filepath in state and state[filepath] == mtime:
                    # File hasn't changed — carry forward
                    new_state[filepath] = mtime
                    stats.files_skipped += 1
                    continue

                # Read and chunk the file
                with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()

                chunks = chunk_file(filepath, content)
                # Filter out empty chunks to prevent OpenRouter API errors
                chunks = [c for c in chunks if c.page_content.strip()]
                documents_to_index.extend(chunks)
                modified_files.append(filepath)

                # Update the new state
                new_state[filepath] = mtime
                stats.files_indexed += 1

            except Exception as e:
                stats.errors.append(f"{filepath}: {e}")

    # ── Phase 2: Update ChromaDB ────────────────────────────────────────────
    os.makedirs(CHROMA_PERSIST_DIR, exist_ok=True)
    vector_store = Chroma(
        collection_name="compass_workspace",
        embedding_function=_embeddings,
        persist_directory=CHROMA_PERSIST_DIR
    )

    # Delete old chunks for modified files (prevents duplicates)
    for filepath in modified_files:
        removed = _delete_chunks_by_source(vector_store, filepath)
        stats.chunks_removed += removed

    # Delete chunks for files that no longer exist (stale cleanup)
    stale_files = set(state.keys()) - set(new_state.keys())
    for filepath in stale_files:
        removed = _delete_chunks_by_source(vector_store, filepath)
        stats.chunks_removed += removed
        stats.files_removed += 1

    # Add new/updated chunks
    if documents_to_index:
        vector_store.add_documents(documents=documents_to_index)
        stats.chunks_added = len(documents_to_index)

    # ── Phase 3: Save state ─────────────────────────────────────────────────
    save_index_state(new_state)
    stats.elapsed_seconds = time.time() - start_time

    return stats


if __name__ == "__main__":
    result = index_workspace("d:\\projects\\compass")
    print(f"\nIndexing complete in {result.elapsed_seconds:.1f}s")
    print(f"  Scanned: {result.files_scanned} files")
    print(f"  Indexed: {result.files_indexed} files ({result.chunks_added} chunks)")
    print(f"  Skipped: {result.files_skipped} (unchanged)")
    print(f"  Removed: {result.files_removed} stale files ({result.chunks_removed} chunks)")
    if result.errors:
        print(f"  Errors:  {len(result.errors)}")
        for err in result.errors:
            print(f"    - {err}")
