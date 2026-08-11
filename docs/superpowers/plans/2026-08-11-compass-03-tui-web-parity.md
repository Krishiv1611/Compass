# Compass TUI and Web Parity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make TUI and web present the same plans, approvals, clarifications, tools, run status, changed files, checks, and terminal outcomes while keeping deliberate security differences explicit.

**Architecture:** Introduce a session-owned web run controller and a pure event-to-view projection shared conceptually with the TUI renderer. Keep surface components thin: the runtime owns event meaning, the controller owns socket lifecycle, and workspace-scoped stores own editor/patch/publish data. Extract TUI slash commands behind a small registry after behavior is covered.

**Tech Stack:** React 19, TypeScript 6, Vitest, Testing Library, WebSocket, existing FastAPI endpoints, Rich/Prompt Toolkit TUI, Python `unittest`.

## Global Constraints

- Consume `ResumeAction`, `InterruptKind`, and event values from Plan 1 without aliases such as `yes` or `no`.
- A web socket, token buffer, timer, approval, and live run belong to exactly one `session_id` and one `run_id`.
- Ignore every callback whose controller generation is no longer current.
- Key all editor state by `(workspace_id, path)`.
- Clear stale workspace-scoped data before loading replacement data.
- Web continues to deny shell and command MCP; TUI labels these as local-only.
- Preserve existing routes, settings, file editing, patch review, GitHub, preview, and four modes.

---

## File Structure

- Create `frontend/src/runtime/RunController.ts`: socket/run lifecycle without React.
- Create `frontend/src/test/fakeSocket.ts`: deterministic browser-free socket factory shared by controller tests.
- Create `frontend/src/hooks/useRunController.ts`: React adapter for the controller.
- Create `frontend/src/runtime/projectRunEvent.ts`: event-to-view reducer.
- Create `frontend/src/types/artifact.ts`: plan, tool, check, file, and terminal view types.
- Create `agent/ui/event_renderer.py`: TUI projection of shared runtime events.
- Create `agent/ui/commands/`: focused slash-command registry and handlers.
- Modify ChatPage, RunContext, MessageList, Timeline, editor/workbench, patches, settings, skills, sessions, and TUI.
- Add focused frontend tests and Python TUI command tests.

### Task 1: Build a session-owned web run controller

**Files:**
- Create: `frontend/src/runtime/RunController.ts`
- Create: `frontend/src/runtime/RunController.test.ts`
- Create: `frontend/src/test/fakeSocket.ts`
- Create: `frontend/src/hooks/useRunController.ts`
- Modify: `frontend/src/api/chat.ts`
- Modify: `frontend/src/api/runs.ts`
- Modify: `frontend/src/pages/ChatPage.tsx`

**Interfaces:**
- Produces `RunController.start({sessionId, content, mode, contextFiles})`.
- Produces `RunController.resume(payload: ResumePayload)`.
- Produces `RunController.cancel()` and `RunController.dispose()`.
- Emits callbacks only while `(sessionId, runId, generation)` matches the active run.
- Test helper `createFakeSocketFactory()` exposes `create(url)`, `forSession(sessionId)`, and fake `open/message/error/close` methods without timers or network access.

- [ ] **Step 1: Write lifecycle tests with a fake WebSocket**

```typescript
import { describe, expect, it, vi } from "vitest";
import { createFakeSocketFactory } from "../test/fakeSocket";
import { RunController } from "./RunController";

describe("RunController", () => {
  it("ignores events from a replaced session", async () => {
    const received: string[] = [];
    const sockets = createFakeSocketFactory();
    const controller = new RunController({
      createSocket: sockets.create,
      cancelRun: vi.fn().mockResolvedValue(undefined),
      onEvent: event => received.push(String(event.content ?? "")),
    });
    controller.start({sessionId: "A", content: "first", mode: "edit", contextFiles: []});
    controller.start({sessionId: "B", content: "second", mode: "edit", contextFiles: []});
    sockets.forSession("A").message({type: "token", content: "old"});
    sockets.forSession("B").message({type: "token", content: "new"});
    expect(received).toEqual(["new"]);
  });

  it("knows the run id before the first server event", () => {
    const sockets = createFakeSocketFactory();
    const controller = new RunController({
      createSocket: sockets.create,
      cancelRun: vi.fn().mockResolvedValue(undefined),
      onEvent: vi.fn(),
    });
    const handle = controller.start({sessionId: "A", content: "x", mode: "ask", contextFiles: []});
    expect(handle.runId).toMatch(/^[0-9a-f-]{36}$/);
  });
});
```

