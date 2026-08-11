# Compass Performance and Observability Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Remove measured latency amplification and make every run explain its model calls, tokens, cache work, database work, tools, verification, persistence, and render behavior.

**Architecture:** Measure first with deterministic fake-model benchmarks, then add a request-scoped timing/usage recorder and a once-per-turn context bundle. Replace repeated full scans and UI full-tree rerenders with incremental updates and scoped components. Provider/network time is reported separately and is not hidden by local optimizations.

**Tech Stack:** Python `time.perf_counter`, context variables, Pydantic artifacts, SQLAlchemy query counters, React Profiler/Vitest fake timers, Vite bundle analysis from manifest output.

## Global Constraints

- Do not optimize by removing planner, evaluator, approval, memory, RAG, skills, MCP, patch review, or verification behavior.
- Compare identical fake-model scenarios before and after each optimization.
- Count fewer calls as an improvement only when the parity and artifact tests still pass.
- Recall memory at most once per user turn.
- Discover MCP at most once per run; cache successful discovery for 300 seconds and failures for 30 seconds.
- Never include API keys, access tokens, prompt contents, tool arguments containing secrets, or file contents in timing records.
- Render completed Markdown fully; temporary plain streaming presentation is allowed.

---

## File Structure

- Create `agent/runtime/metrics.py`: timing spans and usage accumulator.
- Create `agent/runtime/turn_context.py`: once-per-turn memory/MCP/tool/model preparation.
- Create `tests/performance/`: deterministic call-count and latency-amplification tests.
- Create `frontend/src/runtime/renderMetrics.ts`: test-only render counters.
- Modify runtime nodes, LLM/MCP/memory, workspace services, ChatPage/MessageList/Markdown, preview, route loading, and status surfaces.

### Task 1: Establish deterministic performance baselines and budgets

**Files:**
- Create: `tests/performance/__init__.py`
- Create: `tests/performance/fakes.py`
- Create: `tests/performance/test_turn_budget.py`
- Create: `docs/performance-baseline.md`

**Interfaces:**
- Produces `ScenarioMetrics(model_calls, memory_calls, mcp_calls, db_sessions, tool_calls, workspace_scans, events)`.
- Produces fake scenarios `greeting`, `simple_edit`, `two_tool_edit`, `planned_edit`, `goal_success`, `goal_retry`.
- `tests.performance.fakes` exports `fake_input(text)`, `fake_config()`, `services_for_counter(counter)`, and deterministic fake model/tool responses used by later performance tasks.

- [ ] **Step 1: Implement counters around deterministic fakes**

```python
from dataclasses import dataclass


@dataclass
class ScenarioMetrics:
    model_calls: int = 0
    memory_calls: int = 0
    mcp_calls: int = 0
    db_sessions: int = 0
    tool_calls: int = 0
    workspace_scans: int = 0
    events: int = 0
```

Fake model responses are fixed and contain no sleeps. Run each scenario three times and record call counts, not wall-clock pass/fail thresholds.

- [ ] **Step 2: Add initial budget assertions**

The repaired target budgets are:

| Scenario | Model calls | Memory recalls | MCP discoveries | Extra state reads |
|---|---:|---:|---:|---:|
| Greeting | 1 | 0 | 0 | 0 |
| Simple edit without tools | 1 | 1 | 1 | 0 |
| Edit with `r` tool rounds | `r + 1` | 1 | 1 | 0 |
| Planned edit with `r` rounds | `r + 2` | 1 | 1 | 0 |
| Goal success with `r` rounds | `r + 3` | 1 | 1 | 0 |
| One evaluator retry | prior count + 2 | 1 | 1 | 0 |

Mark target tests as expected failures only for the first baseline commit; document current counts in `docs/performance-baseline.md`.

- [ ] **Step 3: Run and commit the baseline**

Run: `python -m unittest tests.performance.test_turn_budget -v`  
Expected: scenario execution completes and target deltas are documented.

```bash
git add tests/performance/__init__.py tests/performance/fakes.py tests/performance/test_turn_budget.py docs/performance-baseline.md
git commit -m "test(perf): capture agent call-count baseline"
```

