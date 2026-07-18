import { motion } from "framer-motion";
import { Card } from "@/components/ui/card";
import { Bot } from "lucide-react";

export default function MessageSkeleton() {
  return (
    <motion.div
      initial={{ opacity: 0, y: 15 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, scale: 0.95 }}
      transition={{ duration: 0.3, ease: "easeOut" }}
      className="flex gap-3 justify-start w-full"
    >
      <div className="mt-1 flex size-7 shrink-0 items-center justify-center rounded-lg bg-primary/12 text-primary">
        <Bot className="h-4 w-4" />
      </div>
      
      <div className="max-w-[82%] w-full">
        <div className="mb-1 flex items-center gap-2 text-[11px] font-semibold uppercase tracking-[0.12em] text-muted-foreground">
          Compass <motion.span 
            animate={{ opacity: [0.4, 1, 0.4] }} 
            transition={{ duration: 1.5, repeat: Infinity }}
            className="text-primary font-mono lowercase"
          >
            is thinking...
          </motion.span>
        </div>
        
        <Card className="rounded-lg px-4 py-3 bg-card w-full shadow-sm border-border">
          <div className="flex flex-col gap-2.5">
            <motion.div 
              className="h-3 rounded-full bg-muted overflow-hidden relative"
              style={{ width: "85%" }}
            >
              <motion.div 
                className="absolute inset-0 bg-gradient-to-r from-transparent via-primary/10 to-transparent"
                animate={{ x: ["-100%", "200%"] }}
                transition={{ duration: 1.5, repeat: Infinity, ease: "linear" }}
              />
            </motion.div>
            <motion.div 
              className="h-3 rounded-full bg-muted overflow-hidden relative"
              style={{ width: "100%" }}
            >
              <motion.div 
                className="absolute inset-0 bg-gradient-to-r from-transparent via-primary/10 to-transparent"
                animate={{ x: ["-100%", "200%"] }}
                transition={{ duration: 1.5, repeat: Infinity, ease: "linear", delay: 0.2 }}
              />
            </motion.div>
            <motion.div 
              className="h-3 rounded-full bg-muted overflow-hidden relative"
              style={{ width: "60%" }}
            >
              <motion.div 
                className="absolute inset-0 bg-gradient-to-r from-transparent via-primary/10 to-transparent"
                animate={{ x: ["-100%", "200%"] }}
                transition={{ duration: 1.5, repeat: Infinity, ease: "linear", delay: 0.4 }}
              />
            </motion.div>
          </div>
        </Card>
      </div>
    </motion.div>
  );
}
