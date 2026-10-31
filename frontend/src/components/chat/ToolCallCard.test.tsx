// @vitest-environment jsdom

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ToolCallCard from "./ToolCallCard";

afterEach(cleanup);

describe("ToolCallCard", () => {
  beforeEach(() => {
    Object.assign(navigator, {
      clipboard: {
        writeText: vi.fn().mockResolvedValue(undefined),
      },
    });
  });

  describe("tool glyph & preview extraction", () => {
    it("renders terminal glyph and command preview for shell_execute / execute_command", () => {
      render(
        <ToolCallCard
          toolName="execute_command"
          args={{ command: "npm test" }}
          result={{ exit_code: 0, stdout: "All 10 tests passed" }}
          status="completed"
        />,
      );

      expect(screen.getByText("execute_command")).toBeTruthy();
      expect(screen.getByText("$ npm test")).toBeTruthy();
      // Should show exit 0 badge for completed shell command
      expect(screen.getByText("exit 0")).toBeTruthy();
    });

    it("renders file glyph and file path preview for file tools", () => {
      render(
        <ToolCallCard
          toolName="read_file"
          args={{ path: "src/components/App.tsx" }}
          result="export default function App() {}"
          status="completed"
        />,
      );

      expect(screen.getByText("read_file")).toBeTruthy();
      expect(screen.getByText("src/components/App.tsx")).toBeTruthy();
    });

    it("renders search glyph and query preview for search tools", () => {
      render(
        <ToolCallCard
          toolName="grep"
          args={{ query: "WorkbenchContext" }}
          result="Found 4 occurrences"
          status="completed"
        />,
      );

      expect(screen.getByText("grep")).toBeTruthy();
      expect(screen.getByText('"WorkbenchContext"')).toBeTruthy();
    });

    it("renders fallback tool name and glyph for unknown tools", () => {
      render(
        <ToolCallCard
          toolName="custom_service_call"
          args={{ serviceId: "svc-123" }}
          status="completed"
        />,
      );

      expect(screen.getByText("custom_service_call")).toBeTruthy();
    });
  });

  describe("status badges and duration", () => {
    it("renders running state with spinning indicator", () => {
      render(
        <ToolCallCard
          toolName="shell_execute"
          args={{ command: "cargo build" }}
          status="running"
        />,
      );

      expect(screen.getByText("Running")).toBeTruthy();
    });

    it("renders error state with exit code badge or error indicator", () => {
      render(
        <ToolCallCard
          toolName="shell_execute"
          args={{ command: "pytest" }}
          status="error"
          error="Process failed with exit code 1"
          result={{ exit_code: 1, stderr: "AssertionError" }}
        />,
      );

      expect(screen.getByText("exit 1")).toBeTruthy();
    });

    it("renders duration badge when durationMs is provided", () => {
      render(
        <ToolCallCard
          toolName="read_file"
          args={{ path: "package.json" }}
          status="completed"
          durationMs={125}
        />,
      );

      expect(screen.getByText("125ms")).toBeTruthy();
    });
  });

  describe("expansion and copy output interaction", () => {
    it("starts collapsed and expands on click to reveal arguments and output", async () => {
      render(
        <ToolCallCard
          toolName="edit_file"
          args={{ path: "src/main.ts", target: "foo", replacement: "bar" }}
          result="--- a/src/main.ts\n+++ b/src/main.ts\n-foo\n+bar"
          status="completed"
        />,
      );

      const headerButton = screen.getByRole("button", { expanded: false });
      expect(screen.queryByText("Arguments")).toBeNull();

      // Click to expand
      await userEvent.click(headerButton);
      expect(screen.getByRole("button", { expanded: true })).toBeTruthy();
      expect(screen.getByText("Arguments")).toBeTruthy();
      expect(screen.getByText("Output")).toBeTruthy();

      // Verify arguments content is visible
      expect(screen.getByText(/"replacement": "bar"/)).toBeTruthy();

      // Click to collapse
      await userEvent.click(headerButton);
      expect(screen.getByRole("button", { expanded: false })).toBeTruthy();
      await waitFor(() => {
        expect(screen.queryByText("Arguments")).toBeNull();
      });
    });

    it("copies output to clipboard when Copy Output button is clicked", async () => {
      render(
        <ToolCallCard
          toolName="execute_command"
          args={{ command: "git status" }}
          result="On branch main, working tree clean"
          status="completed"
        />,
      );

      // Expand card
      await userEvent.click(screen.getByRole("button", { expanded: false }));

      // Find copy output button
      const copyBtn = screen.getByRole("button", { name: /copy output/i });
      await userEvent.click(copyBtn);

      expect(navigator.clipboard.writeText).toHaveBeenCalledWith("On branch main, working tree clean");
      expect(screen.getByText(/copied/i)).toBeTruthy();
    });
  });
});
