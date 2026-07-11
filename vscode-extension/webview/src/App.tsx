import { useState, useEffect } from 'react';
import { SocketClient } from './api/socket';

export default function App() {
  const [messages, setMessages] = useState<any[]>([]);
  const [input, setInput] = useState('');
  const [mode, setMode] = useState<"normal" | "plan">("normal");
  const [socket, setSocket] = useState<SocketClient | null>(null);
  const [context, setContext] = useState<any>(null);

  useEffect(() => {
    // In a real scenario, you'd fetch a valid token or prompt the user to login.
    // For now, we assume a hardcoded or extension-provided token/session.
    const sessionId = "vscode-session-1";
    const dummyToken = "dummy-token"; 

    const ws = new SocketClient(sessionId, dummyToken, {
      onMessage: (msg) => {
        if (msg.type === 'token') {
          setMessages((prev) => {
            const last = prev[prev.length - 1];
            if (last && last.role === 'assistant') {
              return [
                ...prev.slice(0, -1),
                { ...last, content: last.content + msg.content }
              ];
            } else {
              return [...prev, { role: 'assistant', content: msg.content }];
            }
          });
        } else if (msg.type === 'tool_call') {
          // Handle tool visualizations
          setMessages((prev) => [...prev, { role: 'tool', content: `Using tool: ${msg.name}` }]);
        }
      },
      onConnect: () => console.log('Connected'),
      onDisconnect: () => console.log('Disconnected'),
    });

    ws.connect();
    setSocket(ws);

    // Listen to messages from the VS Code extension
    window.addEventListener('message', event => {
      const message = event.data;
      if (message.type === 'contextUpdate') {
        setContext(message.value);
      }
    });

    return () => {
      ws.disconnect();
    };
  }, []);

  const handleSend = () => {
    if (!input.trim() || !socket) return;
    
    setMessages((prev) => [...prev, { role: 'user', content: input }]);
    socket.sendMessage(input, mode, context);
    setInput('');
  };

  const handleDrop = async (e: React.DragEvent) => {
    e.preventDefault();
    const files = Array.from(e.dataTransfer.files);
    if (!files.length) return;

    for (const file of files) {
      const formData = new FormData();
      formData.append('file', file);

      try {
        // We use the dummy sessionId and token for now
        const sessionId = "vscode-session-1";
        const dummyToken = "dummy-token"; 
        
        const res = await fetch(`http://localhost:8000/sessions/${sessionId}/uploads`, {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${dummyToken}`
          },
          body: formData
        });

        if (res.ok) {
          setMessages(prev => [...prev, { role: 'user', content: `Uploaded file: ${file.name}` }]);
        } else {
          setMessages(prev => [...prev, { role: 'assistant', content: `Failed to upload: ${file.name}` }]);
        }
      } catch (err) {
        console.error("Upload error", err);
      }
    }
  };

  return (
    <div 
      className="flex flex-col h-screen bg-background text-foreground"
      onDrop={handleDrop}
      onDragOver={(e) => e.preventDefault()}
    >
      <div className="flex-1 overflow-y-auto p-4 space-y-4">
        {messages.map((m, i) => (
          <div key={i} className={`p-3 rounded-lg ${m.role === 'user' ? 'bg-primary text-primaryForeground ml-auto' : 'bg-secondary mr-auto'} max-w-[85%]`}>
            {m.role === 'tool' ? (
              <span className="italic text-sm opacity-70">{m.content}</span>
            ) : (
              <pre className="whitespace-pre-wrap font-sans">{m.content}</pre>
            )}
          </div>
        ))}
      </div>

      <div className="p-4 border-t border-border flex flex-col gap-2 relative">
        {context?.file && (
          <div className="text-xs text-accent opacity-80 mb-1">
            Context: {context.file.split(/[/\\]/).pop()}
          </div>
        )}
        <div className="flex items-center gap-2 mb-2">
          <label className="text-sm font-semibold">Mode:</label>
          <select 
            className="bg-secondary border border-border rounded p-1 text-sm outline-none"
            value={mode} 
            onChange={(e) => setMode(e.target.value as "normal" | "plan")}
          >
            <option value="normal">Normal</option>
            <option value="plan">Plan</option>
          </select>
        </div>
        <div className="relative w-full">
          <textarea 
            value={input}
            onChange={(e) => setInput(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                handleSend();
              }
            }}
            placeholder="Ask Compass... (Drop files to upload)"
            className="w-full bg-secondary text-foreground border border-border rounded-md p-2 min-h-[80px] resize-none outline-none focus:border-accent pb-10"
          />
          <button 
            onClick={handleSend}
            className="absolute bottom-2 right-2 bg-primary text-primaryForeground px-4 py-1 rounded hover:opacity-90 text-sm"
          >
            Send
          </button>
        </div>
      </div>
    </div>
  );
}
