'use client';

import { memo, useMemo, useState, useEffect } from 'react';
import { type ToolCall } from '@/lib/store';

// ── Types ──────────────────────────────────────────────────────────────
export type ToolCallStatus = 'pending' | 'running' | 'waiting_approval' | 'completed' | 'error' | 'cancelled';

export interface ToolCallStreamItem {
  id: string;
  call: ToolCall;
  status: ToolCallStatus;
  startedAt: number;
  completedAt?: number;
  result?: string;
  error?: string;
}

interface ToolCallStreamProps {
  items: ToolCallStreamItem[];
  /** Max visible items before scrolling */
  maxVisible?: number;
}

// ── Tool categorization ────────────────────────────────────────────────
const SEARCH_TOOLS = new Set([
  'grep_search', 'codebase_search', 'file_search', 'search_file',
  'list_dir', 'read_file',
]);

const EDIT_TOOLS = new Set([
  'edit_file', 'write_file', 'create_file', 'replace_in_file', 'delete_file',
]);

const COMMAND_TOOLS = new Set([
  'run_command', 'execute_command', 'shell',
]);

type ToolCategory = 'search' | 'edit' | 'command' | 'other';

function categorize(toolName: string): ToolCategory {
  if (SEARCH_TOOLS.has(toolName)) return 'search';
  if (EDIT_TOOLS.has(toolName)) return 'edit';
  if (COMMAND_TOOLS.has(toolName)) return 'command';
  return 'other';
}

// ── Icon & label mapping ───────────────────────────────────────────────
const CATEGORY_CONFIG: Record<ToolCategory, { icon: string; label: string }> = {
  search: { icon: '🔍', label: 'Search' },
  edit: { icon: '✏️', label: 'Edit' },
  command: { icon: '⚡', label: 'Command' },
  other: { icon: '🔧', label: 'Tool' },
};

const STATUS_STYLES: Record<ToolCallStatus, { dot: string; text: string; badge: string; bgGlow: string }> = {
  pending: {
    dot: 'bg-gray-400',
    text: 'text-gray-400',
    badge: 'bg-gray-500/10 text-gray-400 border-gray-500/20',
    bgGlow: '',
  },
  running: {
    dot: 'bg-yellow-500 animate-pulse',
    text: 'text-yellow-400',
    badge: 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20',
    bgGlow: 'shadow-[0_0_8px_rgba(234,179,8,0.15)]',
  },
  waiting_approval: {
    dot: 'bg-orange-500 animate-pulse',
    text: 'text-orange-400',
    badge: 'bg-orange-500/10 text-orange-400 border-orange-500/20',
    bgGlow: 'shadow-[0_0_8px_rgba(249,115,22,0.15)]',
  },
  completed: {
    dot: 'bg-green-500',
    text: 'text-green-400',
    badge: 'bg-green-500/10 text-green-400 border-green-500/20',
    bgGlow: '',
  },
  error: {
    dot: 'bg-red-500',
    text: 'text-red-400',
    badge: 'bg-red-500/10 text-red-400 border-red-500/20',
    bgGlow: 'shadow-[0_0_8px_rgba(239,68,68,0.1)]',
  },
  cancelled: {
    dot: 'bg-gray-400',
    text: 'text-gray-400',
    badge: 'bg-gray-500/10 text-gray-400 border-gray-500/20',
    bgGlow: '',
  },
};

const STATUS_LABELS: Record<ToolCallStatus, string> = {
  pending: 'Pending...',
  running: 'Running...',
  waiting_approval: '⚠️ Awaiting approval',
  completed: '✅ Done',
  error: '❌ Error',
  cancelled: '⏹️ Cancelled',
};

// ── Lifecycle order for animation ──────────────────────────────────────
const LIFECYCLE_ORDER: ToolCallStatus[] = [
  'pending', 'running', 'waiting_approval', 'completed', 'error', 'cancelled',
];

const LIFECYCLE_INDEX = Object.fromEntries(
  LIFECYCLE_ORDER.map((s, i) => [s, i])
);

