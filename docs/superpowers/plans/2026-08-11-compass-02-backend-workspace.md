# Compass Backend, Workspace, and BYOK Integrity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Guarantee that every backend action targets an owned, explicitly active workspace; preserve stable project/GitHub identity through edits; shorten database critical sections; make run history truthful; and bind credentials to their intended providers.

**Architecture:** Add small ownership query helpers and an explicit `active_workspace_id` relationship on sessions. Capture a plain immutable run context in a short database scope before external awaits. Store provider credentials by provider name, pass an explicit embedding configuration, and use atomic patch writes with optimistic versions.

**Tech Stack:** FastAPI, Pydantic 2, SQLAlchemy 2 synchronous sessions used in short scopes, Alembic, PostgreSQL, `anyio.to_thread`, `httpx.Client`, Python `unittest` with temporary SQLite for service tests.

## Global Constraints

- Do not convert the project to async SQLAlchemy in this program.
- Never retain an ORM instance or open SQLAlchemy session across an LLM, embedding, upload, GitHub, or WebSocket wait.
- Every workspace operation validates `(workspace_id, user_id)`; every session-bound workspace creation validates `(session_id, user_id)`.
- `Workspace.project_id` is stable after creation. File changes update `context_version`, counts, size, and Git head only.
- A session has exactly one nullable `active_workspace_id`; no “latest row wins” fallback after migration.
- BYOK credentials are keyed by provider and are never reused for another provider.
- Keep web shell and command MCP disabled.

---

## File Structure

- Create `backend/services/ownership.py`: canonical owned-resource queries.
- Create `backend/services/run_context.py`: immutable context snapshot for agent turns.
- Create `backend/schemas/settings.py`: validated provider, model, and embedding preferences.
- Create `backend/services/provider_credentials.py`: provider-key encryption slots and test/remove operations.
- Create `tests/backend/support.py`: temporary SQLite `DatabaseTestCase` and named backend test factories used by this plan and Plan 4.
- Add Alembic revisions for `active_workspace_id`, patch `version`, and GitHub connection separation.
- Modify workspace, patch, run, chat, settings, GitHub, upload, memory, and session services/routers.
- Add backend-focused tests under `tests/backend/`.

### Task 1: Centralize ownership checks and reject workspace-root deletion

**Files:**
- Create: `backend/services/ownership.py`
- Modify: `backend/routers/workspaces.py`
- Modify: `backend/routers/uploads.py`
- Modify: `backend/routers/runs.py`
- Modify: `backend/routers/github.py`
- Create: `tests/backend/support.py`
- Test: `tests/backend/test_ownership.py`

**Interfaces:**
- Produces: `owned_session(db, session_id, user_id) -> ChatSession`.
- Produces: `owned_workspace(db, workspace_id, user_id) -> Workspace`.
- Produces: `owned_patch(db, workspace_id, patch_id, user_id) -> WorkspacePatch`.
- Produces: `safe_workspace_target(root, relative, allow_root=False) -> Path`.
- Produces test-only `DatabaseTestCase`, `workspace(status, project_id)`, `github_workspace()`, `add_messages(count)`, and `stub_workspace(file_count, size_bytes)` from `tests.backend.support`.

- [ ] **Step 1: Write failing relationship and root-path tests**

```python
import tempfile
import unittest
from pathlib import Path

from fastapi import HTTPException

from backend.services.ownership import safe_workspace_target


class WorkspaceBoundaryTests(unittest.TestCase):
    def test_root_target_is_rejected(self):
        with tempfile.TemporaryDirectory() as root:
            for value in ("", "."):
                with self.subTest(value=value), self.assertRaises(HTTPException) as error:
                    safe_workspace_target(Path(root), value)
                self.assertEqual(error.exception.status_code, 400)

    def test_child_target_is_allowed(self):
        with tempfile.TemporaryDirectory() as root:
            result = safe_workspace_target(Path(root), "src/app.py")
            self.assertEqual(result, (Path(root) / "src" / "app.py").resolve())
```

Add database fixtures with user A/session A/workspace A/patch A and user B/session B/workspace B. Assert cross-user session attachment and `workspace_b/patch_a` resolution both return 404.

