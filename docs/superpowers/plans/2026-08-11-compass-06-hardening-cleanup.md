# Compass Hardening, Cleanup, Documentation, and Release Gate Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make setup deterministic, readiness honest, remaining security boundaries explicit, configuration truthful, core interactions accessible, and the code/docs small enough for a student team—without deleting behavior that lacks a tested replacement.

**Architecture:** Use `pyproject.toml` plus generated lock exports as the Python dependency source, package-lock for frontend, separate liveness/readiness, small application-level security controls, request-scoped skill registries, and reachability tests before deletion. Generate architecture/workflow truth from current registered nodes and protocol values.

**Tech Stack:** Python 3.12, uv lock/export, pip frozen install, Docker Compose, FastAPI, SQLAlchemy/Alembic, React/Vitest/Testing Library, PowerShell/Python verification helpers, Mermaid documentation.

## Global Constraints

- Do not add distributed infrastructure or deployment orchestration.
- Liveness reports process health; readiness reports dependency state and may return 503.
- In cloud mode, default JWT/encryption secrets are startup errors.
- Web skills are per-user; local TUI skills remain global/workspace-scoped.
- Remove a source file, API, event, configuration key, dependency, or command only after a test/reachability check proves it has no live consumer or a replacement exists.
- Preserve all user-owned dirty worktree changes.
- Generated-cache cleanup uses an explicit allowlist and dry-run; never use broad `git clean` or recursive deletion of the workspace root.
- Documentation must distinguish working, partial, local-only, web-only, unavailable, and deferred features.

---

## File Structure

- Modify `pyproject.toml`, `requirements.txt`, `uv.lock`, Dockerfiles, environment examples, and bootstrap documentation.
- Create `requirements.lock` and `requirements-dev.lock` from the lock source.
- Create `backend/services/readiness.py` and lightweight auth/rate hardening.
- Refactor skills into request-scoped locations.
- Create `tools/verify.py`, `tools/clean_generated.py`, and `tools/render_workflow.py`.
- Update README, deployment guide, architecture, roadmap, workflow, and report generator.
- Remove only reachability-proven dead source and unused frontend dependencies.

### Task 1: Make Python setup reproducible and replace the broken environment

**Files:**
- Modify: `pyproject.toml`
- Modify: `requirements.txt`
- Create: `requirements.lock`
- Create: `requirements-dev.lock`
- Modify: `uv.lock`
- Modify: `.python-version`
- Modify: `backend.Dockerfile`
- Modify: `README.md`
- Create: `tools/bootstrap.ps1`
- Test: `tests/test_dependency_manifest.py`

**Interfaces:**
- `pyproject.toml` is the human-maintained dependency source.
- `uv.lock` is the resolver lock.
- `requirements.lock` and `requirements-dev.lock` are generated frozen install inputs for Docker/non-uv users.

- [ ] **Step 1: Write manifest consistency tests**

```python
class DependencyManifestTests(unittest.TestCase):
    def test_runtime_requirements_are_exactly_locked(self):
        unlocked = [line for line in Path("requirements.lock").read_text().splitlines()
                    if line and not line.startswith("#") and "==" not in line and " @ " not in line]
        self.assertEqual(unlocked, [])

    def test_docker_uses_frozen_lock(self):
        dockerfile = Path("backend.Dockerfile").read_text(encoding="utf-8")
        self.assertIn("requirements.lock", dockerfile)
        self.assertIn("--require-hashes", dockerfile)
```

- [ ] **Step 2: Recreate the environment safely**

Do not delete the broken `.venv` until its resolved absolute path is verified as `D:\projects\compass\.venv`. Verify `D:\projects\compass\.venv.pre-a-plus` does not exist, rename the old environment to that exact backup path for recoverability, run `uv venv --python 3.12 .venv`, then `uv sync --frozen --all-groups` after the manifests are complete. This filesystem action requires user approval at execution time.

- [ ] **Step 3: Populate and lock dependency groups**

Move current runtime dependencies into `[project.dependencies]`; add a `dev` group containing test/lint/type tools actually used by verification. Run:

```powershell
uv lock
uv export --frozen --no-dev --format requirements-txt --output-file requirements.lock
uv export --frozen --all-groups --format requirements-txt --output-file requirements-dev.lock
```

Configure export hashes and make Docker install `pip install --require-hashes -r requirements.lock`. Keep `requirements.txt` as a short compatibility pointer/document, not an unpinned second source.

- [ ] **Step 4: Add a safe bootstrap script**

`tools/bootstrap.ps1` verifies Python 3.12, `uv`, Node 20+, and npm; creates `.venv`; performs frozen sync; runs frontend `npm ci`; never modifies `.env`; prints exact missing prerequisites.

- [ ] **Step 5: Run tests and commit**

Run: `.\.venv\Scripts\python.exe -m unittest tests.test_dependency_manifest -v`  
Run: `.\.venv\Scripts\python.exe -m unittest discover -s tests -v`  
Expected: dependency tests and full Python suite PASS.

```bash
git add pyproject.toml requirements.txt requirements.lock requirements-dev.lock uv.lock .python-version backend.Dockerfile README.md tools/bootstrap.ps1 tests/test_dependency_manifest.py
git commit -m "build: make python setup reproducible"
```

### Task 2: Separate liveness/readiness and enforce safe cloud configuration

**Files:**
- Create: `backend/services/readiness.py`
- Modify: `backend/main.py`
- Modify: `backend/config.py`
- Modify: `backend/.env.example`
- Modify: `.env.example`
- Modify: `backend/auth/credentials.py`
- Test: `tests/backend/test_readiness.py`

**Interfaces:**
- `GET /health` returns process liveness only.
- `GET /ready` returns component statuses for SQL DB, checkpointer, workspace storage, memory store, and embedding capability; HTTP 503 when required components fail.
- Cloud mode requires non-default `JWT_SECRET`, separate `CREDENTIAL_ENCRYPTION_KEY`, and secure cookies.

- [ ] **Step 1: Write readiness/config tests**

```python
class ReadinessTests(unittest.TestCase):
    def test_db_failure_is_not_ready(self):
        report = build_readiness_report(services=failing_database_services())
        self.assertFalse(report.ready)
        self.assertEqual(report.components["database"].status, "failed")

    def test_missing_embedding_is_degraded_not_unready(self):
        report = build_readiness_report(services=no_embedding_services())
        self.assertTrue(report.ready)
        self.assertEqual(report.components["embeddings"].status, "unavailable")

    def test_cloud_rejects_default_secret(self):
        with self.assertRaisesRegex(ValueError, "JWT_SECRET"):
            Settings(COMPASS_CLOUD_MODE=True, JWT_SECRET="super-secret-default-key-please-change")
```

- [ ] **Step 2: Run and verify failures**

Run: `python -m unittest tests.backend.test_readiness -v`  
Expected: `/health` is always green and cloud defaults are accepted.

- [ ] **Step 3: Implement reports and startup validation**

Use 1-second bounded checks and cache readiness for 5 seconds. Required: DB/checkpointer/workspace root. Optional capability: memory semantic index, embeddings, MCP. `/health` remains constant and cheap. Redact DSNs and exception details from public output while logging sanitized component errors.

- [ ] **Step 4: Document every environment value**

Environment examples include DB URI, JWT secret, credential encryption key, secure cookie, CORS origins, cloud mode, workspace root, default provider/model, and optional embedding provider/model. Do not claim SQLite is the default unless verified by a test.

- [ ] **Step 5: Run tests and commit**

```bash
git add backend/services/readiness.py backend/main.py backend/config.py backend/.env.example .env.example backend/auth/credentials.py tests/backend/test_readiness.py
git commit -m "fix(ops): expose readiness and validate cloud secrets"
```

### Task 3: Add simple refresh revocation and WebSocket cost bounds

**Files:**
- Modify: `backend/models/user.py`
- Create: `backend/alembic/versions/81a004_refresh_version.py`
- Modify: `backend/auth/jwt.py`
- Modify: `backend/auth/oauth.py`
- Modify: `backend/routers/auth.py`
- Modify: `backend/middleware/rate_limit.py`
- Create: `backend/services/ws_limits.py`
- Modify: `backend/routers/chat.py`
- Modify: `backend/routers/sessions.py`
- Modify: `backend/services/run_manager.py`
- Modify: `backend/ws/hub.py`
- Modify: `backend/schemas/chat.py`
- Test: `tests/backend/test_auth_ws_limits.py`

