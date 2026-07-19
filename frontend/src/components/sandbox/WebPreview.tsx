import { useEffect, useRef, useState, useCallback } from "react";
import { WebContainer } from "@webcontainer/api";
import {
  ExternalLink,
  Loader2,
  Play,
  RefreshCcw,
  Square,
  Terminal,
  X,
  Globe,
  ChevronDown,
  ChevronUp,
} from "lucide-react";
import { Button } from "@/components/ui/button";

interface WebPreviewProps {
  /** Files to mount in the WebContainer: { [path]: { file: { contents: string } } } */
  files?: Record<string, any>;
  /** Whether the panel is visible */
  visible: boolean;
  onClose: () => void;
}

let _instance: WebContainer | null = null;
let _booting = false;
const _bootQueue: Array<(wc: WebContainer) => void> = [];

async function getWebContainer(): Promise<WebContainer> {
  if (_instance) return _instance;
  if (_booting) {
    return new Promise((resolve) => _bootQueue.push(resolve));
  }
  _booting = true;
  const wc = await WebContainer.boot();
  _instance = wc;
  _booting = false;
  _bootQueue.forEach((cb) => cb(wc));
  _bootQueue.length = 0;
  return wc;
}

export default function WebPreview({ files, visible, onClose }: WebPreviewProps) {
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const [status, setStatus] = useState<"idle" | "booting" | "installing" | "running" | "ready" | "error">("idle");
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [logs, setLogs] = useState<string[]>([]);
  const [showTerminal, setShowTerminal] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const wcRef = useRef<WebContainer | null>(null);

  const appendLog = useCallback((line: string) => {
    setLogs((prev) => [...prev.slice(-200), line]);
  }, []);

  const startPreview = useCallback(async () => {
    if (!files || Object.keys(files).length === 0) return;

    try {
      setStatus("booting");
      setError(null);
      setLogs([]);
      appendLog("⏳ Booting WebContainer...");

      const wc = await getWebContainer();
      wcRef.current = wc;

      appendLog("📂 Mounting files...");
      await wc.mount(files);

      // Check if package.json exists to determine if we need npm install
      const hasPackageJson = "package.json" in files;

      if (hasPackageJson) {
        setStatus("installing");
        appendLog("📦 Running npm install...");

        const installProcess = await wc.spawn("npm", ["install"]);
        installProcess.output.pipeTo(
          new WritableStream({
            write(chunk) {
              appendLog(chunk);
            },
          })
        );
        const installExitCode = await installProcess.exit;
        if (installExitCode !== 0) {
          throw new Error(`npm install failed with exit code ${installExitCode}`);
        }
        appendLog("✅ Dependencies installed");
      }

      setStatus("running");
      appendLog("🚀 Starting dev server...");

      // Try to detect the start script
      let startCmd = "start";
      if (hasPackageJson) {
        try {
          const pkgContent = typeof files["package.json"] === "object" && files["package.json"].file
            ? files["package.json"].file.contents
            : "";
          if (pkgContent) {
            const pkg = JSON.parse(pkgContent);
            if (pkg.scripts?.dev) startCmd = "dev";
            else if (pkg.scripts?.start) startCmd = "start";
            else if (pkg.scripts?.preview) startCmd = "preview";
          }
        } catch {
          // fallback
        }
      }

      const devProcess = await wc.spawn("npm", ["run", startCmd]);
      devProcess.output.pipeTo(
        new WritableStream({
          write(chunk) {
            appendLog(chunk);
          },
        })
      );

      wc.on("server-ready", (_port, url) => {
        setPreviewUrl(url);
        setStatus("ready");
        appendLog(`✅ Server ready at ${url}`);
        if (iframeRef.current) {
          iframeRef.current.src = url;
        }
      });

      wc.on("error", (err) => {
        appendLog(`❌ Error: ${err.message}`);
        setError(err.message);
        setStatus("error");
      });
    } catch (err: any) {
      setError(err.message || "Failed to start WebContainer");
      setStatus("error");
      appendLog(`❌ ${err.message}`);
    }
  }, [files, appendLog]);

  const handleRefresh = () => {
    if (previewUrl && iframeRef.current) {
      iframeRef.current.src = previewUrl;
    }
  };

  const handleStop = async () => {
    if (wcRef.current) {
      wcRef.current.teardown();
      wcRef.current = null;
      _instance = null;
    }
    setStatus("idle");
    setPreviewUrl(null);
    setLogs([]);
  };

  useEffect(() => {
    return () => {
      // Cleanup on unmount
      if (wcRef.current) {
        wcRef.current.teardown();
        wcRef.current = null;
        _instance = null;
      }
    };
  }, []);

  if (!visible) return null;

  return (
    <div className="flex h-full flex-col border-l border-border bg-background">
      {/* Header */}
      <div className="flex h-10 shrink-0 items-center justify-between border-b border-border px-3 bg-muted/30">
        <div className="flex items-center gap-2 text-xs font-medium">
          <Globe className="h-3.5 w-3.5 text-primary" />
          <span>Live Preview</span>
          {status === "ready" && (
            <span className="flex items-center gap-1 text-green-500">
              <span className="h-1.5 w-1.5 rounded-full bg-green-500 animate-pulse" />
              Live
            </span>
          )}
          {(status === "booting" || status === "installing" || status === "running") && (
            <span className="flex items-center gap-1 text-amber-500">
              <Loader2 className="h-3 w-3 animate-spin" />
              {status === "booting" ? "Booting" : status === "installing" ? "Installing" : "Starting"}
            </span>
          )}
        </div>
        <div className="flex items-center gap-1">
          {status === "idle" && (
            <Button
              size="sm"
              variant="ghost"
              className="h-7 text-xs text-muted-foreground hover:text-foreground"
              onClick={startPreview}
            >
              <Play className="h-3 w-3 mr-1" /> Run
            </Button>
          )}
          {status === "ready" && (
            <>
              <Button
                size="sm"
                variant="ghost"
                className="h-7 w-7 p-0 text-muted-foreground hover:text-foreground"
                onClick={handleRefresh}
                title="Refresh preview"
              >
                <RefreshCcw className="h-3 w-3" />
              </Button>
              {previewUrl && (
                <a
                  href={previewUrl}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex h-7 w-7 items-center justify-center rounded-md text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
                  title="Open in new tab"
                >
                  <ExternalLink className="h-3 w-3" />
                </a>
              )}
            </>
          )}
          {status !== "idle" && (
            <Button
              size="sm"
              variant="ghost"
              className="h-7 w-7 p-0 text-muted-foreground hover:text-red-400"
              onClick={handleStop}
              title="Stop"
            >
              <Square className="h-3 w-3" />
            </Button>
          )}
          <Button
            size="sm"
            variant="ghost"
            className="h-7 w-7 p-0 text-muted-foreground hover:text-foreground"
            onClick={() => setShowTerminal(!showTerminal)}
            title="Toggle terminal"
          >
            {showTerminal ? <ChevronDown className="h-3 w-3" /> : <Terminal className="h-3 w-3" />}
          </Button>
          <Button
            size="sm"
            variant="ghost"
            className="h-7 w-7 p-0 text-muted-foreground hover:text-foreground"
            onClick={onClose}
            title="Close preview"
          >
            <X className="h-3 w-3" />
          </Button>
        </div>
      </div>

      {/* Preview Area */}
      <div className="flex-1 min-h-0 relative">
        {status === "idle" && (
          <div className="flex h-full flex-col items-center justify-center text-center p-6">
            <div className="flex size-14 items-center justify-center rounded-2xl bg-primary/10 text-primary mb-4">
              <Globe className="h-7 w-7" />
            </div>
            <h3 className="text-sm font-semibold mb-1">Live Preview</h3>
            <p className="text-xs text-muted-foreground max-w-[240px] mb-4">
              Run your project in a sandboxed browser environment powered by WebContainers
            </p>
            <Button size="sm" onClick={startPreview} className="rounded-full" disabled={!files || Object.keys(files).length === 0}>
              <Play className="h-3.5 w-3.5 mr-1.5" /> Start Preview
            </Button>
            {(!files || Object.keys(files).length === 0) && (
              <p className="text-[10px] text-muted-foreground/60 mt-2">
                No files loaded. Open a workspace first.
              </p>
            )}
          </div>
        )}

        {status === "error" && (
          <div className="flex h-full flex-col items-center justify-center text-center p-6">
            <div className="flex size-14 items-center justify-center rounded-2xl bg-red-500/10 text-red-500 mb-4">
              <X className="h-7 w-7" />
            </div>
            <h3 className="text-sm font-semibold text-red-400 mb-1">Preview Failed</h3>
            <p className="text-xs text-muted-foreground max-w-[300px] mb-4">
              {error || "An unexpected error occurred"}
            </p>
            <Button size="sm" variant="outline" onClick={startPreview} className="rounded-full">
              <RefreshCcw className="h-3.5 w-3.5 mr-1.5" /> Retry
            </Button>
          </div>
        )}

        {(status === "booting" || status === "installing" || status === "running") && (
          <div className="flex h-full flex-col items-center justify-center text-center p-6">
            <Loader2 className="h-8 w-8 animate-spin text-primary mb-4" />
            <p className="text-sm text-muted-foreground">
              {status === "booting"
                ? "Booting WebContainer…"
                : status === "installing"
                  ? "Installing dependencies…"
                  : "Starting dev server…"}
            </p>
          </div>
        )}

        {status === "ready" && (
          <iframe
            ref={iframeRef}
            title="WebContainer Preview"
            className="h-full w-full border-none bg-white"
            sandbox="allow-scripts allow-same-origin allow-forms allow-popups allow-modals"
          />
        )}
      </div>

      {/* Terminal Logs */}
      {showTerminal && (
        <div className="h-36 shrink-0 border-t border-border bg-background overflow-auto">
          <div className="flex h-7 items-center border-b border-border px-3 text-[10px] font-medium text-muted-foreground uppercase tracking-wider bg-muted/20">
            <Terminal className="h-3 w-3 mr-1.5" /> Output
          </div>
          <pre className="p-2 text-[11px] leading-relaxed font-mono text-muted-foreground whitespace-pre-wrap">
            {logs.length === 0 ? "No output yet." : logs.join("")}
          </pre>
        </div>
      )}
    </div>
  );
}
