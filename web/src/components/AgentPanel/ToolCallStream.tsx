'use client';

import { memo, useMemo } from 'react';
import { type ToolCall } from '@/lib/store';

// ── Types ──────────────────────────────────────────────────────────────
export type ToolCallStatus = 'running' | 'waiting_approval' | 'completed' | 'error';

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

const STATUS_STYLES: Record<ToolCallStatus, { dot: string; text: string; badge: string }> = {
  running: {
    dot: 'bg-yellow-500 animate-pulse',
    text: 'text-yellow-400',
    badge: 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20',
  },
  waiting_approval: {
    dot: 'bg-orange-500 animate-pulse',
    text: 'text-orange-400',
    badge: 'bg-orange-500/10 text-orange-400 border-orange-500/20',
  },
  completed: {
    dot: 'bg-green-500',
    text: 'text-green-400',
    badge: 'bg-green-500/10 text-green-400 border-green-500/20',
  },
  error: {
    dot: 'bg-red-500',
    text: 'text-red-400',
    badge: 'bg-red-500/10 text-red-400 border-red-500/20',
  },
};

const STATUS_LABELS: Record<ToolCallStatus, string> = {
  running: 'Running…',
  waiting_approval: '⚠️ Awaiting approval',
  completed: '✅ Done',
  error: '❌ Error',
};

// ── Helpers ────────────────────────────────────────────────────────────
function extractShortDesc(args: Record<string, unknown>): string {
  const raw = String(
    args.path || args.file_path || args.command || args.pattern || args.query || ''
  );
  return raw.slice(0, 80);
}

function formatDuration(start: number, end?: number): string {
  const ms = (end ?? Date.now()) - start;
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(1)}s`;
}

// ── Single item component ──────────────────────────────────────────────
const StreamItem = memo(function StreamItem({ item }: { item: ToolCallStreamItem }) {
  const category = categorize(item.call.name);
  const config = CATEGORY_CONFIG[category];
  const style = STATUS_STYLES[item.status];
  const desc = extractShortDesc(item.call.arguments);

  return (
    <div
      className={`flex items-start gap-2.5 px-3 py-2 rounded-lg border transition-colors ${
        item.status === 'running'
          ? 'border-border/60 bg-background/80'
          : item.status === 'waiting_approval'
            ? 'border-orange-500/20 bg-orange-500/5'
            : 'border-border/40 bg-background/40'
      }`}
    >
      {/* Status dot */}
      <span className={`inline-block h-2 w-2 rounded-full shrink-0 mt-1.5 ${style.dot}`} />

      {/* Icon */}
      <span className="text-xs shrink-0 mt-0.5" title={config.label}>
        {config.icon}
      </span>

      {/* Content */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-2">
          <span className="text-xs font-medium text-foreground truncate">
            {item.call.name}
          </span>
          {desc && (
            <span className="text-[10px] text-muted truncate">{desc}</span>
          )}
        </div>

        {/* Status line */}
        <div className="flex items-center gap-2 mt-0.5">
          <span className={`text-[10px] ${style.text}`}>
            {STATUS_LABELS[item.status]}
          </span>
          <span className="text-[9px] text-muted/50">
            {formatDuration(item.startedAt, item.completedAt)}
          </span>
        </div>

        {/* Error detail */}
        {item.error && (
          <p className="text-[10px] text-red-400 mt-0.5 truncate">{item.error}</p>
        )}
      </div>

      {/* Status badge */}
      <span className={`text-[9px] px-1.5 py-0.5 rounded border shrink-0 ${style.badge}`}>
        {item.status === 'running' ? '…' : item.status === 'waiting_approval' ? '⚠' : item.status === 'completed' ? '✓' : '✗'}
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

  const runningCount = useMemo(
    () => items.filter((i) => i.status === 'running' || i.status === 'waiting_approval').length,
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
        {runningCount > 0 && (
          <span className="text-[10px] text-yellow-400 flex items-center gap-1">
            <span className="inline-block h-1.5 w-1.5 rounded-full bg-yellow-500 animate-pulse" />
            {runningCount} active
          </span>
        )}
      </div>

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
