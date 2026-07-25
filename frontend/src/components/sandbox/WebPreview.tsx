import { useCallback, useEffect, useRef, useState } from "react";
import { WebContainer } from "@webcontainer/api";
import { ExternalLink, Globe, Loader2, Play, RefreshCcw, Square, Terminal, X } from "lucide-react";
import { Button } from "@/components/ui/button";

type PreviewFiles = Record<string, { file?: { contents: string } }>;
type PreviewState = "idle" | "booting" | "installing" | "running" | "ready" | "error";

let container: WebContainer | null = null;
let bootPromise: Promise<WebContainer> | null = null;

async function getContainer() {
  if (container) return container;
  bootPromise ||= WebContainer.boot().then((instance) => { container = instance; return instance; });
  return bootPromise;
}

export default function WebPreview({ files, visible, onClose }: { files?: PreviewFiles; visible: boolean; onClose: () => void }) {
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const containerRef = useRef<WebContainer | null>(null);
  const [state, setState] = useState<PreviewState>("idle");
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [logs, setLogs] = useState<string[]>([]);
  const [showOutput, setShowOutput] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const log = useCallback((message: string) => setLogs((items) => [...items.slice(-199), message]), []);
  const stop = useCallback(() => {
    containerRef.current?.teardown();
    containerRef.current = null;
    container = null;
    bootPromise = null;
    setState("idle");
    setPreviewUrl(null);
  }, []);

  const start = useCallback(async () => {
    if (!files || !Object.keys(files).length) return;
    setState("booting"); setError(null); setLogs([]);
    try {
      log("Booting WebContainer…\n");
      const current = await getContainer();
      containerRef.current = current;
      log("Mounting workspace files…\n");
      await current.mount(files as never);
      const packageFile = files["package.json"]?.file?.contents;
      if (packageFile) {
        setState("installing"); log("Installing dependencies…\n");
        const install = await current.spawn("npm", ["install"]);
        void install.output.pipeTo(new WritableStream({ write: (chunk) => log(chunk) }));
        if (await install.exit) throw new Error("Dependency installation failed");
      }
      let script = "start";
      if (packageFile) {
        try { const parsed = JSON.parse(packageFile) as { scripts?: Record<string, string> }; script = parsed.scripts?.dev ? "dev" : parsed.scripts?.start ? "start" : parsed.scripts?.preview ? "preview" : script; } catch { /* Use the default script. */ }
      }
      setState("running"); log(`Starting npm run ${script}…\n`);
      const server = await current.spawn("npm", ["run", script]);
      void server.output.pipeTo(new WritableStream({ write: (chunk) => log(chunk) }));
      current.on("server-ready", (_port, url) => { setPreviewUrl(url); setState("ready"); log(`Server ready at ${url}\n`); if (iframeRef.current) iframeRef.current.src = url; });
      current.on("error", (nextError) => { setError(nextError.message); setState("error"); log(`Error: ${nextError.message}\n`); });
    } catch (caught) {
      const message = caught instanceof Error ? caught.message : "Could not start the preview";
      setError(message); setState("error"); log(`Error: ${message}\n`);
    }
  }, [files, log]);

  useEffect(() => () => stop(), [stop]);
  if (!visible) return null;

  const working = state === "booting" || state === "installing" || state === "running";
  return <section className="flex h-full min-h-0 flex-col bg-background">
    <header className="flex h-10 shrink-0 items-center justify-between border-b border-border px-3">
      <div className="flex min-w-0 items-center gap-2 text-xs font-medium"><Globe className="h-4 w-4 text-primary" /><span>Preview</span>{state === "ready" && <span className="text-success">Live</span>}{working && <span className="flex items-center gap-1 text-warning"><Loader2 className="h-3 w-3 animate-spin" /> {state}</span>}</div>
      <div className="flex items-center gap-1">
        {state === "idle" && <Button size="sm" variant="ghost" onClick={() => void start()} disabled={!files || !Object.keys(files).length}><Play className="h-4 w-4" /> Run</Button>}
        {state === "ready" && <><Button size="icon-sm" variant="ghost" onClick={() => { if (previewUrl && iframeRef.current) iframeRef.current.src = previewUrl; }} aria-label="Refresh preview"><RefreshCcw className="h-4 w-4" /></Button>{previewUrl && <a href={previewUrl} target="_blank" rel="noreferrer" className="rounded p-1 text-muted-foreground hover:bg-muted hover:text-foreground" aria-label="Open preview in a new tab"><ExternalLink className="h-4 w-4" /></a>}</>}
        {state !== "idle" && <Button size="icon-sm" variant="ghost" onClick={stop} aria-label="Stop preview"><Square className="h-4 w-4" /></Button>}
        <Button size="icon-sm" variant="ghost" onClick={() => setShowOutput((value) => !value)} aria-label="Toggle preview output"><Terminal className="h-4 w-4" /></Button>
        <Button size="icon-sm" variant="ghost" onClick={onClose} aria-label="Close preview"><X className="h-4 w-4" /></Button>
      </div>
    </header>
    <div className="relative min-h-0 flex-1">
      {state === "idle" && <Empty icon={<Globe className="h-7 w-7" />} title="Preview this project" text="Start a sandboxed browser preview for the current workspace." action={<Button size="sm" onClick={() => void start()} disabled={!files || !Object.keys(files).length}><Play className="h-4 w-4" /> Start preview</Button>} />}
      {working && <Empty icon={<Loader2 className="h-7 w-7 animate-spin" />} title="Preparing preview" text={state === "installing" ? "Installing dependencies" : "Starting the project"} />}
      {state === "error" && <Empty icon={<X className="h-7 w-7" />} title="Preview could not start" text={error || "Review the output and try again."} action={<Button size="sm" variant="outline" onClick={() => void start()}><RefreshCcw className="h-4 w-4" /> Retry</Button>} />}
      {state === "ready" && <iframe ref={iframeRef} title="Workspace preview" className="h-full w-full border-0 bg-card" sandbox="allow-scripts allow-same-origin allow-forms allow-popups allow-modals" />}
    </div>
    {showOutput && <div className="h-36 shrink-0 overflow-auto border-t border-border"><div className="flex h-7 items-center border-b border-border bg-muted/20 px-3 text-xs font-medium text-muted-foreground"><Terminal className="mr-1.5 h-3.5 w-3.5" /> Output</div><pre className="whitespace-pre-wrap p-2 font-mono text-xs leading-relaxed text-muted-foreground">{logs.length ? logs.join("") : "No output yet."}</pre></div>}
  </section>;
}

function Empty({ icon, title, text, action }: { icon: React.ReactNode; title: string; text: string; action?: React.ReactNode }) {
  return <div className="flex h-full flex-col items-center justify-center p-6 text-center"><span className="mb-4 text-primary">{icon}</span><h3 className="text-sm font-semibold">{title}</h3><p className="mt-1 max-w-xs text-xs leading-5 text-muted-foreground">{text}</p>{action && <div className="mt-4">{action}</div>}</div>;
}
