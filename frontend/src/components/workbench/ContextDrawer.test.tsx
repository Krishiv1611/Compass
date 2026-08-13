// @vitest-environment jsdom

import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it } from "vitest";
import { InstructionRows } from "./ContextDrawer";

afterEach(cleanup);

it("renders rule precedence, digest, and truncation status", () => {
  render(<InstructionRows instructions={[
    { path: "AGENTS.md", precedence: 1, digest: "abc123", included: false, truncated: false },
    { path: "COMPASS.md", precedence: 4, digest: "def456", included: true, truncated: true },
  ]} />);

  expect(screen.getByText(/AGENTS\.md · p1 · abc123 · excluded/)).toBeTruthy();
  expect(screen.getByText(/COMPASS\.md · p4 · def456 · truncated/)).toBeTruthy();
});
