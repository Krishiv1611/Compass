import { useEffect, useRef } from "react";
import { motion } from "framer-motion";
import { X } from "lucide-react";
import { getFileIcon } from "@/lib/fileIcons";
import { cn } from "@/lib/utils";

export interface EditorTabBarProps {
  openFiles: string[];
  activePath?: string;
  onSelectFile: (path: string) => void;
  onCloseFile: (path: string) => void;
  isDirty?: (path: string) => boolean;
}

export default function EditorTabBar({
  openFiles,
  activePath,
  onSelectFile,
  onCloseFile,
  isDirty,
}: EditorTabBarProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  // Keyboard shortcut: Ctrl+W or Cmd+W closes the currently active tab
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "w") {
        e.preventDefault();
        if (activePath) {
          onCloseFile(activePath);
        }
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [activePath, onCloseFile]);

  // Scroll active tab into view when activePath changes
  useEffect(() => {
    if (!activePath || !containerRef.current) return;
    const activeElement = containerRef.current.querySelector('[aria-selected="true"]');
    if (activeElement && "scrollIntoView" in activeElement) {
      activeElement.scrollIntoView({ behavior: "smooth", block: "nearest", inline: "nearest" });
    }
  }, [activePath]);

  if (openFiles.length === 0) {
    return null;
  }

  return (
    <div
      ref={containerRef}
      role="tablist"
      aria-label="Open editor tabs"
      className="flex h-9 shrink-0 items-center gap-1 border-b border-border/80 bg-[#080A0E] px-2 overflow-x-auto [scrollbar-width:none] [-ms-overflow-style:none] [&::-webkit-scrollbar]:hidden select-none"
    >
      {openFiles.map((path) => {
        const fileName = path.split("/").pop() || path;
        const isActive = activePath === path;
        const dirty = Boolean(isDirty?.(path));

        return (
          <div
            key={path}
            role="tab"
            aria-selected={isActive}
            aria-label={fileName}
            data-active={isActive ? "true" : "false"}
            tabIndex={0}
            onClick={() => onSelectFile(path)}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                onSelectFile(path);
              }
            }}
            className={cn(
              "group relative flex items-center h-7 px-2.5 rounded-md text-xs font-mono transition-colors cursor-pointer shrink-0 select-none outline-none focus-visible:ring-1 focus-visible:ring-sky-500",
              isActive
                ? "text-foreground font-medium"
                : "text-muted-foreground hover:text-foreground hover:bg-white/[0.04]"
            )}
          >
            {isActive && (
              <motion.div
                layoutId="activeEditorTab"
                data-testid="active-tab-indicator"
                className="absolute inset-0 rounded-md bg-[#161B22] border border-border/80 shadow-sm"
                transition={{ type: "spring", stiffness: 450, damping: 30 }}
              />
            )}
            <span className="relative z-10 flex items-center gap-1.5 min-w-0">
              {getFileIcon(fileName, false, false, "h-3.5 w-3.5 shrink-0")}
              <span className="truncate max-w-[160px]" title={path}>
                {fileName}
              </span>
              {dirty && (
                <span
                  data-testid="dirty-indicator"
                  aria-label="Unsaved changes"
                  title="Unsaved changes"
                  className="h-1.5 w-1.5 rounded-full bg-amber-400 shrink-0 ml-0.5"
                />
              )}
              <button
                type="button"
                data-testid={`close-tab-${fileName}`}
                aria-label={`Close ${fileName}`}
                title={`Close ${fileName} (Ctrl+W)`}
                onClick={(e) => {
                  e.stopPropagation();
                  onCloseFile(path);
                }}
                className="ml-1 rounded p-0.5 text-muted-foreground/50 opacity-60 group-hover:opacity-100 hover:text-foreground hover:bg-white/10 transition-all"
              >
                <X className="h-3 w-3" />
              </button>
            </span>
          </div>
        );
      })}
    </div>
  );
}
