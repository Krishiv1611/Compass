import { useCallback, useEffect, useState } from "react";
import { Brain, ChevronDown, ChevronRight, Loader2, Plus, Sparkles, Trash2, Wrench, X } from "lucide-react";
import { toast } from "react-toastify";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { skillsApi } from "@/api";

type Skill = {
  name: string;
  description: string;
  system_prompt: string;
  allowed_tools: string[] | null;
  model: string | null;
  max_turns: number;
  source_path: string;
};

const errorMessage = (error: unknown, fallback: string) => error instanceof Error ? error.message : fallback;

export default function SkillsManager({ activeSkill = null, onActiveSkillChange }: { activeSkill?: string | null; onActiveSkillChange?: (name: string | null) => void }) {
  const [skills, setSkills] = useState<Skill[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [expandedSkill, setExpandedSkill] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [deletingSkill, setDeletingSkill] = useState<string | null>(null);
  const [formName, setFormName] = useState("");
  const [formDescription, setFormDescription] = useState("");
  const [formPrompt, setFormPrompt] = useState("");
  const [formTools, setFormTools] = useState("");
  const [formModel, setFormModel] = useState("");
  const [formMaxTurns, setFormMaxTurns] = useState(8);

  const fetchSkills = useCallback(async () => {
    setIsLoading(true);
    try {
      setSkills(await skillsApi.listSkills());
    } catch (error) {
      toast.error(errorMessage(error, "Could not load skills"));
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => { void fetchSkills(); }, [fetchSkills]);

  const resetForm = () => {
    setFormName(""); setFormDescription(""); setFormPrompt(""); setFormTools(""); setFormModel(""); setFormMaxTurns(8); setShowForm(false);
  };

  const handleCreate = async () => {
    if (!formName.trim() || !formDescription.trim() || !formPrompt.trim()) {
      toast.error("Name, description, and system prompt are required.");
      return;
    }
    setIsSaving(true);
    try {
      const allowedTools = formTools.split(",").map((tool) => tool.trim()).filter(Boolean);
      await skillsApi.createSkill({
        name: formName.trim().toLowerCase().replace(/\s+/g, "-"),
        description: formDescription.trim(),
        system_prompt: formPrompt.trim(),
        allowed_tools: allowedTools.length ? allowedTools : undefined,
        model: formModel.trim() || undefined,
        max_turns: formMaxTurns,
      });
      toast.success(`Skill "${formName}" created`);
      resetForm();
      await fetchSkills();
    } catch (error) {
      toast.error(errorMessage(error, "Could not create skill"));
    } finally {
      setIsSaving(false);
    }
  };

  const handleDelete = async (name: string) => {
    setDeletingSkill(name);
    try {
      await skillsApi.deleteSkill(name);
      toast.success(`Skill "${name}" deleted`);
      await fetchSkills();
    } catch (error) {
      toast.error(errorMessage(error, "Could not delete skill"));
    } finally {
      setDeletingSkill(null);
    }
  };

  if (isLoading) return <div className="flex items-center justify-center gap-2 py-12 text-sm text-muted-foreground"><Loader2 className="h-4 w-4 animate-spin" /> Loading skills…</div>;

  return (
    <section className="space-y-4" aria-labelledby="skills-heading">
      <div className="flex items-center justify-between gap-3">
        <div><h3 id="skills-heading" className="flex items-center gap-2 text-sm font-semibold"><Sparkles className="h-4 w-4 text-primary" /> Skill authoring</h3><p className="mt-1 text-xs text-muted-foreground">Create reusable instructions for specialized project work.</p></div>
        <Button type="button" size="sm" variant={showForm ? "ghost" : "default"} onClick={() => showForm ? resetForm() : setShowForm(true)}>{showForm ? <X className="h-3.5 w-3.5" /> : <Plus className="h-3.5 w-3.5" />} {showForm ? "Cancel" : "New skill"}</Button>
      </div>

      {showForm && (
        <div className="space-y-3 border-y border-border bg-muted/20 p-4">
          <div className="grid gap-3 sm:grid-cols-2">
            <Field id="skill-name" label="Name"><Input id="skill-name" value={formName} onChange={(event) => setFormName(event.target.value)} placeholder="code-review" /></Field>
            <Field id="skill-turns" label="Maximum turns"><Input id="skill-turns" type="number" value={formMaxTurns} onChange={(event) => setFormMaxTurns(Number(event.target.value))} min={1} max={50} /></Field>
          </div>
          <Field id="skill-description" label="Description"><Input id="skill-description" value={formDescription} onChange={(event) => setFormDescription(event.target.value)} placeholder="Review code for correctness, security, and maintainability" /></Field>
          <Field id="skill-prompt" label="Instructions"><textarea id="skill-prompt" value={formPrompt} onChange={(event) => setFormPrompt(event.target.value)} placeholder="Describe how this skill should approach its work…" className="min-h-32 w-full resize-y rounded-md border border-input bg-background px-3 py-2 text-sm outline-none placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-2 focus-visible:ring-ring/40" /></Field>
          <div className="grid gap-3 sm:grid-cols-2">
            <Field id="skill-tools" label="Allowed tools"><Input id="skill-tools" value={formTools} onChange={(event) => setFormTools(event.target.value)} placeholder="read_file, grep_search" /></Field>
            <Field id="skill-model" label="Model override"><Input id="skill-model" value={formModel} onChange={(event) => setFormModel(event.target.value)} placeholder="Use workspace default" /></Field>
          </div>
          <div className="flex justify-end"><Button type="button" size="sm" onClick={() => void handleCreate()} disabled={isSaving}>{isSaving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Sparkles className="h-3.5 w-3.5" />} Create skill</Button></div>
        </div>
      )}

      {!skills.length ? (
        <div className="border-y border-dashed border-border px-4 py-8 text-center"><Brain className="mx-auto mb-3 h-7 w-7 text-muted-foreground" /><p className="text-sm font-medium">No skills yet</p><p className="mt-1 text-xs text-muted-foreground">Create a skill when a workflow needs reusable instructions.</p></div>
      ) : (
        <div className="divide-y divide-border border-y border-border">
          {skills.map((skill) => {
            const expanded = expandedSkill === skill.name;
            return (
              <article key={skill.name}>
                <div className="flex items-center gap-1">
                  <button type="button" className="flex min-w-0 flex-1 items-center gap-3 px-2 py-3 text-left hover:bg-muted/40" onClick={() => setExpandedSkill(expanded ? null : skill.name)} aria-expanded={expanded}>
                    <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-primary/10 text-primary"><Sparkles className="h-4 w-4" /></span>
                    <span className="min-w-0 flex-1"><span className="flex items-center gap-2"><span className="truncate text-sm font-medium">{skill.name}</span><Badge variant="outline">{skill.max_turns} turns</Badge></span><span className="mt-0.5 block truncate text-xs text-muted-foreground">{skill.description}</span></span>
                    {expanded ? <ChevronDown className="h-4 w-4 shrink-0 text-muted-foreground" /> : <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground" />}
                  </button>
                  {onActiveSkillChange && <Button type="button" size="sm" variant={activeSkill === skill.name ? "default" : "outline"} onClick={() => onActiveSkillChange(activeSkill === skill.name ? null : skill.name)}>{activeSkill === skill.name ? "Active" : "Use next run"}</Button>}
                  <Button type="button" size="icon-sm" variant="ghost" className="mr-1 text-muted-foreground hover:bg-destructive/10 hover:text-destructive" onClick={() => void handleDelete(skill.name)} disabled={deletingSkill === skill.name} aria-label={`Delete ${skill.name}`} title="Delete skill">{deletingSkill === skill.name ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Trash2 className="h-3.5 w-3.5" />}</Button>
                </div>
                {expanded && (
                  <div className="space-y-3 border-t border-border bg-muted/10 px-4 py-3">
                    {!!skill.allowed_tools?.length && <div><p className="text-xs font-medium text-muted-foreground">Tools</p><div className="mt-2 flex flex-wrap gap-1">{skill.allowed_tools.map((tool) => <Badge key={tool} variant="outline"><Wrench className="h-3 w-3" /> {tool}</Badge>)}</div></div>}
                    {skill.model && <div><p className="text-xs font-medium text-muted-foreground">Model</p><p className="mt-1 font-mono text-xs">{skill.model}</p></div>}
                    <div><p className="text-xs font-medium text-muted-foreground">Instructions</p><pre className="mt-1 max-h-40 overflow-auto whitespace-pre-wrap border-l-2 border-border pl-3 font-mono text-xs text-muted-foreground">{skill.system_prompt}</pre></div>
                  </div>
                )}
              </article>
            );
          })}
        </div>
      )}
    </section>
  );
}

function Field({ id, label, children }: { id: string; label: string; children: React.ReactNode }) {
  return <div><label htmlFor={id} className="mb-1.5 block text-xs font-medium">{label}</label>{children}</div>;
}
