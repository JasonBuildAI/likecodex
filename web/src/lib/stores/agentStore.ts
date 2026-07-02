import type { StateCreator } from 'zustand';
import type { ToolCall, AgentMode, Conversation, ToolCallStreamItem, AgentViewMode } from '../store';

// ── Agent slice types ───────────────────────────────────────────────────
export interface AgentSlice {
  conversations: Conversation[];
  activeConversationId: string | null;
  isToolCallLogVisible: boolean;
  agentViewMode: AgentViewMode;
  activeToolCalls: ToolCallStreamItem[];
  agentMode: AgentMode;

  createConversation: (title: string, mode?: AgentMode) => void;
  setActiveConversation: (id: string | null) => void;
  toggleToolCallLog: () => void;
  setAgentViewMode: (mode: AgentViewMode) => void;
  addMessageToConversation: (conversationId: string, content: string) => void;
  upsertToolCallStatus: (item: ToolCallStreamItem) => void;
  clearActiveToolCalls: () => void;
  setAgentMode: (mode: AgentMode) => void;
}

export const createAgentSlice: StateCreator<AgentSlice> = (set) => ({
  conversations: [],
  activeConversationId: null,
  isToolCallLogVisible: false,
  agentViewMode: 'mixed',
  activeToolCalls: [],
  agentMode: 'agent',

  createConversation: (title, mode = 'agent') => {
    const newConversation: Conversation = {
      id: crypto.randomUUID(),
      title,
      mode,
      createdAt: new Date(),
      lastMessageAt: new Date(),
      messageCount: 0,
    };
    set((state) => ({
      conversations: [newConversation, ...state.conversations],
      activeConversationId: newConversation.id,
    }));
  },
  setActiveConversation: (id) => set({ activeConversationId: id }),
  toggleToolCallLog: () =>
    set((state) => ({ isToolCallLogVisible: !state.isToolCallLogVisible })),
  setAgentViewMode: (mode) => set({ agentViewMode: mode }),
  addMessageToConversation: (conversationId, _content) => {
    set((state) => ({
      conversations: state.conversations.map((conv) =>
        conv.id === conversationId
          ? { ...conv, lastMessageAt: new Date(), messageCount: conv.messageCount + 1 }
          : conv
      ),
    }));
  },
  upsertToolCallStatus: (item) => {
    set((state) => {
      const existing = state.activeToolCalls.findIndex(i => i.id === item.id);
      if (existing >= 0) {
        const updated = [...state.activeToolCalls];
        updated[existing] = item;
        return { activeToolCalls: updated };
      }
      return { activeToolCalls: [...state.activeToolCalls, item] };
    });
  },
  clearActiveToolCalls: () => set({ activeToolCalls: [] }),
  setAgentMode: (mode) => set({ agentMode: mode }),
});
