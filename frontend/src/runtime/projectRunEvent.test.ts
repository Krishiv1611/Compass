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
});
