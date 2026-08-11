"""Safe discovery and explicit loading of repository custom tools."""

from __future__ import annotations

import hashlib
import importlib.util
import inspect
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from langchain_core.tools import BaseTool


@dataclass(frozen=True)
class CustomToolCandidate:
    """A Python file that may contain custom tools, without importing it."""

    source_path: Path
    scope: str


def scan_custom_tool_files(workspace_root: Path) -> list[CustomToolCandidate]:
    """List custom-tool Python files without executing repository code."""

    search = [
        (Path.home() / ".compass" / "tools", "global"),
        (workspace_root / ".compass" / "tools", "workspace"),
    ]
    return [
        CustomToolCandidate(path.resolve(), scope)
        for directory, scope in search
        if directory.is_dir()
        for path in sorted(directory.glob("*.py"))
        if path.name != "__init__.py"
    ]


def load_approved_custom_tools(
    candidates: Iterable[CustomToolCandidate],
    approved_paths: Iterable[str | Path],
    *,
    reserved_names: Iterable[str] | None = None,
) -> list[BaseTool]:
    """Import tools only from explicitly approved candidate paths.

    Duplicate names are rejected so custom code cannot shadow built-in tools or
    another approved custom tool.
    """

    approved = {str(Path(path).expanduser().resolve()) for path in approved_paths}
    known_names = set(reserved_names or ())
    loaded: list[BaseTool] = []

    for candidate in candidates:
        source_path = candidate.source_path.resolve()
        if str(source_path) not in approved:
            continue

        digest = hashlib.sha256(str(source_path).encode("utf-8")).hexdigest()[:16]
        module_name = f"compass_custom_tools_{digest}"
        spec = importlib.util.spec_from_file_location(module_name, source_path)
        if spec is None or spec.loader is None:
            raise ImportError(f"Cannot load custom tool module: {source_path}")

        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)

        for _, value in inspect.getmembers(module):
            if not isinstance(value, BaseTool):
                continue
            if value.name in known_names:
                raise ValueError(f"Duplicate tool name: {value.name}")
            known_names.add(value.name)
            loaded.append(value)

    return loaded
