import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import { FakeRunServer, type FakeRunScenario } from "@/test/fakeRunServer";
import { emptyRunArtifact, projectRunEvent } from "@/runtime/projectRunEvent";

const scenarios = JSON.parse(readFileSync(new URL("../../../tests/fixtures/run_events/surface_parity.json", import.meta.url), "utf-8")) as Record<string, FakeRunScenario>;

describe("TUI/web parity scenarios", () => {
  it("projects all six deterministic journeys and records exact resumes", () => {
    const server = new FakeRunServer(scenarios);
    const expectedStatus: Record<string, string> = { ask: "completed", approved_edit: "completed", plan_revise: "waiting_for_approval", clarification: "waiting_for_approval", goal_failure: "failed", cancel: "cancelled" };
    for (const name of Object.keys(scenarios)) {
      const artifact = server.replay(name).reduce(projectRunEvent, emptyRunArtifact());
      expect(artifact.terminal_status, name).toBe(expectedStatus[name]);
      const resume = server.expectedResume(name);
      if (resume) { server.resume(resume); expect(server.resumes.at(-1), name).toEqual(resume); }
    }
  });
});