Implement `DatabaseTestCase` with an in-memory SQLite engine using `StaticPool`, an engine-connect listener that runs `PRAGMA foreign_keys=ON`, `Base.metadata.create_all`, one SQLAlchemy session per test, and `tearDown()` that rolls back, closes, drops metadata, and disposes the engine. Its factory methods create and flush the minimum valid model rows; tests must import these names from `tests.backend.support` rather than relying on undeclared globals.

- [ ] **Step 2: Run and verify failure**

Run: `python -m unittest tests.backend.test_ownership -v`  
Expected: FAIL because `backend.services.ownership` does not exist.

- [ ] **Step 3: Implement canonical helpers**

```python
def safe_workspace_target(root: Path, relative: str, *, allow_root: bool = False) -> Path:
    if not relative.strip():
        raise HTTPException(status_code=400, detail="A file or folder path is required")
    target = (root / relative).resolve()
    base = root.resolve()
    if target != base and base not in target.parents:
        raise HTTPException(status_code=400, detail="Invalid workspace path")
    if target == base and not allow_root:
        raise HTTPException(status_code=400, detail="Workspace root cannot be targeted")
    return target
```

Each owned-resource helper performs one joined query that validates the complete relationship. Replace router-local ownership checks with these helpers, including workspace creation/upload, patch apply/reject/undo, run cancellation, uploads, and GitHub publish.

- [ ] **Step 4: Run tests and commit**

Run: `python -m unittest tests.backend.test_ownership -v`  
Expected: all ownership/boundary tests PASS.

```bash
git add backend/services/ownership.py backend/routers/workspaces.py backend/routers/uploads.py backend/routers/runs.py backend/routers/github.py tests/backend/support.py tests/backend/test_ownership.py
git commit -m "fix(backend): enforce resource ownership and root boundaries"
```

### Task 2: Add explicit active workspace and stable project identity

**Files:**
- Modify: `backend/models/session.py`
- Modify: `backend/models/workspace.py`
- Create: `backend/alembic/versions/81a001_active_workspace.py`
- Modify: `backend/services/workspace.py`
- Modify: `backend/routers/workspaces.py`
- Modify: `backend/schemas/session.py`
- Modify: `backend/services/session_manager.py`
- Modify: `backend/routers/sessions.py`
- Test: `tests/backend/test_active_workspace.py`

**Interfaces:**
- Adds: `ChatSession.active_workspace_id: str | None`.
- Migration revision is `81a001`; `down_revision` is the current head `7e1c9a4d2b60`.
- Produces: `attach_active_workspace(db, session_id, workspace_id, user_id) -> Workspace`.
- Changes: `get_workspace_by_session` resolves only `active_workspace_id` and rejects missing/not-ready workspaces.
- Changes: `update_workspace_stats` never changes `project_id`, `git_remote`, or `git_branch`.
- Session listing computes message count in a pre-aggregated subquery and labels only the active workspace, avoiding the current messages × workspaces multiplication.

- [ ] **Step 1: Write failing active-selection tests**

```python
class ActiveWorkspaceTests(DatabaseTestCase):
    def test_newest_failed_workspace_does_not_shadow_active_workspace(self):
        active = self.workspace(status="ready", project_id="project-stable")
        failed = self.workspace(status="failed", project_id="failed-project")
        self.session.active_workspace_id = active.id
        self.db.commit()
        selected = get_workspace_by_session(self.db, self.session.id, self.user.id)
        self.assertEqual(selected.id, active.id)
        self.assertNotEqual(selected.id, failed.id)

    def test_stats_refresh_preserves_github_binding(self):
        workspace = self.github_workspace()
        before = (workspace.project_id, workspace.git_remote, workspace.git_branch)
        update_workspace_stats(self.db, workspace)
        self.assertEqual((workspace.project_id, workspace.git_remote, workspace.git_branch), before)

    def test_session_count_is_not_multiplied_by_workspaces(self):
        active = self.workspace(status="ready", project_id="active")
        self.session.active_workspace_id = active.id
        self.add_messages(2)
        self.workspace(status="ready", project_id="second")
        self.db.commit()
        item = list_sessions(self.db, self.user.id)[0]
        self.assertEqual(item.message_count, 2)
        self.assertEqual(item.workspace_name, active.name)
```

