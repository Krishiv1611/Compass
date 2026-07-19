import { useEffect, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { toast } from "react-toastify";
import { settingsApi } from "@/api";
import { Loader2, Plus, Trash2, CheckCircle, Server, Terminal, X, Play } from "lucide-react";

interface McpServerConfig {
  command: string;
  args: string[];
  env: Record<string, string>;
}

interface McpConfig {
  mcpServers: Record<string, McpServerConfig>;
}

export default function McpServerManager() {
  const [config, setConfig] = useState<McpConfig>({ mcpServers: {} });
  const [loading, setLoading] = useState(true);
  const [editingServer, setEditingServer] = useState<string | null>(null);
  
  // Form State
  const [formName, setFormName] = useState("");
  const [formCommand, setFormCommand] = useState("");
  const [formArgs, setFormArgs] = useState<string[]>([]);
  const [formEnv, setFormEnv] = useState<{key: string, value: string}[]>([]);
  
  const [isTesting, setIsTesting] = useState(false);
  const [testResult, setTestResult] = useState<string | null>(null);

  useEffect(() => {
    loadServers();
  }, []);

  const loadServers = async () => {
    try {
      const data = await settingsApi.getMcpServers();
      setConfig(data);
    } catch (err) {
      toast.error("Failed to load MCP configuration");
    } finally {
      setLoading(false);
    }
  };

  const handleEdit = (name: string, server: McpServerConfig) => {
    setEditingServer(name);
    setFormName(name);
    setFormCommand(server.command || "");
    setFormArgs(server.args || []);
    setFormEnv(Object.entries(server.env || {}).map(([key, value]) => ({ key, value })));
    setTestResult(null);
  };

  const handleAddNew = () => {
    setEditingServer("");
    setFormName("");
    setFormCommand("");
    setFormArgs([]);
    setFormEnv([]);
    setTestResult(null);
  };

  const handleSave = async () => {
    if (!formName.trim() || !formCommand.trim()) {
      toast.error("Name and Command are required");
      return;
    }
    
    const envRecord: Record<string, string> = {};
    formEnv.forEach(({ key, value }) => {
      if (key.trim()) envRecord[key.trim()] = value;
    });

    const newServer: McpServerConfig = {
      command: formCommand.trim(),
      args: formArgs.filter(a => a.trim() !== ""),
      env: envRecord
    };

    const newConfig = { ...config };
    if (!newConfig.mcpServers) newConfig.mcpServers = {};
    
    // If renaming, delete old key
    if (editingServer && editingServer !== formName) {
      delete newConfig.mcpServers[editingServer];
    }
    
    newConfig.mcpServers[formName] = newServer;

    try {
      await settingsApi.updateMcpServers(newConfig);
      setConfig(newConfig);
      setEditingServer(null);
      toast.success("MCP Server saved");
    } catch (err) {
      toast.error("Failed to save MCP configuration");
    }
  };

  const handleDelete = async (name: string) => {
    const newConfig = { ...config };
    delete newConfig.mcpServers[name];
    try {
      await settingsApi.updateMcpServers(newConfig);
      setConfig(newConfig);
      toast.info(`Deleted ${name}`);
    } catch (err) {
      toast.error("Failed to delete MCP server");
    }
  };

  const handleTest = async () => {
    if (!formCommand.trim()) return;
    setIsTesting(true);
    setTestResult(null);
    try {
      const envRecord: Record<string, string> = {};
      formEnv.forEach(({ key, value }) => {
        if (key.trim()) envRecord[key.trim()] = value;
      });
      const res = await settingsApi.testMcpServer(formName || "test", {
        command: formCommand.trim(),
        args: formArgs.filter(a => a.trim() !== ""),
        env: envRecord
      });
      setTestResult(res.message || "Connection successful");
      toast.success("Test passed");
    } catch (err: any) {
      const msg = err?.response?.data?.detail || "Connection failed";
      setTestResult(`Error: ${msg}`);
      toast.error("Test failed");
    } finally {
      setIsTesting(false);
    }
  };

  if (loading) {
    return <div className="p-8 text-center"><Loader2 className="animate-spin mx-auto text-muted-foreground" /></div>;
  }

  const serversList = Object.entries(config.mcpServers || {});

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h3 className="text-lg font-semibold">Model Context Protocol</h3>
          <p className="text-sm text-muted-foreground">Configure local MCP servers for the agent to access external tools.</p>
        </div>
        {editingServer === null && (
          <Button onClick={handleAddNew} size="sm">
            <Plus className="h-4 w-4 mr-2" /> Add Server
          </Button>
        )}
      </div>

      {editingServer === null ? (
        serversList.length === 0 ? (
          <div className="border border-dashed border-border rounded-lg p-8 text-center bg-muted/20">
            <Server className="h-8 w-8 text-muted-foreground mx-auto mb-3 opacity-50" />
            <p className="text-sm font-medium">No MCP servers configured</p>
            <p className="text-xs text-muted-foreground mt-1 mb-4">Add a server to give your agent more tools</p>
            <Button variant="outline" size="sm" onClick={handleAddNew}>
              <Plus className="h-4 w-4 mr-2" /> Add First Server
            </Button>
          </div>
        ) : (
          <div className="grid gap-3">
            {serversList.map(([name, server]) => (
              <div key={name} className="flex items-center justify-between p-3 border border-border rounded-lg bg-card/50 hover:bg-card transition-colors">
                <div className="flex items-center gap-3">
                  <div className="p-2 bg-primary/10 rounded-md">
                    <Terminal className="h-4 w-4 text-primary" />
                  </div>
                  <div>
                    <p className="font-medium text-sm">{name}</p>
                    <p className="text-xs text-muted-foreground font-mono">{server.command} {server.args.join(" ")}</p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <Button variant="ghost" size="sm" onClick={() => handleEdit(name, server)}>Edit</Button>
                  <Button variant="ghost" size="icon-sm" className="text-red-400 hover:text-red-500 hover:bg-red-500/10" onClick={() => handleDelete(name)}>
                    <Trash2 className="h-4 w-4" />
                  </Button>
                </div>
              </div>
            ))}
          </div>
        )
      ) : (
        <div className="border border-border rounded-xl p-5 bg-card/50 space-y-5 animate-in fade-in slide-in-from-bottom-2">
          <div className="flex items-center justify-between">
            <h4 className="font-medium text-sm">{editingServer ? "Edit Server" : "New Server"}</h4>
            <Button variant="ghost" size="icon-sm" onClick={() => setEditingServer(null)}>
              <X className="h-4 w-4" />
            </Button>
          </div>
          
          <div className="grid gap-4">
            <div className="grid gap-1.5">
              <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Server Name</label>
              <Input 
                value={formName} 
                onChange={e => setFormName(e.target.value)} 
                placeholder="e.g. github, filesystem, brave-search" 
                className="font-mono text-sm"
              />
            </div>
            
            <div className="grid gap-1.5">
              <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Command</label>
              <Input 
                value={formCommand} 
                onChange={e => setFormCommand(e.target.value)} 
                placeholder="e.g. npx, node, python" 
                className="font-mono text-sm"
              />
            </div>

            <div className="grid gap-1.5">
              <div className="flex justify-between items-center">
                <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Arguments</label>
                <Button variant="ghost" size="sm" className="h-6 text-xs px-2" onClick={() => setFormArgs([...formArgs, ""])}>+ Add Arg</Button>
              </div>
              {formArgs.length === 0 && <p className="text-xs text-muted-foreground italic">No arguments added</p>}
              {formArgs.map((arg, idx) => (
                <div key={idx} className="flex items-center gap-2">
                  <Input 
                    value={arg} 
                    onChange={e => {
                      const newArgs = [...formArgs];
                      newArgs[idx] = e.target.value;
                      setFormArgs(newArgs);
                    }} 
                    className="font-mono text-sm h-8" 
                    placeholder="-y @modelcontextprotocol/server-github"
                  />
                  <Button variant="ghost" size="icon-sm" onClick={() => setFormArgs(formArgs.filter((_, i) => i !== idx))}>
                    <Trash2 className="h-3.5 w-3.5 text-muted-foreground" />
                  </Button>
                </div>
              ))}
            </div>

            <div className="grid gap-1.5">
              <div className="flex justify-between items-center">
                <label className="text-xs font-semibold text-muted-foreground uppercase tracking-wider">Environment Variables</label>
                <Button variant="ghost" size="sm" className="h-6 text-xs px-2" onClick={() => setFormEnv([...formEnv, {key: "", value: ""}])}>+ Add Env</Button>
              </div>
              {formEnv.length === 0 && <p className="text-xs text-muted-foreground italic">No environment variables added</p>}
              {formEnv.map((env, idx) => (
                <div key={idx} className="flex items-center gap-2">
                  <Input 
                    value={env.key} 
                    onChange={e => {
                      const newEnv = [...formEnv];
                      newEnv[idx].key = e.target.value;
                      setFormEnv(newEnv);
                    }} 
                    className="font-mono text-sm h-8 w-1/3" 
                    placeholder="KEY"
                  />
                  <Input 
                    value={env.value} 
                    onChange={e => {
                      const newEnv = [...formEnv];
                      newEnv[idx].value = e.target.value;
                      setFormEnv(newEnv);
                    }} 
                    className="font-mono text-sm h-8 flex-1" 
                    placeholder="VALUE"
                    type="password"
                  />
                  <Button variant="ghost" size="icon-sm" onClick={() => setFormEnv(formEnv.filter((_, i) => i !== idx))}>
                    <Trash2 className="h-3.5 w-3.5 text-muted-foreground" />
                  </Button>
                </div>
              ))}
            </div>
          </div>

          {testResult && (
            <div className={`p-3 rounded-md text-xs font-mono border ${testResult.startsWith('Error') ? 'bg-red-500/10 border-red-500/20 text-red-400' : 'bg-emerald-500/10 border-emerald-500/20 text-emerald-400'}`}>
              {testResult}
            </div>
          )}

          <div className="flex justify-between pt-2 border-t border-border">
            <Button variant="outline" size="sm" onClick={handleTest} disabled={isTesting || !formCommand.trim()}>
              {isTesting ? <Loader2 className="h-4 w-4 mr-2 animate-spin" /> : <Play className="h-4 w-4 mr-2" />}
              Test Connection
            </Button>
            <div className="flex gap-2">
              <Button variant="ghost" size="sm" onClick={() => setEditingServer(null)}>Cancel</Button>
              <Button size="sm" onClick={handleSave}>
                <CheckCircle className="h-4 w-4 mr-2" /> Save Server
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
