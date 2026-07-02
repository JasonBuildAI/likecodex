import { useAppStore } from '../store';

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || '/api';

// ── Helper: build headers ──────────────────────────────────────────────
export function getStoreApiKey(): string {
  if (typeof window === 'undefined') return '';
  try {
    return useAppStore.getState().apiKey || localStorage.getItem('likecodex_api_key') || '';
  } catch {
    return localStorage.getItem('likecodex_api_key') || '';
  }
}

export function getStoreModel(): string {
  if (typeof window === 'undefined') return '';
  try {
    return useAppStore.getState().selectedModel || localStorage.getItem('likecodex_model') || '';
  } catch {
    return localStorage.getItem('likecodex_model') || '';
  }
}

export function buildHeaders(): Record<string, string> {
  const headers: Record<string, string> = { 'Content-Type': 'application/json' };
  const apiKey = getStoreApiKey();
  const model = getStoreModel();
  if (apiKey) headers['X-LikeCodex-Api-Key'] = apiKey;
  if (model) headers['X-LikeCodex-Model'] = model;
  return headers;
}

// ── Helper: fetch with timeout + retry ─────────────────────────────────
export async function fetchWithRetry(
  url: string,
  options: RequestInit = {},
  retries = 2,
  timeoutMs = 10000
): Promise<Response> {
  for (let attempt = 0; attempt <= retries; attempt++) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), timeoutMs);
    try {
      const resp = await fetch(url, { ...options, signal: controller.signal });
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
import type { Message, Task, ToolCall, PermissionRequest, PlanStep, AskRequest } from '../store';

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
        kind: 'retrying', taskId, content: String(payload.message || ''),
        retryAttempt: Number(payload.attempt || 1), retryMax: Number(payload.max || 1),
        retryReason: String(payload.reason || 'retry'),
      };
    case 'compaction_started':
      return { kind: 'compaction_started', taskId, content: String(payload.trigger || 'auto') };
    case 'compaction_done':
      return { kind: 'compaction_done', taskId, content: String(payload.archive || payload.messages || '') };
    case 'checkpoint_created':
      return {
        kind: 'checkpoint_created', taskId, content: String(payload.checkpoint_id || ''),
        checkpointLabel: String(payload.label || ''),
        checkpointFiles: Array.isArray(payload.files) ? payload.files.map((f) => String(f)) : [],
      };
    case 'tool_call_requested': {
      const call = payload.call as Record<string, unknown> | undefined;
      return {
        kind: 'tool_call', taskId,
        call: call ? { id: String(call.id || ''), name: String(call.name || ''), arguments: (call.arguments as Record<string, unknown>) || {} } : undefined,
      };
    }
    case 'tool_call_completed':
      return { kind: 'tool_result', taskId, content: String((payload.result as { output?: string })?.output || payload.content || '') };
    case 'tool_executing': {
      const callData = payload as Record<string, unknown>;
      return {
        kind: 'tool_executing', taskId,
        call: { id: String(callData.tool_call_id || ''), name: String(callData.tool_name || ''), arguments: (callData.arguments as Record<string, unknown>) || {} },
        content: String(callData.started_at || ''),
      };
    }
    case 'permission_requested': {
      const req = payload.request as Record<string, unknown> | undefined;
      let parsed: Record<string, unknown> = {};
      try { parsed = JSON.parse(String(req?.description || '{}')); } catch { parsed = { description: req?.description }; }
      return {
        kind: 'permission', taskId,
        permission: { requestId: String(parsed.request_id || req?.id || ''), tool: String(parsed.tool || req?.action_type || ''), description: String(req?.description || parsed.reason || ''), arguments: (parsed.arguments as Record<string, unknown>) || {} },
      };
    }
    case 'permission_responded': {
      const response = String(payload.response || '');
      const approved = response === 'allow' || response === 'allow_once' || response === 'AllowOnce' || response === 'Allow';
      return { kind: 'permission_responded', taskId, permission: { requestId: String(payload.request_id || ''), tool: '', description: approved ? 'approved' : 'denied' } };
    }
    case 'plan_created':
    case 'plan_updated': {
      const steps = (payload.steps as Array<Record<string, unknown>>) || [];
      const step = steps[0];
      return { kind: 'plan', planStep: step ? { id: String(step.id || 'plan'), description: String(step.description || payload.reasoning || ''), status: String(step.status || 'pending') } : undefined, content: String(payload.reasoning || '') };
    }
    case 'plan_mode_changed':
      return { kind: 'plan_mode_changed', taskId, planModeActive: Boolean(payload.active), planModePendingExit: Boolean(payload.pending_exit), content: String(payload.reason || '') };
    case 'ask_requested': {
      const questions = (payload.questions as AskRequest['questions']) || [];
      return { kind: 'ask', taskId, askRequest: { requestId: String(payload.request_id || ''), questions } };
    }
    case 'ask_responded':
      return { kind: 'ask_responded', taskId, content: String(payload.request_id || '') };
    case 'reasoning_delta':
      return { kind: 'reasoning_delta', taskId, reasoningContent: String(payload.content || '') };
    case 'agent_activity':
      return { kind: 'agent_activity', taskId, content: String(payload.description || ''), call: { id: '', name: String(payload.tool_name || ''), arguments: (payload.metadata as Record<string, unknown>) || {} } };
    case 'agent_thinking':
      return { kind: 'agent_thinking', taskId, content: String(payload.content || '') };
    case 'error':
      return { kind: 'error', taskId, message: String(payload.message || 'Unknown error') };
    default:
      return { kind: data.type, taskId, content: JSON.stringify(payload) };
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
  onToolCallStart?: (call: ToolCall) => void;
  onToolCallComplete?: (call: ToolCall, result: string) => void;
};

