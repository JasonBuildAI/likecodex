'use client';

import { memo, useState } from 'react';
import type { Message, ToolCall } from '@/lib/store';

// ── Tool icon & label mapping ─────────────────────────────────────────
const TOOL_META: Record<string, { icon: string; label: string; color: string }> = {
  read_file: { icon: '📄', label: 'Read file', color: 'text-blue-400' },
  write_file: { icon: '✏️', label: 'Write file', color: 'text-green-400' },
  edit_file: { icon: '✏️', label: 'Edit file', color: 'text-green-400' },
  replace_in_file: { icon: '🔄', label: 'Replace in file', color: 'text-green-400' },
  run_command: { icon: '⚡', label: 'Run command', color: 'text-amber-400' },
  execute_command: { icon: '⚡', label: 'Run command', color: 'text-amber-400' },
  shell: { icon: '⚡', label: 'Shell', color: 'text-amber-400' },
  grep_search: { icon: '🔍', label: 'Search', color: 'text-purple-400' },
  codebase_search: { icon: '🔍', label: 'Search code', color: 'text-purple-400' },
  file_search: { icon: '🔍', label: 'Find file', color: 'text-purple-400' },
  list_dir: { icon: '📁', label: 'List directory', color: 'text-blue-400' },
  create_file: { icon: '➕', label: 'Create file', color: 'text-green-400' },
  delete_file: { icon: '🗑️', label: 'Delete file', color: 'text-red-400' },
  git_diff: { icon: '📊', label: 'Git diff', color: 'text-cyan-400' },
  git_log: { icon: '📜', label: 'Git log', color: 'text-cyan-400' },
  git_status: { icon: '📊', label: 'Git status', color: 'text-cyan-400' },
  web_search: { icon: '🌐', label: 'Web search', color: 'text-indigo-400' },
  web_fetch: { icon: '🌐', label: 'Fetch URL', color: 'text-indigo-400' },
  lsp_definition: { icon: '🔗', label: 'Go to definition', color: 'text-blue-400' },
  lsp_references: { icon: '🔗', label: 'Find references', color: 'text-blue-400' },
  lsp_hover: { icon: '💡', label: 'Hover info', color: 'text-blue-400' },
};

const DEFAULT_META = { icon: '🔧', label: 'Tool', color: 'text-muted' };

function getToolMeta(name: string) {
  return TOOL_META[name] || DEFAULT_META;
}

function getToolDescription(call: ToolCall): string {
  const args = call.arguments || {};
  switch (call.name) {
    case 'read_file':
    case 'write_file':
    case 'edit_file':
    case 'replace_in_file':
    case 'create_file':
    case 'delete_file':
      return String(args.path || args.file_path || args.file || '');
    case 'run_command':
    case 'execute_command':
    case 'shell':
      return String(args.command || args.cmd || '').slice(0, 80);
    case 'grep_search':
    case 'codebase_search':
      return String(args.pattern || args.query || args.search || '').slice(0, 60);
    case 'file_search':
      return String(args.pattern || args.query || '').slice(0, 60);
    case 'list_dir':
      return String(args.path || args.dir || '.');
    case 'web_search':
      return String(args.query || '').slice(0, 60);
    case 'web_fetch':
      return String(args.url || '').slice(0, 60);
    case 'lsp_definition':
    case 'lsp_references':
    case 'lsp_hover':
      return `${String(args.file_path || '')}:${String(args.line || '')} ${String(args.symbol || '')}`;
    default:
      return '';
  }
}

