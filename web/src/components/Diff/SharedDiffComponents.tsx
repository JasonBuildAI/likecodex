'use client';

import React from 'react';
import { useDiffStore, type DiffFile } from '@/stores/diffStore';

// ── Status Badge ──────────────────────────────────────────────────────

export function StatusBadge({ status }: { status: DiffFile['status'] }) {
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

// ── Stat Badge ────────────────────────────────────────────────────────

export function StatBadge({ additions, deletions }: { additions: number; deletions: number }) {
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

// ── View Mode Toggle ──────────────────────────────────────────────────

export function ViewModeToggle() {
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

// ── Change Type Icon ──────────────────────────────────────────────────

export function ChangeTypeIcon({ type }: { type: DiffFile['status'] }) {
  switch (type) {
    case 'added':
      return <span className="text-green-500 text-sm font-bold">A</span>;
    case 'deleted':
      return <span className="text-red-500 text-sm font-bold">D</span>;
    case 'modified':
      return <span className="text-yellow-500 text-sm font-bold">M</span>;
    case 'renamed':
      return <span className="text-blue-500 text-sm font-bold">R</span>;
    case 'copied':
      return <span className="text-purple-500 text-sm font-bold">C</span>;
    default:
      return <span className="text-muted text-sm">?</span>;
  }
}
