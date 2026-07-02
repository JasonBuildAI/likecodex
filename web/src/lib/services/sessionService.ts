import { fetchWithRetry, buildHeaders } from './chatService';
import type { SessionSummary, Message } from '../store';

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || '/api';

// ── Sessions ───────────────────────────────────────────────────────────
export async function fetchSessions(): Promise<SessionSummary[]> {
  const resp = await fetchWithRetry(`${API_BASE}/sessions`);
  if (!resp.ok) return [];
  const data = await resp.json();
  return (data.sessions || []) as SessionSummary[];
}

export async function fetchSessionEvents(sessionId: string): Promise<Message[]> {
  const resp = await fetchWithRetry(`${API_BASE}/sessions/${sessionId}/events`);
  if (!resp.ok) return [];
  const data = await resp.json();
  const events = (data.events || []) as Array<{ event_type: string; content: string; timestamp?: number }>;
  return events.map((event, index) => ({
    id: `${sessionId}-${index}`,
    role: event.event_type === 'user' ? 'user' : event.event_type === 'assistant' ? 'assistant' : event.event_type === 'tool_result' ? 'tool' : 'system',
    content: event.content,
    eventType: event.event_type,
    timestamp: event.timestamp || Date.now(),
  }));
}

export async function createNewSession(cwd?: string): Promise<{ ok: boolean; session_id: string; cwd?: string }> {
  const resp = await fetchWithRetry(`${API_BASE}/new`, {
    method: 'POST', headers: buildHeaders(),
    body: JSON.stringify(cwd ? { cwd } : {}),
  });
  if (!resp.ok) throw new Error(`Failed to create session: ${resp.statusText}`);
  return resp.json();
}

export async function resumeSession(sessionId: string): Promise<{ ok: boolean; session_id: string }> {
  const resp = await fetchWithRetry(`${API_BASE}/resume`, {
    method: 'POST', headers: buildHeaders(),
    body: JSON.stringify({ session_id: sessionId }),
  });
  if (!resp.ok) throw new Error(`Failed to resume session: ${resp.statusText}`);
  return resp.json();
}

export async function forkSession(sessionId: string, label?: string): Promise<{ ok: boolean; session_id: string; forked_from: string }> {
  const resp = await fetchWithRetry(`${API_BASE}/fork`, {
    method: 'POST', headers: buildHeaders(),
    body: JSON.stringify({ session_id: sessionId, ...(label ? { label } : {}) }),
  });
  if (!resp.ok) throw new Error(`Failed to fork session: ${resp.statusText}`);
  return resp.json();
}

export async function deleteSession(sessionId: string): Promise<{ ok: boolean; session_id: string }> {
  const resp = await fetchWithRetry(`${API_BASE}/sessions/${sessionId}`, { method: 'DELETE', headers: buildHeaders() });
  if (!resp.ok) throw new Error(`Failed to delete session: ${resp.statusText}`);
  return resp.json();
}

export async function summarizeSession(sessionId: string): Promise<{ session_id: string; message_count: number; user_turns: number; assistant_turns: number; first_user_message?: string; last_assistant_message?: string }> {
  const resp = await fetchWithRetry(`${API_BASE}/summarize`, {
    method: 'POST', headers: buildHeaders(),
    body: JSON.stringify({ session_id: sessionId }),
  });
  if (!resp.ok) throw new Error(`Failed to summarize session: ${resp.statusText}`);
  return resp.json();
}

export async function compactSession(sessionId: string, focus?: string): Promise<{ ok: boolean; session_id: string }> {
  const resp = await fetchWithRetry(`${API_BASE}/compact`, {
    method: 'POST', headers: buildHeaders(),
    body: JSON.stringify({ session_id: sessionId, ...(focus ? { focus } : {}) }),
  });
  if (!resp.ok) throw new Error(`Failed to compact session: ${resp.statusText}`);
  return resp.json();
}

// ── Doctor ─────────────────────────────────────────────────────────────
export interface DoctorReport {
  ok: boolean; engine_reachable: boolean; api_key_configured: boolean;
  approval_mode?: string; mcp_enabled?: boolean; fix?: string | null;
}

export async function fetchDoctor(): Promise<DoctorReport | null> {
  const resp = await fetchWithRetry(`${API_BASE}/doctor`);
  if (!resp.ok) return null;
  return resp.json() as Promise<DoctorReport>;
}
