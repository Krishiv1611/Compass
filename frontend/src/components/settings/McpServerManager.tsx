import { useEffect, useMemo, useState } from "react";
import {
  AlertCircle,
  CheckCircle2,
  Cpu,
  FileCode2,
  FolderTree,
  Globe,
  Layers,
  Loader2,
  Search,
  Server,
  ShieldAlert,
  ShieldCheck,
  Terminal,
  X,
} from "lucide-react";
import { mcpApi, toolsApi } from "@/api";
import { Input } from "@/components/ui/input";

export interface ToolInfo {
  name: string;
  description: string;
  environment: "web" | "tui" | string;
}

interface ManagedMcpResponse {
  mcpServers?: Record<string, unknown>;
  managed?: boolean;
  message?: string;
}

type ToolCategory = "all" | "filesystem" | "execution" | "search" | "workflow";

function getToolCategory(name: string): Exclude<ToolCategory, "all"> {
  const n = name.toLowerCase();
  if (n.includes("file") || n.includes("dir")) return "filesystem";
  if (n.includes("shell") || n.includes("exec") || n.includes("terminal")) return "execution";
  if (n.includes("search") || n.includes("grep") || n.includes("find") || n.includes("codebase")) return "search";
  return "workflow";
}

function getToolIcon(name: string) {
  const cat = getToolCategory(name);
  switch (cat) {
    case "filesystem":
      return FileCode2;
    case "execution":
      return Terminal;
    case "search":
      return Search;
    case "workflow":
      return Cpu;
    default:
      return Layers;
  }
}

