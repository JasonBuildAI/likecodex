'use client';

import { create } from 'zustand';

// ── Types ──────────────────────────────────────────────────────────────

export interface SessionInfo {
  id: string;
  name: string;
  status: 'active' | 'streaming' | 'error' | 'idle';
  created_at: number;
  message_count: number;
}

export interface SessionStoreState {
  sessions: SessionInfo[];
  activeSessionId: string | null;
  sessionOrder: string[]; // 拖拽排序后的 id 列表
  contextMenuSessionId: string | null;
  contextMenuPosition: { x: number; y: number } | null;
  renamingSessionId: string | null;
}

export interface SessionStoreActions {
  addSession: (session: SessionInfo) => void;
  removeSession: (id: string) => void;
  setActiveSession: (id: string) => void;
  renameSession: (id: string, name: string) => void;
  reorderSessions: (fromIndex: number, toIndex: number) => void;
  updateSessionStatus: (id: string, status: SessionInfo['status']) => void;
  openContextMenu: (id: string, x: number, y: number) => void;
  closeContextMenu: () => void;
  setRenamingSession: (id: string | null) => void;
}

export type SessionStore = SessionStoreState & SessionStoreActions;

// ── Initial State ──────────────────────────────────────────────────────

const initialState: SessionStoreState = {
  sessions: [],
  activeSessionId: null,
  sessionOrder: [],
  contextMenuSessionId: null,
  contextMenuPosition: null,
  renamingSessionId: null,
};

// ── Store ──────────────────────────────────────────────────────────────

export const useSessionStore = create<SessionStore>((set, get) => ({
  ...initialState,

  addSession: (session) =>
    set((s) => ({
      sessions: [...s.sessions, session],
      sessionOrder: [...s.sessionOrder, session.id],
    })),

  removeSession: (id) =>
    set((s) => {
      const nextSessions = s.sessions.filter((ses) => ses.id !== id);
      const nextOrder = s.sessionOrder.filter((oid) => oid !== id);
      const nextActive =
        s.activeSessionId === id
          ? nextOrder.length > 0
            ? nextOrder[nextOrder.length - 1]
            : null
          : s.activeSessionId;
      return {
        sessions: nextSessions,
        sessionOrder: nextOrder,
        activeSessionId: nextActive,
      };
    }),

  setActiveSession: (id) => set({ activeSessionId: id }),

  renameSession: (id, name) =>
    set((s) => ({
      sessions: s.sessions.map((ses) =>
        ses.id === id ? { ...ses, name } : ses
      ),
    })),

  reorderSessions: (fromIndex, toIndex) =>
    set((s) => {
      const order = [...s.sessionOrder];
      const [moved] = order.splice(fromIndex, 1);
      order.splice(toIndex, 0, moved);
      return { sessionOrder: order };
    }),

  updateSessionStatus: (id, status) =>
    set((s) => ({
      sessions: s.sessions.map((ses) =>
        ses.id === id ? { ...ses, status } : ses
      ),
    })),

  openContextMenu: (id, x, y) =>
    set({ contextMenuSessionId: id, contextMenuPosition: { x, y } }),

  closeContextMenu: () =>
    set({ contextMenuSessionId: null, contextMenuPosition: null }),

  setRenamingSession: (id) => set({ renamingSessionId: id }),
}));
