# Compass Premium SaaS Studio Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Transform Compass into an elite, commercial-grade autonomous developer platform (Devin + Lovable hybrid) with 0% mockness, directly backed by the FastAPI backend and local subprocess sandbox.

**Architecture:** Maintain existing FastAPI backend and React 19/Vite workbench architecture. Replace basic file explorer and single-file editor state with a multi-tab developer cockpit; elevate the chat transcript into a studio feed with interactive tool cards and telemetry; replace tutorial template cards on the landing page with an active Workspaces Hub and fast action bar; ensure real dual-telemetry sync between live Canvas and CodeMirror editor.

**Tech Stack:** React 19/18, TypeScript, Tailwind CSS v4, Framer Motion v12, Lucide Icons, Allotment, CodeMirror, Vitest, `@webcontainer/api`, FastAPI, LiteLLM.

**Spec:** [`docs/superpowers/specs/2026-10-31-premium-saas-studio-architecture-spec.md`](file:///d:/projects/compass/docs/superpowers/specs/2026-10-31-premium-saas-studio-architecture-spec.md)

## Global Constraints

- Preserve all existing comments and docstrings unrelated to changed logic.
- Do NOT introduce competitor brand names ("Lovable", "Devin") or fake marketing claims (`< 350ms`, `Ready in 2s`).
- All animations must respect `prefers-reduced-motion` and use hardware-accelerated transforms (`x`, `y`, `scale`, `opacity`).
- Maintain 100% pass rate across existing unit tests.

---

### Task 1: IDE File Explorer with Language Glyphs & Git Indicators

**Files:**
- Create: `frontend/src/lib/fileIcons.tsx`
- Modify: `frontend/src/components/sandbox/FileExplorer.tsx`
- Test: `frontend/src/components/sandbox/FileExplorer.test.tsx`

**Interfaces:**
- Consumes: `FileNode`, `WorkbenchContext`
- Produces: `getFileIcon(name: string, isFolder?: boolean, isOpen?: boolean) -> ReactNode`, compact 28px tree with git status badges and hover action bar.

- [ ] **Step 1: Write unit tests for File Explorer and file icon resolution**
- [ ] **Step 2: Implement `fileIcons.tsx` with color-coded language glyphs**
- [ ] **Step 3: Update `FileExplorer.tsx` with compact IDE tree, indent guidelines, and git badges**
- [ ] **Step 4: Run tests and verify: `npm --prefix frontend run test -- --run src/components/sandbox/FileExplorer.test.tsx`**
- [ ] **Step 5: Commit**

---

### Task 2: Multi-Tab Editor Bar & Fuzzy File Navigation

**Files:**
- Create: `frontend/src/components/workbench/EditorTabBar.tsx`
- Modify: `frontend/src/components/workbench/CenterWorkbench.tsx`
- Modify: `frontend/src/contexts/WorkbenchContext.tsx`
- Test: `frontend/src/components/workbench/EditorTabBar.test.tsx`

**Interfaces:**
- Consumes: `WorkbenchContext` (`openFiles`, `activeFile`, `closeFile`, `openFile`)
- Produces: Framer Motion animated multi-tab strip with `layoutId="activeEditorTab"`, dirty dot indicators, `Ctrl+W` tab closing.

- [ ] **Step 1: Write unit tests for EditorTabBar and multi-tab state transitions**
- [ ] **Step 2: Implement `EditorTabBar.tsx` with Framer Motion spring physics**
- [ ] **Step 3: Integrate `EditorTabBar` into `CenterWorkbench.tsx` with keyboard shortcuts**
- [ ] **Step 4: Run tests and verify: `npm --prefix frontend run test -- --run src/components/workbench/EditorTabBar.test.tsx`**
- [ ] **Step 5: Commit**

---

### Task 3: Studio Conversational Stream & Rich Tool Execution Cards

**Files:**
- Modify: `frontend/src/components/chat/MessageRow.tsx`
- Modify: `frontend/src/components/chat/ToolCallCard.tsx`
- Modify: `frontend/src/components/chat/MessageList.tsx`
- Test: `frontend/src/components/chat/ToolCallCard.test.tsx`

**Interfaces:**
- Consumes: `TranscriptMessage`, `ToolCallCardProps`
- Produces: Elevated user prompt cards, structured assistant cards with model telemetry, and interactive expandable tool execution cards with duration badges and formatted diffs.

- [ ] **Step 1: Write unit tests for rich ToolCallCard interactions**
- [ ] **Step 2: Redesign `ToolCallCard.tsx` with tool-specific glyphs, status badges, and expandable logs**
- [ ] **Step 3: Elevate `MessageRow.tsx` with distinct user/assistant card hierarchy and action toolbar**
- [ ] **Step 4: Run tests and verify: `npm --prefix frontend run test -- --run src/components/chat/ToolCallCard.test.tsx`**
- [ ] **Step 5: Commit**

---

### Task 4: Mission Control Workspace Landing Hub

**Files:**
- Modify: `frontend/src/components/sandbox/WorkspaceLanding.tsx`
- Test: `frontend/src/components/sandbox/workspaceTransitions.test.ts`

**Interfaces:**
- Consumes: `workspaceApi.listWorkspaces`, `ensureSession`, `onWorkspaceReady`
- Produces: Fast Action Command Bar (`New Task`, `Clone GitHub`, `Open Local Directory`), Active Workspaces Hub with live git branches and agent status, and Telemetry HUD.

- [ ] **Step 1: Update unit tests for WorkspaceLanding**
- [ ] **Step 2: Implement Mission Control Dashboard in `WorkspaceLanding.tsx`**
- [ ] **Step 3: Run tests and verify: `npm --prefix frontend run test -- --run src/components/sandbox/workspaceTransitions.test.ts`**
- [ ] **Step 4: Commit**

---

### Task 5: Dual-Telemetry Sync & Full Quality Gates

- [ ] **Step 1: Verify dual-telemetry sync between Canvas and Editor upon agent completion**
- [ ] **Step 2: Run all frontend unit tests (`npm --prefix frontend run test -- --run`)**
- [ ] **Step 3: Run frontend production build (`npm --prefix frontend run build`)**
- [ ] **Step 4: Run backend unit test discovery (`uv run --no-sync python -m unittest discover tests`)**
- [ ] **Step 5: Multi-file git review, commit, and push to origin/main**
