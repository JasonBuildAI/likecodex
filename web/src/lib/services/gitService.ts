import { fetchWithRetry, buildHeaders } from './chatService';

export interface GitChangeData {
  path: string; changeType: string; staged: boolean; oldPath?: string;
}
export interface GitStatusData {
  changes: GitChangeData[]; currentBranch: string; isRepo: boolean;
}
export interface GitCommitData {
  hash: string; shortHash: string; message: string; author: string; date: string;
}
export interface GitBranchData {
  name: string; current: boolean; remote: boolean; lastCommit: string;
}
export interface GitDiffData {
  path: string; diff: string; originalContent: string; modifiedContent: string;
}
export interface GitSearchResult {
  path: string; line: number; content: string;
}

export async function fetchGitStatus(): Promise<GitStatusData | null> {
  const resp = await fetchWithRetry('/api/ide/git/status', {}, 1, 10000);
  if (!resp.ok) return null;
  return resp.json();
}

export async function fetchGitDiff(path: string, staged: boolean = false): Promise<GitDiffData | null> {
  const resp = await fetchWithRetry('/api/ide/git/diff', { method: 'POST', headers: buildHeaders(), body: JSON.stringify({ path, staged }) }, 1, 10000);
  if (!resp.ok) return null;
  return resp.json();
}

export async function gitStageFile(path: string): Promise<boolean> {
  const resp = await fetchWithRetry('/api/ide/git/stage', { method: 'POST', headers: buildHeaders(), body: JSON.stringify({ path }) }, 1, 5000);
  return resp.ok;
}

export async function gitUnstageFile(path: string): Promise<boolean> {
  const resp = await fetchWithRetry('/api/ide/git/unstage', { method: 'POST', headers: buildHeaders(), body: JSON.stringify({ path }) }, 1, 5000);
  return resp.ok;
}

export async function gitStageAll(): Promise<boolean> {
  const resp = await fetchWithRetry('/api/ide/git/stage-all', { method: 'POST', headers: buildHeaders() }, 1, 5000);
  return resp.ok;
}

export async function gitCommit(message: string): Promise<{ success: boolean; error?: string }> {
  const resp = await fetchWithRetry('/api/ide/git/commit', { method: 'POST', headers: buildHeaders(), body: JSON.stringify({ message }) }, 1, 10000);
  if (!resp.ok) return { success: false, error: `HTTP ${resp.status}` };
  return resp.json();
}

export async function fetchGitLog(count: number = 50): Promise<GitCommitData[]> {
  const resp = await fetchWithRetry(`/api/ide/git/log?count=${count}`, {}, 1, 10000);
  if (!resp.ok) return [];
  const data = await resp.json();
  return data.commits || [];
}

export async function fetchGitBranches(): Promise<GitBranchData[]> {
  const resp = await fetchWithRetry('/api/ide/git/branches', {}, 1, 5000);
  if (!resp.ok) return [];
  const data = await resp.json();
  return data.branches || [];
}

export async function gitCheckoutBranch(name: string): Promise<boolean> {
  const resp = await fetchWithRetry('/api/ide/git/checkout', { method: 'POST', headers: buildHeaders(), body: JSON.stringify({ name }) }, 1, 10000);
  return resp.ok;
}

export async function gitCreateBranch(name: string): Promise<boolean> {
  const resp = await fetchWithRetry('/api/ide/git/create-branch', { method: 'POST', headers: buildHeaders(), body: JSON.stringify({ name }) }, 1, 5000);
  return resp.ok;
}

export async function gitDiscardChanges(path: string): Promise<boolean> {
  const resp = await fetchWithRetry('/api/ide/git/discard', { method: 'POST', headers: buildHeaders(), body: JSON.stringify({ path }) }, 1, 5000);
  return resp.ok;
}

export async function gitSearch(query: string): Promise<GitSearchResult[]> {
  const resp = await fetchWithRetry(`/api/ide/git/search?q=${encodeURIComponent(query)}`, {}, 1, 15000);
  if (!resp.ok) return [];
  const data = await resp.json();
  return data.results || [];
}

export async function gitPull(): Promise<{ success: boolean; output?: string; error?: string }> {
  const resp = await fetchWithRetry('/api/ide/git/pull', { method: 'POST', headers: buildHeaders() }, 1, 30000);
  if (!resp.ok) return { success: false, error: `HTTP ${resp.status}` };
  return resp.json();
}

export async function gitPush(): Promise<{ success: boolean; output?: string; error?: string }> {
  const resp = await fetchWithRetry('/api/ide/git/push', { method: 'POST', headers: buildHeaders() }, 1, 30000);
  if (!resp.ok) return { success: false, error: `HTTP ${resp.status}` };
  return resp.json();
}

export async function gitFetch(): Promise<{ success: boolean; output?: string; error?: string }> {
  const resp = await fetchWithRetry('/api/ide/git/fetch', { method: 'POST', headers: buildHeaders() }, 1, 30000);
  if (!resp.ok) return { success: false, error: `HTTP ${resp.status}` };
  return resp.json();
}

export async function gitStash(action: string, message: string = ''): Promise<{ success: boolean; output?: string; error?: string }> {
  const resp = await fetchWithRetry('/api/ide/git/stash', { method: 'POST', headers: buildHeaders(), body: JSON.stringify({ action, message }) }, 1, 15000);
  if (!resp.ok) return { success: false, error: `HTTP ${resp.status}` };
  return resp.json();
}
