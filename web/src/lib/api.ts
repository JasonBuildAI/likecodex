import {
  type AskRequest,
  type Message,
  type PermissionRequest,
  type PlanStep,
  type SessionSummary,
  type Skill,
  type Task,
  type ToolCall,
  type SearchResult,
  type FileNode,
} from './store';

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || '/api';

// ── Helper: build headers ──────────────────────────────────────────────
function getStoreApiKey(): string {
  if (typeof window === 'undefined') return '';
  // try zustand store first, fallback to localStorage
  try {
    const { useAppStore } = require('./store');
    return useAppStore.getState().apiKey || localStorage.getItem('likecodex_api_key') || '';
  } catch {
    return localStorage.getItem('likecodex_api_key') || '';
  }
}

function getStoreModel(): string {
  if (typeof window === 'undefined') return '';
  try {
    const { useAppStore } = require('./store');
    return useAppStore.getState().selectedModel || localStorage.getItem('likecodex_model') || '';
  } catch {
    return localStorage.getItem('likecodex_model') || '';
  }
}

function buildHeaders(): Record<string, string> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  const apiKey = getStoreApiKey();
  const model = getStoreModel();
  if (apiKey) headers['X-LikeCodex-Api-Key'] = apiKey;
  if (model) headers['X-LikeCodex-Model'] = model;
  return headers;
}

// ── Helper: fetch with timeout + retry ─────────────────────────────────
async function fetchWithRetry(
  url: string,
  options: RequestInit = {},
  retries = 2,
  timeoutMs = 10000
): Promise<Response> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);

  const fetchOptions: RequestInit = {
    ...options,
    signal: controller.signal,
  };

  for (let attempt = 0; attempt <= retries; attempt++) {
    try {
      const resp = await fetch(url, fetchOptions);
      clearTimeout(timeout);
      return resp;
    } catch (err) {
      clearTimeout(timeout);
      if (attempt === retries) throw err;
      await new Promise((r) => setTimeout(r, 500 * (attempt + 1)));
    }
  }
  throw new Error('fetchWithRetry: unreachable');
}

// ── Event types ────────────────────────────────────────────────────────
export interface RustEvent {
  type: string;
  payload: Record<string, unknown>;
}

export function formatRetryMessage(reason: string, attempt: number, max: number): string {
  const label =
    reason === 'provider'
      ? 'Provider reconnect'
      : reason === 'stream_recovery'
        ? 'Stream interrupted'
        : 'Retrying';
  return `${label} — retrying (${attempt}/${max})`;
}

