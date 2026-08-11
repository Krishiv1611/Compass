# Compass Rules, Checkpoints, Hooks, and Bounded Multi-Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add the lightweight workflow features that make Compass feel like Claude Code, Antigravity, and Codex: persistent project rules, deterministic verification hooks, recoverable checkpoints/forks, structured plans, bounded parallel workers, evidence synthesis, and a final walkthrough in TUI and web.

**Architecture:** The existing planner becomes a coordinator-facing plan producer. A small scheduler runs ready independent tasks with `asyncio` and a semaphore; workers use the existing skill/subagent foundation but receive read-only tools, cannot nest, and return typed artifacts. The coordinator/main executor alone requests or applies writes. Rules, hooks, checkpoints, tasks, and artifacts are plain files/Pydantic models rather than new services.

**Tech Stack:** Python 3.12, Pydantic 2, LangGraph, `asyncio`, standard-library TOML/JSON/gzip/shutil, existing tool registry, FastAPI/WebSocket, React/TypeScript artifact UI.

## Global Constraints

- Default worker concurrency is `2`; configuration may choose `1` through `4`.
- Nested delegation is always disabled in this release.
- Workers receive only registry tools with `worker_allowed=True` and `mutates_workspace=False`.
- Workers never apply patches, edit files, create skills, invoke shell, or approve their own actions.
- The main executor/coordinator is the only write authority and uses the normal approval/checkpoint path.
- Workers must return structured evidence or an explicit failure; free-form success without evidence is invalid.
- Hooks are user-configured deterministic commands, not model-generated background jobs.
- No scheduler daemon, queue, Redis, Celery, browser automation, agent-team chat room, or VS Code work.
- Rule files are treated as instructions, not executable code.

---

## File Structure

- Create `agent/instructions.py`: deterministic rule discovery, precedence, and rendering.
- Create `agent/hooks.py`: TOML hook parsing and approved execution requests.
- Create `agent/checkpoints.py`: file checkpoint manifests, restore, and fork helpers.
- Create `agent/orchestration/models.py`: plan/task/artifact types.
- Create `agent/orchestration/planner.py`: validated structured task planning.
- Create `agent/orchestration/coordinator.py`: dependency scheduler, cancellation, and limits.
- Create `agent/orchestration/worker.py`: read-only worker adapter around skills/subagents.
- Create `agent/orchestration/synthesis.py`: evidence merge and executor handoff.
- Modify graph/runtime/backend/TUI/web to emit and render worker/artifact events.
- Add deterministic tests under `tests/orchestration/` and frontend worker timeline tests.

### Task 1: Load persistent project instructions and make `/init` and `/learn` real

**Files:**
- Create: `agent/instructions.py`
- Modify: `agent/graph/nodes.py`
- Modify: `agent/runtime/turn_context.py`
- Modify: `agent/ui/commands/context.py`
- Modify: `frontend/src/components/workbench/ContextDrawer.tsx`
- Test: `tests/test_project_instructions.py`

**Interfaces:**
- Produces `InstructionSource(path, precedence, content, digest)`.
- Produces `load_project_instructions(workspace_root) -> list[InstructionSource]`.
- Produces `render_project_instructions(sources, max_chars=20_000) -> str`.
- Precedence from lowest to highest: global `~/.compass/COMPASS.md`, workspace `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, workspace `COMPASS.md`.

- [ ] **Step 1: Write precedence and safety tests**

```python
class ProjectInstructionTests(unittest.TestCase):
    def test_workspace_compass_has_highest_precedence(self):
        rules = {
            "AGENTS.md": "style=agents",
            "CLAUDE.md": "style=claude",
            "GEMINI.md": "style=gemini",
            "COMPASS.md": "style=compass",
        }
        for name, content in rules.items():
            (self.root / name).write_text(content, encoding="utf-8")
        sources = load_project_instructions(self.root)
        self.assertEqual([source.path.name for source in sources], [
            "AGENTS.md", "CLAUDE.md", "GEMINI.md", "COMPASS.md",
        ])
        self.assertTrue(render_project_instructions(sources).rstrip().endswith("style=compass"))

    def test_init_never_overwrites_without_force(self):
        target = self.root / "COMPASS.md"
        target.write_text("keep me", encoding="utf-8")
        with self.assertRaises(FileExistsError):
            initialize_compass_file(self.root, force=False)
        self.assertEqual(target.read_text(encoding="utf-8"), "keep me")
