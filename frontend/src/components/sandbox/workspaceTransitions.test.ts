import { describe, expect, it } from "vitest";
import { parseGitHubRemote, resetPublishState, workspacePaths } from "@/components/github/publishState";

describe("workspace transition helpers", () => {
  it("parses repository names containing dots and removes only the final git suffix", () => {
    expect(parseGitHubRemote("git@github.com:owner/repo.with.dots.git")).toEqual({ owner: "owner", repo: "repo.with.dots" });
  });

  it("clears every target-specific publish field", () => {
    expect(resetPublishState()).toEqual({ selectedPaths: [], branch: "", newBranch: "", commitSha: null, pullUrl: null, step: "branch" });
  });

  it("flattens all current workspace files for publishing", () => {
    expect(workspacePaths([{ name: "src", path: "src", type: "folder", children: [{ name: "a.ts", path: "src/a.ts", type: "file" }] }])).toEqual(["src/a.ts"]);
  });
});
