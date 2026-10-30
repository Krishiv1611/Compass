# Compass Premium SaaS Studio: Comprehensive Architecture & UI/UX Specification

**Date:** 2026-10-31  
**Status:** Approved via Interactive Alignment  
**Target:** Transform Compass into a luxury, commercial-grade autonomous developer platform (Devin + Lovable hybrid) with 0% mockness, directly backed by the FastAPI backend and local subprocess sandbox.

---

## 1. Executive Summary & Design Vision

Compass blends the visual velocity of **Lovable** (live visual Canvas, Click-to-Inspect DOM element selection, instant hot-reloading) with the deep autonomous power of **Devin** (multi-file editing, real local subprocess shell execution, git commits/checkpoints, WebSocket terminal drawer, patch review).

Every single button, badge, and input in the frontend directly connects to real backend APIs (`/workspaces`, `/sessions`, `/patches`, `/checkpoints`, `/runs`, `/tools`, `/settings`, `/chat`). Zero mock data, zero placeholder cards, and zero decorative statistics.

---

## 2. Component Specifications

### 2.1 Center Workbench: Adaptive Hybrid Studio
- **File:** `frontend/src/components/workbench/CenterWorkbench.tsx`
- **Tabs:**
  1. `Canvas` (Lovable): Real-time sandboxed preview of the web project with `DOM_INSPECTOR_SCRIPT` for click-to-inspect DOM element selection. Attaches `<tag selector="..." classes="..." text="...">` directly to the chat prompt.
  2. `Editor` (Devin): Full-featured CodeMirror editor equipped with a persistent **Multi-File Tab Bar** (`EditorTabBar.tsx`). Each tab features language glyphs, dirty state indicator dots (`*`), and close buttons (`x`). Supports `Ctrl+S` saving and `Ctrl+W` tab closing.
  3. `Changes` (Devin): Staged git diff review powered by real patches from `patchesApi.getPatches()`, with line-by-line hunk acceptance or rejection.
  4. `Snapshots` (Devin): Rollback timeline powered by real git commit checkpoints from `checkpointsApi.listCheckpoints()`.
- **Bottom Drawer (`ProDrawer.tsx`)**:
  - Instant slide-up terminal connected via real WebSocket relay to the workspace folder (`/ws/workspaces/{workspace_id}/terminal`).

### 2.2 IDE File Explorer with Language Glyphs & Git Indicators
- **Files:** `frontend/src/lib/fileIcons.tsx`, `frontend/src/components/sandbox/FileExplorer.tsx`
- **Features:**
  - Color-coded language glyphs: TypeScript (blue), JavaScript (yellow), Python (blue/yellow), CSS/HTML (orange/cyan), JSON (amber), Markdown (teal), Shell/Git (purple).
  - Git status indicators: `M` (yellow modified), `U` (emerald untracked/new), `D` (crimson deleted).
  - Compact 28px tree row density with hairline vertical indent guidelines.
  - Hover action strip: Create File, Create Folder, Delete, Add to AI Context (`Link2`).

### 2.3 Conversational Feed & Tool Execution Cards
- **Files:** `frontend/src/components/chat/MessageRow.tsx`, `frontend/src/components/chat/ToolCallCard.tsx`
- **Features:**
  - **User Messages**: Sleek elevated card container with subtle surface highlight (`#131822`), distinct user badge, attached context chips (files, inspected DOM elements), and resend action on hover.
  - **Assistant Messages**: Agent header with model pill (`Compass Brain / DeepSeek-R1`), turn duration, token speed telemetry, and 1-click turn revert (`RotateCcw`).
  - **ToolCallCard**:
    - Interactive execution cards: File tools (`read_file`, `write_file`, `edit_file`) with file icon and path; Shell tools (`execute_command`) with terminal prompt and exit code badge (`exit 0` emerald, `exit 1` crimson).
    - Expandable output disclosure with formatted diffs and 1-click "Copy Output".

### 2.4 Workspace Landing: Mission Control Dashboard
- **File:** `frontend/src/components/sandbox/WorkspaceLanding.tsx`
- **Features:**
  - **Fast Action Command Bar**: Top action strip with quick buttons:
    - `[Ctrl+N] New Autonomous Task` (creates real session)
    - `Clone GitHub Repository` (opens real GitHub import dialog)
    - `Open Local Directory` (native folder upload via `workspaceApi.uploadFolder`)
  - **Active Workspaces Hub**: Replaces tutorial template cards with a table/grid of real workspaces listing active git branches, last agent commit timestamps, and quick 1-click launch buttons.
  - **Telemetry HUD**: Live status of LLM Router connectivity, Active model Context window, and Host Subprocess sandbox readiness.

---

## 3. Framer Motion Interaction Specifications

- **Tab Sliders**: `<motion.div layoutId="..." transition={{ type: "spring", stiffness: 450, damping: 32 }} />`
- **Drawer Slide**: `<motion.div initial={{ height: 0, opacity: 0 }} animate={{ height: open ? targetHeight : 0, opacity: 1 }} exit={{ height: 0, opacity: 0 }} transition={{ type: "spring", stiffness: 350, damping: 30 }} />`
- **Hover Micro-Interactions**: `whileHover={{ y: -2, scale: 1.01 }} whileTap={{ scale: 0.98 }}` with subtle box-shadow glow.
- **Accordion Toggles**: `<AnimatePresence>` wrapping collapsible sections with height animation `animate={{ height: "auto" }}`.
- **Accessibility**: Automatic fallback for `prefers-reduced-motion: reduce`.

---

## 4. Test & Quality Matrix

- All existing 19 frontend test suites (56 tests) must pass without regressions.
- New unit tests for multi-tab editor state, file icon resolution, and tool call card expand/collapse.
- Clean production build: `tsc -b && vite build` in < 2.0s with 0 errors.
- 100% backend unit and regression test pass rate (326 tests).