export function parseRustEvent(data: RustEvent): {
  kind: string;
  taskId?: string;
  content?: string;
  task?: Task;
  call?: ToolCall;
  permission?: PermissionRequest;
  planStep?: PlanStep;
  message?: string;
  retryAttempt?: number;
  retryMax?: number;
  retryReason?: string;
  checkpointLabel?: string;
  checkpointFiles?: string[];
  planModeActive?: boolean;
  planModePendingExit?: boolean;
  askRequest?: AskRequest;
  reasoningContent?: string;
} {
  const payload = data.payload || {};
  const taskId = payload.task_id as string | undefined;

  switch (data.type) {
    case 'stream_chunk':
      return { kind: 'stream_chunk', taskId, content: String(payload.content || '') };
    case 'task_started': {
      const task = payload as unknown as Task;
      return {
        kind: 'task_started',
        task: {
          id: (payload as { id?: string }).id || taskId || '',
          prompt: (payload as { description?: string }).description || '',
          status: 'running',
          outputs: [],
        },
      };
    }
    case 'task_completed': {
      const status = (payload as { status?: string }).status;
      return {
        kind: 'task_completed',
        taskId: (payload as { id?: string }).id,
        content: status === 'failed' ? 'failed' : 'completed',
      };
    }
    case 'stream_finished':
      return { kind: 'stream_finished', taskId };
    case 'stream_retrying':
      return {
        kind: 'retrying',
        taskId,
        content: String(payload.message || ''),
        retryAttempt: Number(payload.attempt || 1),
        retryMax: Number(payload.max || 1),
        retryReason: String(payload.reason || 'retry'),
      };
    case 'compaction_started':
      return {
        kind: 'compaction_started',
        taskId,
        content: String(payload.trigger || 'auto'),
      };
    case 'compaction_done':
      return {
        kind: 'compaction_done',
        taskId,
        content: String(payload.archive || payload.messages || ''),
      };
    case 'checkpoint_created':
      return {
        kind: 'checkpoint_created',
        taskId,
        content: String(payload.checkpoint_id || ''),
        checkpointLabel: String(payload.label || ''),
        checkpointFiles: Array.isArray(payload.files)
          ? payload.files.map((f) => String(f))
          : [],
      };
    case 'tool_call_requested': {
      const call = payload.call as Record<string, unknown> | undefined;
      return {
        kind: 'tool_call',
        taskId,
        call: call
          ? {
              id: String(call.id || ''),
              name: String(call.name || ''),
              arguments: (call.arguments as Record<string, unknown>) || {},
            }
          : undefined,
      };
    }
    case 'tool_call_completed':
      return {
        kind: 'tool_result',
        taskId,
        content: String((payload.result as { output?: string })?.output || payload.content || ''),
      };
    case 'permission_requested': {
      const req = payload.request as Record<string, unknown> | undefined;
      let parsed: Record<string, unknown> = {};
      try {
        parsed = JSON.parse(String(req?.description || '{}'));
      } catch {
        parsed = { description: req?.description };
      }
      return {
        kind: 'permission',
        taskId,
        permission: {
          requestId: String(parsed.request_id || req?.id || ''),
          tool: String(parsed.tool || req?.action_type || ''),
          description: String(req?.description || parsed.reason || ''),
          arguments: (parsed.arguments as Record<string, unknown>) || {},
        },
      };
    }
    case 'permission_responded': {
      const response = String(payload.response || '');
      const approved =
        response === 'allow' ||
        response === 'allow_once' ||
        response === 'AllowOnce' ||
        response === 'Allow';
      return {
        kind: 'permission_responded',
        taskId,
        permission: {
          requestId: String(payload.request_id || ''),
          tool: '',
          description: approved ? 'approved' : 'denied',
        },
      };
    }
    case 'plan_created':
    case 'plan_updated': {
      const steps = (payload.steps as Array<Record<string, unknown>>) || [];
      const step = steps[0];
      return {
        kind: 'plan',
        planStep: step
          ? {
              id: String(step.id || 'plan'),
              description: String(step.description || payload.reasoning || ''),
              status: String(step.status || 'pending'),
            }
          : undefined,
        content: String(payload.reasoning || ''),
      };
    }
    case 'plan_mode_changed':
      return {
        kind: 'plan_mode_changed',
        taskId,
        planModeActive: Boolean(payload.active),
        planModePendingExit: Boolean(payload.pending_exit),
        content: String(payload.reason || ''),
      };
    case 'ask_requested': {
      const questions = (payload.questions as AskRequest['questions']) || [];
      return {
        kind: 'ask',
        taskId,
        askRequest: {
          requestId: String(payload.request_id || ''),
          questions,
        },
      };
    }
    case 'ask_responded':
      return {
        kind: 'ask_responded',
        taskId,
        content: String(payload.request_id || ''),
      };
    case 'reasoning_delta':
      return {
        kind: 'reasoning_delta',
        taskId,
        reasoningContent: String(payload.content || ''),
      };
    case 'agent_activity': {
      return {
        kind: 'agent_activity',
        taskId,
        content: String(payload.description || ''),
        call: {
          id: '',
          name: String(payload.tool_name || ''),
          arguments: (payload.metadata as Record<string, unknown>) || {},
        },
      };
    }
    case 'agent_thinking':
      return {
        kind: 'agent_thinking',
        taskId,
        content: String(payload.content || ''),
      };
    case 'error':
      return {
        kind: 'error',
        taskId,
        message: String(payload.message || 'Unknown error'),
      };
    default:
      return { kind: data.type, taskId, content: JSON.stringify(payload) };
  }
}

