import { useEffect, useMemo, useState } from "react";
import { Activity, Bot, Check, Loader2, LogOut, Palette, Settings, Shield, UserCircle } from "lucide-react";
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
import { useWorkbench } from "@/contexts/WorkbenchContext";

interface SafePreferences {
  theme: "light" | "dark" | "system";
  model: string;
  llm_provider: string;
  language: string;
  safe_mode: boolean;
  fast_mode: boolean;
  has_llm_api_key: boolean;
}

interface ProviderTestResult {
  provider: string;
  model: string;
  success: boolean;
  latency_ms: number;
  error: string | null;
}

interface ModelPreset {
  label: string;
  model: string;
  provider?: string;
  tags: { label: string; className: string }[];
}

const FREE_MODEL_PRESETS: ModelPreset[] = [
  { label: "openrouter/free (Auto)", model: "openrouter/free", tags: [{ label: "Auto", className: "border-emerald-500/30 bg-emerald-500/10 text-emerald-400" }] },
  { label: "DeepSeek R1 :free", model: "deepseek/deepseek-r1:free", tags: [{ label: "Reasoning", className: "border-indigo-500/30 bg-indigo-500/10 text-indigo-300" }] },
  { label: "Qwen 2.5 Coder :free", model: "qwen/qwen-2.5-coder-32b-instruct:free", tags: [{ label: "Coder", className: "border-sky-500/30 bg-sky-500/10 text-sky-300" }] },
  { label: "Llama 3.3 70B :free", model: "meta-llama/llama-3.3-70b-instruct:free", tags: [{ label: "General", className: "border-indigo-500/30 bg-indigo-500/10 text-indigo-300" }] },
  { label: "DeepSeek V3 :free", model: "deepseek/deepseek-chat:free", tags: [{ label: "Coder", className: "border-sky-500/30 bg-sky-500/10 text-sky-300" }] },
];

