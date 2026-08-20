import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

import { emptyRunArtifact, projectRunEvent } from "@/runtime/projectRunEvent";
import type { RunEvent } from "@/types/run";

const scenario = JSON.parse(readFileSync(
  new URL("../../../tests/fixtures/run_events/multi_agent_journey.json", import.meta.url),
  "utf-8",
)) as {
  events: RunEvent[];
  expected: {
    plan: string;
    workers: [string, string, number][];
    worker_contributions: string[];
    changed_files: string[];
    checks: string[];
    total_tokens: number;
    usage_by_node: Record<string, { total_tokens: number }>;
    unresolved_conflicts: string[];
    terminal_status: string;
  };
};

describe("bounded multi-agent journey", () => {
  it("projects the same final walkthrough as the TUI", () => {
    const artifact = scenario.events.reduce(projectRunEvent, emptyRunArtifact());
    const expected = scenario.expected;

    expect(artifact.plan).toBe(expected.plan);
    expect(artifact.workers.map(worker => [worker.task_id, worker.status, worker.evidence_count])).toEqual(expected.workers);
    expect(artifact.walkthrough.worker_contributions).toEqual(expected.worker_contributions);
    expect(artifact.changed_files).toEqual(expected.changed_files);
    expect(artifact.checks.map(check => `${check.name}=${check.status}`)).toEqual(expected.checks);
    expect(artifact.usage.total_tokens).toBe(expected.total_tokens);
    expect(artifact.usage.usage_by_node).toEqual(expected.usage_by_node);
    expect(artifact.unresolved_conflicts).toEqual(expected.unresolved_conflicts);
    expect(artifact.terminal_status).toBe(expected.terminal_status);
    expect(artifact.walkthrough).toMatchObject({
      plan: expected.plan,
      worker_contributions: expected.worker_contributions,
      changed_files: expected.changed_files,
      unresolved_conflicts: expected.unresolved_conflicts,
      terminal_status: expected.terminal_status,
    });
  });
});