// ── applyParsedEvent ───────────────────────────────────────────────────
function applyParsedEvent(
  parsed: ReturnType<typeof parseRustEvent>,
  handlers: EventHandler
) {
  switch (parsed.kind) {
    case 'retrying':
      handlers.onMessage?.({
        id: `retry-${Date.now()}`,
        role: 'system',
        content: formatRetryMessage(
          parsed.retryReason || 'retry',
          parsed.retryAttempt || 1,
          parsed.retryMax || 1
        ),
        eventType: 'retrying',
        timestamp: Date.now(),
      });
      break;
    case 'compaction_started':
      handlers.onMessage?.({
        id: `compact-start-${Date.now()}`,
        role: 'system',
        content: `Compacting conversation (${parsed.content || 'auto'})…`,
        eventType: 'compaction_started',
        timestamp: Date.now(),
      });
      break;
    case 'compaction_done':
      handlers.onMessage?.({
        id: `compact-done-${Date.now()}`,
        role: 'system',
        content: 'Context compacted.',
        eventType: 'compaction_done',
        timestamp: Date.now(),
      });
      break;
    case 'checkpoint_created': {
      const files = parsed.checkpointFiles?.length
        ? ` (${parsed.checkpointFiles.join(', ')})`
        : '';
      handlers.onMessage?.({
        id: `checkpoint-${Date.now()}`,
        role: 'system',
        content: `Checkpoint saved: ${parsed.checkpointLabel || 'write'} → ${parsed.content || '?'}${files}`,
        eventType: 'checkpoint',
        timestamp: Date.now(),
      });
      break;
    }
    case 'plan_mode_changed':
      handlers.onPlanModeChanged?.(
        Boolean(parsed.planModeActive),
        Boolean(parsed.planModePendingExit)
      );
      handlers.onMessage?.({
        id: `plan-mode-${Date.now()}`,
        role: 'system',
        content: parsed.planModeActive
          ? 'Plan mode enabled (read-only).'
          : 'Plan mode disabled.',
        eventType: 'plan_mode_changed',
        timestamp: Date.now(),
      });
      break;
    case 'ask':
      if (parsed.askRequest) handlers.onAsk?.(parsed.askRequest);
      break;
    case 'ask_responded':
      if (parsed.content) handlers.onAskResponded?.(parsed.content);
      break;
    case 'stream_chunk':
      if (parsed.content?.startsWith('[retrying]')) {
        handlers.onMessage?.({
          id: `retry-${Date.now()}`,
          role: 'system',
          content: parsed.content.replace(/^\[retrying\]\s*/, 'Stream interrupted — retrying: '),
          eventType: 'retrying',
          timestamp: Date.now(),
        });
      } else if (parsed.content?.startsWith('[usage]')) {
        handlers.onMessage?.({
          id: `usage-${Date.now()}`,
          role: 'system',
          content: parsed.content.replace(/^\[usage\]\s?/, ''),
          eventType: 'usage',
          timestamp: Date.now(),
        });
      } else if (parsed.content?.startsWith('[tool]')) {
        handlers.onMessage?.({
          id: `tool-${Date.now()}`,
          role: 'tool',
          content: parsed.content,
          eventType: 'stream_chunk',
          timestamp: Date.now(),
        });
      } else if (parsed.content) {
        handlers.onAppend?.(parsed.content);
      }
      break;
    case 'task_started':
      if (parsed.task) handlers.onTaskStarted?.(parsed.task);
      break;
    case 'task_completed':
      handlers.onTaskCompleted?.(parsed.taskId || '', parsed.content === 'failed');
      break;
    case 'stream_finished':
      handlers.onStreamFinished?.();
      break;
    case 'tool_call':
      if (parsed.call) {
        const isPartial = parsed.call.arguments?.partial === true;
        if (handlers.onUpsertToolDispatch) {
          handlers.onUpsertToolDispatch(parsed.call, isPartial);
          break;
        }
        if (isPartial) {
          handlers.onMessage?.({
            id: `tool-dispatch-${parsed.call.id || parsed.call.name}-${Date.now()}`,
            role: 'tool',
            content: `Calling ${parsed.call.name}...`,
            toolCalls: [parsed.call],
            eventType: 'tool_dispatch',
            timestamp: Date.now(),
          });
          break;
        }
        handlers.onToolCall?.(parsed.call);
        handlers.onMessage?.({
          id: `tool-call-${parsed.call.id}`,
          role: 'tool',
          content: `[tool] ${parsed.call.name}(${JSON.stringify(parsed.call.arguments)})`,
          toolCalls: [parsed.call],
          eventType: 'tool_call',
          timestamp: Date.now(),
        });
      }
      break;
    case 'tool_result':
      handlers.onMessage?.({
        id: `tool-result-${Date.now()}`,
        role: 'tool',
        content: parsed.content || '',
        eventType: 'tool_result',
        timestamp: Date.now(),
      });
      break;
    case 'permission':
      if (parsed.permission) handlers.onPermission?.(parsed.permission);
      break;
    case 'permission_responded':
      if (parsed.permission?.requestId) {
        handlers.onPermissionResponded?.(
          parsed.permission.requestId,
          parsed.permission.description === 'approved'
        );
      }
      break;
    case 'plan':
      if (parsed.planStep) handlers.onPlanStep?.(parsed.planStep);
      if (parsed.content) {
        handlers.onMessage?.({
          id: `plan-${Date.now()}`,
          role: 'system',
          content: parsed.content,
          eventType: 'plan',
          timestamp: Date.now(),
        });
      }
      break;
    case 'error':
      handlers.onMessage?.({
        id: `error-${Date.now()}`,
        role: 'system',
        content: `Error: ${parsed.message}`,
        eventType: 'error',
        timestamp: Date.now(),
      });
      break;
    case 'reasoning_delta':
      if (parsed.reasoningContent) {
        handlers.onReasoningDelta?.(parsed.reasoningContent);
      }
      break;
    case 'agent_activity':
      if (parsed.call) {
        handlers.onMessage?.({
          id: `agent-activity-${Date.now()}`,
          role: 'tool',
          content: parsed.content || `Agent: ${parsed.call.name}`,
          toolCalls: [parsed.call],
          eventType: 'agent_activity',
          timestamp: Date.now(),
        });
      }
      break;
    case 'agent_thinking':
      handlers.onMessage?.({
        id: `agent-thinking-${Date.now()}`,
        role: 'system',
        content: parsed.content || '',
        eventType: 'agent_thinking',
        timestamp: Date.now(),
      });
      break;
    default:
      break;
  }
}

