import { useEffect, useRef, useState, type DragEvent } from "react";
import { File as FileIcon, FilePenLine, Folder, HelpCircle, ListTree, Loader2, MousePointerClick, Paperclip, Send, SlidersHorizontal, Target, X } from "lucide-react";
import { motion } from "framer-motion";
import { Button } from "@/components/ui/button";
import { workspaceApi } from "@/api";
import type { ChatMode } from "@/types/chat";
import { useWorkbench } from "@/contexts/WorkbenchContext";

interface ChatInputProps {
  onSend: (message: string, files: File[], mode: ChatMode, contextFiles: string[]) => Promise<void> | void;
  isLoading?: boolean;
  workspaceId?: string | null;
  onContextChange?: (paths: string[]) => void;
  initialContextPaths?: string[];
}

export type ReferencedPath = {
  path: string;
  name: string;
  type: "file" | "folder";
};

const chatModes: ChatMode[] = ["ask", "edit", "plan", "goal"];

export default function ChatInput({ onSend, isLoading = false, workspaceId, onContextChange, initialContextPaths = [] }: ChatInputProps) {
  const [input, setInput] = useState("");
  const [isDragging, setIsDragging] = useState(false);
  const [isDraggingPath, setIsDraggingPath] = useState(false);
  const [attachedFiles, setAttachedFiles] = useState<File[]>([]);
  const [referencedPaths, setReferencedPaths] = useState<ReferencedPath[]>(() => initialContextPaths.map(path => ({ path, name: path.split("/").pop() || path, type: "file" })));
  const [submitting, setSubmitting] = useState(false);
  const [mentionResults, setMentionResults] = useState<string[]>([]);
  const [mentionQuery, setMentionQuery] = useState<string | null>(null);
  const [activeMentionIndex, setActiveMentionIndex] = useState(0);
  const { state, setMode, dispatch } = useWorkbench();
  const mode = state.mode;
  const fileInputRef = useRef<HTMLInputElement>(null);
  const modeButtonRefs = useRef(new Map<ChatMode, HTMLButtonElement>());

  const selectMode = (nextMode: ChatMode) => {
    setMode(nextMode);
    modeButtonRefs.current.get(nextMode)?.focus();
  };

  const handleModeKeyDown = (event: React.KeyboardEvent<HTMLButtonElement>, currentMode: ChatMode) => {
    const currentIndex = chatModes.indexOf(currentMode);
    let nextIndex: number | null = null;
    if (event.key === "ArrowRight" || event.key === "ArrowDown") nextIndex = (currentIndex + 1) % chatModes.length;
    if (event.key === "ArrowLeft" || event.key === "ArrowUp") nextIndex = (currentIndex - 1 + chatModes.length) % chatModes.length;
    if (event.key === "Home") nextIndex = 0;
    if (event.key === "End") nextIndex = chatModes.length - 1;
    if (nextIndex !== null) {
      event.preventDefault();
      selectMode(chatModes[nextIndex]);
    }
  };

  useEffect(() => {
    onContextChange?.(referencedPaths.map((item) => item.path));
  }, [onContextChange, referencedPaths]);

  const handleSend = async () => {
    if (isLoading || submitting) return;
    if (input.trim() || attachedFiles.length > 0 || referencedPaths.length > 0 || state.inspectedElement) {
      setSubmitting(true);
      try {
        let messageText = input.trim();
        if (state.inspectedElement) {
          const el = state.inspectedElement;
          const contextBanner = `[Inspecting Element: <${el.tag}${el.id ? ` id="${el.id}"` : ""}${el.classes ? ` class="${el.classes}"` : ""}> selector="${el.selector}"${el.text ? ` text="${el.text}"` : ""}]\n`;
          messageText = contextBanner + messageText;
          dispatch({ type: "setInspectedElement", element: null });
        }
        await onSend(messageText, attachedFiles, mode, referencedPaths.map((item) => item.path));
        setInput("");
        setAttachedFiles([]);
        setReferencedPaths([]);
      } finally {
        setSubmitting(false);
      }
    }
  };

  useEffect(() => {
    const match = input.match(/(?:^|\s)@([^\s@]*)$/);
    const query = match?.[1] ?? null;
    setMentionQuery(query);
    if (query === null || !workspaceId) {
      setMentionResults([]);
      setActiveMentionIndex(0);
      return;
    }
    const timer = window.setTimeout(() => {
      workspaceApi.searchFiles(workspaceId, query, 8)
        .then((files) => {
          setMentionResults(files);
          setActiveMentionIndex(0);
        })
        .catch(() => {
          setMentionResults([]);
          setActiveMentionIndex(0);
        });
    }, 120);
    return () => window.clearTimeout(timer);
  }, [input, workspaceId]);

  const selectMention = (path: string) => {
    if (!referencedPaths.some((item) => item.path === path)) {
      setReferencedPaths((prev) => [
        ...prev,
        { path, name: path.split("/").pop() || path, type: "file" },
      ]);
    }
    setInput((value) => value.replace(/(?:^|\s)@[^\s@]*$/, (token) => token.startsWith(" ") ? " " : ""));
    setMentionResults([]);
    setMentionQuery(null);
    setActiveMentionIndex(0);
  };

  const handleKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (mentionResults.length > 0 && mentionQuery !== null) {
      if (event.key === "ArrowDown") {
        event.preventDefault();
        setActiveMentionIndex((index) => (index + 1) % mentionResults.length);
        return;
      }
      if (event.key === "ArrowUp") {
        event.preventDefault();
        setActiveMentionIndex((index) => (index - 1 + mentionResults.length) % mentionResults.length);
        return;
      }
      if (event.key === "Enter") {
        event.preventDefault();
        selectMention(mentionResults[activeMentionIndex]);
        return;
      }
      if (event.key === "Escape") {
        event.preventDefault();
        setMentionResults([]);
        setMentionQuery(null);
        setActiveMentionIndex(0);
        return;
      }
    }
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      void handleSend();
    }
  };

  const addFiles = (files: FileList | File[]) => {
    setAttachedFiles((prev) => [...prev, ...Array.from(files)]);
  };

  const handleDragOver = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setIsDragging(true);
    if (event.dataTransfer.types.includes("application/x-compass-path")) {
      setIsDraggingPath(true);
    }
  };

  const handleDragLeave = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setIsDragging(false);
    setIsDraggingPath(false);
  };

  const handleDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setIsDragging(false);
    setIsDraggingPath(false);

    const pathData = event.dataTransfer.getData("application/x-compass-path");
    if (pathData) {
      try {
        const parsedPath = JSON.parse(pathData) as ReferencedPath;
        if (!referencedPaths.some(p => p.path === parsedPath.path)) {
          setReferencedPaths(prev => [...prev, parsedPath]);
        }
      } catch (e) {
        console.error("Failed to parse dragged path data", e);
      }
    } else if (event.dataTransfer.files?.length) {
      addFiles(event.dataTransfer.files);
    }
  };

  const removeFile = (index: number) => {
    setAttachedFiles((prev) => prev.filter((_, itemIndex) => itemIndex !== index));
  };

  const removeReferencedPath = (index: number) => {
    setReferencedPaths((prev) => prev.filter((_, itemIndex) => itemIndex !== index));
  };

  return (
    <div className="px-3 pb-[calc(.75rem+env(safe-area-inset-bottom))] pt-2 md:px-5">
      <div
        className={`mx-auto overflow-hidden rounded-md transition-all duration-100 relative bg-card border border-border ${
          isDraggingPath
            ? "border-accent ring-1 ring-accent"
            : isDragging
              ? "border-accent ring-1 ring-accent"
              : state.inspectedElement
                ? "border-sky-500 ring-1 ring-sky-500/60 shadow-[0_0_12px_rgba(56,189,248,0.18)]"
                : "focus-within:border-accent focus-within:ring-1 focus-within:ring-accent/50"
        } ${isLoading ? "opacity-80" : ""}`}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
      >
        {(attachedFiles.length > 0 || referencedPaths.length > 0 || state.inspectedElement) && (
          <div className="flex flex-wrap gap-2 border-b border-border bg-background/60 p-2">
            {state.inspectedElement && (
              <div
                className="flex h-7 max-w-full items-center gap-1.5 rounded-md border border-blue-500/40 bg-blue-500/10 px-2 text-xs font-mono text-blue-400"
                title={`Selector: ${state.inspectedElement.selector}`}
              >
                <MousePointerClick className="h-3.5 w-3.5 shrink-0 text-blue-400" />
                <span className="font-semibold text-blue-300">
                  &lt;{state.inspectedElement.tag}
                  {state.inspectedElement.classes
                    ? `.${state.inspectedElement.classes.split(" ")[0]}`
                    : ""}
                  &gt;
                </span>
                {state.inspectedElement.text && (
                  <span className="max-w-[140px] truncate text-muted-foreground font-sans text-[11px]">
                    "{state.inspectedElement.text}"
                  </span>
                )}
                <button
                  type="button"
                  aria-label="Remove inspected element context"
                  className="text-blue-400/70 hover:text-blue-300 ml-0.5"
                  onClick={() => dispatch({ type: "setInspectedElement", element: null })}
                >
                  <X className="h-3.5 w-3.5" />
                </button>
              </div>
            )}
            {referencedPaths.map((ref, index) => (
              <div key={`${ref.path}-${index}`} className="flex h-7 max-w-full items-center gap-1.5 rounded-md border border-primary/30 bg-primary/10 px-2 text-xs text-primary" title={ref.path}>
                {ref.type === "folder" ? <Folder className="h-3.5 w-3.5 shrink-0" /> : <FileIcon className="h-3.5 w-3.5 shrink-0" />}
                <span className="max-w-[180px] truncate font-medium">{ref.name}</span>
                <button aria-label={`Remove ${ref.name} from context`} className="text-primary/70 hover:text-primary" onClick={() => removeReferencedPath(index)}>
                  <X className="h-3.5 w-3.5" />
                </button>
              </div>
            ))}
            {attachedFiles.map((file, index) => (
              <div key={`${file.name}-${index}`} className="flex h-7 max-w-full items-center gap-1.5 rounded-md border border-border bg-card px-2 text-xs">
                <FileIcon className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                <span className="max-w-[180px] truncate" title={file.name}>{file.name}</span>
                <button aria-label={`Remove ${file.name} attachment`} className="text-muted-foreground hover:text-foreground" onClick={() => removeFile(index)}>
                  <X className="h-3.5 w-3.5" />
                </button>
              </div>
            ))}
          </div>
        )}

        <div className="relative flex items-start pt-3 px-4">
          <textarea
            value={input}
            onChange={(event) => setInput(event.target.value)}
            onKeyDown={handleKeyDown}
            aria-autocomplete="list"
            aria-controls={mentionResults.length > 0 ? "project-file-mentions" : undefined}
            aria-activedescendant={mentionResults.length > 0 ? `project-file-mention-${activeMentionIndex}` : undefined}
            placeholder={
              state.inspectedElement
                ? `Describe what you want to change on this <${state.inspectedElement.tag}> element…`
                : isDraggingPath
                ? "Drop to reference path"
                : isDragging
                ? "Drop files here"
                : "Describe the task or ask about this project"
            }
            className="max-h-44 min-h-20 w-full resize-none bg-transparent text-sm leading-6 text-foreground outline-none placeholder:text-muted-foreground/70"
            disabled={isLoading}
          />
          {mentionQuery !== null && workspaceId && mentionResults.length > 0 && (
            <div id="project-file-mentions" role="listbox" aria-label="Project files" className="absolute inset-x-3 bottom-full z-30 mb-2 overflow-hidden rounded-md border border-border bg-popover shadow-xl">
              <div className="border-b border-border px-3 py-2 text-xs font-medium text-muted-foreground">
                Add project context
              </div>
              {mentionResults.map((path, index) => (
                <button
                  key={path}
                  id={`project-file-mention-${index}`}
                  type="button"
                  role="option"
                  aria-selected={index === activeMentionIndex}
                  className="flex w-full items-center gap-2 px-3 py-2 text-left text-xs text-popover-foreground hover:bg-accent"
                  onMouseDown={(event) => event.preventDefault()}
                  onClick={() => selectMention(path)}
                >
                  <FileIcon className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                  <span className="truncate font-mono">{path}</span>
                </button>
              ))}
            </div>
          )}
        </div>

        <div className="flex items-center justify-between px-4 pb-3">
          <div className="flex items-center gap-2">
            <input
              ref={fileInputRef}
              type="file"
              multiple
              className="hidden"
              onChange={(event) => {
                if (event.target.files?.length) addFiles(event.target.files);
                event.target.value = "";
              }}
              disabled={isLoading}
            />
            <Button variant="ghost" size="icon-sm" className="text-muted-foreground hover:text-foreground" onClick={() => fileInputRef.current?.click()} disabled={isLoading} title="Attach files" aria-label="Attach files">
              <Paperclip className="h-4 w-4" />
            </Button>
            <button
              type="button"
              onClick={() => dispatch({ type: "setContextDrawer", open: true })}
              disabled={isLoading}
              className="flex items-center gap-1.5 rounded-md border border-border/80 bg-background/80 px-2.5 py-1 text-xs font-medium text-muted-foreground hover:text-foreground hover:bg-muted transition-all mr-1.5 shadow-sm"
              title="Manage skills, tools, and project memory"
            >
              <SlidersHorizontal className="h-3.5 w-3.5 text-sky-400" />
              <span className="hidden sm:inline">Context</span>
            </button>

            <div role="radiogroup" aria-label="Conversation mode" className="flex max-w-[calc(100vw-7rem)] items-center overflow-x-auto rounded-md border border-border bg-[#0D1117]/80 p-0.5 shadow-sm">
              <button
                ref={(element) => { if (element) modeButtonRefs.current.set("ask", element); else modeButtonRefs.current.delete("ask"); }}
                type="button"
                role="radio"
                aria-checked={mode === "ask"}
                tabIndex={mode === "ask" ? 0 : -1}
                onClick={() => selectMode("ask")}
                onKeyDown={(event) => handleModeKeyDown(event, "ask")}
                disabled={isLoading}
                className={`relative flex items-center gap-1 rounded px-2 py-1 text-xs font-medium transition-colors sm:gap-1.5 ${
                  mode === "ask" ? "text-sky-300" : "text-muted-foreground hover:text-foreground"
                }`}
                title="Ask uses read-only project tools"
              >
                {mode === "ask" && (
                  <motion.span
                    layoutId="activeModePill"
                    className="absolute inset-0 rounded bg-sky-500/20 border border-sky-500/40 shadow-[0_0_10px_rgba(56,189,248,0.2)]"
                    transition={{ type: "spring", stiffness: 450, damping: 32 }}
                  />
                )}
                <HelpCircle className="relative z-10 h-3.5 w-3.5" /> <span className="relative z-10 hidden sm:inline">Ask</span>
              </button>
              <button
                ref={(element) => { if (element) modeButtonRefs.current.set("edit", element); else modeButtonRefs.current.delete("edit"); }}
                type="button"
                role="radio"
                aria-checked={mode === "edit"}
                tabIndex={mode === "edit" ? 0 : -1}
                onClick={() => selectMode("edit")}
                onKeyDown={(event) => handleModeKeyDown(event, "edit")}
                disabled={isLoading}
                className={`relative flex items-center gap-1 rounded px-2 py-1 text-xs font-medium transition-colors sm:gap-1.5 ${
                  mode === "edit" ? "text-emerald-300" : "text-muted-foreground hover:text-foreground"
                }`}
                title="Edit works directly with project tools"
              >
                {mode === "edit" && (
                  <motion.span
                    layoutId="activeModePill"
                    className="absolute inset-0 rounded bg-emerald-500/20 border border-emerald-500/40 shadow-[0_0_10px_rgba(16,185,129,0.2)]"
                    transition={{ type: "spring", stiffness: 450, damping: 32 }}
                  />
                )}
                <FilePenLine className="relative z-10 h-3.5 w-3.5" /> <span className="relative z-10 hidden sm:inline">Edit</span>
              </button>
              <button
                ref={(element) => { if (element) modeButtonRefs.current.set("plan", element); else modeButtonRefs.current.delete("plan"); }}
                type="button"
                role="radio"
                aria-checked={mode === "plan"}
                tabIndex={mode === "plan" ? 0 : -1}
                onClick={() => selectMode("plan")}
                onKeyDown={(event) => handleModeKeyDown(event, "plan")}
                disabled={isLoading}
                className={`relative flex items-center gap-1 rounded px-2 py-1 text-xs font-medium transition-colors sm:gap-1.5 ${
                  mode === "plan" ? "text-amber-300" : "text-muted-foreground hover:text-foreground"
                }`}
                title="Plan requires approval before editing"
              >
                {mode === "plan" && (
                  <motion.span
                    layoutId="activeModePill"
                    className="absolute inset-0 rounded bg-amber-500/20 border border-amber-500/40 shadow-[0_0_10px_rgba(245,158,11,0.2)]"
                    transition={{ type: "spring", stiffness: 450, damping: 32 }}
                  />
                )}
                <ListTree className="relative z-10 h-3.5 w-3.5" /> <span className="relative z-10 hidden sm:inline">Plan</span>
              </button>
              <button
                ref={(element) => { if (element) modeButtonRefs.current.set("goal", element); else modeButtonRefs.current.delete("goal"); }}
                type="button"
                role="radio"
                aria-checked={mode === "goal"}
                tabIndex={mode === "goal" ? 0 : -1}
                onClick={() => selectMode("goal")}
                onKeyDown={(event) => handleModeKeyDown(event, "goal")}
                disabled={isLoading}
                className={`relative flex items-center gap-1 rounded px-2 py-1 text-xs font-medium transition-colors sm:gap-1.5 ${
                  mode === "goal" ? "text-purple-300" : "text-muted-foreground hover:text-foreground"
                }`}
                title="Goal works autonomously; risky actions still require approval"
              >
                {mode === "goal" && (
                  <motion.span
                    layoutId="activeModePill"
                    className="absolute inset-0 rounded bg-purple-500/20 border border-purple-500/40 shadow-[0_0_10px_rgba(168,85,247,0.2)]"
                    transition={{ type: "spring", stiffness: 450, damping: 32 }}
                  />
                )}
                <Target className="relative z-10 h-3.5 w-3.5" /> <span className="relative z-10 hidden sm:inline">Goal</span>
              </button>
            </div>
          </div>

          <Button size="icon" className="h-9 w-9" onClick={() => void handleSend()} disabled={(!input.trim() && attachedFiles.length === 0 && referencedPaths.length === 0 && !state.inspectedElement) || isLoading || submitting} title="Send message" aria-label="Send message">
            {isLoading || submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
          </Button>
        </div>
      </div>
    </div>
  );
}

