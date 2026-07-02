'use client';

import React, { useMemo, useCallback, useState } from 'react';
import { useGitUIStore, type GitCommitNode, type GitGraphLayout } from '@/stores/gitUIStore';

// ── Color Palette for Graph Lines ────────────────────────────────────

const GRAPH_COLORS = [
  '#4f86e6', '#34d399', '#f472b6', '#a78bfa', '#fbbf24',
  '#60a5fa', '#fb923c', '#e879f9', '#22d3ee', '#f87171',
  '#a3e635', '#c084fc', '#38bdf8', '#fb7185', '#4ade80',
];

function getColor(index: number): string {
  return GRAPH_COLORS[index % GRAPH_COLORS.length];
}

// ── Graph SVG Renderer ────────────────────────────────────────────────

function GraphSVG({
  layout,
  commitHeight,
  selectedHash,
  onSelectCommit,
}: {
  layout: GitGraphLayout;
  commitHeight: number;
  selectedHash: string | null;
  onSelectCommit: (hash: string) => void;
}) {
  const colWidth = 24;
  const padding = 12;
  const nodeRadius = 4;

  const svgWidth = layout.maxColumns * colWidth + padding * 2;
  const svgHeight = layout.commits.length * commitHeight + commitHeight;

  return (
    <svg
      width={svgWidth}
      height={svgHeight}
      className="flex-shrink-0"
      style={{ minWidth: svgWidth }}
    >
      {/* Connections (lines drawn first, under nodes) */}
      {layout.connections.map((conn, i) => {
        const fromIdx = layout.commits.findIndex((c) => c.hash === conn.fromCommit);
        const toIdx = layout.commits.findIndex((c) => c.hash === conn.toCommit);
        if (fromIdx < 0 || toIdx < 0) return null;

        const x1 = padding + conn.fromColumn * colWidth + colWidth / 2;
        const y1 = fromIdx * commitHeight + commitHeight / 2;
        const x2 = padding + conn.toColumn * colWidth + colWidth / 2;
        const y2 = toIdx * commitHeight + commitHeight / 2;

        const midY = (y1 + y2) / 2;

        return (
          <path
            key={`conn-${i}`}
            d={`M ${x1} ${y1} C ${x1} ${midY}, ${x2} ${midY}, ${x2} ${y2}`}
            fill="none"
            stroke={getColor(conn.colorIndex)}
            strokeWidth={2}
            strokeOpacity={0.6}
          />
        );
      })}

      {/* Commit nodes */}
      {layout.commits.map((commit, idx) => {
        const x = padding + commit.column * colWidth + colWidth / 2;
        const y = idx * commitHeight + commitHeight / 2;
        const isSelected = commit.hash === selectedHash;
        const color = getColor(commit.column);

        return (
          <g
            key={commit.hash}
            onClick={() => onSelectCommit(commit.hash)}
            className="cursor-pointer"
          >
            {/* Node circle */}
            <circle
              cx={x}
              cy={y}
              r={isSelected ? nodeRadius + 2 : nodeRadius}
              fill={isSelected ? color : '#1e293b'}
              stroke={color}
              strokeWidth={isSelected ? 2.5 : 1.5}
              className="transition-all duration-150"
            />
            {/* Branch indicator (diamond for merge commits) */}
            {commit.parents.length > 1 && (
              <polygon
                points={`${x - 2},${y - 5} ${x + 2},${y} ${x - 2},${y + 5}`}
                fill={color}
                opacity={0.4}
              />
            )}
          </g>
        );
      })}
    </svg>
  );
}

// ── Commit Row ────────────────────────────────────────────────────────

const COMMIT_HEIGHT = 48;

