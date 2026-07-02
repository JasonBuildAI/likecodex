'use client';

import { useState, useEffect, useCallback } from 'react';
import { fetchMcpTools, type McpToolInfo } from '@/lib/api';

interface ToolDetail {
  name: string;
  description: string;
  server: string;
  enabled: boolean;
  inputSchema?: Record<string, unknown>;
}

export function MCPToolExplorer() {
  const [tools, setTools] = useState<ToolDetail[]>([]);
  const [byServer, setByServer] = useState<Record<string, ToolDetail[]>>({});
  const [loading, setLoading] = useState(false);
  const [selectedTool, setSelectedTool] = useState<ToolDetail | null>(null);
  const [searchQuery, setSearchQuery] = useState('');

  const loadTools = useCallback(async () => {
    setLoading(true);
    try {
      const data = await fetchMcpTools();
      const perServer = data.per_server || {};
      setByServer(perServer as Record<string, ToolDetail[]>);
      const all: ToolDetail[] = [];
      Object.entries(perServer).forEach(([server, serverTools]) => {
        (serverTools as ToolDetail[]).forEach((t) => all.push({ ...t, server }));
      });
      setTools(all);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadTools(); }, [loadTools]);

  const filtered = searchQuery
    ? tools.filter((t) =>
        t.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
        t.description?.toLowerCase().includes(searchQuery.toLowerCase()) ||
        t.server.toLowerCase().includes(searchQuery.toLowerCase())
      )
    : tools;

  const grouped = filtered.reduce<Record<string, ToolDetail[]>>((acc, t) => {
    if (!acc[t.server]) acc[t.server] = [];
    acc[t.server].push(t);
    return acc;
  }, {});

  return (
    <div className="flex flex-col h-full">
      <div className="p-3 border-b border-border space-y-2">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold">MCP Tools</h2>
          <button onClick={loadTools} disabled={loading}
            className="px-2 py-0.5 text-[10px] rounded bg-accent/10 hover:bg-accent/20 transition disabled:opacity-50"
          >{loading ? '...' : 'Refresh'}</button>
        </div>
        <input value={searchQuery} onChange={(e) => setSearchQuery(e.target.value)}
          placeholder="Search tools..." className="w-full px-2 py-1 text-xs rounded bg-surface border border-border focus:border-primary outline-none"
        />
        <div className="text-[10px] text-muted">{tools.length} tools from {Object.keys(byServer).length} servers</div>
      </div>

      <div className="flex-1 overflow-y-auto">
        {loading && tools.length === 0 ? (
          <div className="flex items-center justify-center py-8">
            <div className="h-4 w-4 animate-spin rounded-full border-2 border-primary border-t-transparent" />
          </div>
        ) : filtered.length === 0 ? (
          <div className="text-xs text-muted text-center py-6">No tools found.</div>
        ) : (
          Object.entries(grouped).map(([server, serverTools]) => (
            <div key={server} className="border-b border-border/50 last:border-b-0">
              <div className="px-3 py-1.5 bg-accent/5 text-[10px] font-medium text-muted flex items-center gap-2">
                <span className="inline-block h-1.5 w-1.5 rounded-full bg-green-500" />
                {server}
                <span className="text-muted/60">({serverTools.length})</span>
              </div>
              {serverTools.map((tool) => (
                <div
                  key={`${server}-${tool.name}`}
                  onClick={() => setSelectedTool(selectedTool?.name === tool.name && selectedTool?.server === server ? null : tool)}
                  className={`px-3 py-2 cursor-pointer transition-colors hover:bg-accent/5 ${
                    selectedTool?.name === tool.name && selectedTool?.server === server ? 'bg-accent/10' : ''
                  }`}
                >
                  <div className="flex items-center gap-1.5">
                    <span className="text-[10px]">🔧</span>
                    <span className="text-xs font-medium truncate">{tool.name}</span>
                    {!tool.enabled && <span className="text-[9px] text-muted bg-accent/10 px-1 rounded">disabled</span>}
                  </div>
                  {tool.description && (
                    <div className="text-[10px] text-muted truncate mt-0.5 pl-4">{tool.description}</div>
                  )}
                </div>
              ))}
            </div>
          ))
        )}
      </div>

      {/* Tool detail panel */}
      {selectedTool && (
        <div className="border-t border-border p-3 max-h-[250px] overflow-y-auto bg-surface/50">
          <div className="flex items-center justify-between mb-2">
            <h4 className="text-xs font-semibold">{selectedTool.name}</h4>
            <button onClick={() => setSelectedTool(null)} className="text-muted hover:text-foreground text-[10px]">&times;</button>
          </div>
          <div className="space-y-1.5 text-[10px]">
            <div><span className="text-muted">Server: </span><span className="font-mono">{selectedTool.server}</span></div>
            <div><span className="text-muted">Description: </span>{selectedTool.description || '—'}</div>
            <div><span className="text-muted">Enabled: </span><span className={selectedTool.enabled ? 'text-green-400' : 'text-red-400'}>{String(selectedTool.enabled)}</span></div>
            {selectedTool.inputSchema && (
              <div>
                <div className="text-muted mb-0.5">Input Schema:</div>
                <pre className="text-[9px] font-mono bg-accent/5 rounded p-2 overflow-x-auto">
                  {JSON.stringify(selectedTool.inputSchema, null, 2)}
                </pre>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