- [ ] **Step 2: Run and verify failure**

Run: `python -m unittest tests.backend.test_active_workspace -v`  
Expected: FAIL because `active_workspace_id` and attach behavior do not exist.

- [ ] **Step 3: Add the migration and model relationship**

The migration adds nullable `chat_sessions.active_workspace_id`, a foreign key to `workspaces.id` with `SET NULL`, and an index. Backfill each session with its newest `status='ready'` workspace; leave it null when none exists.

```python
active_workspace_id: Mapped[str | None] = mapped_column(
    String(36), ForeignKey("workspaces.id", ondelete="SET NULL"), nullable=True, index=True
)
```

- [ ] **Step 4: Separate identity from mutable context**

At workspace creation, set `project_id` once to Git repository identity when known, otherwise `workspace:{workspace.id}`. Update `context_version` from Git HEAD plus dirty-tree metadata or the bounded content hash. For `source_type == "github"`, preserve imported remote/branch/head even though the extracted archive lacks `.git`. Rewrite session listing with separate message-count and active-workspace subqueries; do not join both one-to-many relationships into one aggregate.

Add `POST /api/workspaces/{workspace_id}/attach` that validates ownership of both session and workspace before setting `active_workspace_id`.

- [ ] **Step 5: Run tests and commit**

Run: `python -m unittest tests.backend.test_active_workspace -v`  
Expected: all active-workspace and stable-identity tests PASS.

```bash
git add backend/models/session.py backend/models/workspace.py backend/alembic/versions/81a001_active_workspace.py backend/services/workspace.py backend/routers/workspaces.py backend/schemas/session.py backend/services/session_manager.py backend/routers/sessions.py tests/backend/test_active_workspace.py
git commit -m "feat(workspace): add explicit active project identity"
```

### Task 3: Capture a plain run context and close DB sessions before external waits

**Files:**
- Create: `backend/services/run_context.py`
- Modify: `backend/auth/dependencies.py`
- Modify: `backend/routers/chat.py`
- Modify: `backend/services/agent_runner.py`
- Modify: `backend/routers/uploads.py`
- Test: `tests/backend/test_run_context.py`

**Interfaces:**
- Produces immutable `RunContextSnapshot` with user, session, workspace, project, context, preferences, and thread identifiers.
- Produces `load_run_context(session_id, user_id) -> RunContextSnapshot` using one short session.
- `run_agent_stream` consumes the snapshot rather than opening another DB session.

- [ ] **Step 1: Write the snapshot test**

```python
from dataclasses import FrozenInstanceError


class RunContextTests(DatabaseTestCase):
    def test_snapshot_contains_plain_values_and_is_immutable(self):
        snapshot = load_run_context(self.session.id, self.user.id)
        self.assertEqual(snapshot.workspace_id, self.workspace.id)
        self.assertEqual(snapshot.thread_id, self.session.thread_id)
        with self.assertRaises(FrozenInstanceError):
            snapshot.workspace_id = "other"
```

- [ ] **Step 2: Run and verify failure**

Run: `python -m unittest tests.backend.test_run_context -v`  
Expected: FAIL because `RunContextSnapshot` does not exist.

- [ ] **Step 3: Implement immutable context capture**

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class RunContextSnapshot:
    user_id: str
    session_id: str
    thread_id: str
    workspace_id: str
    workspace_path: str
    project_id: str
    context_version: str | None
    preferences: dict
```

Query owned session, active ready workspace, and user preferences in one `with SessionLocal() as db:` scope; copy JSON preferences before return.

- [ ] **Step 4: Shorten async critical sections**

In WebSocket chat, use separate short helper calls for `create_agent_run`, event batch persistence, terminal status, and transcript persistence. Do not retain `db_fallback` across `async for`. Make `get_current_user` synchronous so FastAPI threadpools the sync query. In uploads, perform file reading asynchronously, close the request DB transaction, then run parsing/indexing with `await anyio.to_thread.run_sync(index_uploaded_file, upload_id)`.

- [ ] **Step 5: Verify session lifetime**

Use a fake slow runner and a tracking `SessionLocal` to assert all sessions are closed before the runner’s first awaited yield. Assert upload indexing runs on a non-event-loop thread.

Run: `python -m unittest tests.backend.test_run_context -v`  
Expected: all tests PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/services/run_context.py backend/auth/dependencies.py backend/routers/chat.py backend/services/agent_runner.py backend/routers/uploads.py tests/backend/test_run_context.py
git commit -m "refactor(backend): release db sessions before agent waits"
```

