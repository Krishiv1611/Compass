import { useCallback, useEffect, useState } from "react";
import { BrainCircuit, Loader2, Pencil, Plus, RefreshCw, Trash2 } from "lucide-react";
import { toast } from "react-toastify";

import { memoryApi, type MemoryItem, type MemoryScope } from "@/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

export default function MemoryManager({ projectId }: { projectId?: string | null }) {
  const [scope, setScope] = useState<MemoryScope>("global");
  const [items, setItems] = useState<MemoryItem[]>([]);
  const [content, setContent] = useState("");
  const [category, setCategory] = useState("general");
  const [editingKey, setEditingKey] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [available, setAvailable] = useState(true);

  const resolvedProjectId = projectId ? `workspace:${projectId}` : null;

  const load = useCallback(async () => {
    if (scope === "project" && !resolvedProjectId) {
      setItems([]);
      setLoading(false);
      return;
    }
    setLoading(true);
    try {
      const result = await memoryApi.list(scope, resolvedProjectId);
      setItems(result.memories || []);
      setAvailable(result.enabled);
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not load memory");
    } finally {
      setLoading(false);
    }
  }, [resolvedProjectId, scope]);

  useEffect(() => { void load(); }, [load]);

  const resetComposer = () => {
    setContent("");
    setCategory("general");
    setEditingKey(null);
  };

  const save = async () => {
    if (!content.trim()) return;
    setSaving(true);
    try {
      const body = {
        content: content.trim(),
        category: category.trim() || "general",
        scope,
        project_id: scope === "project" ? resolvedProjectId : null,
        enabled: true,
      } as const;
      if (editingKey) await memoryApi.update(editingKey, body);
      else await memoryApi.create(body);
      toast.success(editingKey ? "Memory updated" : "Memory saved");
      resetComposer();
      await load();
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not save memory");
    } finally {
      setSaving(false);
    }
  };

  const edit = (item: MemoryItem) => {
    setEditingKey(item.key);
    setContent(item.content);
    setCategory(item.category || "general");
  };

  const toggle = async (item: MemoryItem) => {
    await memoryApi.update(item.key, {
      content: item.content,
      category: item.category || "general",
      scope,
      project_id: scope === "project" ? resolvedProjectId : null,
      enabled: !item.enabled,
    });
    await load();
  };

  const remove = async (item: MemoryItem) => {
    try {
      await memoryApi.remove(item.key, scope, resolvedProjectId);
      if (editingKey === item.key) resetComposer();
      setItems((current) => current.filter((value) => value.key !== item.key));
      toast.success("Memory forgotten");
    } catch (error) {
      toast.error(error instanceof Error ? error.message : "Could not delete memory");
    }
  };

  return (
    <section className="space-y-5">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="flex items-center gap-2"><BrainCircuit className="h-4 w-4 text-primary" /><h3 className="text-sm font-semibold">Long-term memory</h3></div>
          <p className="mt-1 max-w-xl text-xs leading-5 text-muted-foreground">Control what Compass can recall across tasks. Project memories stay attached to the open workspace.</p>
        </div>
        <Button variant="ghost" size="sm" onClick={() => void load()} aria-label="Refresh memory"><RefreshCw className="h-4 w-4" /></Button>
      </div>

      <div className="inline-grid grid-cols-2 rounded-md border border-border bg-muted/40 p-1 text-xs">
        <button type="button" onClick={() => setScope("global")} className={`rounded px-3 py-1.5 ${scope === "global" ? "bg-background font-medium text-foreground shadow-sm" : "text-muted-foreground"}`}>Every project</button>
        <button type="button" disabled={!resolvedProjectId} onClick={() => setScope("project")} className={`rounded px-3 py-1.5 disabled:cursor-not-allowed disabled:opacity-40 ${scope === "project" ? "bg-background font-medium text-foreground shadow-sm" : "text-muted-foreground"}`}>This project</button>
      </div>

      <div className="space-y-3 border-l-2 border-primary/40 pl-4">
        <textarea value={content} onChange={(event) => setContent(event.target.value)} rows={3} placeholder="Example: Prefer small composable modules and explain architectural tradeoffs." className="w-full resize-y rounded-md border border-input bg-background px-3 py-2 text-sm leading-6 outline-none focus-visible:ring-2 focus-visible:ring-ring" />
        <div className="flex flex-wrap items-center gap-2">
          <Input value={category} onChange={(event) => setCategory(event.target.value)} className="h-8 max-w-44" aria-label="Memory category" placeholder="Category" />
          <Button size="sm" onClick={() => void save()} disabled={!content.trim() || saving || !available}>{saving ? <Loader2 className="h-4 w-4 animate-spin" /> : editingKey ? <Pencil className="h-4 w-4" /> : <Plus className="h-4 w-4" />}{editingKey ? "Save memory" : "Remember this"}</Button>
          {editingKey && <Button size="sm" variant="ghost" onClick={resetComposer}>Cancel</Button>}
        </div>
      </div>

      {!available ? <p className="rounded-md border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-amber-700 dark:text-amber-300">Memory storage is unavailable. Check the database configuration.</p> : loading ? <div className="flex items-center gap-2 py-6 text-xs text-muted-foreground"><Loader2 className="h-4 w-4 animate-spin" /> Loading memories</div> : items.length === 0 ? <div className="py-6 text-sm text-muted-foreground">Nothing saved in this scope yet.</div> : (
        <div className="divide-y divide-border border-y border-border">
          {items.map((item) => <div key={item.key} className="group flex items-start gap-3 py-3">
            <button type="button" role="switch" aria-checked={item.enabled} onClick={() => void toggle(item)} className={`mt-1 h-4 w-7 rounded-full p-0.5 transition-colors ${item.enabled ? "bg-primary" : "bg-muted-foreground/30"}`}><span className={`block h-3 w-3 rounded-full bg-white transition-transform ${item.enabled ? "translate-x-3" : "translate-x-0"}`} /></button>
            <div className="min-w-0 flex-1"><p className={`text-sm leading-5 ${item.enabled ? "text-foreground" : "text-muted-foreground line-through"}`}>{item.content}</p><p className="mt-1 font-mono text-[10px] text-muted-foreground">{item.category || "general"} · {item.key}</p></div>
            <div className="flex opacity-70 group-hover:opacity-100"><Button variant="ghost" size="sm" onClick={() => edit(item)} aria-label="Edit memory"><Pencil className="h-3.5 w-3.5" /></Button><Button variant="ghost" size="sm" onClick={() => void remove(item)} aria-label="Delete memory"><Trash2 className="h-3.5 w-3.5" /></Button></div>
          </div>)}
        </div>
      )}
    </section>
  );
}
