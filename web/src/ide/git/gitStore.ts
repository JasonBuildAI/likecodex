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
  fetchGitHunks,
  gitStageHunk,
  type GitChangeData,
  type GitCommitData,
  type GitBranchData,
  type GitDiffData,
  type GitSearchResult,
  type GitHunksResult,
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
  hunks: GitHunksResult | null;
  selectedHunk: number;

  // Search
  searchQuery: string;
  searchResults: GitSearchResult[];
  isSearching: boolean;

  // Actions
  refreshStatus: () => Promise<void>;
  refreshLog: () => Promise<void>;
  refreshBranches: () => Promise<void>;
  selectFile: (path: string, staged: boolean) => Promise<void>;
  loadHunks: (path: string, staged: boolean) => Promise<void>;
  stageHunk: (path: string, hunkIndex: number) => Promise<boolean>;
  stageFile: (path: string) => Promise<void>;
  unstageFile: (path: string) => Promise<void>;
  stageAll: () => Promise<void>;
  commit: (message: string) => Promise<boolean>;
  discardChanges: (path: string) => Promise<void>;
  checkoutBranch: (name: string) => Promise<void>;
  createBranch: (name: string) => Promise<void>;
  search: (query: string) => Promise<void>;
  pull: () => Promise<{ success: boolean; output?: string; error?: string }>;
  push: () => Promise<{ success: boolean; output?: string; error?: string }>;
  fetch: () => Promise<{ success: boolean; output?: string; error?: string }>;
  stashPush: (message?: string) => Promise<{ success: boolean; output?: string; error?: string }>;
  stashPop: () => Promise<{ success: boolean; output?: string; error?: string }>;
  stashList: () => Promise<{ success: boolean; output?: string; error?: string }>;
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
  hunks: null,
  selectedHunk: -1,
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

  loadHunks: async (path, staged) => {
    try {
      const hunks = await fetchGitHunks(path, staged);
      set({ hunks, selectedHunk: -1 });
    } catch {
      set({ hunks: null, selectedHunk: -1 });
    }
  },

  stageHunk: async (path, hunkIndex) => {
    try {
      const result = await gitStageHunk(path, hunkIndex);
      if (result.success) {
        await get().refreshStatus();
        await get().loadHunks(path, false);
        return true;
      }
      return false;
    } catch {
      return false;
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

  pull: async () => {
    const result = await gitPull();
    if (result.success) {
      await get().refreshStatus();
      await get().refreshLog();
    } else {
      set({ error: result.error || 'Pull failed' });
    }
    return result;
  },

  push: async () => {
    const result = await gitPush();
    if (!result.success) {
      set({ error: result.error || 'Push failed' });
    }
    return result;
  },

  fetch: async () => {
    const result = await gitFetch();
    if (result.success) {
      await get().refreshBranches();
    } else {
      set({ error: result.error || 'Fetch failed' });
    }
    return result;
  },

  stashPush: async (message) => {
    const result = await gitStash('push', message);
    if (result.success) {
      await get().refreshStatus();
    } else {
      set({ error: result.error || 'Stash failed' });
    }
    return result;
  },

  stashPop: async () => {
    const result = await gitStash('pop');
    if (result.success) {
      await get().refreshStatus();
    } else {
      set({ error: result.error || 'Stash pop failed' });
    }
    return result;
  },

  stashList: async () => {
    return await gitStash('list');
  },
}));
