'use client';

import React, { useState, useCallback, useMemo } from 'react';
import { useGitUIStore, type StagingEntry } from '@/stores/gitUIStore';
import { useGitStore } from '@/ide/git/gitStore';

// ── Type Icons ────────────────────────────────────────────────────────

function ChangeTypeIcon({ type }: { type: StagingEntry['changeType'] }) {
  const icons: Record<string, { icon: string; color: string }> = {
    modified: { icon: 'M', color: 'text-yellow-400' },
    added: { icon: 'A', color: 'text-green-400' },
    deleted: { icon: 'D', color: 'text-red-400' },
    untracked: { icon: 'U', color: 'text-gray-400' },
    renamed: { icon: 'R', color: 'text-blue-400' },
  };
  const info = icons[type] || { icon: '?', color: 'text-muted' };
  return (
    <span className={`text-[10px] font-bold w-4 text-center ${info.color}`}>
      {info.icon}
    </span>
  );
}

function StagingActionButton({
  label,
  onClick,
  variant,
  disabled,
}: {
  label: string;
  onClick: () => void;
  variant: 'stage' | 'unstage' | 'discard';
  disabled?: boolean;
}) {
  const colors = {
    stage: 'bg-green-600/80 hover:bg-green-600 text-white',
    unstage: 'bg-yellow-600/80 hover:bg-yellow-600 text-white',
    discard: 'bg-red-600/80 hover:bg-red-600 text-white',
  };
  return (
    <button
      onClick={onClick}
      disabled={disabled}
      className={`px-2 py-0.5 text-[10px] font-medium rounded transition-colors ${colors[variant]} disabled:opacity-40 disabled:cursor-not-allowed`}
    >
      {label}
    </button>
  );
}

// ── File Entry ────────────────────────────────────────────────────────

