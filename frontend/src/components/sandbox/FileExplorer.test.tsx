// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import FileExplorer, { type FileNode } from "./FileExplorer";
import { getFileColor, getFileIcon, getFileType } from "@/lib/fileIcons";

const mockGetPatches = vi.fn();

vi.mock("@/api", () => ({
  patchesApi: {
    getPatches: (...args: unknown[]) => mockGetPatches(...args),
  },
  workspaceApi: {
    searchFiles: vi.fn(),
  },
}));

let mockWorkbenchState = {
  activeWorkspaceId: null as string | null,
  projectName: "Test Project",
  selectedContextFiles: [] as string[],
  patchesVersion: 0,
};

const mockSetContextFiles = vi.fn();
const mockRemoveContextFile = vi.fn();
const mockDispatch = vi.fn();

vi.mock("@/contexts/WorkbenchContext", () => ({
  useWorkbench: () => ({
    state: mockWorkbenchState,
    dispatch: mockDispatch,
    setContextFiles: mockSetContextFiles,
    removeContextFile: mockRemoveContextFile,
  }),
}));

afterEach(cleanup);

describe("fileIcons", () => {
  it("resolves language types accurately by file extension", () => {
    expect(getFileType("app.ts")).toBe("typescript");
    expect(getFileType("Component.tsx")).toBe("typescript");
    expect(getFileType("index.js")).toBe("javascript");
    expect(getFileType("View.jsx")).toBe("javascript");
    expect(getFileType("script.py")).toBe("python");
    expect(getFileType("styles.css")).toBe("css");
    expect(getFileType("theme.scss")).toBe("css");
    expect(getFileType("index.html")).toBe("html");
    expect(getFileType("page.htm")).toBe("html");
    expect(getFileType("package.json")).toBe("json");
    expect(getFileType("README.md")).toBe("markdown");
    expect(getFileType("doc.mdx")).toBe("markdown");
    expect(getFileType("deploy.sh")).toBe("shell");
    expect(getFileType("build.bash")).toBe("shell");
    expect(getFileType(".env")).toBe("shell");
    expect(getFileType(".env.local")).toBe("shell");
    expect(getFileType("docker-compose.yml")).toBe("shell");
    expect(getFileType("config.yaml")).toBe("shell");
    expect(getFileType("logo.png")).toBe("image");
    expect(getFileType("unknown.xyz")).toBe("default");
  });

  it("returns exact branded color codes for each file type", () => {
    expect(getFileColor("app.ts")).toBe("#3178C6");
    expect(getFileColor("index.js")).toBe("#F7DF1E");
    expect(getFileColor("script.py")).toBe("#3776AB");
    expect(getFileColor("styles.css")).toBe("#38BDF8");
    expect(getFileColor("index.html")).toBe("#E34F26");
    expect(getFileColor("package.json")).toBe("#F59E0B");
    expect(getFileColor("README.md")).toBe("#14B8A6");
    expect(getFileColor("deploy.sh")).toBe("#A855F7");
    expect(getFileColor("folder", true)).toBe("#EAB308");
  });

  it("renders distinct glyph icons for files and folders", () => {
    const { container: tsContainer } = render(<div>{getFileIcon("main.ts")}</div>);
    expect(tsContainer.querySelector('[data-testid="file-icon-typescript"]')).toBeTruthy();

    const { container: jsContainer } = render(<div>{getFileIcon("main.js")}</div>);
    expect(jsContainer.querySelector('[data-testid="file-icon-javascript"]')).toBeTruthy();

    const { container: pyContainer } = render(<div>{getFileIcon("agent.py")}</div>);
    expect(pyContainer.querySelector('[data-testid="file-icon-python"]')).toBeTruthy();

    const { container: folderClosed } = render(<div>{getFileIcon("src", true, false)}</div>);
    expect(folderClosed.querySelector('[data-testid="folder-icon-closed"]')).toBeTruthy();

    const { container: folderOpen } = render(<div>{getFileIcon("src", true, true)}</div>);
    expect(folderOpen.querySelector('[data-testid="folder-icon-open"]')).toBeTruthy();
  });
});