// ── Event handler type ─────────────────────────────────────────────────
export type EventHandler = {
  onMessage: (msg: Message) => void;
  onAppend?: (content: string) => void;
  onTaskStarted?: (task: Task) => void;
  onTaskCompleted?: (taskId: string, failed: boolean) => void;
  onStreamFinished?: () => void;
  onPermission?: (req: PermissionRequest) => void;
  onPermissionResponded?: (requestId: string, approved: boolean) => void;
  onAsk?: (req: AskRequest) => void;
  onAskResponded?: (requestId: string) => void;
  onPlanModeChanged?: (active: boolean, pendingExit: boolean) => void;
  onPlanStep?: (step: PlanStep) => void;
  onToolCall?: (call: ToolCall) => void;
  onUpsertToolDispatch?: (call: ToolCall, partial: boolean) => void;
  onDiff?: (before: string, after: string) => void;
  onError?: (error: Error) => void;
  onReasoningDelta?: (content: string) => void;
};

// ── SSE stream reader shared helper ────────────────────────────────────
async function readSSEStream(
  reader: ReadableStreamDefaultReader<Uint8Array>,
  handlers: EventHandler
): Promise<void> {
  const decoder = new TextDecoder();
  let buffer = '';

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      const parts = buffer.split('\n\n');
      buffer = parts.pop() || '';
      for (const part of parts) {
        for (const line of part.split('\n')) {
          const trimmed = line.trim();
          if (!trimmed.startsWith('data: ')) continue;
          const data = trimmed.slice(6);
          if (data === '[DONE]') {
            handlers.onStreamFinished?.();
            return;
          }
          try {
            const event = JSON.parse(data) as RustEvent;
            applyParsedEvent(parseRustEvent(event), handlers);
          } catch {
            // ignore malformed chunks
          }
        }
      }
    }
  } finally {
    handlers.onStreamFinished?.();
  }
}

// ── Core: streamChat ───────────────────────────────────────────────────
export async function streamChat(
  prompt: string,
  sessionId: string | null,
  handlers: EventHandler,
  signal?: AbortSignal,
  agentMode: 'ask' | 'agent' | 'manual' = 'agent',
  activeFiles?: string[],
): Promise<void> {
  const resp = await fetch(`${API_BASE}/chat`, {
    method: 'POST',
    headers: buildHeaders(),
    body: JSON.stringify({
      prompt,
      agent_mode: agentMode,
      ...(sessionId ? { session_id: sessionId } : {}),
      ...(activeFiles && activeFiles.length > 0 ? { active_files: activeFiles } : {}),
    }),
    signal,
  });
  if (!resp.ok || !resp.body) {
    throw new Error(`Chat stream failed: ${resp.statusText}`);
  }

  handlers.onTaskStarted?.({
    id: sessionId || `chat-${Date.now()}`,
    prompt,
    status: 'running',
    outputs: [],
  });
  handlers.onMessage?.({
    id: `assistant-${Date.now()}`,
    role: 'assistant',
    content: '',
    timestamp: Date.now(),
  });

  await readSSEStream(resp.body.getReader(), handlers);
}

