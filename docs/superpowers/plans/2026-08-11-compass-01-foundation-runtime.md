# Compass Foundation, Safety, and Runtime Contract Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make startup safe, establish one shared action/event contract, guarantee valid tool-message linkage, surface every interrupt, support DB-optional current-process TUI runs, restore real compaction, and make the supplied web deployment reachable.

**Architecture:** Introduce small transport-neutral protocol and tool-policy modules, then make graph, backend, TUI, and web consume them. The graph keeps one ReAct spine and always uses a checkpointer: PostgreSQL when configured, `InMemorySaver` otherwise. Custom Python tools become explicit opt-in and are never imported during repository startup.

**Tech Stack:** Python 3.12 standard library, Pydantic 2, LangGraph 1.2.9-compatible public APIs, FastAPI schemas, React/TypeScript protocol types, Python `unittest`, Docker Compose config validation.

## Global Constraints

- Preserve Ask, Edit, Plan, and Goal behavior.
- Never emit another assistant/human message or `END` while an assistant tool call lacks a matching `ToolMessage`.
- Do not use LangGraph private methods such as `_ainvoke_tool`.
- Custom repository Python is disabled until the user explicitly approves the exact resolved file path.
- Web never loads repository Python tools, shell tools, or command MCP servers.
- TUI without PostgreSQL supports current-process chat, approval, plan, and clarification; cross-process graph resume remains PostgreSQL-backed until the checkpoint plan adds file-level restore/fork.
- Keep all action strings lowercase and defined by `ResumeAction`.

---

## File Structure

- Create `agent/runtime/protocol.py`: shared resume actions, interrupt kinds, and typed payloads.
- Modify `agent/runtime/events.py`: add waiting/clarification events and typed interrupt data.
- Create `frontend/src/types/protocol.ts`: frontend mirror of protocol values.
- Create `agent/tools/registry.py`: built-in tool metadata and policy lookup.
- Modify `agent/tools/discovery.py`: scan without import; load only approved paths.
- Modify `agent/graph/tools_registry.py`: built-ins only at import time; request-scoped tool selection.
- Replace usage of `agent/graph/remote_tool_node.py` with `agent/graph/tool_node.py`: public callable wrapper around `ToolNode`.
- Create `agent/graph/routing.py`: pure route decisions with tool-call-first precedence.
- Create `agent/persistence.py`: PostgreSQL-or-memory checkpointer selection.
- Create `agent/local_sessions.py`: DB-free JSON session metadata adapter.
- Modify graph/runtime/backend/TUI/frontend consumers listed per task.
- Add focused contract tests under `tests/` and frontend tests under `frontend/src/**/*.test.ts`.

### Task 1: Define the shared resume and interrupt protocol

**Files:**
- Create: `agent/runtime/protocol.py`
- Modify: `agent/runtime/events.py`
- Modify: `agent/runtime/__init__.py`
- Modify: `backend/schemas/chat.py`
- Create: `frontend/src/types/protocol.ts`
- Test: `tests/test_protocol_contract.py`

**Interfaces:**
- Produces: `ResumeAction`, `InterruptKind`, `ResumePayload`, `InterruptData`.
- Produces: WebSocket fields `action: ResumeAction | None` and `feedback: str | None`.
- Later tasks consume these exact enum values.

- [ ] **Step 1: Write the failing Python contract test**

```python
import unittest

from agent.runtime.protocol import InterruptKind, ResumeAction, ResumePayload


class ProtocolContractTests(unittest.TestCase):
    def test_resume_actions_are_stable(self):
        self.assertEqual(
            {item.value for item in ResumeAction},
            {
                "approve", "always", "deny", "skip", "execute_plan",
                "revise_plan", "cancel", "answer",
            },
        )

    def test_feedback_round_trips(self):
        payload = ResumePayload(action=ResumeAction.REVISE_PLAN, feedback="Split task 2")
        self.assertEqual(payload.model_dump(mode="json"), {
            "action": "revise_plan",
            "feedback": "Split task 2",
        })

    def test_interrupt_kinds_are_explicit(self):
        self.assertEqual(
            {item.value for item in InterruptKind},
            {"tool_approval", "plan_approval", "clarification"},
        )
```

