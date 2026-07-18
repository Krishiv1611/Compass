# Compass Web Coding Agent Implementation Plan

This plan is based on the current repository state and the new product direction:

```text
Web Compass:
  upload a project folder
  -> work on an isolated server-side copy
  -> agent proposes/implements changes in that copy
  -> user reviews diffs
  -> user downloads the finished project as a ZIP

TUI Compass:
  run inside a local repository
  -> direct filesystem and shell access
  -> approvals, diffs, undo, and local command execution
```

Compass should not become a direct Codex clone. It should become a web coding agent optimized for safe copied workspaces, with a local-power TUI for users who want direct repo access.

---

## 1. Current Repository State

### 1.1 What Already Exists

Backend:

- `backend/main.py` FastAPI app with CORS, logging, Redis setup, rate limiting, health check, and routers.
- Auth system with JWT, password login, Google/GitHub OAuth, and `/auth/me`.
- Session CRUD with `ChatSession` and persisted `Message` records.
- Chat API:
  - `POST /chat/send`
  - `WebSocket /chat/ws/{session_id}`
- WebSocket streaming event schema in `backend/schemas/chat.py`.
- Upload API for RAG documents in `backend/routers/uploads.py`.
- Workspace API in `backend/routers/workspaces.py`:
  - upload folder
  - read tree
  - read file
  - create file/folder
  - update file
  - delete file/folder
  - rename path
  - download ZIP
- Celery/Redis worker scaffolding in `backend/worker/tasks.py`.
- Tool registry in `agent/graph/tools_registry.py`.
- Web-session tool isolation through `agent/tools/utils.py`.

Agent:

- LangGraph workflow in `agent/graph/workflow.py`.
- Planner, executor, safety, direct chat, loop recovery, summary nodes in `agent/graph/nodes.py`.
- Remote/local tool routing in `agent/graph/remote_tool_node.py`.
- File, directory, grep, shell, memory, todo, skill, RAG tools.
- Safety approvals for risky tools.
- RAG upload/index/search infrastructure.
- Skills infrastructure.
- TUI with streaming, slash commands, local filesystem access, and local shell access.

Frontend:

- React/Vite app with protected routes.
- Auth pages and login modal.
- Main layout with sessions sidebar.
- Chat page with WebSocket streaming.
- Chat input with file attachments and normal/plan modes.
- Monaco-based code sandbox.
- File explorer with create/rename/delete controls.
- Settings drawer.
- Markdown message rendering.
- Basic UI primitives.

### 1.2 What Is Missing

There is no first-class model for:

- Workspace
- Agent run
- Run event
- Workspace patch
- Diff review state
- Terminal job
- Workspace indexing status
- Download/export history

The current app is still session-first. A production web coding agent must become workspace-first.

---

## 2. Verified Current Errors And Risks

### 2.1 Frontend Build Problem

Observed:

```text
npm run build
failed to load config from frontend/vite.config.ts
Could not load node_modules/@tailwindcss/oxide-win32-x64-msvc/...
spawn EPERM
```

Interpretation:

- TypeScript itself passes with `npx tsc -b`.
- The current build failure is likely a native Tailwind/Vite dependency or local Windows permission/sandbox issue.
- This must be fixed before production CI can trust frontend builds.

Required fix:

- Reinstall frontend dependencies cleanly.
- Verify Tailwind native oxide package is installed for Windows.
- Add CI build on a clean environment.
- Keep `npx tsc -b` as a separate type-check step.

### 2.2 Backend Import Requires Correct Python Environment

Observed:

- System Python fails imports with missing `fastapi`.
- Project venv succeeds:

```text
.venv/Scripts/python.exe
OK backend.main
OK backend.routers.workspaces
OK backend.routers.chat
OK backend.services.agent_runner
OK backend.worker.tasks
OK agent.graph.workflow
OK agent.graph.nodes
OK agent.tools.file_tools
OK agent.tools.directory_tools
OK agent.tools.shell_tool
```

