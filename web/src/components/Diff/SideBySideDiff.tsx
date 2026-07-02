'use client';

import React, { useMemo, useState, useCallback } from 'react';
import { useDiffStore, type DiffFile, type DiffHunk } from '@/stores/diffStore';
import dynamic from 'next/dynamic';

// ── Lazy-loaded Monaco Editor ──────────────────────────────────────────

const MonacoDiff = dynamic(
  () => import('@monaco-editor/react').then((mod) => {
    const { DiffEditor } = mod;
    return function MonacoDiffWrapper({
      original,
      modified,
      language,
    }: {
      original: string;
      modified: string;
      language: string;
    }) {
      return (
        <DiffEditor
          height="100%"
          original={original}
          modified={modified}
          language={language}
          theme="vs-dark"
          options={{
            readOnly: true,
            renderSideBySide: true,
            minimap: { enabled: false },
            scrollBeyondLastLine: false,
            fontSize: 12,
            lineNumbers: 'on',
            folding: true,
            wordWrap: 'on',
            padding: { top: 4 },
            renderLineHighlight: 'line',
            ignoreTrimWhitespace: false,
            diffAlgorithm: 'advanced',
          }}
        />
      );
    };
  }),
  { ssr: false, loading: () => <LoadingFallback /> }
);

// ── Sub-components ────────────────────────────────────────────────────

function LoadingFallback() {
  return (
    <div className="flex items-center justify-center h-full text-sm text-muted">
      <div className="flex items-center gap-2">
        <svg className="h-4 w-4 animate-spin" viewBox="0 0 24 24" fill="none">
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
        </svg>
        Loading diff editor...
      </div>
    </div>
  );
}