- [ ] **Step 2: Run the focused test and verify the missing module failure**

Run: `python -m unittest tests.test_protocol_contract -v`  
Expected: FAIL with `ModuleNotFoundError: agent.runtime.protocol`.

- [ ] **Step 3: Implement the protocol models**

```python
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


class ResumeAction(str, Enum):
    APPROVE = "approve"
    ALWAYS = "always"
    DENY = "deny"
    SKIP = "skip"
    EXECUTE_PLAN = "execute_plan"
    REVISE_PLAN = "revise_plan"
    CANCEL = "cancel"
    ANSWER = "answer"


class InterruptKind(str, Enum):
    TOOL_APPROVAL = "tool_approval"
    PLAN_APPROVAL = "plan_approval"
    CLARIFICATION = "clarification"


class ResumePayload(BaseModel):
    action: ResumeAction
    feedback: str | None = None


class InterruptData(BaseModel):
    kind: InterruptKind
    prompt: str
    tool_calls: list[dict[str, Any]] = Field(default_factory=list)
    plan: str | None = None
```

Add `CLARIFICATION_REQUIRED = "clarification_required"` and `RUN_WAITING = "run_waiting"` to `StreamEventType`. In `WsClientMessage`, change `action` to `ResumeAction | None` and add `feedback: str | None = None`.

- [ ] **Step 4: Add and verify the TypeScript mirror**

```typescript
export type ResumeAction =
  | "approve" | "always" | "deny" | "skip"
  | "execute_plan" | "revise_plan" | "cancel" | "answer";

export type InterruptKind = "tool_approval" | "plan_approval" | "clarification";

export interface ResumePayload {
  action: ResumeAction;
  feedback?: string;
}
```

Run: `frontend\node_modules\.bin\tsc.cmd -p frontend\tsconfig.app.json --noEmit --incremental false --pretty false`  
Expected: PASS.

- [ ] **Step 5: Run tests and commit**

Run: `python -m unittest tests.test_protocol_contract -v`  
Expected: 3 tests PASS.

```bash
git add agent/runtime/protocol.py agent/runtime/events.py agent/runtime/__init__.py backend/schemas/chat.py frontend/src/types/protocol.ts tests/test_protocol_contract.py
git commit -m "feat(runtime): define shared interrupt protocol"
```

### Task 2: Stop import-time execution of repository custom tools

**Files:**
- Modify: `agent/tools/discovery.py`
- Modify: `agent/graph/tools_registry.py`
- Modify: `agent/config.py`
- Test: `tests/test_custom_tool_discovery.py`

**Interfaces:**
- Produces: `CustomToolCandidate(source_path: Path, scope: str)`.
- Produces: `scan_custom_tool_files(workspace_root: Path) -> list[CustomToolCandidate]`.
- Produces: `load_approved_custom_tools(candidates, approved_paths) -> list[BaseTool]`.

- [ ] **Step 1: Write a failing non-execution test**

```python
import tempfile
import unittest
from pathlib import Path

from agent.tools.discovery import scan_custom_tool_files


class CustomToolDiscoveryTests(unittest.TestCase):
    def test_scan_does_not_execute_python(self):
        with tempfile.TemporaryDirectory() as root:
            workspace = Path(root)
            tools = workspace / ".compass" / "tools"
            tools.mkdir(parents=True)
            marker = workspace / "executed.txt"
            (tools / "evil.py").write_text(
                f"from pathlib import Path\nPath({str(marker)!r}).write_text('ran')\n",
                encoding="utf-8",
            )
            candidates = scan_custom_tool_files(workspace)
            self.assertEqual([item.source_path.name for item in candidates], ["evil.py"])
            self.assertFalse(marker.exists())
```

- [ ] **Step 2: Run and verify failure**

Run: `python -m unittest tests.test_custom_tool_discovery -v`  
Expected: FAIL because `scan_custom_tool_files` does not exist.

- [ ] **Step 3: Implement scan/load separation**

```python
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CustomToolCandidate:
    source_path: Path
    scope: str


def scan_custom_tool_files(workspace_root: Path) -> list[CustomToolCandidate]:
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
```

