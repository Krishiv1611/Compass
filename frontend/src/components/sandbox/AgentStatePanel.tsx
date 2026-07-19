import { useEffect, useState } from "react";
import { BrainCircuit, CheckSquare, Loader2, RefreshCcw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { toolsApi } from "@/api";
import { formatDistanceToNow } from "date-fns";

export default function AgentStatePanel() {
  const [tasks, setTasks] = useState<any[]>([]);
  const [memories, setMemories] = useState<any[]>([]);
  const [isMemoryEnabled, setIsMemoryEnabled] = useState(false);
  const [loading, setLoading] = useState(false);
  const [activeTab, setActiveTab] = useState("tasks");

  const loadData = async () => {
    setLoading(true);
    try {
      if (activeTab === "tasks") {
        const data = await toolsApi.getTasks();
        setTasks(data || []);
      } else {
        const data = await toolsApi.getMemories();
        setMemories(data.memories || []);
        setIsMemoryEnabled(data.enabled || false);
      }
    } catch (error) {
      console.error("Failed to load agent state:", error);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, [activeTab]);

  // Auto-refresh when agent is done
  useEffect(() => {
    const handleAgentDone = () => loadData();
    const handleSetTab = (e: any) => {
      if (e.detail?.tab) setActiveTab(e.detail.tab);
    };
    window.addEventListener("agent-done", handleAgentDone);
    window.addEventListener("set-agent-tab", handleSetTab);
    return () => {
      window.removeEventListener("agent-done", handleAgentDone);
      window.removeEventListener("set-agent-tab", handleSetTab);
    };
  }, [activeTab]);

  return (
    <div className="flex h-full flex-col bg-background">
      <div className="px-3 py-2 flex items-center justify-between border-b border-border/50">
        <Tabs value={activeTab} onValueChange={setActiveTab} className="w-full">
          <div className="flex items-center justify-between">
            <TabsList className="grid w-[140px] grid-cols-2 h-7 bg-muted/50 p-0.5">
              <TabsTrigger value="tasks" className="text-[10px] data-[state=active]:bg-background data-[state=active]:shadow-sm">
                Tasks
              </TabsTrigger>
              <TabsTrigger value="memory" className="text-[10px] data-[state=active]:bg-background data-[state=active]:shadow-sm">
                Memory
              </TabsTrigger>
            </TabsList>
            <Button variant="ghost" size="icon-sm" onClick={loadData} disabled={loading} title="Refresh">
              <RefreshCcw className={`h-3 w-3 text-muted-foreground ${loading ? "animate-spin" : ""}`} />
            </Button>
          </div>
        </Tabs>
      </div>

      <ScrollArea className="flex-1 min-h-0">
        {activeTab === "tasks" && (
          <div className="p-3 space-y-2">
            {tasks.length === 0 ? (
              <div className="text-xs text-muted-foreground text-center py-6">
                No active tasks.
              </div>
            ) : (
              tasks.map((task) => (
                <div key={task.id} className="flex items-start gap-2 text-sm p-2 rounded-md border border-border/50 bg-muted/20">
                  <CheckSquare className={`h-4 w-4 shrink-0 mt-0.5 ${task.done ? "text-green-500" : "text-muted-foreground/50"}`} />
                  <div className="min-w-0 flex-1">
                    <p className={`text-xs ${task.done ? "line-through text-muted-foreground" : "text-foreground"}`}>
                      {task.text}
                    </p>
                  </div>
                </div>
              ))
            )}
          </div>
        )}

        {activeTab === "memory" && (
          <div className="p-3 space-y-3">
            {!isMemoryEnabled ? (
              <div className="text-xs text-amber-500/80 bg-amber-500/10 p-3 rounded-md border border-amber-500/20 text-center">
                <BrainCircuit className="h-5 w-5 mx-auto mb-1 opacity-80" />
                Memory store (Postgres) is not configured. Set DB_URI in backend.
              </div>
            ) : memories.length === 0 ? (
              <div className="text-xs text-muted-foreground text-center py-6">
                No memories stored yet.
              </div>
            ) : (
              memories.map((mem) => (
                <div key={mem.key} className="flex flex-col gap-1 text-sm p-2 rounded-md border border-border/50 bg-muted/20 overflow-hidden">
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-[10px] font-semibold text-primary/80 truncate pr-2">
                      {mem.key}
                    </span>
                    {mem.updated_at && (
                      <span className="text-[9px] text-muted-foreground whitespace-nowrap">
                        {formatDistanceToNow(new Date(mem.updated_at), { addSuffix: true })}
                      </span>
                    )}
                  </div>
                  <div className="text-xs text-muted-foreground bg-background/50 p-1.5 rounded border border-border/30 max-h-32 overflow-y-auto whitespace-pre-wrap">
                    {typeof mem.value === 'object' ? JSON.stringify(mem.value, null, 2) : String(mem.value)}
                  </div>
                </div>
              ))
            )}
          </div>
        )}
      </ScrollArea>
    </div>
  );
}