// ── Helpers ────────────────────────────────────────────────────────────
function extractShortDesc(args: Record<string, unknown>): string {
  const raw = String(
    args.path || args.file_path || args.command || args.pattern || args.query || ''
  );
  return raw.slice(0, 80);
}

function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
  const m = Math.floor(ms / 60000);
  const s = Math.floor((ms % 60000) / 1000);
  return `${m}m ${s}s`;
}

// ── Live Timer ─────────────────────────────────────────────────────────
function useLiveTimer(startedAt: number, completedAt?: number): string {
  const [now, setNow] = useState(Date.now());

  useEffect(() => {
    if (completedAt) return;
    const id = setInterval(() => setNow(Date.now()), 100);
    return () => clearInterval(id);
  }, [completedAt]);

  const end = completedAt || now;
  return formatDuration(end - startedAt);
}

// ── Single item component ──────────────────────────────────────────────
const StreamItem = memo(function StreamItem({ item }: { item: ToolCallStreamItem }) {
  const [expanded, setExpanded] = useState(false);
  const category = categorize(item.call.name);
  const config = CATEGORY_CONFIG[category];
  const style = STATUS_STYLES[item.status];
  const desc = extractShortDesc(item.call.arguments);
  const timerText = useLiveTimer(item.startedAt, item.completedAt);

  const argsStr = useMemo(
    () => JSON.stringify(item.call.arguments, null, 2),
    [item.call.arguments]
  );

  const handleCopy = () => {
    navigator.clipboard.writeText(argsStr);
  };

  return (
    <div
      className={`flex items-start gap-2.5 px-3 py-2 rounded-lg border transition-all duration-500 ${style.bgGlow} ${
        item.status === 'running'
          ? 'border-border/60 bg-background/80'
          : item.status === 'waiting_approval'
            ? 'border-orange-500/20 bg-orange-500/5'
            : item.status === 'error'
              ? 'border-red-500/20 bg-red-500/5'
              : item.status === 'cancelled'
                ? 'border-border/30 bg-background/30'
                : 'border-border/40 bg-background/40'
      }`}
    >
      {/* Status dot with lifecycle animation */}
      <span className="relative shrink-0 mt-1.5">
        <span
          className={`inline-block h-2.5 w-2.5 rounded-full transition-all duration-500 ${style.dot}`}
          style={{
            transform: `scale(${item.status === 'running' || item.status === 'waiting_approval' ? 1.2 : 1})`,
          }}
        />
        {/* Ripple effect for running */}
        {(item.status === 'running' || item.status === 'waiting_approval') && (
          <span className="absolute inset-0 inline-block h-2.5 w-2.5 rounded-full bg-yellow-500/30 animate-ping" />
        )}
      </span>

      {/* Icon */}
      <span className="text-xs shrink-0 mt-0.5" title={config.label}>
        {config.icon}
      </span>

      {/* Content */}
      <div className="flex-1 min-w-0">
        <button
          onClick={() => setExpanded(!expanded)}
          className="w-full text-left"
        >
          <div className="flex items-center gap-2">
            <span className="text-xs font-medium text-foreground truncate">
              {item.call.name}
            </span>
            {desc && (
              <span className="text-[10px] text-muted truncate">{desc}</span>
            )}
          </div>
        </button>

        {/* Status line with live timer */}
        <div className="flex items-center gap-2 mt-0.5">
          <span className={`text-[10px] ${style.text}`}>
            {STATUS_LABELS[item.status]}
          </span>
          <span className="text-[9px] text-muted/50 font-mono">
            {timerText}
          </span>
        </div>

        {/* Error detail */}
        {item.error && (
          <p className="text-[10px] text-red-400 mt-0.5 truncate">{item.error}</p>
        )}

        {/* Expanded args */}
        {expanded && (
          <div className="mt-2 p-2 rounded bg-background/60 border border-border/40">
            <div className="flex items-center justify-between mb-1">
              <span className="text-[9px] font-medium text-muted">Arguments</span>
              <button
                onClick={(e) => { e.stopPropagation(); handleCopy(); }}
                className="text-[9px] text-muted hover:text-foreground px-1 py-0.5 rounded hover:bg-accent/10 transition-colors"
                title="Copy arguments"
              >
                📋 Copy
              </button>
            </div>
            <pre className="text-[10px] text-muted whitespace-pre-wrap break-all max-h-40 overflow-y-auto">
              {argsStr}
            </pre>
          </div>
        )}
      </div>

      {/* Status badge */}
      <span className={`text-[9px] px-1.5 py-0.5 rounded border shrink-0 ${style.badge}`}>
        {item.status === 'pending' ? '○' :
         item.status === 'running' ? '...' :
         item.status === 'waiting_approval' ? '⚠' :
         item.status === 'completed' ? '✓' :
         item.status === 'error' ? '✗' : '⏹'}
      </span>
    </div>
  );
});

