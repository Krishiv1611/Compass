import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { emptyRunArtifact, projectRunEvent } from "./projectRunEvent";
import type { RunEvent } from "@/types/run";
import { eventsFromRunHistory } from "@/api/runs";

const fixture = JSON.parse(
  readFileSync(
    new URL("../../../tests/fixtures/run_events/basic_edit.json", import.meta.url),
    "utf-8",
  ),
) as { events: RunEvent[]; expected: unknown };

describe("projectRunEvent", () => {
  it("projects the shared basic edit fixture", () => {
    const artifact = fixture.events.reduce(projectRunEvent, emptyRunArtifact());

    expect(artifact).toEqual(fixture.expected);
  });

  it("hydrates canonical events from the latest historical run", () => {
    expect(eventsFromRunHistory({
      items: [
        { id: "latest", events: fixture.events },
        { id: "older", events: [{ id: "event-old", type: "done" }] },
      ],
    })).toEqual(fixture.events);
  });

  it("updates one hook check through pending, running, and passed", () => {
    let artifact = emptyRunArtifact();
    for (const status of ["pending", "running", "passed"]) {
      artifact = projectRunEvent(artifact, {
        type: "check_result", content: "python tests", data: { id: "hook-1", status },
      });
    }
    expect(artifact.checks).toHaveLength(1);
    expect(artifact.checks[0].status).toBe("passed");
  });

  it("upserts worker events by task id while preserving streamed fields", () => {
    let artifact = emptyRunArtifact();
    artifact = projectRunEvent(artifact, {
      type: "agent_started",
      data: {
        task_id: "backend",
        title: "Audit backend",
        status: "running",
        duration_ms: 0,
        evidence_count: 0,
      },
    });
    artifact = projectRunEvent(artifact, {
      type: "agent_progress",
      data: {
        task_id: "backend",
        title: "Audit backend",
        status: "running",
        duration_ms: 128,
        evidence_count: 2,
      },
    });
    artifact = projectRunEvent(artifact, {
      type: "agent_completed",
      content: "Validated the API boundary.",
      data: {
        task_id: "backend",
        title: "Audit backend",
        status: "completed",
        duration_ms: 246,
        evidence_count: 3,
      },
    });

    expect(artifact.workers).toEqual([
      {
        task_id: "backend",
        title: "Audit backend",
        status: "completed",
        duration_ms: 246,
        evidence_count: 3,
        summary: "Validated the API boundary.",
      },
    ]);
  });

  it("keeps synthesis conflicts in the final walkthrough", () => {
    let artifact = projectRunEvent(emptyRunArtifact(), {
      type: "status",
      content: "Worker evidence synthesized",
      data: { conflicts: ["src/app.py: claim A <> claim B"] },
    });
    artifact = projectRunEvent(artifact, {
      type: "done",
      content: "Finished with a conflict for the executor.",
      data: { status: "completed" },
    });

    expect(artifact.unresolved_conflicts).toEqual(["src/app.py: claim A <> claim B"]);
    expect(artifact.walkthrough.unresolved_conflicts).toEqual(["src/app.py: claim A <> claim B"]);
  });
});
