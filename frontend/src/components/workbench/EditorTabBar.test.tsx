// @vitest-environment jsdom
import { afterEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import EditorTabBar from "./EditorTabBar";
import { WorkbenchProvider, useWorkbench } from "@/contexts/WorkbenchContext";
import React from "react";

afterEach(cleanup);

describe("EditorTabBar", () => {
  const sampleFiles = [
    "src/index.ts",
    "src/components/App.tsx",
    "src/styles.css",
    "package.json",
  ];

  it("renders all open tabs with base filenames and language glyphs", () => {
    render(
      <EditorTabBar
        openFiles={sampleFiles}
        activePath="src/components/App.tsx"
        onSelectFile={vi.fn()}
        onCloseFile={vi.fn()}
      />
    );

    expect(screen.getByText("index.ts")).toBeTruthy();
    expect(screen.getByText("App.tsx")).toBeTruthy();
    expect(screen.getByText("styles.css")).toBeTruthy();
    expect(screen.getByText("package.json")).toBeTruthy();

    // Verify language glyphs are rendered (e.g. data-testid from fileIcons)
    expect(screen.getAllByTestId("file-icon-typescript")).toHaveLength(2);
    expect(screen.getByTestId("file-icon-css")).toBeTruthy();
    expect(screen.getByTestId("file-icon-json")).toBeTruthy();
  });

  it("highlights the active tab with aria-selected and layoutId indicator", () => {
    render(
      <EditorTabBar
        openFiles={sampleFiles}
        activePath="src/components/App.tsx"
        onSelectFile={vi.fn()}
        onCloseFile={vi.fn()}
      />
    );

    const activeTab = screen.getByRole("tab", { name: /App\.tsx/i });
    expect(activeTab.getAttribute("aria-selected")).toBe("true");

    const inactiveTab = screen.getByRole("tab", { name: /index\.ts/i });
    expect(inactiveTab.getAttribute("aria-selected")).toBe("false");

    expect(screen.getByTestId("active-tab-indicator")).toBeTruthy();
  });

  it("calls onSelectFile when an inactive tab is clicked", async () => {
    const user = userEvent.setup();
    const handleSelect = vi.fn();
    const handleClose = vi.fn();

    render(
      <EditorTabBar
        openFiles={sampleFiles}
        activePath="src/components/App.tsx"
        onSelectFile={handleSelect}
        onCloseFile={handleClose}
      />
    );

    const targetTab = screen.getByRole("tab", { name: /index\.ts/i });
    await user.click(targetTab);

    expect(handleSelect).toHaveBeenCalledWith("src/index.ts");
    expect(handleClose).not.toHaveBeenCalled();
  });

  it("calls onCloseFile on close button click without triggering onSelectFile", async () => {
    const user = userEvent.setup();
    const handleSelect = vi.fn();
    const handleClose = vi.fn();

    render(
      <EditorTabBar
        openFiles={sampleFiles}
        activePath="src/components/App.tsx"
        onSelectFile={handleSelect}
        onCloseFile={handleClose}
      />
    );

    const closeBtn = screen.getByRole("button", { name: /Close index\.ts/i });
    await user.click(closeBtn);

    expect(handleClose).toHaveBeenCalledWith("src/index.ts");
    expect(handleSelect).not.toHaveBeenCalled();
  });

  it("calls onCloseFile when closing the active tab", async () => {
    const user = userEvent.setup();
    const handleSelect = vi.fn();
    const handleClose = vi.fn();

    render(
      <EditorTabBar
        openFiles={sampleFiles}
        activePath="src/components/App.tsx"
        onSelectFile={handleSelect}
        onCloseFile={handleClose}
      />
    );

    const closeBtn = screen.getByRole("button", { name: /Close App\.tsx/i });
    await user.click(closeBtn);

    expect(handleClose).toHaveBeenCalledWith("src/components/App.tsx");
  });

  it("renders dirty dot indicators only for modified/unsaved files", () => {
    const isDirty = (path: string) => path === "src/components/App.tsx" || path === "package.json";

    render(
      <EditorTabBar
        openFiles={sampleFiles}
        activePath="src/components/App.tsx"
        onSelectFile={vi.fn()}
        onCloseFile={vi.fn()}
        isDirty={isDirty}
      />
    );

    const dirtyIndicators = screen.getAllByTestId("dirty-indicator");
    expect(dirtyIndicators).toHaveLength(2);

    const appTab = screen.getByRole("tab", { name: /App\.tsx/i });
    expect(appTab.querySelector('[data-testid="dirty-indicator"]')).toBeTruthy();

    const indexTab = screen.getByRole("tab", { name: /index\.ts/i });
    expect(indexTab.querySelector('[data-testid="dirty-indicator"]')).toBeNull();
  });

  it("closes active tab via Ctrl+W keyboard shortcut", () => {
    const handleClose = vi.fn();

    render(
      <EditorTabBar
        openFiles={sampleFiles}
        activePath="src/components/App.tsx"
        onSelectFile={vi.fn()}
        onCloseFile={handleClose}
      />
    );

    fireEvent.keyDown(window, { key: "w", ctrlKey: true });
    expect(handleClose).toHaveBeenCalledWith("src/components/App.tsx");
  });

  it("closes active tab via Cmd+W keyboard shortcut (metaKey on Mac)", () => {
    const handleClose = vi.fn();

    render(
      <EditorTabBar
        openFiles={sampleFiles}
        activePath="src/styles.css"
        onSelectFile={vi.fn()}
        onCloseFile={handleClose}
      />
    );

    fireEvent.keyDown(window, { key: "w", metaKey: true });
    expect(handleClose).toHaveBeenCalledWith("src/styles.css");
  });

  it("renders nothing when openFiles is empty", () => {
    const { container } = render(
      <EditorTabBar
        openFiles={[]}
        activePath={undefined}
        onSelectFile={vi.fn()}
        onCloseFile={vi.fn()}
      />
    );

    expect(container.firstChild).toBeNull();
  });
});

describe("WorkbenchContext multi-tab closeFile state transitions", () => {
  function TestConsumer() {
    const { state, openFile, closeFile } = useWorkbench();

    return (
      <div>
        <div data-testid="active-file">{state.activeFile?.path ?? "none"}</div>
        <div data-testid="open-files">{state.openFiles.join(",")}</div>
        <button
          onClick={() => openFile({ path: "file1.ts", name: "file1.ts", type: "file" })}
        >
          Open 1
        </button>
        <button
          onClick={() => openFile({ path: "file2.ts", name: "file2.ts", type: "file" })}
        >
          Open 2
        </button>
        <button
          onClick={() => openFile({ path: "file3.ts", name: "file3.ts", type: "file" })}
        >
          Open 3
        </button>
        <button onClick={() => closeFile("file2.ts")}>Close 2</button>
        <button onClick={() => closeFile("file3.ts")}>Close 3</button>
        <button onClick={() => closeFile("file1.ts")}>Close 1</button>
      </div>
    );
  }

  it("handles opening multiple files, closing middle file, and switching active tab properly", async () => {
    const user = userEvent.setup();

    render(
      <WorkbenchProvider>
        <TestConsumer />
      </WorkbenchProvider>
    );

    const activeEl = screen.getByTestId("active-file");
    const openEl = screen.getByTestId("open-files");

    expect(activeEl.textContent).toBe("none");
    expect(openEl.textContent).toBe("");

    // Open file1, file2, file3
    await user.click(screen.getByText("Open 1"));
    expect(activeEl.textContent).toBe("file1.ts");
    expect(openEl.textContent).toBe("file1.ts");

    await user.click(screen.getByText("Open 2"));
    expect(activeEl.textContent).toBe("file2.ts");
    expect(openEl.textContent).toBe("file1.ts,file2.ts");

    await user.click(screen.getByText("Open 3"));
    expect(activeEl.textContent).toBe("file3.ts");
    expect(openEl.textContent).toBe("file1.ts,file2.ts,file3.ts");

    // Close file2 (not active, active is file3)
    await user.click(screen.getByText("Close 2"));
    expect(openEl.textContent).toBe("file1.ts,file3.ts");
    expect(activeEl.textContent).toBe("file3.ts");

    // Close file3 (active, last element: should switch to previous available file file1.ts)
    await user.click(screen.getByText("Close 3"));
    expect(openEl.textContent).toBe("file1.ts");
    expect(activeEl.textContent).toBe("file1.ts");

    // Close file1 (last remaining open file: active should become none)
    await user.click(screen.getByText("Close 1"));
    expect(openEl.textContent).toBe("");
    expect(activeEl.textContent).toBe("none");
  });
});
