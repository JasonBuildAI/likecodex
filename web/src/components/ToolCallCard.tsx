'use client';

import { memo, useState } from 'react';
import { ToolCall } from '@/lib/store';

// Tool icon mapping (including MCP prefixed tools)
const TOOL_ICONS: Record<string, string> = {
  read_file: '📄', write_file: '✏️', edit_file: '✏️', replace_in_file: '🔄',
  run_command: '⚡', execute_command: '⚡', shell: '⚡',
  grep_search: '🔍', codebase_search: '🔍', file_search: '🔍',
  list_dir: '📁', create_file: '➕', delete_file: '🗑️',
  git_diff: '📊', git_log: '📜', git_status: '📊',
  web_search: '🌐', web_fetch: '🌐',
};

function getIcon(name: string): string {
  if (TOOL_ICONS[name]) return TOOL_ICONS[name];
  if (name.startsWith('mcp__')) return '🔌';
  return '🔧';
}

function parseMcpName(name: string): { server?: string; toolName: string; isMcp: boolean } {
  if (name.startsWith('mcp__')) {
    const parts = name.split('__');
    if (parts.length >= 3) {
      return { server: parts[1], toolName: parts.slice(2).join('__'), isMcp: true };
    }
    return { server: 'unknown', toolName: name, isMcp: true };
  }
  return { toolName: name, isMcp: false };
}

function getStatusColor(status?: string): string {
  switch (status) {
    case 'running': case 'pending': return 'bg-yellow-500 animate-pulse';
    case 'completed': return 'bg-green-500';
    case 'error': case 'cancelled': return 'bg-red-500';
    case 'waiting_approval': return 'bg-blue-500 animate-pulse';
    default: return 'bg-green-500';
  }
}

export const ToolCallCard = memo(function ToolCallCard({
  call,
  status,
  result,
  error,
}: {
  call: ToolCall;
  status?: string;
  result?: string;
  error?: string;
}) {
  const [expanded, setExpanded] = useState(false);
  const argsStr = JSON.stringify(call.arguments, null, 2);
  const isLong = argsStr.length > 200;
  const isRunning = call.arguments?.partial === true || status === 'running' || status === 'pending';
  const icon = getIcon(call.name);
  const { server, toolName, isMcp } = parseMcpName(call.name);

  // Extract a short description
  const args = call.arguments || {};
  const shortDesc = String(
    args.path || args.file_path || args.command || args.pattern || args.query || ''
  ).slice(0, 60);

  return (
    <div className={`rounded-lg border overflow-hidden ${
      error ? 'border-red-500/40 bg-red-500/5' :
      isMcp ? 'border-purple-500/40 bg-purple-500/5' :
      'border-border/60 bg-background/80'
    }`}>
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-2 w-full text-left px-3 py-2 hover:bg-accent/5 transition-colors"
      >
        {/* Status indicator */}
        <span className={`inline-block h-2 w-2 rounded-full shrink-0 ${getStatusColor(status)}`} />
        {/* Icon */}
        <span className="text-xs shrink-0">{icon}</span>
        {/* Tool name */}
        <span className="text-xs font-medium text-foreground">{isMcp ? toolName : call.name}</span>
        {/* MCP server badge */}
        {isMcp && server && (
          <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-purple-500/10 text-purple-400 border border-purple-500/20 shrink-0">
            MCP:{server}
          </span>
        )}
        {/* Short description */}
        {shortDesc && (
          <span className="text-[10px] text-muted truncate ml-1">{shortDesc}</span>
        )}
        {/* Status badge */}
        {status && status !== 'completed' && (
          <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-accent/10 text-muted shrink-0">
            {status}
          </span>
        )}
        {/* Expand toggle */}
        {(isLong || result || error) && (
          <span className="text-[9px] text-muted/50 ml-auto shrink-0">
            {expanded ? '▼' : '▶'}
          </span>
        )}
      </button>
      {expanded && (
        <div className="border-t border-border/40 px-3 py-2 space-y-2 max-h-96 overflow-auto">
          <pre className="text-[10px] text-muted whitespace-pre-wrap break-all">{argsStr}</pre>
          {result && (
            <div>
              <div className="text-[9px] text-muted mb-0.5">Result:</div>
              <pre className="text-[10px] text-green-400 whitespace-pre-wrap break-all bg-green-500/5 rounded p-1.5">{result.slice(0, 2000)}</pre>
            </div>
          )}
          {error && (
            <div>
              <div className="text-[9px] text-muted mb-0.5">Error:</div>
              <pre className="text-[10px] text-red-400 whitespace-pre-wrap break-all bg-red-500/5 rounded p-1.5">{error}</pre>
            </div>
          )}
        </div>
      )}
    </div>
  );
});
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
