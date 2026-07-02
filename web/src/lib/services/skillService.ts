import { fetchWithRetry } from './chatService';
import type { Skill } from '../store';

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || '/api';

// ── Skills ─────────────────────────────────────────────────────────────
export async function fetchSkills(): Promise<Skill[]> {
  const resp = await fetchWithRetry(`${API_BASE}/skills`);
  if (!resp.ok) return [];
  const data = await resp.json();
  return (data.skills || []) as Skill[];
}

export async function fetchSkillsList(): Promise<Skill[]> {
  const resp = await fetchWithRetry(`${API_BASE}/api/ide/skills/list`);
  if (!resp.ok) return [];
  const data = await resp.json();
  return (data.skills || []) as Skill[];
}

export async function fetchSkillDetail(name: string): Promise<Skill | null> {
  const resp = await fetchWithRetry(`${API_BASE}/api/ide/skills/detail?name=${encodeURIComponent(name)}`);
  if (!resp.ok) return null;
  return (await resp.json()) as Skill;
}

export async function createSkill(payload: { name: string; description?: string; body?: string; run_as?: string; model?: string; allowed_tools?: string[]; author?: string; version?: string }): Promise<{ ok: boolean; skill: Skill | null }> {
  const resp = await fetch(`${API_BASE}/api/ide/skills/create`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
  });
  return await resp.json();
}

export async function updateSkill(payload: { name: string; description?: string; body?: string; run_as?: string; model?: string | null; allowed_tools?: string[] }): Promise<{ ok: boolean; skill: Skill | null }> {
  const resp = await fetch(`${API_BASE}/api/ide/skills/update`, {
    method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload),
  });
  return await resp.json();
}

export async function deleteSkill(name: string): Promise<{ ok: boolean }> {
  const resp = await fetch(`${API_BASE}/api/ide/skills/delete`, {
    method: 'DELETE', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name }),
  });
  return await resp.json();
}

export async function toggleSkill(name: string): Promise<{ ok: boolean; enabled: boolean }> {
  const resp = await fetch(`${API_BASE}/api/ide/skills/enable`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name }),
  });
  return await resp.json();
}

export async function reloadSkills(): Promise<{ ok: boolean; skills: Skill[] }> {
  const resp = await fetch(`${API_BASE}/api/ide/skills/reload`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: '{}',
  });
  return await resp.json();
}

export async function invokeSkill(name: string, args?: string, sessionId?: string): Promise<{ skill: string; mode: string; result?: string; body?: string }> {
  const resp = await fetch(`${API_BASE}/api/ide/skills/invoke`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ name, args: args || '', session_id: sessionId || '' }),
  });
  return await resp.json();
}

export async function installSkill(url: string): Promise<{ ok: boolean; skill: Skill | null }> {
  const resp = await fetch(`${API_BASE}/api/ide/skills/install`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ url }),
  });
  return await resp.json();
}

export async function exportSkill(name: string): Promise<Blob> {
  const resp = await fetch(`${API_BASE}/api/ide/skills/export?name=${encodeURIComponent(name)}`);
  return await resp.blob();
}

export async function importSkill(zipData: Blob): Promise<{ ok: boolean; imported: string[] }> {
  const formData = new FormData();
  formData.append('file', zipData, 'skills.zip');
  const resp = await fetch(`${API_BASE}/api/ide/skills/import`, { method: 'POST', body: formData });
  return await resp.json();
}

// ── Approval mode ──────────────────────────────────────────────────────
export async function setApprovalMode(sessionId: string, mode: string): Promise<{ ok: boolean; session_id: string; mode: string }> {
  const resp = await fetchWithRetry(`${API_BASE}/tool-approval-mode`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ session_id: sessionId, mode }),
  });
  if (!resp.ok) throw new Error(`Failed to set approval mode: ${resp.statusText}`);
  return resp.json();
}

// ── Task ───────────────────────────────────────────────────────────────
import type { Task } from '../store';

export async function createTask(prompt: string, sessionId?: string | null): Promise<Task> {
  const resp = await fetchWithRetry(`${API_BASE}/tasks`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ prompt, ...(sessionId ? { session_id: sessionId } : {}) }),
  });
  if (!resp.ok) throw new Error(`Failed to create task: ${resp.statusText}`);
  return (await resp.json()).task as Task;
}

// ── Checkpoints ────────────────────────────────────────────────────────
export async function fetchCheckpoints(): Promise<Array<{ id: string; label: string; created_at: number; files: string[] }>> {
  const resp = await fetchWithRetry(`${API_BASE}/checkpoints`);
  if (!resp.ok) return [];
  const data = await resp.json();
  return (data.checkpoints || []) as Array<{ id: string; label: string; created_at: number; files: string[] }>;
}