Move all `exec_module` behavior into `load_approved_custom_tools`. Resolve each candidate and require its string path in `approved_paths` before import. Reject duplicate names against both built-ins and earlier custom tools.

- [ ] **Step 4: Remove import-time discovery**

Change `tools_registry.py` so module import creates only `BUILTIN_TOOLS`. Add:

```python
def tools_for_run(workspace_root: Path, approved_custom_tool_paths: set[str]) -> list:
    candidates = scan_custom_tool_files(workspace_root)
    return [*BUILTIN_TOOLS, *load_approved_custom_tools(candidates, approved_custom_tool_paths)]
```

Add config defaults `custom_tools.enabled = false` and `custom_tools.approved_paths = []`. Web configuration must always pass an empty approved set.

- [ ] **Step 5: Run tests and commit**

Run: `python -m unittest tests.test_custom_tool_discovery -v`  
Expected: PASS and no marker file.

```bash
git add agent/tools/discovery.py agent/graph/tools_registry.py agent/config.py tests/test_custom_tool_discovery.py
git commit -m "fix(security): require explicit custom tool loading"
```

### Task 3: Replace duplicated tool lists and the dead private ToolNode override

**Files:**
- Create: `agent/tools/registry.py`
- Create: `agent/graph/tool_node.py`
- Modify: `agent/graph/tools_registry.py`
- Modify: `agent/graph/workflow.py`
- Modify: `agent/safety.py`
- Test: `tests/test_tool_registry.py`

**Interfaces:**
- Produces: `ToolPolicy(risk, mutates_workspace, web_allowed, worker_allowed)`.
- Produces: `ToolSpec(tool, policy)` and `ToolRegistry`.
- Produces: `CompassToolNode.__call__(state, config) -> dict` using public `ToolNode.ainvoke`.

- [ ] **Step 1: Write registry-policy tests**

```python
import unittest

from agent.tools.registry import build_builtin_registry


class ToolRegistryTests(unittest.TestCase):
    def test_web_excludes_shell_and_skill_creation(self):
        registry = build_builtin_registry()
        names = {tool.name for tool in registry.tools_for("web")}
        self.assertNotIn("shell_execute", names)
        self.assertNotIn("create_skill", names)

    def test_workers_receive_read_only_tools(self):
        registry = build_builtin_registry()
        specs = registry.specs_for("worker")
        self.assertTrue(specs)
        self.assertTrue(all(not spec.policy.mutates_workspace for spec in specs))

    def test_duplicate_tool_names_are_rejected(self):
        registry = build_builtin_registry()
        with self.assertRaisesRegex(ValueError, "Duplicate tool name"):
            registry.register(registry.get("read_file"))
```

- [ ] **Step 2: Run and verify failure**

Run: `python -m unittest tests.test_tool_registry -v`  
Expected: FAIL because `agent.tools.registry` does not exist.

- [ ] **Step 3: Implement metadata and policy selection**

```python
from dataclasses import dataclass
from typing import Literal

from langchain_core.tools import BaseTool

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
            return [s for s in self._specs.values() if s.policy.web_allowed]
        if target == "worker":
            return [s for s in self._specs.values() if s.policy.worker_allowed and not s.policy.mutates_workspace]
        return list(self._specs.values())

    def tools_for(self, target: str) -> list[BaseTool]:
        return [spec.tool for spec in self.specs_for(target)]
```

- [ ] **Step 4: Implement the public ToolNode wrapper**

```python
from langgraph.prebuilt import ToolNode


class CompassToolNode:
    def __init__(self, registry: ToolRegistry):
        self._registry = registry

    async def __call__(self, state: dict, config: dict) -> dict:
        target = config.get("configurable", {}).get("execution_target", "tui")
        node = ToolNode(self._registry.tools_for(target))
        return await node.ainvoke(state, config)
```

Register `CompassToolNode` in `workflow.py`. Change safety decisions to use `ToolPolicy.risk`; delete no files yet. `remote_tool_node.py` and relay removal is deferred to Plan 6 after reachability tests.

- [ ] **Step 5: Run tests and commit**

Run: `python -m unittest tests.test_tool_registry -v`  
Expected: 3 tests PASS.

