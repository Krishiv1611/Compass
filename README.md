# Compass

Compass is an AI coding workbench for understanding, changing, reviewing, and publishing software projects. It pairs a LangGraph-powered agent with two first-class interfaces:

- a local terminal UI for working directly in a checked-out repository; and
- an authenticated web workbench for isolated uploaded or GitHub-imported projects.

Compass is built around a simple principle: powerful coding automation should remain inspectable and under the developer's control. Project context, run activity, approvals, patches, and GitHub publishing are explicit product surfaces rather than hidden behind a chat transcript.

> **Status:** Active development. The web workbench implementation phases F0-F8 are complete. Review the security notes before exposing the service publicly.

## Contents

- [What Compass does](#what-compass-does)
- [Architecture](#architecture)
- [Interfaces](#interfaces)
- [Quick start](#quick-start)
- [Configuration](#configuration)
- [Safety and security](#safety-and-security)
- [Web API and workspaces](#web-api-and-workspaces)
- [Repository layout](#repository-layout)
- [Development and verification](#development-and-verification)
- [Docker and deployment](#docker-and-deployment)
- [Troubleshooting](#troubleshooting)
- [Project documents](#project-documents)

## What Compass does

Compass can:

- plan and execute coding tasks through `Ask`, `Edit`, `Plan`, and `Goal` modes;
- read files, search source, retrieve semantic project context, maintain task context, and use connected tools;
- create patches, show actual change statistics, apply or reject individual changes, and undo applied patches;
- persist web conversations, runs, workspace metadata, and project context versions in PostgreSQL;
- import a GitHub repository, create a branch, commit reviewed files, and open a pull request;
- stream agent activity over WebSocket and show compact run stages, affected files, tool calls, approvals, and failures;
- provide local semantic search/RAG, configurable skills, and local MCP support in the TUI; and
- run the same agent workflow from a terminal or the web product while keeping their execution boundaries distinct.

The hosted web UI deliberately does **not** allow arbitrary local shell commands or command-based MCP server configuration. Those capabilities remain local/TUI concerns.

## Architecture

```mermaid
flowchart TB
  tui["Terminal UI\nlocal repository"] --> agent
  web["React workbench\nisolated workspace"] --> api
  api["FastAPI API\nREST + WebSocket"] --> agent
  api --> db[("PostgreSQL\nusers, sessions, runs, patches")]
  api --> ws["Workspace storage\n~/.compass/workspaces"]
  agent["LangGraph agent"] --> tools["Tools, RAG, skills, memory and safety"]
  agent --> checkpoints[("PostgreSQL checkpoints\nwhen DB_URI is configured")]
  agent --> providers["LLM providers"]
  api --> github["GitHub OAuth / PAT\nrepository connection"]
```

### Agent workflow

The workflow routes short conversation directly to one chat node. Edit requests use the executor and deterministic tool approval. Plan and Goal modes opt into project context, planning, validation, recovery, and clarification only when needed. Skills run as disposable subgraphs that inherit the parent workspace, model, user, and safety context.

### Persistent state

| Data | Store | Purpose |
| --- | --- | --- |
| Web users, sessions, messages, runs, patches, workspaces | PostgreSQL | Product state and ownership checks |
| LangGraph checkpoints | PostgreSQL when `DB_URI` is set | Resume agent threads and workflow state |
| Web workspace files | `~/.compass/workspaces/<user>/<workspace>` | Isolated project contents |
| TUI configuration | `~/.compass/config.toml` or `<project>/.compass/config.toml` | Local preferences and agent settings |
| Long-term user/project memory | LangGraph PostgresStore | Durable cross-thread recall |
| Vector/search data | PGVector | Semantic codebase and upload retrieval |

Web-session deletion is a soft delete: Compass first cancels active runs and
closes that session's WebSocket connections, then hides the conversation from
the product. It does not physically erase associated workspace files, uploads,
vectors, checkpoints, or database records. Retention and physical cleanup are
an operator responsibility until a dedicated retention job is introduced.

## Interfaces

### Web workbench

The React application is an authenticated coding workspace with:

- one shared responsive workbench state across desktop and mobile;
- accessible file filtering and keyboard tree navigation;
- editor, changes, preview, agent, and activity destinations;
- a command palette, context inspector, project rail, status bar, and theme menu;
- email/password, Google OAuth, and GitHub identity sign-in when configured;
- separately managed GitHub repository connection via OAuth or a fine-grained PAT;
- patch review and staged GitHub publishing: branch, commit, then pull request; and
- light, dark, and system themes using locally bundled IBM Plex Sans and JetBrains Mono.

By default, the frontend calls `http://localhost:8000/api` and opens WebSocket connections at `ws://localhost:8000/api/chat/ws/...`. Change those public endpoints with `VITE_API_URL` and `VITE_WS_URL` only; never put secrets in Vite environment variables.

### Terminal UI

Run the local experience from the repository root:

```bash
python main.py
python main.py --workspace /path/to/project
python main.py --message "Explain the current authentication flow"
python main.py --resume
python main.py --session <session-id-prefix>
```

The TUI includes session management, diffs, rollback, RAG indexing, configuration, diagnostics, Git/GitHub helpers, project context, and approval controls. Type `/help` in the TUI for the live command reference.

| Area | Commands |
| --- | --- |
| Conversation | `/new`, `/sessions`, `/resume`, `/rename`, `/history`, `/compact` |
| Project context | `/workspace`, `/index`, `/add`, `/context`, `/init`, `/learn` |
| Changes | `/diff`, `/files`, `/review`, `/undo`, `/commit`, `/pr` |
| Agent behavior | `/mode`, `/goal`, `/permissions`, `/model`, `/tools`, `/cost`, `/status` |
| Integrations | `/github`, `/mcp`, `/config`, `/doctor` |
| Utilities | `/clear`, `/ui`, `/schedule`, `/grill-me`, `/exit` |

## Quick start

### Requirements

- Python 3.12
- uv 0.9 or newer
- Node.js 20 or newer
- PostgreSQL 15 or newer for the web application and durable checkpoints
- an LLM provider key; `OPENROUTER_API_KEY` is the default supported path

Git, Docker, GitHub CLI, and OAuth credentials are optional but enable additional workflows.

### 1. Get the source and bootstrap dependencies

```bash
git clone https://github.com/Krishiv1611/Compass.git
cd Compass
```

On Windows, the bootstrap script verifies prerequisites, creates the frozen
Python environment, and installs the frontend with `npm ci`:

```powershell
.\tools\bootstrap.ps1
```

For manual or non-Windows setup, use the same frozen inputs:

```bash
uv sync --frozen --all-groups
cd frontend && npm ci
```

### 2. Configure local development

Start PostgreSQL with Docker, or point `DB_URI` to an existing PostgreSQL instance:

```bash
docker compose up -d postgres
```

Set the minimum environment variables for the web application. This PowerShell example matches the development Compose database:

```powershell
$env:DB_URI = "postgresql://compass_user:compass_password@localhost:5432/compass_db"
$env:OPENROUTER_API_KEY = "<your-provider-key>"
$env:JWT_SECRET = "<a-long-random-development-secret>"
```

For macOS or Linux:

```bash
export DB_URI='postgresql://compass_user:compass_password@localhost:5432/compass_db'
export OPENROUTER_API_KEY='<your-provider-key>'
export JWT_SECRET='<a-long-random-development-secret>'
```

The backend also reads `.env` and `backend/.env`. Keep both out of version control.

### 3. Run database migrations

```bash
alembic upgrade head
```

### 4. Start the API and web application

In one terminal, with the virtual environment and environment variables active:

```bash
uvicorn backend.main:app --reload --port 8000
```

In a second terminal:

```bash
cd frontend
npm ci
npm run dev
```

Open [http://localhost:5173](http://localhost:5173). The API health endpoint is [http://localhost:8000/health](http://localhost:8000/health), and interactive API documentation is available at [http://localhost:8000/docs](http://localhost:8000/docs).

### TUI-only quick start

If you only need the local terminal agent, `DB_URI` is optional. Install the Python dependencies, set an LLM provider key, then run:

```bash
python main.py --workspace /path/to/project
```

Without `DB_URI`, the agent runs without PostgreSQL-backed LangGraph checkpoints.

## Configuration

### Backend and deployment environment

| Variable | Required | Purpose |
| --- | --- | --- |
| `DB_URI` | Web app | PostgreSQL connection URL; also enables agent checkpoint persistence. |
| `OPENROUTER_API_KEY` | Default provider | OpenRouter model-provider key. |
| `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY`, `GROQ_API_KEY` | Optional | Provider-specific model keys. |
| `JWT_SECRET` | Web app | Token signing secret; use a long random production value. |
| `JWT_ALGORITHM` | Optional | JWT algorithm; defaults to `HS256`. |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Optional | Access-token lifetime; defaults to `15`. |
| `REFRESH_TOKEN_EXPIRE_DAYS` | Optional | Refresh-cookie lifetime; defaults to `7`. |
| `SECURE_COOKIES` | Production | Set `true` behind HTTPS. |
| `CORS_ORIGINS` | Production | Comma-separated allowlist of browser origins. |
| `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` | Optional | Google identity OAuth credentials. |
| `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET` | Optional | GitHub identity and repository-connect OAuth credentials. |
| `CREDENTIAL_ENCRYPTION_KEY` | Recommended in production | Fernet key for stored provider credentials and GitHub PATs. |
| `COMPASS_CLOUD_MODE` | Hosted deployments | Removes the shell tool from the agent tool registry. |
| `TAVILY_API_KEY` | Optional | Enables Tavily-backed web search when configured. |
| `COMPASS_REDIS_URL` | Optional | Enables the configured LLM response-cache path. |
| `SKILLS_ROOT` | Optional | Root for installed skills and isolated web-user skills under `users/{user_id}`. |
| `VITE_API_URL`, `VITE_WS_URL` | Frontend only | Public API and WebSocket bases for separately hosted frontend. Never put secrets here. |

### Local agent configuration

The local agent merges built-in defaults, `~/.compass/config.toml`, `<project>/.compass/config.toml`, then `COMPASS_*` environment variables. A dotted setting maps to an environment variable by replacing dots with underscores; for example, `model.executor` becomes `COMPASS_MODEL_EXECUTOR`.

| Setting | Default | Meaning |
| --- | --- | --- |
| `model.planner` / `model.executor` | `google/gemma-4-31b-it:free` | Role-specific model selection |
| `safety.mode` | `auto` | Local TUI approval-policy setting; use the default for normal work |
| `model.evaluator` | `google/gemma-4-31b-it:free` | Goal validation and direct-chat role |
| `hitl.enabled` | `true` | Enable human-in-the-loop requests |
| `tools.shell_timeout` | `30` | Shell command timeout in seconds |
| `rag.auto_index` | `false` | Index the codebase automatically |
| `rag.chunk_size` | `1000` | RAG chunk size |
| `context.summarize_after` | `10` | Conversation size before compaction |

## Safety and security

Compass is designed to make side effects visible and reviewable. It can modify code and execute local commands, so use it with the same care you would give any automation with repository access.

### Approval model

- Read/search tools are treated as safe.
- Local file writes, edits, and shell commands are classified as risky and require approval under the default `auto` policy.
- Approvals support `yes`, `no`, `always`, and `skip` decisions.
- Goal mode can make progress autonomously, but it does not bypass risky-operation approval.
- In hosted mode (`COMPASS_CLOUD_MODE=true`), `shell_execute` is removed from the available tool registry.

### Workspace isolation and data handling

- Web workspaces are created in a per-user directory and checked against ownership before access.
- Workspace file APIs reject absolute paths and traversal attempts, and keep operations inside the workspace root.
- GitHub access is separate from Compass identity login. Repository connections use OAuth or a user-supplied fine-grained PAT.
- Refresh tokens use an HTTP-only cookie; the browser keeps access tokens in memory rather than persistent browser storage.
- Stored provider credentials and PATs are encrypted using `CREDENTIAL_ENCRYPTION_KEY`; configure an independent, rotated Fernet key in production.
- Hosted web settings reject arbitrary command-based MCP configuration. Configure local MCP servers from the TUI/project environment only.

### Production checklist

1. Use HTTPS and set `SECURE_COOKIES=true`.
2. Set distinct, strong `JWT_SECRET` and `CREDENTIAL_ENCRYPTION_KEY` values.
3. Set `COMPASS_CLOUD_MODE=true` for hosted installations.
4. Set a precise `CORS_ORIGINS` allowlist.
5. Run migrations before starting new releases.
6. Put PostgreSQL and workspace storage on private, backed-up volumes.
7. Run the backend as a non-root operating-system user.
8. Review GitHub OAuth scopes and PAT permissions; use the smallest repository scope that works.
9. Run a single backend worker. HTTP, WebSocket connection, and active-run
   limits are intentionally process-local; using multiple workers weakens those
   bounds until shared rate-limit state is added.

## Web API and workspaces

The FastAPI application mounts its product API under `/api`. Use the generated OpenAPI documentation at `/docs` as the source of truth for request and response shapes.

| Area | Base path | Capabilities |
| --- | --- | --- |
| Health | `/health` | Liveness endpoint |
| Authentication | `/api/auth` | Registration, login, refresh, profile, logout, Google/GitHub identity OAuth |
| Sessions | `/api/sessions` | Create, list, rename, retrieve, and soft-delete conversations |
| Chat | `/api/chat` | HTTP fallback and authenticated streamed WebSocket runs |
| Workspaces | `/api/workspaces` | Upload/create/import projects, tree/file access, context, search, patches, review actions |
| GitHub | `/api/github` | Connection status, OAuth/PAT connect, repository browsing, import, branch/commit/PR publishing |
| Preferences and tools | `/api/settings`, `/api/tools` | Safe preferences, managed MCP status, available tools, run history, skills |

The streaming endpoint is:

```text
ws://<host>/api/chat/ws/<session-id>?token=<access-token>
```

The browser application handles this connection. Direct clients should authenticate, create a session, then pass a short-lived access token only over a secure WebSocket connection.

The hosted backend currently supports one process worker. It enforces up to
five concurrent WebSockets, two active runs, and ten run starts per minute per
user in that process; it also caps WebSocket message content at 64 KiB. Do not
scale workers horizontally expecting these in-memory bounds to be global.

## Repository layout

```text
.
├── agent/                  # LangGraph workflow, tools, RAG, skills, memory, safety, TUI
│   ├── graph/              # State, nodes, routing, and tool registry
│   ├── tools/              # File, search, shell, web, memory, todo, skill tools
│   ├── rag/                # Indexing, chunking, retrieval, vector storage
│   ├── skills/             # Skill models, loading, registry, subagent support
│   └── ui/                 # Terminal UI and relay support
├── backend/                # FastAPI application
│   ├── auth/               # JWT, OAuth, password, credential encryption
│   ├── models/             # SQLAlchemy data models
│   ├── routers/            # HTTP and WebSocket product APIs
│   ├── services/           # Agent runner, sessions, patches, workspaces, GitHub
│   └── alembic/            # Database migrations
├── frontend/               # React 19 + TypeScript coding workbench
│   ├── src/api/            # Typed domain API clients
│   ├── src/contexts/       # Auth, run, and workbench UI state
│   ├── src/components/     # Workbench, agent, project, review, settings UI
│   └── src/pages/          # Login, callback, and workbench routes
├── tests/                  # Fast architecture and routing invariants
├── main.py                 # TUI CLI entry point
├── pyproject.toml          # Human-maintained Python dependencies
├── requirements.lock      # Frozen runtime install input
├── requirements-dev.lock  # Frozen runtime and development install input
├── requirements.txt       # Compatibility pointer to requirements.lock
├── alembic.ini             # Migration configuration
├── docker-compose.yml      # Development Docker stack
└── docker-compose.prod.yml # Production-oriented Docker stack
```

## Development and verification

### Backend and agent checks

```bash
python -m compileall -q agent backend
alembic upgrade head
```

### Frontend checks

```bash
cd frontend
npm run lint
npx tsc -b --pretty false
npm run build
```

The frontend pass also requires manual checks across desktop and mobile viewports, light/dark/system themes, keyboard navigation, reduced motion, empty/loading/error states, GitHub capability states, and browser-console cleanliness. See [frontend/README.md](frontend/README.md) for frontend-specific notes.

### Fast architecture tests

```bash
python -m unittest discover -s tests -v
```

## Docker and deployment

### Development stack

The development Compose file starts PostgreSQL, the backend, and the built frontend:

```bash
OPENROUTER_API_KEY=<your-provider-key> JWT_SECRET=<development-secret> docker compose up --build
```

The frontend is exposed on port `80`, the backend on port `8000`, and PostgreSQL on port `5432`. Apply migrations in the backend environment before relying on a fresh deployment.

### Production stack

`docker-compose.prod.yml` defines resource limits and health checks for PostgreSQL, backend, and frontend containers. Provide at minimum `POSTGRES_PASSWORD`, `DB_URI`, `OPENROUTER_API_KEY`, and `JWT_SECRET`, then start it with:

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

For a public deployment, additionally configure `SECURE_COOKIES=true`, `CORS_ORIGINS`, OAuth redirect URLs and credentials, `CREDENTIAL_ENCRYPTION_KEY`, persistent volumes, TLS termination, backups, and `COMPASS_CLOUD_MODE=true`. See [DEPLOYMENT.md](DEPLOYMENT.md) for the deployment checklist.

## Troubleshooting

| Symptom | What to check |
| --- | --- |
| API fails at startup | Confirm `DB_URI` is set and PostgreSQL is reachable. The API logs database connectivity during startup. |
| Migration command fails | Activate the Python environment, set `DB_URI`, and run `alembic upgrade head` from the repository root. |
| Web app cannot sign in or load data | Confirm the API is running on port `8000`, the frontend uses the expected `VITE_API_URL`, and its origin is in `CORS_ORIGINS`. |
| Browser keeps returning to login | Verify `JWT_SECRET` is stable and browser cookies match `SECURE_COOKIES` / HTTPS settings. |
| GitHub connect is unavailable | Set `GITHUB_CLIENT_ID` and `GITHUB_CLIENT_SECRET`, then check the OAuth redirect URL. |
| Agent cannot call an LLM | Set the matching provider key and verify the selected model/provider settings. |
| Shell tool is unavailable | It is intentionally unavailable in hosted mode. Use the local TUI only when shell execution is appropriate. |
| Semantic search has no useful results | Run `/index` in the TUI or refresh workspace context in the web workbench. |

## Project documents

- [DEPLOYMENT.md](DEPLOYMENT.md) - production deployment notes and security checklist
- [frontend/README.md](frontend/README.md) - frontend architecture and verification commands
- [roadmap.md](roadmap.md) - future ideas; treat it as planning material, not a statement of shipped features
- [docs/COMPASS_ARCHITECTURE.md](docs/COMPASS_ARCHITECTURE.md) - complete feature, workflow, router, table, memory, frontend, and extension reference

## License

No license file is currently included in this repository. Add an explicit license before redistributing or accepting external contributions.
