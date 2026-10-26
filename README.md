# Compass

Compass is an inspectable, full-stack AI developer workbench designed for end-to-end software engineering. It combines an in-browser visual application canvas, interactive DOM element inspection, an embedded xterm.js terminal, ephemeral cloud sandbox microVMs, and an autonomous multi-agent reasoning loop into a single, high-density development environment.

Compass eliminates local hardware bottlenecks and cloud hosting costs by running interactive web preview environments directly inside the browser using client-side WebContainers, and offloading heavy compute and headless browser testing to isolated remote Firecracker microVMs.

---

## System Architecture

```
+-------------------------------------------------------------------------------------------------------------+
| [⚡ Compass]  Project: my-app (main · a1b2c3)     |  [Canvas] [Editor] [Changes 2] [Snapshots]  | <350ms [Terminal] |
+-----------------------+-------------------------------------------------------------+-----------------------+
|  PROJECT RAIL         |  CENTRAL WORKBENCH                                          |  AGENT COPILOT        |
|  - New Task (+)       |  +--------------------------------------------------------+ |  Transcript stream    |
|  - Skills             |  | [100% | 768px | 375px] [Inspect] [Refresh] [Popout]    | |  - Reasoning fold     |
|  - Connectors         |  |--------------------------------------------------------| |  - Patch diff preview |
|                       |  |                                                        | |  - [↺ Revert turn]   |
|  FILE EXPLORER        |  |             LIVE WEBCONTAINER CANVAS                   | |                       |
|  > src/               |  |               (or CodeMirror Editor)                   | |-----------------------|
|    App.tsx            |  |                                                        | | [Ask | Edit|Plan|Goal]|
|    main.tsx           |  |                                                        | | [@file #component]    |
|    index.css          |  +--------------------------------------------------------+ | Prompt input...       |
|                       |  [PRO TERMINAL DRAWER: xterm.js PTY / Logs / Playwright QA] | [Paperclip]   [Send ^]  |
+-----------------------+-------------------------------------------------------------+-----------------------+
|  STATUS: Connected · StackBlitz WebContainer (Active) · E2B Cloud Sandbox (Ready) · LiteLLM Fast Router      |
+-------------------------------------------------------------------------------------------------------------+
```

---

## Core Capabilities

### 1. Interactive Visual Canvas
- **Client-Side WebContainers**: Boots full-stack Node.js, Vite, React 19, and Tailwind CSS environments inside the browser in under 2 seconds. Zero remote server compute required for frontend rendering.
- **Click-to-Inspect DOM Targeting**: Click any UI element in the live preview to inspect its tag, class hierarchy, and text content. Automatically attaches the CSS selector and context directly into the agent copilot prompt.
- **Responsive Viewport Controls**: 1-click preview presets for Desktop (100%), Tablet (768px), and Mobile (375px) with automatic iframe scale stabilization.
- **Pre-Warmed Project Starter Generator**: Instant generation of modern React + Vite + Tailwind starter projects ready for immediate editing and preview.

### 2. Pro Terminal & Cloud Sandboxes
- **Interactive xterm.js PTY**: Collapsible bottom drawer (`Ctrl + \``) powered by `@xterm/xterm` and `FitAddon`, streaming bidirectional stdin/stdout over WebSockets.
- **Remote Ephemeral MicroVMs**: Offload shell commands, package installations, and builds to isolated E2B Firecracker microVMs without requiring a local Docker daemon or root privileges.
- **Playwright Visual QA**: Automated headless Chromium browser captures (`progress.png`) inside microVMs to visually verify UI modifications before committing.
- **Live Process Telemetry**: Real-time streaming logs for background build pipelines, dev servers, and tool executions.

### 3. Multi-Agent Reasoning Engine
- **LangGraph State-Machine**: Orchestrates specialized agent nodes including `router`, `planner`, `call_model`, `tools`, `recovery`, `verify`, and `human_approval`.
- **Specialized Open-Source Agent Roles**:
  - **Planner / Architect**: `deepseek/deepseek-r1` for deep chain-of-thought system planning and multi-step decomposition.
  - **Executor / Coder**: `qwen/qwen-2.5-coder-32b-instruct` for syntax-accurate multi-file edits and tool execution.
  - **Self-Healing Recovery**: `deepseek/deepseek-r1` for diagnosing tracebacks, test failures, and compiler errors.
  - **Summarizer**: `meta-llama/llama-3.3-70b-instruct` for high-fidelity context compaction.
  - **Evaluator**: `qwen/qwen-2.5-coder-32b-instruct` for code review and verification.