```bash
git add agent/tools/registry.py agent/graph/tool_node.py agent/graph/tools_registry.py agent/graph/workflow.py agent/safety.py tests/test_tool_registry.py
git commit -m "refactor(tools): centralize policy and public execution"
```

### Task 4: Enforce tool-call-first graph routing and bounded Goal recovery

**Files:**
- Create: `agent/graph/routing.py`
- Modify: `agent/graph/state.py`
- Modify: `agent/graph/nodes.py`
- Modify: `agent/graph/workflow.py`
- Modify: `agent/loop_detector.py`
- Test: `tests/test_graph_invariants.py`

**Interfaces:**
- Produces: `route_after_executor(state) -> str`.
- Adds state fields `goal_iteration`, `goal_iteration_limit`, `needs_replan`.
- Requires `pending_tool_calls` to take precedence over loop/replan/evaluation routes.

- [ ] **Step 1: Write failing route precedence tests**

```python
import unittest

from agent.graph.routing import route_after_executor


class GraphInvariantTests(unittest.IsolatedAsyncioTestCase):
    async def test_pending_calls_always_route_to_safety_first(self):
        state = {
            "pending_tool_calls": [{"id": "1", "name": "read_file", "args": {"path": "a.py"}}],
            "loop_detected": True,
            "needs_replan": True,
            "mode": "goal",
            "is_done": False,
        }
        self.assertEqual(await route_after_executor(state), "check_safety")

    async def test_goal_iteration_limit_ends_with_explicit_failure(self):
        state = {
            "pending_tool_calls": [], "loop_detected": False, "needs_replan": False,
            "mode": "goal", "is_done": False, "goal_iteration": 3,
            "goal_iteration_limit": 3,
        }
        self.assertEqual(await route_after_executor(state), "goal_limit")
```

- [ ] **Step 2: Run and verify failure**

Run: `python -m unittest tests.test_graph_invariants -v`  
Expected: FAIL because `agent.graph.routing` does not exist.

- [ ] **Step 3: Implement route ordering**

```python
async def route_after_executor(state: dict) -> str:
    if state.get("pending_tool_calls"):
        return "check_safety"
    if state.get("goal_iteration", 0) >= state.get("goal_iteration_limit", 3):
        return "goal_limit"
    if state.get("loop_detected"):
        return "loop_recovery" if state.get("mode") == "goal" else "loop_limit"
    if state.get("needs_replan"):
        return "context_injector"
    if state.get("mode") == "goal":
        return "linter_node" if state.get("is_done") else "executor"
    return "end" if state.get("is_done") else "executor"
```

Move loop detection to use the newly generated assistant response rather than old state. Add `goal_limit_node` and `loop_limit_node` that return a final explicit failure message without unresolved calls. Increment `goal_iteration` only when evaluator failure reopens the goal.

- [ ] **Step 4: Add a complete message-sequence invariant test**

Build the graph with a fake executor that returns two tool calls, fake tools that return two results, and a final fake assistant response. Assert message roles are `human, ai(tool_calls), tool, tool, ai(final)` and that no other role appears between the tool-calling AI message and both tools.

Run: `python -m unittest tests.test_graph_invariants -v`  
Expected: all route and sequence tests PASS.

- [ ] **Step 5: Commit**

```bash
git add agent/graph/routing.py agent/graph/state.py agent/graph/nodes.py agent/graph/workflow.py agent/loop_detector.py tests/test_graph_invariants.py
git commit -m "fix(graph): preserve tool message invariants"
```

### Task 5: Surface tool, plan, and clarification interrupts without false DONE

**Files:**
- Modify: `agent/graph/nodes.py`
- Modify: `agent/runtime/runner.py`
- Modify: `backend/services/agent_runner.py`
- Modify: `backend/routers/chat.py`
- Test: `tests/test_interrupt_runtime.py`

**Interfaces:**
- Consumes: `ResumePayload` and `InterruptData` from Task 1.
- Produces: exactly one `APPROVAL_REQUIRED` or `CLARIFICATION_REQUIRED` event followed by `RUN_WAITING`; no `DONE` until resumed.

