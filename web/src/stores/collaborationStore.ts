'use client';

import { create } from 'zustand';

// ── Types ──────────────────────────────────────────────────────────────

export interface Collaborator {
  id: string;
  name: string;
  avatar?: string;
  isOnline: boolean;
  cursorPosition?: { line: number; column: number };
}

export interface CollaborationStoreState {
  /** Whether collaboration mode is active */
  isEnabled: boolean;
  /** Current room ID, null if not in a room */
  roomId: string | null;
  /** WebSocket / signalling connection status */
  connectionStatus: 'disconnected' | 'connecting' | 'connected';
  /** List of collaborators in the current room */
  collaborators: Collaborator[];
  /** Generated share link for the current session */
  shareLink: string | null;
  /** The current user's display name */
  userName: string;
}

export interface CollaborationStoreActions {
  enable: () => void;
  disable: () => void;
  joinRoom: (roomId: string) => void;
  leaveRoom: () => void;
  updateCursor: (position: { line: number; column: number }) => void;
  setConnectionStatus: (status: 'disconnected' | 'connecting' | 'connected') => void;
  setCollaborators: (collaborators: Collaborator[]) => void;
  addCollaborator: (collaborator: Collaborator) => void;
  removeCollaborator: (id: string) => void;
  updateCollaborator: (id: string, updates: Partial<Collaborator>) => void;
  setShareLink: (link: string | null) => void;
  setUserName: (name: string) => void;
}

export type CollaborationStore = CollaborationStoreState & CollaborationStoreActions;

// ── Initial State ──────────────────────────────────────────────────────

const initialState: CollaborationStoreState = {
  isEnabled: false,
  roomId: null,
  connectionStatus: 'disconnected',
  collaborators: [],
  shareLink: null,
  userName: typeof window !== 'undefined'
    ? localStorage.getItem('likecodex_user_name') || 'Anonymous'
    : 'Anonymous',
};

// ── Store ──────────────────────────────────────────────────────────────

export const useCollaborationStore = create<CollaborationStore>((set, get) => ({
  ...initialState,

  enable: () =>
    set({ isEnabled: true, connectionStatus: 'connecting' }),

  disable: () =>
    set({
      isEnabled: false,
      roomId: null,
      connectionStatus: 'disconnected',
      collaborators: [],
      shareLink: null,
    }),

  joinRoom: (roomId) =>
    set({
      roomId,
      isEnabled: true,
      connectionStatus: 'connecting',
    }),

  leaveRoom: () =>
    set({
      roomId: null,
      isEnabled: false,
      connectionStatus: 'disconnected',
      collaborators: [],
      shareLink: null,
    }),

  updateCursor: (position) =>
    set((state) => ({
      // In a real implementation this would broadcast to the room via WebSocket.
      // For now we update local state only.
      collaborators: state.collaborators.map((c, i) =>
        i === 0 ? { ...c, cursorPosition: position } : c
      ),
    })),

  setConnectionStatus: (status) => set({ connectionStatus: status }),

  setCollaborators: (collaborators) => set({ collaborators }),

  addCollaborator: (collaborator) =>
    set((state) => ({
      collaborators: state.collaborators.some((c) => c.id === collaborator.id)
        ? state.collaborators
        : [...state.collaborators, collaborator],
    })),

  removeCollaborator: (id) =>
    set((state) => ({
      collaborators: state.collaborators.filter((c) => c.id !== id),
    })),

  updateCollaborator: (id, updates) =>
    set((state) => ({
      collaborators: state.collaborators.map((c) =>
        c.id === id ? { ...c, ...updates } : c
      ),
    })),

  setShareLink: (link) => set({ shareLink: link }),

  setUserName: (name) => {
    if (typeof window !== 'undefined') {
      localStorage.setItem('likecodex_user_name', name);
    }
    set({ userName: name });
  },
}));
