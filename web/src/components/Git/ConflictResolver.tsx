'use client';

import React, { useMemo, useCallback, useState } from 'react';
import { useGitUIStore, type ConflictFile, type ConflictBlock, type ConflictResolution } from '@/stores/gitUIStore';

// ── Conflict Block Navigation ─────────────────────────────────────────

function ConflictNav({
  total,
  current,
  onPrev,
  onNext,
}: {
  total: number;
  current: number;
  onPrev: () => void;
  onNext: () => void;
}) {
  return (
    <div className="flex items-center gap-2">
      <button
        onClick={onPrev}
        disabled={current <= 0}
        className="p-1 rounded hover:bg-accent/10 text-muted hover:text-foreground transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
      >
        <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
        </svg>
      </button>
      <span className="text-xs text-muted">{current + 1} / {total}</span>
      <button
        onClick={onNext}
        disabled={current >= total - 1}
        className="p-1 rounded hover:bg-accent/10 text-muted hover:text-foreground transition-colors disabled:opacity-30 disabled:cursor-not-allowed"
      >
        <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
        </svg>
      </button>
    </div>
  );
}

// ── Three-Way Merge View ──────────────────────────────────────────────

function ThreeWayView({
  block,
  onResolve,
}: {
  block: ConflictBlock;
  onResolve: (resolution: ConflictResolution) => void;
}) {
  const [manualText, setManualText] = useState(block.manualContent || '');

  const handleResolve = useCallback(
    (resolution: ConflictResolution) => {
      if (resolution === 'manual') {
        onResolve(resolution);
      } else {
        onResolve(resolution);
      }
    },
    [onResolve]
  );

  const handleManualChange = useCallback(
    (e: React.ChangeEvent<HTMLTextAreaElement>) => {
      setManualText(e.target.value);
    },
    []
  );

  const resolution = block.resolution;

  return (
    <div className="space-y-3">
      {/* Resolution Controls */}
      <div className="flex items-center gap-2">
        <span className="text-[10px] font-semibold text-muted/60 uppercase tracking-wider">Resolve using:</span>
        <button
          onClick={() => handleResolve('ours')}
          className={`px-2.5 py-1 text-[10px] font-medium rounded transition-colors ${
            resolution === 'ours'
              ? 'bg-blue-600 text-white shadow-sm'
              : 'bg-surface/50 border border-border text-muted hover:text-foreground hover:bg-accent/10'
          }`}
        >
          Accept Ours
        </button>
        <button
          onClick={() => handleResolve('base')}
          className={`px-2.5 py-1 text-[10px] font-medium rounded transition-colors ${
            resolution === 'base'
              ? 'bg-gray-600 text-white shadow-sm'
              : 'bg-surface/50 border border-border text-muted hover:text-foreground hover:bg-accent/10'
          }`}
        >
          Accept Base
        </button>
        <button
          onClick={() => handleResolve('theirs')}
          className={`px-2.5 py-1 text-[10px] font-medium rounded transition-colors ${
            resolution === 'theirs'
              ? 'bg-purple-600 text-white shadow-sm'
              : 'bg-surface/50 border border-border text-muted hover:text-foreground hover:bg-accent/10'
          }`}
        >
          Accept Theirs
        </button>
        <button
          onClick={() => handleResolve('both')}
          className={`px-2.5 py-1 text-[10px] font-medium rounded transition-colors ${
            resolution === 'both'
              ? 'bg-green-600 text-white shadow-sm'
              : 'bg-surface/50 border border-border text-muted hover:text-foreground hover:bg-accent/10'
          }`}
        >
          Accept Both
        </button>
      </div>

      {/* Three-Way Panels */}
      <div className="grid grid-cols-3 gap-2">
        {/* Ours */}
        <div className="border border-border rounded-md overflow-hidden">
          <div className="px-2 py-1 bg-blue-500/20 text-blue-400 text-[10px] font-semibold border-b border-border">
            Ours
          </div>
          <div className="max-h-40 overflow-y-auto">
            {block.ours.map((line, i) => (
              <div key={i} className="px-2 py-0.5 text-[11px] font-mono leading-5 bg-blue-900/10 border-b border-blue-900/20">
                <span className="text-blue-400/60 select-none mr-2">{i + 1}</span>
                {line}
              </div>
            ))}
          </div>
        </div>

        {/* Base */}
        <div className="border border-border rounded-md overflow-hidden">
          <div className="px-2 py-1 bg-gray-500/20 text-gray-400 text-[10px] font-semibold border-b border-border">
            Base
          </div>
          <div className="max-h-40 overflow-y-auto">
            {block.base.map((line, i) => (
              <div key={i} className="px-2 py-0.5 text-[11px] font-mono leading-5 bg-gray-500/10 border-b border-gray-500/20">
                <span className="text-gray-400/60 select-none mr-2">{i + 1}</span>
                {line}
              </div>
            ))}
          </div>
        </div>

        {/* Theirs */}
        <div className="border border-border rounded-md overflow-hidden">
          <div className="px-2 py-1 bg-purple-500/20 text-purple-400 text-[10px] font-semibold border-b border-border">
            Theirs
          </div>
          <div className="max-h-40 overflow-y-auto">
            {block.theirs.map((line, i) => (
              <div key={i} className="px-2 py-0.5 text-[11px] font-mono leading-5 bg-purple-900/10 border-b border-purple-900/20">
                <span className="text-purple-400/60 select-none mr-2">{i + 1}</span>
                {line}
              </div>
            ))}
          </div>
        </div>
      </div>

      {/* Manual Edit */}
      <div>
        <div className="flex items-center justify-between mb-1">
          <span className="text-[10px] font-semibold text-muted/60 uppercase tracking-wider">
            Result{resolution ? ` (${resolution})` : ''}
          </span>
          {resolution === 'manual' && (
            <span className="text-[10px] text-yellow-400">Editing manually</span>
          )}
        </div>
        <textarea
          value={
            resolution === 'ours'
              ? block.ours.join('\n')
              : resolution === 'base'
              ? block.base.join('\n')
              : resolution === 'theirs'
              ? block.theirs.join('\n')
              : resolution === 'both'
              ? [...block.ours, '=======', ...block.theirs].join('\n')
              : manualText
          }
          onChange={(e) => {
            setManualText(e.target.value);
            // Auto-set resolution to manual when editing
            if (resolution !== 'manual') {
              onResolve('manual');
            }
          }}
          className="w-full bg-surface/50 border border-border rounded px-2.5 py-2 text-[11px] font-mono text-foreground focus:outline-none focus:border-primary/50 resize-none"
          rows={Math.max(3, Math.min(block.ours.length + block.theirs.length, 8))}
          placeholder="Edit the merged result manually..."
        />
      </div>
    </div>
  );
}