- [ ] **Step 1: Write failing runner tests with a fake snapshot**

```python
import unittest

from agent.runtime.events import StreamEventType
from agent.runtime.runner import events_from_interrupts


class InterruptRuntimeTests(unittest.TestCase):
    def test_clarification_is_not_done(self):
        events = events_from_interrupts([{
            "value": {
                "kind": "clarification",
                "prompt": "Which package should be edited?",
                "tool_calls": [],
                "plan": None,
            }
        }])
        self.assertEqual(
            [event.type for event in events],
            [StreamEventType.CLARIFICATION_REQUIRED, StreamEventType.RUN_WAITING],
        )
```

- [ ] **Step 2: Run and verify failure**

Run: `python -m unittest tests.test_interrupt_runtime -v`  
Expected: FAIL because `events_from_interrupts` does not exist.

- [ ] **Step 3: Implement one interrupt adapter**

```python
def events_from_interrupts(interrupts: list[dict]) -> list[StreamEvent]:
    if not interrupts:
        return []
    data = InterruptData.model_validate(interrupts[0]["value"])
    event_type = (
        StreamEventType.CLARIFICATION_REQUIRED
        if data.kind == InterruptKind.CLARIFICATION
        else StreamEventType.APPROVAL_REQUIRED
    )
    return [
        StreamEvent(type=event_type, content=data.prompt, data=data.model_dump(mode="json")),
        StreamEvent(type=StreamEventType.RUN_WAITING, data={"kind": data.kind.value}),
    ]
```

Use this adapter after streaming. Return immediately when it yields events. In the backend, construct `Command(resume=ResumePayload(action=client_msg.action, feedback=client_msg.feedback).model_dump(mode="json"))`.

- [ ] **Step 4: Verify every resume path**

Add tests for `approve`, `always`, `deny`, `skip`, `execute_plan`, `revise_plan` with feedback, `cancel`, and clarification `answer`. Assert graph nodes receive exactly the action and feedback sent by the adapter.

Run: `python -m unittest tests.test_interrupt_runtime -v`  
Expected: all interrupt tests PASS.

- [ ] **Step 5: Commit**

```bash
git add agent/graph/nodes.py agent/runtime/runner.py backend/services/agent_runner.py backend/routers/chat.py tests/test_interrupt_runtime.py
git commit -m "fix(runtime): transport every interrupt explicitly"
```

### Task 6: Make the TUI usable without PostgreSQL

**Files:**
- Create: `agent/persistence.py`
- Create: `agent/local_sessions.py`
- Modify: `agent/sessions.py`
- Modify: `agent/graph/workflow.py`
- Modify: `main.py`
- Test: `tests/test_local_runtime.py`

**Interfaces:**
- Produces: `async get_checkpointer(db_uri: str | None, require_durable: bool = False)` returning PostgreSQL saver or a process singleton `InMemorySaver`; web startup passes `require_durable=True`.
- Produces: `async build_postgres_checkpointer(db_uri: str) -> tuple[AsyncPostgresSaver, AsyncConnectionPool]`; the caller retains the pool for the saver lifetime.
- Produces: `LocalSessionStore(workspace_root)` with `create`, `get`, `list`, `rename`, and `touch`.
- `SessionManager` selects backend DB lazily only when `DB_URI` is configured.

- [ ] **Step 1: Write a DB-free import and checkpointer test**

```python
import os
import unittest
from unittest.mock import patch

from agent.persistence import get_checkpointer


class LocalRuntimeTests(unittest.IsolatedAsyncioTestCase):
    async def test_missing_db_uri_uses_memory_checkpointer(self):
        with patch.dict(os.environ, {}, clear=True):
            checkpointer = await get_checkpointer(None)
        self.assertIn("memory", checkpointer.__class__.__module__)

    async def test_web_cannot_silently_fall_back(self):
        with self.assertRaisesRegex(RuntimeError, "DB_URI"):
            await get_checkpointer(None, require_durable=True)
```

- [ ] **Step 2: Run and verify failure**

Run: `python -m unittest tests.test_local_runtime -v`  
Expected: FAIL because `agent.persistence` does not exist.

- [ ] **Step 3: Implement non-sticky persistence selection**