- [ ] **Step 2: Run and verify failure**

Run: `cd frontend && npm test -- --run src/runtime/RunController.test.ts`  
Expected: FAIL because the controller does not exist.

- [ ] **Step 3: Implement controller identity and cancellation**

`start` generates `runId = crypto.randomUUID()` and increments `generation`. It closes the previous socket, clears its timers, and sends `run_id` in the first WebSocket message. Backend Plan 2 must create/validate the run with this client-supplied ID. Every `onopen`, `onmessage`, `onerror`, and `onclose` closure captures the generation and returns immediately when stale.

`cancel` first calls the HTTP cancel endpoint using the already-known run ID, then closes the socket in `finally`. `dispose` cancels timers, closes without changing another controller, and marks the run inactive.

- [ ] **Step 4: Replace ChatPage socket refs**

Move socket, active run ID, token buffering, and generation logic out of `ChatPage.tsx`. The page consumes controller callbacks and contains only transcript/workspace composition. Call `dispose()` when `sessionParam` changes and on unmount.

- [ ] **Step 5: Run tests and commit**

Run: `cd frontend && npm test -- --run src/runtime/RunController.test.ts`  
Expected: session replacement, cancellation, stale close, and buffer-flush tests PASS.

```bash
git add frontend/src/runtime/RunController.ts frontend/src/runtime/RunController.test.ts frontend/src/test/fakeSocket.ts frontend/src/hooks/useRunController.ts frontend/src/api/chat.ts frontend/src/api/runs.ts frontend/src/pages/ChatPage.tsx
git commit -m "fix(web): own each run by session and generation"
```

### Task 2: Render tool approval, plan revision, and clarification identically

**Files:**
- Modify: `frontend/src/components/chat/MessageList.tsx`
- Create: `frontend/src/components/chat/ToolApprovalCard.tsx`
- Modify: `frontend/src/components/chat/PlanReviewCard.tsx`
- Create: `frontend/src/components/chat/ClarificationCard.tsx`
- Modify: `frontend/src/pages/ChatPage.tsx`
- Modify: `agent/ui/tui.py`
- Create: `tests/test_surface_resume_actions.py`
- Create: `frontend/src/components/chat/InterruptCards.test.tsx`

**Interfaces:**
- Every surface calls `resume({action, feedback})` with `ResumePayload`.
- Tool buttons map to `approve`, `always`, `skip`, `deny`.
- Plan buttons map to `execute_plan`, `revise_plan`, `cancel`.
- Clarification submission maps to `answer` with user text in `feedback`.

- [ ] **Step 1: Write frontend interaction tests**

```typescript
it("sends approve rather than yes", async () => {
  const resume = vi.fn();
  render(<ToolApprovalCard interrupt={toolInterrupt} onResume={resume} />);
  await userEvent.click(screen.getByRole("button", {name: "Approve once"}));
  expect(resume).toHaveBeenCalledWith({action: "approve"});
});

it("carries plan revision feedback", async () => {
  const resume = vi.fn();
  render(<PlanReviewCard plan="1. Edit" onResume={resume} />);
  await userEvent.click(screen.getByRole("button", {name: "Revise"}));
  await userEvent.type(screen.getByRole("textbox"), "Split the database change");
  await userEvent.click(screen.getByRole("button", {name: "Submit revision"}));
  expect(resume).toHaveBeenCalledWith({action: "revise_plan", feedback: "Split the database change"});
});
```

- [ ] **Step 2: Run and verify failures**

Run: `cd frontend && npm test -- --run src/components/chat/InterruptCards.test.tsx`  
Expected: current approval sends `yes` and no clarification card exists.

- [ ] **Step 3: Implement typed cards and preserve event content**

Store the complete interrupt event, including `content` and typed `data`. Render exact tool names/arguments and clarification prompt. Disable all action buttons after one submission until a new event arrives. Use the same copy in TUI: Approve once, Always allow for this thread, Skip, Deny, Execute plan, Revise plan, Cancel, Answer.

- [ ] **Step 4: Add a cross-surface source contract test**

Read the frontend action type and TUI handler mapping. Assert both sets equal `set(ResumeAction)` excluding actions not valid for that card. This test prevents future `yes/no` drift.

