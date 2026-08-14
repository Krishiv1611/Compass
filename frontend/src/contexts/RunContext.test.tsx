// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { RunProvider, useRunEvents } from "./RunContext";

afterEach(cleanup);


function Harness() {
  const { currentRunEvents, hydrateRun } = useRunEvents();
  return (
    <>
      <button onClick={() => hydrateRun("fork", [])}>history</button>
      <button
        onClick={() =>
          hydrateRun("fork", [{ id: "fork-event", type: "session_forked" }])
        }
      >
        fork
      </button>
      <output>{currentRunEvents.map((event) => event.type).join(",")}</output>
    </>
  );
}


describe("RunContext hydration", () => {
  it("keeps the durable fork event when empty run history finishes last", () => {
    render(<RunProvider><Harness /></RunProvider>);

    fireEvent.click(screen.getByText("fork"));
    fireEvent.click(screen.getByText("history"));

    expect(screen.getByText("session_forked")).toBeTruthy();
  });

  it("adds the durable fork event when run history finishes first", () => {
    render(<RunProvider><Harness /></RunProvider>);

    fireEvent.click(screen.getByText("history"));
    fireEvent.click(screen.getByText("fork"));

    expect(screen.getByText("session_forked")).toBeTruthy();
  });
});