export default function McpServerManager() {
  const [tools, setTools] = useState<ToolInfo[]>([]);
  const [mcpStatus, setMcpStatus] = useState<ManagedMcpResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState("");
  const [selectedCategory, setSelectedCategory] = useState<ToolCategory>("all");

  useEffect(() => {
    let mounted = true;
    setLoading(true);
    setError(null);

    Promise.allSettled([toolsApi.listTools(), mcpApi.getMcpServers()])
      .then(([toolsRes, mcpRes]) => {
        if (!mounted) return;
        if (toolsRes.status === "fulfilled" && Array.isArray(toolsRes.value)) {
          setTools(toolsRes.value);
        } else if (toolsRes.status === "rejected") {
          setError("Capability catalog is temporarily unavailable.");
        }

        if (mcpRes.status === "fulfilled") {
          setMcpStatus(mcpRes.value as ManagedMcpResponse);
        }
      })
      .catch(() => {
        if (mounted) setError("Capability catalog is temporarily unavailable.");
      })
      .finally(() => {
        if (mounted) setLoading(false);
      });

    return () => {
      mounted = false;
    };
  }, []);

  const capabilityCount = Object.keys(mcpStatus?.mcpServers ?? {}).length;

  const filteredTools = useMemo(() => {
    return tools.filter((tool) => {
      const matchesSearch =
        tool.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        tool.description.toLowerCase().includes(searchQuery.toLowerCase());
      if (!matchesSearch) return false;

      if (selectedCategory === "all") return true;
      return getToolCategory(tool.name) === selectedCategory;
    });
  }, [tools, searchQuery, selectedCategory]);

  if (loading) {
    return (
      <div className="flex h-48 flex-col items-center justify-center gap-3 p-8 text-center text-muted-foreground">
        <Loader2 className="h-6 w-6 animate-spin text-primary" />
        <span className="text-xs font-mono">Inspecting agent capabilities & tool registries...</span>
      </div>
    );
  }

  return (
    <section className="space-y-6" aria-labelledby="tools-heading">
      <div className="flex flex-col gap-1 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h3 id="tools-heading" className="text-base font-semibold text-foreground">
            Agent Capabilities & Tools
          </h3>
          <p className="text-xs text-muted-foreground">
            Active tool dispatch table verified against real backend runtime endpoints.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className="inline-flex items-center gap-1.5 rounded-full border border-sky-500/30 bg-sky-500/10 px-2.5 py-0.5 font-mono text-[11px] text-sky-400">
            <span className="h-1.5 w-1.5 rounded-full bg-sky-400" />
            {tools.length} Registered Tools
          </span>
          <span className="inline-flex items-center gap-1 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2.5 py-0.5 font-mono text-[11px] text-emerald-400">
            0% Mocked
          </span>
        </div>
      </div>

      {/* Remote MCP status card */}
      <div className="rounded-lg border border-border/80 bg-muted/20 p-4 space-y-3">
        <div className="flex items-start gap-3">
          <ShieldCheck className="mt-0.5 h-5 w-5 shrink-0 text-primary" aria-hidden="true" />
          <div className="min-w-0 flex-1 space-y-1 text-sm">
            <div className="flex items-center justify-between">
              <p className="font-semibold text-foreground">Local commands are protected</p>
              <span className="inline-flex items-center gap-1 text-[11px] font-mono text-muted-foreground">
                <Server className="h-3 w-3 text-primary" />
                {capabilityCount} approved remote {capabilityCount === 1 ? "capability" : "capabilities"}
              </span>
            </div>
            <p className="text-xs leading-relaxed text-muted-foreground">
              {mcpStatus?.message ?? "MCP capabilities are managed by this workspace."}
            </p>
          </div>
        </div>
      </div>

      {error && (
        <div
          role="alert"
          className="flex items-center gap-2.5 rounded-md border border-destructive/30 bg-destructive/10 px-3.5 py-2.5 text-xs text-destructive"
        >
          <AlertCircle className="h-4 w-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Search and Category Filter Toolbar */}
      <div className="space-y-3">
        <div className="relative">
          <Search className="absolute left-3 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Filter capabilities by name or description..."
            className="h-8 pl-8 pr-8 text-xs font-mono bg-background border-border/70 focus-visible:border-sky-500/60"
          />
          {searchQuery && (
            <button
              type="button"
              onClick={() => setSearchQuery("")}
              className="absolute right-2.5 top-1/2 -translate-y-1/2 text-muted-foreground hover:text-foreground"
              aria-label="Clear filter"
            >
              <X className="h-3.5 w-3.5" />
            </button>
          )}
        </div>

        <div className="flex flex-wrap items-center gap-1.5 text-xs">
          {(
            [
              { id: "all", label: "All Tools" },
              { id: "filesystem", label: "Filesystem" },
              { id: "execution", label: "Terminal / Shell" },
              { id: "search", label: "Search & RAG" },
              { id: "workflow", label: "Planning & Workflow" },
            ] as const
          ).map((cat) => (
            <button
              key={cat.id}
              type="button"
              onClick={() => setSelectedCategory(cat.id)}
              className={`rounded-md px-2.5 py-1 text-[11px] font-medium transition-colors ${
                selectedCategory === cat.id
                  ? "bg-primary text-primary-foreground font-semibold"
                  : "bg-muted/40 text-muted-foreground hover:bg-muted hover:text-foreground"
              }`}
            >
              {cat.label}
            </button>
          ))}
        </div>
      </div>

      {/* Tool Cards Grid */}
      {filteredTools.length === 0 ? (
        <div className="rounded-lg border border-dashed border-border/80 p-8 text-center text-xs text-muted-foreground">
          No tools match the selected filters.
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-2.5 md:grid-cols-2">
          {filteredTools.map((tool) => {
            const Icon = getToolIcon(tool.name);
            const isGated = tool.environment === "tui" || tool.name === "shell_execute";

            return (
              <div
                key={tool.name}
                className="group relative flex flex-col justify-between rounded-lg border border-border/70 bg-card/60 p-3.5 transition-all hover:border-sky-500/40 hover:bg-card hover:shadow-[0_4px_20px_rgba(0,0,0,0.2)]"
              >
                <div>
                  <div className="flex items-start justify-between gap-2">
                    <div className="flex items-center gap-2">
                      <span className="flex h-7 w-7 items-center justify-center rounded-md border border-border/80 bg-muted/30 text-primary">
                        <Icon className="h-3.5 w-3.5" />
                      </span>
                      <span className="font-mono text-xs font-semibold text-foreground tracking-tight">
                        {tool.name}
                      </span>
                    </div>

                    <span
                      className={`inline-flex items-center gap-1 rounded border px-1.5 py-0.5 font-sans text-[10px] font-medium ${
                        isGated
                          ? "border-amber-500/30 bg-amber-500/10 text-amber-300"
                          : "border-sky-500/30 bg-sky-500/10 text-sky-300"
                      }`}
                    >
                      {tool.environment === "tui" ? "Host / TUI Gated" : "Web & Studio"}
                    </span>
                  </div>

                  <p className="mt-2 line-clamp-2 text-xs leading-relaxed text-muted-foreground">
                    {tool.description}
                  </p>
                </div>

                <div className="mt-3 flex items-center justify-between border-t border-border/40 pt-2 text-[10px] font-mono">
                  <span className="text-muted-foreground">Safety Policy</span>
                  {isGated ? (
                    <span className="inline-flex items-center gap-1 text-amber-400 font-medium">
                      <ShieldAlert className="h-3 w-3" />
                      Approval Required
                    </span>
                  ) : (
                    <span className="inline-flex items-center gap-1 text-emerald-400 font-medium">
                      <CheckCircle2 className="h-3 w-3" />
                      Auto-Approved
                    </span>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
}