```

- [ ] **Step 2: Run and verify failure**

Run: `python -m unittest tests.test_project_instructions -v`  
Expected: instruction module does not exist and current `/init` overwrites.

- [ ] **Step 3: Implement deterministic loading and limits**

Read UTF-8 text only, normalize newlines, compute SHA-256 digest, and cap combined content at 20,000 characters by retaining higher-precedence sources first. Do not scan nested folders in this release. Cache by source path, mtime, size, and digest for one turn.

Inject rendered rules once in TurnContext, not as a new persistent conversation message every executor cycle. ContextDrawer lists path, precedence, digest prefix, and included/truncated status.

- [ ] **Step 4: Implement `/init` and `/learn`**

`/init` writes a non-destructive template only when absent. `--force` requires normal write approval. `/learn <text>` displays the exact proposed addition and requires approval, then appends one bullet under `## Learned instructions` in workspace `COMPASS.md`; it records a checkpoint first. Empty input returns usage and performs no write.

- [ ] **Step 5: Run tests and commit**

Run: `python -m unittest tests.test_project_instructions -v`  
Expected: precedence, truncation, no-overwrite, approval, and append tests PASS.

```bash
git add agent/instructions.py agent/graph/nodes.py agent/runtime/turn_context.py agent/ui/commands/context.py frontend/src/components/workbench/ContextDrawer.tsx tests/test_project_instructions.py
git commit -m "feat(context): load persistent project instructions"
```

### Task 2: Add deterministic post-edit verification hooks

**Files:**
- Create: `agent/hooks.py`
- Modify: `agent/config.py`
- Modify: `agent/graph/nodes.py`
- Modify: `agent/runtime/artifacts.py`
- Modify: `agent/ui/commands/system.py`
- Modify: `frontend/src/components/chat/RunTimeline.tsx`
- Test: `tests/test_verification_hooks.py`

**Interfaces:**
- Defines `VerificationHook(name, command, cwd, timeout_seconds, run_on)`.
- Reads `[[hooks.after_edit]]` entries from `.compass/config.toml`.
- Produces approved `HookRunRequest`; actual execution uses existing `shell_execute` policy.

- [ ] **Step 1: Write parser and approval tests**

Use this exact configuration fixture:

```toml
[[hooks.after_edit]]
name = "python tests"
command = "python -m unittest discover -s tests -v"
cwd = "."
timeout_seconds = 120
run_on = ["py"]

[[hooks.after_edit]]
name = "frontend lint"
command = "npm run lint"
cwd = "frontend"
timeout_seconds = 180
run_on = ["ts", "tsx"]
```

Assert only matching hooks are selected, timeout is clamped to 600 seconds, traversal cwd is rejected, and hook selection creates approval requests rather than executing subprocesses directly.

- [ ] **Step 2: Run and verify failure**

Run: `python -m unittest tests.test_verification_hooks -v`  
Expected: hook module does not exist.

- [ ] **Step 3: Implement selection and graph handoff**

After the main executor finishes with changed files, select matching hooks once, place them in `pending_tool_calls` as `shell_execute` calls, and route through normal approval/tools. Capture command, exit code, duration, and truncated/redacted output in RunArtifact checks. A denied hook is `skipped`, not `passed`.

- [ ] **Step 4: Add `/hooks` inspection**

`/hooks` lists parsed names, commands, cwd, timeout, run_on, and validation errors. It never executes them. Web Timeline shows pending/running/passed/failed/skipped checks from shared events.

- [ ] **Step 5: Run tests and commit**

```bash
git add agent/hooks.py agent/config.py agent/graph/nodes.py agent/runtime/artifacts.py agent/ui/commands/system.py frontend/src/components/chat/RunTimeline.tsx tests/test_verification_hooks.py
git commit -m "feat(workflow): run approved post-edit verification hooks"
```

### Task 3: Persist recoverable file checkpoints and restore created/deleted files

**Files:**
- Create: `agent/checkpoints.py`
- Modify: `agent/tools/change_tracker.py`
- Modify: `agent/tools/file_tools.py`
- Modify: `backend/services/patch_manager.py`
- Modify: `agent/ui/commands/session.py`
- Create: `backend/routers/checkpoints.py`
- Modify: `backend/main.py`
- Test: `tests/test_file_checkpoints.py`

**Interfaces:**
- Defines `CheckpointManifest(id, workspace_id, thread_id, created_at, label, files)`.
- Defines each file entry as `path`, `existed`, `sha256`, `size`, and compressed content path.
- Produces `create_checkpoint`, `list_checkpoints`, `preview_restore`, and `restore_checkpoint`.