Risk:

- Developer onboarding and CI can easily use the wrong Python.

Required fix:

- Document venv usage.
- Add `make`, `just`, or npm scripts for backend checks.
- Add CI that installs requirements and runs import tests.

### 2.3 Import-Time Network And Redis Side Effects

Observed during backend import:

```text
[LLM] Warning: Failed to connect to Redis, using in-memory cache.
[RAG] Warning: Embedding cache unavailable...
```

Risk:

- Importing modules triggers Redis/cache/tracing/tool loading behavior.
- This can slow startup, fail serverless environments, and make tests flaky.

Required fix:

- Move Redis cache setup to FastAPI lifespan or lazy factory.
- Move embedding cache setup to lazy runtime initialization.
- Avoid network calls during module import.
- Convert print warnings into structured logs with clear severity.

### 2.4 Encoding / Mojibake

Observed:

- Many files contain corrupted text like `aEUR`, `a"`, and broken emoji sequences.
- This appears in backend comments, TUI strings, roadmap, and visible terminal output.

Risk:

- Product feels broken.
- TUI display is unprofessional.
- Some strings may render incorrectly to users.

Required fix:

- Normalize all source files to UTF-8.
- Replace corrupted decorations with ASCII or valid UTF-8.
- Add editorconfig and CI check for encoding.

### 2.5 Global Settings Mutation Per User

Observed in:

- `backend/routers/chat.py`
- `backend/worker/tasks.py`

Current behavior:

- User preferences are copied into global `agent.config.settings`.
- `OPENROUTER_API_KEY` is mutated in process environment.
- `workspace_dir` is set globally.

Risk:

- Multi-user leakage.
- Concurrent requests can override model/API key/workspace for other users.
- Web uploaded workspace state is mixed with user global settings.

Required fix:

- Use request/run-scoped config.
- Pass model, API key, workspace id/path through LangGraph `config["configurable"]`.
- Do not mutate global process settings for per-user data.

### 2.6 Redis Rate Limit Middleware Receives `None`

Observed:

- `backend/main.py` calls `app.add_middleware(RedisRateLimitMiddleware, redis_client=redis_client)` before lifespan initializes `redis_client`.

Risk:

- Middleware may always receive `None`.
- Redis rate limiting may silently degrade even when Redis later connects.

Required fix:

- Middleware should read `request.app.state.redis_client`.
- Or add middleware after Redis init through a factory pattern.
- Add health output for active rate-limit backend.

### 2.7 WebSocket Streaming Is Not A Durable Run System

Observed:

- WebSocket streams token/tool events.
- Assistant response is persisted by concatenating token events only.
- Tool events, approvals, errors, patches, and run timeline are not durably modeled.

Risk:

- Refresh loses the live run timeline.
- Tool state is hard to debug.
- User cannot inspect what the agent did after the fact.
- There is no reliable cancel/retry/replay model.

Required fix:

- Add `AgentRun` and `RunEvent` models.
- Persist every significant stream event.
- Frontend should replay run events after refresh.

### 2.8 `rpc_call` Is Not Implemented In Frontend

Observed:

- `frontend/src/pages/ChatPage.tsx` logs `rpc_call` and does nothing else.

Risk:

- If backend emits RPC calls, the web UI silently fails to execute them.
- User sees no clear state or error.

Required product decision:

- Web mode should not use RPC for local tools.
- Web mode should execute only safe server workspace tools.
- TUI relay mode can use RPC later, but should be clearly separate.

### 2.9 Shell Tool Is Confusing In Web Mode

Observed:

- `shell_execute` returns:

```text
Error: Shell execution is disabled for web users for security reasons.
```

- `tools_registry.py` still includes `shell_execute` unless `COMPASS_CLOUD_MODE=true`.
- Frontend settings can list tools without explaining which are available in web mode.

Risk:

- Agent may try shell in web and fail.
- UI says tools are enabled while a key coding-agent capability is disabled.

Required fix:

