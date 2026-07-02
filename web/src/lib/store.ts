import { create } from 'zustand';
import type { ChatSlice } from './stores/chatStore';
import type { UISlice } from './stores/uiStore';
import type { FileSlice } from './stores/fileStore';
import type { AgentSlice } from './stores/agentStore';

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

export interface Toast {
  id: string;
  type: 'info' | 'success' | 'warning' | 'error';
  message: string;
  duration?: number;
}

export interface Skill {
  name: string;
  description: string;
  body?: string;
  run_as?: string;
  path?: string | null;
  model?: string | null;
  allowed_tools?: string[];
  license?: string;
  compatibility?: string;
  metadata?: Record<string, string>;
  version?: string;
  author?: string;
  enabled?: boolean;
  source_type?: string;
  source_dir?: string | null;
  source?: string;
  directory_files?: string[];
}

export interface SearchResult {
  name: string;
  kind: string;
  path: string;
  line?: number;
}

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

export type AgentMode = 'ask' | 'agent' | 'manual';

export interface Conversation {
  id: string;
  title: string;
  mode: AgentMode;
  createdAt: Date;
  lastMessageAt: Date;
  messageCount: number;
}

export type ToolCallStatus = 'pending' | 'running' | 'waiting_approval' | 'completed' | 'error' | 'cancelled';

export interface ToolCallStreamItem {
  id: string;
  call: ToolCall;
  status: ToolCallStatus;
  startedAt: number;
  completedAt?: number;
  result?: string;
  error?: string;
}

export type AgentViewMode = 'chat' | 'agent' | 'mixed';

// ── Combined AppState ──────────────────────────────────────────────────
export interface AppState extends ChatSlice, UISlice, FileSlice, AgentSlice {
  // Core state not in slices
  pendingPermissions: PermissionRequest[];
  pendingAskRequests: AskRequest[];
  activeDiff: { before: string; after: string } | null;
  sessions: SessionSummary[];
  config: Record<string, unknown>;
  cacheHitRate: number | null;
  currentSessionId: string | null;
  planModeActive: boolean;
  planModePendingExit: boolean;
  collaborationMode: 'normal' | 'plan' | 'goal';
  settingsOpen: boolean;
  apiKey: string;
  selectedModel: string;

  // Core actions not in slices
  setSettingsOpen: (open: boolean) => void;
  setApiKey: (key: string) => void;
  setSelectedModel: (model: string) => void;
  setCacheHitRate: (rate: number | null) => void;
  upsertToolDispatch: (call: ToolCall, partial: boolean) => void;
  addPendingPermission: (req: PermissionRequest) => void;
  removePendingPermission: (requestId: string) => void;
  addPendingAsk: (req: AskRequest) => void;
  removePendingAsk: (requestId: string) => void;
  setPlanMode: (active: boolean, pendingExit?: boolean) => void;
  setCollaborationMode: (mode: 'normal' | 'plan' | 'goal') => void;
  setActiveDiff: (diff: { before: string; after: string } | null) => void;
  setSessions: (sessions: SessionSummary[]) => void;
  setConfig: (config: Record<string, unknown>) => void;
  setCurrentSessionId: (id: string | null) => void;
}

// ── Slice imports ───────────────────────────────────────────────────────
import { createChatSlice } from './stores/chatStore';
import { createUISlice } from './stores/uiStore';
import { createFileSlice } from './stores/fileStore';
import { createAgentSlice } from './stores/agentStore';

// ── Create combined store ──────────────────────────────────────────────
export const useAppStore = create<AppState>()((...a) => ({
  // Slices
  ...createChatSlice(...a),
  ...createUISlice(...a),
  ...createFileSlice(...a),
  ...createAgentSlice(...a),

  // Core state
  pendingPermissions: [],
  pendingAskRequests: [],
  activeDiff: null,
  sessions: [],
  config: {},
  cacheHitRate: null,
  currentSessionId: null,
  planModeActive: false,
  planModePendingExit: false,
  collaborationMode: 'normal',
  settingsOpen: false,
  apiKey: typeof window !== 'undefined' ? localStorage.getItem('likecodex_api_key') || '' : '',
  selectedModel: typeof window !== 'undefined' ? localStorage.getItem('likecodex_model') || 'deepseek-v4-flash' : 'deepseek-v4-flash',

  // Core actions
  setSettingsOpen: (open) => a[0]({ settingsOpen: open }),
  setApiKey: (key) => {
    if (typeof window !== 'undefined') localStorage.setItem('likecodex_api_key', key);
    a[0]({ apiKey: key });
  },
  setSelectedModel: (model) => {
    if (typeof window !== 'undefined') localStorage.setItem('likecodex_model', model);
    a[0]({ selectedModel: model });
  },
  setCacheHitRate: (rate) => a[0]({ cacheHitRate: rate }),
  upsertToolDispatch: (call, partial) =>
    a[0]((state) => {
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
  addPendingPermission: (req) =>
    a[0]((state) => ({
      pendingPermissions: [...state.pendingPermissions, req],
    })),
  removePendingPermission: (requestId) =>
    a[0]((state) => ({
      pendingPermissions: state.pendingPermissions.filter(
        (p) => p.requestId !== requestId
      ),
    })),
  addPendingAsk: (req) =>
    a[0]((state) => ({
      pendingAskRequests: [...state.pendingAskRequests, req],
    })),
  removePendingAsk: (requestId) =>
    a[0]((state) => ({
      pendingAskRequests: state.pendingAskRequests.filter(
        (p) => p.requestId !== requestId
      ),
    })),
  setPlanMode: (active, pendingExit = false) =>
    a[0]({ planModeActive: active, planModePendingExit: pendingExit }),
  setCollaborationMode: (mode) => a[0]({ collaborationMode: mode }),
  setActiveDiff: (diff) => a[0]({ activeDiff: diff }),
  setSessions: (sessions) => a[0]({ sessions }),
  setConfig: (config) => a[0]({ config }),
  setCurrentSessionId: (id) => a[0]({ currentSessionId: id }),
}));
