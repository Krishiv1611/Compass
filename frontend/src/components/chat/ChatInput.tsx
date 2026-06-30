import { useRef, useState, type DragEvent } from "react";
import { File as FileIcon, GitCommit, Loader2, Paperclip, Send, Sparkles, X, Zap } from "lucide-react";
import { Button } from "@/components/ui/button";

interface ChatInputProps {
  onSend: (message: string, files: File[], mode: "normal" | "plan") => void;
  isLoading?: boolean;
}

export default function ChatInput({ onSend, isLoading = false }: ChatInputProps) {
  const [input, setInput] = useState("");
  const [isDragging, setIsDragging] = useState(false);
  const [attachedFiles, setAttachedFiles] = useState<File[]>([]);
  const [mode, setMode] = useState<"normal" | "plan">("normal");
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleSend = () => {
    if (isLoading) return;
    if (input.trim() || attachedFiles.length > 0) {
      onSend(input, attachedFiles, mode);
      setInput("");
      setAttachedFiles([]);
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
  };

  const handleDragLeave = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault();
    setIsDragging(false);
    if (event.dataTransfer.files?.length) addFiles(event.dataTransfer.files);
  };

  const removeFile = (index: number) => {
    setAttachedFiles((prev) => prev.filter((_, itemIndex) => itemIndex !== index));
  };

  return (
    <div className="px-4 pb-4 pt-2 md:px-8">
      <div
        className={`mx-auto max-w-3xl overflow-hidden rounded-lg border bg-card shadow-sm transition-colors ${
          isDragging ? "border-primary ring-2 ring-primary/20" : "border-border focus-within:border-ring focus-within:ring-2 focus-within:ring-ring/20"
        } ${isLoading ? "opacity-80" : ""}`}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
      >
        {attachedFiles.length > 0 && (
          <div className="flex flex-wrap gap-2 border-b border-border bg-background/60 p-2">
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

        <textarea
          value={input}
          onChange={(event) => setInput(event.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={isDragging ? "Drop files here" : "Ask Compass to inspect, edit, build, or explain..."}
          className="max-h-44 min-h-20 w-full resize-none bg-transparent px-4 py-3 text-sm leading-6 text-foreground outline-none placeholder:text-muted-foreground"
          disabled={isLoading}
        />

        <div className="flex items-center justify-between border-t border-border bg-background/60 px-2 py-2">
          <div className="flex items-center gap-1">
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
            <Button variant="ghost" size="sm" onClick={() => fileInputRef.current?.click()} disabled={isLoading}>
              <Paperclip className="h-4 w-4" /> Attach
            </Button>
            <div className="ml-1 flex rounded-lg border border-border bg-card p-0.5">
              <button
                className={`flex h-7 items-center gap-1 rounded-md px-2 text-xs font-medium ${mode === "normal" ? "bg-muted text-foreground" : "text-muted-foreground hover:text-foreground"}`}
                onClick={() => setMode("normal")}
                disabled={isLoading}
              >
                <Zap className="h-3.5 w-3.5" /> Normal
              </button>
              <button
                className={`flex h-7 items-center gap-1 rounded-md px-2 text-xs font-medium ${mode === "plan" ? "bg-muted text-foreground" : "text-muted-foreground hover:text-foreground"}`}
                onClick={() => setMode("plan")}
                disabled={isLoading}
              >
                <GitCommit className="h-3.5 w-3.5" /> Plan
              </button>
            </div>
          </div>

          <Button size="sm" onClick={handleSend} disabled={(!input.trim() && attachedFiles.length === 0) || isLoading}>
            {isLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : mode === "plan" ? <Sparkles className="h-4 w-4" /> : <Send className="h-4 w-4" />}
            Send
          </Button>
        </div>
      </div>
    </div>
  );
}
