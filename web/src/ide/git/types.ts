/** Git types for the version control UI */

export type GitChangeType =
  | 'modified'
  | 'added'
  | 'deleted'
  | 'untracked'
  | 'renamed'
  | 'both-added';

export interface GitChange {
  path: string;
  changeType: GitChangeType;
  staged: boolean;
  oldPath?: string;
}

export interface GitCommit {
  hash: string;
  shortHash: string;
  message: string;
  author: string;
  date: string;
  files?: string[];
}

export interface GitBranch {
  name: string;
  current: boolean;
  remote: boolean;
  lastCommit: string;
}

export interface GitStatus {
  changes: GitChange[];
  currentBranch: string;
  isRepo: boolean;
}

export interface GitDiffResult {
  path: string;
  diff: string;
  originalContent: string;
  modifiedContent: string;
}

export interface SearchResult {
  path: string;
  line: number;
  content: string;
}
