# Compass frontend

React 19, TypeScript, Vite, Tailwind CSS, Base UI, CodeMirror, and WebContainers power the Compass coding workbench.

## Setup

```bash
npm install
npm run dev
```

The development server proxies `/api` and the chat WebSocket to the backend. Copy `.env.example` to `.env` only when an environment-specific public URL is required; never place secrets in Vite variables.

## Architecture

- `src/pages` owns route-level composition.
- `src/contexts` owns authentication, run streaming, and shared workbench state.
- `src/api` contains typed domain clients backed by one HTTP client.
- `src/components/workbench` contains the agent/editor/review shell.
- `src/components/settings` contains preferences and status-only advanced surfaces.

IBM Plex Sans and JetBrains Mono are bundled locally through Fontsource. Theme and semantic UI tokens live in `src/index.css`.

## Verification

```bash
npm run lint
npm run build
```

Manual QA must cover desktop and mobile sizes, light and dark themes, keyboard-only navigation, reduced motion, slow/offline states, long content, GitHub capability states, and the browser console. Progress and results are tracked in `../COMPASS_IMPLEMENTATION_STATUS.md`.
