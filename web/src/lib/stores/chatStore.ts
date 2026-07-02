import type { StateCreator } from 'zustand';
import type { Message, Task, PlanStep } from '../store';

// ── Chat slice types ───────────────────────────────────────────────────
export interface ChatSlice {
  messages: Message[];
  tasks: Task[];
  currentTaskId: string | null;
  isStreaming: boolean;
  planSteps: PlanStep[];
  reasoningContent: string;

  addMessage: (message: Message) => void;
  appendToLastMessage: (content: string) => void;
  setMessages: (messages: Message[]) => void;
  clearMessages: () => void;
  setTasks: (tasks: Task[]) => void;
  updateTask: (taskId: string, update: Partial<Task>) => void;
  setCurrentTaskId: (id: string | null) => void;
  setIsStreaming: (streaming: boolean) => void;
  setPlanSteps: (steps: PlanStep[]) => void;
  updatePlanStep: (id: string, update: Partial<PlanStep>) => void;
  appendReasoningContent: (content: string) => void;
  flushReasoningToLastMessage: () => void;
}

export const createChatSlice: StateCreator<ChatSlice> = (set) => ({
  messages: [],
  tasks: [],
  currentTaskId: null,
  isStreaming: false,
  planSteps: [],
  reasoningContent: '',

  addMessage: (message) =>
    set((state) => ({ messages: [...state.messages, message] })),
  appendToLastMessage: (content) =>
    set((state) => {
      const messages = [...state.messages];
      const last = messages[messages.length - 1];
      if (last && last.role === 'assistant') {
        messages[messages.length - 1] = { ...last, content: last.content + content };
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
  setMessages: (messages) => set({ messages }),
  clearMessages: () => set({ messages: [], currentTaskId: null }),
  setTasks: (tasks) => set({ tasks }),
  updateTask: (taskId, update) =>
    set((state) => ({
      tasks: state.tasks.map((t) => (t.id === taskId ? { ...t, ...update } : t)),
    })),
  setCurrentTaskId: (id) => set({ currentTaskId: id }),
  setIsStreaming: (streaming) => set({ isStreaming: streaming }),
  setPlanSteps: (steps) => set({ planSteps: steps }),
  updatePlanStep: (id, update) =>
    set((state) => ({
      planSteps: state.planSteps.map((s) => (s.id === id ? { ...s, ...update } : s)),
    })),
  appendReasoningContent: (content) =>
    set((state) => ({ reasoningContent: state.reasoningContent + content })),
  flushReasoningToLastMessage: () =>
    set((state) => {
      if (!state.reasoningContent) return {};
      const messages = state.messages.map((msg, idx) =>
        idx === state.messages.length - 1 && msg.role === 'assistant'
          ? { ...msg, reasoningContent: (msg.reasoningContent || '') + state.reasoningContent }
          : msg
      );
      return { messages, reasoningContent: '' };
    }),
});
