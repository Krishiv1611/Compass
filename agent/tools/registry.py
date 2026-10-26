"""Policy-aware registry for Compass tools."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Literal

from langchain_core.tools import BaseTool

from agent.rag.retriever import codebase_search
from agent.tools.create_skill_tool import create_skill
from agent.tools.directory_tools import find_files, list_dir, make_dir
from agent.tools.file_tools import edit_file, read_file, write_to_file
from agent.tools.memory_tool import memory
from agent.tools.search_tools import grep_search
from agent.tools.shell_tool import shell_execute
from agent.tools.todo_tool import todo
from agent.tools.visual_qa_tool import visual_qa_verify
from agent.tools.web_tools import web_search


Risk = Literal["safe", "approval", "always_approval"]


@dataclass(frozen=True)
class ToolPolicy:
    risk: Risk
    mutates_workspace: bool
    web_allowed: bool
    worker_allowed: bool


@dataclass(frozen=True)
class ToolSpec:
    tool: BaseTool
    policy: ToolPolicy


class ToolRegistry:
    def __init__(self, specs: list[ToolSpec]):
        self._specs: dict[str, ToolSpec] = {}
        for spec in specs:
            self.register(spec)

    def register(self, spec: ToolSpec) -> None:
        if spec.tool.name in self._specs:
            raise ValueError(f"Duplicate tool name: {spec.tool.name}")
        self._specs[spec.tool.name] = spec

    def get(self, name: str) -> ToolSpec:
        return self._specs[name]

    def specs_for(self, target: str) -> list[ToolSpec]:
        if target == "web":
            return [
                spec for spec in self._specs.values() if spec.policy.web_allowed
            ]
        if target == "worker":
            return [
                spec
                for spec in self._specs.values()
                if spec.policy.worker_allowed
                and not spec.policy.mutates_workspace
            ]
        return list(self._specs.values())

    def tools_for(self, target: str) -> list[BaseTool]:
        return [spec.tool for spec in self.specs_for(target)]

    def worker_tools(self, requested_names: list[str]) -> list[BaseTool]:
        """Resolve an exact worker allowlist or reject it without partial access."""
        resolved = []
        for name in requested_names:
            spec = self._specs.get(name)
            if (
                spec is None
                or not spec.policy.worker_allowed
                or spec.policy.mutates_workspace
            ):
                raise ValueError(f"tool '{name}' is not worker-allowed")
            resolved.append(spec.tool)
        return resolved


def _spec(
    tool: BaseTool,
    *,
    risk: Risk = "safe",
    mutates_workspace: bool = False,
    web_allowed: bool = True,
    worker_allowed: bool = True,
) -> ToolSpec:
    return ToolSpec(
        tool=tool,
        policy=ToolPolicy(
            risk=risk,
            mutates_workspace=mutates_workspace,
            web_allowed=web_allowed,
            worker_allowed=worker_allowed,
        ),
    )


def build_builtin_registry() -> ToolRegistry:
    """Build the single source of truth for built-in tools and policies."""

    return ToolRegistry(
        [
            _spec(read_file),
            _spec(
                write_to_file,
                risk="approval",
                mutates_workspace=True,
                worker_allowed=False,
            ),
            _spec(
                edit_file,
                risk="approval",
                mutates_workspace=True,
                worker_allowed=False,
            ),
            _spec(list_dir),
            _spec(
                make_dir,
                risk="safe",
                mutates_workspace=True,
                web_allowed=True,
                worker_allowed=False,
            ),
            _spec(find_files),
            _spec(grep_search),
            _spec(codebase_search),
            _spec(web_search),
            _spec(visual_qa_verify),
            _spec(
                shell_execute,
                risk="always_approval",
                mutates_workspace=True,
                web_allowed=False,
                worker_allowed=False,
            ),
            _spec(memory, worker_allowed=False),
            _spec(todo, worker_allowed=False),
            _spec(
                create_skill,
                risk="approval",
                mutates_workspace=True,
                web_allowed=False,
                worker_allowed=False,
            ),
        ]
    )
