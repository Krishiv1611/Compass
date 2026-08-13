"""Deterministic, bounded project-instruction discovery and updates."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path


WORKSPACE_RULES = ("AGENTS.md", "CLAUDE.md", "GEMINI.md", "COMPASS.md")
DEFAULT_MAX_CHARS = 20_000


@dataclass(frozen=True, slots=True)
class InstructionSource:
    path: Path
    precedence: int
    content: str
    digest: str


def _read_utf8(path: Path) -> tuple[str, str] | None:
    """Read one regular UTF-8 rule file, caching it by stable file metadata."""
    try:
        if not path.is_file() or path.is_symlink():
            return None
        raw = path.read_bytes()
        content = raw.decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")
    except (OSError, UnicodeDecodeError):
        return None
    value = (content, hashlib.sha256(content.encode("utf-8")).hexdigest())
    return value


def load_project_instructions(
    workspace_root: str | Path,
    *,
    home: str | Path | None = None,
) -> list[InstructionSource]:
    """Load known instruction files from lowest to highest precedence."""
    root = Path(workspace_root).resolve()
    home_root = Path(home).resolve() if home is not None else Path.home().resolve()
    candidates = [(home_root / ".compass" / "COMPASS.md", 0)]
    candidates.extend((root / name, index) for index, name in enumerate(WORKSPACE_RULES, 1))
    sources: list[InstructionSource] = []
    for path, precedence in candidates:
        value = _read_utf8(path)
        if value is None:
            continue
        content, digest = value
        sources.append(InstructionSource(path, precedence, content, digest))
    return sources


def _source_block(source: InstructionSource, content: str | None = None) -> str:
    value = source.content if content is None else content
    return f"Instructions from {source.path.name}:\n{value.rstrip()}\n"


def _selected_blocks(
    sources: list[InstructionSource], max_chars: int
) -> tuple[dict[Path, str], set[Path]]:
    if max_chars <= 0:
        return {}, set()
    selected: dict[Path, str] = {}
    truncated: set[Path] = set()
    remaining = max_chars
    for source in sorted(sources, key=lambda item: item.precedence, reverse=True):
        block = _source_block(source)
        if len(block) <= remaining:
            selected[source.path] = block
            remaining -= len(block)
            continue
        prefix = f"Instructions from {source.path.name}:\n"
        marker = "\n[truncated]\n"
        room = remaining - len(prefix) - len(marker)
        if room > 0:
            selected[source.path] = prefix + source.content[:room].rstrip() + marker
            truncated.add(source.path)
        break
    return selected, truncated


def render_project_instructions(
    sources: list[InstructionSource], max_chars: int = DEFAULT_MAX_CHARS
) -> str:
    """Render within a hard limit, retaining higher-precedence rules first."""
    selected, _ = _selected_blocks(sources, max_chars)
    return "\n".join(
        selected[source.path].rstrip()
        for source in sorted(sources, key=lambda item: item.precedence)
        if source.path in selected
    )[:max_chars]


def instruction_manifest(
    sources: list[InstructionSource], max_chars: int = DEFAULT_MAX_CHARS
) -> list[dict[str, object]]:
    """Return safe rule metadata for TUI/web inspection."""
    selected, truncated = _selected_blocks(sources, max_chars)
    return [
        {
            "path": str(source.path),
            "precedence": source.precedence,
            "digest": source.digest[:12],
            "included": source.path in selected,
            "truncated": source.path in truncated,
        }
        for source in sources
    ]


COMPASS_TEMPLATE = """# Compass project instructions

Add stable project-specific guidance here. Compass reads this file once per turn.

## Learned instructions
"""


def initialize_compass_file(
    workspace_root: str | Path,
    *,
    force: bool = False,
    approved: bool = False,
) -> Path:
    """Create a minimal COMPASS.md without silently replacing user content."""
    target = Path(workspace_root).resolve() / "COMPASS.md"
    if target.exists() and not force:
        raise FileExistsError(f"{target} already exists")
    if target.exists() and force and not approved:
        raise PermissionError("Replacing COMPASS.md requires approval")
    target.write_text(COMPASS_TEMPLATE, encoding="utf-8", newline="\n")
    return target


def proposed_learned_instruction(text: str) -> str:
    value = text.strip()
    if not value or "\n" in value or "\r" in value:
        raise ValueError("Learned instruction must be one non-empty line")
    if len(value) > 500:
        raise ValueError("Learned instruction must be at most 500 characters")
    return f"- {value}"


def append_learned_instruction(
    workspace_root: str | Path,
    text: str,
    *,
    approved: bool = False,
) -> str:
    """Append exactly one approved bullet under the learned-instructions heading."""
    addition = proposed_learned_instruction(text)
    if not approved:
        raise PermissionError("Appending a learned instruction requires approval")
    target = Path(workspace_root).resolve() / "COMPASS.md"
    if not target.exists():
        initialize_compass_file(workspace_root)
    content = target.read_text(encoding="utf-8")
    heading = "## Learned instructions"
    if heading not in content:
        content = content.rstrip() + f"\n\n{heading}\n"
    if not content.endswith("\n"):
        content += "\n"
    target.write_text(content + addition + "\n", encoding="utf-8", newline="\n")
    return addition