- Split tool registry by execution environment:
  - web-safe
  - web-disabled
  - TUI-local
  - future Docker-terminal
- Frontend should show this explicitly.

### 2.10 Workspace Ownership Is Incomplete

Observed:

- `backend/routers/workspaces.py` derives path from `current_user.id` and `session_id`.
- It does not consistently validate that `session_id` exists and belongs to the user.
- `get_workspace_dir()` creates folders implicitly.

Risk:

- Users can create workspaces for arbitrary session ids under their own user path.
- Workspace lifecycle is not tied to session lifecycle.
- Deleted sessions may still have accessible workspace directories.

Required fix:

- Validate owned session or workspace record on every workspace endpoint.
- Stop implicit workspace creation except in explicit create/upload flows.
- Add cleanup behavior for deleted sessions/workspaces.

### 2.11 Workspace Upload Is Destructive

Observed:

- Uploading a folder deletes all existing files in the session workspace.

Risk:

- User can lose prior agent changes by uploading again.
- No confirmation, version, or previous workspace snapshot.

Required fix:

- Add workspace versions or require explicit replace confirmation.
- Prefer creating a new workspace per upload.
- Provide `Replace workspace` and `Create new workspace` actions.

### 2.12 Direct File Mutation Prevents Codex-Like Review

Observed:

- Frontend save writes directly.
- Agent file tools write directly in web mode.
- No durable pending diff model.

Risk:

- Agent changes can be invisible.
- User cannot accept/reject per file.
- `Download ZIP` may include unintended changes.

Required fix:

- Add virtual patch system for agent changes.
- Manual editor saves can write directly but should create version entries.
- Agent writes should create pending patches first.

---

## 3. Feature Lag By Area

### 3.1 Workspace Feature Lag

Currently available:

- Upload folder.
- Tree view.
- Read file.
- Create file/folder.
- Save file.
- Rename.
- Delete.
- Download ZIP.

Lagging:

- No `Workspace` database model.
- No workspace list.
- No workspace status.
- No upload progress.
- No uploaded file count/size summary in UI.
- No skipped-file report.
- No workspace replace confirmation.
- No workspace versioning.
- No conflict handling.
- No binary file preview state.
- No file search in frontend.
- No changed files panel.
- No diff review.
- No accept/reject.
- No revert.
- No `download contains these changes` summary.

### 3.2 Agent Run Feature Lag

Currently available:

- Send message.
- WebSocket streaming tokens.
- Tool call events.
- Tool result events.
- Approval required event.
- Done/error events.

Lagging:

- No `AgentRun` model.
- No durable run status.
- No run cancellation in backend.
- No run replay after refresh.
- No run timeline.
- No event persistence.
- No per-run cost/token summary surfaced in web.
- No per-run changed files summary.
- No per-run logs.
- No run retry from failed state.

### 3.3 Diff Review Feature Lag

Currently available:

- Monaco editor for files.
- Dirty state for manual edits.
- Save/reset current file.

Lagging:

- No Monaco `DiffEditor`.
- No `WorkspacePatch` model.
- No pending patches.
- No accept/reject flow.
- No file-by-file review.
- No unified diff export.
- No `apply all` or `reject all`.
- No patch conflict detection.
- No rollback after accepted patch.

### 3.4 Terminal Feature Lag

Currently available:

- TUI can run local shell.
- Web shell is disabled.

Lagging:

- No web terminal.
- No Docker sandbox.
- No command jobs.
- No stdout/stderr streaming in frontend.
- No command history per workspace.
- No resource limits.
- No dependency install flow.
- No test/build command detection.

Recommended:

- MVP web should skip shell and focus on file edits plus download ZIP.
- Phase 2 should add Docker terminal jobs.

### 3.5 RAG / Search Feature Lag

Currently available:

- Upload individual docs for RAG.
- Chroma/vector store infrastructure.
- `codebase_search` tool.
- File upload indexing.

Lagging:

- Uploaded project folder is not clearly indexed as workspace context.
- Frontend does not show indexing status.
- Frontend does not show indexed files/chunks.
- Search capability is not visible to user.
- Agent failures due missing index are not surfaced well.
- No per-workspace vector namespace model.

### 3.6 Planner / Loop Recovery Feature Lag

Currently available:

- Plan mode.
- Planner node.
- Loop detector.
- Recovery node.

Lagging:

- Frontend does not show plan as a checklist.
- Current step is not surfaced.
- Recovery attempts are invisible or confusing.
- User cannot intervene in a stuck run.
- No clear `agent is retrying` state.

### 3.7 Safety / Approval Feature Lag

Currently available:

- Risky tool approval interrupt.
- Frontend approval card.
- TUI approval prompt.

Lagging:

- Approval action naming is inconsistent or fragile across surfaces.
- Approval state is not persisted as a first-class event.
- No audit trail of approved/denied actions.
- No per-run policy display.
- No explanation of risk levels.
- No approval settings UI.

### 3.8 TUI Feature Lag Relative To New Product Direction

Currently available:

- Rich local coding-agent REPL.
- Direct project access.
- Local shell.
- Slash commands.

Lagging:

- TUI and web do not share a unified run/event contract.
- TUI local changes and web copied-workspace changes are not represented similarly.
- TUI output has encoding issues.
- TUI approval actions must match backend.
- TUI should clearly be `local mode`, not the same as web mode.

---

## 4. UX Problems In Current Frontend

### 4.1 Product Mental Model Is Unclear

Current issue:

- UI says `Open Folder` and `Workspace` but does not clearly tell users that the browser uploads a copy.
- Users may expect the original local folder to change.

Required UX:

- Show persistent workspace banner:

```text
Editing a copy of your project. Download ZIP when finished.
```

- After upload, show:
  - workspace name
  - file count
  - size
  - last modified
  - download button

### 4.2 Chat Dominates, Work Is Hidden

Current issue:

- Agent actions are chat bubbles/tool snippets.
- No durable action timeline.

Required UX:

- Add run timeline:
  - planning
  - reading files
  - searching
  - proposing patch
  - waiting approval
  - completed
  - failed

### 4.3 File Explorer Controls Are Too Hidden

Current issue:

- Create/rename/delete icons mostly appear on hover.
- Root create exists but is small.

Required UX:

- Make `New File` and `New Folder` visible in header.
- Add context menu/right-click later.
- Add empty-folder create actions.
- Add confirm states for destructive actions.

### 4.4 Sandbox Is Not A Real Workspace IDE Yet

Current issue:

- Monaco editor is present, but no tabs, no split diff, no search, no changed files.

Required UX:

- Add tabs:
  - Files
  - Diffs
  - Logs
  - Terminal later
- Add open file tabs.
- Add changed files list.
- Add file search.

### 4.5 Approval UI Is Too Low-Context

Current issue:

- Approval card shows tool args, but not risk, file diff, or expected consequence.

Required UX:

- Approval card should show:
  - action type
  - affected file or command
  - risk label
  - exact args
  - resulting patch if applicable
  - approve once
  - always for this run
  - skip
  - deny

### 4.6 Errors Are Not Actionable

Current issue:

- Errors often show generic toast messages.

Required UX:

- Inline error panels with:
  - what failed
  - likely cause
  - retry action
  - fallback action
  - log details expandable

### 4.7 Mobile UX Is Incomplete

Current issue:

- Sandbox is hidden on smaller screens.

Required UX:

- Mobile bottom tabs:
  - Chat
  - Files
  - Diffs
  - Logs
- The user must be able to review and download on mobile.

---

## 5. Backend Capabilities Not Properly Accessed By Frontend

### 5.1 Tool Registry

Backend:

- `/tools` lists all tools.

Frontend gap:

- Settings shows a list, but does not distinguish usable web tools from TUI-only tools.
- No capability panel in the main workspace.

Implement:

- Return tool metadata:
  - name
  - description
  - environment: `web | tui | docker | disabled`
  - requires_approval
  - risk_level
- Add frontend capability panel.

### 5.2 Planner

Backend:

- Planner node creates a plan.

Frontend gap:

- Plan is not rendered as first-class checklist.

Implement:

- Emit `plan_created` and `plan_step_updated` events.
- Render plan checklist in run timeline.

### 5.3 Loop Recovery

Backend:

- Loop detector and recovery node exist.

Frontend gap:

- User cannot see retries or recovery guidance.

Implement:

- Emit `loop_detected`, `recovery_started`, `recovery_guidance`, `recovery_failed`.
- Show retry count and final fallback summary.

### 5.4 RAG

Backend:

- Uploaded files and codebase search exist.

Frontend gap:

- No visible indexing status for uploaded project folder.
- No user-facing semantic search panel.

Implement:

- Add workspace indexing job.
- Add `WorkspaceIndex` status fields or events.
- Show `Indexing project` progress.

### 5.5 Token/Cost Tracking

Backend/agent:

- Token usage tracking exists in agent/TUI.

Frontend gap:

- Cost/tokens are not visible in web run summary.

Implement:

- Persist token usage per `AgentRun`.
- Show tokens and cost in run details.

### 5.6 Worker Queue

Backend:

- Celery/Redis worker exists.

Frontend gap:

- UI has no queued/running state beyond `isLoading`.
- No task id/run id.

Implement:

- Start every message as an `AgentRun`.
- WebSocket subscribes to run events.
- UI shows queued/running/cancelled/failed/completed.

---

## 6. Target Architecture

### 6.1 New Core Models

Add `backend/models/workspace.py`:

```python
Workspace:
    id
    user_id
    session_id
    name
    storage_path
    source_type       # upload, github, template
    status            # empty, uploading, ready, indexing, error
    file_count
    size_bytes
    created_at
    updated_at
```

Add `backend/models/agent_run.py`:

```python
AgentRun:
    id
    user_id
    session_id
    workspace_id
    mode              # normal, plan
    prompt
    status            # queued, running, waiting_approval, completed, failed, cancelled
    final_response
    error
    token_usage
    started_at
    completed_at
    created_at
```

Add `backend/models/run_event.py`:

```python
RunEvent:
    id
    run_id
    type              # token, plan, tool_call, tool_result, patch_proposed, approval_required, done, error
    node
    payload
    created_at
```

Add `backend/models/workspace_patch.py`:

```python
WorkspacePatch:
    id
    run_id
    workspace_id
    file_path
    before_content
    after_content
    unified_diff
    status            # pending, accepted, rejected, applied, failed
    created_at
    updated_at
```

### 6.2 API Shape

Workspace:

```text
POST   /workspaces/upload
GET    /workspaces
GET    /workspaces/{workspace_id}
GET    /workspaces/{workspace_id}/tree
GET    /workspaces/{workspace_id}/file
PUT    /workspaces/{workspace_id}/file
POST   /workspaces/{workspace_id}/file
DELETE /workspaces/{workspace_id}/file
POST   /workspaces/{workspace_id}/rename
GET    /workspaces/{workspace_id}/download
```

Runs:

```text
POST   /runs
GET    /runs/{run_id}
GET    /runs/{run_id}/events
POST   /runs/{run_id}/cancel
WS     /runs/{run_id}/stream
```

Patches:

```text
GET    /runs/{run_id}/patches
POST   /patches/{patch_id}/accept
POST   /patches/{patch_id}/reject
POST   /runs/{run_id}/accept-all
POST   /runs/{run_id}/reject-all
```

### 6.3 Event Contract

Every streaming event should include:

```json
{
  "id": "event id",
  "run_id": "run id",
  "type": "token",
  "node": "executor",
  "payload": {},
  "created_at": "timestamp"
}
```

Required event types:

- `run_queued`
- `run_started`
- `token`
- `assistant_delta`
- `plan_created`
- `plan_step_started`
- `plan_step_completed`
- `tool_call`
- `tool_result`
- `approval_required`
- `approval_resolved`
- `patch_proposed`
- `patch_applied`
- `patch_rejected`
- `loop_detected`
- `recovery_started`
- `recovery_completed`
- `run_cancelled`
- `run_failed`
- `run_completed`

---

## 7. Implementation Phases

### Phase 0: Stabilization

Goal:

- Make the existing app consistently build, import, and start.

Tasks:

- Fix Tailwind/Vite native build failure.
- Add backend check script using `.venv`.
- Remove import-time Redis/cache network calls.
- Fix corrupted encoding in user-visible strings.
- Remove stale placeholder comments.
- Ensure frontend build, typecheck, and lint are separate scripts.

Acceptance criteria:

- `npx tsc -b` passes.
- `npm run build` passes in clean environment.
- Backend import check passes using venv.
- Startup logs are clean and structured.

### Phase 1: Workspace Model And Ownership

Goal:

- Replace implicit session folders with first-class workspaces.

Tasks:

- Add `Workspace` model and migration.
- Add workspace service layer.
- Refactor `backend/routers/workspaces.py`.
- Validate ownership on every workspace endpoint.
- Stop implicit workspace creation outside upload/create flows.
- Keep compatibility path for old session workspace endpoints temporarily.
- Remove web use of global `workspace_dir`.

Acceptance criteria:

- A user can upload a folder and gets a workspace record.
- Workspace belongs to exactly one user and session.
- Deleted sessions cannot access workspace endpoints.
- Download ZIP works from workspace id.

### Phase 2: Run/Event Persistence

Goal:

- Convert chat turns into durable agent runs.

Tasks:

- Add `AgentRun` model.
- Add `RunEvent` model.
- Create run service.
- Refactor `backend/routers/chat.py` or add `backend/routers/runs.py`.
- Persist every streamed event.
- Add event replay endpoint.
- Add cancellation endpoint.

Acceptance criteria:

- Refreshing browser can replay current/past run timeline.
- Every run has status.
- Errors are persisted.
- Cancellation updates run status.

### Phase 3: Virtual Patches And Diff Review

Goal:

- Agent changes should be reviewable before they affect downloadable workspace.

Tasks:

- Add `WorkspacePatch` model and migration.
- Add diff generation utility.
- Modify web-mode `write_to_file` and `edit_file` to create patches.
- Add accept/reject/apply endpoints.
- Add conflict detection if file changed after patch creation.
- Keep TUI direct-write behavior separate.

Acceptance criteria:

- Agent edit creates pending patch.
- Pending patch appears in frontend.
- Accept applies file.
- Reject leaves file unchanged.
- Download ZIP includes accepted patches only.

### Phase 4: Frontend Workspace Redesign

Goal:

- Make UI feel like a copied-workspace coding agent, not just chat.

Tasks:

- Add workspace state management.
- Build `WorkspacePanel`.
- Build `RunTimeline`.
- Build `ToolCallCard`.
- Build `ApprovalCard`.
- Build `DiffReviewPanel` with Monaco `DiffEditor`.
- Add visible `Download ZIP` flow.
- Add persistent copy-workspace banner.
- Add empty states for no workspace, upload progress, failed upload, no patches.

Acceptance criteria:

- User understands they are editing a copy.
- User can upload, inspect, ask agent, review changes, download ZIP.
- Tool calls and patches are visible and understandable.

### Phase 5: Backend Capability Surfacing

Goal:

- Expose existing backend powers correctly in frontend.

Tasks:

- Add environment-aware tool metadata.
- Add planner events.
- Add loop recovery events.
- Add token/cost run summary.
- Add workspace indexing status.
- Add web-safe/TUI-only labels.

Acceptance criteria:

- Frontend shows what the agent can and cannot do.
- Plan mode renders a checklist.
- Loop recovery is visible.
- Search/indexing status is visible.