### Task 4: Make streaming and non-streaming run lifecycle truthful

**Files:**
- Create: `backend/services/run_persistence.py`
- Modify: `backend/models/run.py`
- Modify: `backend/services/run_manager.py`
- Modify: `backend/routers/chat.py`
- Modify: `backend/routers/runs.py`
- Modify: `agent/runtime/runner.py`
- Test: `tests/backend/test_run_lifecycle.py`

**Interfaces:**
- Defines statuses `running`, `waiting_for_approval`, `completed`, `cancelled`, `failed`, `interrupted`.
- Produces `RunTerminal` from runtime terminal events.
- Produces `messages_created_this_turn(before_ids, after_messages)` for non-stream fallback.
- Accepts a client-generated UUID `run_id` on the first chat/resume frame, binds it to `(user_id, session_id)`, and rejects malformed, duplicate-active, or cross-session IDs before a model call.

- [ ] **Step 1: Write terminal-state tests**

```python
class RunLifecycleTests(unittest.TestCase):
    def test_error_is_failed_not_completed(self):
        terminal = terminal_from_events([StreamEvent(type=StreamEventType.ERROR, content="boom")])
        self.assertEqual(terminal.status, "failed")

    def test_approval_is_waiting(self):
        terminal = terminal_from_events([StreamEvent(type=StreamEventType.RUN_WAITING, data={"kind": "tool_approval"})])
        self.assertEqual(terminal.status, "waiting_for_approval")

    def test_nonstream_returns_only_new_messages(self):
        from langchain_core.messages import HumanMessage

        self.assertEqual(
            [m.id for m in messages_created_this_turn(
                {"old"},
                [HumanMessage(content="old", id="old"), HumanMessage(content="new", id="new")],
            )],
            ["new"],
        )
```

- [ ] **Step 2: Run and verify failure**

Run: `python -m unittest tests.backend.test_run_lifecycle -v`  
Expected: FAIL because terminal and delta helpers do not exist.

- [ ] **Step 3: Implement terminal capture and incremental persistence**

The runtime emits one terminal event containing `status` and aggregate usage. The backend reads that event rather than calling `workflow.aget_state()` again. Persist non-token events in bounded batches of 25 and flush immediately for waiting/error/done. Record the assistant transcript only from current-turn final assistant content, not concatenated text from every tool round.

Validate the client `run_id` with `uuid.UUID`, insert the owned run row before invoking the runner, and make the `(session_id, run_id)` association immutable. Resume/cancel frames must resolve that same owned row; a second active start using the ID returns a conflict without reaching the model.

- [ ] **Step 4: Paginate run history**

Add query parameters `cursor: str | None` and `limit: int = Field(default=25, ge=1, le=100)`. Use `selectinload(AgentRun.events)` and return `next_cursor`; reconcile stale `running` rows to `interrupted` during application startup.

- [ ] **Step 5: Run tests and commit**

Run: `python -m unittest tests.backend.test_run_lifecycle -v`  
Expected: all lifecycle, delta, batch, and pagination tests PASS.

```bash
git add backend/services/run_persistence.py backend/models/run.py backend/services/run_manager.py backend/routers/chat.py backend/routers/runs.py agent/runtime/runner.py tests/backend/test_run_lifecycle.py
git commit -m "fix(runs): persist truthful terminal state and turn deltas"
```

### Task 5: Bind credentials to providers and add test/remove actions

