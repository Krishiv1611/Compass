import { useRef, useState, type DragEvent } from "react";
import { File as FileIcon, GitCommit, Loader2, Paperclip, Send, Sparkles, X, Zap } from "lucide-react";
import { Button } from "@/components/ui/button";

interface ChatInputProps {
  onSend: (message: string, files: File[], mode: "normal" | "plan" | "fast") => void;
  isLoading?: boolean;
}

export default function ChatInput({ onSend, isLoading = false }: ChatInputProps) {
  const [input, setInput] = useState("");
  const [isDragging, setIsDragging] = useState(false);
  const [attachedFiles, setAttachedFiles] = useState<File[]>([]);
  const [mode, setMode] = useState<"normal" | "plan" | "fast">("normal");
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
    <div className="px-4 pb-[calc(1rem+env(safe-area-inset-bottom))] pt-2 md:px-8">
      <div
        className={`glass-input-container mx-auto max-w-3xl overflow-hidden transition-all duration-300 relative ${
          isDragging ? "border-primary ring-2 ring-primary/20" : "focus-within:border-primary/50 focus-within:ring-4 focus-within:ring-primary/10"
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

        <div className="relative flex items-start pt-3 px-4">
          <Sparkles className="h-5 w-5 mt-1 mr-3 text-primary shrink-0" />
          <textarea
            value={input}
            onChange={(event) => setInput(event.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={isDragging ? "Drop files here" : "Ask Anything..."}
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
            <Button variant="ghost" size="sm" className="text-muted-foreground hover:text-foreground rounded-full px-3 h-8" onClick={() => fileInputRef.current?.click()} disabled={isLoading}>
              <Paperclip className="h-4 w-4 mr-1.5" /> Attach
            </Button>
            <div className="flex items-center ml-2">
              <select
                value={mode}
                onChange={(e) => setMode(e.target.value as any)}
                disabled={isLoading}
                className="h-8 rounded-full bg-background/50 px-3 py-0 text-xs font-medium text-muted-foreground outline-none hover:bg-background hover:text-foreground focus:ring-2 focus:ring-primary/20 transition-all border border-border appearance-none cursor-pointer pr-8 bg-no-repeat bg-[url('data:image/svg+xml;charset=utf-8,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20viewBox%3D%220%200%2024%2024%22%20fill%3D%22none%22%20stroke%3D%22%236b7280%22%20stroke-width%3D%222%22%20stroke-linecap%3D%22round%22%20stroke-linejoin%3D%22round%22%3E%3Cpolyline%20points%3D%226%209%2012%2015%2018%209%22%3E%3C%2Fpolyline%3E%3C%2Fsvg%3E')] bg-[length:14px_14px] bg-[right_8px_center]"
              >
                <option value="normal">⚡ Normal - Balanced speed and standard safety checks</option>
                <option value="plan">📝 Plan - Analyzes the request and creates a structured plan first</option>
                <option value="fast">🚀 Fast - Bypasses safety checks for maximum speed</option>
              </select>
            </div>
          </div>

          <Button size="icon" className="h-9 w-9 rounded-full bg-primary hover:bg-primary/90 text-primary-foreground shadow-[0_0_15px_rgba(147,51,234,0.4)] transition-all" onClick={handleSend} disabled={(!input.trim() && attachedFiles.length === 0) || isLoading}>
            {isLoading ? <Loader2 className="h-4 w-4 animate-spin" /> : mode === "plan" ? <Sparkles className="h-4 w-4" /> : <Send className="h-4 w-4 ml-0.5" />}
          </Button>
        </div>
      </div>
    </div>
  );
}

