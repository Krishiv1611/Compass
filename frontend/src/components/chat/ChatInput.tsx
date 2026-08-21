import { useEffect, useRef, useState, type DragEvent } from "react";
import { File as FileIcon, FilePenLine, Folder, HelpCircle, ListTree, Loader2, Paperclip, Send, Target, X } from "lucide-react";
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
    if (input.trim() || attachedFiles.length > 0 || referencedPaths.length > 0) {
      setSubmitting(true);
      try {
        await onSend(input.trim(), attachedFiles, mode, referencedPaths.map((item) => item.path));
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
              : "focus-within:border-accent focus-within:ring-1 focus-within:ring-accent/50"
        } ${isLoading ? "opacity-80" : ""}`}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
      >
        {(attachedFiles.length > 0 || referencedPaths.length > 0) && (
          <div className="flex flex-wrap gap-2 border-b border-border bg-background/60 p-2">
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
            placeholder={isDraggingPath ? "Drop to reference path" : isDragging ? "Drop files here" : "Describe the task or ask about this project"}
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
            <div className="flex max-w-[calc(100vw-7rem)] items-center overflow-x-auto rounded-md border border-border bg-background p-0.5 mr-2">
              <button
                type="button"
                onClick={() => dispatch({ type: "setContextDrawer", open: true })}
                disabled={isLoading}
                className="flex items-center gap-1 rounded px-1.5 py-1.5 text-xs font-medium transition-colors sm:gap-1.5 sm:px-2 text-muted-foreground hover:text-foreground hover:bg-muted"
                title="Manage skills"
              >
                Skills
              </button>
              <button
                type="button"
                onClick={() => dispatch({ type: "setContextDrawer", open: true })}
                disabled={isLoading}
                className="flex items-center gap-1 rounded px-1.5 py-1.5 text-xs font-medium transition-colors sm:gap-1.5 sm:px-2 text-muted-foreground hover:text-foreground hover:bg-muted"
                title="Available tools"
              >
                Tools
              </button>
              <button
                type="button"
                onClick={() => dispatch({ type: "setContextDrawer", open: true })}
                disabled={isLoading}
                className="flex items-center gap-1 rounded px-1.5 py-1.5 text-xs font-medium transition-colors sm:gap-1.5 sm:px-2 text-muted-foreground hover:text-foreground hover:bg-muted"
                title="Project memory"
              >
                Memory
              </button>
            </div>

            <div role="radiogroup" aria-label="Conversation mode" className="flex max-w-[calc(100vw-7rem)] items-center overflow-x-auto rounded-md border border-border bg-background p-0.5">
              <button
                ref={(element) => { if (element) modeButtonRefs.current.set("ask", element); else modeButtonRefs.current.delete("ask"); }}
                type="button"
                role="radio"
                aria-checked={mode === "ask"}
                tabIndex={mode === "ask" ? 0 : -1}
                onClick={() => selectMode("ask")}
                onKeyDown={(event) => handleModeKeyDown(event, "ask")}
                disabled={isLoading}
                className={`flex items-center gap-1 rounded px-1.5 py-1.5 text-xs font-medium transition-colors sm:gap-1.5 sm:px-2 ${
                  mode === "ask"
                    ? "bg-primary text-primary-foreground"
                    : "text-muted-foreground hover:text-foreground hover:bg-muted"
                }`}
                title="Ask uses read-only project tools"
              >
                <HelpCircle className="h-3.5 w-3.5" /> <span className="hidden sm:inline">Ask</span>
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
                className={`flex items-center gap-1 rounded px-1.5 py-1.5 text-xs font-medium transition-colors sm:gap-1.5 sm:px-2 ${
                  mode === "edit"
                    ? "bg-primary text-primary-foreground"
                    : "text-muted-foreground hover:text-foreground hover:bg-muted"
                }`}
                title="Edit works directly with project tools"
              >
                <FilePenLine className="h-3.5 w-3.5" /> <span className="hidden sm:inline">Edit</span>
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
                className={`flex items-center gap-1 rounded px-1.5 py-1.5 text-xs font-medium transition-colors sm:gap-1.5 sm:px-2 ${
                  mode === "plan"
                    ? "bg-primary text-primary-foreground"
                    : "text-muted-foreground hover:text-foreground hover:bg-muted"
                }`}
                title="Plan requires approval before editing"
              >
                <ListTree className="h-3.5 w-3.5" /> <span className="hidden sm:inline">Plan</span>
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
                className={`flex items-center gap-1 rounded px-1.5 py-1.5 text-xs font-medium transition-colors sm:gap-1.5 sm:px-2 ${
                  mode === "goal"
                    ? "bg-primary text-primary-foreground"
                    : "text-muted-foreground hover:text-foreground hover:bg-muted"
                }`}
                title="Goal works autonomously; risky actions still require approval"
              >
                <Target className="h-3.5 w-3.5" /> <span className="hidden sm:inline">Goal</span>
              </button>
            </div>
          </div>

          <Button size="icon" className="h-9 w-9" onClick={() => void handleSend()} disabled={(!input.trim() && attachedFiles.length === 0 && referencedPaths.length === 0) || isLoading || submitting} title="Send message" aria-label="Send message">
            {isLoading || submitting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Send className="h-4 w-4" />}
          </Button>
        </div>
      </div>
    </div>
  );
}