const STANDARD_MODEL_PRESETS: ModelPreset[] = [
  { label: "Gemini 3.8 Flash", model: "gemini/gemini-3.8-flash", provider: "google", tags: [{ label: "Vision", className: "border-amber-500/30 bg-amber-500/10 text-amber-300" }, { label: "Fast", className: "border-emerald-500/30 bg-emerald-500/10 text-emerald-400" }] },
  { label: "DeepSeek R1", model: "deepseek/deepseek-r1", provider: "openrouter", tags: [{ label: "Reasoning", className: "border-indigo-500/30 bg-indigo-500/10 text-indigo-300" }] },
  { label: "Qwen 2.5 Coder", model: "qwen/qwen-2.5-coder-32b-instruct", provider: "openrouter", tags: [{ label: "Coder", className: "border-sky-500/30 bg-sky-500/10 text-sky-300" }] },
  { label: "Llama 3.3 70B", model: "meta-llama/llama-3.3-70b-instruct", provider: "openrouter", tags: [{ label: "General", className: "border-indigo-500/30 bg-indigo-500/10 text-indigo-300" }] },
  { label: "DeepSeek V3", model: "deepseek/deepseek-chat", provider: "openrouter", tags: [{ label: "Coder", className: "border-sky-500/30 bg-sky-500/10 text-sky-300" }] },
  { label: "Codestral", model: "mistralai/codestral-2501", provider: "openrouter", tags: [{ label: "Coder", className: "border-sky-500/30 bg-sky-500/10 text-sky-300" }] },
  { label: "Nemotron 70B", model: "nvidia/llama-3.1-nemotron-70b-instruct", provider: "openrouter", tags: [{ label: "Reasoning", className: "border-indigo-500/30 bg-indigo-500/10 text-indigo-300" }] },
];

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
  if (value === "skills") return "skills";
  if (value === "advanced" || value === "mcp" || value === "tools") return "advanced";
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
  const { setTheme } = useTheme();
  const { state, dispatch } = useWorkbench();
  const [preferences, setPreferences] = useState<SafePreferences>(defaults);
  const [newApiKey, setNewApiKey] = useState("");
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [providerBusy, setProviderBusy] = useState<"test" | "remove" | null>(null);
  const [testResult, setTestResult] = useState<ProviderTestResult | null>(null);
  const activeTab = useMemo(() => normalizeTab(initialTab), [initialTab]);

  useEffect(() => {
    if (!open || !user) return;
    setLoading(true);
    setLoaded(false);
    setNewApiKey("");
    setError(null);
    setTestResult(null);
    preferencesApi.getSettings()
      .then((value) => { setPreferences({ ...defaults, ...value, theme: value.theme || "system" }); setLoaded(true); })
      .catch((requestError) => setError(requestError instanceof Error ? requestError.message : "Could not load settings"))
      .finally(() => setLoading(false));
  }, [open, user]);

  const close = () => { setNewApiKey(""); setTestResult(null); onOpenChange(false); };

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
      window.dispatchEvent(new CustomEvent("compass:settings-changed", { detail: saved }));
      setNewApiKey("");
      setTheme(preferences.theme);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Could not save settings");
    } finally {
      setSaving(false);
    }
  };

  const testProvider = async () => {
    setProviderBusy("test");
    setError(null);
    setTestResult(null);
    try {
      const result = (await preferencesApi.testProvider({
        provider: preferences.llm_provider,
        model: preferences.model.trim(),
        ...(newApiKey ? { api_key: newApiKey } : {}),
      })) as ProviderTestResult;
      setTestResult(result);
      if (!result.success && result.error) {
        setError(result.error);
      }
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "Provider test failed");
      setTestResult(null);
    } finally {
      setProviderBusy(null);
    }
  };

  const removeCredential = async () => {
    setProviderBusy("remove"); setError(null);
    try {
      const saved = await preferencesApi.removeCredential(preferences.llm_provider);
      setPreferences({ ...defaults, ...saved });
      window.dispatchEvent(new CustomEvent("compass:settings-changed", { detail: saved }));
      setNewApiKey("");
    } catch (requestError) { setError(requestError instanceof Error ? requestError.message : "Could not remove credential"); }
    finally { setProviderBusy(null); }
  };

  return (
    <Modal open={open} onClose={close} maxWidth="max-w-3xl" showClose ariaLabel="Settings">
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
              <TabsList className="grid w-full grid-cols-6">
                <TabsTrigger value="account">Account</TabsTrigger>
                <TabsTrigger value="model">Model</TabsTrigger>
                <TabsTrigger value="appearance">Appearance</TabsTrigger>
                <TabsTrigger value="memory">Memory</TabsTrigger>
                <TabsTrigger value="skills">Skills</TabsTrigger>
                <TabsTrigger value="advanced">Advanced</TabsTrigger>
              </TabsList>
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
                <Field label="Provider">
                  <select
                    value={preferences.llm_provider}
                    onChange={(event) => {
                      setPreferences((value) => ({ ...value, llm_provider: event.target.value }));
                      setTestResult(null);
                    }}
                    className="h-9 w-full rounded-md border border-input bg-background px-3 text-sm"
                  >
                    <option value="openrouter">OpenRouter (DeepSeek, Qwen, Llama)</option>
                    <option value="litellm">LiteLLM Proxy Router</option>
                    <option value="google">Google Gemini</option>
                    <option value="openai">OpenAI</option>
                    <option value="anthropic">Anthropic</option>
                  </select>
                </Field>
                <div>
                  <Field label="Model">
                    <Input
                      value={preferences.model}
                      onChange={(event) => {
                        setPreferences((value) => ({ ...value, model: event.target.value }));
                        setTestResult(null);
                      }}
                      placeholder="Provider model identifier (e.g. qwen/qwen-2.5-coder-32b-instruct)"
                    />
                  </Field>
                  <div className="mt-3 space-y-3">
                    <div>
                      <div className="flex items-center gap-1.5 mb-1.5">
                        <span className="text-[11px] font-semibold text-emerald-400">Free Models</span>
                        <span className="text-[10px] text-muted-foreground font-mono">(Zero credits required on OpenRouter)</span>
                      </div>
                      <div className="flex flex-wrap gap-1.5">
                        {FREE_MODEL_PRESETS.map((preset) => {
                          const isSelected = preferences.model === preset.model;
                          return (
                            <button
                              key={preset.model}
                              type="button"
                              onClick={() => {
                                setPreferences((prev) => ({
                                  ...prev,
                                  llm_provider: "openrouter",
                                  model: preset.model,
                                }));
                                setTestResult(null);
                              }}
                              className={`flex items-center gap-1.5 rounded border px-2 py-1 font-mono text-[11px] transition-colors ${
                                isSelected
                                  ? "border-emerald-500 bg-emerald-500/15 text-emerald-300 font-medium shadow-[0_0_10px_rgba(16,185,129,0.15)]"
                                  : "border-emerald-500/30 bg-emerald-500/5 text-emerald-300/90 hover:border-emerald-500/60 hover:bg-emerald-500/10"
                              }`}
                            >
                              <span>{preset.label}</span>
                              <div className="flex items-center gap-1">
                                {preset.tags.map((tag) => (
                                  <span
                                    key={tag.label}
                                    className={`rounded border px-1 py-0.2 text-[9px] font-sans font-medium tracking-tight ${tag.className}`}
                                  >
                                    {tag.label}
                                  </span>
                                ))}
                              </div>
                            </button>
                          );
                        })}
                      </div>
                    </div>

                    <div>
                      <div className="flex items-center gap-1.5 mb-1.5">
                        <span className="text-[11px] font-semibold text-muted-foreground">Standard / Direct Models</span>
                      </div>
                      <div className="flex flex-wrap gap-1.5">
                        {STANDARD_MODEL_PRESETS.map((preset) => {
                          const isSelected = preferences.model === preset.model;
                          return (
                            <button
                              key={preset.model}
                              type="button"
                              onClick={() => {
                                setPreferences((prev) => ({
                                  ...prev,
                                  llm_provider: preset.provider || prev.llm_provider,
                                  model: preset.model,
                                }));
                                setTestResult(null);
                              }}
                              className={`flex items-center gap-1.5 rounded border px-2 py-1 font-mono text-[11px] transition-colors ${
                                isSelected
                                  ? "border-primary bg-primary/15 text-primary font-medium shadow-[0_0_10px_rgba(99,102,241,0.15)]"
                                  : "border-border/80 bg-muted/40 text-muted-foreground hover:border-sky-500/50 hover:bg-muted hover:text-foreground"
                              }`}
                            >
                              <span>{preset.label}</span>
                              <div className="flex items-center gap-1">
                                {preset.tags.map((tag) => (
                                  <span
                                    key={tag.label}
                                    className={`rounded border px-1 py-0.2 text-[9px] font-sans font-medium tracking-tight ${tag.className}`}
                                  >
                                    {tag.label}
                                  </span>
                                ))}
                              </div>
                            </button>
                          );
                        })}
                      </div>
                    </div>
                  </div>
                </div>
                <Field label={preferences.has_llm_api_key ? "Replace API key" : "API key"} help="Write-only. Compass encrypts this value on the backend and never returns it to the browser."><Input type="password" autoComplete="off" value={newApiKey} onChange={(event) => setNewApiKey(event.target.value)} placeholder={preferences.has_llm_api_key ? "A credential is already stored" : "Enter provider credential"} /></Field>
                <div className="flex flex-wrap items-center gap-2.5">
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => void testProvider()}
                    disabled={!preferences.model.trim() || !!providerBusy}
                    className="h-8 border-sky-500/30 hover:border-sky-500/60 hover:bg-sky-500/10"
                  >
                    {providerBusy === "test" ? (
                      <>
                        <Loader2 className="h-3.5 w-3.5 animate-spin text-sky-400" />
                        <span>Pinging provider...</span>
                      </>
                    ) : (
                      <>
                        <Activity className="h-3.5 w-3.5 text-sky-400" />
                        <span>Test provider</span>
                      </>
                    )}
                  </Button>
                  {preferences.has_llm_api_key && (
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={() => void removeCredential()}
                      disabled={!!providerBusy}
                      className="h-8 text-xs text-muted-foreground hover:text-destructive"
                    >
                      {providerBusy === "remove" && <Loader2 className="h-3.5 w-3.5 animate-spin" />}
                      Remove credential
                    </Button>
                  )}
                  {testResult && (
                    <div
                      role="status"
                      className={`inline-flex items-center gap-2 rounded-full border px-2.5 py-1 text-xs font-medium font-mono ${
                        testResult.success
                          ? "border-emerald-500/40 bg-emerald-500/10 text-emerald-300 shadow-[0_0_12px_rgba(16,185,129,0.15)]"
                          : "border-destructive/40 bg-destructive/10 text-destructive"
                      }`}
                    >
                      <span className="relative flex h-2 w-2">
                        {testResult.success && (
                          <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />
                        )}
                        <span
                          className={`relative inline-flex h-2 w-2 rounded-full ${
                            testResult.success ? "bg-emerald-400" : "bg-destructive"
                          }`}
                        />
                      </span>
                      <span>
                        Ping: {testResult.latency_ms}ms · {testResult.success ? "Operational" : "Failed"}
                      </span>
                    </div>
                  )}
                </div>
                <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={preferences.safe_mode} onChange={(event) => setPreferences((value) => ({ ...value, safe_mode: event.target.checked }))} /> Stage agent file changes for review</label>
                <label className="flex items-center gap-2 text-sm"><input type="checkbox" checked={preferences.fast_mode} onChange={(event) => setPreferences((value) => ({ ...value, fast_mode: event.target.checked }))} /> Reduce approval prompts; shell and custom tools still require approval</label>
              </TabsContent>
              <TabsContent value="appearance" className="m-0 space-y-5 p-5">
                <SectionTitle icon={Palette} title="Appearance" description="Theme changes update the full workbench, editor, syntax, dialogs, and toasts." />
                <div className="grid grid-cols-3 gap-2">{(["system", "light", "dark"] as const).map((option) => <button key={option} type="button" onClick={() => { setPreferences((value) => ({ ...value, theme: option })); setTheme(option); }} className={`rounded-md border px-3 py-4 text-sm font-medium capitalize ${preferences.theme === option ? "border-primary bg-primary/10 text-primary" : "border-border hover:bg-muted"}`}>{option}</button>)}</div>
                <Field label="Interface language"><Input value={preferences.language} onChange={(event) => setPreferences((value) => ({ ...value, language: event.target.value }))} /></Field>
              </TabsContent>
              <TabsContent value="advanced" className="m-0 space-y-8 p-5">
                <SectionTitle icon={Shield} title="Advanced" description="Author reusable skills and inspect server-managed remote capabilities. Select skills for normal tasks from the context workflow." />
                <div className="border-t border-border pt-6"><McpServerManager /></div>
              </TabsContent>
              <TabsContent value="memory" className="m-0 p-5"><MemoryManager projectId={projectId} /></TabsContent>
              <TabsContent value="skills" className="m-0 p-5"><SkillsManager activeSkill={state.activeSkill} onActiveSkillChange={(skill) => dispatch({ type: "setActiveSkill", skill })} /></TabsContent>
            </div>
          </Tabs>
        )}
        <div className="flex justify-end gap-2 border-t border-border px-5 py-3">
          <Button variant="outline" onClick={close}>Close</Button>
          <Button onClick={() => void save()} disabled={!user || !loaded || loading || saving}>{saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Check className="h-4 w-4" />} Save changes</Button>
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