**Files:**
- Create: `backend/schemas/settings.py`
- Create: `backend/services/provider_credentials.py`
- Modify: `backend/routers/settings.py`
- Modify: `backend/services/agent_runner.py`
- Modify: `backend/services/session_manager.py`
- Modify: `agent/llm.py`
- Modify: `agent/tools/memory_tool.py`
- Modify: `agent/rag/vector_store.py`
- Modify: `frontend/src/api/preferences.ts`
- Test: `tests/backend/test_provider_credentials.py`

**Interfaces:**
- Preferences store encrypted credentials under `llm_credentials_encrypted: {provider: ciphertext}`.
- Produces `ResolvedProviderConfig(provider, model, api_key, embedding_provider, embedding_model, embedding_api_key)`.
- Adds `POST /api/settings/provider-test` and `DELETE /api/settings/credentials/{provider}`.
- Test helpers `encrypted_preferences(slots, selected)` and `decrypt_slots(preferences)` live in `tests/backend/test_provider_credentials.py` and call the same encrypt/decrypt primitives as the service.

- [ ] **Step 1: Write provider-isolation tests**

```python
class ProviderCredentialTests(unittest.TestCase):
    def test_openai_key_is_not_reused_for_openrouter(self):
        prefs = encrypted_preferences({"openai": "sk-openai"}, selected="openrouter")
        with self.assertRaisesRegex(ValueError, "No credential stored for openrouter"):
            resolve_provider_config(prefs)

    def test_delete_removes_only_selected_provider(self):
        prefs = encrypted_preferences({"openai": "a", "anthropic": "b"}, selected="openai")
        result = remove_provider_credential(prefs, "openai")
        self.assertNotIn("openai", decrypt_slots(result))
        self.assertEqual(decrypt_slots(result)["anthropic"], "b")
```

Above the test class, define `encrypted_preferences` to encrypt each supplied value into `llm_credentials_encrypted` and set `provider=selected`; define `decrypt_slots` to decrypt and return only that mapping. Do not hard-code ciphertext or compare encrypted bytes.

- [ ] **Step 2: Run and verify failure**

Run: `python -m unittest tests.backend.test_provider_credentials -v`  
Expected: FAIL because provider credential services do not exist.

- [ ] **Step 3: Implement provider slots and validation**

Validate providers against `{"openrouter", "openai", "anthropic", "google"}`. Unknown providers must return 422, never fall through to OpenRouter. Validate that the model prefix/provider pair is allowed. Provider-test performs one minimal model request with timeout 15 seconds and returns provider, model, success, latency, and sanitized error; it never stores the supplied test key unless the normal save endpoint is called.

Memory/RAG must receive `ResolvedProviderConfig`. If no explicit embedding credential exists, disable semantic embedding for that user and return a disclosed capability error; never use the operator key silently.

- [ ] **Step 4: Remove critical-path default-provider title generation**

Replace model-based auto-title with a deterministic title from the first non-empty user message: normalize whitespace, take at most eight words and 80 characters. This avoids blocking async chat and leaking the excerpt to a different provider.

- [ ] **Step 5: Run tests and commit**

Run: `python -m unittest tests.backend.test_provider_credentials -v`  
Expected: all provider isolation, delete, validation, and deterministic title tests PASS.

```bash
git add backend/schemas/settings.py backend/services/provider_credentials.py backend/routers/settings.py backend/services/agent_runner.py backend/services/session_manager.py agent/llm.py agent/tools/memory_tool.py agent/rag/vector_store.py frontend/src/api/preferences.ts tests/backend/test_provider_credentials.py
git commit -m "fix(byok): isolate provider credentials and embeddings"
```

### Task 6: Repair memory/RAG scope and exclude secret-like files

**Files:**
- Modify: `agent/tools/memory_tool.py`
- Modify: `agent/rag/indexer.py`
- Modify: `agent/rag/retriever.py`
- Modify: `agent/rag/loaders.py`
- Modify: `agent/ui/tui.py`
- Test: `tests/test_memory_rag_scope.py`

**Interfaces:**
- Produces one canonical memory namespace `(user_id, scope, project_id, category)`.
- `index_workspace` requires `project_id` and `context_version` keyword arguments.
- Produces `should_index_path(path) -> bool` with explicit secret/config deny rules.

- [ ] **Step 1: Write scope and secret tests**