### Phase 6: Web Terminal Later

Goal:

- Add command execution only after workspace/diff/run model is solid.

MVP:

- No web shell.
- File/search/RAG tools only.

Later:

- Add `TerminalJob` model.
- Run commands in Docker per workspace.
- Stream stdout/stderr as run events.
- Add CPU/memory/time limits.
- Require approval for risky commands.

Acceptance criteria:

- Web terminal cannot access host filesystem.
- Commands run only inside workspace copy.
- Output streams to frontend.
- Jobs can be cancelled.

### Phase 7: TUI Alignment

Goal:

- Keep TUI as the local-power version of Compass.

Tasks:

- Fix TUI encoding.
- Align approval actions.
- Align run/event vocabulary where practical.
- Preserve direct filesystem and shell access.
- Improve local diff/undo UX.
- Clearly label TUI as local mode.

Acceptance criteria:

- TUI remains powerful and local.
- Web remains safe and copied-workspace based.
- Users understand the difference.

---

## 8. Recommended UI Structure

Desktop layout:

```text
Left sidebar:
  Sessions
  Workspaces
  Upload/import controls

Center:
  Chat
  Streaming assistant response
  Run timeline

Right panel:
  Files
  Diffs
  Logs
  Terminal later
```

Mobile layout:

```text
Bottom tabs:
  Chat
  Files
  Diffs
  Logs
```

Primary user flow:

```text
1. Sign in
2. Upload project folder
3. See workspace summary
4. Ask Compass to implement feature/fix bug
5. Watch run timeline
6. Review pending diffs
7. Accept or reject changes
8. Download ZIP
```

---

## 9. Testing Plan

Backend unit tests:

- Workspace path traversal blocked.
- Workspace ownership enforced.
- Upload rejects oversized files.
- Tree endpoint hides ignored folders.
- File create/update/delete/rename works.
- Patch accept/reject works.
- Rejected patch does not change file.
- Accepted patch changes file.
- Download ZIP includes expected files.

Backend integration tests:

- Start run.
- Stream token event.
- Persist run events.
- Replay run events.
- Approval required/resume.
- Agent file write creates patch.

Frontend tests:

- Upload workspace.
- Show file tree.
- Open file.
- Create file.
- Save file.
- Show run timeline.
- Show diff review.
- Accept patch.
- Download ZIP button available after workspace ready.

End-to-end tests:

- Upload sample project.
- Ask agent to modify a file.
- Review patch.
- Accept patch.
- Download ZIP.
- Verify ZIP contains modified file.

CI gates:

- Frontend typecheck.
- Frontend build.
- Frontend lint.
- Backend import check with venv.
- Backend tests.
- Alembic migration check.

---

## 10. Work To Deprioritize

Do not focus on these until copied-workspace web agent is stable:

- Teams dashboard.
- Visual workflow builder.
- VS Code extension.
- Complex multi-agent team templates.
- Social media/research/data workflow templates.
- Web terminal before Docker isolation.
- Generic landing-page polish.

These may be valuable later, but they do not fix the core product gap.

---

## 11. Immediate Next Sprint

Sprint goal:

Make Compass a coherent uploaded-workspace coding agent MVP.

Tasks:

1. Fix frontend production build.
2. Clean import-time Redis/cache behavior.
3. Add `Workspace` model and ownership validation.
4. Refactor workspace upload/download around workspace id.
5. Remove web reliance on global `workspace_dir`.
6. Add `AgentRun` and `RunEvent`.
7. Persist WebSocket events.
8. Add run timeline UI.
9. Add copy-workspace banner and download ZIP UX.
10. Design `WorkspacePatch` schema and implement first pending patch flow.

Definition of done:

- User uploads project folder.
- Compass creates isolated workspace copy.
- User asks for a code change.
- Streaming response works.
- Tool/run timeline is visible.
- Agent-proposed file change appears as a diff.
- User accepts the diff.
- User downloads ZIP containing the accepted change.
