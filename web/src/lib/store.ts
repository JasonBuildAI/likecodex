import { create } from 'zustand';

export interface Message {
  id: string;
  role: 'user' | 'assistant' | 'tool' | 'system';
  content: string;
  toolCalls?: ToolCall[];
  eventType?: string;
  timestamp: number;
  reasoningContent?: string;
}

export interface ToolCall {
  id: string;
  name: string;
  arguments: Record<string, unknown>;
}

export interface Task {
  id: string;
  prompt: string;
  status: 'running' | 'completed' | 'failed';
  outputs: Message[];
}

export interface PermissionRequest {
  requestId: string;
  tool?: string;
  description: string;
  arguments?: Record<string, unknown>;
}

export interface AskRequest {
  requestId: string;
  questions: Array<{
    header: string;
    question: string;
    options: Array<{ label: string; description?: string }>;
    multiSelect?: boolean;
  }>;
}

export interface PlanStep {
  id: string;
  description: string;
  status: string;
}

export interface SessionSummary {
  id: string;
  created_at?: string;
  updated_at?: string;
  metadata?: Record<string, unknown>;
}

interface AppState {
  messages: Message[];
  tasks: Task[];
  currentTaskId: string | null;
  isStreaming: boolean;
  pendingPermissions: PermissionRequest[];
  pendingAskRequests: AskRequest[];
  planSteps: PlanStep[];
  activeDiff: { before: string; after: string } | null;
  sessions: SessionSummary[];
  config: Record<string, unknown>;
  cacheHitRate: number | null;
  currentSessionId: string | null;
  planModeActive: boolean;
  planModePendingExit: boolean;
  collaborationMode: 'normal' | 'plan' | 'goal';
  reasoningContent: string;
  setCacheHitRate: (rate: number | null) => void;
  addMessage: (message: Message) => void;
  appendToLastMessage: (content: string) => void;
  upsertToolDispatch: (call: ToolCall, partial: boolean) => void;
  setTasks: (tasks: Task[]) => void;
  updateTask: (taskId: string, update: Partial<Task>) => void;
  setCurrentTaskId: (id: string | null) => void;
  setIsStreaming: (streaming: boolean) => void;
  addPendingPermission: (req: PermissionRequest) => void;
  removePendingPermission: (requestId: string) => void;
  addPendingAsk: (req: AskRequest) => void;
  removePendingAsk: (requestId: string) => void;
  setPlanMode: (active: boolean, pendingExit?: boolean) => void;
  setCollaborationMode: (mode: 'normal' | 'plan' | 'goal') => void;
  setPlanSteps: (steps: PlanStep[]) => void;
  updatePlanStep: (id: string, update: Partial<PlanStep>) => void;
  setActiveDiff: (diff: { before: string; after: string } | null) => void;
  setSessions: (sessions: SessionSummary[]) => void;
  setConfig: (config: Record<string, unknown>) => void;
  clearMessages: () => void;
  setCurrentSessionId: (id: string | null) => void;
  setMessages: (messages: Message[]) => void;
  appendReasoningContent: (content: string) => void;
  flushReasoningToLastMessage: () => void;
}

export const useAppStore = create<AppState>((set) => ({
  messages: [],
  tasks: [],
  currentTaskId: null,
  isStreaming: false,
  pendingPermissions: [],
  pendingAskRequests: [],
  planSteps: [],
  activeDiff: null,
  sessions: [],
  config: {},
  cacheHitRate: null,
  currentSessionId: null,
  planModeActive: false,
  planModePendingExit: false,
  collaborationMode: 'normal',
  reasoningContent: '',
  addMessage: (message) =>
    set((state) => ({ messages: [...state.messages, message] })),
  appendToLastMessage: (content) =>
    set((state) => {
      const messages = [...state.messages];
      const last = messages[messages.length - 1];
      if (last && last.role === 'assistant') {
        last.content += content;
      } else {
        messages.push({
          id: `assistant-${Date.now()}`,
          role: 'assistant',
          content,
          timestamp: Date.now(),
        });
      }
      return { messages };
    }),
  appendReasoningContent: (content) =>
    set((state) => ({ reasoningContent: state.reasoningContent + content })),
  flushReasoningToLastMessage: () =>
    set((state) => {
      if (!state.reasoningContent) return state;
      const messages = [...state.messages];
      const last = messages[messages.length - 1];
      if (last && last.role === 'assistant') {
        last.reasoningContent = (last.reasoningContent || '') + state.reasoningContent;
      }
      return { messages, reasoningContent: '' };
    }),
  upsertToolDispatch: (call, partial) =>
    set((state) => {
      const messages = [...state.messages];
      const matchIndex = messages.findIndex(
        (msg) =>
          msg.eventType === 'tool_dispatch' &&
          ((call.id && msg.toolCalls?.[0]?.id === call.id) ||
            (!call.id && msg.toolCalls?.[0]?.name === call.name))
      );
      const content = partial
        ? `Calling ${call.name}...`
        : `[tool] ${call.name}(${JSON.stringify(call.arguments)})`;
      const next: Message = {
        id:
          matchIndex >= 0
            ? messages[matchIndex].id
            : `tool-dispatch-${call.id || call.name}-${Date.now()}`,
        role: 'tool',
        content,
        toolCalls: [call],
        eventType: partial ? 'tool_dispatch' : 'tool_call',
        timestamp: Date.now(),
      };
      if (matchIndex >= 0) {
        messages[matchIndex] = next;
      } else {
        messages.push(next);
      }
      return { messages };
    }),
  setTasks: (tasks) => set({ tasks }),
  updateTask: (taskId, update) =>
    set((state) => ({
      tasks: state.tasks.map((t) =>
        t.id === taskId ? { ...t, ...update } : t
      ),
    })),
  setCurrentTaskId: (id) => set({ currentTaskId: id }),
  setIsStreaming: (streaming) => set({ isStreaming: streaming }),
  addPendingPermission: (req) =>
    set((state) => ({
      pendingPermissions: [...state.pendingPermissions, req],
    })),
  removePendingPermission: (requestId) =>
    set((state) => ({
      pendingPermissions: state.pendingPermissions.filter(
        (p) => p.requestId !== requestId
      ),
    })),
  addPendingAsk: (req) =>
    set((state) => ({
      pendingAskRequests: [...state.pendingAskRequests, req],
    })),
  removePendingAsk: (requestId) =>
    set((state) => ({
      pendingAskRequests: state.pendingAskRequests.filter(
        (p) => p.requestId !== requestId
      ),
    })),
  setPlanMode: (active, pendingExit = false) =>
    set({ planModeActive: active, planModePendingExit: pendingExit }),
  setCollaborationMode: (mode) => set({ collaborationMode: mode }),
  setPlanSteps: (steps) => set({ planSteps: steps }),
  updatePlanStep: (id, update) =>
    set((state) => ({
      planSteps: state.planSteps.map((s) =>
        s.id === id ? { ...s, ...update } : s
      ),
    })),
  setActiveDiff: (diff) => set({ activeDiff: diff }),
  setSessions: (sessions) => set({ sessions }),
  setConfig: (config) => set({ config }),
  setCacheHitRate: (rate) => set({ cacheHitRate: rate }),
  clearMessages: () => set({ messages: [], currentTaskId: null }),
  setCurrentSessionId: (id) => set({ currentSessionId: id }),
  setMessages: (messages) => set({ messages }),
}));