function CollapseButton({ collapsed, onClick }: { collapsed: boolean; onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className="absolute -left-3 top-1/2 -translate-y-1/2 w-6 h-6 flex items-center justify-center rounded-full bg-surface border border-border text-muted hover:text-foreground hover:bg-accent/10 transition-colors z-10"
      title={collapsed ? 'Expand' : 'Collapse'}
    >
      <svg className={`h-3 w-3 transition-transform ${collapsed ? '' : 'rotate-180'}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 15l7-7 7 7" />
      </svg>
    </button>
  );
}

function StatBadge({ additions, deletions }: { additions: number; deletions: number }) {
  return (
    <div className="flex items-center gap-2 text-xs font-mono">
      <span className="text-green-400 bg-green-500/10 px-1.5 py-0.5 rounded">
        +{additions}
      </span>
      <span className="text-red-400 bg-red-500/10 px-1.5 py-0.5 rounded">
        -{deletions}
      </span>
    </div>
  );
}

function ChangeActionButtons({
  onAccept,
  onReject,
  accepted,
  rejected,
}: {
  onAccept: () => void;
  onReject: () => void;
  accepted: boolean;
  rejected: boolean;
}) {
  return (
    <div className="flex items-center gap-1 opacity-0 group-hover/hunk:opacity-100 transition-opacity">
      <button
        onClick={onAccept}
        disabled={accepted || rejected}
        className={`px-2 py-0.5 text-[10px] font-medium rounded transition-colors ${
          accepted
            ? 'bg-green-600/30 text-green-400 cursor-default'
            : 'bg-green-600/80 hover:bg-green-600 text-white'
        } disabled:opacity-40`}
      >
        {accepted ? '✓' : 'Accept'}
      </button>
      <button
        onClick={onReject}
        disabled={accepted || rejected}
        className={`px-2 py-0.5 text-[10px] font-medium rounded transition-colors ${
          rejected
            ? 'bg-red-600/30 text-red-400 cursor-default'
            : 'bg-red-600/80 hover:bg-red-600 text-white'
        } disabled:opacity-40`}
      >
        {rejected ? '✗' : 'Reject'}
      </button>
    </div>
  );
}

// ── Hunk (Manual) Renderer ────────────────────────────────────────────

function HunkBlock({
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

  const handleToggle = useCallback(() => toggleCollapse(filePath, hunkIndex), [filePath, hunkIndex, toggleCollapse]);
  const handleAccept = useCallback(() => acceptChange(filePath, hunkIndex), [filePath, hunkIndex, acceptChange]);
  const handleReject = useCallback(() => rejectChange(filePath, hunkIndex), [filePath, hunkIndex, rejectChange]);

  if (hunk.collapsed) {
    return (
      <div className="group/hunk relative border border-border rounded-md mb-2 overflow-hidden">
        <div className="flex items-center justify-between px-3 py-1.5 bg-surface/50 text-xs text-muted">
          <button onClick={handleToggle} className="flex items-center gap-2 hover:text-foreground transition-colors">
            <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
            </svg>
            <span>@@ -{hunk.oldStart},{hunk.oldLines} +{hunk.newStart},{hunk.newLines} @@{hunk.header ? ` ${hunk.header}` : ''}</span>
            <span className="text-muted/60">({hunk.lines.length} lines collapsed)</span>
          </button>
          <ChangeActionButtons onAccept={handleAccept} onReject={handleReject} accepted={accepted} rejected={rejected} />
        </div>
      </div>
    );
  }

  return (
    <div className="group/hunk relative border border-border rounded-md mb-2 overflow-hidden">
      <div className="flex items-center justify-between px-3 py-1 bg-surface/30 text-xs text-muted border-b border-border">
        <button onClick={handleToggle} className="flex items-center gap-2 hover:text-foreground transition-colors font-mono">
          <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 15l7-7 7 7" />
          </svg>
          @@ -{hunk.oldStart},{hunk.oldLines} +{hunk.newStart},{hunk.newLines} @@{hunk.header ? ` ${hunk.header}` : ''}
        </button>
        <ChangeActionButtons onAccept={handleAccept} onReject={handleReject} accepted={accepted} rejected={rejected} />
      </div>
      <div className="overflow-x-auto">
        {hunk.lines.map((line, i) => {
          const lineColor =
            line.type === 'add' ? 'bg-green-900/20 border-green-600/40' :
            line.type === 'del' ? 'bg-red-900/20 border-red-600/40' :
            'border-transparent';
          const prefix = line.type === 'add' ? '+' : line.type === 'del' ? '-' : ' ';
          const prefixColor = line.type === 'add' ? 'text-green-500' : line.type === 'del' ? 'text-red-500' : 'text-muted/40';

          return (
            <div key={i} className={`flex border-l-2 ${lineColor} group/line`}>
              <div className="flex-shrink-0 w-[4.5rem] text-right pr-2 text-[10px] leading-6 text-muted/40 font-mono select-none border-r border-border/30">
                {line.oldLineNum !== null ? (
                  <span className="text-red-400/60">{line.oldLineNum}</span>
                ) : (
                  <span className="text-green-400/60">{line.newLineNum}</span>
                )}
              </div>
              <div className="flex-shrink-0 w-[4.5rem] text-right pr-2 text-[10px] leading-6 text-muted/40 font-mono select-none border-r border-border/30">
                {line.newLineNum !== null ? (
                  <span className="text-green-400/60">{line.newLineNum}</span>
                ) : (
                  <span className="text-red-400/60">{line.oldLineNum}</span>
                )}
              </div>
              <span className={`flex-shrink-0 w-5 text-center text-[10px] leading-6 font-mono select-none ${prefixColor}`}>
                {prefix}
              </span>
              <code className="flex-1 text-[11px] leading-6 font-mono pl-2 whitespace-pre overflow-x-auto">
                {line.changedRanges && line.changedRanges.length > 0 ? (
                  <HighlightChanges text={line.content} ranges={line.changedRanges} type={line.type} />
                ) : (
                  line.content || ' '
                )}
              </code>
            </div>
          );
        })}
      </div>
    </div>
  );
}

function HighlightChanges({
  text,
  ranges,
  type,
}: {
  text: string;
  ranges: Array<[number, number]>;
  type: 'add' | 'del' | 'context';
}) {
  if (ranges.length === 0) return <>{text}</>;
  const parts: React.ReactNode[] = [];
  let lastEnd = 0;
  const bg = type === 'add' ? 'bg-green-600/30' : 'bg-red-600/30';

  for (const [start, end] of ranges) {
    if (start > lastEnd) {
      parts.push(<span key={`t-${lastEnd}`}>{text.slice(lastEnd, start)}</span>);
    }
    parts.push(
      <span key={`hl-${start}-${end}`} className={`${bg} rounded px-0.5`}>
        {text.slice(start, end)}
      </span>
    );
    lastEnd = end;
  }
  if (lastEnd < text.length) {
    parts.push(<span key={`t-${lastEnd}`}>{text.slice(lastEnd)}</span>);
  }
  return <>{parts}</>;
}

// ── SideBySide Diff Header ────────────────────────────────────────────

function DiffHeader({
  file,
  onAcceptAll,
  onRejectAll,
}: {
  file: DiffFile;
  onAcceptAll: () => void;
  onRejectAll: () => void;
}) {
  return (
    <div className="flex items-center justify-between px-3 py-2 border-b border-border bg-surface/30 shrink-0">
      <div className="flex items-center gap-3 min-w-0">
        <StatusBadge status={file.status} />
        <span className="text-sm font-medium truncate">{file.path}</span>
        {file.oldPath && file.status === 'renamed' && (
          <span className="text-xs text-muted/60 truncate">(was {file.oldPath})</span>
        )}
        <StatBadge additions={file.additions} deletions={file.deletions} />
      </div>
      <div className="flex items-center gap-2">
        <button
          onClick={onAcceptAll}
          className="px-2.5 py-1 text-[10px] font-medium rounded bg-green-600/80 hover:bg-green-600 text-white transition-colors"
        >
          Accept All
        </button>
        <button
          onClick={onRejectAll}
          className="px-2.5 py-1 text-[10px] font-medium rounded bg-red-600/80 hover:bg-red-600 text-white transition-colors"
        >
          Reject All
        </button>
      </div>
    </div>
  );
}

function StatusBadge({ status }: { status: DiffFile['status'] }) {
  const colorMap: Record<string, string> = {
    added: 'bg-green-500/20 text-green-400 border-green-500/30',
    modified: 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30',
    deleted: 'bg-red-500/20 text-red-400 border-red-500/30',
    renamed: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
    copied: 'bg-purple-500/20 text-purple-400 border-purple-500/30',
  };
  return (
    <span className={`text-[10px] font-medium px-1.5 py-0.5 rounded border ${colorMap[status] || colorMap.modified}`}>
      {status}
    </span>
  );
}

// ── View Mode Toggle ──────────────────────────────────────────────────

function ViewModeToggle() {
  const viewMode = useDiffStore((s) => s.viewMode);
  const setViewMode = useDiffStore((s) => s.setViewMode);

  return (
    <div className="flex items-center gap-0.5 bg-surface/50 rounded-lg p-0.5 border border-border">
      {(['side-by-side', 'inline', 'unified'] as const).map((mode) => (
        <button
          key={mode}
          onClick={() => setViewMode({ type: mode })}
          className={`px-2.5 py-1 text-[10px] font-medium rounded-md transition-colors ${
            viewMode.type === mode
              ? 'bg-primary/20 text-primary shadow-sm'
              : 'text-muted hover:text-foreground'
          }`}
        >
          {mode === 'side-by-side' ? 'Split' : mode === 'inline' ? 'Inline' : 'Unified'}
        </button>
      ))}
    </div>
  );
}

// ── Main Component ────────────────────────────────────────────────────

export interface SideBySideDiffProps {
  files?: DiffFile[];
  className?: string;
}

export function SideBySideDiff({ files: propFiles, className = '' }: SideBySideDiffProps) {
  const storeFiles = useDiffStore((s) => s.files);
  const activeFilePath = useDiffStore((s) => s.activeFilePath);
  const setActiveFile = useDiffStore((s) => s.setActiveFile);
  const acceptAll = useDiffStore((s) => s.acceptAll);
  const rejectAll = useDiffStore((s) => s.rejectAll);
  const acceptedChanges = useDiffStore((s) => s.acceptedChanges);
  const rejectedChanges = useDiffStore((s) => s.rejectedChanges);

  const files = propFiles || storeFiles;
  const activeFile = files.find((f) => f.path === activeFilePath) || files[0];

  // Build original/modified content from hunks
  const { originalContent, modifiedContent } = useMemo(() => {
    if (!activeFile) return { originalContent: '', modifiedContent: '' };
    if (activeFile.oldContent && activeFile.newContent) {
      return { originalContent: activeFile.oldContent, modifiedContent: activeFile.newContent };
    }
    const origLines: string[] = [];
    const modLines: string[] = [];
    let oldOffset = 0;
    let newOffset = 0;
    for (const hunk of activeFile.hunks) {
      // Add context lines before each hunk
      while (oldOffset < hunk.oldStart - 1) {
        origLines.push('');
        modLines.push('');
        oldOffset++;
        newOffset++;
      }
      for (const line of hunk.lines) {
        if (line.type === 'context') {
          origLines.push(line.content);
          modLines.push(line.content);
          oldOffset++;
          newOffset++;
        } else if (line.type === 'del') {
          origLines.push(line.content);
          modLines.push('');
          oldOffset++;
        } else if (line.type === 'add') {
          origLines.push('');
          modLines.push(line.content);
          newOffset++;
        }
      }
    }
    return {
      originalContent: origLines.join('\n'),
      modifiedContent: modLines.join('\n'),
    };
  }, [activeFile]);

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
      <DiffHeader
        file={activeFile}
        onAcceptAll={() => acceptAll(activeFile.path)}
        onRejectAll={() => rejectAll(activeFile.path)}
      />

      {/* Toolbar */}
      <div className="flex items-center justify-between px-3 py-1.5 border-b border-border bg-surface/20 shrink-0">
        <div className="flex items-center gap-2">
          {files.length > 1 && (
            <div className="flex items-center gap-1">
              {files.map((f) => (
                <button
                  key={f.path}
                  onClick={() => setActiveFile(f.path)}
                  className={`text-[10px] px-1.5 py-0.5 rounded transition-colors ${
                    f.path === activeFile.path
                      ? 'bg-primary/20 text-primary'
                      : 'text-muted hover:text-foreground hover:bg-accent/10'
                  }`}
                >
                  {f.path.split('/').pop()}
                </button>
              ))}
            </div>
          )}
        </div>
        <ViewModeToggle />
      </div>

      {/* Monaco Diff Editor for side-by-side view */}
      <div className="flex-1 min-h-0">
        <MonacoDiff
          original={originalContent}
          modified={modifiedContent}
          language={activeFile.language}
        />
      </div>
    </div>
  );
}
