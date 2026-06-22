import { create } from 'zustand';

// ── Core types ─────────────────────────────────────────────────────────
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

// ── NEW types ──────────────────────────────────────────────────────────
export interface Toast {
  id: string;
  type: 'info' | 'success' | 'warning' | 'error';
  message: string;
  duration?: number;
}

export interface Skill {
  name: string;
  description: string;
  source?: string;
}

export interface SearchResult {
  name: string;
  kind: string;
  path: string;
  line?: number;
}

// ── File tree types ─────────────────────────────────────────────────────
export interface FileNode {
  name: string;
  path: string;
  type: 'file' | 'directory';
  size?: number;
  children?: FileNode[];
}

export interface OpenFile {
  path: string;
  name: string;
  content: string;
  savedContent: string;
  modified: boolean;
}

// ── App state ──────────────────────────────────────────────────────────
interface AppState {
  // Core
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
  collaborationMode: 'normal' | "plan" | "goal";
  agentMode: 'ask' | 'agent' | 'manual';
  
  // NEW: UI state
  toasts: Toast[];
  theme: 'dark' | 'light';
  sidebarOpen: boolean;
  commandPaletteOpen: boolean;
  approvalMode: string;
  skills: Skill[];
  codeGraphResults: SearchResult[];

  // ── File tree & editor state ──────────────────────────────
  fileTree: FileNode | null;
  fileTreeLoading: boolean;
  openFiles: OpenFile[];
  activeFilePath: string | null;

  // UI settings
  settingsOpen: boolean;
  apiKey: string;
  selectedModel: string;
  reasoningContent: string;

  // Core actions
  setSettingsOpen: (open: boolean) => void;
  setApiKey: (key: string) => void;
  setSelectedModel: (model: string) => void;
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
  setAgentMode: (mode: 'ask' | 'agent' | 'manual') => void;
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

  // NEW actions
  addToast: (toast: Omit<Toast, 'id'>) => void;
  removeToast: (id: string) => void;
  setTheme: (theme: 'dark' | 'light') => void;
  toggleSidebar: () => void;
  setSidebarOpen: (open: boolean) => void;
  setCommandPaletteOpen: (open: boolean) => void;
  setApprovalMode: (mode: string) => void;
  setSkills: (skills: Skill[]) => void;
  setCodeGraphResults: (results: SearchResult[]) => void;

  // ── File tree & editor actions ─────────────────────────────
  setFileTree: (tree: FileNode | null) => void;
  setFileTreeLoading: (loading: boolean) => void;
  openFile: (file: { path: string; name: string; content: string }) => void;
  closeFile: (path: string) => void;
  setActiveFile: (path: string | null) => void;
  updateFileContent: (path: string, content: string) => void;
  markFileSaved: (path: string) => void;
}

export const useAppStore = create<AppState>((set) => ({
  // Core state
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

  // ── File tree & editor defaults ────────────────────────────
  fileTree: null,
  fileTreeLoading: false,
  openFiles: [],
  activeFilePath: null,

  // NEW state defaults
  toasts: [],
  theme: 'dark',
  sidebarOpen: true,
  commandPaletteOpen: false,
  approvalMode: 'auto',
  skills: [],
  codeGraphResults: [],
  agentMode: 'agent',

  // UI settings
  settingsOpen: false,
  apiKey: typeof window !== 'undefined' ? localStorage.getItem('likecodex_api_key') || '' : '',
  selectedModel: typeof window !== 'undefined' ? localStorage.getItem('likecodex_model') || 'deepseek-v4-flash' : 'deepseek-v4-flash',

  // ── Core actions ───────────────────────────────────────────────────
  setSettingsOpen: (open) => set({ settingsOpen: open }),
  setApiKey: (key) => {
    if (typeof window !== 'undefined') localStorage.setItem('likecodex_api_key', key);
    set({ apiKey: key });
  },
  setSelectedModel: (model) => {
    if (typeof window !== 'undefined') localStorage.setItem('likecodex_model', model);
    set({ selectedModel: model });
  },
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
  setAgentMode: (mode) => set({ agentMode: mode }),
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

  // ── NEW actions ───────────────────────────────────────────────────
  addToast: (toast) =>
    set((state) => ({
      toasts: [...state.toasts, { ...toast, id: `toast-${Date.now()}-${Math.random().toString(36).slice(2, 7)}` }],
    })),
  removeToast: (id) =>
    set((state) => ({
      toasts: state.toasts.filter((t) => t.id !== id),
    })),
  setTheme: (theme) => set({ theme }),
  toggleSidebar: () => set((state) => ({ sidebarOpen: !state.sidebarOpen })),
  setSidebarOpen: (open) => set({ sidebarOpen: open }),
  setCommandPaletteOpen: (open) => set({ commandPaletteOpen: open }),
  setApprovalMode: (mode) => set({ approvalMode: mode }),
  setSkills: (skills) => set({ skills }),
  setCodeGraphResults: (results) => set({ codeGraphResults: results }),

  // ── File tree & editor actions ───────────────────────────────────
  setFileTree: (tree) => set({ fileTree: tree }),
  setFileTreeLoading: (loading) => set({ fileTreeLoading: loading }),
  openFile: (file) =>
    set((state) => {
      const existing = state.openFiles.find((f) => f.path === file.path);
      if (existing) {
        return { activeFilePath: file.path };
      }
      return {
        openFiles: [
          ...state.openFiles,
          {
            path: file.path,
            name: file.name,
            content: file.content,
            savedContent: file.content,
            modified: false,
          },
        ],
        activeFilePath: file.path,
      };
    }),
  closeFile: (path) =>
    set((state) => {
      const newOpenFiles = state.openFiles.filter((f) => f.path !== path);
      let newActive = state.activeFilePath;
      if (state.activeFilePath === path) {
        const idx = state.openFiles.findIndex((f) => f.path === path);
        if (newOpenFiles.length === 0) {
          newActive = null;
        } else if (idx > 0) {
          newActive = newOpenFiles[Math.min(idx - 1, newOpenFiles.length - 1)].path;
        } else {
          newActive = newOpenFiles[0]?.path ?? null;
        }
      }
      return { openFiles: newOpenFiles, activeFilePath: newActive };
    }),
  setActiveFile: (path) => set({ activeFilePath: path }),
  updateFileContent: (path, content) =>
    set((state) => ({
      openFiles: state.openFiles.map((f) =>
        f.path === path ? { ...f, content, modified: content !== f.savedContent } : f
      ),
    })),
  markFileSaved: (path) =>
    set((state) => ({
      openFiles: state.openFiles.map((f) =>
        f.path === path ? { ...f, savedContent: f.content, modified: false } : f
      ),
    })),
}));