- [ ] **Step 1: Write create/edit/delete restore tests**

```python
class FileCheckpointTests(unittest.TestCase):
    def test_restore_removes_file_created_after_checkpoint(self):
        checkpoint = create_checkpoint(self.root, ["new.py"], workspace_id="w", thread_id="t")
        (self.root / "new.py").write_text("created", encoding="utf-8")
        restore_checkpoint(self.root, checkpoint.id)
        self.assertFalse((self.root / "new.py").exists())

    def test_restore_recreates_deleted_file(self):
        target = self.root / "old.py"
        target.write_text("before", encoding="utf-8")
        checkpoint = create_checkpoint(self.root, ["old.py"], workspace_id="w", thread_id="t")
        target.unlink()
        restore_checkpoint(self.root, checkpoint.id)
        self.assertEqual(target.read_text(encoding="utf-8"), "before")
```

- [ ] **Step 2: Run and verify failure**

Run: `python -m unittest tests.test_file_checkpoints -v`  
Expected: checkpoint module does not exist and current undo leaves created files empty.

- [ ] **Step 3: Implement manifests and atomic restore**

Store checkpoints below `.compass/checkpoints/{checkpoint_id}/manifest.json` and gzip-compressed file bodies. Resolve every path through workspace boundaries. Stage restore bodies to temporary siblings and atomically replace after all validation. For `existed=false`, restore deletes the current path. Check current hashes and return conflicts unless `force=True`; force requires explicit approval.

Create one checkpoint immediately before each approved main-executor write batch and patch apply/undo, not one per streamed token/tool event.

- [ ] **Step 4: Add TUI and web endpoints**

TUI `/checkpoints`, `/restore <id>`, and `/undo` use the same service. Web endpoints list, preview, and restore owned workspace checkpoints. Restore emits changed-file and checkpoint-restored events and refreshes editor/tree state.

- [ ] **Step 5: Run tests and commit**

```bash
git add agent/checkpoints.py agent/tools/change_tracker.py agent/tools/file_tools.py backend/services/patch_manager.py agent/ui/commands/session.py backend/routers/checkpoints.py backend/main.py tests/test_file_checkpoints.py
git commit -m "feat(checkpoints): restore files across create edit and delete"
```

### Task 4: Add session fork using checkpoint state and an isolated workspace copy

**Files:**
- Create: `backend/services/session_fork.py`
- Modify: `backend/routers/sessions.py`
- Modify: `backend/schemas/session.py`
- Modify: `agent/ui/commands/session.py`
- Modify: `agent/sessions.py`
- Modify: `frontend/src/api/projects.ts`
- Modify: `frontend/src/components/layout/ProjectRail.tsx`
- Test: `tests/backend/test_session_fork.py`

**Interfaces:**
- Produces `fork_session(source_session_id, user_id, checkpoint_id=None) -> ChatSession`.
- Web fork clones active workspace files and metadata into a new workspace owned by the new session.
- TUI fork creates a new thread ID in the same local workspace and records shared-workspace status explicitly.

- [ ] **Step 1: Write fork isolation tests**

Create a source session/workspace/checkpoint, fork it, modify a file in the fork, and assert source content remains unchanged. Assert messages/checkpoint state exist through the selected source checkpoint and later messages do not. Assert another user cannot fork the session.

- [ ] **Step 2: Run and verify failure**

Run: `python -m unittest tests.backend.test_session_fork -v`  
Expected: fork service/endpoint does not exist.

- [ ] **Step 3: Implement bounded workspace clone and state copy**

Clone only tracked workspace content, excluding `.git`, `.compass/checkpoints`, dependency caches, build output, and files rejected by secret/storage policy. Enforce the same 2,000-file/100 MiB copied limit. Create new session/thread/workspace in `preparing`, copy, then mark `ready` and active in one final transaction. On failure, delete partial directory/rows.

Copy graph state by reading the source snapshot and calling `workflow.aupdate_state` on the new thread with messages, summary, plan, and approved non-secret state; clear pending calls, approvals, run IDs, and loop counters.

- [ ] **Step 4: Add surface actions and commit**

ProjectRail “Fork task” creates and navigates to the new session. TUI `/fork` prints the new thread and that it shares the current working directory. Both add a checkpoint/fork event to the artifact.