// ── Global events: subscribeEvents (fetch SSE, replaces EventSource) ───
export function subscribeEvents(handlers: EventHandler): () => void {
  let aborted = false;
  const abortController = new AbortController();

  async function connect() {
    while (!aborted) {
      try {
        const resp = await fetch(`${API_BASE}/events`, {
          headers: buildHeaders(),
          signal: abortController.signal,
        });
        if (!resp.ok || !resp.body) {
          if (!aborted) handlers.onError?.(new Error(`Events stream failed: ${resp.statusText}`));
          await new Promise((r) => setTimeout(r, 3000));
          continue;
        }
        await readSSEStream(resp.body.getReader(), handlers);
      } catch (err) {
        if (aborted) break;
        handlers.onError?.(err instanceof Error ? err : new Error(String(err)));
        await new Promise((r) => setTimeout(r, 3000));
      }
    }
  }

  connect();

  return () => {
    aborted = true;
    abortController.abort();
  };
}

// ── Task ───────────────────────────────────────────────────────────────
export async function createTask(prompt: string, sessionId?: string | null): Promise<Task> {
  const resp = await fetchWithRetry(`${API_BASE}/tasks`, {
    method: 'POST',
    headers: buildHeaders(),
    body: JSON.stringify({
      prompt,
      ...(sessionId ? { session_id: sessionId } : {}),
    }),
  });
  if (!resp.ok) throw new Error(`Failed to create task: ${resp.statusText}`);
  const data = await resp.json();
  return data.task as Task;
}

// ── Checkpoints ────────────────────────────────────────────────────────
export async function fetchCheckpoints(): Promise<
  Array<{ id: string; label: string; created_at: number; files: string[] }>
> {
  const resp = await fetchWithRetry(`${API_BASE}/checkpoints`);
  if (!resp.ok) return [];
  const data = await resp.json();
  return (data.checkpoints || []) as Array<{
    id: string;
    label: string;
    created_at: number;
    files: string[];
  }>;
}

export async function rewindCheckpoint(
  checkpointId: string | null,
  mode: 'code' | 'conversation' | 'both' | 'fork' | 'summarize_from' | 'summarize_upto' = 'code'
): Promise<Record<string, unknown>> {
  const resp = await fetchWithRetry(`${API_BASE}/checkpoints/rewind`, {
    method: 'POST',
    headers: buildHeaders(),
    body: JSON.stringify({ checkpoint_id: checkpointId, mode }),
  });
  return resp.json();
}

// ── Ask ────────────────────────────────────────────────────────────────
export async function respondAsk(
  requestId: string,
  answers: Array<{ questionIndex: number; selected: string[] }>
): Promise<void> {
  const resp = await fetchWithRetry(`${API_BASE}/ask/${requestId}/respond`, {
    method: 'POST',
    headers: buildHeaders(),
    body: JSON.stringify({ answers }),
  });
  if (!resp.ok) throw new Error(`Ask response failed: ${resp.statusText}`);
}

// ── Config & Metrics ───────────────────────────────────────────────────
export async function fetchConfig(): Promise<Record<string, unknown>> {
  const resp = await fetchWithRetry(`${API_BASE}/config`);
  if (!resp.ok) return {};
  return resp.json();
}

export async function fetchCacheMetrics(): Promise<{
  hit_rate?: number;
  recent_hit_rate?: number;
}> {
  const resp = await fetchWithRetry(`${API_BASE}/metrics`);
  if (!resp.ok) return {};
  return resp.json();
}

// ── Sessions ───────────────────────────────────────────────────────────
export async function fetchSessions(): Promise<SessionSummary[]> {
  const resp = await fetchWithRetry(`${API_BASE}/sessions`);
  if (!resp.ok) return [];
  const data = await resp.json();
  return (data.sessions || []) as SessionSummary[];
}

export interface DoctorReport {
  ok: boolean;
  engine_reachable: boolean;
  api_key_configured: boolean;
  approval_mode?: string;
  mcp_enabled?: boolean;
  fix?: string | null;
}

export async function fetchDoctor(): Promise<DoctorReport | null> {
  const resp = await fetchWithRetry(`${API_BASE}/doctor`);
  if (!resp.ok) return null;
  return resp.json() as Promise<DoctorReport>;
}

export async function fetchSessionEvents(sessionId: string): Promise<Message[]> {
  const resp = await fetchWithRetry(`${API_BASE}/sessions/${sessionId}/events`);
  if (!resp.ok) return [];
  const data = await resp.json();
  const events = (data.events || []) as Array<{
    event_type: string;
    content: string;
    timestamp?: number;
  }>;
  return events.map((event, index) => ({
    id: `${sessionId}-${index}`,
    role:
      event.event_type === 'user'
        ? 'user'
        : event.event_type === 'assistant'
          ? 'assistant'
          : event.event_type === 'tool_result'
            ? 'tool'
            : 'system',
    content: event.content,
    eventType: event.event_type,
    timestamp: event.timestamp || Date.now(),
  }));
}

