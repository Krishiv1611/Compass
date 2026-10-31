import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { Compass, Cpu, ShieldCheck, Terminal, Workflow } from "lucide-react";
import AuthSurface from "@/components/auth/AuthSurface";
import { useAuth } from "@/contexts/AuthContext";

const CAPABILITY_TAGS = [
  "Vite / React",
  "FastAPI",
  "CodeMirror",
  "WebContainers",
  "Git Staging",
] as const;

export default function LoginPage() {
  const navigate = useNavigate();
  const { status } = useAuth();

  useEffect(() => {
    if (status === "authenticated") navigate("/chat", { replace: true });
  }, [navigate, status]);

  if (status === "loading") {
    return <div className="h-screen w-full bg-[#080A0E]" />;
  }

  return (
    <div className="relative min-h-screen w-full bg-[#080A0E] text-foreground flex flex-col md:grid md:grid-cols-2 overflow-x-hidden">
      {/* Ambient background glows */}
      <div
        className="pointer-events-none absolute -top-40 -left-40 h-[500px] w-[500px] rounded-full bg-cyan-500/10 blur-[130px]"
        aria-hidden="true"
      />
      <div
        className="pointer-events-none absolute top-1/2 left-1/4 h-[400px] w-[400px] -translate-y-1/2 rounded-full bg-indigo-500/10 blur-[140px]"
        aria-hidden="true"
      />
      <div
        className="pointer-events-none absolute -bottom-40 right-10 h-[500px] w-[500px] rounded-full bg-sky-500/10 blur-[130px]"
        aria-hidden="true"
      />

      {/* Left Showcase Panel: Visible on md+ screens */}
      <aside
        className="relative hidden md:flex flex-col justify-between p-10 lg:p-14 border-r border-border/70 bg-[#080A0E]/80 backdrop-blur-md studio-glow-cyan"
        aria-label="Architecture telemetry showcase"
      >
        {/* Top Logo with glowing halo */}
        <div>
          <div className="flex items-center gap-3">
            <div className="flex size-11 items-center justify-center rounded-xl bg-gradient-to-br from-cyan-500/20 to-indigo-500/20 border border-cyan-500/30 text-cyan-400 studio-glow-cyan shadow-lg">
              <Compass className="h-5 w-5" />
            </div>
            <div>
              <span className="text-base font-semibold tracking-tight text-foreground">Compass Studio</span>
              <span className="ml-2 rounded-full border border-cyan-500/30 bg-cyan-500/10 px-2 py-0.5 text-[10px] font-mono text-cyan-400 font-medium">
                v2.0 Enterprise
              </span>
            </div>
          </div>

          {/* Heading */}
          <div className="mt-12 mb-8">
            <h2 className="text-3xl lg:text-4xl font-bold tracking-tight text-foreground leading-tight">
              Autonomous Software <br />
              <span className="bg-gradient-to-r from-cyan-400 via-sky-300 to-indigo-400 bg-clip-text text-transparent">
                Engineering Studio
              </span>
            </h2>
            <p className="mt-3 text-xs lg:text-sm text-muted-foreground leading-relaxed max-w-lg">
              Full-lifecycle autonomous developer studio combining real-time visual canvas inspection with deep deterministic terminal orchestration.
            </p>
          </div>

          {/* Live Architecture Telemetry Ticker */}
          <div className="space-y-3 max-w-lg">
            <div className="text-[11px] font-mono font-medium text-muted-foreground tracking-wider uppercase">
              Architecture Telemetry
            </div>

            {/* Agent State Machine */}
            <div className="rounded-xl border border-border/80 bg-[#0D1117]/80 p-3.5 backdrop-blur-sm transition-all hover:border-cyan-500/40">
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs font-semibold text-foreground flex items-center gap-2">
                  <Workflow className="h-4 w-4 text-cyan-400 shrink-0" />
                  Agent State Machine
                </span>
                <span className="flex items-center gap-1.5 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-2 py-0.5 text-[11px] font-mono text-emerald-400">
                  <span className="size-1.5 rounded-full bg-emerald-400 animate-pulse" />
                  Graph Workflow: Active
                </span>
              </div>
              <p className="text-xs text-muted-foreground">
                Deterministic LangGraph agent orchestration with automated checkpoints & rollback safety.
              </p>
            </div>

            {/* Execution Sandboxes */}
            <div className="rounded-xl border border-border/80 bg-[#0D1117]/80 p-3.5 backdrop-blur-sm transition-all hover:border-cyan-500/40">
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs font-semibold text-foreground flex items-center gap-2">
                  <Cpu className="h-4 w-4 text-indigo-400 shrink-0" />
                  Execution Sandboxes
                </span>
                <span className="text-[11px] font-mono text-cyan-400 font-medium">
                  Subprocess Local Runner + Cloud E2B Firecracker
                </span>
              </div>
              <p className="text-xs text-muted-foreground">
                Zero-latency host terminal execution with microVM cloud fallback for untrusted workloads.
              </p>
            </div>

            {/* Hybrid Safety Gate */}
            <div className="rounded-xl border border-border/80 bg-[#0D1117]/80 p-3.5 backdrop-blur-sm transition-all hover:border-cyan-500/40">
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs font-semibold text-foreground flex items-center gap-2">
                  <ShieldCheck className="h-4 w-4 text-emerald-400 shrink-0" />
                  Hybrid Safety Gate
                </span>
                <span className="text-[11px] font-mono text-emerald-400 font-medium">
                  Policy Governed
                </span>
              </div>
              <p className="text-xs text-muted-foreground">
                Auto-approves safe tests, gates destructive changes with human-in-the-loop review.
              </p>
            </div>

            {/* Dual-Telemetry Studio */}
            <div className="rounded-xl border border-border/80 bg-[#0D1117]/80 p-3.5 backdrop-blur-sm transition-all hover:border-cyan-500/40">
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs font-semibold text-foreground flex items-center gap-2">
                  <Terminal className="h-4 w-4 text-sky-400 shrink-0" />
                  Dual-Telemetry Studio
                </span>
                <span className="text-[11px] font-mono text-sky-400 font-medium">
                  Canvas visual inspector + terminal cockpit
                </span>
              </div>
              <p className="text-xs text-muted-foreground">
                Bidir WebSocket telemetry streaming real-time shell stdout, test runs, and interactive DOM selection.
              </p>
            </div>
          </div>
        </div>

        {/* Bottom: Capability Tags */}
        <div className="pt-6 border-t border-border/50">
          <div className="text-[10px] font-mono text-muted-foreground uppercase tracking-wider mb-2.5">
            Integrated Stack & Capabilities
          </div>
          <div className="flex flex-wrap gap-2">
            {CAPABILITY_TAGS.map((tag) => (
              <span
                key={tag}
                className="cursor-default rounded-md border border-border/80 bg-[#0D1117] px-2.5 py-1 text-xs font-mono text-muted-foreground hover:text-cyan-400 hover:border-cyan-500/40 transition-colors"
              >
                {tag}
              </span>
            ))}
          </div>
        </div>
      </aside>

      {/* Right Auth Panel: Centered column with subtle glass styling */}
      <main className="relative flex min-h-screen w-full items-center justify-center p-6 lg:p-12 bg-[#0D1117]/60">
        <div className="w-full max-w-md">
          <AuthSurface
            onSuccess={() => {
              navigate("/chat", { replace: true });
            }}
          />
        </div>
      </main>
    </div>
  );
}