function CommitRow({
  commit,
  layout,
  isSelected,
  onSelect,
}: {
  commit: GitCommitNode;
  layout: GitGraphLayout;
  isSelected: boolean;
  onSelect: (hash: string) => void;
}) {
  const timeAgo = useMemo(() => {
    const diff = Date.now() - commit.timestamp * 1000;
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return 'just now';
    if (mins < 60) return `${mins}m ago`;
    const hours = Math.floor(mins / 60);
    if (hours < 24) return `${hours}h ago`;
    const days = Math.floor(hours / 24);
    if (days < 30) return `${days}d ago`;
    return commit.date;
  }, [commit.timestamp, commit.date]);

  return (
    <div
      onClick={() => onSelect(commit.hash)}
      className={`flex items-stretch h-12 border-b border-border/30 cursor-pointer transition-colors hover:bg-accent/5 ${
        isSelected ? 'bg-primary/10' : ''
      }`}
    >
      {/* Graph column is handled by the SVG overlay */}
      <div className="flex items-center gap-3 px-3 min-w-0 flex-1">
        {/* Short hash */}
        <span className="text-[10px] font-mono text-muted/60 flex-shrink-0 w-16">
          {commit.shortHash}
        </span>
        {/* Message */}
        <span className="flex-1 text-xs truncate">{commit.message}</span>
        {/* Author */}
        <span className="text-[10px] text-muted/60 flex-shrink-0 truncate max-w-[120px]">
          {commit.author}
        </span>
        {/* Date */}
        <span className="text-[10px] text-muted/40 flex-shrink-0 w-16 text-right">
          {timeAgo}
        </span>
        {/* Refs/Branches */}
        {commit.refs.length > 0 && (
          <div className="flex items-center gap-1 flex-shrink-0">
            {commit.refs.slice(0, 3).map((ref, i) => (
              <span
                key={`ref-${i}`}
                className={`text-[9px] font-medium px-1.5 py-0.5 rounded-full border ${
                  ref.type === 'branch'
                    ? 'bg-blue-500/20 text-blue-400 border-blue-500/30'
                    : ref.type === 'tag'
                    ? 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30'
                    : 'bg-purple-500/20 text-purple-400 border-purple-500/30'
                }`}
              >
                {ref.name}
              </span>
            ))}
            {commit.refs.length > 3 && (
              <span className="text-[9px] text-muted/40">+{commit.refs.length - 3}</span>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// ── Commit Detail Panel ───────────────────────────────────────────────

function CommitDetailPanel({
  commit,
  onClose,
}: {
  commit: GitCommitNode;
  onClose: () => void;
}) {
  return (
    <div className="border-t border-border bg-surface/50">
      <div className="flex items-center justify-between px-3 py-2 border-b border-border">
        <span className="text-xs font-semibold">Commit Details</span>
        <button
          onClick={onClose}
          className="p-1 rounded hover:bg-accent/10 text-muted hover:text-foreground transition-colors"
        >
          <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>
      <div className="p-3 space-y-2 text-xs">
        <div className="flex items-center gap-3">
          <span className="text-muted/60 w-16">Hash</span>
          <span className="font-mono text-foreground">{commit.hash}</span>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-muted/60 w-16">Author</span>
          <span className="text-foreground">{commit.author} &lt;{commit.authorEmail}&gt;</span>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-muted/60 w-16">Date</span>
          <span className="text-foreground">{commit.date}</span>
        </div>
        <div className="flex items-start gap-3">
          <span className="text-muted/60 w-16 shrink-0">Message</span>
          <span className="text-foreground whitespace-pre-wrap">{commit.message}</span>
        </div>
        {commit.parents.length > 0 && (
          <div className="flex items-center gap-3">
            <span className="text-muted/60 w-16">Parents</span>
            <span className="font-mono text-foreground">{commit.parents.map((p) => p.slice(0, 7)).join(', ')}</span>
          </div>
        )}
        {commit.branch && (
          <div className="flex items-center gap-3">
            <span className="text-muted/60 w-16">Branch</span>
            <span className="text-blue-400">{commit.branch}</span>
          </div>
        )}
        {commit.refs.length > 0 && (
          <div className="flex items-center gap-3">
            <span className="text-muted/60 w-16">Refs</span>
            <div className="flex items-center flex-wrap gap-1">
              {commit.refs.map((ref, i) => (
                <span
                  key={i}
                  className={`text-[9px] font-medium px-1.5 py-0.5 rounded-full border ${
                    ref.type === 'branch'
                      ? 'bg-blue-500/20 text-blue-400 border-blue-500/30'
                      : ref.type === 'tag'
                      ? 'bg-yellow-500/20 text-yellow-400 border-yellow-500/30'
                      : 'bg-purple-500/20 text-purple-400 border-purple-500/30'
                  }`}
                >
                  {ref.name}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ── Main Component ────────────────────────────────────────────────────

export interface GitGraphProps {
  layout?: GitGraphLayout;
  loading?: boolean;
  error?: string | null;
  className?: string;
}

export function GitGraph({
  layout: propLayout,
  loading: propLoading,
  error: propError,
  className = '',
}: GitGraphProps) {
  const storeLayout = useGitUIStore((s) => s.graphLayout);
  const storeLoading = useGitUIStore((s) => s.graphLoading);
  const storeError = useGitUIStore((s) => s.graphError);
  const selectedCommit = useGitUIStore((s) => s.selectedCommit);
  const commitDetailOpen = useGitUIStore((s) => s.commitDetailOpen);
  const selectCommit = useGitUIStore((s) => s.selectCommit);
  const setCommitDetailOpen = useGitUIStore((s) => s.setCommitDetailOpen);

  const layout = propLayout || storeLayout;
  const loading = propLoading ?? storeLoading;
  const error = propError ?? storeError;

  const [selectedHash, setSelectedHash] = useState<string | null>(null);

  const handleSelect = useCallback(
    (hash: string) => {
      const commit = layout?.commits.find((c) => c.hash === hash);
      if (commit) {
        selectCommit(commit);
        setSelectedHash(hash);
        setCommitDetailOpen(true);
      }
    },
    [layout, selectCommit, setCommitDetailOpen]
  );

  const handleCloseDetail = useCallback(() => {
    setCommitDetailOpen(false);
    selectCommit(null);
  }, [setCommitDetailOpen, selectCommit]);

  // Loading state
  if (loading) {
    return (
      <div className={`flex items-center justify-center h-full ${className}`}>
        <div className="flex flex-col items-center gap-2">
          <svg className="h-6 w-6 animate-spin text-muted" viewBox="0 0 24 24" fill="none">
            <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
            <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
          </svg>
          <span className="text-xs text-muted">Loading commit history...</span>
        </div>
      </div>
    );
  }

  // Error state
  if (error) {
    return (
      <div className={`flex items-center justify-center h-full ${className}`}>
        <div className="flex flex-col items-center gap-2 text-xs text-red-400">
          <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
          </svg>
          <span>Failed to load git graph: {error}</span>
        </div>
      </div>
    );
  }

  // Empty
  if (!layout || layout.commits.length === 0) {
    return (
      <div className={`flex items-center justify-center h-full text-xs text-muted/60 ${className}`}>
        <div className="flex flex-col items-center gap-2">
          <svg className="h-8 w-8 text-muted/30" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
          </svg>
          <span>No commits found</span>
        </div>
      </div>
    );
  }

  return (
    <div className={`flex flex-col h-full ${className}`}>
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-border bg-surface/30 shrink-0">
        <span className="text-[10px] font-semibold uppercase tracking-wider text-muted/60">
          Git Graph
        </span>
        <span className="text-[10px] text-muted/40">
          {layout.commits.length} commit{layout.commits.length !== 1 ? 's' : ''}
        </span>
      </div>

      {/* Column Headers */}
      <div className="flex items-stretch border-b border-border/30 bg-surface/10 shrink-0">
        <div className="flex items-center gap-3 px-3 py-1.5 flex-1">
          <span className="text-[9px] font-medium text-muted/40 uppercase w-16">Hash</span>
          <span className="text-[9px] font-medium text-muted/40 uppercase flex-1">Message</span>
          <span className="text-[9px] font-medium text-muted/40 uppercase w-[120px]">Author</span>
          <span className="text-[9px] font-medium text-muted/40 uppercase w-16 text-right">Date</span>
        </div>
      </div>

      {/* Commit List with Graph Overlay */}
      <div className="flex-1 overflow-y-auto">
        <div className="relative">
          {/* SVG Graph Layer (absolutely positioned) */}
          <div className="absolute top-0 left-0 bottom-0 pointer-events-none z-10">
            <GraphSVG
              layout={layout}
              commitHeight={COMMIT_HEIGHT}
              selectedHash={selectedHash}
              onSelectCommit={handleSelect}
            />
          </div>
          {/* Commit Rows Layer */}
          <div className="relative z-20" style={{ marginLeft: layout.maxColumns * 24 + 24 }}>
            {layout.commits.map((commit) => (
              <CommitRow
                key={commit.hash}
                commit={commit}
                layout={layout}
                isSelected={commit.hash === selectedHash}
                onSelect={handleSelect}
              />
            ))}
          </div>
        </div>
      </div>

      {/* Commit Detail Panel */}
      {commitDetailOpen && selectedCommit && (
        <CommitDetailPanel commit={selectedCommit} onClose={handleCloseDetail} />
      )}
    </div>
  );
}