```python
class MemoryRagScopeTests(unittest.TestCase):
    def test_categorized_save_can_be_found_in_same_category(self):
        namespace = memory_namespace("u1", "project", "p1", "preference")
        self.assertEqual(namespace, ("memories", "u1", "project", "p1", "preference"))

    def test_secret_like_files_are_not_indexed(self):
        for path in (".env", "secrets.env", "config/credentials.json", ".git/config", "id_rsa"):
            with self.subTest(path=path):
                self.assertFalse(should_index_path(Path(path)))

    def test_normal_source_is_indexed(self):
        self.assertTrue(should_index_path(Path("src/app.py")))
```

- [ ] **Step 2: Run and verify failure**

Run: `python -m unittest tests.test_memory_rag_scope -v`  
Expected: FAIL for inconsistent namespaces and missing deny policy.

- [ ] **Step 3: Implement one namespace and one index identity**

Use `memory_namespace` for save/get/search/list/delete. Change TUI `/index` to pass the active `project_id` and `context_version`. Reject missing identity instead of writing blank metadata. Retrieval uses exactly the same fields.

Secret rules reject exact dotfiles and basename patterns for credentials, tokens, private keys, `.git`, `.compass/checkpoints`, build output, and dependency caches. Notebook loading is either made reachable through `TEXT_EXTENSIONS` with JSON extraction or removed from the advertised list in Plan 6; choose implementation here only if the loader test covers it.

- [ ] **Step 4: Run tests and commit**

Run: `python -m unittest tests.test_memory_rag_scope -v`  
Expected: all scope/filter/index identity tests PASS.

```bash
git add agent/tools/memory_tool.py agent/rag/indexer.py agent/rag/retriever.py agent/rag/loaders.py agent/ui/tui.py tests/test_memory_rag_scope.py
git commit -m "fix(context): align memory rag identity and secret policy"
```

### Task 7: Make patch application atomic and emit patch-created events

**Files:**
- Modify: `backend/models/patch.py`
- Create: `backend/alembic/versions/81a002_patch_version.py`
- Modify: `backend/services/patch_manager.py`
- Modify: `backend/routers/workspaces.py`
- Modify: `agent/tools/file_tools.py`
- Test: `tests/backend/test_patch_atomicity.py`

**Interfaces:**
- Adds `WorkspacePatch.version: int` default `1`.
- Migration revision is `81a002`; `down_revision` is `81a001`.
- Produces `stage_patch_files`, `commit_staged_files`, and `discard_staged_files`.
- Patch mutation requires `expected_version` and returns 409 on conflict.
- Patch creation emits `WORKSPACE_PATCH` with patch/workspace/session IDs.

- [ ] **Step 1: Write failure and concurrency tests**

Create a two-file patch. Inject a write failure for the second target and assert neither target changes and patch remains pending. Simulate two clients both using `expected_version=1`; assert the first succeeds and the second receives 409 rather than overwriting JSON status.

- [ ] **Step 2: Run and verify failure**

Run: `python -m unittest tests.backend.test_patch_atomicity -v`  
Expected: current implementation leaves the first file modified and permits the lost update.

- [ ] **Step 3: Implement staged atomic replacement**

For each target, validate current content, write proposed bytes to a temporary sibling, and fsync/close it. Only after every stage succeeds, use `os.replace` for each target. On any stage failure, delete all temporary files. Record enough before-content to compensate if an `os.replace` fails mid-commit, then restore already-replaced targets before returning an error.

Update the patch row with `WHERE id=:id AND version=:expected_version`, incrementing version. Emit the creation event immediately after the patch record commits, not only after apply/reject/undo.

- [ ] **Step 4: Run tests and commit**

Run: `python -m unittest tests.backend.test_patch_atomicity -v`  
Expected: atomicity, conflict, ownership, and creation-event tests PASS.

```bash
git add backend/models/patch.py backend/alembic/versions/81a002_patch_version.py backend/services/patch_manager.py backend/routers/workspaces.py agent/tools/file_tools.py tests/backend/test_patch_atomicity.py
git commit -m "fix(patches): apply atomically with optimistic versions"
```

### Task 8: Bound GitHub/upload ingestion and separate GitHub integration identity

