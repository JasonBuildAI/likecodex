/**
 * Git Store — Zustand state for version control panel.
 */

import { create } from 'zustand';
import {
  fetchGitStatus,
  fetchGitDiff,
  gitStageFile,
  gitUnstageFile,
  gitStageAll,
  gitCommit as apiCommit,
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
  type GitCommitData,
  type GitBranchData,
  type GitDiffData,
  type GitSearchResult,
} from '@/lib/api';

interface GitState {
  changes: GitChangeData[];
  currentBranch: string;
  isRepo: boolean;
  commits: GitCommitData[];
  branches: GitBranchData[];
  selectedDiff: GitDiffData | null;
  selectedPath: string | null;
  isLoading: boolean;
  error: string | null;

  // Search
  searchQuery: string;
  searchResults: GitSearchResult[];
  isSearching: boolean;

  // Actions
  refreshStatus: () => Promise<void>;
  refreshLog: () => Promise<void>;
  refreshBranches: () => Promise<void>;
  selectFile: (path: string, staged: boolean) => Promise<void>;
  stageFile: (path: string) => Promise<void>;
  unstageFile: (path: string) => Promise<void>;
  stageAll: () => Promise<void>;
  commit: (message: string) => Promise<boolean>;
  discardChanges: (path: string) => Promise<void>;
  checkoutBranch: (name: string) => Promise<void>;
  createBranch: (name: string) => Promise<void>;
  search: (query: string) => Promise<void>;
}

export const useGitStore = create<GitState>((set, get) => ({
  changes: [],
  currentBranch: '',
  isRepo: false,
  commits: [],
  branches: [],
  selectedDiff: null,
  selectedPath: null,
  isLoading: false,
  error: null,
  searchQuery: '',
  searchResults: [],
  isSearching: false,

  refreshStatus: async () => {
    set({ isLoading: true, error: null });
    try {
      const status = await fetchGitStatus();
      if (status) {
        set({
          changes: status.changes,
          currentBranch: status.currentBranch,
          isRepo: status.isRepo,
          isLoading: false,
        });
      } else {
        set({ isLoading: false });
      }
    } catch (err) {
      set({ isLoading: false, error: String(err) });
    }
  },

  refreshLog: async () => {
    try {
      const commits = await fetchGitLog(50);
      set({ commits });
    } catch {
      // Best-effort
    }
  },

  refreshBranches: async () => {
    try {
      const branches = await fetchGitBranches();
      set({ branches });
    } catch {
      // Best-effort
    }
  },

  selectFile: async (path, staged) => {
    set({ selectedPath: path });
    try {
      const diff = await fetchGitDiff(path, staged);
      set({ selectedDiff: diff });
    } catch {
      set({ selectedDiff: null });
    }
  },

  stageFile: async (path) => {
    await gitStageFile(path);
    await get().refreshStatus();
  },

  unstageFile: async (path) => {
    await gitUnstageFile(path);
    await get().refreshStatus();
  },

  stageAll: async () => {
    await gitStageAll();
    await get().refreshStatus();
  },

  commit: async (message) => {
    const result = await apiCommit(message);
    if (result.success) {
      await get().refreshStatus();
      await get().refreshLog();
      set({ selectedDiff: null, selectedPath: null });
    } else {
      set({ error: result.error || 'Commit failed' });
    }
    return result.success;
  },

  discardChanges: async (path) => {
    await gitDiscardChanges(path);
    await get().refreshStatus();
  },

  checkoutBranch: async (name) => {
    await gitCheckoutBranch(name);
    await get().refreshStatus();
    await get().refreshBranches();
  },

  createBranch: async (name) => {
    await gitCreateBranch(name);
    await get().refreshBranches();
  },

  search: async (query) => {
    if (!query.trim()) {
      set({ searchResults: [], searchQuery: '' });
      return;
    }
    set({ isSearching: true, searchQuery: query });
    try {
      const results = await gitSearch(query);
      set({ searchResults: results, isSearching: false });
    } catch {
      set({ isSearching: false, searchResults: [] });
    }
  },
}));