Run: `python -m unittest tests.test_surface_resume_actions -v`  
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/components/chat/MessageList.tsx frontend/src/components/chat/ToolApprovalCard.tsx frontend/src/components/chat/PlanReviewCard.tsx frontend/src/components/chat/ClarificationCard.tsx frontend/src/components/chat/InterruptCards.test.tsx frontend/src/pages/ChatPage.tsx agent/ui/tui.py tests/test_surface_resume_actions.py
git commit -m "fix(ui): align approval plan and clarification actions"
```

### Task 3: Project runtime events into one run artifact model

**Files:**
- Create: `agent/runtime/artifacts.py`
- Modify: `agent/runtime/events.py`
- Modify: `agent/runtime/runner.py`
- Create: `frontend/src/types/artifact.ts`
- Create: `frontend/src/runtime/projectRunEvent.ts`
- Create: `frontend/src/runtime/projectRunEvent.test.ts`
- Create: `agent/ui/event_renderer.py`
- Modify: `frontend/src/contexts/RunContext.tsx`
- Modify: `frontend/src/components/chat/RunTimeline.tsx`
- Modify: `frontend/src/components/chat/ToolCallCard.tsx`
- Modify: `frontend/src/components/chat/PlanChecklist.tsx`
- Modify: `agent/ui/tui.py`
- Create: `tests/fixtures/run_events/basic_edit.json`
- Test: `tests/test_run_artifact.py`

**Interfaces:**
- Produces `RunArtifact` with `plan`, `steps`, `tools`, `changed_files`, `checks`, `usage`, `terminal_status`, and `final_summary`.
- Produces pure `reduce_run_event(artifact, event) -> RunArtifact` in Python and `projectRunEvent` in TypeScript with matching fixtures.
- Produces `ToolCallAssembler.add(chunk) -> list[StreamEvent]`, emitting one tool-call event only after name, stable ID, and complete JSON arguments are available.

- [ ] **Step 1: Define a shared JSON fixture and failing reducers**

Create `tests/fixtures/run_events/basic_edit.json` containing status, split tool-call chunks, the resulting complete tool-call event, tool-result, plan-created, workspace-patch, verification result, usage, and done events. Add a runner test where name and JSON arguments arrive in separate chunks; assert the emitted call retains the real ID and full arguments and is emitted exactly once. Python and TypeScript tests load the projected events and assert:

```json
{
  "terminal_status": "completed",
  "changed_files": ["src/app.py"],
  "completed_steps": 2,
  "tool_names": ["read_file", "edit_file"],
  "checks_passed": 1
}
```

- [ ] **Step 2: Run and verify failures**

Run: `python -m unittest tests.test_run_artifact -v`  
Run: `cd frontend && npm test -- --run src/runtime/projectRunEvent.test.ts`  
Expected: reducers/types do not exist.

- [ ] **Step 3: Implement artifact types and reducers**

Use stable IDs from runtime events; do not generate `Date.now()` identity inside reducers. Assemble streamed tool-call chunks by provider call ID/index and parse arguments only when complete; never replace partial JSON with `{}`. Interpret `event.node`, `event.data.duration_ms`, and `event.seq`; stop expecting top-level `stage` fields that runtime never sends. Preserve raw events separately only for debugging.

- [ ] **Step 4: Connect both surfaces**

RunContext owns one artifact per active run and resets it in `startRun`, including `firstTokenSeen.current = false`. TUI passes each event through `event_renderer.py`. Timeline, plan checklist, and tool cards render the artifact rather than unreachable transcript fields. Historical run API hydrates the same reducer on reload.

- [ ] **Step 5: Run tests and commit**

Run both reducer suites; expected final projections are byte-for-byte equivalent after JSON serialization.

```bash
git add agent/runtime/artifacts.py agent/runtime/events.py agent/runtime/runner.py agent/ui/event_renderer.py agent/ui/tui.py frontend/src/types/artifact.ts frontend/src/runtime/projectRunEvent.ts frontend/src/runtime/projectRunEvent.test.ts frontend/src/contexts/RunContext.tsx frontend/src/components/chat/RunTimeline.tsx frontend/src/components/chat/ToolCallCard.tsx frontend/src/components/chat/PlanChecklist.tsx tests/test_run_artifact.py tests/fixtures/run_events/basic_edit.json
git commit -m "feat(runtime): project shared run walkthrough artifacts"
```

### Task 4: Scope editor data and async loads to the active workspace

**Files:**
- Create: `frontend/src/components/workbench/editorState.ts`
- Create: `frontend/src/components/workbench/editorState.test.ts`
- Modify: `frontend/src/components/workbench/CenterWorkbench.tsx`
- Modify: `frontend/src/hooks/useWorkspaceTree.ts`
- Modify: `frontend/src/contexts/WorkbenchContext.tsx`
- Modify: `frontend/src/components/sandbox/FileExplorer.tsx`

**Interfaces:**
- Produces `editorKey(workspaceId, path) -> string`.
- Each load/save carries a generation and active workspace ID.
- Patch/tree versions invalidate affected open-file cache entries.
- Editor tracks dirty state per `(workspace_id, path)`; Ctrl/Cmd+S saves the active file, and task/workspace navigation warns before discarding unsaved content.

- [ ] **Step 1: Write reducer tests**

```typescript
it("does not share same-path content between projects", () => {
  let state = emptyEditorState();
  state = storeLoadedFile(state, {workspaceId: "A", path: "src/app.ts", content: "A", generation: 1});
  state = storeLoadedFile(state, {workspaceId: "B", path: "src/app.ts", content: "B", generation: 2});
  expect(selectContent(state, "A", "src/app.ts")).toBe("A");
  expect(selectContent(state, "B", "src/app.ts")).toBe("B");
});

