import { create } from 'zustand';

// ── Types ──────────────────────────────────────────────────────────────
export type AgentMode = 'ask' | 'agent' | 'manual';

export interface Conversation {
  id: string;
  title: string;
  mode: AgentMode;
  createdAt: Date;
  lastMessageAt: Date;
  messageCount: number;
}

interface AgentState {
  // 当前模式
  currentMode: AgentMode;

  // 对话列表
  conversations: Conversation[];
  activeConversationId: string | null;

  // UI 状态
  isSidebarOpen: boolean;
  isToolCallLogVisible: boolean;

  // Actions
  switchMode: (mode: AgentMode) => void;
  createConversation: (title: string, mode?: AgentMode) => void;
  setActiveConversation: (id: string | null) => void;
  toggleSidebar: () => void;
  toggleToolCallLog: () => void;
  addMessageToConversation: (conversationId: string, content: string) => void;
}

// ── Store ──────────────────────────────────────────────────────────────
export const useAgentStore = create<AgentState>((set, get) => ({
  currentMode: 'agent',
  conversations: [],
  activeConversationId: null,
  isSidebarOpen: true,
  isToolCallLogVisible: false,

  switchMode: (mode) => set({ currentMode: mode }),

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
      currentMode: mode,
    }));
  },

  setActiveConversation: (id) => set({ activeConversationId: id }),

  toggleSidebar: () =>
    set((state) => ({ isSidebarOpen: !state.isSidebarOpen })),

  toggleToolCallLog: () =>
    set((state) => ({ isToolCallLogVisible: !state.isToolCallLogVisible })),

  addMessageToConversation: (conversationId, _content) => {
    set((state) => ({
      conversations: state.conversations.map((conv) =>
        conv.id === conversationId
          ? { ...conv, lastMessageAt: new Date(), messageCount: conv.messageCount + 1 }
          : conv
      ),
    }));
  },
}));
