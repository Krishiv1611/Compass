import os
import uuid
from pathlib import Path

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from agent.workspace import discover_local_workspace
from backend.config import settings
from backend.models.session import ChatSession
from backend.models.workspace import Workspace
from backend.services.ownership import owned_session, owned_workspace


def create_workspace_record(db: Session, user_id: str, session_id: str, name: str) -> Workspace:
    """Create a new Workspace record and initialize its directory.

    Pre-generates UUID so storage_path can be set before the first commit,
    avoiding a two-commit sequence that leaves the record temporarily path-less.
    """
    workspace_id = str(uuid.uuid4())
    workspace_dir = Path(settings.workspace_root) / user_id / workspace_id
    workspace_dir.mkdir(parents=True, exist_ok=True)

    workspace = Workspace(
        id=workspace_id,
        user_id=user_id,
        session_id=session_id,
        name=name,
        source_type="upload",
        status="uploading",
        storage_path=str(workspace_dir),
        project_id=f"workspace:{workspace_id}",
        context_version="content:empty",
    )
    db.add(workspace)
    db.commit()
    db.refresh(workspace)
    return workspace


def seed_starter_template(workspace_dir: Path, name: str) -> None:
    """Seed a modern React + Vite + Tailwind starter template into a fresh workspace."""
    import json
    package_json = {
        "name": (name.lower().replace(" ", "-") or "compass-app"),
        "private": True,
        "version": "0.1.0",
        "type": "module",
        "scripts": {
            "dev": "vite",
            "build": "vite build",
            "preview": "vite preview"
        },
        "dependencies": {
            "react": "^18.3.1",
            "react-dom": "^18.3.1",
            "lucide-react": "^0.460.0"
        },
        "devDependencies": {
            "@vitejs/plugin-react": "^4.3.4",
            "autoprefixer": "^10.4.20",
            "postcss": "^8.4.49",
            "tailwindcss": "^3.4.15",
            "vite": "^5.4.11"
        }
    }
    (workspace_dir / "package.json").write_text(json.dumps(package_json, indent=2), encoding="utf-8")
    (workspace_dir / "vite.config.ts").write_text(
        "import { defineConfig } from 'vite';\nimport react from '@vitejs/plugin-react';\n\nexport default defineConfig({\n  plugins: [react()],\n});\n",
        encoding="utf-8",
    )
    (workspace_dir / "tailwind.config.js").write_text(
        "/** @type {import('tailwindcss').Config} */\nexport default {\n  content: ['./index.html', './src/**/*.{js,ts,jsx,tsx}'],\n  theme: { extend: {} },\n  plugins: [],\n};\n",
        encoding="utf-8",
    )
    (workspace_dir / "postcss.config.js").write_text(
        "export default {\n  plugins: { tailwindcss: {}, autoprefixer: {} },\n};\n",
        encoding="utf-8",
    )
    (workspace_dir / "index.html").write_text(
        "<!doctype html>\n<html lang=\"en\">\n  <head>\n    <meta charset=\"UTF-8\" />\n    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\" />\n"
        f"    <title>{name}</title>\n  </head>\n  <body class=\"bg-slate-950 text-slate-100 min-h-screen selection:bg-indigo-500 selection:text-white\">\n    <div id=\"root\"></div>\n    <script type=\"module\" src=\"/src/main.tsx\"></script>\n  </body>\n</html>\n",
        encoding="utf-8",
    )
    src_dir = workspace_dir / "src"
    src_dir.mkdir(parents=True, exist_ok=True)
    (src_dir / "main.tsx").write_text(
        "import React from 'react';\nimport ReactDOM from 'react-dom/client';\nimport App from './App';\nimport './index.css';\n\nReactDOM.createRoot(document.getElementById('root')!).render(\n  <React.StrictMode>\n    <App />\n  </React.StrictMode>,\n);\n",
        encoding="utf-8",
    )
    (src_dir / "index.css").write_text(
        "@tailwind base;\n@tailwind components;\n@tailwind utilities;\n",
        encoding="utf-8",
    )
    (src_dir / "App.tsx").write_text(
        "import React, { useState } from 'react';\nimport { Sparkles, ArrowRight, Layers, Zap, Palette, CheckCircle2 } from 'lucide-react';\n\n"
        "export default function App() {\n  const [count, setCount] = useState(0);\n\n  return (\n"
        "    <div className=\"min-h-screen bg-gradient-to-b from-slate-950 via-slate-900 to-slate-950 text-white flex flex-col justify-between p-6 sm:p-12 font-sans\">\n"
        "      <header className=\"max-w-5xl mx-auto w-full flex items-center justify-between py-4\">\n"
        f"        <div className=\"flex items-center gap-2 font-bold text-lg tracking-tight\">\n"
        f"          <span className=\"h-8 w-8 rounded-lg bg-indigo-600 flex items-center justify-center text-white shadow-lg shadow-indigo-500/20\">\n"
        f"            <Sparkles className=\"h-4 w-4\" />\n          </span>\n          <span>{name}</span>\n        </div>\n"
        "        <nav className=\"flex items-center gap-4 text-sm text-slate-400\">\n          <a href=\"#features\" className=\"hover:text-white transition-colors\">Features</a>\n"
        "          <button onClick={() => setCount(c => c + 1)} className=\"px-3 py-1.5 rounded-full bg-slate-800 hover:bg-slate-700 text-xs font-medium text-slate-200 border border-slate-700 transition-colors\">\n"
        "            Clicks: {count}\n          </button>\n        </nav>\n      </header>\n\n"
        "      <main className=\"max-w-5xl mx-auto w-full my-auto py-12 flex flex-col items-center text-center\">\n"
        "        <div className=\"inline-flex items-center gap-2 px-3 py-1 rounded-full bg-indigo-500/10 border border-indigo-500/20 text-indigo-400 text-xs font-medium mb-6\">\n"
        "          <Zap className=\"h-3.5 w-3.5\" /> Live WebContainer Ready\n        </div>\n"
        f"        <h1 className=\"text-4xl sm:text-6xl font-extrabold tracking-tight max-w-2xl bg-gradient-to-r from-white via-slate-200 to-indigo-200 bg-clip-text text-transparent\">\n"
        f"          Build something remarkable with {name}\n        </h1>\n"
        "        <p className=\"mt-4 max-w-xl text-base sm:text-lg text-slate-400 leading-relaxed\">\n"
        "          Click any element using the Inspect tool or ask Compass in the chat to transform this app in real time.\n        </p>\n"
        "        <div className=\"mt-8 flex flex-wrap items-center justify-center gap-3\">\n"
        "          <button className=\"px-6 py-3 rounded-xl bg-indigo-600 hover:bg-indigo-500 text-white font-semibold text-sm shadow-xl shadow-indigo-600/30 transition-all flex items-center gap-2 group\">\n"
        "            Get Started <ArrowRight className=\"h-4 w-4 group-hover:translate-x-0.5 transition-transform\" />\n          </button>\n"
        "        </div>\n\n"
        "        <div className=\"grid grid-cols-1 sm:grid-cols-3 gap-4 mt-16 w-full text-left\">\n"
        "          <div className=\"p-5 rounded-2xl bg-slate-900/60 border border-slate-800/80 hover:border-indigo-500/40 transition-colors\">\n"
        "            <Layers className=\"h-5 w-5 text-indigo-400 mb-3\" />\n"
        "            <h3 className=\"font-semibold text-sm text-slate-200\">Instant HMR</h3>\n"
        "            <p className=\"text-xs text-slate-400 mt-1\">Lightning fast Vite compilation running directly in your browser.</p>\n          </div>\n"
        "          <div className=\"p-5 rounded-2xl bg-slate-900/60 border border-slate-800/80 hover:border-indigo-500/40 transition-colors\">\n"
        "            <Palette className=\"h-5 w-5 text-emerald-400 mb-3\" />\n"
        "            <h3 className=\"font-semibold text-sm text-slate-200\">Tailwind CSS</h3>\n"
        "            <p className=\"text-xs text-slate-400 mt-1\">Utility-first styling with modern dark theme and fluid typography.</p>\n          </div>\n"
        "          <div className=\"p-5 rounded-2xl bg-slate-900/60 border border-slate-800/80 hover:border-indigo-500/40 transition-colors\">\n"
        "            <CheckCircle2 className=\"h-5 w-5 text-blue-400 mb-3\" />\n"
        "            <h3 className=\"font-semibold text-sm text-slate-200\">Click-to-Inspect</h3>\n"
        "            <p className=\"text-xs text-slate-400 mt-1\">Select any component on screen to focus your next AI prompt instantly.</p>\n          </div>\n"
        "        </div>\n      </main>\n\n"
        "      <footer className=\"max-w-5xl mx-auto w-full py-4 text-center text-xs text-slate-500 border-t border-slate-900\">\n"
        "        Powered by Compass Hybrid Workbench\n      </footer>\n    </div>\n  );\n}\n",
        encoding="utf-8",
    )