```python
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg_pool import AsyncConnectionPool

_memory_saver = InMemorySaver()
_postgres_pool: AsyncConnectionPool | None = None


async def build_postgres_checkpointer(db_uri: str):
    pool = AsyncConnectionPool(
        conninfo=db_uri,
        min_size=1,
        max_size=20,
        kwargs={"autocommit": True, "prepare_threshold": 0},
        open=False,
    )
    await pool.open(wait=True, timeout=3)
    saver = AsyncPostgresSaver(pool)
    await saver.setup()
    return saver, pool


async def get_checkpointer(db_uri: str | None, *, require_durable: bool = False):
    global _postgres_pool
    if not db_uri:
        if require_durable:
            raise RuntimeError("Durable persistence requires DB_URI")
        return _memory_saver
    try:
        saver, _postgres_pool = await build_postgres_checkpointer(db_uri)
        return saver
    except Exception:
        if require_durable:
            raise
        return _memory_saver
```

Close a partially opened pool when construction/setup fails. Do not cache a failed PostgreSQL initialization as the final workflow forever. Protect workflow initialization with an `asyncio.Lock`, and provide `reset_workflow()` for tests/recovery. Local TUI calls with the default fallback; backend/web startup requires durable persistence and exposes failure through Plan 6 readiness rather than silently switching stores.

- [ ] **Step 4: Implement local session metadata**

Store `.compass/sessions.json` using an atomic temporary-file replacement. Each record contains `id`, `thread_id`, `title`, `turn_count`, `created_at`, `updated_at`, `project_id`, and `context_version`. Import backend settings and `SessionLocal` only inside the database-backed adapter.

- [ ] **Step 5: Verify a fake DB-free approval turn**

Run a fake graph with `interrupt()` using the memory saver, resume it with `approve`, and assert DONE. Also import `main` with `DB_URI` absent and assert no backend settings validation error.

Run: `python -m unittest tests.test_local_runtime -v`  
Expected: all local runtime tests PASS.

- [ ] **Step 6: Commit**

```bash
git add agent/persistence.py agent/local_sessions.py agent/sessions.py agent/graph/workflow.py main.py tests/test_local_runtime.py
git commit -m "fix(tui): provide database-free local runtime"
```

### Task 7: Restore real automatic and manual compaction

**Files:**
- Create: `agent/runtime/compaction.py`
- Modify: `agent/graph/nodes.py`
- Modify: `agent/graph/workflow.py`
- Modify: `agent/ui/tui.py`
- Test: `tests/test_compaction.py`

**Interfaces:**
- Produces: `build_compaction_update(messages, summary, keep_recent=6) -> dict`.
- Produces: `async compact_thread(workflow, config, force=False) -> CompactionResult`.

- [ ] **Step 1: Write a failing pure compaction test**

```python
import unittest
from langchain_core.messages import HumanMessage
from langgraph.graph.message import RemoveMessage

from agent.runtime.compaction import build_compaction_update


class CompactionTests(unittest.TestCase):
    def test_old_messages_are_removed_and_recent_messages_remain(self):
        messages = [HumanMessage(content=str(i), id=str(i)) for i in range(12)]
        update = build_compaction_update(messages, "summary", keep_recent=6)
        removals = [item for item in update["messages"] if isinstance(item, RemoveMessage)]
        self.assertEqual([item.id for item in removals], [str(i) for i in range(6)])
        self.assertEqual(update["summary"], "summary")
```

- [ ] **Step 2: Run and verify failure**

Run: `python -m unittest tests.test_compaction -v`  
Expected: FAIL because `agent.runtime.compaction` does not exist.

- [ ] **Step 3: Implement and link compaction**

Implement `build_compaction_update` with `RemoveMessage` for all but the newest six messages. Register `summary_node` and route to it only when there are no pending tool calls and `len(messages) > context.summarize_after`. Return to `executor` only if the current turn is unfinished; otherwise end.

Implement `compact_thread` by reading the snapshot, generating one summary, and applying the update with `workflow.aupdate_state(config, update, as_node="summary_node")`. TUI `/compact` must call this service and report counts before/after.

- [ ] **Step 4: Verify automatic and manual behavior**