// ── NEW: Session management ────────────────────────────────────────────
export async function createNewSession(cwd?: string): Promise<{ ok: boolean; session_id: string; cwd?: string }> {
  const resp = await fetchWithRetry(`${API_BASE}/new`, {
    method: 'POST',
    headers: buildHeaders(),
    body: JSON.stringify(cwd ? { cwd } : {}),
  });
  if (!resp.ok) throw new Error(`Failed to create session: ${resp.statusText}`);
  return resp.json();
}

export async function resumeSession(sessionId: string): Promise<{ ok: boolean; session_id: string }> {
  const resp = await fetchWithRetry(`${API_BASE}/resume`, {
    method: 'POST',
    headers: buildHeaders(),
    body: JSON.stringify({ session_id: sessionId }),
  });
  if (!resp.ok) throw new Error(`Failed to resume session: ${resp.statusText}`);
  return resp.json();
}

export async function forkSession(sessionId: string, label?: string): Promise<{ ok: boolean; session_id: string; forked_from: string }> {
  const resp = await fetchWithRetry(`${API_BASE}/fork`, {
    method: 'POST',
    headers: buildHeaders(),
    body: JSON.stringify({ session_id: sessionId, ...(label ? { label } : {}) }),
  });
  if (!resp.ok) throw new Error(`Failed to fork session: ${resp.statusText}`);
  return resp.json();
}

export async function deleteSession(sessionId: string): Promise<{ ok: boolean; session_id: string }> {
  const resp = await fetchWithRetry(`${API_BASE}/sessions/${sessionId}`, {
    method: 'DELETE',
    headers: buildHeaders(),
  });
  if (!resp.ok) throw new Error(`Failed to delete session: ${resp.statusText}`);
  return resp.json();
}

export async function summarizeSession(sessionId: string): Promise<{
  session_id: string;
  message_count: number;
  user_turns: number;
  assistant_turns: number;
  first_user_message?: string;
  last_assistant_message?: string;
}> {
  const resp = await fetchWithRetry(`${API_BASE}/summarize`, {
    method: 'POST',
    headers: buildHeaders(),
    body: JSON.stringify({ session_id: sessionId }),
  });
  if (!resp.ok) throw new Error(`Failed to summarize session: ${resp.statusText}`);
  return resp.json();
}

export async function compactSession(sessionId: string, focus?: string): Promise<{ ok: boolean; session_id: string }> {
  const resp = await fetchWithRetry(`${API_BASE}/compact`, {
    method: 'POST',
    headers: buildHeaders(),
    body: JSON.stringify({ session_id: sessionId, ...(focus ? { focus } : {}) }),
  });
  if (!resp.ok) throw new Error(`Failed to compact session: ${resp.statusText}`);
  return resp.json();
}

// ── NEW: Approval mode ─────────────────────────────────────────────────
export async function setApprovalMode(sessionId: string, mode: string): Promise<{ ok: boolean; session_id: string; mode: string }> {
  const resp = await fetchWithRetry(`${API_BASE}/tool-approval-mode`, {
    method: 'POST',
    headers: buildHeaders(),
    body: JSON.stringify({ session_id: sessionId, mode }),
  });
  if (!resp.ok) throw new Error(`Failed to set approval mode: ${resp.statusText}`);
  return resp.json();
}

// ── NEW: Skills ────────────────────────────────────────────────────────
export async function fetchSkills(): Promise<Skill[]> {
  const resp = await fetchWithRetry(`${API_BASE}/skills`);
  if (!resp.ok) return [];
  const data = await resp.json();
  return (data.skills || []) as Skill[];
}

// ── NEW: CodeGraph & Index search ──────────────────────────────────────
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

// ── NEW: Execute ───────────────────────────────────────────────────────
export async function executeCommand(command: string, workingDir?: string): Promise<{
  command: string;
  stdout: string;
  stderr: string;
  exit_code: number;
  timed_out: boolean;
  duration_ms: number;
}> {
  const resp = await fetchWithRetry(`${API_BASE}/execute`, {
    method: 'POST',
    headers: buildHeaders(),
    body: JSON.stringify({ command, working_dir: workingDir }),
  });
  if (!resp.ok) throw new Error(`Execute failed: ${resp.statusText}`);
  return resp.json();
}

