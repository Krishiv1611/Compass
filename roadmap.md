# Compass evidence-based roadmap

This file separates behavior covered by repository tests from work that is unavailable or deferred. A checked item means a focused automated test exists; it does not mean the full release gate or manual journey matrix has been completed.

## Tested baseline

- [x] Shared TUI/web runtime events, typed interrupts, resume actions, and turn-local state.
- [x] Ask/Edit/Plan/Goal routing invariants, loop/goal limits, and threshold-based context compaction.
- [x] Owned active web workspace selection, traversal rejection, context versions, and run snapshots.
- [x] Patch creation, apply/reject/undo behavior, file checkpoints, preview, conflict handling, and restore.
- [x] Run lifecycle persistence, reconnect replay, cancellation, terminal events, and startup reconciliation.
- [x] Access/refresh authentication, single-use refresh rotation, logout revocation, verified OAuth email handling, and credential encryption boundaries.
- [x] Single-process WebSocket connection/message/run limits and weighted HTTP rate-limit pruning.
- [x] Per-user web skill isolation, validated skill names, read-only global skills, and request-scoped registries.
- [x] Public local configuration consumers and truthful command-result statuses, including unavailable scheduling.
- [x] Project instruction precedence/bounds and approval-controlled verification hook scheduling.
- [x] Bounded read-only worker planning, dependency layers, timeout/cancellation, evidence validation, synthesis, and surface events.
- [x] Runtime timing/token metrics and redacted diagnostics.
- [x] Core web accessible names, mention keyboard behavior, file-tree navigation, mutation error propagation, and shared session loading.
- [x] GitHub connection/import/publish service boundaries and workspace patch flows.
- [x] Liveness/readiness separation and cloud secret validation.
- [x] Reachability reports plus allowlisted generated-file cleanup safety.

## Release gate still required

- [ ] Run `tools/verify.py --scope all` successfully in the working checkout.
- [ ] Bootstrap a clean copied checkout from frozen Python and frontend inputs, then run the same verification command successfully.
- [ ] Complete the program-level TUI/web manual journey matrix across authentication, workspaces, modes, interrupts, patches, reconnect/cancel/delete, responsive accessibility, and GitHub recovery.
- [ ] Review production Compose overrides for all cloud security variables, persistent volumes, TLS termination, backups, and one-worker enforcement.
- [ ] Obtain code review for the complete hardening program.

## Near-term reliability

- [ ] Add browser-level end-to-end coverage for the manual journey matrix; current frontend tests use component/runtime fixtures rather than a deployed browser stack.
- [ ] Add tested migration deployment/rollback rehearsal against a disposable PostgreSQL instance.
- [ ] Add operational dashboards and alert thresholds for the safe aggregate metrics already emitted.
- [ ] Define and implement physical retention for soft-deleted sessions, workspace files, uploads, vector data, and checkpoints.
- [ ] Expand GitHub conflict, permission, remote-advance, and retry recovery coverage.
- [ ] Replace legacy duplicated TUI help metadata with one registry-derived display source.

## Explicitly unavailable

- Scheduled/background task execution: `/schedule` reports unavailable and creates nothing.
- Multi-process or horizontally scaled enforcement: limits are process-local; the supported deployment is one backend process.
- Browser-supplied command MCP servers or hosted arbitrary shell execution.
- Automatic physical erasure after session soft deletion.
- A separate `/grill-me` interview engine; the command enters Plan mode.

## Deferred heavy infrastructure

These are candidates only after measured need and explicit design/testing:

- Shared rate-limit, WebSocket, and active-run coordination for multi-worker deployment.
- A durable job scheduler and worker fleet.
- Centralized organization policy administration, audit export, enterprise identity, and retention controls.
- Large-scale evaluation infrastructure and production experiment management.
- Team-owned reusable workflow templates after the single-executor and approval contracts remain stable.
- Alternative retrieval stores only with migration, scope-isolation, and relevance evidence.

## Decision rules

1. Do not mark an item done from prose or screenshots; link it to a repeatable test or an accepted manual release record.
2. Preserve one mutation executor and explicit approval boundaries unless a replacement has equivalent tests.
3. Do not add distributed infrastructure before the one-process limitation becomes a measured blocker.
4. Treat deletion, retention, authentication, credential, and workspace changes as security-sensitive migrations.
5. Keep TUI and web capability differences deliberate and documented instead of promising false parity.
