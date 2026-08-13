import type { FileNode } from "@/components/sandbox/FileExplorer";

export const parseGitHubRemote = (remote?: string | null) => {
  if (!remote) return null;
  const match = remote.match(/github\.com[/:]([^/]+)\/(.+)$/i);
  if (!match) return null;
  return { owner: match[1], repo: match[2].replace(/\.git$/i, "") };
};

export const resetPublishState = () => ({
  selectedPaths: [] as string[],
  branch: "",
  newBranch: "",
  commitSha: null as string | null,
  pullUrl: null as string | null,
  step: "branch" as const,
});

export function workspacePaths(nodes: FileNode[]): string[] {
  return nodes.flatMap(node => node.type === "file" ? [node.path] : workspacePaths(node.children ?? []));
}
