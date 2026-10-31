# Compass Premium SaaS Phase 2: Control Plane & Luxury Auth Surface

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete the transition of Compass into a world-class autonomous developer SaaS by elevating the Settings Control Plane (live LLM latency probe and tool capability explorer) and transforming the Login surface into a luxury split-screen experience with architectural telemetry.

**Architecture:** Directly backed by existing FastAPI routes (`/settings/provider-test`, `/tools`, `/auth`). Zero mockness, real token handshake latency measurements, and 100% test coverage.

**Tech Stack:** React 19/18, TypeScript, Tailwind CSS v4, Framer Motion v12, Lucide Icons, Vitest, FastAPI, LiteLLM.

**Spec:** [`docs/superpowers/specs/2026-10-31-premium-saas-studio-architecture-spec.md`](file:///d:/projects/compass/docs/superpowers/specs/2026-10-31-premium-saas-studio-architecture-spec.md)

## Global Constraints

- Preserve all existing comments and docstrings unrelated to changed logic.
- Do NOT introduce competitor brand names ("Lovable", "Devin") or fake marketing claims (`< 350ms`, `Ready in 2s`).
- All animations must respect `prefers-reduced-motion` and use hardware-accelerated transforms (`x`, `y`, `scale`, `opacity`).
- Maintain 100% pass rate across existing unit tests.

---

### Task 1: Split-Screen Luxury Login & Architecture Showcase

**Files:**
- Modify: `frontend/src/pages/LoginPage.tsx`
- Modify: `frontend/src/components/auth/AuthSurface.tsx`
- Create: `frontend/src/pages/LoginPage.test.tsx`

**Interfaces:**
- Consumes: `useAuth`, `authApi.getGithubAuthUrl`, `authApi.getGoogleAuthUrl`
- Produces: Responsive split-screen login page with left-side architecture telemetry showcase (agent state machine, runner status, feature highlights) and right-side elevated obsidian glass `AuthSurface`.

- [x] **Step 1: Write unit tests in `frontend/src/pages/LoginPage.test.tsx`**
- [x] **Step 2: Update `AuthSurface.tsx` with luxury obsidian glass styling and Framer Motion tab slider**
- [x] **Step 3: Redesign `LoginPage.tsx` into the split-screen luxury architecture showcase**
- [x] **Step 4: Run tests and verify: `npm --prefix frontend run test -- --run src/pages/LoginPage.test.tsx`**
- [x] **Step 5: Commit**

---

### Task 2: Enterprise Model Control Plane with Real Latency Ping

**Files:**
- Modify: `frontend/src/components/settings/SettingsModal.tsx`
- Create: `frontend/src/components/settings/SettingsModal.test.tsx`

**Interfaces:**
- Consumes: `preferencesApi.testProvider`, `ProviderTestResponse` (`latency_ms`, `success`, `error`)
- Produces: Interactive "Test Connection & Ping" button, animated latency badge (`134.2ms · Operational` with emerald glow), model capability tags, and transparent error feedback.

- [x] **Step 1: Write unit tests in `frontend/src/components/settings/SettingsModal.test.tsx`**
- [x] **Step 2: Update `SettingsModal.tsx` to display real `ProviderTestResponse` latency badges and capability tags**
- [x] **Step 3: Run tests and verify: `npm --prefix frontend run test -- --run src/components/settings/SettingsModal.test.tsx`**
- [x] **Step 4: Commit**

---

### Task 3: MCP & Agent Tool Capability Inspector

**Files:**
- Modify: `frontend/src/components/settings/McpServerManager.tsx`
- Create: `frontend/src/components/settings/McpServerManager.test.tsx`

**Interfaces:**
- Consumes: `toolsApi.listTools` (`/tools`), `mcpApi.getMcpServers`
- Produces: Real agent capability catalog with tool category glyphs, environment tags (Web / Host), and safety indicators.

- [x] **Step 1: Write unit tests in `frontend/src/components/settings/McpServerManager.test.tsx`**
- [x] **Step 2: Update `McpServerManager.tsx` to list active agent capabilities and tools**
- [x] **Step 3: Run tests and verify: `npm --prefix frontend run test -- --run src/components/settings/McpServerManager.test.tsx`**
- [x] **Step 4: Commit**

---

### Task 4: Full Quality Gates & Production Build

- [x] **Step 1: Run all frontend unit tests (`npm --prefix frontend run test -- --run`)**
- [x] **Step 2: Run frontend production build (`npm --prefix frontend run build`)**
- [x] **Step 3: Run backend unit test discovery (`uv run --no-sync python -m unittest discover tests`)**
- [x] **Step 4: Multi-file git review, commit, and push to origin/main**
