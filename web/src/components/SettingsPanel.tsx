'use client';

import { useState, useEffect, useCallback } from 'react';
import { useAppStore } from '@/lib/store';
import { setApprovalMode as setApprovalModeApi } from '@/lib/api';
import {
  fetchMcpServers,
  fetchMcpTools,
  connectMcpServer,
  disconnectMcpServer,
  updateMcpServerConfig,
  deleteMcpServer,
  testMcpConnection,
  type McpServerInfo,
  type McpToolInfo,
} from '@/lib/api';

export function SettingsPanel() {
  const {
    settingsOpen, setSettingsOpen,
    apiKey, setApiKey,
    selectedModel, setSelectedModel,
    theme, setTheme,
    currentSessionId, approvalMode, setApprovalMode,
    addToast, config,
  } = useAppStore();
  const [showKey, setShowKey] = useState(false);
  const [activeTab, setActiveTab] = useState<'general' | 'mcp-tools' | 'mcp-servers'>('general');

  // MCP state
  const [mcpServers, setMcpServers] = useState<McpServerInfo[]>([]);
  const [mcpTools, setMcpTools] = useState<Record<string, McpToolInfo[]>>({});
  const [mcpLoading, setMcpLoading] = useState(false);
  const [connecting, setConnecting] = useState<string | null>(null);

  // Server config form
  const [showAddServer, setShowAddServer] = useState(false);
  const [editServer, setEditServer] = useState<string | null>(null);
  const [serverForm, setServerForm] = useState({ name: '', command: '', args: '', env: '' });
  const [testResult, setTestResult] = useState<string | null>(null);
  const [testing, setTesting] = useState(false);

  const loadMcpData = useCallback(async () => {
    setMcpLoading(true);
    try {
      const [servers, toolsData] = await Promise.all([
        fetchMcpServers(),
        fetchMcpTools(),
      ]);
      setMcpServers(servers);
      setMcpTools(toolsData.per_server || {});
    } catch (err) {
      console.error('Failed to load MCP data:', err);
    } finally {
      setMcpLoading(false);
    }
  }, []);

  useEffect(() => {
    if (settingsOpen) {
      loadMcpData();
    }
  }, [settingsOpen, loadMcpData]);

  const handleConnect = async (name: string) => {
    setConnecting(name);
    try {
      const res = await connectMcpServer(name);
      if (res.ok) {
        addToast({ type: 'success', message: `Connected to ${name}` });
      } else {
        addToast({ type: 'error', message: res.error || `Failed to connect ${name}` });
      }
      loadMcpData();
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
      loadMcpData();
    } catch (err) {
      addToast({ type: 'error', message: String(err) });
    }
  };

  const handleToggleServer = async (name: string, enabled: boolean) => {
    try {
      await updateMcpServerConfig(name, { enabled });
      addToast({ type: 'success', message: `${name} ${enabled ? 'enabled' : 'disabled'}` });
      loadMcpData();
    } catch (err) {
      addToast({ type: 'error', message: String(err) });
    }
  };

  const handleSaveServer = async () => {
    const { name, command, args, env } = serverForm;
    if (!name.trim() || !command.trim()) {
      addToast({ type: 'error', message: 'Name and command are required' });
      return;
    }
    try {
      const argsList = args.split(' ').filter(Boolean);
      let envObj: Record<string, string> = {};
      try {
        envObj = env ? JSON.parse(env) : {};
      } catch {
        addToast({ type: 'error', message: 'Environment must be valid JSON' });
        return;
      }
      await updateMcpServerConfig(name, { command, args: argsList, env: envObj });
      addToast({ type: 'success', message: `Server ${name} saved` });
      setShowAddServer(false);
      setEditServer(null);
      setServerForm({ name: '', command: '', args: '', env: '' });
      loadMcpData();
    } catch (err) {
      addToast({ type: 'error', message: String(err) });
    }
  };

  const handleDeleteServer = async (name: string) => {
    if (!confirm(`Delete MCP server "${name}"?`)) return;
    try {
      await deleteMcpServer(name);
      addToast({ type: 'success', message: `Deleted ${name}` });
      loadMcpData();
    } catch (err) {
      addToast({ type: 'error', message: String(err) });
    }
  };

  const handleTestConnection = async () => {
    const { name, command, args, env } = serverForm;
    if (!command.trim()) {
      addToast({ type: 'error', message: 'Command is required to test' });
      return;
    }
    setTesting(true);
    setTestResult(null);
    try {
      const argsList = args.split(' ').filter(Boolean);
      let envObj: Record<string, string> = {};
      try { envObj = env ? JSON.parse(env) : {}; } catch { /* ignore */ }
      const res = await testMcpConnection(name || 'test', { command, args: argsList, env: envObj });
      if (res.connected) {
        setTestResult(`Connected! ${res.tools_count} tools found: ${res.tools?.join(', ') || 'none'}`);
      } else {
        setTestResult(`Failed: ${res.error}`);
      }
    } catch (err) {
      setTestResult(`Error: ${err}`);
    } finally {
      setTesting(false);
    }
  };

  const openEditServer = (server: McpServerInfo) => {
    setServerForm({
      name: server.name,
      command: server.command,
      args: server.args.join(' '),
      env: '{}',
    });
    setEditServer(server.name);
    setShowAddServer(true);
  };

  const statusColor = (status: string) => {
    switch (status) {
      case 'connected': return 'text-green-500';
      case 'connecting': return 'text-yellow-500';
      case 'error': return 'text-red-500';
      default: return 'text-muted';
    }
  };

  const statusDot = (status: string) => {
    switch (status) {
      case 'connected': return 'bg-green-500';
      case 'connecting': return 'bg-yellow-500 animate-pulse';
      case 'error': return 'bg-red-500';
      default: return 'bg-gray-400';
    }
  };

  // Load available models from config
  const availableModels = (() => {
    const cfg = config as Record<string, unknown>;
    const llm = (cfg.llm || {}) as Record<string, unknown>;
    if (llm.model) return [String(llm.model)];
    return ['deepseek-v4-flash', 'deepseek-v4-pro'];
  })();

  const approvalModes = [
    { value: 'read-only', label: 'Read Only', desc: 'Only read operations' },
    { value: 'auto', label: 'Auto', desc: 'Auto-approve safe ops' },
    { value: 'auto-approve', label: 'Auto Approve', desc: 'Approve all tools' },
    { value: 'full-access', label: 'Full Access', desc: 'All operations allowed' },
    { value: 'yolo', label: 'YOLO', desc: 'No confirmations' },
    { value: 'sandbox-required', label: 'Sandbox', desc: 'Sandbox only' },
  ];

  const handleSetApproval = async (mode: string) => {
    try {
      if (currentSessionId) {
        await setApprovalModeApi(currentSessionId, mode);
      }
      setApprovalMode(mode);
      addToast({ type: 'success', message: `Approval mode: ${mode}` });
    } catch (err) {
      addToast({ type: 'error', message: `Failed: ${err}` });
    }
  };

  if (!settingsOpen) {
    return (
      <button
        onClick={() => setSettingsOpen(true)}
        className="fixed bottom-4 right-4 z-50 flex h-10 w-10 items-center justify-center rounded-full bg-surface shadow-lg border border-border hover:bg-accent/10 transition-colors"
        title="Settings"
      >
        <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
        </svg>
      </button>
    );
  }

  return (
    <div className="fixed bottom-4 right-4 z-50 w-96 rounded-xl bg-surface border border-border shadow-2xl p-4 max-h-[85vh] overflow-y-auto">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold">Settings</h3>
        <button
          onClick={() => setSettingsOpen(false)}
          className="text-muted hover:text-foreground transition-colors"
        >
          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      {/* Tabs */}
      <div className="flex gap-1 mb-3 border-b border-border pb-2">
        <button
          onClick={() => setActiveTab('general')}
          className={`px-2 py-1 text-[10px] rounded transition-colors ${
            activeTab === 'general' ? 'bg-primary text-white' : 'bg-accent/10 hover:bg-accent/20'
          }`}
        >
          General
        </button>
        <button
          onClick={() => setActiveTab('mcp-tools')}
          className={`px-2 py-1 text-[10px] rounded transition-colors ${
            activeTab === 'mcp-tools' ? 'bg-primary text-white' : 'bg-accent/10 hover:bg-accent/20'
          }`}
        >
          MCP Tools
        </button>
        <button
          onClick={() => setActiveTab('mcp-servers')}
          className={`px-2 py-1 text-[10px] rounded transition-colors ${
            activeTab === 'mcp-servers' ? 'bg-primary text-white' : 'bg-accent/10 hover:bg-accent/20'
          }`}
        >
          MCP Servers
        </button>
      </div>

      {activeTab === 'general' && (
        <div className="space-y-4">
          {/* Theme */}
          <div>
            <label className="block text-xs font-medium text-muted mb-1">Theme</label>
            <div className="flex gap-1.5">
              <button
                onClick={() => setTheme('dark')}
                className={`flex-1 rounded-lg px-3 py-2 text-xs font-medium transition-colors ${
                  theme === 'dark' ? 'bg-primary text-white' : 'bg-accent/10 hover:bg-accent/20'
                }`}
              >
                Dark
              </button>
              <button
                onClick={() => setTheme('light')}
                className={`flex-1 rounded-lg px-3 py-2 text-xs font-medium transition-colors ${
                  theme === 'light' ? 'bg-primary text-white' : 'bg-accent/10 hover:bg-accent/20'
                }`}
              >
                Light
              </button>
            </div>
          </div>

          {/* Model Selector */}
          <div>
            <label className="block text-xs font-medium text-muted mb-1">Model</label>
            <div className="flex flex-wrap gap-1.5">
              {availableModels.map((model) => {
                const label = model.includes('pro') ? 'Pro' : model.includes('flash') ? 'Flash' : model;
                return (
                  <button
                    key={model}
                    onClick={() => setSelectedModel(model)}
                    className={`rounded-lg px-3 py-2 text-xs font-medium transition-colors ${
                      selectedModel === model
                        ? 'bg-primary text-white'
                        : 'bg-accent/10 hover:bg-accent/20'
                    }`}
                  >
                    {label}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Approval Mode */}
          <div>
            <label className="block text-xs font-medium text-muted mb-1">Approval Mode</label>
            <div className="grid grid-cols-3 gap-1">
              {approvalModes.map((m) => (
                <button
                  key={m.value}
                  onClick={() => handleSetApproval(m.value)}
                  title={m.desc}
                  className={`rounded px-2 py-1.5 text-[10px] font-medium transition-colors text-center ${
                    approvalMode === m.value
                      ? 'bg-primary text-white'
                      : 'bg-accent/10 hover:bg-accent/20'
                  }`}
                >
                  {m.label}
                </button>
              ))}
            </div>
          </div>

          {/* API Key */}
          <div>
            <label className="block text-xs font-medium text-muted mb-1">DeepSeek API Key</label>
            <div className="flex gap-1">
              <div className="relative flex-1">
                <input
                  type={showKey ? 'text' : 'password'}
                  value={apiKey}
                  onChange={(e) => setApiKey(e.target.value)}
                  placeholder="sk-..."
                  className="w-full rounded-lg border border-border bg-background px-3 py-2 pr-8 text-xs font-mono placeholder:text-muted/50 focus:outline-none focus:border-primary"
                />
                <button
                  onClick={() => setShowKey(!showKey)}
                  className="absolute right-2 top-1/2 -translate-y-1/2 text-muted hover:text-foreground"
                >
                  {showKey ? (
                    <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21" />
                    </svg>
                  ) : (
                    <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                    </svg>
                  )}
                </button>
              </div>
            </div>
          </div>

          {/* Status */}
          <div className="flex items-center justify-between rounded-lg bg-accent/5 px-3 py-2">
            <span className="text-xs text-muted">Status</span>
            <span className={`flex items-center gap-1.5 text-xs font-medium ${apiKey ? 'text-green-600' : 'text-amber-600'}`}>
              <span className={`inline-block h-2 w-2 rounded-full ${apiKey ? 'bg-green-500' : 'bg-amber-500'}`} />
              {apiKey ? 'Configured' : 'Not set'}
            </span>
          </div>

          {/* Cache Hit Rate */}
          <CacheHitRatePanel sessionId={currentSessionId} />

          {/* Token Statistics */}
          <TokenStatsPanel sessionId={currentSessionId} />
        </div>
      )}

      {activeTab === 'mcp-tools' && (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <label className="text-xs font-medium text-muted">MCP Tools</label>
            <button
              onClick={loadMcpData}
              disabled={mcpLoading}
              className="px-2 py-0.5 text-[10px] rounded bg-accent/10 hover:bg-accent/20 transition disabled:opacity-50"
            >
              {mcpLoading ? '...' : 'Refresh'}
            </button>
          </div>
          {mcpLoading ? (
            <div className="flex items-center justify-center py-4">
              <div className="h-4 w-4 animate-spin rounded-full border-2 border-primary border-t-transparent" />
            </div>
          ) : Object.keys(mcpTools).length === 0 ? (
            <div className="text-xs text-muted py-4 text-center">No MCP tools registered. Connect to an MCP server first.</div>
          ) : (
            Object.entries(mcpTools).map(([server, tools]) => (
              <div key={server} className="rounded-lg border border-border/60 overflow-hidden">
                <div className="px-3 py-1.5 bg-accent/5 border-b border-border/40 text-xs font-medium text-muted flex items-center gap-2">
                  <span className={`inline-block h-1.5 w-1.5 rounded-full ${
                    mcpServers.find(s => s.name === server)?.status === 'connected' ? 'bg-green-500' : 'bg-gray-400'
                  }`} />
                  {server}
                  <span className="text-[10px] text-muted/60">({tools.length} tools)</span>
                </div>
                <div className="space-y-0.5 p-2">
                  {tools.map((tool) => (
                    <div key={tool.name} className="flex items-center justify-between px-2 py-1.5 rounded hover:bg-accent/5 transition-colors">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-1.5">
                          <span className="text-[10px] text-muted/50">🔧</span>
                          <span className="text-xs font-medium truncate">{tool.name}</span>
                        </div>
                        {tool.description && (
                          <div className="text-[10px] text-muted truncate pl-4">{tool.description}</div>
                        )}
                      </div>
                      <span className="text-[9px] text-muted/50 px-1.5 py-0.5 rounded bg-accent/10">{server}</span>
                    </div>
                  ))}
                </div>
              </div>
            ))
          )}
        </div>
      )}

      {activeTab === 'mcp-servers' && (
        <div className="space-y-3">
          <div className="flex items-center justify-between">
            <label className="text-xs font-medium text-muted">MCP Servers</label>
            <div className="flex gap-1">
              <button
                onClick={loadMcpData}
                disabled={mcpLoading}
                className="px-2 py-0.5 text-[10px] rounded bg-accent/10 hover:bg-accent/20 transition"
              >
                Refresh
              </button>
              <button
                onClick={() => {
                  setEditServer(null);
                  setServerForm({ name: '', command: '', args: '', env: '' });
                  setTestResult(null);
                  setShowAddServer(true);
                }}
                className="px-2 py-0.5 text-[10px] rounded bg-primary text-white hover:bg-primary/80 transition"
              >
                + Add
              </button>
            </div>
          </div>

          {/* Server list */}
          {mcpLoading ? (
            <div className="flex items-center justify-center py-4">
              <div className="h-4 w-4 animate-spin rounded-full border-2 border-primary border-t-transparent" />
            </div>
          ) : mcpServers.length === 0 ? (
            <div className="text-xs text-muted py-4 text-center">No MCP servers configured. Add one to get started.</div>
          ) : (
            <div className="space-y-2">
              {mcpServers.map((server) => (
                <div key={server.name} className="rounded-lg border border-border/60 p-3 space-y-2">
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <span className={`inline-block h-2 w-2 rounded-full ${statusDot(server.status)}`} />
                      <span className="text-xs font-medium">{server.name}</span>
                      <span className={`text-[10px] ${statusColor(server.status)}`}>{server.status}</span>
                    </div>
                    <div className="flex gap-1">
                      <button
                        onClick={() => openEditServer(server)}
                        className="px-1.5 py-0.5 text-[9px] rounded bg-accent/10 hover:bg-accent/20 transition"
                      >
                        Edit
                      </button>
                      <button
                        onClick={() => handleDeleteServer(server.name)}
                        className="px-1.5 py-0.5 text-[9px] rounded bg-red-500/10 text-red-400 hover:bg-red-500/20 transition"
                      >
                        Del
                      </button>
                    </div>
                  </div>
                  <div className="flex items-center gap-2 text-[10px] text-muted">
                    <code className="px-1 py-0.5 rounded bg-accent/10 truncate max-w-[200px]">{server.command} {server.args.join(' ')}</code>
                  </div>
                  <div className="flex items-center justify-between">
                    <div className="flex items-center gap-2">
                      <label className="text-[10px] text-muted">Enabled</label>
                      <button
                        onClick={() => handleToggleServer(server.name, !server.enabled)}
                        className={`relative inline-flex h-4 w-7 items-center rounded-full transition-colors ${
                          server.enabled ? 'bg-primary' : 'bg-accent/20'
                        }`}
                      >
                        <span className={`inline-block h-3 w-3 rounded-full bg-white transition-transform ${
                          server.enabled ? 'translate-x-3.5' : 'translate-x-0.5'
                        }`} />
                      </button>
                    </div>
                    <div className="flex gap-1">
                      {server.status === 'connected' ? (
                        <button
                          onClick={() => handleDisconnect(server.name)}
                          className="px-2 py-0.5 text-[9px] rounded bg-yellow-500/10 text-yellow-400 hover:bg-yellow-500/20 transition"
                        >
                          Disconnect
                        </button>
                      ) : (
                        <button
                          onClick={() => handleConnect(server.name)}
                          disabled={connecting === server.name}
                          className="px-2 py-0.5 text-[9px] rounded bg-primary/10 text-primary hover:bg-primary/20 transition disabled:opacity-50"
                        >
                          {connecting === server.name ? '...' : 'Connect'}
                        </button>
                      )}
                    </div>
                  </div>
                  {server.tools_count > 0 && (
                    <div className="text-[10px] text-muted">{server.tools_count} tools registered</div>
                  )}
                </div>
              ))}
            </div>
          )}

          {/* Add/Edit server form */}
          {showAddServer && (
            <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/50" onClick={() => setShowAddServer(false)}>
              <div className="bg-surface rounded-lg border border-border w-full max-w-md shadow-xl p-4" onClick={(e) => e.stopPropagation()}>
                <div className="flex items-center justify-between mb-3">
                  <h4 className="text-sm font-semibold">{editServer ? 'Edit Server' : 'Add MCP Server'}</h4>
                  <button onClick={() => setShowAddServer(false)} className="text-muted hover:text-foreground">&times;</button>
                </div>
                <div className="space-y-3">
                  <div>
                    <label className="text-[10px] text-muted block mb-0.5">Name</label>
                    <input
                      value={serverForm.name}
                      onChange={(e) => setServerForm(f => ({ ...f, name: e.target.value }))}
                      placeholder="my-server"
                      disabled={!!editServer}
                      className="w-full px-2 py-1.5 text-xs rounded bg-background border border-border focus:border-primary outline-none disabled:opacity-50"
                    />
                  </div>
                  <div>
                    <label className="text-[10px] text-muted block mb-0.5">Command</label>
                    <input
                      value={serverForm.command}
                      onChange={(e) => setServerForm(f => ({ ...f, command: e.target.value }))}
                      placeholder="npx"
                      className="w-full px-2 py-1.5 text-xs rounded bg-background border border-border focus:border-primary outline-none"
                    />
                  </div>
                  <div>
                    <label className="text-[10px] text-muted block mb-0.5">Arguments (space separated)</label>
                    <input
                      value={serverForm.args}
                      onChange={(e) => setServerForm(f => ({ ...f, args: e.target.value }))}
                      placeholder="-y @modelcontextprotocol/server-filesystem ."
                      className="w-full px-2 py-1.5 text-xs rounded bg-background border border-border focus:border-primary outline-none"
                    />
                  </div>
                  <div>
                    <label className="text-[10px] text-muted block mb-0.5">Environment Variables (JSON)</label>
                    <textarea
                      value={serverForm.env}
                      onChange={(e) => setServerForm(f => ({ ...f, env: e.target.value }))}
                      placeholder='{"API_KEY": "xxx"}'
                      rows={3}
                      className="w-full px-2 py-1.5 text-xs rounded bg-background border border-border focus:border-primary outline-none font-mono"
                    />
                  </div>
                  {testResult && (
                    <div className={`px-2 py-1.5 text-[10px] rounded ${
                      testResult.includes('Connected') ? 'bg-green-500/10 text-green-400' : 'bg-red-500/10 text-red-400'
                    }`}>
                      {testResult}
                    </div>
                  )}
                  <div className="flex gap-2">
                    <button
                      onClick={handleTestConnection}
                      disabled={testing || !serverForm.command.trim()}
                      className="px-3 py-1.5 text-[10px] rounded bg-accent/10 hover:bg-accent/20 transition disabled:opacity-50"
                    >
                      {testing ? 'Testing...' : 'Test Connection'}
                    </button>
                    <button
                      onClick={handleSaveServer}
                      disabled={!serverForm.name.trim() || !serverForm.command.trim()}
                      className="px-3 py-1.5 text-[10px] rounded bg-primary text-white hover:bg-primary/80 transition disabled:opacity-50 ml-auto"
                    >
                      Save
                    </button>
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ── Cache Hit Rate Sub-Component ────────────────────────────────────────

interface CacheStats {
  hit_rate: number;
  recent_hit_rate: number;
  request_count: number;
  total_hit_tokens: number;
  total_miss_tokens: number;
  cost_savings?: number;
}

function CacheHitRatePanel({ sessionId }: { sessionId: string | null }) {
  const [stats, setStats] = useState<CacheStats | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const fetchStats = async () => {
      setLoading(true);
      try {
        const params = new URLSearchParams();
        if (sessionId) params.set('session_id', sessionId);
        const resp = await fetch(`/api/deepseek/cache-stats?${params.toString()}`);
        if (!cancelled && resp.ok) {
          const data = await resp.json();
          const flashInputPrice = 0.10;
          const flashCachePrice = 0.01;
          const cacheSavings = (
            data.total_hit_tokens * (flashInputPrice - flashCachePrice)
          ) / 1_000_000;
          setStats({ ...data, cost_savings: cacheSavings });
        }
      } catch {
        // ignore
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    fetchStats();
    const interval = setInterval(fetchStats, 10000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [sessionId]);

  if (!stats && loading) {
    return (
      <div>
        <label className="block text-xs font-medium text-muted mb-1">Cache Hit Rate</label>
        <div className="rounded-lg bg-accent/5 px-3 py-2 text-xs text-muted">Loading...</div>
      </div>
    );
  }

  if (!stats) return null;

  const hitRatePct = (stats.hit_rate * 100).toFixed(1);
  const recentPct = (stats.recent_hit_rate * 100).toFixed(1);
  const tokensSaved = (stats.total_hit_tokens / 1000).toFixed(0);
  const totalTokens = ((stats.total_hit_tokens + stats.total_miss_tokens) / 1000).toFixed(0);

  return (
    <div>
      <label className="block text-xs font-medium text-muted mb-1">
        Cache Hit Rate
        {loading && <span className="ml-1 text-[10px] text-muted/50">⟳</span>}
      </label>
      <div className="rounded-lg bg-accent/5 px-3 py-2 space-y-1.5">
        <div className="flex items-center gap-2">
          <div className="flex-1 h-2 bg-accent/10 rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full transition-all duration-500 ${
                stats.hit_rate > 0.6 ? 'bg-green-500' : stats.hit_rate > 0.3 ? 'bg-amber-500' : 'bg-red-500'
              }`}
              style={{ width: `${hitRatePct}%` }}
            />
          </div>
          <span className="text-xs font-mono font-medium">{hitRatePct}%</span>
        </div>
        <div className="grid grid-cols-3 gap-2 text-[10px]">
          <div>
            <span className="text-muted block">Requests</span>
            <span className="font-mono font-medium">{stats.request_count}</span>
          </div>
          <div>
            <span className="text-muted block">Tokens Saved</span>
            <span className="font-mono font-medium">{tokensSaved}K</span>
          </div>
          <div>
            <span className="text-muted block">Total /K</span>
            <span className="font-mono font-medium">{totalTokens}K</span>
          </div>
        </div>
        <div className="flex items-center justify-between pt-1 border-t border-border/50">
          <span className="text-[10px] text-muted">Est. Savings</span>
          <span className="text-xs font-mono font-medium text-green-600">
            ${stats.cost_savings?.toFixed(4) || '0.0000'}
          </span>
        </div>
        <div className="flex items-center justify-between">
          <span className="text-[10px] text-muted">Recent (last 100)</span>
          <span className={`text-xs font-mono font-medium ${
            parseFloat(recentPct) > 60 ? 'text-green-500' : 'text-amber-500'
          }`}>
            {recentPct}%
          </span>
        </div>
      </div>
    </div>
  );
}

// ── Token Statistics Sub-Component ──────────────────────────────────────

interface TokenStats {
  session_id: string;
  request_count: number;
  total_tokens: number;
  total_input_tokens: number;
  total_output_tokens: number;
  total_cache_hit_tokens: number;
  total_cache_miss_tokens: number;
  overall_cache_hit_rate: number;
  total_cost: number;
  total_input_cost: number;
  total_output_cost: number;
  model_switch_count: number;
  duration_seconds: number;
}

function TokenStatsPanel({ sessionId }: { sessionId: string | null }) {
  const [tokenStats, setTokenStats] = useState<TokenStats | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    let cancelled = false;
    const fetchData = async () => {
      if (!sessionId) return;
      setLoading(true);
      try {
        const resp = await fetch(`/api/deepseek/session-cost?session_id=${encodeURIComponent(sessionId)}`);
        if (!cancelled && resp.ok) {
          setTokenStats(await resp.json());
        }
      } catch {
        // ignore
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    fetchData();
    const interval = setInterval(fetchData, 15000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [sessionId]);

  if (!sessionId) return null;
  if (!tokenStats && loading) {
    return (
      <div>
        <label className="block text-xs font-medium text-muted mb-1">Token Usage</label>
        <div className="rounded-lg bg-accent/5 px-3 py-2 text-xs text-muted">Loading...</div>
      </div>
    );
  }

  if (!tokenStats) return null;

  const totalInputK = (tokenStats.total_input_tokens / 1000).toFixed(1);
  const totalOutputK = (tokenStats.total_output_tokens / 1000).toFixed(1);
  const totalTokensK = (tokenStats.total_tokens / 1000).toFixed(1);
  const hitPct = (tokenStats.overall_cache_hit_rate * 100).toFixed(1);
  const inputBarPct = tokenStats.total_tokens > 0
    ? (tokenStats.total_input_tokens / tokenStats.total_tokens * 100).toFixed(1)
    : '50';

  return (
    <div>
      <label className="block text-xs font-medium text-muted mb-1">Token Usage</label>
      <div className="rounded-lg bg-accent/5 px-3 py-2 space-y-2">
        {/* Token bar chart */}
        <div className="space-y-1">
          <div className="flex items-center justify-between text-[10px]">
            <span className="text-muted">Input / Output</span>
            <span className="font-mono font-medium">{totalInputK}K / {totalOutputK}K</span>
          </div>
          <div className="h-3 bg-accent/10 rounded-full overflow-hidden flex">
            <div
              className="h-full bg-blue-500 transition-all duration-500"
              style={{ width: `${inputBarPct}%` }}
              title={`Input: ${totalInputK}K`}
            />
            <div
              className="h-full bg-purple-500 transition-all duration-500"
              style={{ width: `${(100 - parseFloat(inputBarPct))}%` }}
              title={`Output: ${totalOutputK}K`}
            />
          </div>
          <div className="flex items-center gap-3 text-[9px] text-muted">
            <span className="flex items-center gap-1">
              <span className="inline-block h-2 w-2 rounded bg-blue-500" /> Input
            </span>
            <span className="flex items-center gap-1">
              <span className="inline-block h-2 w-2 rounded bg-purple-500" /> Output
            </span>
          </div>
        </div>

        {/* Model breakdown */}
        <div className="grid grid-cols-3 gap-2 text-[10px]">
          <div>
            <span className="text-muted block">Total Tokens</span>
            <span className="font-mono font-medium">{totalTokensK}K</span>
          </div>
          <div>
            <span className="text-muted block">Cache Hit</span>
            <span className="font-mono font-medium">{hitPct}%</span>
          </div>
          <div>
            <span className="text-muted block">Switches</span>
            <span className="font-mono font-medium">{tokenStats.model_switch_count}</span>
          </div>
        </div>

        {/* Model usage breakdown */}
        <div className="pt-1 border-t border-border/50">
          <span className="text-[10px] text-muted block mb-1">Model Breakdown</span>
          <div className="flex gap-2">
            <div className="flex-1 rounded bg-accent/10 px-2 py-1.5 text-center">
              <div className="text-[9px] text-muted">Flash</div>
              <div className="text-xs font-mono font-medium">
                {tokenStats.total_input_cost > 0 ? 'Active' : '—'}
              </div>
            </div>
            <div className="flex-1 rounded bg-accent/10 px-2 py-1.5 text-center">
              <div className="text-[9px] text-muted">Pro</div>
              <div className="text-xs font-mono font-medium">
                {tokenStats.total_input_cost > 0.01 ? 'Active' : '—'}
              </div>
            </div>
          </div>
        </div>

        {/* Cost estimation */}
        <div className="flex items-center justify-between pt-1 border-t border-border/50">
          <span className="text-[10px] text-muted">Est. Cost</span>
          <span className="text-xs font-mono font-medium">
            ${tokenStats.total_cost.toFixed(6)}
          </span>
        </div>

        {/* Session duration */}
        <div className="flex items-center justify-between">
          <span className="text-[10px] text-muted">Session Duration</span>
          <span className="text-xs font-mono font-medium">
            {tokenStats.duration_seconds > 3600
              ? `${(tokenStats.duration_seconds / 3600).toFixed(1)}h`
              : tokenStats.duration_seconds > 60
                ? `${(tokenStats.duration_seconds / 60).toFixed(0)}m`
                : `${tokenStats.duration_seconds.toFixed(0)}s`}
          </span>
        </div>
      </div>
    </div>
  );
}