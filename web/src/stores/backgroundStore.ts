'use client';

import { create } from 'zustand';

// ── Types ──────────────────────────────────────────────────────────────

export interface BackgroundTask {
  id: string;
  name: string;
  description: string;
  status: 'pending' | 'running' | 'paused' | 'completed' | 'failed' | 'cancelled';
  progress: number;
  created_at: number;
  started_at?: number;
  completed_at?: number;
  result?: unknown;
  error?: string;
}

export interface BackgroundStoreState {
  tasks: BackgroundTask[];
  isPanelOpen: boolean;

  addTask: (task: BackgroundTask) => void;
  updateTask: (id: string, updates: Partial<BackgroundTask>) => void;
  removeTask: (id: string) => void;
  setPanelOpen: (open: boolean) => void;
  cancelTask: (id: string) => void;
  pauseTask: (id: string) => void;
  resumeTask: (id: string) => void;
}

// ── Initial state factory ──────────────────────────────────────────────

const initialState = (): Pick<BackgroundStoreState, 'tasks' | 'isPanelOpen'> => ({
  tasks: [],
  isPanelOpen: false,
});

// ── Store ──────────────────────────────────────────────────────────────

export const useBackgroundStore = create<BackgroundStoreState>((set) => ({
  ...initialState(),

  addTask: (task) =>
    set((state) => ({
      tasks: [...state.tasks, task],
    })),

  updateTask: (id, updates) =>
    set((state) => ({
      tasks: state.tasks.map((t) => (t.id === id ? { ...t, ...updates } : t)),
    })),

  removeTask: (id) =>
    set((state) => ({
      tasks: state.tasks.filter((t) => t.id !== id),
    })),

  setPanelOpen: (open) => set({ isPanelOpen: open }),

  cancelTask: (id) =>
    set((state) => ({
      tasks: state.tasks.map((t) =>
        t.id === id ? { ...t, status: 'cancelled' as const, completed_at: Date.now() } : t,
      ),
    })),

  pauseTask: (id) =>
    set((state) => ({
      tasks: state.tasks.map((t) =>
        t.id === id ? { ...t, status: 'paused' as const } : t,
      ),
    })),

  resumeTask: (id) =>
    set((state) => ({
      tasks: state.tasks.map((t) =>
        t.id === id ? { ...t, status: 'running' as const } : t,
      ),
    })),
}));
