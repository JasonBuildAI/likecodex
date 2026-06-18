import {
  Message,
  PermissionRequest,
  PlanStep,
  SessionSummary,
  Task,
  ToolCall,
} from './store';

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || '/api';

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

export async function createTask(prompt: string): Promise<Task> {
  const resp = await fetch(`${API_BASE}/tasks`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ prompt }),
  });
  if (!resp.ok) {
    throw new Error(`Failed to create task: ${resp.statusText}`);
  }
  const data = await resp.json();
  return data.task as Task;
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

export async function respondPermission(
  requestId: string,
  approved: boolean
): Promise<void> {
  const resp = await fetch(`${API_BASE}/permissions/${requestId}/respond`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ approved }),
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
  onPlanStep?: (step: PlanStep) => void;
  onToolCall?: (call: ToolCall) => void;
  onDiff?: (before: string, after: string) => void;
  onError?: (error: Error) => void;
};

export function subscribeEvents(handlers: EventHandler): () => void {
  const eventSource = new EventSource(`${API_BASE}/events`);

  eventSource.onmessage = (event) => {
    try {
      const data = JSON.parse(event.data) as RustEvent;
      const parsed = parseRustEvent(data);

      switch (parsed.kind) {
        case 'stream_chunk':
          if (parsed.content?.startsWith('[tool]')) {
            handlers.onMessage({
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
          handlers.onTaskCompleted?.(
            parsed.taskId || '',
            parsed.content === 'failed'
          );
          break;
        case 'stream_finished':
          handlers.onStreamFinished?.();
          break;
        case 'tool_call':
          if (parsed.call) {
            handlers.onToolCall?.(parsed.call);
            handlers.onMessage({
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
          handlers.onMessage({
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
        case 'plan':
          if (parsed.planStep) handlers.onPlanStep?.(parsed.planStep);
          if (parsed.content) {
            handlers.onMessage({
              id: `plan-${Date.now()}`,
              role: 'system',
              content: parsed.content,
              eventType: 'plan',
              timestamp: Date.now(),
            });
          }
          break;
        case 'error':
          handlers.onMessage({
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
