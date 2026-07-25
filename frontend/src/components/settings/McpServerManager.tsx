import { useEffect, useState } from "react";
import { Loader2, Server, ShieldCheck, Terminal } from "lucide-react";
import { mcpApi } from "@/api";

interface ManagedMcpResponse {
  mcpServers?: Record<string, unknown>;
  managed?: boolean;
  message?: string;
}

/**
 * Hosted Compass never accepts executable local MCP commands from a browser.
 * Local MCP setup is intentionally kept in the TUI/project configuration.
 */
export default function McpServerManager() {
  const [status, setStatus] = useState<ManagedMcpResponse | null>(null);
  const [error, setError] = useState(false);

  useEffect(() => {
    mcpApi.getMcpServers()
      .then((response: ManagedMcpResponse) => setStatus(response))
      .catch(() => setError(true));
  }, []);

  if (!status && !error) {
    return <div className="p-8 text-center"><Loader2 className="mx-auto animate-spin text-muted-foreground" /></div>;
  }

  const capabilityCount = Object.keys(status?.mcpServers ?? {}).length;

  return (
    <section className="space-y-4" aria-labelledby="mcp-heading">
      <div>
        <h3 id="mcp-heading" className="text-lg font-semibold">MCP capabilities</h3>
        <p className="text-sm text-muted-foreground">Hosted workspaces expose approved capabilities only.</p>
      </div>

      <div className="flex gap-3 border-y border-border bg-muted/20 p-4">
        <ShieldCheck className="mt-0.5 h-5 w-5 shrink-0 text-primary" aria-hidden="true" />
        <div className="space-y-1 text-sm">
          <p className="font-medium">Local commands are protected</p>
          <p className="text-muted-foreground">
            {error
              ? "Capability status is temporarily unavailable."
              : status?.message ?? "MCP capabilities are managed by this workspace."}
          </p>
        </div>
      </div>

      <div className="flex items-center gap-3 border-y border-border p-4 text-sm">
        {capabilityCount ? <Server className="h-4 w-4 text-primary" /> : <Terminal className="h-4 w-4 text-muted-foreground" />}
        <div>
          <p className="font-medium">{capabilityCount} approved remote {capabilityCount === 1 ? "capability" : "capabilities"}</p>
          <p className="text-muted-foreground">Configure local command MCP servers from the Compass TUI, not this web settings page.</p>
        </div>
      </div>
    </section>
  );
}