```bash
git add backend/services/session_fork.py backend/routers/sessions.py backend/schemas/session.py agent/ui/commands/session.py agent/sessions.py frontend/src/api/projects.ts frontend/src/components/layout/ProjectRail.tsx tests/backend/test_session_fork.py
git commit -m "feat(sessions): fork task state and workspace"
```

### Task 5: Define validated execution plans, tasks, and worker artifacts

**Files:**
- Create: `agent/orchestration/__init__.py`
- Create: `agent/orchestration/models.py`
- Create: `agent/orchestration/validation.py`
- Test: `tests/orchestration/__init__.py`
- Test: `tests/orchestration/factories.py`
- Test: `tests/orchestration/test_models.py`

**Interfaces:**
- Produces `AgentTask`, `ExecutionPlan`, `AgentEvidence`, `AgentArtifact`, and status enums.
- Task fields: `id`, `title`, `objective`, `kind`, `depends_on`, `allowed_tools`, `success_criteria`, `timeout_seconds`, `token_budget`.
- Worker kinds: `analysis`, `research`, `verification`, `implementation_proposal`; every kind is read-only.
- Test factory `make_task(task_id, **overrides) -> AgentTask` supplies a valid title, objective, read-only tools, one success criterion, and deterministic limits before applying overrides.

- [ ] **Step 1: Write validation tests**

```python
from tests.orchestration.factories import make_task


class OrchestrationModelTests(unittest.TestCase):
    def test_cycle_is_rejected(self):
        plan = ExecutionPlan(tasks=[make_task("a", depends_on=["b"]), make_task("b", depends_on=["a"])])
        with self.assertRaisesRegex(ValueError, "cycle"):
            validate_execution_plan(plan, available_tools={"read_file"})

    def test_mutating_worker_tool_is_rejected(self):
        plan = ExecutionPlan(tasks=[make_task("a", allowed_tools=["edit_file"])])
        with self.assertRaisesRegex(ValueError, "not worker-allowed"):
            validate_execution_plan(plan, available_tools={"read_file"})

    def test_limits_are_clamped(self):
        item = make_task("a", timeout_seconds=5000, token_budget=999999)
        self.assertEqual((item.timeout_seconds, item.token_budget), (600, 50000))
```

- [ ] **Step 2: Run and verify failure**

Run: `python -m unittest tests.orchestration.test_models -v`  
Expected: orchestration package does not exist.

- [ ] **Step 3: Implement strict models**

Use Pydantic `extra="forbid"`; IDs match `[a-z0-9][a-z0-9_-]{0,39}`. Defaults are timeout 300 seconds and token budget 20,000; maximums are 600 and 50,000. Success criteria require one to five non-empty strings. Evidence types are `file`, `command`, `url`, `test`, and `finding`, each containing a locator and concise claim.

Artifacts contain task ID, status, summary, evidence, files_considered, proposed_changes, checks, usage, started/ended timestamps, and sanitized error.

- [ ] **Step 4: Run tests and commit**

```bash
git add agent/orchestration/__init__.py agent/orchestration/models.py agent/orchestration/validation.py tests/orchestration/__init__.py tests/orchestration/factories.py tests/orchestration/test_models.py
git commit -m "feat(orchestration): define bounded task and artifact contracts"
```

### Task 6: Produce structured plans with a safe single-task fallback

**Files:**
- Create: `agent/orchestration/planner.py`
- Modify: `agent/graph/nodes.py`
- Modify: `agent/graph/state.py`
- Modify: `agent/graph/workflow.py`
- Test: `tests/orchestration/test_planner.py`

**Interfaces:**
- Produces `async create_execution_plan(request, turn_context, model) -> ExecutionPlan`.
- Adds `execution_plan`, `worker_artifacts`, and `orchestration_enabled` to graph state.
- Invalid or unsupported structured output becomes one main-executor task; it never fails the user turn.

- [ ] **Step 1: Write planner/fallback tests**

Provide fake structured output containing two independent tasks (`audit-backend`, `audit-web`) and one dependent synthesis task. Assert dependencies validate and two tasks are initially ready. Provide malformed JSON and assert a one-task plan with `kind="analysis"`, no worker delegation, and the original objective.

- [ ] **Step 2: Run and verify failure**

Run: `python -m unittest tests.orchestration.test_planner -v`  
Expected: structured planner does not exist.

- [ ] **Step 3: Implement task-specific planning prompt**