it("ignores late file loads", () => {
  const state = storeLoadedFile(beginLoad(emptyEditorState(), "B", "b.ts", 2), {
    workspaceId: "A", path: "a.ts", content: "late", generation: 1,
  });
  expect(selectContent(state, "A", "a.ts")).toBeUndefined();
});
```

Add an interaction test that edits workspace A, switches to B, and asserts a discard confirmation appears. Press Ctrl/Cmd+S and assert Save is awaited, the dirty indicator clears only on success, and a failed save retains both content and dirty state.

- [ ] **Step 2: Run and verify failure**

Run: `cd frontend && npm test -- --run src/components/workbench/editorState.test.ts`  
Expected: editor state helpers do not exist.

- [ ] **Step 3: Implement scoped state and invalidation**

Use key `${workspaceId}\u0000${path}`. Abort fetches on workspace/path changes with `AbortController`. On patch-created/applied/undone events, invalidate affected paths and refetch an open affected file only when it has no unsaved local changes; otherwise show a conflict banner. Register the save shortcut while the editor is active, show a visible dirty marker, and use the same dirty-state guard for in-app task/workspace changes and `beforeunload`.

- [ ] **Step 4: Wire create/rename/delete controls**

Pass existing workspace API callbacks into `FileExplorer`. After successful create/rename/delete, refresh once, update selection, and preserve an undo/checkpoint artifact. Empty workspaces show a “Create first file” action.

- [ ] **Step 5: Run tests and commit**

```bash
git add frontend/src/components/workbench/editorState.ts frontend/src/components/workbench/editorState.test.ts frontend/src/components/workbench/CenterWorkbench.tsx frontend/src/hooks/useWorkspaceTree.ts frontend/src/contexts/WorkbenchContext.tsx frontend/src/components/sandbox/FileExplorer.tsx
git commit -m "fix(workbench): scope editor state by workspace"
```

### Task 5: Clear stale patch, publish, and workspace-selection state

**Files:**
- Modify: `frontend/src/components/sandbox/DiffReviewPanel.tsx`
- Modify: `frontend/src/components/github/GitHubImportDialog.tsx`
- Modify: `frontend/src/components/github/GitHubPublishDialog.tsx`
- Modify: `frontend/src/components/sandbox/WorkspaceLanding.tsx`
- Modify: `frontend/src/pages/ChatPage.tsx`
- Modify: `frontend/src/api/projects.ts`
- Test: `frontend/src/components/sandbox/workspaceTransitions.test.tsx`

**Interfaces:**
- Workspace-scoped request state is `{workspaceId, generation, status, data, error}`.
- Recent-project selection calls the Plan 2 attach endpoint before updating local workbench state.
- GitHub repository/branch loads use request generations; publish file selection may include any current workspace path, not only paths originating in applied agent patches.

- [ ] **Step 1: Write wrong-target prevention tests**

Test switching from workspace A to B while A’s patch request is pending. Resolve A after B and assert no A patch appears. Render a selected recent workspace belonging to session X while current session is Y; assert attach API is called before `setWorkspace`. Switch publish dialog A→B and assert repository, branch, commit, and PR state clear immediately. Load GitHub page 2 and assert page 1 is not automatically fetched/replaced; switch repository A→B, resolve A last, and assert only B branches render. Assert `owner/repo.with.dots.git` parses correctly and a manually saved workspace path can be selected for publish.

- [ ] **Step 2: Run and verify failures**

Run: `cd frontend && npm test -- --run src/components/sandbox/workspaceTransitions.test.tsx`  
Expected: stale patch/publish data remains and recent selection skips attachment.

- [ ] **Step 3: Implement generation-scoped loaders**

Clear visible data at load start, increment generation, abort the prior request where possible, and discard stale responses. Keep GitHub page cursor in response state rather than in the initial-load callback dependency; “Load more” appends exactly once. Clear branch selection immediately when repository changes. Disable mutation buttons unless the record workspace ID equals the current workspace ID. Recent-project click awaits `workspaceApi.attachWorkspace(currentSessionId, workspace.id)` and then refreshes both workspace and session context. Publish dialog loads the bounded workspace tree and lets the user select current files; applied patch paths are merely preselected. Parse the remote by removing the final optional `.git` suffix rather than rejecting dots in the repository name.

- [ ] **Step 4: Run tests and commit**

```bash
git add frontend/src/components/sandbox/DiffReviewPanel.tsx frontend/src/components/github/GitHubImportDialog.tsx frontend/src/components/github/GitHubPublishDialog.tsx frontend/src/components/sandbox/WorkspaceLanding.tsx frontend/src/pages/ChatPage.tsx frontend/src/api/projects.ts frontend/src/components/sandbox/workspaceTransitions.test.tsx
git commit -m "fix(web): prevent stale workspace mutations"
```

### Task 6: Make settings, memory, skills, and uploads reachable and honest

**Files:**
- Modify: `frontend/src/components/settings/SettingsModal.tsx`
- Modify: `frontend/src/components/settings/MemoryManager.tsx`
- Modify: `frontend/src/components/settings/SkillsManager.tsx`
- Modify: `frontend/src/components/chat/ChatInput.tsx`
- Modify: `frontend/src/api/preferences.ts`
- Modify: `frontend/src/api/uploads.ts`
- Modify: `frontend/src/pages/ChatPage.tsx`
- Test: `frontend/src/components/settings/SettingsModal.test.tsx`
- Test: `frontend/src/components/chat/ChatInput.test.tsx`

**Interfaces:**
- Root tabs are `account`, `model`, `appearance`, `memory`, `skills`, `advanced`.
- SkillsManager exposes selected `activeSkill: string | null` to the next run payload.
- Context-only sends count as valid when `contextFiles.length > 0`.

- [ ] **Step 1: Write reachability and send tests**

Render Settings, click Memory, and assert MemoryManager content is visible. Simulate a failed settings GET and assert Save remains disabled. Enter a new API key, close, reopen, and assert the unsaved key field is empty. Select a skill and assert the run payload contains `active_skill`. Add one context reference with empty text and assert `onSend` is awaited and receives it.

- [ ] **Step 2: Run and verify failures**

Run: `cd frontend && npm test -- --run src/components/settings/SettingsModal.test.tsx src/components/chat/ChatInput.test.tsx`  
Expected: memory is hidden, failed GET permits defaults, skill activation absent, context-only send discarded.

- [ ] **Step 3: Flatten tabs and expose real policy**

Move Memory and Skills panels to root-level `TabsContent`. Fetch settings once per modal opening, not on theme changes. Clear secret input on close and after save. Show actual provider/model, `safe_mode` as “Stage agent file changes for review”, and `fast_mode` as “Reduce approval prompts; shell and custom tools still require approval”. Add provider test/remove buttons from Plan 2.

- [ ] **Step 4: Add upload preflight**

Check server-advertised limits before upload, retain failed files with retry/remove controls, await `onSend`, and expose existing delete-upload API. Clear the composer only after upload/run start succeeds.

- [ ] **Step 5: Run tests and commit**

```bash
git add frontend/src/components/settings/SettingsModal.tsx frontend/src/components/settings/MemoryManager.tsx frontend/src/components/settings/SkillsManager.tsx frontend/src/components/chat/ChatInput.tsx frontend/src/api/preferences.ts frontend/src/api/uploads.ts frontend/src/pages/ChatPage.tsx frontend/src/components/settings/SettingsModal.test.tsx frontend/src/components/chat/ChatInput.test.tsx
git commit -m "fix(web): expose settings skills memory and context sends"
```

### Task 7: Extract TUI slash commands behind a tested registry

**Files:**
- Create: `agent/ui/commands/__init__.py`
- Create: `agent/ui/commands/models.py`
- Create: `agent/ui/commands/registry.py`
- Create: `agent/ui/commands/session.py`
- Create: `agent/ui/commands/context.py`
- Create: `agent/ui/commands/integrations.py`
- Create: `agent/ui/commands/system.py`
- Modify: `agent/ui/tui.py`
- Test: `tests/test_tui_commands.py`

**Interfaces:**
- Defines `CommandContext` with console, workflow, run config, session store, workspace, and settings.
- Defines `SlashCommand(name, aliases, help, handler)`.
- Handler returns `CommandResult(consumed, message, state_updates)`.

- [ ] **Step 1: Write registry and false-success tests**

```python
class TuiCommandTests(unittest.IsolatedAsyncioTestCase):
    async def test_schedule_never_claims_a_task_was_queued(self):
        result = await registry.execute("/schedule tomorrow run tests", context)
        self.assertTrue(result.consumed)
        self.assertIn("not available", result.message.lower())
        self.assertNotIn("queued", result.message.lower())

    async def test_history_reads_checkpoint_messages(self):
        result = await registry.execute("/history", context_with_checkpoint(["one", "two"]))
        self.assertIn("one", result.message)
        self.assertIn("two", result.message)
