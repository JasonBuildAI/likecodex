import {
  AskRequest,
  Message,
  PermissionRequest,
  PlanStep,
  SessionSummary,
  Task,
  ToolCall,
} from './store';

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || '/api';

export function formatRetryMessage(reason: string, attempt: number, max: number): string {
  const label =
    reason === 'provider'
      ? 'Provider reconnect'
      : reason === 'stream_recovery'
        ? 'Stream interrupted'
        : 'Retrying';
  return `${label} — retrying (${attempt}/${max})`;
}

export interface RustEvent {
  type: string;
  payload: Record<string, unknown>;
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

export async function createTask(prompt: string, sessionId?: string | null): Promise<Task> {
  const resp = await fetch(`${API_BASE}/tasks`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      prompt,
      ...(sessionId ? { session_id: sessionId } : {}),
    }),
  });
  if (!resp.ok) {
    throw new Error(`Failed to create task: ${resp.statusText}`);
  }
  const data = await resp.json();
  return data.task as Task;
}

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
    default:
      break;
  }
}

/** Stream a chat turn via POST /chat SSE (primary Web path). */
export async function streamChat(
  prompt: string,
  sessionId: string | null,
  handlers: EventHandler,
  signal?: AbortSignal
): Promise<void> {
  const resp = await fetch(`${API_BASE}/chat`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      prompt,
      ...(sessionId ? { session_id: sessionId } : {}),
    }),
    signal,
  });
  if (!resp.ok || !resp.body) {
    throw new Error(`Chat stream failed: ${resp.statusText}`);
  }

  const reader = resp.body.getReader();
  const decoder = new TextDecoder();
  let buffer = '';

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

export async function fetchCheckpoints(): Promise<
  Array<{ id: string; label: string; created_at: number; files: string[] }>
> {
  const resp = await fetch(`${API_BASE}/checkpoints`);
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
  const resp = await fetch(`${API_BASE}/checkpoints/rewind`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ checkpoint_id: checkpointId, mode }),
  });
  return resp.json();
}

export async function respondAsk(
  requestId: string,
  answers: Array<{ questionIndex: number; selected: string[] }>
): Promise<void> {
  const resp = await fetch(`${API_BASE}/ask/${requestId}/respond`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ answers }),
  });
  if (!resp.ok) {
    throw new Error(`Ask response failed: ${resp.statusText}`);
  }
}

export async function fetchConfig(): Promise<Record<string, unknown>> {
  const resp = await fetch(`${API_BASE}/config`);
  if (!resp.ok) return {};
  return resp.json();
}

export async function fetchCacheMetrics(): Promise<{
  hit_rate?: number;
  recent_hit_rate?: number;
}> {
  const resp = await fetch(`${API_BASE}/metrics`);
  if (!resp.ok) return {};
  return resp.json();
}

export async function fetchSessions(): Promise<SessionSummary[]> {
  const resp = await fetch(`${API_BASE}/sessions`);
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
  const resp = await fetch(`${API_BASE}/doctor`);
  if (!resp.ok) return null;
  return resp.json() as Promise<DoctorReport>;
}

export async function fetchSessionEvents(sessionId: string): Promise<Message[]> {
  const resp = await fetch(`${API_BASE}/sessions/${sessionId}/events`);
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

export async function respondPermission(
  requestId: string,
  approved: boolean,
  grantScope: 'once' | 'session' | 'prefix' = 'once'
): Promise<void> {
  const resp = await fetch(`${API_BASE}/permissions/${requestId}/respond`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ approved, grant_scope: grantScope }),
  });
  if (!resp.ok) {
    throw new Error(`Permission response failed: ${resp.statusText}`);
  }
}

export type EventHandler = {
  onMessage: (msg: Message) => void;
  onAppend?: (content: string) => void;
  onTaskStarted?: (task: Task) => void;
  onTaskCompleted?: (taskId: string, failed: boolean) => void;
  onStreamFinished?: () => void;
  onPermission?: (req: PermissionRequest) => void;
  onPermissionResponded?: (requestId: string, approved: boolean) => void;
  onAsk?: (req: AskRequest) => void;
  onPlanModeChanged?: (active: boolean, pendingExit: boolean) => void;
  onPlanStep?: (step: PlanStep) => void;
  onToolCall?: (call: ToolCall) => void;
  onUpsertToolDispatch?: (call: ToolCall, partial: boolean) => void;
  onDiff?: (before: string, after: string) => void;
  onError?: (error: Error) => void;
};

export function subscribeEvents(handlers: EventHandler): () => void {
  const eventSource = new EventSource(`${API_BASE}/events`);

  eventSource.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data) as RustEvent;
      applyParsedEvent(parseRustEvent(data), handlers);
    } catch {
      // Ignore malformed events
    }
  };

  eventSource.onerror = () => {
    handlers.onError?.(new Error('EventSource error'));
  };

  return () => eventSource.close();
}

export function parseToolCalls(toolCalls?: ToolCall[]): string {
  if (!toolCalls || toolCalls.length === 0) return '';
  return toolCalls.map((tc) => `[tool] ${tc.name}`).join('\n');
}