### Task 2: Aggregate per-node timing and usage accurately

**Files:**
- Create: `agent/runtime/metrics.py`
- Modify: `agent/telemetry.py`
- Modify: `agent/graph/nodes.py`
- Modify: `agent/runtime/runner.py`
- Modify: `agent/runtime/artifacts.py`
- Modify: `frontend/src/types/artifact.ts`
- Test: `tests/test_runtime_metrics.py`

**Interfaces:**
- Produces `RunMetrics.span(name)` async/sync context manager.
- Produces `RunMetrics.add_usage(node, usage_metadata)`.
- Produces `RunMetrics.snapshot() -> MetricsSnapshot` containing per-node durations, calls, tokens, and total cost when pricing is known.

- [ ] **Step 1: Write aggregation tests**

```python
class RuntimeMetricsTests(unittest.TestCase):
    def test_usage_sums_all_nodes(self):
        metrics = RunMetrics()
        metrics.add_usage("planner", {"input_tokens": 10, "output_tokens": 4})
        metrics.add_usage("executor", {"input_tokens": 20, "output_tokens": 6})
        snapshot = metrics.snapshot()
        self.assertEqual(snapshot.total_input_tokens, 30)
        self.assertEqual(snapshot.total_output_tokens, 10)
        self.assertEqual(snapshot.calls_by_node, {"planner": 1, "executor": 1})

    def test_secret_values_are_not_serialized(self):
        metrics = RunMetrics()
        metrics.add_tag("provider", "openrouter")
        self.assertNotIn("api_key", metrics.snapshot().model_dump_json())
```

- [ ] **Step 2: Run and verify failure**

Run: `python -m unittest tests.test_runtime_metrics -v`  
Expected: `RunMetrics` does not exist.

- [ ] **Step 3: Implement request-scoped metrics**

Use a `ContextVar[RunMetrics | None]`; initialize it at turn start and reset it in `finally`. Wrap planner, executor, recovery, summarizer, linter, evaluator, skills/workers, tools, checkpoint reads, and persistence adapters. Normalize dict/object usage metadata in one function.

```python
with metrics.span("executor.model"):
    response = await model.ainvoke(messages)
metrics.add_usage("executor", response.usage_metadata or {})
```

DONE carries the snapshot; backend does no extra `aget_state` usage fetch. RunArtifact displays totals and per-stage breakdown.

- [ ] **Step 4: Run tests and commit**

Run: `python -m unittest tests.test_runtime_metrics -v`  
Expected: aggregation, nested span, exception, and redaction tests PASS.

```bash
git add agent/runtime/metrics.py agent/telemetry.py agent/graph/nodes.py agent/runtime/runner.py agent/runtime/artifacts.py frontend/src/types/artifact.ts tests/test_runtime_metrics.py
git commit -m "feat(metrics): report complete run timing and usage"
```

### Task 3: Build memory, MCP, tools, and models once per turn

**Files:**
- Create: `agent/runtime/turn_context.py`
- Modify: `agent/graph/nodes.py`
- Modify: `agent/mcp.py`
- Modify: `agent/tools/memory_tool.py`
- Modify: `agent/llm.py`
- Modify: `agent/graph/tools_registry.py`
- Test: `tests/test_turn_context.py`
- Modify: `tests/performance/test_turn_budget.py`

**Interfaces:**
- Produces `TurnContext(user_query, recalled_memory, mcp_tools, tools, model_clients, workspace)`.
- Produces `async prepare_turn_context(input, config) -> TurnContext` once at run start.
- Produces MCP cache entries `(value, expires_at, error_summary)` with 300/30 second TTLs.

- [ ] **Step 1: Write once-per-turn tests**

```python
from collections import Counter

from tests.performance.fakes import fake_config, fake_input, services_for_counter


class TurnContextTests(unittest.IsolatedAsyncioTestCase):
    async def test_executor_rounds_share_prepared_context(self):
        calls = Counter()
        context = await prepare_turn_context(
            fake_input("fix auth"),
            fake_config(),
            services=services_for_counter(calls),
        )
        await executor_with_context(context)
        await executor_with_context(context)
        self.assertEqual(calls["memory"], 1)
        self.assertEqual(calls["mcp"], 1)
        self.assertEqual(calls["bind_tools"], 1)

    async def test_failed_mcp_uses_negative_cache(self):
        service = failing_mcp_service()
        await service.get_tools("project")
        await service.get_tools("project")
        self.assertEqual(service.discovery_calls, 1)
```

