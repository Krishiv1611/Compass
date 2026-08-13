import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";
import type { FakeRunScenario } from "@/test/fakeRunServer";
import { createFakeSocketFactory } from "@/test/fakeSocket";
import { emptyRunArtifact, projectRunEvent } from "@/runtime/projectRunEvent";
import { RunController } from "@/runtime/RunController";

const scenarios = JSON.parse(readFileSync(new URL("../../../tests/fixtures/run_events/surface_parity.json", import.meta.url), "utf-8")) as Record<string, FakeRunScenario>;

describe("TUI/web parity scenarios", () => {
  it("projects all six deterministic journeys and records exact resumes", () => {
    const expectedStatus: Record<string, string> = { ask: "completed", approved_edit: "completed", plan_revise: "waiting_for_approval", clarification: "waiting_for_approval", goal_failure: "failed", cancel: "cancelled" };
    for (const [name, scenario] of Object.entries(scenarios)) {
      const sockets = createFakeSocketFactory();
      let artifact = emptyRunArtifact();
      const controller = new RunController({
        createSocket: sockets.create,
        cancelRun: async () => undefined,
        onEvent: event => { artifact = projectRunEvent(artifact, event); },
      });
      controller.start({ sessionId: name, content: name, mode: "edit", contextFiles: [] });
      const socket = sockets.forSession(name);
      socket.open();
      if (scenario.resume) {
        expect(controller.resume(scenario.resume), name).toBe(true);
        expect(JSON.parse(socket.sent[1]), name).toMatchObject({ type: "resume", ...scenario.resume });
      }
      scenario.events.forEach(event => socket.message(event));

      expect(artifact.terminal_status, name).toBe(expectedStatus[name]);
      expect(artifact.changed_files, name).toEqual(name === "approved_edit" ? ["a.py"] : []);
      expect(artifact.checks.map(check => check.status), name).toEqual(name === "approved_edit" ? ["passed"] : name === "goal_failure" ? ["failed"] : []);
    }
  });
});
