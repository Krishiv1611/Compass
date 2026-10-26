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
from pathlib import Path
from typing import List

from dotenv import load_dotenv
from langchain_core.documents import Document

from agent.rag.chunker import chunk_file
from agent.config import settings
from agent.rag.vector_store import (
    WORKSPACE_DIR,
    delete_chunks_by_filter,
    get_vector_store,
)

load_dotenv()

# Directories to ignore during traversal
IGNORE_DIRS = {
    ".git",
    ".venv",
    "venv",
    "__pycache__",
    ".compass",
    "node_modules",
    ".antigravitycli",
    "dist",
    "build",
    "target",
    ".next",
    ".cache",
    "coverage",
}

_DENIED_EXACT_NAMES = {
    ".env",
    ".npmrc",
    ".pypirc",
    ".netrc",
    "credentials.json",
    "credentials.yml",
    "credentials.yaml",
    "secrets.json",
    "secrets.yml",
    "secrets.yaml",
    "id_rsa",
    "id_dsa",
    "id_ecdsa",
    "id_ed25519",
}
_DENIED_SUFFIXES = (".pem", ".key", ".p12", ".pfx", ".jks", ".keystore")


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


def load_index_state(state_file: str) -> dict:
    """Load the versioned index state, upgrading the legacy flat format."""
    if os.path.exists(state_file):
        try:
            with open(state_file, "r", encoding="utf-8") as f:
                state = json.load(f)
                if "files" not in state:
                    return {"context_version": None, "files": state}
                return state
        except Exception as e:
            print(f"Error loading index state: {e}")
    return {"context_version": None, "files": {}}


def save_index_state(state: dict, state_file: str):
    """Save the index state."""
    os.makedirs(os.path.dirname(state_file), exist_ok=True)
    with open(state_file, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=4)


def is_text_file(filepath: str) -> bool:
    """Basic check if a file is likely to be text-based."""
    valid_extensions = {
        ".py",
        ".js",
        ".ts",
        ".jsx",
        ".tsx",
        ".md",
        ".txt",
        ".html",
        ".css",
        ".json",
        ".yml",
        ".yaml",
        ".toml",
        ".ini",
        ".c",
        ".cpp",
        ".h",
        ".hpp",
        ".java",
        ".go",
        ".rs",
        ".rb",
        ".php",
        ".sh",
        ".bash",
        ".zsh",
        ".cs",
        ".env",
        ".cfg",
        ".conf",
        ".xml",
        ".sql",
        ".graphql",
        ".proto",
    }
    _, ext = os.path.splitext(filepath)
    return ext.lower() in valid_extensions


def should_index_path(path: Path) -> bool:
    """Reject secrets, VCS internals, caches, and generated output."""
    parts = tuple(part.lower() for part in path.parts)
    if any(part in IGNORE_DIRS for part in parts[:-1]):
        return False
    if len(parts) >= 2 and parts[0] == ".compass" and parts[1] == "checkpoints":
        return False
    name = path.name.lower()
    if name in _DENIED_EXACT_NAMES or name.endswith(_DENIED_SUFFIXES):
        return False
    if name.endswith(".env") or name.startswith(".env."):
        return False
    if any(term in name for term in ("credential", "secret", "api_key", "token")):
        return False
    return is_text_file(str(path))


def _delete_chunks_by_source(
    source_path: str,
    project_id: str | None,
    provider_config: dict | None = None,
) -> int:
    """Delete all chunks for a source path from ChromaDB."""
    where = {"source": source_path}
    if project_id:
        where["project_id"] = project_id
    return delete_chunks_by_filter(where, provider_config=provider_config)


