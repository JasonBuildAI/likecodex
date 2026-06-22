'use client';

import { memo, useState } from 'react';
import { ToolCall } from '@/lib/store';

// Tool icon mapping
const TOOL_ICONS: Record<string, string> = {
  read_file: '📄', write_file: '✏️', edit_file: '✏️', replace_in_file: '🔄',
  run_command: '⚡', execute_command: '⚡', shell: '⚡',
  grep_search: '🔍', codebase_search: '🔍', file_search: '🔍',
  list_dir: '📁', create_file: '➕', delete_file: '🗑️',
  git_diff: '📊', git_log: '📜', git_status: '📊',
  web_search: '🌐', web_fetch: '🌐',
};

export const ToolCallCard = memo(function ToolCallCard({ call }: { call: ToolCall }) {
  const [expanded, setExpanded] = useState(false);
  const argsStr = JSON.stringify(call.arguments, null, 2);
  const isLong = argsStr.length > 200;
  const isRunning = call.arguments?.partial === true;
  const icon = TOOL_ICONS[call.name] || '🔧';

  // Extract a short description
  const args = call.arguments || {};
  const shortDesc = String(
    args.path || args.file_path || args.command || args.pattern || args.query || ''
  ).slice(0, 60);

  return (
    <div className="rounded-lg border border-border/60 bg-background/80 overflow-hidden">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-2 w-full text-left px-3 py-2 hover:bg-accent/5 transition-colors"
      >
        {/* Status indicator */}
        <span
          className={`inline-block h-2 w-2 rounded-full shrink-0 ${
            isRunning ? 'bg-yellow-500 animate-pulse' : 'bg-green-500'
          }`}
        />
        {/* Icon */}
        <span className="text-xs shrink-0">{icon}</span>
        {/* Tool name */}
        <span className="text-xs font-medium text-foreground">{call.name}</span>
        {/* Short description */}
        {shortDesc && (
          <span className="text-[10px] text-muted truncate ml-1">{shortDesc}</span>
        )}
        {/* Expand toggle */}
        {isLong && (
          <span className="text-[9px] text-muted/50 ml-auto shrink-0">
            {expanded ? '▼' : '▶'}
          </span>
        )}
      </button>
      {expanded && (
        <div className="border-t border-border/40 px-3 py-2 max-h-48 overflow-auto">
          <pre className="text-[10px] text-muted whitespace-pre-wrap break-all">{argsStr}</pre>
        </div>
      )}
    </div>
  );
});
