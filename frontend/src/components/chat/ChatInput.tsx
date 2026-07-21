import { useRef, useState, type DragEvent } from "react";
import { File as FileIcon, Loader2, Paperclip, Send, Sparkles, X, Folder, Zap, Target, Activity } from "lucide-react";
import { Button } from "@/components/ui/button";

interface ChatInputProps {
  onSend: (message: string, files: File[], mode: "normal" | "plan" | "fast" | "goal") => void;
  isLoading?: boolean;
}

export type ReferencedPath = {
  path: string;
  name: string;
  type: "file" | "folder";
};

export default function ChatInput({ onSend, isLoading = false }: ChatInputProps) {
  const [input, setInput] = useState("");
  const [isDragging, setIsDragging] = useState(false);
  const [isDraggingPath, setIsDraggingPath] = useState(false);
  const [attachedFiles, setAttachedFiles] = useState<File[]>([]);
  const [referencedPaths, setReferencedPaths] = useState<ReferencedPath[]>([]);
  const [mode, setMode] = useState<"normal" | "plan" | "fast" | "goal">("normal");
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleSend = () => {
    if (isLoading) return;
    if (input.trim() || attachedFiles.length > 0 || referencedPaths.length > 0) {
      let finalMessage = input.trim();
      
      if (referencedPaths.length > 0) {
        const pathsString = referencedPaths.map(p => p.path).join(", ");
        const referencePrefix = `[Referring to: ${pathsString}]\n\n`;
        finalMessage = referencePrefix + finalMessage;
      }

      onSend(finalMessage, attachedFiles, mode);
      setInput("");
      setAttachedFiles([]);
      setReferencedPaths([]);
    }
  };

  const handleKeyDown = (event: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      handleSend();
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
    <div className="px-4 pb-[calc(1rem+env(safe-area-inset-bottom))] pt-2 md:px-8">
      <div
        className={`mx-auto max-w-3xl overflow-hidden transition-all duration-100 relative bg-card border border-border ${
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
                <button className="text-primary/70 hover:text-primary" onClick={() => removeReferencedPath(index)}>
                  <X className="h-3.5 w-3.5" />
                </button>
              </div>
            ))}
            {attachedFiles.map((file, index) => (
              <div key={`${file.name}-${index}`} className="flex h-7 max-w-full items-center gap-1.5 rounded-md border border-border bg-card px-2 text-xs">
                <FileIcon className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                <span className="max-w-[180px] truncate" title={file.name}>{file.name}</span>
                <button className="text-muted-foreground hover:text-foreground" onClick={() => removeFile(index)}>
                  <X className="h-3.5 w-3.5" />
                </button>
              </div>
            ))}
          </div>
        )}

        <div className="relative flex items-start pt-3 px-4">
          <Sparkles className="h-5 w-5 mt-1 mr-3 text-primary shrink-0" />
          <textarea
            value={input}
            onChange={(event) => setInput(event.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={isDraggingPath ? "Drop to reference path" : isDragging ? "Drop files here" : "Ask Anything..."}
            className="max-h-44 min-h-20 w-full resize-none bg-transparent text-base leading-7 text-foreground outline-none placeholder:text-muted-foreground/60"
            disabled={isLoading}
          />
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
            <Button variant="ghost" size="sm" className="text-muted-foreground hover:text-foreground rounded-none px-3 h-8 border border-transparent hover:border-border" onClick={() => fileInputRef.current?.click()} disabled={isLoading}>
              <Paperclip className="h-4 w-4 mr-1.5" /> Attach
            </Button>
            <div className="flex items-center ml-2 bg-background border border-border rounded-none p-0.5">
              <button
                type="button"
                onClick={() => setMode("normal")}
                disabled={isLoading}
                className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-none transition-colors ${
                  mode === "normal"
                    ? "bg-accent text-accent-foreground"
                    : "text-muted-foreground hover:text-foreground hover:bg-muted"
                }`}
                title="Normal - Balanced speed and standard safety checks"
              >
                <Activity className="h-3.5 w-3.5" /> Normal
              </button>
              <button
                type="button"
                onClick={() => setMode("plan")}
                disabled={isLoading}
                className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-none transition-colors ${
                  mode === "plan"
                    ? "bg-accent text-accent-foreground"
                    : "text-muted-foreground hover:text-foreground hover:bg-muted"
                }`}
                title="Plan - Analyzes the request and creates a structured plan first"
              >
                <Sparkles className="h-3.5 w-3.5" /> Plan
              </button>
              <button
                type="button"
                onClick={() => setMode("fast")}
                disabled={isLoading}
                className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-none transition-colors ${
                  mode === "fast"
                    ? "bg-accent text-accent-foreground"
                    : "text-muted-foreground hover:text-foreground hover:bg-muted"
                }`}
                title="Fast - Bypasses safety checks for maximum speed"
              >
                <Zap className="h-3.5 w-3.5" /> Fast
              </button>
              <button
                type="button"
                onClick={() => setMode("goal")}
                disabled={isLoading}
                className={`flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium rounded-none transition-colors ${
                  mode === "goal"
                    ? "bg-accent text-accent-foreground"
                    : "text-muted-foreground hover:text-foreground hover:bg-muted"
                }`}
                title="Goal - Deep autonomous execution without interruptions"
              >
                <Target className="h-3.5 w-3.5" /> Goal
              </button>
            </div>
          </div>

          <Button size="icon" className="h-9 w-9 rounded-none bg-accent hover:bg-accent/90 text-accent-foreground transition-all" onClick={handleSend} disabled={(!input.trim() && attachedFiles.length === 0) || isLoading}>
            {isLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : mode === "plan" ? <Sparkles className="h-4 w-4" /> : <Send className="h-4 w-4 ml-0.5" />}
          </Button>
        </div>
      </div>
    </div>
  );
}