```

- [ ] **Step 2: Run and verify failures**

Run: `python -m unittest tests.test_tui_commands -v`  
Expected: command registry does not exist and `/schedule` falsely claims success.

- [ ] **Step 3: Extract behavior without redesigning the screen**

Move session commands, context/index commands, MCP/GitHub/config commands, and system commands into focused modules. Keep their names/aliases. `/doctor` checks actual imports, DB/checkpointer state, provider credential, MCP filename, workspace permissions, and frontend URL. `/mcp` calls `get_mcp_tools`. `/ui` checks the configured web URL and opens it only when reachable; otherwise prints the exact start command. `/schedule` reports unavailable without mutation. `/history` reads checkpoint state. `/model` reads active provider/model rather than a startup constant.

- [ ] **Step 4: Run tests and commit**

Run: `python -m unittest tests.test_tui_commands -v`  
Expected: registry, help, alias, history, doctor, MCP, UI, schedule, and model tests PASS.

```bash
git add agent/ui/commands/__init__.py agent/ui/commands/models.py agent/ui/commands/registry.py agent/ui/commands/session.py agent/ui/commands/context.py agent/ui/commands/integrations.py agent/ui/commands/system.py agent/ui/tui.py tests/test_tui_commands.py
git commit -m "refactor(tui): extract tested slash commands"
```

### Task 8: Add a TUI/web parity journey suite

**Files:**
- Create: `tests/integration/fake_agent.py`
- Create: `tests/integration/test_surface_parity.py`
- Create: `frontend/src/test/fakeRunServer.ts`
- Create: `frontend/src/pages/ChatPage.parity.test.tsx`

**Interfaces:**
- Fake agent scenarios: `ask`, `approved_edit`, `plan_revise`, `clarification`, `goal_failure`, `cancel`.
- Each scenario uses one fixed event fixture consumed by TUI and web tests.

- [ ] **Step 1: Implement fixture-driven fake scenarios**

The fake server must never call a real model, database, network, shell, or project custom tool. It replays deterministic protocol events and records resume payloads.

- [ ] **Step 2: Assert equivalent outcomes**

For each scenario, assert TUI and web produce the same terminal status, plan text, tool names, changed files, checks, and resume action/feedback. Deliberate differences are limited to display formatting and the web’s absence of shell/MCP command controls.

- [ ] **Step 3: Run full parity suite**

Run: `python -m unittest tests.integration.test_surface_parity -v`  
Run: `cd frontend && npm test -- --run src/pages/ChatPage.parity.test.tsx`  
Expected: all six scenarios PASS in both surfaces.

- [ ] **Step 4: Commit**

```bash
git add tests/integration/fake_agent.py tests/integration/test_surface_parity.py frontend/src/test/fakeRunServer.ts frontend/src/pages/ChatPage.parity.test.tsx
git commit -m "test(ui): protect tui and web runtime parity"
```

## Plan 3 Completion Gate

- [ ] All frontend tests, no-emit typecheck, and lint pass.
- [ ] All Python TUI/parity tests pass.
- [ ] Switching sessions during a stream never changes the new transcript or artifact.
- [ ] Approve once, Always, Skip, Deny, Execute, Revise with feedback, Cancel, and Answer work in both surfaces.
- [ ] Editor, patches, publish dialog, and agent runtime resolve the same active workspace.
- [ ] Memory, skills, provider test/remove, context-only send, and first-file creation are reachable.
- [ ] TUI commands no longer claim unperformed work.
- [ ] Request code review before Plan 4.