// ── Main component ─────────────────────────────────────────────────────
export const ToolCallStream = memo(function ToolCallStream({
  items,
  maxVisible = 20,
}: ToolCallStreamProps) {
  const visibleItems = useMemo(
    () => items.slice(-maxVisible),
    [items, maxVisible]
  );

  const currentStageIdx = useMemo(() => {
    let maxIdx = 0;
    for (const item of items) {
      const idx = LIFECYCLE_ORDER.indexOf(item.status);
      if (idx > maxIdx) maxIdx = idx;
    }
    return maxIdx;
  }, [items]);

  const pendingCount = useMemo(
    () => items.filter((i) => i.status === 'pending').length,
    [items]
  );

  const runningCount = useMemo(
    () => items.filter((i) => i.status === 'running' || i.status === 'waiting_approval').length,
    [items]
  );

  const completedCount = useMemo(
    () => items.filter((i) => i.status === 'completed').length,
    [items]
  );

  const errorCount = useMemo(
    () => items.filter((i) => i.status === 'error' || i.status === 'cancelled').length,
    [items]
  );

  if (items.length === 0) return null;

  return (
    <div className="flex flex-col gap-1.5">
      {/* Header */}
      <div className="flex items-center justify-between px-1">
        <span className="text-[10px] font-medium text-muted uppercase tracking-wider">
          Tool Calls
        </span>
        <div className="flex items-center gap-2">
          {pendingCount > 0 && (
            <span className="text-[10px] text-gray-400 flex items-center gap-1">
              <span className="inline-block h-1.5 w-1.5 rounded-full bg-gray-400" />
              {pendingCount} pending
            </span>
          )}
          {runningCount > 0 && (
            <span className="text-[10px] text-yellow-400 flex items-center gap-1">
              <span className="inline-block h-1.5 w-1.5 rounded-full bg-yellow-500 animate-pulse" />
              {runningCount} active
            </span>
          )}
          {completedCount > 0 && (
            <span className="text-[10px] text-green-400">
              ✓{completedCount}
            </span>
          )}
          {errorCount > 0 && (
            <span className="text-[10px] text-red-400">
              ✗{errorCount}
            </span>
          )}
        </div>
      </div>

      {/* Lifecycle progress indicator */}
      {items.length > 0 && (
        <div className="flex items-center gap-1 px-1">
          {LIFECYCLE_ORDER.map((stage) => {
            const count = items.filter((it) => it.status === stage).length;
            return (
              <div
                key={stage}
                className={`flex-1 h-1 rounded-full transition-all duration-300 ${
                  count > 0
                    ? stage === 'completed'
                      ? 'bg-green-500'
                      : stage === 'error'
                        ? 'bg-red-500'
                        : stage === 'running'
                          ? 'bg-yellow-500 animate-pulse'
                          : 'bg-gray-500/30'
                    : 'bg-background'
                }`}
                title={`${stage}: ${count}`}
              />
            );
          })}
        </div>
      )}

      {/* Items list */}
      <div className="flex flex-col gap-1 max-h-[400px] overflow-y-auto pr-1 scrollbar-thin">
        {visibleItems.map((item) => (
          <StreamItem key={item.id} item={item} />
        ))}
      </div>

      {/* Overflow indicator */}
      {items.length > maxVisible && (
        <p className="text-[9px] text-muted/50 text-center">
          +{items.length - maxVisible} earlier calls hidden
        </p>
      )}
    </div>
  );
});

export type { ToolCallStreamItem };
