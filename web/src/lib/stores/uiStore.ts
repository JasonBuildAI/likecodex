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

  // ── Phase 7.7: Variable Watch Panel ──────────────────────────────
  // Future state for debugging variable watches:
  watchExpressions: string[];      // expressions the user wants to watch
  watchValues: Record<string, string>;  // expression -> evaluated value
  debugSessionActive: boolean;    // whether a DAP session is running
  // Actions:
  addWatchExpression: (expr: string) => void;
  removeWatchExpression: (expr: string) => void;
  updateWatchValues: (values: Record<string, string>) => void;
  setDebugSessionActive: (active: boolean) => void;

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

  // Phase 7.7: Variable Watch initial state
  watchExpressions: [],
  watchValues: {},
  debugSessionActive: false,

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

  // Phase 7.7: Variable Watch actions (stubs for future DAP integration)
  addWatchExpression: (expr) =>
    set((state) => ({
      watchExpressions: [...state.watchExpressions, expr],
    })),
  removeWatchExpression: (expr) =>
    set((state) => ({
      watchExpressions: state.watchExpressions.filter((e) => e !== expr),
    })),
  updateWatchValues: (values) => set({ watchValues: values }),
  setDebugSessionActive: (active) => set({ debugSessionActive: active }),
});
