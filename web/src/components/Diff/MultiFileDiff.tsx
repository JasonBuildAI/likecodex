'use client';

import React, { useMemo, useCallback, useState } from 'react';
import { useDiffStore, type DiffFile } from '@/stores/diffStore';
import { StatusBadge, StatBadge, ChangeTypeIcon } from './SharedDiffComponents';
import { SideBySideDiff } from './SideBySideDiff';
import { InlineDiff } from './InlineDiff';

// ── File Tree Sidebar ─────────────────────────────────────────────────

function FileTreeItem({
  file,
  active,
  onClick,
  depth,
}: {
  file: DiffFile;
  active: boolean;
  onClick: () => void;
  depth: number;
}) {
  const [expanded, setExpanded] = useState(true);
  const isDir = false; // All are files in diff

  return (
    <div>
      <button
        onClick={onClick}
        className={`w-full flex items-center gap-2 px-2 py-1.5 text-xs transition-colors ${
          active
            ? 'bg-primary/15 text-primary border-l-2 border-primary'
            : 'text-muted hover:text-foreground hover:bg-accent/5 border-l-2 border-transparent'
        }`}
        style={{ paddingLeft: `${8 + depth * 12}px` }}
      >
        <ChangeTypeIcon type={file.status} />
        <span className="flex-1 truncate text-left">{file.path.split('/').pop()}</span>
        <span className="text-green-400 text-[10px]">+{file.additions}</span>
        <span className="text-red-400 text-[10px]">-{file.deletions}</span>
      </button>
    </div>
  );
}

function FileTree({
  files,
  activePath,
  onSelect,
  collapsed,
  onToggleCollapse,
}: {
  files: DiffFile[];
  activePath: string | null;
  onSelect: (path: string) => void;
  collapsed: boolean;
  onToggleCollapse: () => void;
}) {
  const [query, setQuery] = useState('');

  const totalAdditions = useMemo(() => files.reduce((s, f) => s + f.additions, 0), [files]);
  const totalDeletions = useMemo(() => files.reduce((s, f) => s + f.deletions, 0), [files]);

  const filtered = useMemo(
    () => (query ? files.filter((f) => f.path.toLowerCase().includes(query.toLowerCase())) : files),
    [files, query]
  );

  return (
    <div className={`flex flex-col bg-surface/20 border-r border-border overflow-hidden transition-all duration-200 ${collapsed ? 'w-0 min-w-0' : 'w-60 min-w-[15rem]'}`}>
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-border shrink-0">
        <span className="text-[10px] font-semibold uppercase tracking-wider text-muted/60">
          Files
        </span>
        <button
          onClick={onToggleCollapse}
          className="p-1 rounded hover:bg-accent/10 text-muted hover:text-foreground transition-colors"
          title="Close sidebar"
        >
          <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M11 19l-7-7 7-7m8 14l-7-7 7-7" />
          </svg>
        </button>
      </div>

      {/* Summary */}
      <div className="px-3 py-1.5 border-b border-border bg-surface/20">
        <div className="flex items-center gap-3 text-[10px]">
          <span className="text-muted/60">{files.length} file{files.length !== 1 ? 's' : ''}</span>
          <span className="text-green-400">+{totalAdditions}</span>
          <span className="text-red-400">-{totalDeletions}</span>
        </div>
      </div>

      {/* Filter */}
      <div className="px-2 py-1.5 border-b border-border">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Filter files..."
          className="w-full bg-surface/50 border border-border rounded px-2 py-1 text-[10px] text-foreground placeholder:text-muted/40 focus:outline-none focus:border-primary/50"
        />
      </div>

      {/* File List */}
      <div className="flex-1 overflow-y-auto">
        {filtered.map((file) => (
          <FileTreeItem
            key={file.path}
            file={file}
            active={file.path === activePath}
            onClick={() => onSelect(file.path)}
            depth={file.path.split('/').length - 1}
          />
        ))}
        {filtered.length === 0 && (
          <div className="text-xs text-muted/60 text-center py-8">
            {query ? 'No matching files' : 'No files'}
          </div>
        )}
      </div>
    </div>
  );
}

// ── Main Component ────────────────────────────────────────────────────

export interface MultiFileDiffProps {
  files?: DiffFile[];
  className?: string;
}

export function MultiFileDiff({ files: propFiles, className = '' }: MultiFileDiffProps) {
  const storeFiles = useDiffStore((s) => s.files);
  const activeFilePath = useDiffStore((s) => s.activeFilePath);
  const setActiveFile = useDiffStore((s) => s.setActiveFile);
  const showFileTree = useDiffStore((s) => s.showFileTree);
  const toggleFileTree = useDiffStore((s) => s.toggleFileTree);
  const acceptAll = useDiffStore((s) => s.acceptAll);
  const rejectAll = useDiffStore((s) => s.rejectAll);
  const viewMode = useDiffStore((s) => s.viewMode);

  const files = propFiles || storeFiles;
  const activeFile = files.find((f) => f.path === activeFilePath);

  const handleSelect = useCallback((path: string) => setActiveFile(path), [setActiveFile]);
  const handleAcceptAll = useCallback(() => acceptAll(), [acceptAll]);
  const handleRejectAll = useCallback(() => rejectAll(), [rejectAll]);

  if (files.length === 0) {
    return (
      <div className={`flex items-center justify-center h-48 text-sm text-muted ${className}`}>
        <div className="flex flex-col items-center gap-3">
          <svg className="h-10 w-10 text-muted/30" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
          <span>No changes to display</span>
        </div>
      </div>
    );
  }

  return (
    <div className={`flex h-full ${className}`}>
      {/* Sidebar: File Tree */}
      <FileTree
        files={files}
        activePath={activeFilePath}
        onSelect={handleSelect}
        collapsed={!showFileTree}
        onToggleCollapse={toggleFileTree}
      />

      {/* Main: Diff Content */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Global Toolbar */}
        <div className="flex items-center justify-between px-3 py-1.5 border-b border-border bg-surface/20 shrink-0">
          <div className="flex items-center gap-2">
            {!showFileTree && (
              <button
                onClick={toggleFileTree}
                className="p-1 rounded hover:bg-accent/10 text-muted hover:text-foreground transition-colors"
                title="Show file list"
              >
                <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
                </svg>
              </button>
            )}
            {activeFile && (
              <>
                <StatusBadge status={activeFile.status} />
                <span className="text-sm font-medium truncate">{activeFile.path}</span>
              </>
            )}
          </div>
          <div className="flex items-center gap-2">
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

        {/* Diff Content */}
        <div className="flex-1 min-h-0">
          {viewMode.type === 'side-by-side' ? (
            <SideBySideDiff files={files} />
          ) : (
            <InlineDiff files={files} />
          )}
        </div>
      </div>
    </div>
  );
}
