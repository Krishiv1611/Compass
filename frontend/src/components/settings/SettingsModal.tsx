import { useEffect, useMemo, useState } from "react";
import {
  Brain,
  Check,
  Loader2,
  Settings,
  Sparkles,
  UserCircle,
  Wrench,
  LogOut,
  Paperclip,
  Trash2,
  Globe,
  Terminal as TerminalIcon,
  Shield,
} from "lucide-react";
import { toast } from "react-toastify";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import Modal from "@/components/ui/modal";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { settingsApi, toolsApi, uploadsApi, authApi } from "@/api";
import { useTheme } from "@/components/ThemeProvider";
import McpServerManager from "./McpServerManager";
import SkillsManager from "./SkillsManager";

type SettingsDrawerProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  user: any | null;
  sessionId?: string | null;
  initialTab?: string;
};

type ToolInfo = {
  name: string;
  description: string;
  environment?: string;
};

type UploadInfo = {
  id: string;
  filename: string;
  size_bytes: number;
  status: string;
  chunk_count?: number;
};

const defaultSettings = {
  theme: "dark",
  llm_provider: "openrouter",
  llm_api_key: "",
  model: "google/gemma-4-31b-it:free",
  language: "en",
  guardrails_enabled: true,
  safe_mode: false,
  fast_mode: false,
  long_term_memory: [] as string[],
};