**Interfaces:**
- Adds `User.refresh_version: int` default `0`.
- Migration revision is `81a004`; `down_revision` is `81a003` from Plan 2.
- Refresh JWT carries `rv`; refresh validates it against current user.
- Logout increments `refresh_version`; rotation increments then issues the next token.
- WebSocket limits: 5 concurrent connections per user, 64 KiB message content, 2 active runs per user, 10 run starts per minute.
- OAuth email identity is `strip().casefold()` and must be provider-verified; `(oauth_provider, oauth_provider_id)` is unique.
- HTTP rate-limit buckets prune expired/empty keys and assign higher weights to auth, upload/import, and chat-start endpoints.
- Soft-deleting a session cancels its active runs and disconnects its WebSockets before returning success; storage retention remains explicit in documentation.

- [ ] **Step 1: Write revocation and limit tests**

Issue a refresh token at version 0, logout, then assert refresh returns 401. Rotate one token and assert replaying the old token returns 401. Send 65 KiB content and assert WebSocket close code 1009. Open six connections and assert the sixth closes with a clear policy code. Start three simultaneous runs and assert the third is rejected without creating a model call. Soft-delete a session with one active run/socket and assert cancellation plus disconnect occur before the 204 response. Reject an OAuth profile with unverified email; assert mixed-case verified email resolves to one canonical account and a concurrent uniqueness conflict returns 409 rather than 500. Advance the HTTP limiter clock past its window and assert empty client keys are removed; assert an import consumes more quota than a health read.

- [ ] **Step 2: Run and verify failures**

Run: `python -m unittest tests.backend.test_auth_ws_limits -v`  
Expected: old refresh tokens remain valid and WebSocket limits are absent.

- [ ] **Step 3: Implement in-process bounded state**

Use one process-local limiter because the deployment remains single-process. Store per-user connection sets, active run IDs, and a deque of recent start timestamps; remove state on disconnect/terminal events. Session deletion resolves owned active run IDs, signals cancellation, asks the hub to close that session’s sockets, then marks the row deleted; document retained workspace/vector data and provide no false “physically deleted” claim. Prune HTTP limiter timestamps and delete empty keys during each access, with a small endpoint-weight table. Normalize email before lookup/storage, require Google `email_verified` or GitHub email `verified`, catch uniqueness races, and add the provider-identity unique constraint in revision `81a004`. Document multi-worker limitation rather than adding distributed state.

- [ ] **Step 4: Run tests and commit**

```bash
git add backend/models/user.py backend/alembic/versions/81a004_refresh_version.py backend/auth/jwt.py backend/auth/oauth.py backend/routers/auth.py backend/middleware/rate_limit.py backend/services/ws_limits.py backend/routers/chat.py backend/routers/sessions.py backend/services/run_manager.py backend/ws/hub.py backend/schemas/chat.py tests/backend/test_auth_ws_limits.py
git commit -m "fix(auth): revoke refresh tokens and bound websocket cost"
```

### Task 4: Namespace skills by user and sanitize every skill name/path

**Files:**
- Modify: `agent/skills/loader.py`
- Modify: `agent/skills/registry.py`
- Modify: `agent/tools/create_skill_tool.py`
- Modify: `backend/routers/skills.py`
- Modify: `backend/services/agent_runner.py`
- Test: `tests/backend/test_skill_isolation.py`

**Interfaces:**
- Produces `SkillScope(global_dir, workspace_dir, user_dir)`.
- Web user directory: configured skill root plus `users/{user_id}`.
- Skill names match `[a-z0-9][a-z0-9-]{0,63}` and resolve beneath the selected scope.
- Registries are request/run-scoped rather than one mutable singleton.

- [ ] **Step 1: Write isolation/path tests**

Create user A skill `review`, list as user B, and assert it is absent. Attempt names `../../escape`, `A B`, empty string, and 65 characters; assert 422/no file. Create a workspace skill and assert local TUI can see it while unrelated web users cannot.

