import { useCallback, useContext, useEffect, useRef, useState } from "react";
import type { WebContainer as WebContainerInstance, WebContainerProcess } from "@webcontainer/api";
import {
  ExternalLink,
  Globe,
  Loader2,
  Monitor,
  MousePointerClick,
  Play,
  RefreshCcw,
  Smartphone,
  Square,
  Tablet,
  Terminal,
  X,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { toast } from "react-toastify";
import { WorkbenchContext } from "@/contexts/WorkbenchContext";
import { DOM_INSPECTOR_SCRIPT } from "@/components/preview/domInspector";

type PreviewFiles = Record<string, { file?: { contents: string } }>;
type PreviewState = "idle" | "booting" | "installing" | "running" | "ready" | "error";

let container: WebContainerInstance | null = null;
let bootPromise: Promise<WebContainerInstance> | null = null;
let teardownPromise: Promise<void> = Promise.resolve();

async function getContainer() {
  await teardownPromise;
  if (container) return container;
  if (!bootPromise) {
    const pending = import("@webcontainer/api").then(({ WebContainer }) => WebContainer.boot());
    bootPromise = pending;
    void pending.then((instance) => {
      if (bootPromise === pending) container = instance;
    });
  }
  return bootPromise;
}

async function disposeContainer() {
  const current = container;
  const pending = bootPromise;
  container = null;
  bootPromise = null;
  teardownPromise = teardownPromise.then(async () => {
    const instance = current ?? await pending?.catch(() => null);
    await instance?.teardown();
  });
  await teardownPromise;
}

function previewScript(files: PreviewFiles): string {
  const source = files["package.json"]?.file?.contents;
  if (!source) throw new Error("Preview requires a package.json file.");
  let parsed: { scripts?: Record<string, string> };
  try {
    parsed = JSON.parse(source) as { scripts?: Record<string, string> };
  } catch {
    throw new Error("package.json is not valid JSON.");
  }
  const scripts = parsed.scripts ?? {};
  const script = ["dev", "start", "preview"].find((name) => scripts[name]);
  if (!script) throw new Error("package.json needs a dev, start, or preview script.");
  return script;
}

export default function WebPreview({
  files,
  visible,
  onClose,
}: {
  files?: PreviewFiles;
  visible: boolean;
  onClose: () => void;
}) {
  const workbench = useContext(WorkbenchContext);
  const viewportMode = workbench?.state?.viewportMode ?? "desktop";
  const isInspectActive = workbench?.state?.inspectActive ?? false;
  const dispatch = workbench?.dispatch;

  const iframeRef = useRef<HTMLIFrameElement>(null);
  const containerRef = useRef<WebContainerInstance | null>(null);
  const processRef = useRef<WebContainerProcess | null>(null);
  const unsubscribeRef = useRef<Array<() => void>>([]);
  const generationRef = useRef(0);
  const logBufferRef = useRef<string[]>([]);
  const logTimerRef = useRef<number | null>(null);
  const [state, setState] = useState<PreviewState>("idle");
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [logs, setLogs] = useState<string[]>([]);
  const [showOutput, setShowOutput] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const flushLogs = useCallback(() => {
    logTimerRef.current = null;
    const pending = logBufferRef.current.splice(0);
    if (pending.length) setLogs((items) => [...items, ...pending].slice(-200));
  }, []);

  const log = useCallback((message: string) => {
    logBufferRef.current.push(message);
    logTimerRef.current ??= window.setTimeout(flushLogs, 100);
  }, [flushLogs]);

  const cleanExecution = useCallback(() => {
    processRef.current?.kill();
    processRef.current = null;
    unsubscribeRef.current.splice(0).forEach((unsubscribe) => unsubscribe());
  }, []);

  const stop = useCallback(async () => {
    generationRef.current += 1;
    cleanExecution();
    if (logTimerRef.current != null) window.clearTimeout(logTimerRef.current);
    logTimerRef.current = null;
    logBufferRef.current = [];
    containerRef.current = null;
    setState("idle");
    setPreviewUrl(null);
    await disposeContainer();
  }, [cleanExecution]);

  // Click-to-Inspect postMessage receiver
  useEffect(() => {
    const handleMessage = (event: MessageEvent) => {
      if (!event.data || typeof event.data !== "object") return;
      if (event.data.type === "COMPASS_ELEMENT_SELECTED") {
        const payload = event.data.payload;
        dispatch?.({ type: "setInspectedElement", element: payload });
        dispatch?.({ type: "setMode", mode: "edit" });
        toast.info(`Inspecting <${payload.tag}>: prompt context attached`);
      }
    };
    window.addEventListener("message", handleMessage);
    return () => window.removeEventListener("message", handleMessage);
  }, [dispatch]);

  // Sync inspect active state to iframe
  useEffect(() => {
    if (state === "ready" && iframeRef.current?.contentWindow) {
      iframeRef.current.contentWindow.postMessage(
        { type: "COMPASS_INSPECT_MODE", active: isInspectActive },
        "*"
      );
    }
  }, [isInspectActive, state]);

  const start = useCallback(async () => {
    if (!files || !Object.keys(files).length) return;
    cleanExecution();
    const generation = ++generationRef.current;
    setState("booting");
    setError(null);
    setLogs([]);
    try {
      const script = previewScript(files);
      log("Booting preview runtime…\n");
      const current = await getContainer();
      if (generation !== generationRef.current) return;
      containerRef.current = current;

      log("Mounting workspace files with DOM Inspector…\n");
      // Inject the DOM inspector script into index.html if present
      const preparedFiles: PreviewFiles = { ...files };
      if (preparedFiles["index.html"]?.file?.contents) {
        let html = preparedFiles["index.html"].file.contents;
        if (!html.includes("__COMPASS_INSPECTOR_INITIALIZED__")) {
          const scriptTag = `<script>\n${DOM_INSPECTOR_SCRIPT}\n</script>`;
          if (html.includes("</body>")) {
            html = html.replace("</body>", `${scriptTag}\n</body>`);
          } else {
            html = `${html}\n${scriptTag}`;
          }
          preparedFiles["index.html"] = { file: { contents: html } };
        }
      }
      await current.mount(preparedFiles as never);
      if (generation !== generationRef.current) return;

      setState("installing");
      log("Installing dependencies…\n");
      const install = await current.spawn("npm", ["install"]);
      processRef.current = install;
      void install.output
        .pipeTo(new WritableStream({ write: (chunk) => log(chunk) }))
        .catch(() => undefined);
      const installExit = await install.exit;
      if (generation !== generationRef.current) return;
      processRef.current = null;
      if (installExit !== 0)
        throw new Error(`Dependency installation exited with code ${installExit}.`);

      setState("running");
      log(`Starting npm run ${script}…\n`);
      let serverReady = false;
      unsubscribeRef.current = [
        current.on("server-ready", (_port, url) => {
          if (generation !== generationRef.current) return;
          serverReady = true;
          setPreviewUrl(url);
          setState("ready");
          log(`Server ready at ${url}\n`);
          if (iframeRef.current) iframeRef.current.src = url;
        }),
        current.on("error", (nextError) => {
          if (generation !== generationRef.current) return;
          setError(nextError.message);
          setState("error");
          log(`Error: ${nextError.message}\n`);
        }),
      ];
      const server = await current.spawn("npm", ["run", script]);
      if (generation !== generationRef.current) {
        server.kill();
        return;
      }
      processRef.current = server;
      void server.output
        .pipeTo(new WritableStream({ write: (chunk) => log(chunk) }))
        .catch(() => undefined);
      void server.exit.then((code) => {
        if (generation !== generationRef.current) return;
        const message = serverReady
          ? `Preview server stopped with code ${code}.`
          : `Preview server exited with code ${code} before it became ready.`;
        setError(message);
        setState("error");
        log(`Error: ${message}\n`);
      });
    } catch (caught) {
      if (generation !== generationRef.current) return;
      const message = caught instanceof Error ? caught.message : "Could not start the preview";
      setError(message);
      setState("error");
      log(`Error: ${message}\n`);
    }
  }, [cleanExecution, files, log]);

  useEffect(() => () => { void stop(); }, [stop]);

  if (!visible) return null;

  const working = state === "booting" || state === "installing" || state === "running";

  return (
    <section className="flex h-full min-h-0 flex-col bg-background">
      <header className="flex h-11 shrink-0 items-center justify-between border-b border-border bg-card/60 px-3 backdrop-blur">
        {/* Left side: Status indicator & Live badge */}
        <div className="flex min-w-0 items-center gap-2 text-xs font-medium">
          <Globe className="h-4 w-4 text-primary" />
          <span className="font-semibold">Canvas</span>
          {state === "ready" && (
            <span className="flex items-center gap-1 rounded bg-emerald-500/10 px-1.5 py-0.5 text-[11px] font-semibold text-emerald-500">
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 animate-pulse" />
              Live
            </span>
          )}
          {working && (
            <span className="flex items-center gap-1 text-warning">
              <Loader2 className="h-3 w-3 animate-spin" /> {state}
            </span>
          )}
        </div>

        {/* Center: Viewport & Click-to-Inspect controls */}
        {state === "ready" && (
          <div className="flex items-center gap-1 rounded-md border border-border bg-muted/40 p-0.5">
            <button
              type="button"
              onClick={() => dispatch?.({ type: "setInspectActive", active: !isInspectActive })}
              className={`flex items-center gap-1.5 rounded px-2.5 py-1 text-xs font-medium transition-all ${
                isInspectActive
                  ? "bg-sky-500 text-white shadow-sm ring-2 ring-sky-400/50"
                  : "text-muted-foreground hover:bg-muted hover:text-foreground"
              }`}
              title="Click-to-Inspect DOM Element"
            >
              <MousePointerClick className="h-3.5 w-3.5" />
              <span>Inspect</span>
              {isInspectActive && <span className="h-1.5 w-1.5 rounded-full bg-white animate-pulse" />}
            </button>
            <div className="h-4 w-px bg-border mx-0.5" />
            <button
              type="button"
              onClick={() => dispatch?.({ type: "setViewportMode", mode: "desktop" })}
              className={`rounded p-1 transition-colors ${
                viewportMode === "desktop"
                  ? "bg-background text-foreground shadow-sm"
                  : "text-muted-foreground hover:text-foreground"
              }`}
              title="Desktop viewport (100%)"
            >
              <Monitor className="h-3.5 w-3.5" />
            </button>
            <button
              type="button"
              onClick={() => dispatch?.({ type: "setViewportMode", mode: "tablet" })}
              className={`rounded p-1 transition-colors ${
                viewportMode === "tablet"
                  ? "bg-background text-foreground shadow-sm"
                  : "text-muted-foreground hover:text-foreground"
              }`}
              title="Tablet viewport (768px)"
            >
              <Tablet className="h-3.5 w-3.5" />
            </button>
            <button
              type="button"
              onClick={() => dispatch?.({ type: "setViewportMode", mode: "mobile" })}
              className={`rounded p-1 transition-colors ${
                viewportMode === "mobile"
                  ? "bg-background text-foreground shadow-sm"
                  : "text-muted-foreground hover:text-foreground"
              }`}
              title="Mobile viewport (375px)"
            >
              <Smartphone className="h-3.5 w-3.5" />
            </button>
          </div>
        )}

        {/* Right side: Actions */}
        <div className="flex items-center gap-1">
          {state === "idle" && (
            <Button
              size="sm"
              variant="ghost"
              onClick={() => void start()}
              disabled={!files || !Object.keys(files).length}
            >
              <Play className="h-3.5 w-3.5 mr-1" /> Run
            </Button>
          )}
          {state === "ready" && (
            <>
              <Button
                size="icon-sm"
                variant="ghost"
                onClick={() => {
                  if (previewUrl && iframeRef.current) iframeRef.current.src = previewUrl;
                }}
                aria-label="Refresh preview"
              >
                <RefreshCcw className="h-4 w-4" />
              </Button>
              {previewUrl && (
                <a
                  href={previewUrl}
                  target="_blank"
                  rel="noreferrer"
                  className="rounded p-1 text-muted-foreground hover:bg-muted hover:text-foreground"
                  aria-label="Open preview in a new tab"
                >
                  <ExternalLink className="h-4 w-4" />
                </a>
              )}
            </>
          )}
          {state !== "idle" && (
            <Button size="icon-sm" variant="ghost" onClick={() => void stop()} aria-label="Stop preview">
              <Square className="h-4 w-4" />
            </Button>
          )}
          <Button
            size="icon-sm"
            variant="ghost"
            onClick={() => setShowOutput((value) => !value)}
            aria-label="Toggle preview output"
          >
            <Terminal className="h-4 w-4" />
          </Button>
          <Button size="icon-sm" variant="ghost" onClick={onClose} aria-label="Close preview">
            <X className="h-4 w-4" />
          </Button>
        </div>
      </header>

      {/* Main Preview Canvas Area */}
      <div className="relative min-h-0 flex-1 overflow-auto bg-muted/20 flex flex-col items-center justify-center p-2">
        {state === "idle" && (
          <Empty
            icon={<Globe className="h-8 w-8 text-primary" />}
            title="Preview Canvas"
            text="Start the preview server to inspect your web application in real time with interactive element selection."
            action={
              <Button size="sm" onClick={() => void start()} disabled={!files || !Object.keys(files).length}>
                <Play className="h-4 w-4 mr-1.5" /> Start Preview
              </Button>
            }
          />
        )}
        {working && (
          <Empty
            icon={<Loader2 className="h-8 w-8 animate-spin text-primary" />}
            title="Starting Development Server"
            text={state === "installing" ? "Installing dependencies…" : "Starting dev server…"}
          />
        )}
        {state === "error" && (
          <Empty
            icon={<X className="h-8 w-8 text-destructive" />}
            title="Preview could not start"
            text={error || "Review the output logs and try again."}
            action={
              <div className="flex flex-wrap items-center justify-center gap-2">
                <Button size="sm" variant="outline" onClick={() => void start()}>
                  <RefreshCcw className="h-4 w-4 mr-1.5" /> Retry
                </Button>
                {error?.includes("package.json") && (
                  <>
                    <Button
                      size="sm"
                      variant="secondary"
                      onClick={() => workbench?.dispatch?.({ type: "setCenterTab", tab: "editor" })}
                    >
                      Open Editor
                    </Button>
                    <Button
                      size="sm"
                      variant="secondary"
                      onClick={() => workbench?.dispatch?.({ type: "setProDrawer", open: true })}
                    >
                      Open Terminal
                    </Button>
                  </>
                )}
              </div>
            }
          />
        )}
        {state === "ready" && (
          <div
            className={`h-full transition-all duration-200 flex flex-col ${
              viewportMode === "desktop"
                ? "w-full"
                : viewportMode === "tablet"
                ? "w-[768px] max-w-full my-auto rounded-lg shadow-2xl border border-border/80 overflow-hidden bg-background"
                : "w-[375px] max-w-full h-[667px] my-auto rounded-3xl shadow-2xl border-4 border-muted-foreground/30 overflow-hidden bg-background"
            }`}
          >
            {viewportMode !== "desktop" && (
              <div className="flex h-6 shrink-0 items-center justify-center bg-muted/60 border-b border-border text-[10px] font-mono text-muted-foreground">
                {viewportMode === "tablet" ? "iPad / Tablet (768px)" : "Mobile Device (375 × 667)"}
              </div>
            )}
            <iframe
              ref={iframeRef}
              title="Workspace preview"
              className="h-full w-full border-0 bg-card"
              sandbox="allow-scripts allow-same-origin allow-forms allow-popups allow-modals"
              onLoad={() => {
                if (isInspectActive && iframeRef.current?.contentWindow) {
                  iframeRef.current.contentWindow.postMessage(
                    { type: "COMPASS_INSPECT_MODE", active: true },
                    "*"
                  );
                }
              }}
            />
          </div>
        )}
      </div>

      {/* Terminal Output Panel */}
      {showOutput && (
        <div className="h-36 shrink-0 overflow-auto border-t border-border bg-card">
          <div className="flex h-7 items-center border-b border-border bg-muted/40 px-3 text-xs font-medium text-muted-foreground">
            <Terminal className="mr-1.5 h-3.5 w-3.5" /> Console Output
          </div>
          <pre className="whitespace-pre-wrap p-2 font-mono text-xs leading-relaxed text-muted-foreground">
            {logs.length ? logs.join("") : "No output yet."}
          </pre>
        </div>
      )}
    </section>
  );
}

function Empty({
  icon,
  title,
  text,
  action,
}: {
  icon: React.ReactNode;
  title: string;
  text: string;
  action?: React.ReactNode;
}) {
  return (
    <div className="flex h-full flex-col items-center justify-center p-6 text-center">
      <span className="mb-4">{icon}</span>
      <h3 className="text-sm font-semibold">{title}</h3>
      <p className="mt-1 max-w-xs text-xs leading-5 text-muted-foreground">{text}</p>
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}