function formatBytes(bytes: number): string {
  if (bytes === 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / k ** i).toFixed(1))} ${sizes[i]}`;
}

export default function SettingsModal({
  open,
  onOpenChange,
  user,
  initialTab,
  sessionId,
}: SettingsDrawerProps) {
  const [settings, setSettings] = useState<Record<string, any>>(defaultSettings);
  const [tools, setTools] = useState<ToolInfo[]>([]);
  const [uploads, setUploads] = useState<UploadInfo[]>([]);
  const [uploadCaps, setUploadCaps] = useState<any>(null);
  const [memoryText, setMemoryText] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [isDeletingUpload, setIsDeletingUpload] = useState<string | null>(null);
  const { setTheme } = useTheme();

  const displayName =
    user?.display_name || user?.email?.split("@")[0] || "Signed out";
  const accountMeta = useMemo(() => {
    if (!user) return "Sign in to persist sessions, files, preferences, and memory.";
    const createdAt = user.created_at
      ? new Date(user.created_at).toLocaleDateString()
      : "recently";
    return `${user.email} joined ${createdAt}`;
  }, [user]);

  useEffect(() => {
    if (!open || !user) return;

    const load = async () => {
      setIsLoading(true);
      try {
        const promises: Promise<any>[] = [
          settingsApi.getSettings(),
          toolsApi.listTools(),
        ];
        if (sessionId) {
          promises.push(uploadsApi.listUploads(sessionId));
          promises.push(uploadsApi.getCapabilities(sessionId));
        }

        const [settingsData, toolData, uploadData, capsData] =
          await Promise.all(promises);

        const merged = { ...defaultSettings, ...settingsData };
        const memory = Array.isArray(merged.long_term_memory)
          ? merged.long_term_memory
          : [];
        setSettings(merged);
        setMemoryText(memory.join("\n"));
        setTools(toolData);
        if (uploadData) setUploads(uploadData);
        if (capsData) setUploadCaps(capsData);
      } catch (error: any) {
        toast.error(error?.response?.data?.detail || "Could not load settings");
      } finally {
        setIsLoading(false);
      }
    };

    load();
  }, [open, user, sessionId]);

  const saveSettings = async () => {
    if (!user) return;
    if (!settings.model?.trim()) {
      toast.error("Model is required.");
      return;
    }

    setIsSaving(true);
    try {
      const longTermMemory = memoryText
        .split("\n")
        .map((line) => line.trim())
        .filter(Boolean);
      const nextSettings: Record<string, unknown> = {
        ...settings,
        long_term_memory: longTermMemory,
      };
      const saved = await settingsApi.updateSettings(nextSettings);
      setSettings({ ...defaultSettings, ...saved });
      setTheme(
        String(nextSettings.theme || "dark") as "dark" | "light" | "system"
      );
      toast.success("Settings saved");
    } catch (error: any) {
      toast.error(error?.response?.data?.detail || "Could not save settings");
    } finally {
      setIsSaving(false);
    }
  };

  const handleDeleteUpload = async (uploadId: string) => {
    if (!sessionId) return;
    setIsDeletingUpload(uploadId);
    try {
      await uploadsApi.deleteUpload(sessionId, uploadId);
      setUploads((prev) => prev.filter((u) => u.id !== uploadId));
      toast.success("Attachment removed");
    } catch (error: any) {
      toast.error(error?.response?.data?.detail || "Could not remove attachment");
    } finally {
      setIsDeletingUpload(null);
    }
  };

  return (
    <Modal open={open} onClose={() => onOpenChange(false)} maxWidth="max-w-2xl" showClose>
      <div className="flex h-[85vh] max-h-[800px] flex-col w-full bg-card overflow-hidden rounded-xl">
        <div className="border-b border-border px-5 py-4 shrink-0 bg-background/50">
          <div className="flex items-center gap-2 text-lg font-semibold text-foreground">
            <Settings className="h-5 w-5 text-primary" /> Settings
          </div>
          <p className="text-sm text-muted-foreground mt-1">
            Account, model defaults, attachments, and agent capabilities.
          </p>
        </div>

        {/* Account section — always visible */}
        <div className="px-5 pt-4 shrink-0">
          <section className="rounded-lg border border-border bg-background/60 p-4">
            <div className="flex items-start gap-3">
              <div className="flex size-10 items-center justify-center rounded-lg bg-primary/12 text-primary">
                <UserCircle className="h-5 w-5" />
              </div>
              <div className="min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <h3 className="truncate text-sm font-semibold">{displayName}</h3>
                  {user?.oauth_provider && (
                    <Badge variant="outline">{user.oauth_provider}</Badge>
                  )}
                </div>
                <p className="mt-1 text-xs text-muted-foreground">{accountMeta}</p>
              </div>
              {user && (
                <Button
                  variant="outline"
                  size="sm"
                  className="shrink-0 text-muted-foreground hover:text-foreground"
                  onClick={async () => {
                    await authApi.logout();
                    onOpenChange(false);
                  }}
                >
                  <LogOut className="mr-2 h-4 w-4" />
                  Logout
                </Button>
              )}
            </div>
          </section>
        </div>

        {!user ? (
          <div className="px-5 pt-4 pb-2 shrink-0">
            <div className="rounded-lg border border-amber-500/20 bg-amber-500/10 p-4 text-sm text-amber-200">
              Sign in before editing memory or persistent preferences.
            </div>
          </div>
        ) : isLoading ? (
          <div className="flex flex-1 items-center justify-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="h-4 w-4 animate-spin" /> Loading settings
          </div>
        ) : (
          <Tabs defaultValue={initialTab || "defaults"} key={initialTab} className="flex flex-col flex-1 min-h-0">
            <div className="px-5 pt-3 shrink-0">
              <TabsList className="w-full grid grid-cols-5">
                <TabsTrigger value="defaults">Defaults</TabsTrigger>
                <TabsTrigger value="attachments">
                  Attachments
                  {uploads.length > 0 && (
                    <Badge className="ml-1.5 h-4 min-w-4 px-1 text-[10px]">
                      {uploads.length}
                    </Badge>
                  )}
                </TabsTrigger>
                <TabsTrigger value="skills">Skills</TabsTrigger>
                <TabsTrigger value="mcp">Connectors</TabsTrigger>
                <TabsTrigger value="tools">Tools</TabsTrigger>
              </TabsList>
            </div>

            {/* ── Skills Tab ──────────────────────────────────────────────── */}
            <TabsContent
              value="skills"
              className="flex-1 min-h-0 mt-0 data-[state=inactive]:hidden"
            >
              <ScrollArea className="h-full px-5 py-4">
                <div className="mx-auto max-w-2xl pb-6">
                  <SkillsManager />
                </div>
              </ScrollArea>
            </TabsContent>

            {/* ── MCP Servers Tab ──────────────────────────────────────────── */}
            <TabsContent
              value="mcp"
              className="flex-1 min-h-0 mt-0 data-[state=inactive]:hidden"
            >
              <ScrollArea className="h-full px-5 py-4">
                <div className="mx-auto max-w-2xl pb-6">
                  <McpServerManager />
                </div>
              </ScrollArea>
            </TabsContent>

            {/* ── Defaults Tab ──────────────────────────────────────────── */}
            <TabsContent
              value="defaults"
              className="flex-1 min-h-0 mt-0 data-[state=inactive]:hidden"
            >
              <ScrollArea className="h-full">
                <div className="space-y-5 p-5">
                  <section className="rounded-lg border border-border bg-background/60 p-4">
                    <div className="mb-3 flex items-center gap-2">
                      <Sparkles className="h-4 w-4 text-primary" />
                      <h3 className="text-sm font-semibold">Model & API</h3>
                    </div>
                    <div className="grid gap-3">
                      <div className="grid grid-cols-2 gap-3">
                        <label className="grid gap-1.5 text-xs font-medium text-muted-foreground">
                          LLM Provider
                          <select
                            value={settings.llm_provider || "openrouter"}
                            onChange={(e) =>
                              setSettings((p) => ({ ...p, llm_provider: e.target.value }))
                            }
                            className="h-9 rounded-lg border border-input bg-background px-2 text-sm text-foreground outline-none focus:ring-2 focus:ring-ring/30"
                          >
                            <option value="openrouter">OpenRouter</option>
                            <option value="openai">OpenAI</option>
                            <option value="anthropic">Anthropic</option>
                            <option value="groq">Groq</option>
                            <option value="gemini">Gemini</option>
                          </select>
                        </label>
                        <label className="grid gap-1.5 text-xs font-medium text-muted-foreground">
                          API Key
                          <Input
                            type="password"
                            value={settings.llm_api_key || settings.api_key || ""}
                            onChange={(e) =>
                              setSettings((p) => ({ ...p, llm_api_key: e.target.value, api_key: e.target.value }))
                            }
                            className="h-9"
                            placeholder="sk-..."
                          />
                        </label>
                      </div>
                      <label className="grid gap-1.5 text-xs font-medium text-muted-foreground">
                        Model Name
                        <Input
                          value={settings.model || ""}
                          onChange={(e) =>
                            setSettings((p) => ({ ...p, model: e.target.value }))
                          }
                          className="h-9"
                          placeholder="e.g. gpt-4o, claude-3-opus-20240229"
                        />
                      </label>
                      <label className="grid gap-1.5 text-xs font-medium text-muted-foreground">
                        Workspace Directory
                        <Input
                          value={settings.workspace_dir || ""}
                          onChange={(e) =>
                            setSettings((p) => ({ ...p, workspace_dir: e.target.value }))
                          }
                          className="h-9"
                          placeholder="e.g. C:\Users\user\my-project"
                        />
                      </label>
                      <div className="grid grid-cols-2 gap-3">
                        <label className="grid gap-1.5 text-xs font-medium text-muted-foreground">
                          Theme
                          <select
                            value={settings.theme || "dark"}
                            onChange={(e) =>
                              setSettings((p) => ({ ...p, theme: e.target.value }))
                            }
                            className="h-9 rounded-lg border border-input bg-background px-2 text-sm text-foreground outline-none focus:ring-2 focus:ring-ring/30"
                          >
                            <option value="dark">Dark</option>
                            <option value="light">Light</option>
                            <option value="system">System</option>
                          </select>
                        </label>
                        <label className="grid gap-1.5 text-xs font-medium text-muted-foreground">
                          Language
                          <Input
                            value={settings.language || "en"}
                            onChange={(e) =>
                              setSettings((p) => ({ ...p, language: e.target.value }))
                            }
                            className="h-9"
                          />
                        </label>
                      </div>
                    </div>
                  </section>

                  <section className="rounded-lg border border-border bg-background/60 p-4">
                    <div className="mb-3 flex items-center gap-2">
                      <Shield className="h-4 w-4 text-primary" />
                      <h3 className="text-sm font-semibold">Guardrails</h3>
                    </div>
                    <label className="flex items-center justify-between cursor-pointer">
                      <div>
                        <div className="text-sm font-medium">Enable input/output guardrails</div>
                        <div className="text-xs text-muted-foreground mt-0.5">
                          Screen messages for safety and policy compliance
                        </div>
                      </div>
                      <button
                        role="switch"
                        aria-checked={settings.guardrails_enabled !== false}
                        onClick={() =>
                          setSettings((p) => ({
                            ...p,
                            guardrails_enabled: !p.guardrails_enabled,
                          }))
                        }
                        className={`relative inline-flex h-5 w-9 shrink-0 rounded-full border-2 border-transparent transition-colors duration-200 focus-visible:ring-2 focus-visible:ring-primary/40 ${
                          settings.guardrails_enabled !== false
                            ? "bg-primary"
                            : "bg-muted-foreground/30"
                        }`}
                      >
                        <span
                          className={`inline-block h-4 w-4 rounded-full bg-white shadow transition-transform duration-200 ${
                            settings.guardrails_enabled !== false
                              ? "translate-x-4"
                              : "translate-x-0"
                          }`}
                        />
                      </button>
                    </label>

                    <div className="mt-4 border-t border-border pt-4">
                      <label className="flex items-center justify-between cursor-pointer">
                        <div>
                          <div className="text-sm font-medium">Safe Mode (File Protection)</div>
                          <div className="text-xs text-muted-foreground mt-0.5">
                            Require manual review before applying file patches
                          </div>
                        </div>
                        <button
                          role="switch"
                          aria-checked={settings.safe_mode === true}
                          onClick={() =>
                            setSettings((p) => ({
                              ...p,
                              safe_mode: !p.safe_mode,
                            }))
                          }
                          className={`relative inline-flex h-5 w-9 shrink-0 rounded-full border-2 border-transparent transition-colors duration-200 focus-visible:ring-2 focus-visible:ring-primary/40 ${
                            settings.safe_mode === true
                              ? "bg-primary"
                              : "bg-muted-foreground/30"
                          }`}
                        >
                          <span
                            className={`inline-block h-4 w-4 rounded-full bg-white shadow transition-transform duration-200 ${
                              settings.safe_mode === true
                                ? "translate-x-4"
                                : "translate-x-0"
                            }`}
                          />
                        </button>
                      </label>
                    </div>

                    <div className="mt-4 border-t border-border pt-4">
                      <label className="flex items-center justify-between cursor-pointer">
                        <div>
                          <div className="text-sm font-medium text-amber-500">Fast Mode (Latency Bypass)</div>
                          <div className="text-xs text-muted-foreground mt-0.5">
                            Bypass all guardrails & safety approvals for extreme speed.
                          </div>
                        </div>
                        <button
                          role="switch"
                          aria-checked={settings.fast_mode === true}
                          onClick={() =>
                            setSettings((p) => ({
                              ...p,
                              fast_mode: !p.fast_mode,
                            }))
                          }
                          className={`relative inline-flex h-5 w-9 shrink-0 rounded-full border-2 border-transparent transition-colors duration-200 focus-visible:ring-2 focus-visible:ring-primary/40 ${
                            settings.fast_mode === true
                              ? "bg-amber-500"
                              : "bg-muted-foreground/30"
                          }`}
                        >
                          <span
                            className={`inline-block h-4 w-4 rounded-full bg-white shadow transition-transform duration-200 ${
                              settings.fast_mode === true
                                ? "translate-x-4"
                                : "translate-x-0"
                            }`}
                          />
                        </button>
                      </label>
                      {settings.fast_mode === true && (
                        <div className="mt-3 text-[10px] leading-relaxed text-amber-500 bg-amber-500/10 border border-amber-500/20 rounded-md p-2.5">
                          ⚠️ WARNING: Fast Mode disables safety filters and human-in-the-loop approvals. The agent will execute shell commands and file changes instantly without verification. Use with caution.
                        </div>
                      )}
                    </div>
                  </section>

                  <section className="rounded-lg border border-border bg-background/60 p-4">
                    <div className="mb-3 flex items-center gap-2">
                      <Brain className="h-4 w-4 text-primary" />
                      <h3 className="text-sm font-semibold">Long-Term Memory</h3>
                    </div>
                    <textarea
                      value={memoryText}
                      onChange={(e) => setMemoryText(e.target.value)}
                      placeholder="One memory per line — e.g. Prefers concise technical answers."
                      className="min-h-32 w-full resize-y rounded-lg border border-input bg-background p-3 text-sm leading-6 text-foreground outline-none placeholder:text-muted-foreground focus:ring-2 focus:ring-ring/30"
                    />
                    <p className="mt-2 text-xs text-muted-foreground">
                      Injected as personalization context on every turn.
                    </p>
                  </section>
                </div>
              </ScrollArea>
            </TabsContent>

            {/* ── Attachments Tab ───────────────────────────────────────── */}
            <TabsContent
              value="attachments"
              className="flex-1 min-h-0 mt-0 data-[state=inactive]:hidden"
            >
              <ScrollArea className="h-full">
                <div className="p-5 space-y-3">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <Paperclip className="h-4 w-4 text-primary" />
                      <h3 className="text-sm font-semibold">Session Attachments</h3>
                    </div>
                    {uploadCaps && (
                      <span
                        className="text-[10px] text-muted-foreground"
                        title={`Supported: ${uploadCaps.supported_extensions?.join(", ")}`}
                      >
                        Max {Math.round(uploadCaps.max_upload_bytes / 1024 / 1024)} MB
                      </span>
                    )}
                  </div>

                  {!sessionId ? (
                    <p className="text-xs text-muted-foreground">
                      Open a chat session to manage attachments.
                    </p>
                  ) : uploads.length === 0 ? (
                    <div className="flex flex-col items-center gap-2 py-10 text-center text-sm text-muted-foreground">
                      <Paperclip className="h-8 w-8 opacity-30" />
                      No files attached to this session yet.
                    </div>
                  ) : (
                    uploads.map((upload) => (
                      <div
                        key={upload.id}
                        className="flex items-center justify-between gap-3 rounded-lg border border-border bg-background/60 px-3 py-2.5"
                      >
                        <div className="min-w-0 flex-1">
                          <div className="truncate text-xs font-medium text-foreground">
                            {upload.filename}
                          </div>
                          <div className="mt-0.5 flex items-center gap-2 text-[10px] text-muted-foreground">
                            <span>{formatBytes(upload.size_bytes)}</span>
                            {upload.chunk_count != null && (
                              <span>{upload.chunk_count} chunks</span>
                            )}
                            <Badge
                              variant="outline"
                              className={`h-4 px-1 text-[10px] ${
                                upload.status === "ready"
                                  ? "text-green-500 border-green-500/30"
                                  : upload.status === "failed"
                                  ? "text-red-500 border-red-500/30"
                                  : "text-amber-500 border-amber-500/30"
                              }`}
                            >
                              {upload.status}
                            </Badge>
                          </div>
                        </div>
                        <Button
                          variant="ghost"
                          size="icon-sm"
                          aria-label={`Remove ${upload.filename}`}
                          onClick={() => handleDeleteUpload(upload.id)}
                          disabled={isDeletingUpload === upload.id}
                          className="shrink-0 text-muted-foreground hover:text-red-500 focus-visible:ring-2 focus-visible:ring-primary/40"
                        >
                          {isDeletingUpload === upload.id ? (
                            <Loader2 className="h-3.5 w-3.5 animate-spin" />
                          ) : (
                            <Trash2 className="h-3.5 w-3.5" />
                          )}
                        </Button>
                      </div>
                    ))
                  )}
                </div>
              </ScrollArea>
            </TabsContent>



            {/* ── Tools Tab ────────────────────────────────────────────── */}
            <TabsContent
              value="tools"
              className="flex-1 min-h-0 mt-0 data-[state=inactive]:hidden"
            >
              <ScrollArea className="h-full">
                <div className="p-5 space-y-3">
                  <div className="flex items-center gap-2 mb-1">
                    <Wrench className="h-4 w-4 text-primary" />
                    <h3 className="text-sm font-semibold">Agent Powers</h3>
                    <Badge variant="outline">{tools.length}</Badge>
                  </div>
                  {tools.map((tool) => (
                    <div
                      key={tool.name}
                      className="rounded-md border border-border/70 bg-card/60 p-3"
                    >
                      <div className="flex items-center gap-2">
                        <span className="text-xs font-semibold text-foreground">
                          {tool.name}
                        </span>
                        {tool.environment === "tui" ? (
                          <Badge
                            variant="outline"
                            className="h-4 px-1.5 text-[10px] text-amber-500 border-amber-500/30 bg-amber-500/8"
                            title="Only available in TUI mode"
                          >
                            <TerminalIcon className="h-2.5 w-2.5 mr-0.5" />
                            TUI only
                          </Badge>
                        ) : (
                          <Badge
                            variant="outline"
                            className="h-4 px-1.5 text-[10px] text-green-500 border-green-500/30 bg-green-500/8"
                          >
                            <Globe className="h-2.5 w-2.5 mr-0.5" />
                            web
                          </Badge>
                        )}
                      </div>
                      <div className="mt-1 line-clamp-2 text-xs leading-5 text-muted-foreground">
                        {tool.description}
                      </div>
                    </div>
                  ))}
                </div>
              </ScrollArea>
            </TabsContent>
          </Tabs>
        )}

        <div className="border-t border-border p-4 shrink-0">
          <Button
            className="w-full"
            onClick={saveSettings}
            disabled={!user || isSaving}
          >
            {isSaving ? (
              <Loader2 className="h-4 w-4 animate-spin" />
            ) : (
              <Check className="h-4 w-4" />
            )}
            Save Settings
          </Button>
        </div>
      </div>
    </Modal>
  );
}
