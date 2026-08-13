// @vitest-environment jsdom
import { afterEach, expect, it, vi } from "vitest";
import { cleanup, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ChatInput from "./ChatInput";

vi.mock("@/contexts/WorkbenchContext", () => ({ useWorkbench: () => ({ state: { mode: "ask" }, setMode: vi.fn(), dispatch: vi.fn() }) }));

afterEach(cleanup);

it("awaits a context-only send before clearing the reference", async () => {
  let finish!: () => void;
  const onSend = vi.fn(() => new Promise<void>(resolve => { finish = resolve; }));
  render(<ChatInput onSend={onSend} workspaceId="workspace-1" initialContextPaths={["src/app.ts"]} />);

  await userEvent.click(screen.getByRole("button", { name: "Send message" }));
  expect(onSend).toHaveBeenCalledWith("", [], "ask", ["src/app.ts"]);
  expect(screen.getByText("app.ts")).toBeTruthy();
  finish();
  await screen.findByPlaceholderText("Describe the task or ask about this project");
  expect(screen.queryByText("app.ts")).toBeNull();
});