// ── Single activity item ──────────────────────────────────────────────
export const ActivityItem = memo(function ActivityItem({
  call,
  isRunning,
  result,
}: {
  call: ToolCall;
  isRunning: boolean;
  result?: string;
}) {
  const [expanded, setExpanded] = useState(false);
  const meta = getToolMeta(call.name);
  const desc = getToolDescription(call);
  const hasResult = result !== undefined;

  return (
    <div className="group">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-2 w-full text-left py-0.5 px-1 rounded hover:bg-accent/5 transition-colors"
      >
        {/* Status indicator */}
        <span className="shrink-0">
          {isRunning ? (
            <span className="inline-block h-3 w-3 rounded-full border-2 border-blue-400 border-t-transparent animate-spin" />
          ) : hasResult ? (
            <span className="inline-block h-3 w-3 rounded-full bg-green-500/80" />
          ) : (
            <span className="text-xs">{meta.icon}</span>
          )}
        </span>
        {/* Tool label */}
        <span className={`text-[11px] font-medium shrink-0 ${meta.color}`}>
          {meta.label}
        </span>
        {/* Description */}
        {desc && (
          <span className="text-[11px] text-muted truncate ml-1">
            {desc}
          </span>
        )}
        {/* Expand indicator */}
        {hasResult && (
          <span className="ml-auto text-[9px] text-muted/40 shrink-0">
            {expanded ? '▼' : '▶'}
          </span>
        )}
      </button>
      {/* Expanded result */}
      {expanded && hasResult && (
        <div className="ml-5 mt-1 mb-2 p-2 rounded bg-background/50 border border-border/50 max-h-48 overflow-auto">
          <pre className="text-[10px] text-muted whitespace-pre-wrap break-all">{result}</pre>
        </div>
      )}
      {/* Expanded arguments (when no result yet) */}
      {expanded && !hasResult && (
        <div className="ml-5 mt-1 mb-2 p-2 rounded bg-background/50 border border-border/50 max-h-32 overflow-auto">
          <pre className="text-[10px] text-muted whitespace-pre-wrap break-all">
            {JSON.stringify(call.arguments, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
});

// ── Activity stream: groups consecutive tool messages ──────────────────
export interface ActivityEntry {
  call: ToolCall;
  isRunning: boolean;
  result?: string;
}

export function extractActivities(messages: Message[]): ActivityEntry[] {
  const activities: ActivityEntry[] = [];
  const resultMap = new Map<string, string>();

  // Build result map from tool_result messages
  for (const msg of messages) {
    if (msg.eventType === 'tool_result' && msg.toolCalls?.[0]) {
      const key = msg.toolCalls[0].id || msg.toolCalls[0].name;
      resultMap.set(key, msg.content);
    }
  }

  // Collect tool calls
  for (const msg of messages) {
    if ((msg.eventType === 'tool_call' || msg.eventType === 'tool_dispatch') && msg.toolCalls?.[0]) {
      const call = msg.toolCalls[0];
      const key = call.id || call.name;
      const isRunning = msg.eventType === 'tool_dispatch' || call.arguments?.partial === true;
      activities.push({
        call,
        isRunning,
        result: resultMap.get(key),
      });
    }
  }

  return activities;
}

// ── AgentActivity panel (renders inline in chat) ──────────────────────
export const AgentActivity = memo(function AgentActivity({
  activities,
}: {
  activities: ActivityEntry[];
}) {
  if (activities.length === 0) return null;

  const runningCount = activities.filter((a) => a.isRunning).length;
  const completedCount = activities.filter((a) => a.result !== undefined).length;

  return (
    <div className="my-2 rounded-lg border border-border/60 bg-surface/30 overflow-hidden">
      {/* Header */}
      <div className="flex items-center gap-2 px-3 py-1.5 border-b border-border/40 bg-surface/50">
        <svg className="h-3.5 w-3.5 text-blue-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
        </svg>
        <span className="text-[11px] font-medium text-foreground">Agent Activity</span>
        <span className="text-[10px] text-muted">
          {runningCount > 0 ? (
            <span className="text-blue-400">{runningCount} running</span>
          ) : (
            <span>{completedCount} completed</span>
          )}
        </span>
      </div>
      {/* Activity list */}
      <div className="px-2 py-1 max-h-64 overflow-y-auto">
        {activities.map((activity, i) => (
          <ActivityItem
            key={activity.call.id || activity.call.name || i}
            call={activity.call}
            isRunning={activity.isRunning}
            result={activity.result}
          />
        ))}
      </div>
    </div>
  );
});
