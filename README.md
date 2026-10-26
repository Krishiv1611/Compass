# Compass

Compass is an inspectable AI coding workbench with two working entry points:

- **Local TUI:** runs against a checked-out repository and can use local file, shell, Git, skill, RAG, and MCP capabilities under its approval policy.
- **Web workbench:** runs authenticated agent tasks against an owned server workspace, streams run events, reviews patches, and supports GitHub import/publish flows. Hosted execution intentionally omits arbitrary shell and browser-configured command MCP servers.

Compass is under active development. It is designed for a single backend process today; read [DEPLOYMENT.md](DEPLOYMENT.md) before exposing it publicly.

## Working paths

### Local TUI

Requirements: Python 3.12, `uv` 0.9 or newer, and a key for the selected model provider. PostgreSQL is optional for the TUI; without `DB_URI`, checkpoints use the local fallback.

```powershell
.\tools\bootstrap.ps1
$env:OPENROUTER_API_KEY = "<key>"
.\.venv\Scripts\python.exe main.py --workspace D:\path\to\project
```

Equivalent manual setup is `uv sync --frozen --all-groups`, followed by `python main.py --workspace <path>`.

### Web workbench

Requirements: the Python prerequisites above, Node.js 20 or newer, PostgreSQL 15 or newer, and Docker Compose or an equivalent PostgreSQL installation.

```powershell
.\tools\bootstrap.ps1
docker compose up -d postgres
$env:DB_URI = "postgresql://compass_user:compass_password@localhost:5432/compass_db"
$env:OPENROUTER_API_KEY = "<key>"
$env:JWT_SECRET = "<long-random-development-secret>"
alembic upgrade head
uvicorn backend.main:app --reload --port 8000
```

In a second terminal:

```powershell
Set-Location frontend
npm run dev
```

