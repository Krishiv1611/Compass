import { useEffect, useState } from "react";
import {
  Brain,
  ChevronDown,
  ChevronRight,
  Loader2,
  Plus,
  Sparkles,
  Trash2,
  Wrench,
  X,
} from "lucide-react";
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

export default function SkillsManager() {
  const [skills, setSkills] = useState<Skill[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [showForm, setShowForm] = useState(false);
  const [expandedSkill, setExpandedSkill] = useState<string | null>(null);
  const [isSaving, setIsSaving] = useState(false);
  const [deletingSkill, setDeletingSkill] = useState<string | null>(null);

  // Form state
  const [formName, setFormName] = useState("");
  const [formDescription, setFormDescription] = useState("");
  const [formPrompt, setFormPrompt] = useState("");
  const [formTools, setFormTools] = useState("");
  const [formModel, setFormModel] = useState("");
  const [formMaxTurns, setFormMaxTurns] = useState(8);

  const fetchSkills = async () => {
    try {
      setIsLoading(true);
      const data = await skillsApi.listSkills();
      setSkills(data);
    } catch (error: any) {
      toast.error(error?.response?.data?.detail || "Failed to load skills");
    } finally {
      setIsLoading(false);
    }
  };

  useEffect(() => {
    fetchSkills();
  }, []);

  const resetForm = () => {
    setFormName("");
    setFormDescription("");
    setFormPrompt("");
    setFormTools("");
    setFormModel("");
    setFormMaxTurns(8);
    setShowForm(false);
  };

  const handleCreate = async () => {
    if (!formName.trim() || !formDescription.trim() || !formPrompt.trim()) {
      toast.error("Name, description, and system prompt are required.");
      return;
    }

    setIsSaving(true);
    try {
      const allowedTools = formTools
        .split(",")
        .map((t) => t.trim())
        .filter(Boolean);

      await skillsApi.createSkill({
        name: formName.trim().toLowerCase().replace(/\s+/g, "-"),
        description: formDescription.trim(),
        system_prompt: formPrompt.trim(),
        allowed_tools: allowedTools.length > 0 ? allowedTools : undefined,
        model: formModel.trim() || undefined,
        max_turns: formMaxTurns,
      });

      toast.success(`Skill "${formName}" created`);
      resetForm();
      await fetchSkills();
    } catch (error: any) {
      toast.error(error?.response?.data?.detail || "Failed to create skill");
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
    } catch (error: any) {
      toast.error(error?.response?.data?.detail || "Failed to delete skill");
    } finally {
      setDeletingSkill(null);
    }
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12 gap-2 text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" /> Loading skills…
      </div>
    );
  }

  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-sm font-semibold flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-primary" /> Skills
          </h3>
          <p className="text-xs text-muted-foreground mt-0.5">
            Modular sub-agents loaded from SKILL.md files
          </p>
        </div>
        <Button
          size="sm"
          variant={showForm ? "ghost" : "default"}
          onClick={() => (showForm ? resetForm() : setShowForm(true))}
          className="rounded-full"
        >
          {showForm ? (
            <>
              <X className="h-3.5 w-3.5 mr-1" /> Cancel
            </>
          ) : (
            <>
              <Plus className="h-3.5 w-3.5 mr-1" /> New Skill
            </>
          )}
        </Button>
      </div>

      {/* Create Form */}
      {showForm && (
        <div className="rounded-lg border border-primary/30 bg-primary/5 p-4 space-y-3">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs font-medium text-muted-foreground mb-1 block">
                Name (kebab-case)
              </label>
              <Input
                value={formName}
                onChange={(e) => setFormName(e.target.value)}
                placeholder="code-review"
                className="h-8 text-sm"
              />
            </div>
            <div>
              <label className="text-xs font-medium text-muted-foreground mb-1 block">
                Max Turns
              </label>
              <Input
                type="number"
                value={formMaxTurns}
                onChange={(e) => setFormMaxTurns(Number(e.target.value))}
                min={1}
                max={50}
                className="h-8 text-sm"
              />
            </div>
          </div>

          <div>
            <label className="text-xs font-medium text-muted-foreground mb-1 block">
              Description
            </label>
            <Input
              value={formDescription}
              onChange={(e) => setFormDescription(e.target.value)}
              placeholder="Perform a thorough code review of the given code"
              className="h-8 text-sm"
            />
          </div>

          <div>
            <label className="text-xs font-medium text-muted-foreground mb-1 block">
              System Prompt
            </label>
            <textarea
              value={formPrompt}
              onChange={(e) => setFormPrompt(e.target.value)}
              placeholder="You are a senior code reviewer. Analyze the provided code for bugs, security issues, and style violations..."
              className="w-full min-h-[120px] rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground outline-none resize-y placeholder:text-muted-foreground/60 focus:ring-2 focus:ring-primary/20"
            />
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div>
              <label className="text-xs font-medium text-muted-foreground mb-1 block">
                Allowed Tools (comma-separated, empty = all)
              </label>
              <Input
                value={formTools}
                onChange={(e) => setFormTools(e.target.value)}
                placeholder="read_file, grep_search, list_dir"
                className="h-8 text-sm"
              />
            </div>
            <div>
              <label className="text-xs font-medium text-muted-foreground mb-1 block">
                Model Override (optional)
              </label>
              <Input
                value={formModel}
                onChange={(e) => setFormModel(e.target.value)}
                placeholder="Leave empty for default"
                className="h-8 text-sm"
              />
            </div>
          </div>

          <div className="flex justify-end">
            <Button
              size="sm"
              onClick={handleCreate}
              disabled={isSaving}
              className="rounded-full"
            >
              {isSaving ? (
                <Loader2 className="h-3.5 w-3.5 mr-1 animate-spin" />
              ) : (
                <Sparkles className="h-3.5 w-3.5 mr-1" />
              )}
              Create Skill
            </Button>
          </div>
        </div>
      )}

      {/* Skill List */}
      {skills.length === 0 ? (
        <div className="rounded-lg border border-dashed border-border p-8 text-center">
          <Brain className="h-8 w-8 mx-auto mb-3 text-muted-foreground/40" />
          <p className="text-sm text-muted-foreground">
            No skills registered yet
          </p>
          <p className="text-xs text-muted-foreground/70 mt-1">
            Create a skill to add modular, reusable sub-agents
          </p>
        </div>
      ) : (
        <div className="space-y-2">
          {skills.map((skill) => {
            const isExpanded = expandedSkill === skill.name;
            return (
              <div
                key={skill.name}
                className="rounded-lg border border-border bg-background/60 overflow-hidden transition-all"
              >
                <button
                  onClick={() =>
                    setExpandedSkill(isExpanded ? null : skill.name)
                  }
                  className="flex w-full items-center justify-between px-4 py-3 text-left hover:bg-muted/30 transition-colors"
                >
                  <div className="flex items-center gap-3 min-w-0">
                    <div className="flex size-8 shrink-0 items-center justify-center rounded-md bg-primary/10 text-primary">
                      <Sparkles className="h-4 w-4" />
                    </div>
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-sm font-medium truncate">
                          {skill.name}
                        </span>
                        <Badge
                          variant="outline"
                          className="text-[10px] shrink-0"
                        >
                          {skill.max_turns} turns
                        </Badge>
                      </div>
                      <p className="text-xs text-muted-foreground truncate mt-0.5">
                        {skill.description}
                      </p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2 shrink-0 ml-2">
                    <Button
                      size="sm"
                      variant="ghost"
                      className="h-7 w-7 p-0 text-muted-foreground hover:text-red-400 hover:bg-red-500/10"
                      onClick={(e) => {
                        e.stopPropagation();
                        handleDelete(skill.name);
                      }}
                      disabled={deletingSkill === skill.name}
                    >
                      {deletingSkill === skill.name ? (
                        <Loader2 className="h-3.5 w-3.5 animate-spin" />
                      ) : (
                        <Trash2 className="h-3.5 w-3.5" />
                      )}
                    </Button>
                    {isExpanded ? (
                      <ChevronDown className="h-4 w-4 text-muted-foreground" />
                    ) : (
                      <ChevronRight className="h-4 w-4 text-muted-foreground" />
                    )}
                  </div>
                </button>

                {isExpanded && (
                  <div className="border-t border-border px-4 py-3 space-y-2 bg-muted/5">
                    {skill.allowed_tools && skill.allowed_tools.length > 0 && (
                      <div>
                        <span className="text-[10px] uppercase tracking-wider text-muted-foreground font-semibold">
                          Tools
                        </span>
                        <div className="flex flex-wrap gap-1 mt-1">
                          {skill.allowed_tools.map((t) => (
                            <Badge
                              key={t}
                              variant="outline"
                              className="text-[10px] gap-1"
                            >
                              <Wrench className="h-2.5 w-2.5" /> {t}
                            </Badge>
                          ))}
                        </div>
                      </div>
                    )}
                    {skill.model && (
                      <div>
                        <span className="text-[10px] uppercase tracking-wider text-muted-foreground font-semibold">
                          Model
                        </span>
                        <p className="text-xs text-foreground mt-0.5">
                          {skill.model}
                        </p>
                      </div>
                    )}
                    <div>
                      <span className="text-[10px] uppercase tracking-wider text-muted-foreground font-semibold">
                        System Prompt
                      </span>
                      <pre className="mt-1 max-h-40 overflow-auto rounded-md border border-border bg-background p-2 text-xs text-muted-foreground whitespace-pre-wrap">
                        {skill.system_prompt}
                      </pre>
                    </div>
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
