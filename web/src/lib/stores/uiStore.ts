import type { StateCreator } from 'zustand';
import type { Toast, Skill, SearchResult } from '../store';

// ── UI slice types ───────────────────────────────────────────────────
export interface UISlice {
  toasts: Toast[];
  theme: 'dark' | 'light';
  sidebarOpen: boolean;
  commandPaletteOpen: boolean;
  settingsOpen: boolean;
  approvalMode: string;
  skills: Skill[];
  skillDetail: Skill | null;
  skillEditorOpen: boolean;
  skillSearchQuery: string;
  skillFilter: 'all' | 'builtin' | 'project' | 'home';
  codeGraphResults: SearchResult[];

  addToast: (toast: Omit<Toast, 'id'>) => void;
  removeToast: (id: string) => void;
  setTheme: (theme: 'dark' | 'light') => void;
  toggleSidebar: () => void;
  setSidebarOpen: (open: boolean) => void;
  setCommandPaletteOpen: (open: boolean) => void;
  setSettingsOpen: (open: boolean) => void;
  setApprovalMode: (mode: string) => void;
  setSkills: (skills: Skill[]) => void;
  setSkillDetail: (skill: Skill | null) => void;
  setSkillEditorOpen: (open: boolean) => void;
  setSkillSearchQuery: (query: string) => void;
  setSkillFilter: (filter: 'all' | 'builtin' | 'project' | 'home') => void;
  setCodeGraphResults: (results: SearchResult[]) => void;
}

export const createUISlice: StateCreator<UISlice> = (set) => ({
  toasts: [],
  theme: 'dark',
  sidebarOpen: true,
  commandPaletteOpen: false,
  settingsOpen: false,
  approvalMode: 'auto',
  skills: [],
  skillDetail: null,
  skillEditorOpen: false,
  skillSearchQuery: '',
  skillFilter: 'all' as const,
  codeGraphResults: [],

  addToast: (toast) =>
    set((state) => ({
      toasts: [...state.toasts, { ...toast, id: `toast-${Date.now()}-${Math.random().toString(36).slice(2, 7)}` }],
    })),
  removeToast: (id) =>
    set((state) => ({ toasts: state.toasts.filter((t) => t.id !== id) })),
  setTheme: (theme) => set({ theme }),
  toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),
  setSidebarOpen: (open) => set({ sidebarOpen: open }),
  setCommandPaletteOpen: (open) => set({ commandPaletteOpen: open }),
  setSettingsOpen: (open) => set({ settingsOpen: open }),
  setApprovalMode: (mode) => set({ approvalMode: mode }),
  setSkills: (skills) => set({ skills }),
  setSkillDetail: (skill) => set({ skillDetail: skill }),
  setSkillEditorOpen: (open) => set({ skillEditorOpen: open }),
  setSkillSearchQuery: (query) => set({ skillSearchQuery: query }),
  setSkillFilter: (filter) => set({ skillFilter: filter }),
  setCodeGraphResults: (results) => set({ codeGraphResults: results }),
});