// ── File Tab ──────────────────────────────────────────────────────────

function ConflictFileTab({
  file,
  active,
  onClick,
}: {
  file: ConflictFile;
  active: boolean;
  onClick: () => void;
}) {
  const unresolvedCount = file.conflicts.filter((b) => !b.resolution).length;
  return (
    <button
      onClick={onClick}
      className={`flex items-center gap-2 px-3 py-2 text-xs border-b-2 transition-colors whitespace-nowrap ${
        active
          ? 'border-primary text-foreground bg-accent/10'
          : 'border-transparent text-muted hover:text-foreground hover:bg-accent/5'
      }`}
    >
      <span className="truncate max-w-[200px]">{file.path}</span>
      {unresolvedCount > 0 && (
        <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-red-500/20 text-red-400">
          {unresolvedCount}
        </span>
      )}
      {file.resolved && (
        <span className="text-green-400 text-[10px]">✓ Resolved</span>
      )}
    </button>
  );
}

// ── Main Component ────────────────────────────────────────────────────

export interface ConflictResolverProps {
  conflictFiles?: ConflictFile[];
  className?: string;
  onSave?: (filePath: string) => void;
  onCancel?: () => void;
}

export function ConflictResolver({
  conflictFiles: propFiles,
  className = '',
  onSave,
  onCancel,
}: ConflictResolverProps) {
  const storeFiles = useGitUIStore((s) => s.conflictFiles);
  const activeFile = useGitUIStore((s) => s.activeConflictFile);
  const activeBlock = useGitUIStore((s) => s.activeConflictBlock);
  const setActiveFile = useGitUIStore((s) => s.setActiveConflictFile);
  const setActiveBlock = useGitUIStore((s) => s.setActiveConflictBlock);
  const resolveConflict = useGitUIStore((s) => s.resolveConflict);
  const markResolved = useGitUIStore((s) => s.markConflictResolved);

  const files = propFiles || storeFiles;
  const currentFile = files.find((f) => f.path === activeFile) || files[0];

  const totalConflicts = useMemo(
    () => currentFile?.conflicts.length || 0,
    [currentFile]
  );
  const resolvedCount = useMemo(
    () => currentFile?.conflicts.filter((b) => b.resolution).length || 0,
    [currentFile]
  );

  const handleResolve = useCallback(
    (blockId: string, resolution: ConflictResolution) => {
      if (!currentFile) return;
      resolveConflict(currentFile.path, blockId, resolution);
    },
    [currentFile, resolveConflict]
  );

  const handleMarkResolved = useCallback(() => {
    if (!currentFile) return;
    markResolved(currentFile.path);
  }, [currentFile, markResolved]);

  const handlePrev = useCallback(
    () => setActiveBlock(Math.max(0, activeBlock - 1)),
    [activeBlock, setActiveBlock]
  );
  const handleNext = useCallback(
    () => setActiveBlock(Math.min(totalConflicts - 1, activeBlock + 1)),
    [activeBlock, totalConflicts, setActiveBlock]
  );

  if (files.length === 0) {
    return (
      <div className={`flex items-center justify-center h-full text-sm text-muted ${className}`}>
        <div className="flex flex-col items-center gap-2">
          <svg className="h-8 w-8 text-muted/30" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 9v2m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <span>No merge conflicts</span>
        </div>
      </div>
    );
  }

  if (!currentFile) {
    return (
      <div className={`flex items-center justify-center h-full text-sm text-muted ${className}`}>
        Select a conflicting file
      </div>
    );
  }

  const currentBlock = currentFile.conflicts[activeBlock];

  return (
    <div className={`flex flex-col h-full ${className}`}>
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-border bg-surface/30 shrink-0">
        <div className="flex items-center gap-3">
          <span className="text-[10px] font-semibold uppercase tracking-wider text-muted/60">
            Merge Conflict
          </span>
          <span className="text-xs text-muted">
            {resolvedCount} / {totalConflicts} resolved
          </span>
        </div>
        <div className="flex items-center gap-2">
          <ConflictNav
            total={totalConflicts}
            current={activeBlock}
            onPrev={handlePrev}
            onNext={handleNext}
          />
          {onCancel && (
            <button
              onClick={onCancel}
              className="px-2.5 py-1 text-[10px] font-medium rounded border border-border text-muted hover:text-foreground hover:bg-accent/10 transition-colors"
            >
              Cancel
            </button>
          )}
          <button
            onClick={() => {
              if (currentFile) handleMarkResolved();
              if (onSave && currentFile) onSave(currentFile.path);
            }}
            disabled={resolvedCount < totalConflicts}
            className="px-2.5 py-1 text-[10px] font-medium rounded bg-blue-600 hover:bg-blue-700 text-white transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
          >
            Mark Resolved
          </button>
        </div>
      </div>

      {/* File Tabs */}
      {files.length > 1 && (
        <div className="flex border-b border-border overflow-x-auto shrink-0">
          {files.map((file) => (
            <ConflictFileTab
              key={file.path}
              file={file}
              active={file.path === currentFile.path}
              onClick={() => setActiveFile(file.path)}
            />
          ))}
        </div>
      )}

      {/* Current File Info */}
      <div className="px-3 py-1.5 border-b border-border bg-surface/10 shrink-0">
        <span className="text-xs font-medium">{currentFile.path}</span>
        {currentBlock && (
          <span className="text-[10px] text-muted/60 ml-2">
            Conflict block {activeBlock + 1}: lines 
            {currentBlock.ours.length} ours / {currentBlock.base.length} base / {currentBlock.theirs.length} theirs
          </span>
        )}
      </div>

      {/* Conflict Content */}
      <div className="flex-1 overflow-y-auto p-3">
        {currentBlock ? (
          <ThreeWayView
            block={currentBlock}
            onResolve={(resolution) => handleResolve(currentBlock.id, resolution)}
          />
        ) : (
          <div className="flex items-center justify-center h-full text-xs text-muted/60">
            No conflict blocks in this file
          </div>
        )}
      </div>
    </div>
  );
}