- **Universal Fast Router**: Sub-350ms Time-to-First-Token (TTFT) via LiteLLM routing to Google's Gemini 3.8 Flash (1M context window) with automatic failover across leading open-source models.
- **Self-Healing Loop**: Traps non-zero exit codes, compiler errors, and test failures to automatically inject targeted recovery instructions into executor turns.

### 4. Patch Review & Version Snapshots
- **Two-Phase Diff Review**: Every agent code edit is staged as an inspectable unified diff with per-file and per-hunk accept/reject controls before committing to disk.
- **Automatic Checkpoint Snapshots**: Every agent turn automatically captures a workspace snapshot. Users can restore prior states with 1 click using the `↺ Revert turn` chip.
- **GitHub Integration**: Connect via OAuth or Personal Access Token (PAT) to clone remote repositories, manage branches, commit changes, and publish pull requests.

---

## Working Paths & Quickstart

### Prerequisites
- **Python 3.12+** and [`uv`](https://docs.astral.sh/uv/)
- **Node.js 20+** and [`pnpm`](https://pnpm.io/)
- **PostgreSQL 15+** (or SQLite for local development)

### 1. Backend Setup
```powershell
# Install Python dependencies
uv sync --frozen --all-groups

# Configure environment variables
Copy-Item .env.example .env

# Set required database URI and secrets
$env:DB_URI = "postgresql://compass_user:compass_password@localhost:5432/compass_db"
$env:JWT_SECRET = "compass-development-secret-key-32-chars-minimum"
$env:OPENROUTER_API_KEY = "<your-key>"  # or GOOGLE_API_KEY for Gemini 3.8 Flash

# Run database migrations and start backend server
alembic upgrade head
uv run uvicorn backend.main:app --reload --port 8000
```

### 2. Frontend Setup
In a second terminal:
```powershell
Set-Location frontend
pnpm install
pnpm run dev
```

Open [http://localhost:5173](http://localhost:5173). The frontend uses the same-origin `/api` base by default. Vite development proxies `/api` HTTP and WebSocket traffic to `http://localhost:8000`; the built Nginx image proxies the same prefix to the backend. Set `VITE_API_URL` only when the UI must use a different public API origin or base path.

`GET /health` is cheap process liveness. `GET /ready` checks the database, durable checkpointer, and workspace storage as required dependencies; memory, embeddings, and MCP are reported as optional capabilities. Readiness probes are bounded and cached.

---

## Product Capabilities

| Capability | Compass Web Workbench |
| --- | --- |
| **Conversation Modes** | `Ask` (Read-only), `Edit` (Direct mutations), `Plan` (Approval-gated), `Goal` (Autonomous) |
| **Visual Canvas** | In-browser WebContainer live preview with React 19 + Tailwind starter templates |
| **Click-to-Inspect** | DOM Inspector with targeting HUD and element selector prompt injection |
| **Interactive Terminal** | xterm.js PTY via bidirectional WebSocket (`/{workspace_id}/terminal`) |
| **Remote Sandboxes** | E2B Firecracker microVMs with Playwright visual QA ($0 cost free tier) |
| **Fast Router** | LiteLLM routing with sub-350ms TTFT (Gemini 3.8 Flash default) |
| **Open Source Models** | Native support for DeepSeek-R1, Qwen 2.5 Coder 32B, Llama 3.3, and Codestral |
| **Checkpoints & Revert** | Recoverable pre-turn snapshots with 1-click turn rollback (`↺ Revert turn`) |
| **GitHub Delivery** | Repository import, branch management, commit generation, and PR creation |
| **Self-Healing Loop** | Automatic detection of compiler errors, test failures, and tracebacks |

Provider use is BYOK: users or operators supply credentials for the selected model provider. Access tokens stay in browser memory. The refresh token is a rotating, single-use HttpOnly cookie scoped to `/api/auth`; refresh rotation and logout revoke the previous refresh generation. Stored web provider credentials and GitHub PATs use `CREDENTIAL_ENCRYPTION_KEY`.

Embedding capability is separate from chat-model capability. Configure both `EMBEDDING_PROVIDER` and `EMBEDDING_MODEL`, plus the relevant user/provider credential, before expecting semantic memory or retrieval. Missing embeddings are reported as unavailable rather than making the whole service unready.

---

## Configuration Reference

Backend settings are read from the environment, `.env`, or `backend/.env`.

| Variable | Requirement and Effect |
| --- | --- |
| `DB_URI` | Database connection URI (PostgreSQL or SQLite supported with multi-dialect schema guards). |
| `COMPASS_CLOUD_MODE` | Set `true` for hosted execution; restricts local process execution to E2B sandboxes. |
| `JWT_SECRET` | Secret key used to sign access and refresh tokens. |
| `CREDENTIAL_ENCRYPTION_KEY` | Fernet key for encrypting provider API keys and GitHub PATs at rest. |
| `SECURE_COOKIES` | Set `true` in production behind HTTPS. |
| `CORS_ORIGINS` | Comma-separated list of allowed browser origins. |
| `WORKSPACE_ROOT` | Server directory where user workspaces and project files are stored. |
| `SKILLS_ROOT` | Directory for global and user-authored skills. |
| `DEFAULT_PROVIDER`, `DEFAULT_MODEL` | Defaults used before a user configures BYOK settings (defaults to `qwen/qwen-2.5-coder-32b-instruct`). |
| `EMBEDDING_PROVIDER`, `EMBEDDING_MODEL` | Optional semantic retrieval and project memory configuration. |
| `MCP_SERVERS_FILE` | Optional server-side MCP configuration path. |
| `JWT_ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES`, `REFRESH_TOKEN_EXPIRE_DAYS` | Token algorithm and expiration settings. |
| `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET` | Optional Google OAuth credentials. |
| `GITHUB_CLIENT_ID`, `GITHUB_CLIENT_SECRET` | Optional GitHub OAuth credentials for repository import and export. |
| `OPENROUTER_API_KEY`, `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GOOGLE_API_KEY`, `GROQ_API_KEY` | Provider API keys consumed by the runtime router. |
| `E2B_API_KEY` | Optional E2B Cloud Sandbox API key (free tier available at e2b.dev). |
| `COMPASS_FAST_MODEL` | Override default fast router model (defaults to `gemini/gemini-3.8-flash`). |
| `TAVILY_API_KEY` | Optional web search API key for autonomous research. |
| `COMPASS_REDIS_URL` | Optional Redis URL for LLM response caching. |
| `VITE_API_URL` | Public frontend API base URL; defaults to `/api`. |

The compaction router reads `context.summarize_after`; its built-in default is `10` messages. It compacts only after the message count exceeds that threshold and no tool calls are pending.

---

## Runtime & Safety Model

Compass executes all agent reasoning through an instrumented LangGraph executor spine (`agent/graph/workflow.py`).

1. **State-Driven Workflow**: Transitions smoothly between `router`, `planner`, `call_model`, `tools`, `recovery`, and `human_approval`.
2. **Explicit Interrupts**: Critical actions, code modifications in `Plan` mode, and high-risk terminal commands trigger explicit LangGraph interrupts requiring user confirmation.
3. **Workspace Isolation**: Workspaces are isolated per-session. Path traversal and unauthorized access outside the designated project directory are strictly blocked.
4. **Soft Deletion & Snapshots**: Every agent turn automatically creates a snapshot checkpoint, allowing immediate 1-click rollback via the UI or API.

---

## Web API Reference

The interactive OpenAPI schema is available at `/docs`. Primary endpoints include:

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

---

## Verification & Test Suite

Compass enforces strict automated verification across both backend and frontend:

```powershell
# 1. Full Backend Test Suite (315+ tests)
uv run --no-sync python -m unittest discover -s tests

# 2. Frontend Unit & Accessibility Tests (52 tests across 19 suites)
pnpm --prefix frontend test -- --run

# 3. Frontend Production Build & Typecheck
pnpm --prefix frontend run build

# 4. Multi-Scope Release Gate
uv run --no-sync python tools/verify.py --scope all
```

---

## Project Documents

- [Deployment Guide](DEPLOYMENT.md)
- [Architecture Reference](docs/COMPASS_ARCHITECTURE.md)
- [Generated LangGraph Workflow](langgraph_workflow.md)
