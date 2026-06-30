import { useEffect, useMemo, useState } from "react";
import { Brain, Check, Loader2, Settings, Sparkles, UserCircle, Wrench } from "lucide-react";
import { toast } from "react-toastify";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet";
import { Input } from "@/components/ui/input";
import { ScrollArea } from "@/components/ui/scroll-area";
import { settingsApi, toolsApi } from "@/api";
import { useTheme } from "@/components/ThemeProvider";

type SettingsDrawerProps = {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  user: any | null;
};

type ToolInfo = {
  name: string;
  description: string;
};

const defaultSettings = {
  theme: "dark",
  model: "google/gemma-4-31b-it:free",
  language: "en",
  long_term_memory: [] as string[],
};

export default function SettingsDrawer({ open, onOpenChange, user }: SettingsDrawerProps) {
  const [settings, setSettings] = useState<Record<string, any>>(defaultSettings);
  const [tools, setTools] = useState<ToolInfo[]>([]);
  const [memoryText, setMemoryText] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const { setTheme } = useTheme();

  const displayName = user?.display_name || user?.email?.split("@")[0] || "Unsigned user";
  const accountMeta = useMemo(() => {
    if (!user) return "Sign in to persist sessions, files, preferences, and memory.";
    const createdAt = user.created_at ? new Date(user.created_at).toLocaleDateString() : "recently";
    return `${user.email} joined ${createdAt}`;
  }, [user]);

  useEffect(() => {
    if (!open || !user) return;

    const load = async () => {
      setIsLoading(true);
      try {
        const [settingsData, toolData] = await Promise.all([
          settingsApi.getSettings(),
          toolsApi.listTools(),
        ]);
        const merged = { ...defaultSettings, ...settingsData };
        const memory = Array.isArray(merged.long_term_memory) ? merged.long_term_memory : [];
        setSettings(merged);
        setMemoryText(memory.join("\n"));
        setTools(toolData);
      } catch (error: any) {
        toast.error(error?.response?.data?.detail || "Could not load settings");
      } finally {
        setIsLoading(false);
      }
    };

    load();
  }, [open, user]);

  const saveSettings = async () => {
    if (!user) return;
    setIsSaving(true);
    try {
      const longTermMemory = memoryText
        .split("\n")
        .map((line) => line.trim())
        .filter(Boolean);
      const nextSettings: Record<string, unknown> = { ...settings, long_term_memory: longTermMemory };
      const saved = await settingsApi.updateSettings(nextSettings);
      setSettings({ ...defaultSettings, ...saved });
      setTheme((String(nextSettings.theme || "dark") as "dark" | "light" | "system"));
      toast.success("Settings saved");
    } catch (error: any) {
      toast.error(error?.response?.data?.detail || "Could not save settings");
    } finally {
      setIsSaving(false);
    }
  };

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent side="right" className="w-full border-l border-border bg-card p-0 sm:max-w-[520px]" showCloseButton>
        <SheetHeader className="border-b border-border px-5 py-4">
          <SheetTitle className="flex items-center gap-2 text-sm font-semibold">
            <Settings className="h-4 w-4 text-primary" /> Settings
          </SheetTitle>
          <SheetDescription className="text-xs">
            Account, personalization memory, model defaults, and agent capabilities.
          </SheetDescription>
        </SheetHeader>

        <ScrollArea className="flex-1">
          <div className="space-y-5 p-5">
            <section className="rounded-lg border border-border bg-background/60 p-4">
              <div className="flex items-start gap-3">
                <div className="flex size-10 items-center justify-center rounded-lg bg-primary/12 text-primary">
                  <UserCircle className="h-5 w-5" />
                </div>
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2">
                    <h3 className="truncate text-sm font-semibold">{displayName}</h3>
                    {user?.oauth_provider && <Badge variant="outline">{user.oauth_provider}</Badge>}
                  </div>
                  <p className="mt-1 text-xs text-muted-foreground">{accountMeta}</p>
                </div>
              </div>
            </section>

            {!user ? (
              <div className="rounded-lg border border-amber-500/20 bg-amber-500/10 p-4 text-sm text-amber-200">
                Sign in before editing memory or persistent preferences.
              </div>
            ) : isLoading ? (
              <div className="flex h-40 items-center justify-center gap-2 text-sm text-muted-foreground">
                <Loader2 className="h-4 w-4 animate-spin" /> Loading settings
              </div>
            ) : (
              <>
                <section className="rounded-lg border border-border bg-background/60 p-4">
                  <div className="mb-3 flex items-center gap-2">
                    <Sparkles className="h-4 w-4 text-primary" />
                    <h3 className="text-sm font-semibold">Defaults</h3>
                  </div>
                  <div className="grid gap-3">
                    <label className="grid gap-1.5 text-xs font-medium text-muted-foreground">
                      Model
                      <Input
                        value={settings.model || ""}
                        onChange={(event) => setSettings((prev) => ({ ...prev, model: event.target.value }))}
                        className="h-9 text-foreground"
                      />
                    </label>
                    <div className="grid grid-cols-2 gap-3">
                      <label className="grid gap-1.5 text-xs font-medium text-muted-foreground">
                        Theme
                        <select
                          value={settings.theme || "dark"}
                          onChange={(event) => setSettings((prev) => ({ ...prev, theme: event.target.value }))}
                          className="h-9 rounded-lg border border-input bg-background px-2 text-sm text-foreground outline-none focus:border-ring focus:ring-2 focus:ring-ring/30"
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
                          onChange={(event) => setSettings((prev) => ({ ...prev, language: event.target.value }))}
                          className="h-9 text-foreground"
                        />
                      </label>
                    </div>
                  </div>
                </section>

                <section className="rounded-lg border border-border bg-background/60 p-4">
                  <div className="mb-3 flex items-center gap-2">
                    <Brain className="h-4 w-4 text-primary" />
                    <h3 className="text-sm font-semibold">Long-Term Memory</h3>
                  </div>
                  <textarea
                    value={memoryText}
                    onChange={(event) => setMemoryText(event.target.value)}
                    placeholder="One memory per line, for example: Prefers concise technical answers."
                    className="min-h-36 w-full resize-y rounded-lg border border-input bg-background p-3 text-sm leading-6 text-foreground outline-none placeholder:text-muted-foreground focus:border-ring focus:ring-2 focus:ring-ring/30"
                  />
                  <p className="mt-2 text-xs text-muted-foreground">
                    These notes are exposed as editable personalization memory in user preferences.
                  </p>
                </section>

                <section className="rounded-lg border border-border bg-background/60 p-4">
                  <div className="mb-3 flex items-center gap-2">
                    <Wrench className="h-4 w-4 text-primary" />
                    <h3 className="text-sm font-semibold">Agent Powers</h3>
                    <Badge variant="outline">{tools.length}</Badge>
                  </div>
                  <div className="grid gap-2">
                    {tools.slice(0, 12).map((tool) => (
                      <div key={tool.name} className="rounded-md border border-border/70 bg-card/60 p-3">
                        <div className="text-xs font-semibold text-foreground">{tool.name}</div>
                        <div className="mt-1 line-clamp-2 text-xs leading-5 text-muted-foreground">{tool.description}</div>
                      </div>
                    ))}
                  </div>
                </section>
              </>
            )}
          </div>
        </ScrollArea>

        <div className="border-t border-border p-4">
          <Button className="w-full" onClick={saveSettings} disabled={!user || isSaving}>
            {isSaving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Check className="h-4 w-4" />}
            Save Settings
          </Button>
        </div>
      </SheetContent>
    </Sheet>
  );
}