def index_workspace(
    workspace_path: str = WORKSPACE_DIR,
    *,
    project_id: str,
    context_version: str,
    provider_config: dict | None = None,
) -> IndexStats:
    """
    Traverse the workspace, chunk modified files, and index them into ChromaDB.

    Returns an IndexStats dataclass with detailed statistics about the run.
    """
    start_time = time.time()
    stats = IndexStats()

    if not project_id:
        raise ValueError("project_id is required for workspace indexing")
    if not context_version:
        raise ValueError("context_version is required for workspace indexing")

    workspace_path = os.path.abspath(workspace_path)
    state_file = os.path.join(workspace_path, ".compass", "index_state.json")
    stored_state = load_index_state(state_file)
    state = stored_state.get("files", {})
    version_changed = bool(
        context_version
        and stored_state.get("context_version") != context_version
    )
    if version_changed:
        if not project_id:
            stats.errors.append(
                "Cannot rebuild a versioned index without a project_id."
            )
            stats.elapsed_seconds = time.time() - start_time
            return stats
        stats.chunks_removed += delete_chunks_by_filter(
            {"source_type": "workspace", "project_id": project_id},
            provider_config=provider_config,
        )
        state = {}
    new_state = {}

    documents_to_index: List[Document] = []
    modified_files: List[str] = []
    chunk_size = int(settings.get("rag.chunk_size", 1000))

    # Phase 1: Traverse and collect changed files
    for root, dirs, files in os.walk(workspace_path):
        dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]

        for file in files:
            filepath = os.path.join(root, file)

            relative_candidate = Path(filepath).relative_to(workspace_path)
            if not should_index_path(relative_candidate):
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

                relative_path = os.path.relpath(filepath, workspace_path).replace("\\", "/")
                chunks = chunk_file(
                    relative_path,
                    content,
                    metadata={
                        "source_type": "workspace",
                        "project_id": project_id,
                        "context_version": context_version,
                    },
                    chunk_size=chunk_size,
                )
                chunks = [c for c in chunks if c.page_content.strip()]
                documents_to_index.extend(chunks)
                modified_files.append(filepath)

                new_state[filepath] = mtime
                stats.files_indexed += 1

            except Exception as e:
                stats.errors.append(f"{filepath}: {e}")

    # Phase 2: Update ChromaDB / PGVector
    try:
        vector_store = get_vector_store(create=True, provider_config=provider_config)
    except Exception as exc:
        stats.errors.append(f"Vector store unavailable: {exc}")
        stats.elapsed_seconds = time.time() - start_time
        return stats
    if vector_store is None:
        stats.errors.append("Vector store could not be initialized.")
        stats.elapsed_seconds = time.time() - start_time
        return stats

    for filepath in modified_files:
        relative_path = os.path.relpath(filepath, workspace_path).replace("\\", "/")
        stats.chunks_removed += _delete_chunks_by_source(
            relative_path, project_id, provider_config
        )

    stale_files = set(state.keys()) - set(new_state.keys())
    for filepath in stale_files:
        relative_path = os.path.relpath(filepath, workspace_path).replace("\\", "/")
        stats.chunks_removed += _delete_chunks_by_source(
            relative_path, project_id, provider_config
        )
        stats.files_removed += 1

    if documents_to_index:
        vector_store.add_documents(documents=documents_to_index)
        stats.chunks_added = len(documents_to_index)

    # Phase 3: Save state
    save_index_state(
        {"context_version": context_version, "files": new_state},
        state_file,
    )
    stats.elapsed_seconds = time.time() - start_time

    return stats


def index_workspace_if_enabled(
    workspace_path: str,
    project_id: str,
    context_version: str,
    indexer=None,
    provider_config: dict | None = None,
) -> IndexStats | None:
    """Run post-import indexing only when the user enabled it."""
    if not settings.get("rag.auto_index", False):
        return None
    runner = indexer or index_workspace
    return runner(
        workspace_path,
        project_id=project_id,
        context_version=context_version,
        provider_config=provider_config,
    )


if __name__ == "__main__":
    from agent.workspace import discover_local_workspace

    identity = discover_local_workspace(Path.cwd())
    result = index_workspace(
        str(identity.root),
        project_id=identity.project_id or "",
        context_version=identity.context_version or "",
    )
    print(f"\nIndexing complete in {result.elapsed_seconds:.1f}s")
    print(f"  Scanned: {result.files_scanned} files")
    print(f"  Indexed: {result.files_indexed} files ({result.chunks_added} chunks)")
    print(f"  Skipped: {result.files_skipped} (unchanged)")
    print(
        f"  Removed: {result.files_removed} stale files ({result.chunks_removed} chunks)"
    )
    if result.errors:
        print(f"  Errors:  {len(result.errors)}")
        for err in result.errors:
            print(f"    - {err}")