- [ ] **Step 2: Run and verify failures**

Run: `python -m unittest tests.test_turn_context -v`  
Expected: repeated executor calls repeat preparation.

- [ ] **Step 3: Implement turn preparation**

Use the latest user message text as the memory query. Recall enabled global/project memories once, capped by configured count and token budget. Discover MCP once with cache/backoff. Resolve approved tools once. Create/bind role model clients once for the current provider/model/key fingerprint. Store TurnContext in `configurable` runtime context, not persistent graph state.

- [ ] **Step 4: Update budget tests and commit**

Run: `python -m unittest tests.test_turn_context tests.performance.test_turn_budget -v`  
Expected: every target call-count budget PASS.

```bash
git add agent/runtime/turn_context.py agent/graph/nodes.py agent/mcp.py agent/tools/memory_tool.py agent/llm.py agent/graph/tools_registry.py tests/test_turn_context.py tests/performance/test_turn_budget.py
git commit -m "perf(agent): prepare context once per turn"
```

### Task 4: Replace full workspace rescans with incremental metadata updates

**Files:**
- Create: `backend/services/workspace_changes.py`
- Modify: `backend/services/workspace.py`
- Modify: `backend/routers/workspaces.py`
- Modify: `backend/services/patch_manager.py`
- Modify: `agent/workspace.py`
- Modify: `agent/tools/change_tracker.py`
- Modify: `frontend/src/components/workbench/ContextDrawer.tsx`
- Modify: `frontend/src/components/workbench/CommandPalette.tsx`
- Modify: `frontend/src/contexts/WorkbenchContext.tsx`
- Test: `tests/backend/test_workspace_changes.py`
- Test: `frontend/src/components/workbench/contextRefresh.test.tsx`

**Interfaces:**
- Defines `FileChange(path, before_size, after_size, operation)`.
- Produces `apply_workspace_metadata_delta(workspace, changes)`.
- Produces `refresh_git_context(root) -> (head, dirty_digest)` using at most two Git commands.
- Frontend exposes distinct `refreshTree()` and `refreshBackendContext()` operations; one user action invokes each requested operation once.

- [ ] **Step 1: Write incremental-stat tests**

```python
from tests.backend.support import stub_workspace


class WorkspaceChangeTests(unittest.TestCase):
    def test_create_updates_count_and_size_without_scan(self):
        workspace = stub_workspace(file_count=2, size_bytes=20)
        apply_workspace_metadata_delta(workspace, [FileChange("a.py", 0, 12, "create")])
        self.assertEqual((workspace.file_count, workspace.size_bytes), (3, 32))

    def test_edit_updates_only_size(self):
        workspace = stub_workspace(file_count=2, size_bytes=20)
        apply_workspace_metadata_delta(workspace, [FileChange("a.py", 5, 8, "edit")])
        self.assertEqual((workspace.file_count, workspace.size_bytes), (2, 23))
```

In the frontend test, click Context Drawer refresh and assert each context endpoint is called once, not twice. Invoke the command-palette “Refresh retrieval context” action and assert it calls the backend refresh endpoint rather than only incrementing a local tree version.

- [ ] **Step 2: Run and verify failure**

Run: `python -m unittest tests.backend.test_workspace_changes -v`  
Expected: delta helpers do not exist and current mutations invoke full stats refresh.

Run: `cd frontend && npm test -- --run src/components/workbench/contextRefresh.test.tsx`  
Expected: duplicate request fan-out and local-only command behavior fail.

- [ ] **Step 3: Implement deltas and bounded reconciliation**

File CRUD and patch services already know before/after content; pass exact size deltas. Rename preserves totals. Delete directory computes only that subtree before deletion. Run a full reconciliation only on initial import, explicit `/context refresh`, or detected inconsistency.