// ── Permission ─────────────────────────────────────────────────────────
export async function respondPermission(
  requestId: string,
  approved: boolean,
  grantScope: 'once' | 'session' | 'prefix' = 'once'
): Promise<void> {
  const resp = await fetchWithRetry(`${API_BASE}/permissions/${requestId}/respond`, {
    method: 'POST',
    headers: buildHeaders(),
    body: JSON.stringify({ approved, grant_scope: grantScope }),
  });
  if (!resp.ok) throw new Error(`Permission response failed: ${resp.statusText}`);
}

// ── Workspace API (file tree & editor) ────────────────────────────────
export interface WorkspaceFile {
  path: string;
  name: string;
  content: string;
  size: number;
}

export interface InlineEditParams {
  code: string;
  instruction: string;
  language: string;
  full_content?: string;
  file_path?: string;
}

export interface InlineEditResult {
  original: string;
  modified: string;
  explanation: string;
  model: string;
  usage?: Record<string, unknown>;
}

export async function fetchWorkspaceTree(path: string = '.'): Promise<FileNode | null> {
  const resp = await fetchWithRetry(`/workspace/list?path=${encodeURIComponent(path)}`);
  if (!resp.ok) return null;
  return resp.json();
}

export async function fetchWorkspaceFile(path: string): Promise<WorkspaceFile | null> {
  const resp = await fetchWithRetry(`/workspace/read?path=${encodeURIComponent(path)}`);
  if (!resp.ok) return null;
  return resp.json();
}

export async function writeWorkspaceFile(path: string, content: string): Promise<boolean> {
  const resp = await fetchWithRetry(`/workspace/write`, {
    method: 'POST',
    headers: buildHeaders(),
    body: JSON.stringify({ path, content }),
  });
  return resp.ok;
}

export async function inlineEditCode(
  params: InlineEditParams,
  signal?: AbortSignal
): Promise<InlineEditResult | null> {
  const resp = await fetch(`/inline-edit`, {
    method: 'POST',
    headers: buildHeaders(),
    body: JSON.stringify(params),
    signal,
  });
  if (!resp.ok) return null;
  return resp.json();
}

// ── IDE Context Search API (@ mentions) ─────────────────────────────────
export interface ContextMentionResult {
  id: string;
  type: string;
  label: string;
  description?: string;
  icon: string;
  content: string;
  token_estimate: number;
  relevance_score: number;
}

export async function fetchContextMentions(query: string): Promise<ContextMentionResult[]> {
  const resp = await fetchWithRetry(
    `/api/ide/context/search?q=${encodeURIComponent(query)}`,
    {},
    1,
    5000
  );
  if (!resp.ok) return [];
  const data = await resp.json();
  return (data.results || []) as ContextMentionResult[];
}

// ── IDE LSP API (definition, references, hover) ────────────────────────
export interface LSPDefinition {
  uri?: string;
  range?: {
    start: { line: number; character: number };
    end: { line: number; character: number };
  };
}

export interface LSPHover {
  contents?: string | { language?: string; value?: string } | Array<{ language?: string; value?: string }>;
}

export async function lspDefinition(
  filePath: string,
  line: number,
  symbol: string
): Promise<{ definitions?: LSPDefinition[]; error?: string } | null> {
  const resp = await fetchWithRetry(`/api/ide/lsp/definition`, {
    method: 'POST',
    headers: buildHeaders(),
    body: JSON.stringify({ file_path: filePath, line, symbol }),
  }, 1, 10000);
  if (!resp.ok) return null;
  return resp.json();
}

export async function lspReferences(
  filePath: string,
  line: number,
  symbol: string
): Promise<{ references?: LSPDefinition[]; error?: string } | null> {
  const resp = await fetchWithRetry(`/api/ide/lsp/references`, {
    method: 'POST',
    headers: buildHeaders(),
    body: JSON.stringify({ file_path: filePath, line, symbol }),
  }, 1, 10000);
  if (!resp.ok) return null;
  return resp.json();
}

export async function lspHover(
  filePath: string,
  line: number,
  symbol: string
): Promise<{ hover?: LSPHover; error?: string } | null> {
  const resp = await fetchWithRetry(`/api/ide/lsp/hover`, {
    method: 'POST',
    headers: buildHeaders(),
    body: JSON.stringify({ file_path: filePath, line, symbol }),
  }, 1, 10000);
  if (!resp.ok) return null;
  return resp.json();
}