describe("FileExplorer", () => {
  const sampleTree: FileNode[] = [
    {
      name: "src",
      path: "src",
      type: "folder",
      children: [
        { name: "index.ts", path: "src/index.ts", type: "file" },
        { name: "styles.css", path: "src/styles.css", type: "file" },
      ],
    },
    { name: "package.json", path: "package.json", type: "file" },
    { name: "README.md", path: "README.md", type: "file" },
  ];

  beforeEach(() => {
    mockGetPatches.mockReset();
    mockGetPatches.mockResolvedValue([]);
    mockSetContextFiles.mockReset();
    mockRemoveContextFile.mockReset();
    mockDispatch.mockReset();
    mockWorkbenchState = {
      activeWorkspaceId: null,
      projectName: "Test Project",
      selectedContextFiles: [],
      patchesVersion: 0,
    };
  });

  it("renders tree nodes with compact 28px density and hairline indent guidelines", () => {
    const { container } = render(
      <FileExplorer files={sampleTree} onFileSelect={vi.fn()} />
    );

    // Check compact row height (h-7 is 28px)
    const treeItems = screen.getAllByRole("treeitem");
    expect(treeItems.length).toBeGreaterThan(0);
    for (const item of treeItems) {
      expect(item.className).toContain("h-7");
    }

    // Children of "src" (depth 1) should have hairline indent guide
    const indentGuides = container.querySelectorAll('[data-testid="indent-guide"]');
    expect(indentGuides.length).toBeGreaterThan(0);
  });

  it("renders language glyphs beside files and opens/closes folders on click", async () => {
    const user = userEvent.setup();
    const onSelect = vi.fn();
    render(<FileExplorer files={sampleTree} onFileSelect={onSelect} />);

    // Check language glyphs
    expect(screen.getByTestId("file-icon-typescript")).toBeTruthy();
    expect(screen.getByTestId("file-icon-css")).toBeTruthy();
    expect(screen.getByTestId("file-icon-json")).toBeTruthy();
    expect(screen.getByTestId("file-icon-markdown")).toBeTruthy();

    // Select a file
    await user.click(screen.getByRole("treeitem", { name: "index.ts" }));
    expect(onSelect).toHaveBeenCalledWith(expect.objectContaining({ path: "src/index.ts" }));

    // Click folder to collapse
    const srcFolder = screen.getByRole("treeitem", { name: "src" });
    await user.click(srcFolder);
    expect(screen.queryByRole("treeitem", { name: "index.ts" })).toBeNull();

    // Click again to expand
    await user.click(srcFolder);
    expect(screen.getByRole("treeitem", { name: "index.ts" })).toBeTruthy();
  });

  it("displays git change status indicators (M, U, D)", () => {
    render(
      <FileExplorer
        files={sampleTree}
        onFileSelect={vi.fn()}
        gitStatus={{
          "src/index.ts": "M",
          "src/styles.css": "U",
          "package.json": "D",
        }}
      />
    );

    const modifiedBadge = screen.getByTestId("git-status-src/index.ts");
    expect(modifiedBadge).toBeTruthy();
    expect(modifiedBadge.textContent).toBe("M");
    expect(modifiedBadge.className).toContain("text-amber-400");

    const untrackedBadge = screen.getByTestId("git-status-src/styles.css");
    expect(untrackedBadge).toBeTruthy();
    expect(untrackedBadge.textContent).toBe("U");
    expect(untrackedBadge.className).toContain("text-emerald-400");

    const deletedBadge = screen.getByTestId("git-status-package.json");
    expect(deletedBadge).toBeTruthy();
    expect(deletedBadge.textContent).toBe("D");
    expect(deletedBadge.className).toContain("text-rose-400");
  });

  it("fetches git change status automatically from active workspace patches", async () => {
    mockWorkbenchState.activeWorkspaceId = "ws-123";
    mockGetPatches.mockResolvedValueOnce([
      {
        id: "patch-1",
        version: 1,
        status: "pending",
        changes: [
          { path: "src/index.ts", type: "edit" },
          { path: "README.md", type: "create" },
        ],
      },
    ]);

    render(<FileExplorer files={sampleTree} onFileSelect={vi.fn()} />);

    await waitFor(() => {
      expect(screen.getByTestId("git-status-src/index.ts")).toBeTruthy();
    });

    expect(screen.getByTestId("git-status-src/index.ts").textContent).toBe("M");
    expect(screen.getByTestId("git-status-README.md").textContent).toBe("U");
  });

  it("supports 1-click 'Add to AI Context' button in hover action bar", async () => {
    const user = userEvent.setup();
    render(<FileExplorer files={sampleTree} onFileSelect={vi.fn()} />);

    const addBtn = screen.getByRole("button", { name: "Add index.ts to context" });
    await user.click(addBtn);

    expect(mockSetContextFiles).toHaveBeenCalledWith(["src/index.ts"]);
  });

  it("supports removing a file from AI Context when already present", async () => {
    mockWorkbenchState.selectedContextFiles = ["src/index.ts"];
    const user = userEvent.setup();
    render(<FileExplorer files={sampleTree} onFileSelect={vi.fn()} />);

    const removeBtn = screen.getByRole("button", { name: "Remove index.ts from context" });
    await user.click(removeBtn);

    expect(mockRemoveContextFile).toHaveBeenCalledWith("src/index.ts");
  });

  it("renders folder creation and item modification actions", async () => {
    const user = userEvent.setup();
    const onCreate = vi.fn();
    const onRename = vi.fn();
    const onDelete = vi.fn();

    render(
      <FileExplorer
        files={sampleTree}
        onFileSelect={vi.fn()}
        onCreate={onCreate}
        onRename={onRename}
        onDelete={onDelete}
      />
    );

    // New file in folder
    const newFileBtn = screen.getByRole("button", { name: "New file in src" });
    await user.click(newFileBtn);
    expect(onCreate).toHaveBeenCalledWith("src", "file");

    // New folder in folder
    const newFolderBtn = screen.getByRole("button", { name: "New folder in src" });
    await user.click(newFolderBtn);
    expect(onCreate).toHaveBeenCalledWith("src", "folder");

    // Rename file
    const renameBtn = screen.getByRole("button", { name: "Rename package.json" });
    await user.click(renameBtn);
    expect(onRename).toHaveBeenCalledWith("package.json");

    // Delete file
    const deleteBtn = screen.getByRole("button", { name: "Delete package.json" });
    await user.click(deleteBtn);
    expect(onDelete).toHaveBeenCalledWith("package.json");
  });

  it("supports keyboard navigation across files and folders", () => {
    render(<FileExplorer files={sampleTree} onFileSelect={vi.fn()} />);

    const items = screen.getAllByRole("treeitem");
    expect(items[0].getAttribute("tabindex")).toBe("0");

    // Down to first child
    fireEvent.keyDown(items[0], { key: "ArrowDown" });
    expect(document.activeElement).toBe(items[1]);

    // End to last element
    fireEvent.keyDown(items[1], { key: "End" });
    expect(document.activeElement).toBe(items[items.length - 1]);

    // Home back to first
    fireEvent.keyDown(items[items.length - 1], { key: "Home" });
    expect(document.activeElement).toBe(items[0]);
  });
});