Open [http://localhost:5173](http://localhost:5173). The frontend uses the same-origin `/api` base by default. Vite development proxies `/api` HTTP and WebSocket traffic to `http://localhost:8000`; the built Nginx image proxies the same prefix to the backend. Set `VITE_API_URL` only when the UI must use a different public API origin or base path.

`GET /health` is cheap process liveness. `GET /ready` checks the database, durable checkpointer, and workspace storage as required dependencies; memory, embeddings, and MCP are reported as optional capabilities. Readiness probes are bounded and cached.

## Product surfaces

| Capability | Local TUI | Web workbench |
| --- | --- | --- |
| Ask, Edit, Plan, Goal modes | Working | Working |
| Project files and search | Current repository | Owned active workspace |
| Shell execution | Approval-controlled | Unavailable in cloud mode |
| Skills | Global + workspace scope | Global read-only + isolated per-user scope |
| MCP | Local configuration | Server-managed capability status only |
| Semantic retrieval | Local index when configured | Available only with embedding configuration and credentials |
| File checkpoints and restore | Working | Working for owned workspaces |
| GitHub delivery | Local CLI helpers | OAuth/PAT connection, import, branch, commit, pull request |
| Scheduling/background jobs | Unavailable | Unavailable |

Provider use is BYOK: users or operators supply credentials for the selected model provider. Access tokens stay in browser memory. The refresh token is a rotating, single-use HttpOnly cookie scoped to `/api/auth`; refresh rotation and logout revoke the previous refresh generation. Stored web provider credentials and GitHub PATs use `CREDENTIAL_ENCRYPTION_KEY`.

Embedding capability is separate from chat-model capability. Configure both `EMBEDDING_PROVIDER` and `EMBEDDING_MODEL`, plus the relevant user/provider credential, before expecting semantic memory or retrieval. Missing embeddings are reported as unavailable rather than making the whole service unready.

## Terminal UI

Run `python main.py --workspace <path>` and type `/help` for the live reference. Public commands are registered by the TUI; some commands may return `waiting`, `unavailable`, or `failed` instead of claiming an action occurred.

| Status | Commands |
| --- | --- |
| Session and recovery | `/new`, `/sessions`, `/resume`, `/rename`, `/history`, `/fork`, `/checkpoints`, `/restore`, `/undo`, `/compact` |
| Context and changes | `/workspace`, `/index`, `/add`, `/context`, `/init`, `/learn`, `/diff`, `/files`, `/review` |
| Agent inspection/control | `/mode`, `/goal`, `/grill-me`, `/permissions`, `/model`, `/tools`, `/cost`, `/status`, `/capabilities`, `/route`, `/timing`, `/hooks`, `/agents` |
| Integrations and utilities | `/github`, `/commit`, `/pr`, `/mcp`, `/config`, `/doctor`, `/ui`, `/help`, `/clear`, `/exit` |
| Explicitly unavailable | `/schedule` reports that scheduling is unavailable and does not create a task. |

`/grill-me` enters Plan mode; it does not start a separate interview workflow. `/ui` opens the configured web URL only when it is reachable. GitHub and MCP commands report failures or missing configuration rather than synthesizing success.

## Configuration

Copy [.env.example](.env.example) and review every value. Backend settings are read from the environment, `.env`, or `backend/.env`.

| Variable | Requirement and effect |
| --- | --- |
| `DB_URI` | Required for the web app and durable LangGraph checkpointing; there is no implicit SQLite web default. |
| `COMPASS_CLOUD_MODE` | Set `true` for hosted execution; removes the shell tool and activates cloud security validation. |
| `JWT_SECRET` | Signs access and refresh tokens. Cloud mode rejects defaults and weak values. |
| `CREDENTIAL_ENCRYPTION_KEY` | Independent Fernet key for stored credentials; required in cloud mode. |
| `SECURE_COOKIES` | Must be `true` in cloud mode behind HTTPS. |
| `CORS_ORIGINS` | Comma-separated credentialed browser origins. |
| `WORKSPACE_ROOT` | Server-owned web workspace root. |
| `SKILLS_ROOT` | Global skill root; web-user skills live below its isolated user area. |
| `DEFAULT_PROVIDER`, `DEFAULT_MODEL` | Defaults used before a web user selects BYOK provider settings. |
| `EMBEDDING_PROVIDER`, `EMBEDDING_MODEL` | Optional semantic-memory capability; configure both. |
| `MCP_SERVERS_FILE` | Optional server-side MCP capability file; the web UI cannot submit executable commands. |
| `JWT_ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES`, `REFRESH_TOKEN_EXPIRE_DAYS` | Token algorithm and lifetimes. |
| `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` | Optional Google identity OAuth. |
| `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET` | Optional GitHub identity and repository connection OAuth. |
| `OPENROUTER_API_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY`, `GROQ_API_KEY` | Model-provider credentials consumed by the local/runtime provider adapter. |
| `TAVILY_API_KEY` | Optional Tavily web search; the tool falls back when it is absent. |
| `COMPASS_REDIS_URL` | Optional LLM response cache. |
| `VITE_API_URL` | Public frontend API base; defaults to `/api`. Never place secrets in Vite variables. |

Local agent preferences merge built-in defaults, `~/.compass/config.toml`, project `.compass/config.toml`, then derived `COMPASS_*` environment overrides. Retained public keys have runtime consumers for theme, tool result limit, shell timeout, compaction threshold, loop limit, RAG auto-index/chunk size, HITL policy, blocked commands, and orchestration controls.

The compaction router reads `context.summarize_after`; its built-in default is `10` messages. It compacts only after the message count exceeds that threshold and no tool calls are pending.

## Runtime and safety model

Both surfaces call the same `agent.runtime.runner` and one registered LangGraph executor spine. Short read-only requests may route directly; planning, approval, tool execution, recovery, validation, verification hooks, and bounded read-only worker analysis are entered only when needed.

Plan approval, tool approval, and clarification are explicit LangGraph interrupts. Risky local actions stay approval-controlled. Web turns are pinned to the session's owned active workspace snapshot; absolute paths, traversal, and stale context are rejected. File mutations create recoverable checkpoints and patch/run events.

Web session deletion is soft deletion. Compass cancels active runs and disconnects session sockets before returning success, but it does not physically erase workspace files, uploads, vectors, checkpoints, or database records. Operators own retention and physical cleanup.

The single-process web limits are five concurrent WebSockets per user, 64 KiB message content, two active runs per user, and ten run starts per minute. HTTP rate buckets and these run/socket bounds are process-local, so do not scale to multiple backend workers and assume global enforcement.

## Web API

Request/response details live in generated OpenAPI at `/docs`. Registered public bases are:

| Area | Base |
| --- | --- |
| Liveness / readiness | `/health`, `/ready` |
| Authentication | `/api/auth` |
| Sessions, runs, uploads | `/api/sessions` |
| Streaming chat | `/api/chat` |
| Workspaces, patches, checkpoints | `/api/workspaces` |
| Preferences | `/api/settings` |
| Skills and tools | `/api/skills`, `/api/tools` |
| GitHub | `/api/github` |
| Memory | `/api/memory` |

WebSockets use `/api/chat/ws/<session-id>` and authenticate through the `compass.v1` and `compass.jwt.<access-token>` subprotocol values. Tokens are not placed in the query string.

## Verification

Run one summarized release gate from the repository root:

```powershell
.\.venv\Scripts\python.exe tools\verify.py --scope all
```

Available scopes are `python`, `frontend`, `compose`, `docs`, and `all`. The command prints each argument array, duration, exit code, timeout, and a final pass/failure summary. It does not replace the program-level manual TUI/web journey matrix.

Generate or check the graph document without starting runtime services:

```powershell
.\.venv\Scripts\python.exe tools\render_workflow.py
.\.venv\Scripts\python.exe tools\render_workflow.py --check
```

## Troubleshooting

| Symptom | Exact check |
| --- | --- |
| API is live but not ready | Open `/ready`; fix required `database`, `checkpointer`, or `workspace` failures. Optional unavailable components do not force 503. |
| Browser API calls fail in Vite development | Confirm the checked-in `/api` proxy can reach `http://localhost:8000`; for an alternate backend, set `VITE_API_URL` and include the frontend origin in `CORS_ORIGINS`. |
| Refresh immediately signs out | Keep `JWT_SECRET` stable, use HTTPS with `SECURE_COOKIES=true` in cloud mode, and verify the reverse proxy preserves `/api/auth` cookies. Refresh tokens are single-use. |
| WebSocket cannot connect | Proxy `/api/` with Upgrade headers and confirm the client supplies both required subprotocol values. |
| Cloud startup rejects configuration | Replace the default `JWT_SECRET`, generate a separate Fernet `CREDENTIAL_ENCRYPTION_KEY`, and enable `SECURE_COOKIES`. |
| Semantic memory is unavailable | Configure embedding provider/model and a matching provider credential; check `/ready` for the optional component status. |
| A deleted session's storage remains | This is expected soft-delete retention; apply an operator-reviewed retention procedure. |

## Project documents

- [Deployment guide](DEPLOYMENT.md)
- [Architecture reference](docs/COMPASS_ARCHITECTURE.md)
- [Generated workflow](langgraph_workflow.md)
- [Evidence-based roadmap](roadmap.md)

No license file is currently included. Add an explicit license before redistribution or external contributions.