export async function rewindCheckpoint(checkpointId: string | null, mode: 'code' | 'conversation' | 'both' | 'fork' | 'summarize_from' | 'summarize_upto' = 'code'): Promise<Record<string, unknown>> {
  const resp = await fetchWithRetry(`${API_BASE}/checkpoints/rewind`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ checkpoint_id: checkpointId, mode }),
  });
  return resp.json();
}

// ── Ask ────────────────────────────────────────────────────────────────
export async function respondAsk(requestId: string, answers: Array<{ questionIndex: number; selected: string[] }>): Promise<void> {
  const resp = await fetchWithRetry(`${API_BASE}/ask/${requestId}/respond`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ answers }),
  });
  if (!resp.ok) throw new Error(`Ask response failed: ${resp.statusText}`);
}

// ── Permission ─────────────────────────────────────────────────────────
export async function respondPermission(requestId: string, approved: boolean, grantScope: 'once' | 'session' | 'prefix' = 'once'): Promise<void> {
  const resp = await fetchWithRetry(`${API_BASE}/permissions/${requestId}/respond`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ approved, grant_scope: grantScope }),
  });
  if (!resp.ok) throw new Error(`Permission response failed: ${resp.statusText}`);
}

// ── Config & Metrics ───────────────────────────────────────────────────
export async function fetchConfig(): Promise<Record<string, unknown>> {
  const resp = await fetchWithRetry(`${API_BASE}/config`);
  if (!resp.ok) return {};
  return resp.json();
}

export async function fetchCacheMetrics(): Promise<{ hit_rate?: number; recent_hit_rate?: number }> {
  const resp = await fetchWithRetry(`${API_BASE}/metrics`);
  if (!resp.ok) return {};
  return resp.json();
}

// ── Codegraph & Index ──────────────────────────────────────────────────
import type { SearchResult } from '../store';

export async function searchCodeGraph(pattern: string): Promise<{ pattern: string; results: SearchResult[]; files?: string[] }> {
  const resp = await fetchWithRetry(`${API_BASE}/codegraph/search?pattern=${encodeURIComponent(pattern)}`);
  if (!resp.ok) return { pattern, results: [] };
  return resp.json();
}

export async function searchIndex(pattern: string): Promise<{ pattern: string; results: Array<{ path: string; language: string; size: number }> }> {
  const resp = await fetchWithRetry(`${API_BASE}/index/search?pattern=${encodeURIComponent(pattern)}`);
  if (!resp.ok) return { pattern, results: [] };
  return resp.json();
}

export async function searchCodeGraphCallers(name: string): Promise<{ symbol: string; callers: Array<{ path: string; line: number }>; count: number }> {
  const resp = await fetchWithRetry(`${API_BASE}/codegraph/callers?name=${encodeURIComponent(name)}`);
  if (!resp.ok) return { symbol: name, callers: [], count: 0 };
  return resp.json();
}

export interface CodeGraphVizResult {
  symbol: string;
  nodes: Array<{ name: string; kind: string; path: string; line: number; depth: number }>;
  edges: Array<{ source: string; target: string; type: string }>;
  total_nodes: number;
  total_edges: number;
}

export async function searchCodeGraphViz(name: string, max_depth: number = 2): Promise<CodeGraphVizResult> {
  const resp = await fetchWithRetry(`${API_BASE}/codegraph/viz?name=${encodeURIComponent(name)}&max_depth=${max_depth}`);
  if (!resp.ok) return { symbol: name, nodes: [], edges: [], total_nodes: 0, total_edges: 0 };
  return resp.json();
}

// ── Execute ────────────────────────────────────────────────────────────
export async function executeCommand(command: string, workingDir?: string): Promise<{ command: string; stdout: string; stderr: string; exit_code: number; timed_out: boolean; duration_ms: number }> {
  const resp = await fetchWithRetry(`${API_BASE}/execute`, {
    method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ command, working_dir: workingDir }),
  });
  if (!resp.ok) throw new Error(`Execute failed: ${resp.statusText}`);
  return resp.json();
}

// ── Utility ────────────────────────────────────────────────────────────
import type { ToolCall } from '../store';

export function parseToolCalls(toolCalls?: ToolCall[]): string {
  if (!toolCalls || toolCalls.length === 0) return '';
  return toolCalls.map((tc) => `[tool] ${tc.name}`).join('\n');
}
