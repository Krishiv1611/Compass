# Compass Deployment

## Production mode

Set `COMPASS_CLOUD_MODE=true` for hosted deployments. In cloud mode, configure an isolated workspace root, database URL, JWT secret, OAuth credentials, and model provider keys through environment variables rather than local config files.

## Required environment

- `DB_URI`: production Postgres connection string.
- `JWT_SECRET`: long random secret for access and refresh tokens.
- `COMPASS_CLOUD_MODE=true`: enables hosted assumptions and avoids local-only workflows.
- `OPENROUTER_API_KEY` or provider-specific model credentials.
- `GOOGLE_CLIENT_ID` / `GOOGLE_CLIENT_SECRET` and GitHub OAuth values if OAuth login is enabled.
- `CORS_ORIGINS`: comma-separated frontend origins.

## Runtime setup

Run database migrations before starting the API. Serve the built frontend from a static host or reverse proxy, and proxy `/chat/ws/*` with WebSocket upgrade enabled. Keep workspaces on a private volume, never inside the public frontend directory.

## Security checklist

Use HTTPS, rotate JWT secrets on compromise, keep refresh tokens in request bodies, enforce workspace path checks, and run the backend with a non-admin OS user. Back up Postgres and workspace storage separately.