Add a fake summarizer test that asserts exactly one model call, six recent messages retained, summary stored, and the next turn receives summary plus recent messages.

Run: `python -m unittest tests.test_compaction -v`  
Expected: all compaction tests PASS.

- [ ] **Step 5: Commit**

```bash
git add agent/runtime/compaction.py agent/graph/nodes.py agent/graph/workflow.py agent/ui/tui.py tests/test_compaction.py
git commit -m "fix(context): make compaction update checkpoint state"
```

### Task 8: Repair explicit skills, file search, MCP inspection, and validation approval

**Files:**
- Modify: `agent/graph/workflow.py`
- Modify: `agent/skills/manager.py`
- Modify: `agent/skills/subagent_factory.py`
- Modify: `agent/tools/directory_tools.py`
- Modify: `agent/mcp.py`
- Modify: `agent/ui/tui.py`
- Modify: `agent/graph/nodes.py`
- Test: `tests/test_regression_contracts.py`

**Interfaces:**
- Explicit `active_skill` takes precedence at START.
- Invalid skills return an explicit error artifact and resume the main executor.
- Subagents cannot finish with unresolved tool calls.
- Goal validation commands use the same approval protocol as shell tools.

- [ ] **Step 1: Write regression tests**

Add tests that assert:

```python
self.assertEqual(_route_start({"active_skill": {"name": "review"}, "mode": "edit", "messages": []}), "skill_manager")
self.assertEqual(find_files.invoke({"pattern": "*.py", "path": temp_root})["matches"][0], "sample.py")
self.assertEqual(runtime_mcp_config_name(), "mcp_servers.json")
```

Add a subagent test where the last allowed model turn returns a tool call; assert the factory returns a bounded error result rather than ending with the unresolved call. Add a Goal test asserting TypeScript validation requests approval through `shell_execute` rather than calling `subprocess` inside the linter node.

- [ ] **Step 2: Run and verify failures**

Run: `python -m unittest tests.test_regression_contracts -v`  
Expected: failures for skill route, missing `Path`, MCP filename/API mismatch, subagent max-turn behavior, and direct `npx` execution.

- [ ] **Step 3: Apply minimal repairs**

Import `Path` in `directory_tools.py`. Route `active_skill` before intent heuristics. Change invalid skill behavior to a structured error returned to the main executor. Use one MCP filename and expose `get_mcp_tools` to `/mcp`. Replace direct `_typescript_check` subprocess with a pending `shell_execute` tool call carrying `npx tsc --noEmit` and normal approval policy.

- [ ] **Step 4: Run tests and commit**

Run: `python -m unittest tests.test_regression_contracts -v`  
Expected: all regression tests PASS.

```bash
git add agent/graph/workflow.py agent/skills/manager.py agent/skills/subagent_factory.py agent/tools/directory_tools.py agent/mcp.py agent/ui/tui.py agent/graph/nodes.py tests/test_regression_contracts.py
git commit -m "fix(agent): restore skills search mcp and approved checks"
```

### Task 9: Establish one same-origin web deployment contract

**Files:**
- Modify: `frontend/package.json`
- Modify: `frontend/package-lock.json`
- Modify: `frontend/src/api/client.ts`
- Modify: `frontend/src/api/chat.ts`
- Modify: `frontend/vite.config.ts`
- Modify: `frontend/nginx.conf`
- Modify: `frontend.Dockerfile`
- Modify: `frontend/.env.example`
- Modify: `docker-compose.yml`
- Modify: `docker-compose.prod.yml`
- Modify: `backend/routers/chat.py`
- Test: `frontend/src/api/client.test.ts`
- Test: `tests/backend/test_websocket_auth.py`

**Interfaces:**
- Browser HTTP base defaults to `/api`.
- Browser WebSocket base is derived from `window.location` and uses `/api/chat/ws/{session_id}`.
- Browser access credentials use the `Sec-WebSocket-Protocol` values `compass.v1` and `compass.jwt.{access_token}` rather than a query string.
- Nginx proxies `/api/` without stripping `/api` and enables upgrades for `/api/chat/ws/`.

- [ ] **Step 1: Add the frontend test runner and URL tests**