// ── Utility ────────────────────────────────────────────────────────────
export function parseToolCalls(toolCalls?: ToolCall[]): string {
  if (!toolCalls || toolCalls.length === 0) return '';
  return toolCalls.map((tc) => `[tool] ${tc.name}`).join('\n');
}

// ── IDE Git API (version control) ─────────────────────────────────────
export interface GitChangeData {
  path: string;
  changeType: string;
  staged: boolean;
  oldPath?: string;
}

export interface GitStatusData {
  changes: GitChangeData[];
  currentBranch: string;
  isRepo: boolean;
}

export interface GitCommitData {
  hash: string;
  shortHash: string;
  message: string;
  author: string;
  date: string;
}

export interface GitBranchData {
  name: string;
  current: boolean;
  remote: boolean;
  lastCommit: string;
}

export interface GitDiffData {
  path: string;
  diff: string;
  originalContent: string;
  modifiedContent: string;
}

export interface GitSearchResult {
  path: string;
  line: number;
  content: string;
}

export async function fetchGitStatus(): Promise<GitStatusData | null> {
  const resp = await fetchWithRetry(`/api/ide/git/status`, {}, 1, 10000);
  if (!resp.ok) return null;
  return resp.json();
}

export async function fetchGitDiff(path: string, staged: boolean = false): Promise<GitDiffData | null> {
  const resp = await fetchWithRetry(`/api/ide/git/diff`, {
    method: 'POST',
    headers: buildHeaders(),
    body: JSON.stringify({ path, staged }),
  }, 1, 10000);
  if (!resp.ok) return null;
  return resp.json();
}

export async function gitStageFile(path: string): Promise<boolean> {
  const resp = await fetchWithRetry(`/api/ide/git/stage`, {
    method: 'POST',
    headers: buildHeaders(),
    body: JSON.stringify({ path }),
  }, 1, 5000);
  return resp.ok;
}

export async function gitUnstageFile(path: string): Promise<boolean> {
  const resp = await fetchWithRetry(`/api/ide/git/unstage`, {
    method: 'POST',
    headers: buildHeaders(),
    body: JSON.stringify({ path }),
  }, 1, 5000);
  return resp.ok;
}

export async function gitStageAll(): Promise<boolean> {
  const resp = await fetchWithRetry(`/api/ide/git/stage-all`, {
    method: 'POST',
    headers: buildHeaders(),
  }, 1, 5000);
  return resp.ok;
}

export async function gitCommit(message: string): Promise<{ success: boolean; error?: string }> {
  const resp = await fetchWithRetry(`/api/ide/git/commit`, {
    method: 'POST',
    headers: buildHeaders(),
    body: JSON.stringify({ message }),
  }, 1, 10000);
  if (!resp.ok) return { success: false, error: `HTTP ${resp.status}` };
  const data = await resp.json();
  return { success: data.success, error: data.error };
}

export async function fetchGitLog(count: number = 50): Promise<GitCommitData[]> {
  const resp = await fetchWithRetry(`/api/ide/git/log?count=${count}`, {}, 1, 10000);
  if (!resp.ok) return [];
  const data = await resp.json();
  return data.commits || [];
}

export async function fetchGitBranches(): Promise<GitBranchData[]> {
  const resp = await fetchWithRetry(`/api/ide/git/branches`, {}, 1, 5000);
  if (!resp.ok) return [];
  const data = await resp.json();
  return data.branches || [];
}

export async function gitCheckoutBranch(name: string): Promise<boolean> {
  const resp = await fetchWithRetry(`/api/ide/git/checkout`, {
    method: 'POST',
    headers: buildHeaders(),
    body: JSON.stringify({ name }),
  }, 1, 10000);
  return resp.ok;
}

export async function gitCreateBranch(name: string): Promise<boolean> {
  const resp = await fetchWithRetry(`/api/ide/git/create-branch`, {
    method: 'POST',
    headers: buildHeaders(),
    body: JSON.stringify({ name }),
  }, 1, 5000);
  return resp.ok;
}

export async function gitDiscardChanges(path: string): Promise<boolean> {
  const resp = await fetchWithRetry(`/api/ide/git/discard`, {
    method: 'POST',
    headers: buildHeaders(),
    body: JSON.stringify({ path }),
  }, 1, 5000);
  return resp.ok;
}

export async function gitSearch(query: string): Promise<GitSearchResult[]> {
  const resp = await fetchWithRetry(`/api/ide/git/search?q=${encodeURIComponent(query)}`, {}, 1, 15000);
  if (!resp.ok) return [];
  const data = await resp.json();
  return data.results || [];
}
