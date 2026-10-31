// @vitest-environment jsdom

import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import MessageRow from "./MessageRow";
import { WorkbenchContext, type WorkbenchContextValue } from "@/contexts/WorkbenchContext";
import type { TranscriptMessage } from "./MessageList";

afterEach(cleanup);

describe("MessageRow", () => {
  describe("user message", () => {
    it("renders user badge and message content", () => {
      const message: TranscriptMessage = {
        id: "msg-1",
        role: "user",
        content: "Please build a dark mode toggle button",
      };

      render(<MessageRow message={message} />);

      expect(screen.getByText("User Prompt")).toBeTruthy();
      expect(screen.getByText("Please build a dark mode toggle button")).toBeTruthy();
    });

    it("renders retry button when isLast and onRetry provided, and invokes callback", async () => {
      const handleRetry = vi.fn();
      const message: TranscriptMessage = {
        id: "msg-2",
        role: "user",
        content: "Fix the failing tests",
      };

      render(
        <MessageRow
          message={message}
          onRetry={handleRetry}
          isLast={true}
          isLoading={false}
        />,
      );

      const retryBtn = screen.getByRole("button", { name: /retry/i });
      expect(retryBtn).toBeTruthy();

      await userEvent.click(retryBtn);
      expect(handleRetry).toHaveBeenCalledWith("Fix the failing tests");
    });
  });

  describe("assistant message", () => {
    it("renders model indicator and turn ready status", () => {
      const message: TranscriptMessage = {
        id: "msg-3",
        role: "assistant",
        content: "I have updated the styles.",
        model: "DeepSeek-R1",
      };

      render(<MessageRow message={message} />);

      expect(screen.getByText("DeepSeek-R1")).toBeTruthy();
      expect(screen.getByText("Turn Ready")).toBeTruthy();
      expect(screen.getByText("I have updated the styles.")).toBeTruthy();
    });

    it("renders generating indicator when message is pending", () => {
      const message: TranscriptMessage = {
        id: "msg-4",
        role: "assistant",
        content: "Thinking through changes...",
        pending: true,
      };

      render(<MessageRow message={message} />);

      expect(screen.getByText("Generating")).toBeTruthy();
    });

    it("renders revert turn button when activeWorkspaceId is present", () => {
      const message: TranscriptMessage = {
        id: "msg-5",
        role: "assistant",
        content: "Workspace updated.",
      };

      const mockWorkbench = {
        state: {
          activeWorkspaceId: "ws-test-123",
        },
        refreshWorkspace: vi.fn(),
      } as unknown as WorkbenchContextValue;

      render(
        <WorkbenchContext.Provider value={mockWorkbench}>
          <MessageRow message={message} />
        </WorkbenchContext.Provider>,
      );

      expect(screen.getByRole("button", { name: /revert turn/i })).toBeTruthy();
    });
  });
});
