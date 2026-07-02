'use client';

import { create } from 'zustand';

// ── Types ──────────────────────────────────────────────────────────────

export interface GitCommitNode {
  hash: string;
  shortHash: string;
  message: string;
  author: string;
  authorEmail: string;
  date: string;
  timestamp: number;
  branch: string | null;  // branch name if HEAD of branch
  parents: string[];       // parent hashes
  refs: Array<{ name: string; type: 'branch' | 'tag' | 'remote' }>;
  /** Graph column this commit sits in */
  column: number;
}

export interface GitGraphLayout {
  commits: GitCommitNode[];
  /** For each commit, the lines connecting to parents */
  connections: Array<{
    fromCommit: string;
    toCommit: string;
    fromColumn: number;
    toColumn: number;
    colorIndex: number;
  }>;
  maxColumns: number;
}

export interface ConflictFile {
  path: string;
  /** Each conflict block identified in this file */
  conflicts: ConflictBlock[];
  resolved: boolean;
}

export interface ConflictBlock {
  id: string;
  ours: string[];
  base: string[];
  theirs: string[];
  resolution: 'ours' | 'theirs' | 'both' | 'manual' | null;
  manualContent: string | null;
}

export type ConflictResolution = 'ours' | 'theirs' | 'both' | 'manual';

export interface StagingEntry {
  path: string;
  changeType: 'modified' | 'added' | 'deleted' | 'untracked' | 'renamed';
  staged: boolean;
  oldPath?: string;
  hunks?: Array<{ header: string; content: string; staged: boolean }>;
}

// ── Git UI Store ───────────────────────────────────────────────────────

interface GitUIState {
  // Graph
  graphLayout: GitGraphLayout | null;
  graphLoading: boolean;
  graphError: string | null;

  // Staging
  unstagedFiles: StagingEntry[];
  stagedFiles: StagingEntry[];
  stagingLoading: boolean;

  // Conflicts
  conflictFiles: ConflictFile[];
  activeConflictFile: string | null;
  activeConflictBlock: number;

  // Generic
  selectedCommit: GitCommitNode | null;
  commitDetailOpen: boolean;
}

interface GitUIActions {
  setGraphLayout: (layout: GitGraphLayout | null) => void;
  setGraphLoading: (loading: boolean) => void;
  setGraphError: (err: string | null) => void;

  setUnstagedFiles: (files: StagingEntry[]) => void;
  setStagedFiles: (files: StagingEntry[]) => void;
  setStagingLoading: (loading: boolean) => void;

  setConflictFiles: (files: ConflictFile[]) => void;
  setActiveConflictFile: (path: string | null) => void;
  setActiveConflictBlock: (index: number) => void;
  resolveConflict: (filePath: string, blockId: string, resolution: ConflictResolution) => void;
  setManualContent: (filePath: string, blockId: string, content: string) => void;
  markConflictResolved: (filePath: string) => void;

  selectCommit: (commit: GitCommitNode | null) => void;
  setCommitDetailOpen: (open: boolean) => void;
}

export type GitUIStore = GitUIState & GitUIActions;

const initialGitUIState: GitUIState = {
  graphLayout: null,
  graphLoading: false,
  graphError: null,

  unstagedFiles: [],
  stagedFiles: [],
  stagingLoading: false,

  conflictFiles: [],
  activeConflictFile: null,
  activeConflictBlock: 0,

  selectedCommit: null,
  commitDetailOpen: false,
};

export const useGitUIStore = create<GitUIStore>((set, get) => ({
  ...initialGitUIState,

  setGraphLayout: (layout) => set({ graphLayout: layout, graphLoading: false }),
  setGraphLoading: (loading) => set({ graphLoading: loading }),
  setGraphError: (err) => set({ graphError: err, graphLoading: false }),

  setUnstagedFiles: (files) => set({ unstagedFiles: files }),
  setStagedFiles: (files) => set({ stagedFiles: files }),
  setStagingLoading: (loading) => set({ stagingLoading: loading }),

  setConflictFiles: (files) =>
    set({ conflictFiles: files, activeConflictFile: files[0]?.path || null, activeConflictBlock: 0 }),

  setActiveConflictFile: (path) => set({ activeConflictFile: path, activeConflictBlock: 0 }),

  setActiveConflictBlock: (index) => set({ activeConflictBlock: index }),

  resolveConflict: (filePath, blockId, resolution) =>
    set((s) => ({
      conflictFiles: s.conflictFiles.map((f) =>
        f.path === filePath
          ? {
              ...f,
              conflicts: f.conflicts.map((b) =>
                b.id === blockId
                  ? { ...b, resolution, manualContent: resolution === 'manual' ? b.manualContent : null }
                  : b
              ),
            }
          : f
      ),
    })),

  setManualContent: (filePath, blockId, content) =>
    set((s) => ({
      conflictFiles: s.conflictFiles.map((f) =>
        f.path === filePath
          ? {
              ...f,
              conflicts: f.conflicts.map((b) =>
                b.id === blockId ? { ...b, manualContent: content, resolution: 'manual' as const } : b
              ),
            }
          : f
      ),
    })),

  markConflictResolved: (filePath) =>
    set((s) => ({
      conflictFiles: s.conflictFiles.map((f) =>
        f.path === filePath ? { ...f, resolved: true } : f
      ),
    })),

  selectCommit: (commit) => set({ selectedCommit: commit }),
  setCommitDetailOpen: (open) => set({ commitDetailOpen: open }),
}));
