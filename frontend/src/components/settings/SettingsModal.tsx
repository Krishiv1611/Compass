import { useEffect, useMemo, useState } from "react";
import { Bot, Check, Loader2, LogOut, Palette, Settings, Shield, UserCircle } from "lucide-react";
import { preferencesApi } from "@/api";
import type { AuthUser } from "@/types/auth";
import { useAuth } from "@/contexts/AuthContext";
import { useTheme } from "@/components/ThemeProvider";
import GitHubConnectionPanel from "@/components/github/GitHubConnectionPanel";
import McpServerManager from "./McpServerManager";
import SkillsManager from "./SkillsManager";
import Modal from "@/components/ui/modal";
import MemoryManager from "./MemoryManager";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

interface SafePreferences {
  theme: "light" | "dark" | "system";
  model: string;
  llm_provider: string;
  language: string;
  safe_mode: boolean;
  fast_mode: boolean;
  has_llm_api_key: boolean;
}

const defaults: SafePreferences = {
  theme: "system",
  model: "google/gemma-4-31b-it:free",
  llm_provider: "openrouter",
  language: "en",
  safe_mode: false,
  fast_mode: false,
  has_llm_api_key: false,
};

const normalizeTab = (value?: string) => {
  if (value === "defaults" || value === "model") return "model";
  if (value === "appearance") return "appearance";
  if (value === "advanced" || value === "skills" || value === "mcp" || value === "tools") return "advanced";
  if (value === "memory") return "memory";
  return "account";
};

