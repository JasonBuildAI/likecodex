// ── Unified API Module ──────────────────────────────────────────────────
// This file re-exports all API functions from modular service files.
// Import from '@/lib/api' to access any API function.

// Chat service (streamChat, subscribeEvents, event types)
export {
  streamChat,
  subscribeEvents,
  formatRetryMessage,
  parseRustEvent,
  type RustEvent,
  type EventHandler,
} from './services/chatService';

// Session service (session CRUD, doctor)
export {
  fetchSessions,
  fetchSessionEvents,
  createNewSession,
  resumeSession,
  forkSession,
  deleteSession,
  summarizeSession,
  compactSession,
  fetchDoctor,
  type DoctorReport,
} from './services/sessionService';

// Git service
export {
  fetchGitStatus,
  fetchGitDiff,
  gitStageFile,
  gitUnstageFile,
  gitStageAll,
  gitCommit,
  fetchGitLog,
  fetchGitBranches,
  gitCheckoutBranch,
  gitCreateBranch,
  gitDiscardChanges,
  gitSearch,
  gitPull,
  gitPush,
  gitFetch,
  gitStash,
  type GitChangeData,
  type GitStatusData,
  type GitCommitData,
  type GitBranchData,
  type GitDiffData,
  type GitSearchResult,
} from './services/gitService';

// Skills & Tasks & Checkpoints & Other API functions
export {
  fetchSkills,
  fetchSkillsList,
  fetchSkillDetail,
  createSkill,
  updateSkill,
  deleteSkill,
  toggleSkill,
  reloadSkills,
  invokeSkill,
  installSkill,
  exportSkill,
  importSkill,
  setApprovalMode,
  createTask,
  fetchCheckpoints,
  rewindCheckpoint,
  respondAsk,
  respondPermission,
  fetchConfig,
  fetchCacheMetrics,
  searchCodeGraph,
  searchIndex,
  executeCommand,
  parseToolCalls,
} from './services/skillService';

// Workspace & IDE services
export {
  fetchWorkspaceTree,
  fetchWorkspaceFile,
  writeWorkspaceFile,
  inlineEditCode,
  fetchContextMentions,
  lspDefinition,
  lspReferences,
  lspHover,
  type WorkspaceFile,
  type InlineEditParams,
  type InlineEditResult,
  type ContextMentionResult,
  type LSPDefinition,
  type LSPHover,
  fetchFileSymbols,
  type FileSymbol,
} from './services/workspaceService';
