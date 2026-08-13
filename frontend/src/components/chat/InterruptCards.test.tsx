// @vitest-environment jsdom

import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ToolApprovalCard from "./ToolApprovalCard";
import PlanReviewCard from "./PlanReviewCard";
import ClarificationCard from "./ClarificationCard";

afterEach(cleanup);

describe("interrupt cards", () => {
  it("sends approve rather than a legacy yes alias", async () => {
    const resume = vi.fn();
    render(
      <ToolApprovalCard
        interrupt={{
          content: "Allow this tool?",
          data: { tool_calls: [{ id: "call-1", name: "write_file", args: { path: "a.py" } }] },
        }}
        onResume={resume}
      />,
    );

    await userEvent.click(screen.getByRole("button", { name: "Approve once" }));

    expect(resume).toHaveBeenCalledWith({ action: "approve" });
    expect(screen.getAllByRole("button").every(button => button.hasAttribute("disabled"))).toBe(true);
  });

  it("carries plan revision feedback", async () => {
    const resume = vi.fn();
    render(<PlanReviewCard plan="1. Edit" onResume={resume} />);

    await userEvent.click(screen.getByRole("button", { name: "Revise" }));
    await userEvent.type(screen.getByRole("textbox"), "Split the database change");
    await userEvent.click(screen.getByRole("button", { name: "Submit revision" }));

    expect(resume).toHaveBeenCalledWith({
      action: "revise_plan",
      feedback: "Split the database change",
    });
  });

  it("answers a clarification with the entered text", async () => {
    const resume = vi.fn();
    render(<ClarificationCard prompt="Which package should change?" onResume={resume} />);

    await userEvent.type(screen.getByRole("textbox"), "Use the frontend package");
    await userEvent.click(screen.getByRole("button", { name: "Answer" }));

    expect(resume).toHaveBeenCalledWith({
      action: "answer",
      feedback: "Use the frontend package",
    });
  });
});