For Git repositories, call `git rev-parse HEAD` and one `git status --porcelain=v1 -z`; hash the status bytes for `dirty_digest`. For non-Git workspaces, update a rolling context digest from sorted changed path/digest pairs instead of hashing 2,000 files after every write.

In the web workbench, remove the refresh-counter-plus-direct-load combination. `refreshTree` changes only file-tree state; `refreshBackendContext` calls the version/index refresh endpoint and then reloads the context summary. Both Context Drawer and Command Palette call the named operation once and display its error instead of treating a local counter as backend success.

- [ ] **Step 4: Run tests and commit**

Run: `python -m unittest tests.backend.test_workspace_changes -v`  
Run: `cd frontend && npm test -- --run src/components/workbench/contextRefresh.test.tsx`  
Expected: create/edit/delete/rename/patch delta and reconciliation tests PASS with zero full scans in ordinary edits; frontend refresh counts and backend effects PASS.

```bash
git add backend/services/workspace_changes.py backend/services/workspace.py backend/routers/workspaces.py backend/services/patch_manager.py agent/workspace.py agent/tools/change_tracker.py frontend/src/components/workbench/ContextDrawer.tsx frontend/src/components/workbench/CommandPalette.tsx frontend/src/contexts/WorkbenchContext.tsx tests/backend/test_workspace_changes.py frontend/src/components/workbench/contextRefresh.test.tsx
git commit -m "perf(workspace): update metadata incrementally"
```

### Task 5: Isolate streaming transcript renders

**Files:**
- Create: `frontend/src/components/chat/MessageRow.tsx`
- Create: `frontend/src/components/chat/StreamingText.tsx`
- Modify: `frontend/src/components/chat/MessageList.tsx`
- Modify: `frontend/src/components/chat/MarkdownMessage.tsx`
- Modify: `frontend/src/components/agent/AgentPanel.tsx`
- Modify: `frontend/src/pages/ChatPage.tsx`
- Create: `frontend/src/components/chat/streamingRender.test.tsx`

**Interfaces:**
- Completed rows are memoized by `(id, content, pending, artifact revision)`.
- Pending assistant content uses `StreamingText`; final content uses Markdown once.
- Auto-scroll follows only while the user remains within 80 px of the bottom.

- [ ] **Step 1: Write render-count tests**

Use a test spy component around MarkdownMessage. Send 100 token events in one fake-timer interval and assert the completed first message renders once, the pending row flushes once, and Markdown parsing for the pending row occurs only after DONE.

- [ ] **Step 2: Run and verify failure**

Run: `cd frontend && npm test -- --run src/components/chat/streamingRender.test.tsx`  
Expected: full message list and Markdown rerender during token flushing.

- [ ] **Step 3: Implement row isolation and follow behavior**

Use `React.memo(MessageRow)`. Hoist Markdown component/plugin objects to module scope. During streaming, render escaped plain text with a caret; on terminal event, render ReactMarkdown. Connect the existing bottom ref and disable follow mode when the user scrolls more than 80 px upward; show a “Jump to latest” button.

- [ ] **Step 4: Run tests and commit**

```bash
git add frontend/src/components/chat/MessageRow.tsx frontend/src/components/chat/StreamingText.tsx frontend/src/components/chat/MessageList.tsx frontend/src/components/chat/MarkdownMessage.tsx frontend/src/components/agent/AgentPanel.tsx frontend/src/pages/ChatPage.tsx frontend/src/components/chat/streamingRender.test.tsx
git commit -m "perf(web): isolate streaming transcript renders"
```

### Task 6: Reduce route, editor, syntax, and preview bundle/runtime work

**Files:**
- Modify: `frontend/src/App.tsx`
- Modify: `frontend/src/components/chat/LazyCodeBlock.tsx`
- Modify: `frontend/src/components/workbench/CenterWorkbench.tsx`
- Modify: `frontend/src/components/sandbox/WebPreview.tsx`
- Create: `frontend/src/components/sandbox/WebPreview.test.tsx`
- Modify: `frontend/vite.config.ts`
- Modify: `docs/performance-baseline.md`