- [ ] **Step 2: Run and verify failures**

Run: `python -m unittest tests.backend.test_skill_isolation -v`  
Expected: users share global skills and traversal names are accepted.

- [ ] **Step 3: Implement scoped discovery and mutation**

Global installed skills are read-only. TUI may read global plus current workspace; explicit create writes current workspace after approval. Web reads global plus its user directory; create/update/delete affects only its user directory. Return display source labels, never raw server paths.

- [ ] **Step 4: Run tests and commit**

```bash
git add agent/skills/loader.py agent/skills/registry.py agent/tools/create_skill_tool.py backend/routers/skills.py backend/services/agent_runner.py tests/backend/test_skill_isolation.py
git commit -m "fix(skills): isolate users and validate paths"
```

### Task 5: Make every configuration key and slash command truthful

**Files:**
- Modify: `agent/config.py`
- Modify: `agent/safety.py`
- Modify: `agent/ui/commands/registry.py`
- Modify: `agent/ui/commands/system.py`
- Modify: `agent/ui/commands/context.py`
- Test: `tests/test_config_coverage.py`

**Interfaces:**
- Produces `effective_settings_report()` mapping each public key to its consuming function and effective value.
- Public commands return one of `performed`, `waiting`, `unavailable`, `failed`; no generic success string without state evidence.

- [ ] **Step 1: Write configuration coverage test**

Maintain one table in the test containing every documented public key: theme, tool result limit, shell timeout, compaction threshold, loop limit, RAG auto-index/chunk size, HITL enabled/auto-safe, safety mode/blocked commands, orchestration enabled/max workers. For each key, assert a registered consumer exists and changing the value alters a focused behavior test.

- [ ] **Step 2: Run and identify no-op keys**

Run: `python -m unittest tests.test_config_coverage -v`  
Expected: test reports current no-op keys.

- [ ] **Step 3: Wire or retire each key**

Wire shell timeout into the tool, chunk size into indexer, compaction/loop limits into graph, auto-index into explicit post-import indexing, HITL enabled/auto-safe into policy, blocked commands into shell policy, and orchestration limits into coordinator. Theme remains a UI preference. Remove only keys whose intended behavior is explicitly unavailable and whose docs/UI are removed in the same commit.

Slash commands `/schedule` and unsupported background features remain registered but return `unavailable` with no mutation. `/grill-me` must either initiate a real clarification sequence using shared interrupts or be renamed in help to “enter Plan mode”; do not claim a grilling workflow if none occurs.

- [ ] **Step 4: Run tests and commit**

Run: `python -m unittest tests.test_config_coverage -v`  
Expected: every retained public key has behavior coverage and every command status is truthful.

```bash
git add agent/config.py agent/safety.py agent/ui/commands/registry.py agent/ui/commands/system.py agent/ui/commands/context.py tests/test_config_coverage.py
git commit -m "fix(config): wire settings and truthful command status"
```

### Task 6: Fix core accessibility and error propagation

**Files:**
- Modify: `frontend/src/components/layout/TopBar.tsx`
- Modify: `frontend/src/components/ui/sheet.tsx`
- Modify: `frontend/src/components/chat/ChatInput.tsx`
- Modify: `frontend/src/components/sandbox/FileExplorer.tsx`
- Modify: `frontend/src/components/sandbox/DiffReviewPanel.tsx`
- Modify: `frontend/src/components/layout/AppLayout.tsx`
- Modify: `frontend/src/components/layout/ProjectRail.tsx`
- Modify: `frontend/src/hooks/useSessions.ts`
- Modify: `frontend/src/App.tsx`
- Create: `frontend/src/components/accessibility.test.tsx`
- Create: `frontend/src/hooks/useSessions.test.ts`

**Interfaces:**
- Session mutations throw/reject on failure; callers close/navigate only after success.
- `useSessions` is instantiated once by `AppLayout` and passed to desktop/mobile rails, avoiding duplicate list requests.
- Icon-only controls have accessible names.
- Mention popup uses listbox/option keyboard behavior.
- File tree uses one roving tab stop and ArrowUp/ArrowDown/Home/End/ArrowLeft/ArrowRight.