def get_workspace(db: Session, workspace_id: str, user_id: str) -> Workspace:
    """Get a workspace by ID, ensuring the user owns it."""
    return owned_workspace(db, workspace_id, user_id)


def get_workspace_by_session(db: Session, session_id: str, user_id: str) -> Workspace:
    """Return only the ready workspace explicitly selected for the session."""
    workspace = (
        db.query(Workspace)
        .join(ChatSession, ChatSession.active_workspace_id == Workspace.id)
        .filter(
            ChatSession.id == session_id,
            ChatSession.user_id == user_id,
            ChatSession.is_deleted.is_(False),
            Workspace.user_id == user_id,
            Workspace.session_id == session_id,
            Workspace.status == "ready",
        )
        .first()
    )
    
    if not workspace:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No ready active workspace is attached to this session",
        )
    return workspace


def _sync_session_context(session: ChatSession, workspace: Workspace) -> None:
    session.active_workspace_id = workspace.id
    session.project_id = workspace.project_id
    session.git_remote = workspace.git_remote
    session.git_branch = workspace.git_branch
    session.git_head = workspace.git_head
    session.context_version = workspace.context_version


def attach_active_workspace(
    db: Session,
    session_id: str,
    workspace_id: str,
    user_id: str,
) -> Workspace:
    """Attach one ready, owned workspace to its owned session."""
    session = owned_session(db, session_id, user_id)
    workspace = owned_workspace(db, workspace_id, user_id)
    if workspace.session_id != session.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Workspace not found for this session",
        )
    if workspace.status != "ready":
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Workspace is not ready",
        )

    _sync_session_context(session, workspace)
    db.commit()
    db.refresh(workspace)
    return workspace


def update_workspace_stats(db: Session, workspace: Workspace, sync_session: bool = True):
    """Update file count and size stats based on current directory contents."""
    path = Path(workspace.storage_path)
    if not path.exists():
        workspace.status = "error"
        db.commit()
        return

    count = 0
    size = 0
    for root, _, files in os.walk(path):
        for file in files:
            file_path = Path(root) / file
            relative_parts = file_path.relative_to(path).parts
            if (
                ".git" in relative_parts
                or "node_modules" in relative_parts
                or relative_parts[:2] == (".compass", "checkpoints")
            ):
                continue
            count += 1
            try:
                size += file_path.stat().st_size
            except OSError:
                pass
                
    workspace.file_count = count
    workspace.size_bytes = size
    identity = discover_local_workspace(path, allow_parent_git=False)
    if identity.git_head:
        workspace.git_head = identity.git_head
    workspace.context_version = identity.context_version
    if sync_session and workspace.session is not None:
        _sync_session_context(workspace.session, workspace)
    workspace.status = "ready"
    db.commit()
    db.refresh(workspace)