**Interfaces:**
- Login and chat routes are lazy modules.
- Syntax highlighting registers only `bash`, `css`, `html`, `javascript`, `json`, `markdown`, `python`, `typescript`, and plaintext fallback.
- Preview observes process exit and batches output at 100 ms.

- [ ] **Step 1: Write preview lifecycle tests**

Assert a project without `package.json` shows a clear unsupported state without spawning. Assert a missing start script shows an error. Assert process exit before `server-ready` transitions to failed. Assert retry removes listeners and terminates the previous process.

- [ ] **Step 2: Run and verify failures**

Run: `cd frontend && npm test -- --run src/components/sandbox/WebPreview.test.tsx`  
Expected: preview remains running or leaks listeners.

- [ ] **Step 3: Implement lazy boundaries and small language registry**

Use `React.lazy` for LoginPage, ChatPage, preview, GitHub dialogs, and diff review. Replace the full Prism style/language barrel with the light highlighter and explicit language registration. Split CenterWorkbench vendor chunks only where Vite manifest evidence shows a distinct lazy boundary.

- [ ] **Step 4: Build and record artifact comparison**

Run: `cd frontend && npm run build`  
Expected: exit 0, no approximately 500 language chunks, login route does not depend on workbench chunks, and main entry is smaller than the pre-plan baseline recorded in `docs/performance-baseline.md`.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/App.tsx frontend/src/components/chat/LazyCodeBlock.tsx frontend/src/components/workbench/CenterWorkbench.tsx frontend/src/components/sandbox/WebPreview.tsx frontend/src/components/sandbox/WebPreview.test.tsx frontend/vite.config.ts docs/performance-baseline.md
git commit -m "perf(web): lazy load routes preview and syntax languages"
```

### Task 7: Expose route, capability, timing, and cost diagnostics

**Files:**
- Create: `agent/runtime/diagnostics.py`
- Modify: `agent/ui/commands/system.py`
- Modify: `backend/routers/runs.py`
- Modify: `frontend/src/components/layout/StatusBar.tsx`
- Modify: `frontend/src/components/chat/RunTimeline.tsx`
- Test: `tests/test_diagnostics.py`

**Interfaces:**
- Produces `capability_report(config)`, `route_report(state)`, and `timing_report(metrics)` with redacted structured output.
- TUI commands `/capabilities`, `/route`, `/timing`.
- Web run details show provider/model, total calls/tokens/cost, per-stage duration, cache status, and unavailable capabilities.

- [ ] **Step 1: Write redaction and truth tests**

Create configs with/without DB, embeddings, MCP, custom tools, shell, and provider key. Assert capability report matches effective runtime behavior and contains no secret. Assert route report for a complex edit names context→planner, while a greeting names direct-chat.

- [ ] **Step 2: Run and verify failure**

Run: `python -m unittest tests.test_diagnostics -v`  
Expected: diagnostic helpers/commands do not exist.

- [ ] **Step 3: Implement and surface diagnostics**

StatusBar replaces “Default model” with actual provider/model and permission profile. Timing UI distinguishes provider wait, local compute, tool time, approval wait, and persistence. Unknown price yields “cost unavailable” rather than zero.

- [ ] **Step 4: Run tests and commit**

```bash
git add agent/runtime/diagnostics.py agent/ui/commands/system.py backend/routers/runs.py frontend/src/components/layout/StatusBar.tsx frontend/src/components/chat/RunTimeline.tsx tests/test_diagnostics.py
git commit -m "feat(observability): show route capability timing and cost"
```

## Plan 4 Completion Gate

- [ ] All deterministic call-count budgets pass.
- [ ] Memory recall, MCP discovery, and tool binding occur once per turn in every executor-round test.
- [ ] Usage totals include all model roles and workers introduced later.
- [ ] Ordinary file edits perform zero full workspace scans.
- [ ] A 2,000-token fake stream does not repeatedly parse Markdown while pending.
- [ ] Production frontend build has no language-chunk explosion and passes typecheck/lint/tests.
- [ ] Manual real-provider smoke report separates external model latency from local overhead.
- [ ] Update `docs/performance-baseline.md` with before/after counts and measurements.
- [ ] Request code review before Plan 5.
