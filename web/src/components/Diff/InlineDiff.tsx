'use client';

import React, { useMemo, useCallback, useState } from 'react';
import { useDiffStore, type DiffFile, type DiffHunk } from '@/stores/diffStore';
import { StatusBadge, StatBadge, ViewModeToggle } from './SharedDiffComponents';

// ── Word-level Diff ───────────────────────────────────────────────────

function WordHighlight({
  text,
  type,
  isChanged,
}: {
  text: string;
  type: 'add' | 'del' | 'context';
  isChanged: boolean;
}) {
  if (!isChanged) {
    return <>{text}</>;
  }
  const bg = type === 'add' ? 'bg-green-600/40' : 'bg-red-600/40';
  // Split into tokens and highlight changed portions
  const tokens = text.split(/(\s+)/);
  return (
    <>
      {tokens.map((token, i) => {
        // Simple heuristic: mark tokens that differ from empty context
        const changed = token.length > 0 && !/^\s+$/.test(token);
        return changed ? (
          <span key={i} className={`${bg} rounded px-0.5`}>{token}</span>
        ) : (
          <span key={i}>{token}</span>
        );
      })}
    </>
  );
}

// ── Inline Hunk Renderer ──────────────────────────────────────────────

function InlineHunkRenderer({
  hunk,
  hunkIndex,
  filePath,
  accepted,
  rejected,
}: {
  hunk: DiffHunk;
  hunkIndex: number;
  filePath: string;
  accepted: boolean;
  rejected: boolean;
}) {
  const toggleCollapse = useDiffStore((s) => s.toggleHunkCollapse);
  const acceptChange = useDiffStore((s) => s.acceptChange);
  const rejectChange = useDiffStore((s) => s.rejectChange);

  const [collapsed, setCollapsed] = useState(false);

  const handleToggle = useCallback(() => {
    toggleCollapse(filePath, hunkIndex);
    setCollapsed((c) => !c);
  }, [filePath, hunkIndex, toggleCollapse]);

  if (collapsed) {
    return (
      <div className="flex items-center gap-2 px-3 py-1 text-xs text-muted hover:bg-accent/5 cursor-pointer transition-colors border-b border-border/30" onClick={handleToggle}>
        <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
        </svg>
        <span className="font-mono">@@ -{hunk.oldStart},{hunk.oldLines} +{hunk.newStart},{hunk.newLines} @@</span>
        <span className="text-muted/60">{hunk.header}</span>
        <span className="ml-auto text-muted/40">{hunk.lines.filter(l => l.type === 'add').length} additions, {hunk.lines.filter(l => l.type === 'del').length} deletions</span>
      </div>
    );
  }

  return (
    <div className="border-b border-border/30">
      {/* Hunk Header */}
      <div className="flex items-center justify-between px-3 py-1 bg-surface/30 text-xs text-muted border-b border-border/20">
        <div className="flex items-center gap-2">
          <button onClick={handleToggle} className="hover:text-foreground transition-colors" title="Collapse">
            <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 15l7-7 7 7" />
            </svg>
          </button>
          <span className="font-mono">@@ -{hunk.oldStart},{hunk.oldLines} +{hunk.newStart},{hunk.newLines} @@</span>
          {hunk.header && <span className="text-muted/60">{hunk.header}</span>}
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={() => acceptChange(filePath, hunkIndex)}
            disabled={accepted || rejected}
            className={`px-2 py-0.5 text-[10px] font-medium rounded transition-colors ${
              accepted ? 'bg-green-600/30 text-green-400 cursor-default' : 'bg-green-600/80 hover:bg-green-600 text-white'
            } disabled:opacity-40`}
          >
            {accepted ? '✓ Accepted' : 'Accept'}
          </button>
          <button
            onClick={() => rejectChange(filePath, hunkIndex)}
            disabled={accepted || rejected}
            className={`px-2 py-0.5 text-[10px] font-medium rounded transition-colors ${
              rejected ? 'bg-red-600/30 text-red-400 cursor-default' : 'bg-red-600/80 hover:bg-red-600 text-white'
            } disabled:opacity-40`}
          >
            {rejected ? '✗ Rejected' : 'Reject'}
          </button>
        </div>
      </div>
      {/* Hunk Lines */}
      <div className="overflow-x-auto">
        {hunk.lines.map((line, i) => {
          const bgColor =
            line.type === 'add' ? 'bg-green-900/15' :
            line.type === 'del' ? 'bg-red-900/15' : '';
          const borderColor =
            line.type === 'add' ? 'border-l-green-600' :
            line.type === 'del' ? 'border-l-red-600' :
            'border-l-transparent';
          const oldNum = line.oldLineNum !== null ? String(line.oldLineNum) : '';
          const newNum = line.newLineNum !== null ? String(line.newLineNum) : '';

          return (
            <div key={i} className={`flex border-l-2 ${borderColor} ${bgColor} hover:bg-accent/5 transition-colors`}>
              <div className="flex-shrink-0 w-[3.5rem] text-right pr-1.5 text-[10px] leading-6 text-red-400/50 font-mono select-none border-r border-border/20 bg-surface/20">
                {oldNum}
              </div>
              <div className="flex-shrink-0 w-[3.5rem] text-right pr-1.5 text-[10px] leading-6 text-green-400/50 font-mono select-none border-r border-border/20 bg-surface/20">
                {newNum}
              </div>
              <span className="flex-shrink-0 w-5 text-center text-[10px] leading-6 font-mono select-none">
                {line.type === 'add' ? (
                  <span className="text-green-500">+</span>
                ) : line.type === 'del' ? (
                  <span className="text-red-500">-</span>
                ) : (
                  <span className="text-muted/30">&nbsp;</span>
                )}
              </span>
              <code className="flex-1 text-[11px] leading-6 font-mono pl-2 whitespace-pre overflow-x-auto">
                {line.content || ' '}
              </code>
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ── File Tab ──────────────────────────────────────────────────────────

function FileTab({
  file,
  active,
  onClick,
}: {
  file: DiffFile;
  active: boolean;
  onClick: () => void;
}) {
  return (
    <button
      onClick={onClick}
      className={`flex items-center gap-2 px-3 py-2 text-xs border-b-2 transition-colors whitespace-nowrap ${
        active
          ? 'border-primary text-foreground bg-accent/10'
          : 'border-transparent text-muted hover:text-foreground hover:bg-accent/5'
      }`}
    >
      <StatusBadge status={file.status} />
      <span className="truncate max-w-[200px]">{file.path}</span>
      <span className="text-green-400">+{file.additions}</span>
      <span className="text-red-400">-{file.deletions}</span>
    </button>
  );
}

// ── File Search/Filter ────────────────────────────────────────────────

function FileFilter({
  files,
  activePath,
  onSelect,
}: {
  files: DiffFile[];
  activePath: string | null;
  onSelect: (path: string) => void;
}) {
  const [query, setQuery] = useState('');

  const filtered = useMemo(
    () => (query ? files.filter((f) => f.path.toLowerCase().includes(query.toLowerCase())) : files),
    [files, query]
  );

  return (
    <div className="border-b border-border">
      <div className="px-2 py-1.5">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Filter files..."
          className="w-full bg-surface/50 border border-border rounded px-2 py-1 text-[10px] text-foreground placeholder:text-muted/40 focus:outline-none focus:border-primary/50"
        />
      </div>
      <div className="flex overflow-x-auto scrollbar-thin">
        {filtered.map((file) => (
          <FileTab
            key={file.path}
            file={file}
            active={file.path === activePath}
            onClick={() => onSelect(file.path)}
          />
        ))}
      </div>
    </div>
  );
}

// ── Main Component ────────────────────────────────────────────────────

export interface InlineDiffProps {
  files?: DiffFile[];
  className?: string;
}

export function InlineDiff({ files: propFiles, className = '' }: InlineDiffProps) {
  const storeFiles = useDiffStore((s) => s.files);
  const activeFilePath = useDiffStore((s) => s.activeFilePath);
  const setActiveFile = useDiffStore((s) => s.setActiveFile);
  const acceptedChanges = useDiffStore((s) => s.acceptedChanges);
  const rejectedChanges = useDiffStore((s) => s.rejectedChanges);
  const acceptAll = useDiffStore((s) => s.acceptAll);
  const rejectAll = useDiffStore((s) => s.rejectAll);

  const files = propFiles || storeFiles;
  const activeFile = files.find((f) => f.path === activeFilePath) || files[0];

  const handleSelect = useCallback((path: string) => setActiveFile(path), [setActiveFile]);
  const handleAcceptAll = useCallback(() => activeFile && acceptAll(activeFile.path), [activeFile, acceptAll]);
  const handleRejectAll = useCallback(() => activeFile && rejectAll(activeFile.path), [activeFile, rejectAll]);

  if (!activeFile) {
    return (
      <div className={`flex items-center justify-center h-40 text-sm text-muted ${className}`}>
        <div className="flex flex-col items-center gap-2">
          <svg className="h-8 w-8 text-muted/40" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
          <span>Select a file to view diff</span>
        </div>
      </div>
    );
  }

  return (
    <div className={`flex flex-col h-full ${className}`}>
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-border bg-surface/30 shrink-0">
        <div className="flex items-center gap-3 min-w-0">
          <StatusBadge status={activeFile.status} />
          <span className="text-sm font-medium truncate">{activeFile.path}</span>
          <StatBadge additions={activeFile.additions} deletions={activeFile.deletions} />
        </div>
        <div className="flex items-center gap-2">
          <ViewModeToggle />
          <button
            onClick={handleAcceptAll}
            className="px-2.5 py-1 text-[10px] font-medium rounded bg-green-600/80 hover:bg-green-600 text-white transition-colors"
          >
            Accept All
          </button>
          <button
            onClick={handleRejectAll}
            className="px-2.5 py-1 text-[10px] font-medium rounded bg-red-600/80 hover:bg-red-600 text-white transition-colors"
          >
            Reject All
          </button>
        </div>
      </div>

      {/* File Tabs */}
      {files.length > 1 && (
        <FileFilter files={files} activePath={activeFile.path} onSelect={handleSelect} />
      )}

      {/* Hunk Content */}
      <div className="flex-1 overflow-y-auto">
        {activeFile.hunks.length === 0 ? (
          <div className="flex items-center justify-center h-full text-xs text-muted/60">
            No changes in this file
          </div>
        ) : (
          activeFile.hunks.map((hunk, i) => (
            <InlineHunkRenderer
              key={i}
              hunk={hunk}
              hunkIndex={i}
              filePath={activeFile.path}
              accepted={acceptedChanges.has(`${activeFile.path}:${i}`)}
              rejected={rejectedChanges.has(`${activeFile.path}:${i}`)}
            />
          ))
        )}
      </div>
    </div>
  );
}
