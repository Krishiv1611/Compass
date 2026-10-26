import { useEffect, useRef } from "react";
import { Terminal } from "@xterm/xterm";
import { FitAddon } from "@xterm/addon-fit";
import "@xterm/xterm/css/xterm.css";

interface TerminalViewProps {
  onInput?: (data: string) => void;
  streamText?: string;
  className?: string;
}

export default function TerminalView({ onInput, streamText, className = "" }: TerminalViewProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const termRef = useRef<Terminal | null>(null);
  const fitAddonRef = useRef<FitAddon | null>(null);
  const lastStreamIndexRef = useRef(0);

  useEffect(() => {
    if (!containerRef.current) return;

    const term = new Terminal({
      cursorBlink: true,
      fontSize: 12.5,
      fontFamily: "'JetBrains Mono Variable', Menlo, Monaco, Consolas, monospace",
      theme: {
        background: "#090d16",
        foreground: "#cbd5e1",
        cursor: "#38bdf8",
        selectionBackground: "rgba(56, 189, 248, 0.3)",
        black: "#0f172a",
        red: "#f87171",
        green: "#4ade80",
        yellow: "#facc15",
        blue: "#60a5fa",
        magenta: "#c084fc",
        cyan: "#38bdf8",
        white: "#f8fafc",
        brightBlack: "#475569",
        brightRed: "#ef4444",
        brightGreen: "#22c55e",
        brightYellow: "#eab308",
        brightBlue: "#3b82f6",
        brightMagenta: "#a855f7",
        brightCyan: "#06b6d4",
        brightWhite: "#ffffff",
      },
      convertEol: true,
    });

    const fitAddon = new FitAddon();
    term.loadAddon(fitAddon);
    term.open(containerRef.current);
    fitAddon.fit();

    termRef.current = term;
    fitAddonRef.current = fitAddon;

    // Welcome banner
    term.writeln("\x1b[1;36mCompass Terminal\x1b[0m \x1b[90m— interactive session ready\x1b[0m");
    term.writeln("\x1b[90m$ Ready for shell commands and background agent execution.\x1b[0m\r\n");

    const onDataDisposable = term.onData((data) => {
      onInput?.(data);
      // Echo input locally if no custom onInput is attached
      if (!onInput) {
        if (data === "\r") {
          term.write("\r\n$ ");
        } else if (data === "\u007f") {
          term.write("\b \b");
        } else {
          term.write(data);
        }
      }
    });

    const handleResize = () => {
      try {
        fitAddon.fit();
      } catch {
        // Ignored if terminal is hidden
      }
    };
    window.addEventListener("resize", handleResize);

    return () => {
      window.removeEventListener("resize", handleResize);
      onDataDisposable.dispose();
      term.dispose();
      termRef.current = null;
      fitAddonRef.current = null;
    };
  }, [onInput]);

  // Stream new incoming text
  useEffect(() => {
    if (termRef.current && streamText) {
      const newChunk = streamText.slice(lastStreamIndexRef.current);
      if (newChunk) {
        termRef.current.write(newChunk);
        lastStreamIndexRef.current = streamText.length;
      }
    }
  }, [streamText]);

  return (
    <div
      ref={containerRef}
      className={`h-full w-full overflow-hidden bg-[#090d16] p-2 ${className}`}
    />
  );
}
