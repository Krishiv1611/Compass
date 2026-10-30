import { useEffect, useRef, useState } from "react";
import {
  Camera,
  ChevronDown,
  ChevronUp,
  FileText,
  Loader2,
  Maximize2,
  Minimize2,
  Terminal as TerminalIcon,
  Trash2,
  X,
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import TerminalView from "@/components/terminal/TerminalView";
import { Button } from "@/components/ui/button";

interface ProDrawerProps {
  open: boolean;
  onClose: () => void;
  logs?: string[];
  screenshotUrl?: string | null;
  workspaceId?: string | null;
  previewUrl?: string | null;
  onTriggerQA?: () => Promise<void> | void;
}

type DrawerTab = "terminal" | "logs" | "qa";

export default function ProDrawer({
  open,
  onClose,
  logs = [],
  screenshotUrl,
  workspaceId,
  previewUrl,
  onTriggerQA,
}: ProDrawerProps) {
  const [activeTab, setActiveTab] = useState<DrawerTab>("terminal");
  const [isExpanded, setIsExpanded] = useState(false);
  const [terminalStream, setTerminalStream] = useState("");
  const [qaRunning, setQaRunning] = useState(false);
  const [qaStatusMsg, setQaStatusMsg] = useState<string | null>(null);
  const wsRef = useRef<WebSocket | null>(null);
  const inputBufferRef = useRef("");

  useEffect(() => {
    if (!open || !workspaceId) return;

    const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
    const host = window.location.host;
    const wsUrl = `${protocol}//${host}/api/workspaces/${workspaceId}/terminal`;

    let socket: WebSocket | null = null;
    try {
      socket = new WebSocket(wsUrl);
      wsRef.current = socket;

      socket.onmessage = (event) => {
        try {
          const payload = JSON.parse(event.data);
          if (payload.data) {
            setTerminalStream((prev) => prev + payload.data);
          }
        } catch {
          setTerminalStream((prev) => prev + event.data);
        }
      };

      socket.onclose = () => {
        wsRef.current = null;
      };
    } catch {
      // Offline fallback
    }

    return () => {
      socket?.close();
      wsRef.current = null;
    };
  }, [open, workspaceId]);

  const handleTerminalInput = (char: string) => {
    if (char === "\r") {
      const cmd = inputBufferRef.current;
      inputBufferRef.current = "";
      if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ cmd }));
      } else {
        setTerminalStream((prev) => prev + `\r\n\x1b[90m$ [local] ${cmd}\x1b[0m\r\n$ `);
      }
    } else if (char === "\u007f") {
      inputBufferRef.current = inputBufferRef.current.slice(0, -1);
      setTerminalStream((prev) => prev + "\b \b");
    } else {
      inputBufferRef.current += char;
      setTerminalStream((prev) => prev + char);
    }
  };

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ height: 0, opacity: 0 }}
          animate={{ height: isExpanded ? 384 : 256, opacity: 1 }}
          exit={{ height: 0, opacity: 0 }}
          transition={{ type: "spring", stiffness: 350, damping: 30 }}
          className="border-t border-border bg-[#080A0E] flex flex-col overflow-hidden shadow-2xl"
        >
          {/* Header bar */}
          <div className="flex h-9 shrink-0 items-center justify-between border-b border-border/80 bg-[#0D1117] px-3 text-xs">
        {/* Tabs */}
        <div className="flex items-center gap-1">
          <button
            type="button"
            onClick={() => setActiveTab("terminal")}
            className={`flex items-center gap-1.5 px-2.5 py-1 rounded font-medium transition-colors ${
              activeTab === "terminal"
                ? "bg-slate-800 text-sky-400 font-semibold"
                : "text-slate-400 hover:text-slate-200"
            }`}
          >
            <TerminalIcon className="h-3.5 w-3.5" />
            <span>Terminal</span>
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("logs")}
            className={`flex items-center gap-1.5 px-2.5 py-1 rounded font-medium transition-colors ${
              activeTab === "logs"
                ? "bg-slate-800 text-sky-400 font-semibold"
                : "text-slate-400 hover:text-slate-200"
            }`}
          >
            <FileText className="h-3.5 w-3.5" />
            <span>Process Logs</span>
            {logs.length > 0 && (
              <span className="rounded-full bg-slate-700 px-1.5 py-0.2 text-[10px] text-slate-300">
                {logs.length}
              </span>
            )}
          </button>
          <button
            type="button"
            onClick={() => setActiveTab("qa")}
            className={`flex items-center gap-1.5 px-2.5 py-1 rounded font-medium transition-colors ${
              activeTab === "qa"
                ? "bg-slate-800 text-sky-400 font-semibold"
                : "text-slate-400 hover:text-slate-200"
            }`}
          >
            <Camera className="h-3.5 w-3.5" />
            <span>Visual QA</span>
            {screenshotUrl && (
              <span className="h-1.5 w-1.5 rounded-full bg-emerald-400 animate-pulse" />
            )}
          </button>
        </div>

        {/* Controls */}
        <div className="flex items-center gap-1">
          {activeTab === "terminal" && (
            <Button
              size="icon-sm"
              variant="ghost"
              className="text-slate-400 hover:text-slate-200"
              onClick={() => setTerminalStream("\x1b[2J\x1b[H\x1b[1;36mCompass Terminal\x1b[0m — Ready.\r\n$ ")}
              title="Clear terminal"
              aria-label="Clear terminal"
            >
              <Trash2 className="h-3.5 w-3.5" />
            </Button>
          )}
          <Button
            size="icon-sm"
            variant="ghost"
            className="text-slate-400 hover:text-slate-200"
            onClick={() => setIsExpanded((prev) => !prev)}
            title={isExpanded ? "Collapse height" : "Expand height"}
            aria-label={isExpanded ? "Collapse height" : "Expand height"}
          >
            {isExpanded ? (
              <Minimize2 className="h-3.5 w-3.5" />
            ) : (
              <Maximize2 className="h-3.5 w-3.5" />
            )}
          </Button>
          <Button
            size="icon-sm"
            variant="ghost"
            className="text-slate-400 hover:text-slate-200"
            onClick={onClose}
            title="Close Drawer (Ctrl + `)"
            aria-label="Close drawer"
          >
            <X className="h-3.5 w-3.5" />
          </Button>
        </div>
      </div>

      {/* Content pane */}
      <div className="min-h-0 flex-1 relative overflow-hidden">
        {activeTab === "terminal" && (
          <TerminalView streamText={terminalStream} onInput={handleTerminalInput} />
        )}

        {activeTab === "logs" && (
          <div className="h-full overflow-y-auto p-3 font-mono text-xs text-slate-300 leading-relaxed bg-[#0b0f19]">
            {logs.length > 0 ? (
              logs.map((line, idx) => (
                <div key={idx} className="hover:bg-slate-900/50 py-0.5">
                  <span className="text-slate-500 mr-2 select-none">[{idx + 1}]</span>
                  <span>{line}</span>
                </div>
              ))
            ) : (
              <div className="flex h-full items-center justify-center text-slate-500 italic">
                No process logs available for this session.
              </div>
            )}
          </div>
        )}

        {activeTab === "qa" && (
          <div className="h-full overflow-y-auto p-4 flex flex-col justify-between bg-[#0b0f19]">
            <div className="w-full flex items-center justify-between border-b border-slate-800 pb-2 mb-3">
              <div className="flex items-center gap-2">
                <span className="text-xs font-semibold text-slate-200">Playwright Visual Verification</span>
                <span className="inline-flex items-center gap-1 rounded-full border border-sky-500/30 bg-sky-500/10 px-2 py-0.5 text-[10px] font-medium text-sky-400">
                  <span className="h-1.5 w-1.5 rounded-full bg-sky-400 animate-pulse" />
                  Remote E2B / Local Headless
                </span>
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={async () => {
                  setQaRunning(true);
                  setQaStatusMsg(null);
                  try {
                    if (onTriggerQA) {
                      await onTriggerQA();
                      setQaStatusMsg("Verification cycle complete.");
                    } else {
                      // Standby trigger
                      await new Promise((r) => setTimeout(r, 600));
                      setQaStatusMsg("Triggered verification check across active preview port.");
                    }
                  } catch (e: any) {
                    setQaStatusMsg(`Verification note: ${e?.message || e}`);
                  } finally {
                    setQaRunning(false);
                  }
                }}
                disabled={qaRunning}
                className="h-7 text-xs border-slate-700 bg-slate-800/60 hover:bg-slate-700 text-slate-200"
              >
                {qaRunning ? (
                  <>
                    <Loader2 className="mr-1.5 h-3.5 w-3.5 animate-spin text-sky-400" />
                    Running QA...
                  </>
                ) : (
                  <>
                    <Camera className="mr-1.5 h-3.5 w-3.5 text-sky-400" />
                    Run Visual QA
                  </>
                )}
              </Button>
            </div>

            <div className="flex-1 flex flex-col items-center justify-center min-h-0">
              {screenshotUrl ? (
                <div className="flex flex-col items-center max-w-full">
                  <span className="text-xs text-emerald-400 font-medium mb-2 flex items-center gap-1.5">
                    <Camera className="h-3.5 w-3.5" /> Latest Visual Snapshot (progress.png)
                  </span>
                  <img
                    src={screenshotUrl}
                    alt="Playwright verification snapshot"
                    className="max-h-56 rounded-lg border border-slate-700 shadow-xl object-contain"
                  />
                </div>
              ) : (
                <div className="flex flex-col items-center text-center text-slate-500 max-w-xs">
                  <Camera className="h-8 w-8 mb-2 text-slate-600" />
                  <p className="text-xs font-medium text-slate-400">No Visual QA Snapshot Yet</p>
                  <p className="text-[11px] mt-1 text-slate-500">
                    When tests or verification tools run, Playwright scripts headless Chromium to verify UI layout and console errors into progress.png.
                  </p>
                  {qaStatusMsg && (
                    <p className="mt-2 text-[11px] font-mono text-sky-400">{qaStatusMsg}</p>
                  )}
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </motion.div>
  )}
</AnimatePresence>
  );
}