Run: `cd frontend && npm install --save-dev vitest jsdom`  
Expected: `package.json` and `package-lock.json` record the test dependencies. Add `"test": "vitest"` to `package.json` scripts in the same step.

```typescript
import { describe, expect, it } from "vitest";
import { buildWebSocketProtocols, buildWebSocketUrl } from "./client";

describe("API URL contract", () => {
  it("uses the same origin API path", () => {
    expect(buildWebSocketUrl("abc", "https://compass.test"))
      .toBe("wss://compass.test/api/chat/ws/abc");
    expect(buildWebSocketProtocols("token"))
      .toEqual(["compass.v1", "compass.jwt.token"]);
  });
});
```

- [ ] **Step 2: Run and verify failure**

Run: `cd frontend && npm test -- --run src/api/client.test.ts`  
Expected: FAIL because `buildWebSocketUrl` does not exist.

- [ ] **Step 3: Implement URL and proxy agreement**

```typescript
export const API_BASE_URL = import.meta.env.VITE_API_URL || "/api";

export function buildWebSocketUrl(sessionId: string, origin = window.location.origin) {
  const base = new URL(API_BASE_URL, origin);
  base.protocol = base.protocol === "https:" ? "wss:" : "ws:";
  base.pathname = `${base.pathname.replace(/\/$/, "")}/chat/ws/${sessionId}`;
  return base.toString();
}

export function buildWebSocketProtocols(token = getAccessToken() || "") {
  if (!token) throw new Error("An access token is required");
  return ["compass.v1", `compass.jwt.${token}`];
}
```

Create the socket with `new WebSocket(buildWebSocketUrl(sessionId), buildWebSocketProtocols())`. Backend parses the offered protocols, verifies the `compass.jwt.` access token and active user, then accepts only `compass.v1`; reject missing/malformed credentials before session lookup. Do not accept or log a `token` query parameter. Configure Vite `/api` proxy with `ws: true`. In Nginx, use one `/api/` location with `proxy_pass http://api;` and no rewrite, including upgrade headers. Remove the unused Vite Docker build argument. Move `COMPASS_CLOUD_MODE=true` into backend `environment` in development Compose.

- [ ] **Step 4: Verify configs and tests**

Run: `cd frontend && npm test -- --run src/api/client.test.ts && npm run lint`  
Expected: URL test PASS and lint has zero errors.

Run: `python -m unittest tests.backend.test_websocket_auth -v`  
Expected: valid subprotocol auth PASS; missing credentials, query credentials, inactive users, and malformed tokens are rejected before a model call.

Run: `docker compose -f docker-compose.yml config --quiet`  
Expected: exit 0.

Run (PowerShell): `$env:POSTGRES_PASSWORD='audit-only'; $env:DB_URI='postgresql+psycopg://compass_user:audit-only@postgres:5432/compass_db'; $env:JWT_SECRET='audit-only-not-for-runtime'; $env:OPENROUTER_API_KEY=''; docker compose -f docker-compose.prod.yml config --quiet`  
Expected: exit 0; obsolete `version` warning is removed after deleting the top-level `version` field.

- [ ] **Step 5: Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/src/api/client.ts frontend/src/api/chat.ts frontend/src/api/client.test.ts frontend/vite.config.ts frontend/nginx.conf frontend.Dockerfile frontend/.env.example docker-compose.yml docker-compose.prod.yml backend/routers/chat.py tests/backend/test_websocket_auth.py
git commit -m "fix(web): align same-origin api and websocket routing"
```

## Plan 1 Completion Gate

- [ ] Run `python -m unittest discover -s tests -v` and confirm zero failures.
- [ ] Run `cd frontend && npm test -- --run` and confirm zero failures.
- [ ] Run frontend no-emit typecheck and lint.
- [ ] Run both Compose config commands.
- [ ] Manually start TUI with no `DB_URI`, fake model, and one approval interrupt.
- [ ] Manually start web Compose, sign in, send one Ask turn, and confirm WebSocket upgrade.
- [ ] Confirm opening a repository with an unapproved `.compass/tools/*.py` file does not execute it.
- [ ] Request code review before starting Plans 2 or 3.
