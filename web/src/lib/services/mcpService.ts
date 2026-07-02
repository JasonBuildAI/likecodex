/** MCP Service — API functions for MCP server and tool management */

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || '/api';

export interface McpServerInfo {
  name: string;
  command: string;
  args: string[];
  enabled: boolean;
  startup: string;
  status: 'disconnected' | 'connecting' | 'connected' | 'error';
  tools_count: number;
}

export interface McpToolInfo {
  name: string;
  description: string;
  server: string;
  enabled: boolean;
}

export async function fetchMcpServers(): Promise<McpServerInfo[]> {
  const resp = await fetch(`${API_BASE}/api/ide/mcp/servers`);
  if (!resp.ok) return [];
  const data = await resp.json();
  return (data.servers || []) as McpServerInfo[];
}

export async function fetchMcpServerStatus(name: string): Promise<{ status: string; tools: unknown[]; tools_count: number }> {
  const resp = await fetch(`${API_BASE}/api/ide/mcp/status?name=${encodeURIComponent(name)}`);
  if (!resp.ok) return { status: 'disconnected', tools: [], tools_count: 0 };
  return resp.json();
}

export async function connectMcpServer(name: string): Promise<{ ok: boolean; status: string; error?: string }> {
  const resp = await fetch(`${API_BASE}/api/ide/mcp/connect`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name }),
  });
  return resp.json();
}

export async function disconnectMcpServer(name: string): Promise<{ ok: boolean }> {
  const resp = await fetch(`${API_BASE}/api/ide/mcp/disconnect`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name }),
  });
  return resp.json();
}

export async function fetchMcpTools(): Promise<{ tools: unknown[]; per_server: Record<string, McpToolInfo[]> }> {
  const resp = await fetch(`${API_BASE}/api/ide/mcp/tools`);
  if (!resp.ok) return { tools: [], per_server: {} };
  return resp.json();
}

export async function updateMcpServerConfig(
  name: string,
  config: { command?: string; args?: string[]; env?: Record<string, string>; enabled?: boolean }
): Promise<{ ok: boolean }> {
  const resp = await fetch(`${API_BASE}/api/ide/mcp/config`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name, ...config }),
  });
  return resp.json();
}

export async function deleteMcpServer(name: string): Promise<{ ok: boolean }> {
  const resp = await fetch(`${API_BASE}/api/ide/mcp/config`, {
    method: 'DELETE', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name }),
  });
  return resp.json();
}

export async function testMcpConnection(
  name: string,
  config: { command?: string; args?: string[]; env?: Record<string, string> }
): Promise<{ ok: boolean; connected: boolean; tools_count?: number; tools?: string[]; error?: string }> {
  const resp = await fetch(`${API_BASE}/api/ide/mcp/test`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name, ...config }),
  });
  return resp.json();
}
