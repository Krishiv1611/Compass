"""
Compass RAG - Codebase Indexer.

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
from typing import List

from dotenv import load_dotenv
from langchain_core.documents import Document

from rag.chunker import chunk_file
from rag.vector_store import WORKSPACE_DIR, delete_chunks_by_filter, get_vector_store

load_dotenv()

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


def _delete_chunks_by_source(source_path: str) -> int:
    """Delete all chunks for a source path from ChromaDB."""
    return delete_chunks_by_filter({"source": source_path})


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
    modified_files: List[str] = []

    # Phase 1: Traverse and collect changed files
    for root, dirs, files in os.walk(workspace_path):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]

        for file in files:
            filepath = os.path.join(root, file)

            if not is_text_file(filepath):
                continue

            stats.files_scanned += 1

            try:
                mtime = os.path.getmtime(filepath)

                if filepath in state and state[filepath] == mtime:
                    new_state[filepath] = mtime
                    stats.files_skipped += 1
                    continue

                with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()

                chunks = chunk_file(
                    filepath,
                    content,
                    metadata={"source_type": "workspace"},
                )
                chunks = [c for c in chunks if c.page_content.strip()]
                documents_to_index.extend(chunks)
                modified_files.append(filepath)

                new_state[filepath] = mtime
                stats.files_indexed += 1

            except Exception as e:
                stats.errors.append(f"{filepath}: {e}")

    # Phase 2: Update ChromaDB
    vector_store = get_vector_store(create=True)
    if vector_store is None:
        stats.errors.append("Vector store could not be initialized.")
        stats.elapsed_seconds = time.time() - start_time
        return stats

    for filepath in modified_files:
        stats.chunks_removed += _delete_chunks_by_source(filepath)

    stale_files = set(state.keys()) - set(new_state.keys())
    for filepath in stale_files:
        stats.chunks_removed += _delete_chunks_by_source(filepath)
        stats.files_removed += 1

    if documents_to_index:
        vector_store.add_documents(documents=documents_to_index)
        stats.chunks_added = len(documents_to_index)

    # Phase 3: Save state
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