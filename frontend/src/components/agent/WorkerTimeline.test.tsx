// @vitest-environment jsdom

import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { afterEach, describe, expect, it } from "vitest";

import WorkerTimeline, { FinalWalkthrough } from "./WorkerTimeline";
import type { RunWalkthroughArtifact, WorkerArtifact } from "@/types/artifact";

afterEach(cleanup);

const workers: WorkerArtifact[] = [
  {
    task_id: "backend",
    title: "Audit backend",
    status: "running",
    duration_ms: 128,
    evidence_count: 0,
  },
  {
    task_id: "web",
    title: "Audit web",
    status: "completed",
    duration_ms: 1_240,
    evidence_count: 3,
    summary: "Validated the streaming boundary.",
  },
];

describe("WorkerTimeline", () => {
  it("shows each worker's ownership, status, duration, and evidence count", () => {
    render(<WorkerTimeline workers={workers} />);

    expect(screen.getByRole("region", { name: "Worker activity" })).toBeTruthy();
    expect(screen.getByText("Audit backend")).toBeTruthy();
    expect(screen.getByText("Running")).toBeTruthy();
    expect(screen.getByText("128ms")).toBeTruthy();
    expect(screen.getByText("0 evidence")).toBeTruthy();
    expect(screen.getByText("Audit web")).toBeTruthy();
    expect(screen.getByText("Completed")).toBeTruthy();
    expect(screen.getByText("1.2s")).toBeTruthy();
    expect(screen.getByText("3 evidence")).toBeTruthy();
  });

  it("reveals a public worker summary only when requested", async () => {
    const user = userEvent.setup();
    render(<WorkerTimeline workers={workers} />);

    const disclosure = screen.getByRole("button", { name: "Show summary for Audit web" });
    expect(disclosure.getAttribute("aria-expanded")).toBe("false");
    expect(screen.queryByText("Validated the streaming boundary.")).toBeNull();
    expect(screen.queryByRole("button", { name: "Show summary for Audit backend" })).toBeNull();

    await user.click(disclosure);

    expect(screen.getByText("Validated the streaming boundary.")).toBeTruthy();
    expect(screen.getByRole("button", { name: "Hide summary for Audit web" }).getAttribute("aria-expanded")).toBe("true");
  });

  it("renders the final plan, workers, files, checks, usage, conflicts, and status", () => {
    const walkthrough: RunWalkthroughArtifact = {
      plan: "Audit, then edit",
      worker_contributions: ["Audit web: found a stale route"],
      changed_files: ["src/app.ts"],
      checks: [{ id: "tests", name: "tests", status: "passed", duration_ms: 12, details: null }],
      usage: { total_tokens: 42 },
      unresolved_conflicts: ["src/app.ts: route is stale <> route is current"],
      terminal_status: "completed",
    };

    render(<FinalWalkthrough walkthrough={walkthrough} />);

    expect(screen.getByText("Final walkthrough · completed")).toBeTruthy();
    expect(screen.getByText("Audit, then edit")).toBeTruthy();
    expect(screen.getByText("Audit web: found a stale route")).toBeTruthy();
    expect(screen.getByText("src/app.ts")).toBeTruthy();
    expect(screen.getByText("tests=passed")).toBeTruthy();
    expect(screen.getByText("42 tokens")).toBeTruthy();
    expect(screen.getByText("src/app.ts: route is stale <> route is current")).toBeTruthy();
  });
});