The prompt states worker tools, read-only restriction, evidence schema, default/max workers, no nested delegation, exact stopping rules, and that dependent or conflicting edits remain with the main executor. Use model structured output when supported; otherwise parse one JSON object and validate. Reject plans over 12 tasks.

Route Plan/Goal and heuristic complex Edit through structured planning. Plan approval displays both human-readable Markdown and typed tasks. A user revision is included as planner feedback.

- [ ] **Step 4: Run tests and commit**

```bash
git add agent/orchestration/planner.py agent/graph/nodes.py agent/graph/state.py agent/graph/workflow.py tests/orchestration/test_planner.py
git commit -m "feat(orchestration): create validated execution plans"
```

### Task 7: Run bounded read-only workers with cancellation and no nesting

**Files:**
- Create: `agent/orchestration/worker.py`
- Create: `agent/orchestration/coordinator.py`
- Modify: `agent/skills/subagent_factory.py`
- Modify: `agent/skills/manager.py`
- Modify: `agent/tools/registry.py`
- Modify: `agent/runtime/events.py`
- Test: `tests/orchestration/test_coordinator.py`

**Interfaces:**
- Produces `WorkerRunner.run(task, context, cancel_event) -> AgentArtifact`.
- Produces `Coordinator.run(plan, context, cancel_event, max_workers=2) -> list[AgentArtifact]`.
- Adds events `agent_started`, `agent_progress`, `agent_completed`, `agent_failed`.

- [ ] **Step 1: Write concurrency/dependency/cancel tests**

Use fake workers that block on events and record active count. Assert two independent tasks overlap with default max 2, never exceed 2, and a dependent task starts only after prerequisites complete. Configure 99 and assert clamp to 4. Cancel and assert every active worker returns cancelled. Give a worker `create_skill`/`edit_file` and assert registry denial. Attempt nested coordinator creation from a worker context and assert denial.

- [ ] **Step 2: Run and verify failure**

Run: `python -m unittest tests.orchestration.test_coordinator -v`  
Expected: coordinator/worker do not exist.

- [ ] **Step 3: Implement scheduler and worker adapter**

Coordinator repeatedly selects tasks whose dependencies completed successfully, schedules them through `asyncio.Semaphore(max_workers)`, and waits for first completion. A failed dependency marks dependent tasks blocked with an explicit artifact. Use `asyncio.timeout(task.timeout_seconds)`. Cancellation cancels child tasks and awaits them with `return_exceptions=True`.

WorkerRunner builds the existing subagent with only `registry.tools_for("worker")`, sets `delegation_allowed=False`, supplies task objective/success criteria/rules/workspace context, and validates the final artifact. It never returns raw unresolved tool calls.

- [ ] **Step 4: Emit redacted worker events**

Events contain task ID/title/status/duration and evidence counts, not full prompts or file contents. Add worker usage into RunMetrics.

- [ ] **Step 5: Run tests and commit**

```bash
git add agent/orchestration/worker.py agent/orchestration/coordinator.py agent/skills/subagent_factory.py agent/skills/manager.py agent/tools/registry.py agent/runtime/events.py tests/orchestration/test_coordinator.py
git commit -m "feat(orchestration): run bounded read-only workers"
```

### Task 8: Synthesize evidence, hand writes to the main executor, and render workers

**Files:**
- Create: `agent/orchestration/synthesis.py`
- Modify: `agent/graph/nodes.py`
- Modify: `agent/graph/workflow.py`
- Modify: `agent/runtime/artifacts.py`
- Modify: `agent/ui/event_renderer.py`
- Modify: `frontend/src/types/artifact.ts`
- Create: `frontend/src/components/agent/WorkerTimeline.tsx`
- Modify: `frontend/src/components/agent/AgentPanel.tsx`
- Modify: `frontend/src/components/chat/RunTimeline.tsx`
- Create: `frontend/src/components/agent/WorkerTimeline.test.tsx`
- Test: `tests/orchestration/test_synthesis.py`

**Interfaces:**
- Produces `SynthesisResult(summary, supported_findings, conflicts, proposed_changes, missing_evidence)`.
- Main executor receives synthesis plus artifacts and is solely responsible for write tool calls.
- RunArtifact adds `workers` and final walkthrough sections.

- [ ] **Step 1: Write conflict/evidence tests**

Provide two artifacts that make the same supported claim and assert deduplication. Provide contradictory claims about the same file/line and assert a conflict is surfaced, not arbitrarily selected. Provide a success artifact with no evidence and assert it is downgraded to invalid. Assert proposed changes remain text proposals until main executor calls a write tool.

