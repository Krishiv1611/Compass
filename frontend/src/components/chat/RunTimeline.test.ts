import { describe, expect, it } from "vitest";
import { deriveStageStates, stageForEvent } from "@/runtime/runTimelineProjection";

describe("run timeline stage projection", () => {
  it("derives stages from canonical event nodes", () => {
    expect(stageForEvent({ type: "status", node: "context_injector" })).toBe("context");
    expect(stageForEvent({ type: "plan_created", node: "planner" })).toBe("plan");
    expect(stageForEvent({ type: "tool_call", node: "executor" })).toBe("edit");
    expect(stageForEvent({ type: "check_result", node: "linter_node" })).toBe("check");
    expect(stageForEvent({ type: "workspace_patch" })).toBe("review");
    expect(stageForEvent({ type: "checkpoint_restored" })).toBe("review");
    expect(stageForEvent({ type: "done" })).toBe("complete");
  });

  it("completes stages before the current canonical node", () => {
    const stages = ["context", "plan", "edit", "complete"] as const;
    const states = deriveStageStates(
      [
        { type: "status", node: "context_injector" },
        { type: "plan_created", node: "planner" },
        { type: "status", node: "executor" },
      ],
      [...stages],
      true,
    );

    expect(states.get("context")).toBe("complete");
    expect(states.get("plan")).toBe("complete");
    expect(states.get("edit")).toBe("active");
  });
});
