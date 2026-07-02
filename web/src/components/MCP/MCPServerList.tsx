'use client';

import { useState, useEffect, useCallback } from 'react';
import {
  fetchMcpServers,
  connectMcpServer,
  disconnectMcpServer,
  testMcpConnection,
  updateMcpServerConfig,
  deleteMcpServer,
  type McpServerInfo,
} from '@/lib/api';
import { useAppStore } from '@/lib/store';

export function MCPServerList() {
  const [servers, setServers] = useState<McpServerInfo[]>([]);
  const [loading, setLoading] = useState(false);
  const [connecting, setConnecting] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [editName, setEditName] = useState<string | null>(null);
  const [form, setForm] = useState({ name: '', command: '', args: '', env: '' });
  const [testResult, setTestResult] = useState<string | null>(null);
  const [testing, setTesting] = useState(false);
  const addToast = useAppStore((s) => s.addToast);

  const loadServers = useCallback(async () => {
    setLoading(true);
    try {
      const data = await fetchMcpServers();
      setServers(data);
    } catch {
      // ignore
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadServers(); }, [loadServers]);

  const handleConnect = async (name: string) => {
    setConnecting(name);
    try {
      const res = await connectMcpServer(name);
      addToast({ type: res.ok ? 'success' : 'error', message: res.ok ? `Connected to ${name}` : res.error || 'Failed' });
      loadServers();
    } catch (err) {
      addToast({ type: 'error', message: String(err) });
    } finally {
      setConnecting(null);
    }
  };

  const handleDisconnect = async (name: string) => {
    try {
      await disconnectMcpServer(name);
      addToast({ type: 'success', message: `Disconnected ${name}` });
      loadServers();
    } catch (err) {
      addToast({ type: 'error', message: String(err) });
    }
  };

  const handleToggle = async (name: string, enabled: boolean) => {
    try {
      await updateMcpServerConfig(name, { enabled });
      addToast({ type: 'success', message: `${name} ${enabled ? 'enabled' : 'disabled'}` });
      loadServers();
    } catch (err) {
      addToast({ type: 'error', message: String(err) });
    }
  };

  const handleSave = async () => {
    if (!form.name.trim() || !form.command.trim()) {
      addToast({ type: 'error', message: 'Name and command are required' });
      return;
    }
    try {
      const argsList = form.args.split(' ').filter(Boolean);
      let envObj: Record<string, string> = {};
      try { envObj = form.env ? JSON.parse(form.env) : {}; } catch { addToast({ type: 'error', message: 'Invalid JSON for env' }); return; }
      await updateMcpServerConfig(form.name, { command: form.command, args: argsList, env: envObj });
      addToast({ type: 'success', message: `Server ${form.name} saved` });
      setShowForm(false); setEditName(null);
      setForm({ name: '', command: '', args: '', env: '' });
      loadServers();
    } catch (err) {
      addToast({ type: 'error', message: String(err) });
    }
  };

  const handleDelete = async (name: string) => {
    try {
      await deleteMcpServer(name);
      addToast({ type: 'success', message: `Deleted ${name}` });
      loadServers();
    } catch (err) {
      addToast({ type: 'error', message: String(err) });
    }
  };

  const handleTest = async () => {
    if (!form.command.trim()) return;
    setTesting(true); setTestResult(null);
    try {
      const argsList = form.args.split(' ').filter(Boolean);
      let envObj: Record<string, string> = {};
      try { envObj = form.env ? JSON.parse(form.env) : {}; } catch { /* ignore */ }
      const res = await testMcpConnection(form.name || 'test', { command: form.command, args: argsList, env: envObj });
      setTestResult(res.connected ? `Connected! ${res.tools_count} tools` : `Failed: ${res.error}`);
    } catch (err) {
      setTestResult(`Error: ${err}`);
    } finally { setTesting(false); }
  };

  const openEdit = (server: McpServerInfo) => {
    setForm({ name: server.name, command: server.command, args: server.args.join(' '), env: '{}' });
    setEditName(server.name);
    setShowForm(true);
  };

  const statusDot = (status: string) => {
    switch (status) {
      case 'connected': return 'bg-green-500';
      case 'connecting': return 'bg-yellow-500 animate-pulse';
      case 'error': return 'bg-red-500';
      default: return 'bg-gray-400';
    }
  };

  return (
    <div className="flex flex-col h-full">
      <div className="p-3 border-b border-border">
        <div className="flex items-center justify-between mb-2">
          <h2 className="text-sm font-semibold">MCP Servers</h2>
          <div className="flex gap-1">
            <button onClick={loadServers} disabled={loading}
              className="px-2 py-0.5 text-[10px] rounded bg-accent/10 hover:bg-accent/20 transition disabled:opacity-50"
            >{loading ? '...' : 'Refresh'}</button>
            <button onClick={() => { setEditName(null); setForm({ name: '', command: '', args: '', env: '' }); setTestResult(null); setShowForm(true); }}
              className="px-2 py-0.5 text-[10px] rounded bg-primary text-white hover:bg-primary/80 transition"
            >+ Add</button>
          </div>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-2 space-y-2">
        {loading && servers.length === 0 ? (
          <div className="flex items-center justify-center py-6">
            <div className="h-4 w-4 animate-spin rounded-full border-2 border-primary border-t-transparent" />
          </div>
        ) : servers.length === 0 ? (
          <div className="text-xs text-muted text-center py-6">No MCP servers configured.</div>
        ) : (
          servers.map((server) => (
            <div key={server.name} className="rounded-lg border border-border/60 p-3 space-y-2">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className={`inline-block h-2 w-2 rounded-full ${statusDot(server.status)}`} />
                  <span className="text-xs font-medium">{server.name}</span>
                  <span className={`text-[10px] ${server.status === 'connected' ? 'text-green-500' : server.status === 'error' ? 'text-red-500' : 'text-muted'}`}>{server.status}</span>
                </div>
                <div className="flex gap-1">
                  <button onClick={() => openEdit(server)} className="px-1.5 py-0.5 text-[9px] rounded bg-accent/10 hover:bg-accent/20 transition">Edit</button>
                  <button onClick={() => handleDelete(server.name)} className="px-1.5 py-0.5 text-[9px] rounded bg-red-500/10 text-red-400 hover:bg-red-500/20 transition">Del</button>
                </div>
              </div>
              <div className="text-[10px] text-muted font-mono truncate">{server.command} {server.args.join(' ')}</div>
              <div className="flex items-center justify-between">
                <label className="flex items-center gap-1.5 text-[10px] text-muted cursor-pointer">
                  <button onClick={() => handleToggle(server.name, !server.enabled)}
                    className={`relative inline-flex h-4 w-7 items-center rounded-full transition-colors ${server.enabled ? 'bg-primary' : 'bg-accent/20'}`}
                  >
                    <span className={`inline-block h-3 w-3 rounded-full bg-white transition-transform ${server.enabled ? 'translate-x-3.5' : 'translate-x-0.5'}`} />
                  </button>
                  Enabled
                </label>
                <div className="flex gap-1">
                  {server.status === 'connected' ? (
                    <button onClick={() => handleDisconnect(server.name)} className="px-2 py-0.5 text-[9px] rounded bg-yellow-500/10 text-yellow-400 hover:bg-yellow-500/20 transition">Disconnect</button>
                  ) : (
                    <button onClick={() => handleConnect(server.name)} disabled={connecting === server.name}
                      className="px-2 py-0.5 text-[9px] rounded bg-primary/10 text-primary hover:bg-primary/20 transition disabled:opacity-50"
                    >{connecting === server.name ? '...' : 'Connect'}</button>
                  )}
                </div>
              </div>
              {server.tools_count > 0 && <div className="text-[10px] text-muted">{server.tools_count} tools</div>}
            </div>
          ))
        )}
      </div>

      {/* Add/Edit form modal */}
      {showForm && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/50" onClick={() => setShowForm(false)}>
          <div className="bg-surface rounded-lg border border-border w-full max-w-md shadow-xl p-4" onClick={(e) => e.stopPropagation()}>
            <div className="flex items-center justify-between mb-3">
              <h4 className="text-sm font-semibold">{editName ? 'Edit Server' : 'Add MCP Server'}</h4>
              <button onClick={() => setShowForm(false)} className="text-muted hover:text-foreground">&times;</button>
            </div>
            <div className="space-y-3">
              <div>
                <label className="text-[10px] text-muted block mb-0.5">Name</label>
                <input value={form.name} onChange={(e) => setForm(f => ({ ...f, name: e.target.value }))} placeholder="my-server" disabled={!!editName}
                  className="w-full px-2 py-1.5 text-xs rounded bg-background border border-border focus:border-primary outline-none disabled:opacity-50"
                />
              </div>
              <div>
                <label className="text-[10px] text-muted block mb-0.5">Command</label>
                <input value={form.command} onChange={(e) => setForm(f => ({ ...f, command: e.target.value }))} placeholder="npx"
                  className="w-full px-2 py-1.5 text-xs rounded bg-background border border-border focus:border-primary outline-none"
                />
              </div>
              <div>
                <label className="text-[10px] text-muted block mb-0.5">Arguments</label>
                <input value={form.args} onChange={(e) => setForm(f => ({ ...f, args: e.target.value }))} placeholder="-y package"
                  className="w-full px-2 py-1.5 text-xs rounded bg-background border border-border focus:border-primary outline-none"
                />
              </div>
              <div>
                <label className="text-[10px] text-muted block mb-0.5">Env (JSON)</label>
                <textarea value={form.env} onChange={(e) => setForm(f => ({ ...f, env: e.target.value }))} placeholder='{"KEY": "val"}' rows={3}
                  className="w-full px-2 py-1.5 text-xs rounded bg-background border border-border focus:border-primary outline-none font-mono"
                />
              </div>
              {testResult && (
                <div className={`px-2 py-1.5 text-[10px] rounded ${testResult.includes('Connected') ? 'bg-green-500/10 text-green-400' : 'bg-red-500/10 text-red-400'}`}>
                  {testResult}
                </div>
              )}
              <div className="flex gap-2">
                <button onClick={handleTest} disabled={testing || !form.command.trim()}
                  className="px-3 py-1.5 text-[10px] rounded bg-accent/10 hover:bg-accent/20 transition disabled:opacity-50"
                >{testing ? 'Testing...' : 'Test'}</button>
                <button onClick={handleSave} disabled={!form.name.trim() || !form.command.trim()}
                  className="px-3 py-1.5 text-[10px] rounded bg-primary text-white hover:bg-primary/80 transition disabled:opacity-50 ml-auto"
                >Save</button>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