export default function SettingsModal({
  open,
  onOpenChange,
  user,
  initialTab,
  projectId,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  user: AuthUser | null;
  projectId?: string | null;
  initialTab?: string;
}) {
  const { signOut } = useAuth();
  const { theme, setTheme } = useTheme();
  const [preferences, setPreferences] = useState<SafePreferences>(defaults);
  const [newApiKey, setNewApiKey] = useState("");
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const activeTab = useMemo(() => normalizeTab(initialTab), [initialTab]);

  useEffect(() => {
    if (!open || !user) return;
    setLoading(true);
    setError(null);
    preferencesApi.getSettings()
      .then((value) => setPreferences({ ...defaults, ...value, theme: value.theme || theme }))
      .catch((requestError) => setError(requestError instanceof Error ? requestError.message : "Could not load settings"))
      .finally(() => setLoading(false));
  }, [open, theme, user]);

  const save = async () => {
    if (!preferences.model.trim()) {
      setError("Choose a model before saving.");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      const saved = await preferencesApi.updateSettings({
        theme: preferences.theme,
        model: preferences.model.trim(),
        llm_provider: preferences.llm_provider,
        language: preferences.language,
        safe_mode: preferences.safe_mode,
        fast_mode: preferences.fast_mode,
        ...(newApiKey ? { llm_api_key: newApiKey } : {}),
      });
      setPreferences({ ...defaults, ...saved });
      setNewApiKey("");
      setTheme(preferences.theme);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Could not save settings");
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal open={open} onClose={() => onOpenChange(false)} maxWidth="max-w-3xl" showClose ariaLabel="Settings">
      <div className="flex h-[min(760px,86vh)] flex-col">
        <div className="border-b border-border px-5 py-4">
          <div className="flex items-center gap-2"><Settings className="h-5 w-5 text-primary" /><h2 className="text-base font-semibold">Settings</h2></div>
          <p className="mt-1 text-xs text-muted-foreground">Account, model, appearance, and advanced authoring.</p>
        </div>
        {!user ? <div className="flex flex-1 items-center justify-center p-6 text-sm text-muted-foreground">Sign in to edit persistent settings.</div> : loading ? (
          <div className="flex flex-1 items-center justify-center gap-2 text-sm text-muted-foreground"><Loader2 className="h-4 w-4 animate-spin" /> Loading settings</div>
        ) : (
          <Tabs key={activeTab} defaultValue={activeTab} className="flex min-h-0 flex-1 flex-col">
            <div className="border-b border-border px-5 py-2">
              <TabsList className="grid w-full grid-cols-5">
                <TabsTrigger value="account">Account</TabsTrigger>
                <TabsTrigger value="model">Model</TabsTrigger>
                <TabsTrigger value="appearance">Appearance</TabsTrigger>
                <TabsTrigger value="advanced">Advanced</TabsTrigger>
              </TabsList>
                <TabsTrigger value="memory">Memory</TabsTrigger>
            </div>
            {error && <p role="alert" className="mx-5 mt-4 border border-destructive/30 bg-destructive/10 px-3 py-2 text-xs text-destructive">{error}</p>}
            <div className="min-h-0 flex-1 overflow-y-auto">
              <TabsContent value="account" className="m-0 space-y-6 p-5">
                <section>
                  <div className="flex items-start gap-3 border-b border-border pb-5">
                    <span className="flex h-10 w-10 items-center justify-center rounded-full bg-primary/10 text-primary">{user.avatar_url ? <img src={user.avatar_url} alt="" className="h-10 w-10 rounded-full" /> : <UserCircle className="h-5 w-5" />}</span>
                    <div className="min-w-0 flex-1"><p className="truncate text-sm font-semibold">{user.display_name || user.email}</p><p className="mt-1 truncate text-xs text-muted-foreground">{user.email}</p></div>
                    <Button variant="outline" size="sm" onClick={async () => { await signOut(); onOpenChange(false); }}><LogOut className="h-4 w-4" /> Sign out</Button>
                  </div>
                </section>
                <GitHubConnectionPanel />
              </TabsContent>
              <TabsContent value="model" className="m-0 space-y-5 p-5">
                <SectionTitle icon={Bot} title="Model defaults" description="These choices apply to new tasks unless the composer overrides them." />
                <Field label="Provider"><select value={preferences.llm_provider} onChange={(event) => setPreferences((value) => ({ ...value, llm_provider: event.target.value }))} className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm"><option value="openrouter">OpenRouter</option><option value="openai">OpenAI</option><option value="anthropic">Anthropic</option><option value="groq">Groq</option><option value="gemini">Gemini</option></select></Field>
                <Field label="Model"><Input value={preferences.model} onChange={(event) => setPreferences((value) => ({ ...value, model: event.target.value }))} placeholder="Provider model identifier" /></Field>
                <Field label={preferences.has_llm_api_key ? "Replace API key" : "API key"} help="Write-only. Compass encrypts this value on the backend and never returns it to the browser."><Input type="password" autoComplete="off" value={newApiKey} onChange={(event) => setNewApiKey(event.target.value)} placeholder={preferences.has_llm_api_key ? "A credential is already stored" : "Enter provider credential"} /></Field>
                <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={preferences.safe_mode} onChange={(event) => setPreferences((value) => ({ ...value, safe_mode: event.target.checked }))} /> Require additional approval for risky changes</label>
              </TabsContent>
              <TabsContent value="appearance" className="m-0 space-y-5 p-5">
                <SectionTitle icon={Palette} title="Appearance" description="Theme changes update the full workbench, editor, syntax, dialogs, and toasts." />
                <div className="grid grid-cols-3 gap-2">{(["system", "light", "dark"] as const).map((option) => <button key={option} type="button" onClick={() => { setPreferences((value) => ({ ...value, theme: option })); setTheme(option); }} className={`rounded-md border px-3 py-4 text-sm font-medium capitalize ${preferences.theme === option ? "border-primary bg-primary/10 text-primary" : "border-border hover:bg-muted"}`}>{option}</button>)}</div>
                <Field label="Interface language"><Input value={preferences.language} onChange={(event) => setPreferences((value) => ({ ...value, language: event.target.value }))} /></Field>
              </TabsContent>
              <TabsContent value="advanced" className="m-0 space-y-8 p-5">
                <SectionTitle icon={Shield} title="Advanced" description="Author reusable skills and inspect server-managed remote capabilities. Select skills for normal tasks from the context workflow." />
              <TabsContent value="memory" className="m-0 p-5">
                <MemoryManager projectId={projectId} />
              </TabsContent>
                <SkillsManager />
                <div className="border-t border-border pt-6"><McpServerManager /></div>
              </TabsContent>
            </div>
          </Tabs>
        )}
        <div className="flex justify-end gap-2 border-t border-border px-5 py-3">
          <Button variant="outline" onClick={() => onOpenChange(false)}>Close</Button>
          <Button onClick={() => void save()} disabled={!user || loading || saving}>{saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Check className="h-4 w-4" />} Save changes</Button>
        </div>
      </div>
    </Modal>
  );
}

function SectionTitle({ icon: Icon, title, description }: { icon: React.ComponentType<{ className?: string }>; title: string; description: string }) {
  return <div><div className="flex items-center gap-2"><Icon className="h-4 w-4 text-primary" /><h3 className="text-sm font-semibold">{title}</h3></div><p className="mt-1 text-xs leading-5 text-muted-foreground">{description}</p></div>;
}

function Field({ label, help, children }: { label: string; help?: string; children: React.ReactNode }) {
  return <label className="block space-y-2"><span className="text-xs font-medium">{label}</span>{children}{help && <span className="block text-xs leading-5 text-muted-foreground">{help}</span>}</label>;
}
