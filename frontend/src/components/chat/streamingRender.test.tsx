// @vitest-environment jsdom

import { render } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import MessageList, { type TranscriptMessage } from "./MessageList";

const mocks = vi.hoisted(() => ({ markdown: vi.fn() }));
vi.mock("./MarkdownMessage", () => ({
  default: (props: { content: string }) => { mocks.markdown(props); return null; },
}));

describe("streaming transcript rendering", () => {
  it("parses completed markdown once and waits until DONE for the pending row", () => {
    const completed: TranscriptMessage = { id: "done", role: "assistant", content: "finished" };
    let pending: TranscriptMessage = { id: "live", role: "assistant", content: "a", pending: true };
    const props = { isLoading: true, onRetry: vi.fn(), pendingApproval: null, onResume: vi.fn() };
    const view = render(<MessageList {...props} messages={[completed, pending]} />);

    for (let index = 0; index < 100; index += 1) {
      pending = { ...pending, content: `token ${index}` };
      view.rerender(<MessageList {...props} messages={[completed, pending]} />);
    }

    expect(mocks.markdown).toHaveBeenCalledTimes(1);
    pending = { ...pending, pending: false };
    view.rerender(<MessageList {...props} isLoading={false} messages={[completed, pending]} />);
    expect(mocks.markdown).toHaveBeenCalledTimes(2);
  });
});