function FileEntry({
  entry,
  onStage,
  onUnstage,
  onDiscard,
  onViewDiff,
}: {
  entry: StagingEntry;
  onStage: () => void;
  onUnstage: () => void;
  onDiscard: () => void;
  onViewDiff: () => void;
}) {
  const [showHunks, setShowHunks] = useState(false);
  const [expanded, setExpanded] = useState(false);

  return (
    <div className="border-b border-border/30 last:border-b-0">
      {/* File Row */}
      <div className="flex items-center gap-2 px-3 py-2 hover:bg-accent/5 transition-colors">
        <button
          onClick={() => {
            setExpanded(!expanded);
            if (entry.hunks && entry.hunks.length > 0) setShowHunks(true);
          }}
          className="p-0.5 rounded hover:bg-accent/10 text-muted transition-colors"
        >
          <svg
            className={`h-3 w-3 transition-transform ${expanded ? 'rotate-90' : ''}`}
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
          </svg>
        </button>
        <ChangeTypeIcon type={entry.changeType} />
        <span className="flex-1 text-xs truncate">{entry.path}</span>
        {entry.oldPath && (
          <span className="text-[9px] text-muted/40 truncate">(was {entry.oldPath})</span>
        )}
        <div className="flex items-center gap-1 flex-shrink-0">
          {entry.staged ? (
            <StagingActionButton label="Unstage" onClick={onUnstage} variant="unstage" />
          ) : (
            <>
              <StagingActionButton label="Stage" onClick={onStage} variant="stage" />
              <StagingActionButton label="Discard" onClick={onDiscard} variant="discard" />
            </>
          )}
          <button
            onClick={onViewDiff}
            className="px-2 py-0.5 text-[10px] font-medium rounded bg-accent/20 hover:bg-accent/30 text-muted hover:text-foreground transition-colors"
          >
            Diff
          </button>
        </div>
      </div>

      {/* Hunk List (expandable) */}
      {expanded && entry.hunks && entry.hunks.length > 0 && (
        <div className="pl-8 pr-3 pb-2 space-y-1">
          {entry.hunks.map((hunk, i) => (
            <div
              key={i}
              className="flex items-center justify-between px-2 py-1 rounded bg-surface/30 text-[10px] font-mono text-muted border border-border/20"
            >
              <span className="truncate">{hunk.header || `Hunk ${i + 1}`}</span>
              <div className="flex items-center gap-1 flex-shrink-0 ml-2">
                {entry.staged ? (
                  <button
                    onClick={() => onUnstage()}
                    className="px-1.5 py-0.5 text-[9px] font-medium rounded bg-yellow-600/60 hover:bg-yellow-600 text-white transition-colors"
                  >
                    Unstage hunk
                  </button>
                ) : (
                  <button
                    onClick={() => onStage()}
                    className="px-1.5 py-0.5 text-[9px] font-medium rounded bg-green-600/60 hover:bg-green-600 text-white transition-colors"
                  >
                    Stage hunk
                  </button>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Commit Input ──────────────────────────────────────────────────────

function CommitInput({ branch }: { branch: string }) {
  const [message, setMessage] = useState('');
  const commit = useGitStore((s) => s.commit);
  const [committing, setCommitting] = useState(false);

  const stagedFiles = useGitUIStore((s) => s.stagedFiles);

  const handleCommit = useCallback(async () => {
    if (!message.trim() || committing) return;
    setCommitting(true);
    const success = await commit(message.trim());
    setCommitting(false);
    if (success) setMessage('');
  }, [message, committing, commit]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
      e.preventDefault();
      handleCommit();
    }
  };

  return (
    <div className="p-3 border-t border-border">
      <div className="flex items-center gap-2 mb-1.5">
        <span className="text-[10px] font-semibold uppercase text-muted/60">Commit</span>
        <span className="text-[10px] text-muted/40">on {branch}</span>
      </div>
      <textarea
        value={message}
        onChange={(e) => setMessage(e.target.value)}
        onKeyDown={handleKeyDown}
        placeholder="Commit message..."
        className="w-full bg-surface/50 border border-border rounded px-2.5 py-2 text-xs text-foreground placeholder:text-muted/40 focus:outline-none focus:border-primary/50 resize-none min-h-[56px]"
        rows={2}
        disabled={committing || stagedFiles.length === 0}
      />
      <div className="flex items-center justify-between mt-1.5">
        <span className="text-[10px] text-muted/40">
          {stagedFiles.length} file{stagedFiles.length !== 1 ? 's' : ''} staged
        </span>
        <button
          onClick={handleCommit}
          disabled={!message.trim() || stagedFiles.length === 0 || committing}
          className="px-3 py-1 text-[10px] font-medium rounded bg-blue-600 hover:bg-blue-700 text-white transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
        >
          {committing ? 'Committing...' : 'Commit'}
        </button>
      </div>
    </div>
  );
}

// ── Search Input ──────────────────────────────────────────────────────

function FileSearchInput({
  value,
  onChange,
  placeholder,
}: {
  value: string;
  onChange: (v: string) => void;
  placeholder: string;
}) {
  return (
    <div className="px-3 py-1.5">
      <input
        type="text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="w-full bg-surface/50 border border-border rounded px-2 py-1 text-[10px] text-foreground placeholder:text-muted/40 focus:outline-none focus:border-primary/50"
      />
    </div>
  );
}

// ── Main Component ────────────────────────────────────────────────────

export interface StagingAreaProps {
  unstagedFiles?: StagingEntry[];
  stagedFiles?: StagingEntry[];
  currentBranch?: string;
  className?: string;
  onStageFile?: (path: string) => void;
  onUnstageFile?: (path: string) => void;
  onStageAll?: () => void;
  onUnstageAll?: () => void;
  onDiscard?: (path: string) => void;
  onViewDiff?: (path: string) => void;
}

export function StagingArea({
  unstagedFiles: propUnstaged,
  stagedFiles: propStaged,
  currentBranch: propBranch,
  className = '',
  onStageFile: propOnStage,
  onUnstageFile: propOnUnstage,
  onStageAll: propOnStageAll,
  onUnstageAll: propOnUnstageAll,
  onDiscard: propOnDiscard,
  onViewDiff: propOnViewDiff,
}: StagingAreaProps) {
  const storeUnstaged = useGitUIStore((s) => s.unstagedFiles);
  const storeStaged = useGitUIStore((s) => s.stagedFiles);
  const storeBranch = useGitStore((s) => s.currentBranch);
  const stageFile = useGitStore((s) => s.stageFile);
  const unstageFile = useGitStore((s) => s.unstageFile);
  const stageAll = useGitStore((s) => s.stageAll);
  const discardChanges = useGitStore((s) => s.discardChanges);
  const selectFile = useGitStore((s) => s.selectFile);

  const unstaged = propUnstaged || storeUnstaged;
  const staged = propStaged || storeStaged;
  const branch = propBranch || storeBranch;

  const [unstagedQuery, setUnstagedQuery] = useState('');
  const [stagedQuery, setStagedQuery] = useState('');

  const filteredUnstaged = useMemo(
    () => (unstagedQuery ? unstaged.filter((f) => f.path.toLowerCase().includes(unstagedQuery.toLowerCase())) : unstaged),
    [unstaged, unstagedQuery]
  );
  const filteredStaged = useMemo(
    () => (stagedQuery ? staged.filter((f) => f.path.toLowerCase().includes(stagedQuery.toLowerCase())) : staged),
    [staged, stagedQuery]
  );

  const handleStage = useCallback(
    (path: string) => (propOnStage ? propOnStage(path) : stageFile(path)),
    [propOnStage, stageFile]
  );
  const handleUnstage = useCallback(
    (path: string) => (propOnUnstage ? propOnUnstage(path) : unstageFile(path)),
    [propOnUnstage, unstageFile]
  );
  const handleDiscard = useCallback(
    (path: string) => (propOnDiscard ? propOnDiscard(path) : discardChanges(path)),
    [propOnDiscard, discardChanges]
  );
  const handleViewDiff = useCallback(
    (path: string) => {
      if (propOnViewDiff) propOnViewDiff(path);
      else selectFile(path, staged.some((f) => f.path === path));
    },
    [propOnViewDiff, selectFile, staged]
  );
  const handleStageAll = useCallback(
    () => (propOnStageAll ? propOnStageAll() : stageAll()),
    [propOnStageAll, stageAll]
  );
  const handleUnstageAll = useCallback(
    () => (propOnUnstageAll ? propOnUnstageAll() : unstaged.forEach((f) => unstageFile(f.path))),
    [propOnUnstageAll, unstageFile, unstaged]
  );

  return (
    <div className={`flex flex-col h-full ${className}`}>
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-border bg-surface/30 shrink-0">
        <span className="text-[10px] font-semibold uppercase tracking-wider text-muted/60">
          Staging Area
        </span>
        <span className="text-[10px] text-muted/40">{branch || 'No repo'}</span>
      </div>

      {/* Unstaged Changes */}
      <div className="flex-1 overflow-y-auto min-h-0">
        <div className="sticky top-0 z-10 bg-surface/80 backdrop-blur-sm">
          <div className="flex items-center justify-between px-3 py-1.5">
            <span className="text-[10px] font-medium text-muted">
              Unstaged ({filteredUnstaged.length})
            </span>
            <button
              onClick={handleStageAll}
              disabled={unstaged.length === 0}
              className="text-[9px] px-1.5 py-0.5 rounded bg-green-600/60 hover:bg-green-600 text-white transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
            >
              Stage All
            </button>
          </div>
          {unstaged.length > 8 && (
            <FileSearchInput value={unstagedQuery} onChange={setUnstagedQuery} placeholder="Filter unstaged files..." />
          )}
        </div>
        {filteredUnstaged.length === 0 ? (
          <div className="flex items-center justify-center h-12 text-[10px] text-muted/40">
            No unstaged changes
          </div>
        ) : (
          filteredUnstaged.map((entry) => (
            <FileEntry
              key={entry.path}
              entry={entry}
              onStage={() => handleStage(entry.path)}
              onUnstage={() => handleUnstage(entry.path)}
              onDiscard={() => handleDiscard(entry.path)}
              onViewDiff={() => handleViewDiff(entry.path)}
            />
          ))
        )}
      </div>

      {/* Divider */}
      <div className="h-px bg-border/60 mx-3" />

      {/* Staged Changes */}
      <div className="flex-1 overflow-y-auto min-h-0">
        <div className="sticky top-0 z-10 bg-surface/80 backdrop-blur-sm">
          <div className="flex items-center justify-between px-3 py-1.5">
            <span className="text-[10px] font-medium text-muted">
              Staged ({filteredStaged.length})
            </span>
            <button
              onClick={handleUnstageAll}
              disabled={staged.length === 0}
              className="text-[9px] px-1.5 py-0.5 rounded bg-yellow-600/60 hover:bg-yellow-600 text-white transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
            >
              Unstage All
            </button>
          </div>
          {staged.length > 8 && (
            <FileSearchInput value={stagedQuery} onChange={setStagedQuery} placeholder="Filter staged files..." />
          )}
        </div>
        {filteredStaged.length === 0 ? (
          <div className="flex items-center justify-center h-12 text-[10px] text-muted/40">
            No staged changes
          </div>
        ) : (
          filteredStaged.map((entry) => (
            <FileEntry
              key={entry.path}
              entry={entry}
              onStage={() => handleStage(entry.path)}
              onUnstage={() => handleUnstage(entry.path)}
              onDiscard={() => handleDiscard(entry.path)}
              onViewDiff={() => handleViewDiff(entry.path)}
            />
          ))
        )}
      </div>

      {/* Commit Input */}
      <CommitInput branch={branch} />
    </div>
  );
}
