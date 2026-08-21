"""Safely remove a narrow, explicit set of generated Compass files."""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from pathlib import Path


PROTECTED_COMPONENTS = frozenset(
    {
        ".git",
        ".env",
        ".compass",
        ".cache",
        "node_modules",
        ".venv",
        "uploads",
        "workspaces",
        "checkpoints",
    }
)
CACHE_DIRECTORY_NAMES = frozenset({"__pycache__", ".pytest_cache"})
FRONTEND_OUTPUTS = (Path("frontend") / ".vite", Path("frontend") / "dist")


def _resolved_descendant(path: Path, workspace: Path) -> Path | None:
    """Return a safe relative path, rejecting symlinks and protected areas."""
    try:
        relative = path.resolve().relative_to(workspace)
    except (OSError, ValueError):
        return None
    if not relative.parts or any(
        part in PROTECTED_COMPONENTS or part.startswith(".venv.")
        for part in relative.parts
    ):
        return None
    return relative


def _generated_paths(workspace: Path) -> list[Path]:
    """Return only allowlisted generated descendants, in stable display order."""
    selected: dict[Path, Path] = {}

    def add(path: Path) -> None:
        relative = _resolved_descendant(path, workspace)
        if relative is not None and path.exists():
            selected[relative] = path

    frontend_root = workspace / "frontend"
    for current, directory_names, file_names in os.walk(
        workspace, topdown=True, followlinks=False
    ):
        directory = Path(current)
        relative = (
            Path(".")
            if directory == workspace
            else _resolved_descendant(directory, workspace)
        )
        if relative is None:
            directory_names[:] = []
            continue
        if directory.name in CACHE_DIRECTORY_NAMES:
            add(directory)
            directory_names[:] = []
            continue

        retained_directories = []
        for name in directory_names:
            child = directory / name
            if name in PROTECTED_COMPONENTS or name.startswith(".venv."):
                continue
            if directory == frontend_root and name in {"dist", ".vite"}:
                add(child)
                continue
            if name in CACHE_DIRECTORY_NAMES:
                add(child)
                continue
            retained_directories.append(name)
        directory_names[:] = retained_directories

        for name in file_names:
            if Path(name).suffix in {".pyc", ".log"}:
                add(directory / name)

    return [selected[relative] for relative in sorted(selected, key=lambda item: item.as_posix())]


def _size_bytes(path: Path) -> int:
    if path.is_file() or path.is_symlink():
        return path.stat().st_size
    return sum(item.stat().st_size for item in path.rglob("*") if item.is_file())


def _remove(path: Path, workspace: Path) -> None:
    if _resolved_descendant(path, workspace) is None:
        raise ValueError(f"Refusing to remove path outside workspace: {path}")
    if path.is_dir() and not path.is_symlink():
        shutil.rmtree(path)
    else:
        path.unlink()


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="print the cleanup plan")
    mode.add_argument("--apply", action="store_true", help="remove the printed paths")
    parser.add_argument("--workspace", help="explicit workspace root for the cleanup")
    args = parser.parse_args(argv)
    if args.apply and not args.workspace:
        parser.error("--apply requires --workspace")
    return args


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    workspace = Path(args.workspace or Path.cwd()).resolve()
    if not workspace.is_dir():
        print(f"Workspace is not a directory: {workspace}", file=sys.stderr)
        return 2

    paths = _generated_paths(workspace)
    total_bytes = sum(_size_bytes(path) for path in paths)
    action = "APPLY" if args.apply else "DRY RUN"
    print(f"{action}: {len(paths)} allowlisted generated paths ({total_bytes} bytes)")
    for path in paths:
        print(f"- {path.resolve().relative_to(workspace).as_posix()}")

    if args.apply:
        for path in paths:
            _remove(path, workspace)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