// ── applyParsedEvent ───────────────────────────────────────────────────
function applyParsedEvent(
  parsed: ReturnType<typeof parseRustEvent>,
  handlers: EventHandler
) {
  switch (parsed.kind) {
    case 'retrying':
      handlers.onMessage?.({
        id: `retry-${Date.now()}`, role: 'system',
        content: formatRetryMessage(parsed.retryReason || 'retry', parsed.retryAttempt || 1, parsed.retryMax || 1),
        eventType: 'retrying', timestamp: Date.now(),
      });
      break;
    case 'compaction_started':
      handlers.onMessage?.({ id: `compact-start-${Date.now()}`, role: 'system', content: `Compacting conversation (${parsed.content || 'auto'})…`, eventType: 'compaction_started', timestamp: Date.now() });
      break;
    case 'compaction_done':
      handlers.onMessage?.({ id: `compact-done-${Date.now()}`, role: 'system', content: 'Context compacted.', eventType: 'compaction_done', timestamp: Date.now() });
      break;
    case 'checkpoint_created': {
      const files = parsed.checkpointFiles?.length ? ` (${parsed.checkpointFiles.join(', ')})` : '';
      handlers.onMessage?.({ id: `checkpoint-${Date.now()}`, role: 'system', content: `Checkpoint saved: ${parsed.checkpointLabel || 'write'} → ${parsed.content || '?'}${files}`, eventType: 'checkpoint', timestamp: Date.now() });
      break;
    }
    case 'plan_mode_changed':
      handlers.onPlanModeChanged?.(Boolean(parsed.planModeActive), Boolean(parsed.planModePendingExit));
      handlers.onMessage?.({ id: `plan-mode-${Date.now()}`, role: 'system', content: parsed.planModeActive ? 'Plan mode enabled (read-only).' : 'Plan mode disabled.', eventType: 'plan_mode_changed', timestamp: Date.now() });
      break;
    case 'ask':
      if (parsed.askRequest) handlers.onAsk?.(parsed.askRequest);
      break;
    case 'ask_responded':
      if (parsed.content) handlers.onAskResponded?.(parsed.content);
      break;
    case 'stream_chunk':
      if (parsed.content?.startsWith('[retrying]')) {
        handlers.onMessage?.({ id: `retry-${Date.now()}`, role: 'system', content: parsed.content.replace(/^\[retrying\]\s*/, 'Stream interrupted — retrying: '), eventType: 'retrying', timestamp: Date.now() });
      } else if (parsed.content?.startsWith('[usage]')) {
        handlers.onMessage?.({ id: `usage-${Date.now()}`, role: 'system', content: parsed.content.replace(/^\[usage\]\s?/, ''), eventType: 'usage', timestamp: Date.now() });
      } else if (parsed.content?.startsWith('[tool]')) {
        handlers.onMessage?.({ id: `tool-${Date.now()}`, role: 'tool', content: parsed.content, eventType: 'stream_chunk', timestamp: Date.now() });
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
          handlers.onMessage?.({ id: `tool-dispatch-${parsed.call.id || parsed.call.name}-${Date.now()}`, role: 'tool', content: `Calling ${parsed.call.name}...`, toolCalls: [parsed.call], eventType: 'tool_dispatch', timestamp: Date.now() });
          break;
        }
        handlers.onToolCall?.(parsed.call);
        handlers.onMessage?.({ id: `tool-call-${parsed.call.id}`, role: 'tool', content: `[tool] ${parsed.call.name}(${JSON.stringify(parsed.call.arguments)})`, toolCalls: [parsed.call], eventType: 'tool_call', timestamp: Date.now() });
      }
      break;
    case 'tool_result':
      handlers.onMessage?.({ id: `tool-result-${Date.now()}`, role: 'tool', content: parsed.content || '', eventType: 'tool_result', timestamp: Date.now() });
      try {
        const state = useAppStore.getState();
        const activeCalls = state.activeToolCalls;
        if (activeCalls.length > 0) {
          const lastRunning = [...activeCalls].reverse().find(c => c.status === 'running');
          if (lastRunning) {
            state.upsertToolCallStatus({ ...lastRunning, status: parsed.content?.toLowerCase().includes('error') ? 'error' : 'completed', completedAt: Date.now(), result: parsed.content });
          }
        }
      } catch { /* store not available */ }
      break;
    case 'permission':
      if (parsed.permission) handlers.onPermission?.(parsed.permission);
      break;
    case 'permission_responded':
      if (parsed.permission?.requestId) {
        handlers.onPermissionResponded?.(parsed.permission.requestId, parsed.permission.description === 'approved');
      }
      break;
    case 'plan':
      if (parsed.planStep) handlers.onPlanStep?.(parsed.planStep);
      if (parsed.content) {
        handlers.onMessage?.({ id: `plan-${Date.now()}`, role: 'system', content: parsed.content, eventType: 'plan', timestamp: Date.now() });
      }
      break;
    case 'error':
      handlers.onMessage?.({ id: `error-${Date.now()}`, role: 'system', content: `Error: ${parsed.message}`, eventType: 'error', timestamp: Date.now() });
      break;
    case 'reasoning_delta':
      if (parsed.reasoningContent) {
        handlers.onReasoningDelta?.(parsed.reasoningContent);
        try { useAppStore.getState().appendReasoningContent(parsed.reasoningContent); } catch { /* store not available */ }
      }
      break;
    case 'agent_activity':
      if (parsed.call) {
        handlers.onMessage?.({ id: `agent-activity-${Date.now()}`, role: 'tool', content: parsed.content || `Agent: ${parsed.call.name}`, toolCalls: [parsed.call], eventType: 'agent_activity', timestamp: Date.now() });
      }
      break;
    case 'agent_thinking':
      handlers.onMessage?.({ id: `agent-thinking-${Date.now()}`, role: 'system', content: parsed.content || '', eventType: 'agent_thinking', timestamp: Date.now() });
      break;
    case 'tool_executing':
      if (parsed.call) {
        handlers.onToolCallStart?.(parsed.call);
        try {
          const state = useAppStore.getState();
          state.upsertToolCallStatus({ id: parsed.call.id || `${parsed.call.name}-${Date.now()}`, call: parsed.call, status: 'running', startedAt: Date.now() });
        } catch { /* store not available */ }
      }
      break;
    default:
      break;
  }
}

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
          if (data === '[DONE]') { handlers.onStreamFinished?.(); return; }
          try {
            const event = JSON.parse(data) as RustEvent;
            applyParsedEvent(parseRustEvent(event), handlers);
          } catch { /* ignore malformed chunks */ }
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
  skillName?: string,
): Promise<void> {
  const resp = await fetch(`${API_BASE}/chat`, {
    method: 'POST',
    headers: buildHeaders(),
    body: JSON.stringify({
      prompt, agent_mode: agentMode,
      ...(sessionId ? { session_id: sessionId } : {}),
      ...(activeFiles && activeFiles.length > 0 ? { active_files: activeFiles } : {}),
      ...(skillName ? { skill: skillName } : {}),
    }),
    signal,
  });
  if (!resp.ok || !resp.body) throw new Error(`Chat stream failed: ${resp.statusText}`);
  handlers.onTaskStarted?.({ id: sessionId || `chat-${Date.now()}`, prompt, status: 'running', outputs: [] });
  handlers.onMessage?.({ id: `assistant-${Date.now()}`, role: 'assistant', content: '', timestamp: Date.now() });
  await readSSEStream(resp.body.getReader(), handlers);
}

// ── Global events: subscribeEvents ─────────────────────────────────────
export function subscribeEvents(handlers: EventHandler): () => void {
  let aborted = false;
  const abortController = new AbortController();
  async function connect() {
    let retryCount = 0;
    const MAX_RETRIES = 10;
    while (!aborted && retryCount < MAX_RETRIES) {
      try {
        retryCount = 0;
        const resp = await fetch(`${API_BASE}/events`, { headers: buildHeaders(), signal: abortController.signal });
        if (!resp.ok || !resp.body) {
          if (!aborted) handlers.onError?.(new Error(`Events stream failed: ${resp.statusText}`));
          retryCount++;
          await new Promise((r) => setTimeout(r, Math.min(1000 * Math.pow(2, retryCount), 30000)));
          continue;
        }
        await readSSEStream(resp.body.getReader(), handlers);
      } catch (err) {
        if (aborted) break;
        retryCount++;
        handlers.onError?.(err instanceof Error ? err : new Error(String(err)));
        await new Promise((r) => setTimeout(r, Math.min(1000 * Math.pow(2, retryCount), 30000)));
      }
    }
  }
  connect();
  return () => { aborted = true; abortController.abort(); };
}
