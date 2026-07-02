import { fetchWithRetry, buildHeaders } from './chatService';
import type { FileNode } from '../store';

// ── Workspace API ──────────────────────────────────────────────────────
export interface WorkspaceFile {
  path: string; name: string; content: string; size: number;
}

export interface InlineEditParams {
  code: string; instruction: string; language: string;
  full_content?: string; file_path?: string;
}
export interface InlineEditResult {
  original: string; modified: string; explanation: string;
  model: string; usage?: Record<string, unknown>;
}

export async function fetchWorkspaceTree(path: string = '.'): Promise<FileNode | null> {
  const resp = await fetchWithRetry(`/workspace/list?path=${encodeURIComponent(path)}`);
  if (!resp.ok) return null;
  return resp.json();
}

export async function fetchWorkspaceFile(path: string): Promise<WorkspaceFile | null> {
  const resp = await fetchWithRetry(`/workspace/read?path=${encodeURIComponent(path)}`);
  if (!resp.ok) return null;
  return resp.json();
}

export async function writeWorkspaceFile(path: string, content: string): Promise<boolean> {
  const resp = await fetchWithRetry('/workspace/write', {
    method: 'POST', headers: buildHeaders(), body: JSON.stringify({ path, content }),
  });
  return resp.ok;
}

export async function inlineEditCode(params: InlineEditParams, signal?: AbortSignal): Promise<InlineEditResult | null> {
  const resp = await fetch('/inline-edit', {
    method: 'POST', headers: buildHeaders(), body: JSON.stringify(params), signal,
  });
  if (!resp.ok) return null;
  return resp.json();
}

// ── IDE Context Search API (@ mentions) ────────────────────────────────
export interface ContextMentionResult {
  id: string; type: string; label: string;
  description?: string; icon: string; content: string;
  token_estimate: number; relevance_score: number;
}

// ── File Symbols API (CodeGraph) ────────────────────────────────────────
export interface FileSymbol {
  name: string;
  kind: string;
  line: number;
}

export async function fetchFileSymbols(filePath: string): Promise<FileSymbol[]> {
  const resp = await fetchWithRetry(`/api/ide/codegraph/symbols?path=${encodeURIComponent(filePath)}`);
  if (!resp.ok) return [];
  const data = await resp.json();
  return (data.symbols || []) as FileSymbol[];
}

export async function fetchContextMentions(query: string): Promise<ContextMentionResult[]> {
  const resp = await fetchWithRetry(`/api/ide/context/search?q=${encodeURIComponent(query)}`, {}, 1, 5000);
  if (!resp.ok) return [];
  const data = await resp.json();
  return (data.results || []) as ContextMentionResult[];
}

// ── IDE LSP API ────────────────────────────────────────────────────────
export interface LSPDefinition { uri?: string; range?: { start: { line: number; character: number }; end: { line: number; character: number } }; }
export interface LSPHover { contents?: string | { language?: string; value?: string } | Array<{ language?: string; value?: string }>; }

export async function lspDefinition(filePath: string, line: number, symbol: string): Promise<{ definitions?: LSPDefinition[]; error?: string } | null> {
  const resp = await fetchWithRetry('/api/ide/lsp/definition', { method: 'POST', headers: buildHeaders(), body: JSON.stringify({ file_path: filePath, line, symbol }) }, 1, 10000);
  if (!resp.ok) return null;
  return resp.json();
}

export async function lspReferences(filePath: string, line: number, symbol: string): Promise<{ references?: LSPDefinition[]; error?: string } | null> {
  const resp = await fetchWithRetry('/api/ide/lsp/references', { method: 'POST', headers: buildHeaders(), body: JSON.stringify({ file_path: filePath, line, symbol }) }, 1, 10000);
  if (!resp.ok) return null;
  return resp.json();
}

export async function lspHover(filePath: string, line: number, symbol: string): Promise<{ hover?: LSPHover; error?: string } | null> {
  const resp = await fetchWithRetry('/api/ide/lsp/hover', { method: 'POST', headers: buildHeaders(), body: JSON.stringify({ file_path: filePath, line, symbol }) }, 1, 10000);
  if (!resp.ok) return null;
  return resp.json();
}

// ── IDE LSP Diagnostics API ────────────────────────────────────────────
export interface LSPDiagnostic {
  message: string;
  severity: 'error' | 'warning' | 'info' | 'hint';
  file: string;
  line: number;
  column: number;
  code?: string;
  source?: string;
}

export async function lspDiagnostics(path: string = '.'): Promise<{ diagnostics: LSPDiagnostic[]; checked: boolean; language?: string; ok?: boolean }> {
  const resp = await fetchWithRetry(`/api/ide/lsp/diagnostics?path=${encodeURIComponent(path)}`);
  if (!resp.ok) return { diagnostics: [], checked: false };
  return resp.json();
}