- [ ] **Step 1: Write keyboard/name/error tests**

Use Testing Library roles to assert mobile menu, settings, attachment removal, context removal, diff actions, and retry have names. Navigate mentions with Down/Up/Enter/Escape. Navigate a three-node tree with required keys. Mock failed session delete and assert dialog stays open, error is shown, and navigation does not occur. Render desktop and mobile rails together and assert session listing is requested once.

- [ ] **Step 2: Run and verify failures**

Run: `cd frontend && npm test -- --run src/components/accessibility.test.tsx src/hooks/useSessions.test.ts`  
Expected: unnamed controls, incomplete keyboard behavior, and swallowed mutation failures.

- [ ] **Step 3: Implement minimal semantic behavior**

Add `aria-label`, sheet title, `aria-pressed`/radio semantics for modes, listbox/option roles, roving tree focus, and visible focus styles. Change hooks to report errors to callers rather than swallowing them. Lift the single `useSessions` result into `AppLayout` and pass it to both rail renderings. Add a catch-all route that renders a simple not-found action back to the app.

- [ ] **Step 4: Run tests and commit**

```bash
git add frontend/src/components/layout/TopBar.tsx frontend/src/components/ui/sheet.tsx frontend/src/components/chat/ChatInput.tsx frontend/src/components/sandbox/FileExplorer.tsx frontend/src/components/sandbox/DiffReviewPanel.tsx frontend/src/components/layout/AppLayout.tsx frontend/src/components/layout/ProjectRail.tsx frontend/src/hooks/useSessions.ts frontend/src/App.tsx frontend/src/components/accessibility.test.tsx frontend/src/hooks/useSessions.test.ts
git commit -m "fix(web): improve keyboard access and error handling"
```

### Task 7: Remove only reachability-proven dead code and generated clutter

**Files:**
- Create: `tests/test_reachability.py`
- Create: `tools/clean_generated.py`
- Delete after reachability approval: `agent/graph/remote_tool_node.py`
- Delete after reachability approval: `agent/ui/relay.py`
- Report only: unused event values, config fields, frontend UI modules, APIs, CSS, and dependencies identified by tests; add any extra deletion as an exact reviewed amendment before staging it.
- Modify: `.gitignore`

**Interfaces:**
- Produces a reachability allowlist for intentionally dynamic entry points.
- `tools/clean_generated.py --dry-run` prints only exact allowlisted generated paths.
- `--apply` requires `--workspace D:\projects\compass` and refuses any resolved path outside it.

- [ ] **Step 1: Write reachability assertions before deletion**

Assert active graph node names, runtime event emitters/consumers, TUI command handlers, backend router registrations, frontend imports/API call sites, and package dependencies. Keep an explicit allowlist for framework-discovered modules and generated UI primitives. Test that removed remote relay behavior has a replacement: TUI executes local tools directly and web executes allowed tools inside its owned server workspace.

- [ ] **Step 2: Run reachability tests and review the report**

Run: `python -m unittest tests.test_reachability -v`  
Expected: report lists dead candidates without deleting them. A reviewer approves the exact deletion list.

- [ ] **Step 3: Delete approved dead source and dependencies**

Delete the private-method remote node and relay only after their replacement tests pass and the reviewer approves both paths. Report unused event values with no producer/consumer, obsolete guardrail/eval cache references, frontend `card`/`separator` modules, dead CSS, and unused dependencies, but do not delete those additional candidates in this task until this plan is amended with their literal paths and replacement evidence. Do not delete empty user-owned directories without explicit approval.

- [ ] **Step 4: Add safe generated cleanup**

Allow only `__pycache__`, `*.pyc`, `.pytest_cache`, frontend `dist`, frontend `.vite`, and stale log files. Resolve every path, require it to be a descendant of the supplied workspace, and show dry-run totals. Never include `.git`, `.env`, `.compass`, source, uploads, workspaces, checkpoints, `node_modules`, or `.venv`.

- [ ] **Step 5: Run full tests and commit**

