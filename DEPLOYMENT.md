# Compass deployment

Compass currently supports a single backend process. The included Compose files are useful build/run references, but operators must supply the cloud security variables and run migrations before serving traffic. There is no distributed limiter, scheduler, retention worker, or multi-process coordination layer.

## Required production configuration

Set these values in the backend process (or an operator-owned Compose override/secrets mechanism):

| Variable | Production requirement |
| --- | --- |
| `DB_URI` | Reachable PostgreSQL connection. The web service has no SQLite fallback. |
| `COMPASS_CLOUD_MODE=true` | Enables hosted boundaries and cloud validation. |
| `JWT_SECRET` | Non-default random value of at least 32 characters. |
| `CREDENTIAL_ENCRYPTION_KEY` | Valid Fernet key, distinct from `JWT_SECRET`. |
| `SECURE_COOKIES=true` | Required by cloud validation; terminate HTTPS before the app. |
| `CORS_ORIGINS` | Exact comma-separated browser origins. Do not use a public wildcard with credentials. |
| `WORKSPACE_ROOT` | Private writable persistent volume for owned workspaces. |
| `SKILLS_ROOT` | Private skill root; web writes stay inside its isolated user area. |
| `DEFAULT_PROVIDER`, `DEFAULT_MODEL` | Fallback provider/model shown before user BYOK selection. |

Optional integrations use `EMBEDDING_PROVIDER`, `EMBEDDING_MODEL`, `MCP_SERVERS_FILE`, `GOOGLE_CLIENT_ID`, `GOOGLE_CLIENT_SECRET`, `GITHUB_CLIENT_ID`, and `GITHUB_CLIENT_SECRET`. Missing optional embeddings, memory, or MCP are reported as unavailable by readiness; missing required database, checkpointer, or workspace access returns 503.

Generate an encryption key without printing any other secrets:

```powershell
.\.venv\Scripts\python.exe -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

## Database and startup order

1. Provision PostgreSQL and private persistent workspace storage.
2. Install frozen dependencies with `uv sync --frozen --all-groups` and `npm ci`.
3. Export the backend settings above.
4. Run `alembic upgrade head` once for the release.
5. Start one backend process and the built frontend.
6. Route traffic only after `/health` returns 200 and `/ready` returns 200.

`/health` proves only that the API process can answer. `/ready` runs one-second-bounded component probes and caches the report for five seconds. Do not use liveness as a substitute for readiness.

## Reverse proxy

The built frontend Nginx configuration proxies the entire `/api/` prefix to FastAPI and preserves WebSocket Upgrade headers. This includes the live socket at `/api/chat/ws/<session-id>`. Do not proxy a separate `/chat/ws` path; it is not a registered public base.

Forward the original host and scheme, allow credentialed requests only from `CORS_ORIGINS`, and keep the backend off the public network when possible. The frontend's `VITE_API_URL` is a public URL/path only and must never contain credentials.

## Browser authentication

- The short-lived access token is held in browser memory and sent as a Bearer token for HTTP calls.
- The refresh token is a rotating, single-use HttpOnly cookie scoped to `/api/auth`.
- Refresh rotation increments the user's refresh generation before issuing the next cookie; replaying the old token fails.
- Logout increments the generation and clears the cookie.
- WebSockets authenticate with the `compass.v1` and `compass.jwt.<access-token>` subprotocol values. Access tokens are not query parameters.

Because refresh state is server-side and cookies are secure in cloud mode, HTTPS termination and stable secrets are mandatory. Rotating `JWT_SECRET` invalidates existing access and refresh tokens.

## Process-local bounds

Run exactly one backend worker. Per-user enforcement is process-local:

- five concurrent WebSockets;
- 64 KiB message content;
- two active runs;
- ten run starts per minute; and
- weighted HTTP rate buckets.

Starting additional workers multiplies the effective bounds. Add shared state and tests before changing this deployment assumption.

## Storage and deletion

Web sessions select one owned active workspace. Requests use a detached snapshot of that workspace, project, user preferences, and context version. A stale or mismatched context is rejected rather than silently running against another workspace.

Session deletion cancels active runs and closes session sockets before the 204 response, then performs a soft delete. It does not physically erase workspace files, uploads, semantic data, checkpoints, or related database records. Back up PostgreSQL and workspace storage separately, and define an operator-reviewed physical retention process.

## Release verification

From the repository root:

```powershell
.\.venv\Scripts\python.exe tools\verify.py --scope all
```

The command runs Python tests, frontend tests/typecheck/lint/build, both Compose configuration checks, documentation truth, and the Alembic single-head check. It reports command arrays, timeouts, durations, and exit codes. Run it twice for a release gate: once in the working checkout and once in a clean copied checkout after frozen bootstrap.

Automated verification does not replace the manual journey matrix: sign-up/login/refresh/logout, workspace create/upload/import/switch, Ask/Edit/Plan/Goal, approval/deny/resume, patch apply/reject/undo, reconnect/cancel/delete, mobile keyboard/accessibility, and GitHub publish/recovery.

## Production checklist

- HTTPS is enforced and `SECURE_COOKIES=true`.
- `JWT_SECRET` and `CREDENTIAL_ENCRYPTION_KEY` are strong and distinct.
- `/ready` is the traffic gate and `/health` is only the process probe.
- One backend worker is running.
- PostgreSQL migrations are at one Alembic head.
- PostgreSQL and workspace volumes are private and backed up.
- OAuth redirects and `CORS_ORIGINS` exactly match the public origin.
- Provider and GitHub credentials use least privilege.
- The backend runs as a non-administrator OS user.
- Physical retention and incident-response procedures are documented externally.
