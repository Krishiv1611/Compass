import { motion } from "framer-motion";
import { Sparkles } from "lucide-react";

export default function ThinkingIndicator({ text = "Thinking" }: { text?: string }) {
  return (
    <div className="flex items-center gap-3 px-1 py-2">
      <div className="relative flex h-8 w-8 items-center justify-center rounded-lg bg-primary/10 text-primary">
        <Sparkles className="h-4 w-4" />
        <motion.div
          className="absolute inset-0 rounded-lg border border-primary/30"
          animate={{
            scale: [1, 1.1, 1],
            opacity: [0.3, 0.7, 0.3],
          }}
          transition={{
            duration: 2,
            repeat: Infinity,
            ease: "easeInOut",
          }}
        />
      </div>
      <div className="flex items-center gap-1.5">
        <span className="text-sm font-medium text-muted-foreground">{text}</span>
        <motion.div className="flex gap-0.5">
          {[0, 1, 2].map((i) => (
            <motion.div
              key={i}
              className="h-1 w-1 rounded-full bg-primary/60"
              animate={{ opacity: [0.2, 1, 0.2] }}
              transition={{
                duration: 1.5,
                repeat: Infinity,
                delay: i * 0.2,
                ease: "easeInOut",
              }}
            />
          ))}
        </motion.div>
      </div>
    </div>
  );
}