```bash
git add agent/graph/remote_tool_node.py agent/ui/relay.py tests/test_reachability.py tools/clean_generated.py .gitignore
git commit -m "refactor: remove reachability-proven dead surface"
```

### Task 8: Generate truthful workflow/docs and add one verification command

**Files:**
- Create: `tools/render_workflow.py`
- Create: `tools/verify.py`
- Modify: `README.md`
- Modify: `DEPLOYMENT.md`
- Modify: `docs/COMPASS_ARCHITECTURE.md`
- Modify: `langgraph_workflow.md`
- Modify: `roadmap.md`
- Modify: `tools/build_compass_report.py`
- Modify generated: `artifacts/compass_report_assets/architecture.png`
- Modify generated: `artifacts/compass_report_assets/workflow.png`
- Modify generated: `Compass_Product_and_Technical_Report.docx`
- Test: `tests/test_documentation_truth.py`

**Interfaces:**
- `python tools/verify.py --scope all` runs Python tests, frontend tests/typecheck/lint/build, Compose config, doc truth, and migration-head check with summarized exit codes.
- `render_workflow.py` emits Mermaid node/edge text from the registered builder description without model/network/DB/custom-tool execution.

- [ ] **Step 1: Write documentation truth tests**

Assert every README slash command is registered; every documented environment key exists in settings; every documented router prefix exists; every workflow node/edge matches the graph descriptor; docs do not claim NeMo guardrails, Chroma, Vite proxy paths, compaction, scheduler, MCP filenames, or refresh behavior inconsistent with code.

- [ ] **Step 2: Run and verify current failures**

Run: `python -m unittest tests.test_documentation_truth -v`  
Expected: stale workflow, roadmap, deployment, proxy, compaction, scheduler, and guardrail claims fail.

- [ ] **Step 3: Generate workflow and rewrite user docs**

README starts with working TUI/web paths, honest prerequisites, deliberate surface differences, BYOK/embedding disclosure, command status table, and exact troubleshooting. DEPLOYMENT uses HttpOnly refresh cookies and `/api` WebSocket proxy. Architecture describes one executor spine, explicit interrupts, active workspace, metrics, rules/hooks/checkpoints, and bounded read-only workers. Roadmap marks only tested behavior done and moves heavy deferred items into a clearly labeled section.

Update the report generator and regenerate report assets only after its claims pass the same truth tests.

- [ ] **Step 4: Implement verification orchestration**

Use `subprocess.run` with explicit argument arrays, workspace cwd, per-command timeout, and no shell. Print command, duration, exit code, and final failure summary. Scopes are `python`, `frontend`, `compose`, `docs`, and `all`.

- [ ] **Step 5: Run all verification and commit**

Run: `.\.venv\Scripts\python.exe tools\verify.py --scope all`  
Expected: every scope PASS.

```bash
git add tools/render_workflow.py tools/verify.py README.md DEPLOYMENT.md docs/COMPASS_ARCHITECTURE.md langgraph_workflow.md roadmap.md tools/build_compass_report.py tests/test_documentation_truth.py artifacts/compass_report_assets/architecture.png artifacts/compass_report_assets/workflow.png Compass_Product_and_Technical_Report.docx
git commit -m "docs: align product claims with verified behavior"
```

## Plan 6 Completion Gate

- [ ] Fresh bootstrap works from a clean copied checkout with frozen dependencies.
- [ ] Liveness/readiness behavior and cloud secret validation pass.
- [ ] Logout/rotation revokes refresh tokens and WebSocket bounds work in the documented single-process deployment.
- [ ] Web skills are isolated per user and every name/path is validated.
- [ ] Every retained public config key has a behavioral consumer test.
- [ ] Core accessibility and error-propagation tests pass.
- [ ] Every deletion is backed by reachability and replacement tests.
- [ ] Generated cleanup dry-run contains only allowlisted descendants.
- [ ] Workflow, README, deployment, architecture, roadmap, report, commands, environment, and router truth tests pass.
- [ ] `tools/verify.py --scope all` passes twice: once locally and once from a clean copied checkout.
- [ ] Perform the complete program-level TUI/web manual journey matrix.
- [ ] Invoke `superpowers:verification-before-completion`, then `superpowers:requesting-code-review`.