**Files:**
- Create: `backend/models/github_connection.py`
- Create: `backend/alembic/versions/81a003_github_connections.py`
- Modify: `backend/models/user.py`
- Modify: `backend/models/__init__.py`
- Modify: `backend/auth/jwt.py`
- Modify: `backend/auth/oauth.py`
- Modify: `backend/routers/auth.py`
- Modify: `backend/routers/github.py`
- Modify: `backend/services/github.py`
- Modify: `backend/routers/workspaces.py`
- Create: `backend/schemas/workspace.py`
- Test: `tests/backend/test_github_ingestion.py`

**Interfaces:**
- Adds one `GitHubConnection` per user with encrypted token, provider user ID, scopes, and timestamps.
- Migration revision is `81a003`; `down_revision` is `81a002`.
- OAuth connect state includes authenticated `user_id`, intent, nonce, and expiry.
- Archive limits: 50 MiB compressed, 250 MiB expanded, 20,000 members, 2,000 imported files, 100 MiB aggregate upload.
- One reusable `httpx.Client` per GitHub operation.
- Public workspace responses exclude `storage_path`; tree/export endpoints enforce the same 2,000-file/100 MiB workspace bounds and stream archives from a temporary file instead of building them fully in memory.

- [ ] **Step 1: Write state-binding and archive-limit tests**

Assert user B cannot complete user A’s signed `connect_github` state. Build an in-memory ZIP whose declared expanded size exceeds 250 MiB and assert rejection occurs before extraction. Upload 2,001 tiny files and assert 413. Assert Google login fields remain unchanged after connecting GitHub. Serialize create/import/tree responses and assert the absolute `storage_path` never appears. Build a legacy oversized tree and assert bounded tree/export failure rather than recursive materialization.

- [ ] **Step 2: Run and verify failures**

Run: `python -m unittest tests.backend.test_github_ingestion -v`  
Expected: state is not user-bound, identity fields are overwritten, and aggregate/member limits are absent.

- [ ] **Step 3: Add the connection model and migrate existing GitHub integrations**

Move repository token/scopes/provider user ID out of general login identity fields. Backfill rows whose `oauth_provider == 'github'` and token exists. Keep password/Google/GitHub login identity behavior intact while repository integration reads only `GitHubConnection`.

- [ ] **Step 4: Add simple limits and connection reuse**

Inspect ZIP metadata before extraction; reject absolute/traversal/symlink members. Stream upload contents while incrementing file count and aggregate bytes. Use `with httpx.Client(base_url="https://api.github.com", timeout=30.0) as client:` for the complete GitHub operation, including commit blob calls. Return explicit Pydantic workspace response models containing public IDs/metadata only. Walk tree/export with counters and a depth limit, reject legacy workspaces outside the cap with a clear error, and stream a temporary archive after safe creation/cleanup.

- [ ] **Step 5: Run tests and commit**

Run: `python -m unittest tests.backend.test_github_ingestion -v`  
Expected: all identity, CSRF, limit, path, and reuse tests PASS.

```bash
git add backend/models/github_connection.py backend/alembic/versions/81a003_github_connections.py backend/models/user.py backend/models/__init__.py backend/auth/jwt.py backend/auth/oauth.py backend/routers/auth.py backend/routers/github.py backend/services/github.py backend/routers/workspaces.py backend/schemas/workspace.py tests/backend/test_github_ingestion.py
git commit -m "fix(github): isolate integration identity and bound imports"
```

## Plan 2 Completion Gate

- [ ] Run all `tests/backend` and existing tests with zero failures.
- [ ] Apply Alembic upgrade from a copy of the pre-plan database and verify downgrade/upgrade round-trip.
- [ ] Confirm every router that accepts `session_id`, `workspace_id`, `patch_id`, or `run_id` calls a canonical ownership helper.
- [ ] Confirm a GitHub-imported project remains publishable after create/edit/delete/patch operations.
- [ ] Confirm no database session remains open during a fake 2-second LLM or GitHub wait.
- [ ] Confirm provider A’s key is never presented to provider B in logs/mocks.
- [ ] Request code review before Plan 4.
