import { useState } from "react";
import { Brain, ChevronDown, ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";
import ShimmerLoader from "./ShimmerLoader";
import MarkdownMessage from "./MarkdownMessage";
import { motion, AnimatePresence } from "framer-motion";

interface ThinkingBlockProps {
  content?: string;
  isProcessing?: boolean;
}

export default function ThinkingBlock({ content, isProcessing }: ThinkingBlockProps) {
  const [isOpen, setIsOpen] = useState(false);

  // If there's no content and we aren't processing, don't show the block
  if (!content && !isProcessing) return null;

  return (
    <div className="my-2 flex flex-col gap-1 rounded-md border border-border/50 bg-muted/20">
      <button
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center justify-between px-3 py-2 text-xs font-medium text-muted-foreground hover:text-foreground transition-colors"
      >
        <div className="flex items-center gap-2">
          {isProcessing ? (
            <div className="relative flex items-center justify-center">
              <Brain className="h-3.5 w-3.5 animate-pulse text-primary" />
              <div className="absolute inset-0 rounded-full animate-ping border border-primary/50" />
            </div>
          ) : (
            <Brain className="h-3.5 w-3.5" />
          )}
          <span>{isProcessing ? "Thinking..." : "View reasoning"}</span>
        </div>
        {isOpen ? <ChevronDown className="h-3.5 w-3.5" /> : <ChevronRight className="h-3.5 w-3.5" />}
      </button>

      <AnimatePresence>
        {isOpen && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: "auto", opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            className="overflow-hidden"
          >
            <div className="px-3 pb-3 text-sm text-muted-foreground/80">
              {content ? (
                <div className="prose prose-sm prose-invert max-w-none opacity-80">
                  <MarkdownMessage content={content} />
                </div>
              ) : (
                <div className="flex flex-col gap-2 mt-2">
                  <ShimmerLoader className="w-full" />
                  <ShimmerLoader className="w-5/6" />
                  <ShimmerLoader className="w-4/6" />
                </div>
              )}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
}