- [ ] **Step 2: Run and verify failure**

Run: `python -m unittest tests.orchestration.test_synthesis -v`  
Expected: synthesis module does not exist.

- [ ] **Step 3: Implement deterministic pre-synthesis and one model synthesis**

First normalize/deduplicate evidence by `(type, locator, claim)`, identify exact conflicts, and list failed/blocked tasks without a model. Then make at most one synthesizer model call to produce a concise executor briefing containing verified evidence, conflicts, proposed changes, and missing items. Add its usage to metrics.

Graph flow after plan approval becomes coordinator → synthesis → main executor → approval/tools → hooks/evaluator → final. If no parallel tasks exist, bypass coordinator/synthesis.

- [ ] **Step 4: Render worker state in TUI and web**

WorkerTimeline shows task title, status, duration, evidence count, and expandable summary. It does not expose hidden prompts or secrets. TUI prints compact start/complete lines and `/agents` shows the current task table. Final walkthrough includes plan, worker contributions, changed files, checks, usage, unresolved conflicts, and terminal status.

- [ ] **Step 5: Run tests and commit**

Run: `python -m unittest tests.orchestration.test_synthesis -v`  
Run: `cd frontend && npm test -- --run src/components/agent/WorkerTimeline.test.tsx`  
Expected: evidence, conflict, write-authority, and UI tests PASS.

```bash
git add agent/orchestration/synthesis.py agent/graph/nodes.py agent/graph/workflow.py agent/runtime/artifacts.py agent/ui/event_renderer.py frontend/src/types/artifact.ts frontend/src/components/agent/WorkerTimeline.tsx frontend/src/components/agent/WorkerTimeline.test.tsx frontend/src/components/agent/AgentPanel.tsx frontend/src/components/chat/RunTimeline.tsx tests/orchestration/test_synthesis.py
git commit -m "feat(orchestration): synthesize worker evidence and walkthroughs"
```

### Task 9: Add an end-to-end bounded multi-agent acceptance suite

**Files:**
- Create: `tests/integration/test_multi_agent_journey.py`
- Create: `frontend/src/pages/MultiAgentJourney.test.tsx`
- Modify: `tests/integration/fake_agent.py`

**Interfaces:**
- Scenario: one task delegates backend audit and web audit in parallel, then main executor proposes one approved change, runs one hook, and finishes.

- [ ] **Step 1: Build the deterministic journey**

Use two fake read-only workers with distinct evidence, one synthesis result, one main-executor edit tool call, one approval resume, one checkpoint, one verification hook, and DONE. Record concurrency, actions, events, usage, artifacts, and changed content.

- [ ] **Step 2: Assert system guarantees**

Assert maximum active workers is 2; workers receive no mutating tools; only main executor writes; one checkpoint precedes write; approval precedes write; hook follows write; total usage includes planner/workers/synthesizer/executor; final artifact contains both worker contributions and the changed file.

- [ ] **Step 3: Assert TUI/web parity**

Replay the same event fixture in both surfaces and assert plan, workers, changed files, checks, usage, and final walkthrough are equivalent.

- [ ] **Step 4: Run and commit**

Run: `python -m unittest tests.integration.test_multi_agent_journey -v`  
Run: `cd frontend && npm test -- --run src/pages/MultiAgentJourney.test.tsx`  
Expected: complete journey PASS.

```bash
git add tests/integration/test_multi_agent_journey.py tests/integration/fake_agent.py frontend/src/pages/MultiAgentJourney.test.tsx
git commit -m "test(orchestration): protect bounded multi-agent journey"
```

## Plan 5 Completion Gate

- [ ] Rule precedence, `/init`, and `/learn` are deterministic and non-destructive.
- [ ] Hooks execute only through approval and appear as checks, never background jobs.
- [ ] Checkpoints restore create/edit/delete correctly and surface conflicts.
- [ ] Web session fork creates an isolated workspace; TUI fork clearly reports shared local workspace.
- [ ] Planner invalid output falls back to one main-executor task.
- [ ] Default/max concurrency is 2/4, nested delegation is impossible, and cancellation reaches all workers.
- [ ] Workers have no mutating tools and cannot approve actions.
- [ ] Only the main executor writes after approval and checkpoint.
- [ ] Final walkthrough is equivalent in TUI and web.
- [ ] All usage/timing includes worker and synthesis calls.
- [ ] Request code review before Plan 6.
