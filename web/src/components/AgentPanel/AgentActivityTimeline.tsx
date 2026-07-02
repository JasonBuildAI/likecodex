'use client';

import React, { useMemo } from 'react';
import type { ToolCallStreamItem } from '@/lib/store';

// ── Props ──────────────────────────────────────────────────────────────
interface AgentActivityTimelineProps {
  activeToolCalls: ToolCallStreamItem[];
  isStreaming: boolean;
  variant: 'full' | 'compact';
}

// ── Helpers ────────────────────────────────────────────────────────────
function formatTime(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
  return `${Math.floor(ms / 60000)}m ${Math.floor((ms % 60000) / 1000)}s`;
}

function isSubAgent(toolName: string): boolean {
  return toolName.startsWith('subagent_') || toolName.includes('delegate') || toolName.includes('sub_agent');
}

// ── Step Item ──────────────────────────────────────────────────────────
const TimelineStep = React.memo(function TimelineStep({
  item,
  index,
  maxDuration,
  isSub,
}: {
  item: ToolCallStreamItem;
  index: number;
  maxDuration: number;
  isSub: boolean;
}) {
  const duration = item.completedAt
    ? item.completedAt - item.startedAt
    : Date.now() - item.startedAt;

  const barWidth = maxDuration > 0 ? (duration / maxDuration) * 100 : 0;

  const isRunning = item.status === 'running' || item.status === 'waiting_approval';
  const isCompleted = item.status === 'completed';
  const isError = item.status === 'error' || item.status === 'cancelled';

  const statusColor = isRunning
    ? 'bg-yellow-500'
    : isError
      ? 'bg-red-500'
      : 'bg-green-500';

  const barColor = isRunning
    ? 'bg-gradient-to-r from-yellow-500 to-amber-400'
    : isError
      ? 'bg-gradient-to-r from-red-500 to-red-400'
      : 'bg-gradient-to-r from-emerald-500 to-green-400';

  return (
    <div className={`flex items-start gap-2 py-1 group ${isSub ? 'ml-5 pl-3 border-l-2 border-border/30' : ''}`}>
      {/* Step number */}
      <div className="flex items-center gap-1.5 shrink-0 mt-0.5">
        <span className={`inline-flex items-center justify-center w-4 h-4 rounded-full text-[8px] font-bold 
          ${isRunning ? 'bg-yellow-500/20 text-yellow-400' : isError ? 'bg-red-500/20 text-red-400' : 'bg-green-500/20 text-green-400'}
        `}>
          {index + 1}
        </span>
      </div>

      {/* Content */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-1.5">
          {isSub && (
            <span className="text-[9px] text-muted/50 font-medium">⊳</span>
          )}
          <span className={`text-[11px] font-medium truncate ${
            isRunning ? 'text-yellow-400' : isError ? 'text-red-400' : 'text-foreground/90'
          }`}>
            {item.call.name}
          </span>
          <span className="text-[9px] text-muted/50 font-mono ml-auto shrink-0">
            {formatTime(duration)}
          </span>
        </div>

        {/* Duration bar */}
        <div className="mt-0.5 h-1.5 bg-background rounded-full overflow-hidden">
          <div
            className={`h-full rounded-full transition-all duration-500 ${isRunning ? 'animate-pulse' : ''} ${barColor}`}
            style={{ width: `${Math.min(100, barWidth)}%` }}
          />
        </div>

        {/* Description */}
        {item.call.arguments && (
          <div className="text-[9px] text-muted/50 truncate mt-0.5">
            {String(
              item.call.arguments.path ||
              item.call.arguments.file_path ||
              item.call.arguments.command ||
              item.call.arguments.pattern ||
              item.call.arguments.query ||
              ''
            ).slice(0, 60)}
          </div>
        )}
      </div>

      {/* Status dot */}
      <span className={`inline-block h-1.5 w-1.5 rounded-full shrink-0 mt-1.5 ${statusColor} ${isRunning ? 'animate-pulse' : ''}`} />
    </div>
  );
});

// ── Main Component ──────────────────────────────────────────────────────
export const AgentActivityTimeline: React.FC<AgentActivityTimelineProps> = ({
  activeToolCalls,
  isStreaming,
  variant,
}) => {
  const runningCount = useMemo(
    () => activeToolCalls.filter((i) => i.status === 'running' || i.status === 'waiting_approval').length,
    [activeToolCalls]
  );

  const completedCount = useMemo(
    () => activeToolCalls.filter((i) => i.status === 'completed').length,
    [activeToolCalls]
  );

  const errorCount = useMemo(
    () => activeToolCalls.filter((i) => i.status === 'error' || i.status === 'cancelled').length,
    [activeToolCalls]
  );

  const totalDuration = useMemo(() => {
    if (activeToolCalls.length === 0) return 0;
    const first = activeToolCalls[0].startedAt;
    const last = activeToolCalls[activeToolCalls.length - 1];
    return (last.completedAt || Date.now()) - first;
  }, [activeToolCalls]);

  const maxDuration = useMemo(() => {
    let max = 0;
    for (const item of activeToolCalls) {
      const d = item.completedAt ? item.completedAt - item.startedAt : 1000;
      if (d > max) max = d;
    }
    return max || 1;
  }, [activeToolCalls]);

  if (activeToolCalls.length === 0 && !isStreaming) {
    if (variant === 'full') {
      return (
        <div className="text-center py-8 text-muted/50">
          <svg className="h-8 w-8 mx-auto mb-2 opacity-40" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
          </svg>
          <p className="text-[10px]">Agent activity will appear here</p>
        </div>
      );
    }
    return null;
  }

  return (
    <div className="space-y-2">
      {/* Summary bar */}
      <div className="flex items-center justify-between px-1">
        <span className="text-[10px] font-medium text-muted uppercase tracking-wider flex items-center gap-1.5">
          Activity
          {activeToolCalls.length > 0 && (
            <span className="text-[9px] font-normal text-muted/50">#{activeToolCalls.length}</span>
          )}
          {isStreaming && (
            <span className="inline-block h-1.5 w-1.5 rounded-full bg-blue-500 animate-pulse" />
          )}
        </span>
        <div className="flex items-center gap-2 text-[9px] text-muted/60">
          {runningCount > 0 && (
            <span className="text-yellow-400">{runningCount} running</span>
          )}
          {completedCount > 0 && (
            <span className="text-green-400">{completedCount} done</span>
          )}
          {errorCount > 0 && (
            <span className="text-red-400">{errorCount} failed</span>
          )}
          {totalDuration > 0 && (
            <span>{formatTime(totalDuration)}</span>
          )}
        </div>
      </div>

      {/* Progress bar */}
      {activeToolCalls.length > 0 && (
        <div className="h-1 bg-background rounded-full overflow-hidden">
          <div
            className="h-full bg-gradient-to-r from-blue-500 to-green-500 rounded-full transition-all duration-500"
            style={{
              width: `${Math.round((completedCount / activeToolCalls.length) * 100)}%`,
            }}
          />
        </div>
      )}

      {/* Timeline steps */}
      {variant === 'full' && activeToolCalls.length > 0 && (
        <div className="space-y-0.5 px-1">
          {activeToolCalls.map((item, i) => (
            <TimelineStep
              key={item.id}
              item={item}
              index={i}
              maxDuration={maxDuration}
              isSub={isSubAgent(item.call.name)}
            />
          ))}
        </div>
      )}

      {/* Status indicators for compact mode */}
      {variant === 'compact' && activeToolCalls.length > 0 && (
        <div className="flex flex-wrap gap-1">
          {activeToolCalls.slice(-8).map((item) => (
            <span
              key={item.id}
              className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full text-[9px] font-medium border ${
                item.status === 'running'
                  ? 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20 animate-pulse'
                  : item.status === 'completed'
                    ? 'bg-green-500/10 text-green-400 border-green-500/20'
                    : item.status === 'error'
                      ? 'bg-red-500/10 text-red-400 border-red-500/20'
                      : 'bg-orange-500/10 text-orange-400 border-orange-500/20'
              }`}
            >
              <span
                className={`h-1 w-1 rounded-full ${
                  item.status === 'running' ? 'bg-yellow-500 animate-pulse' : 'bg-current'
                }`}
              />
              {item.call.name}
            </span>
          ))}
          {activeToolCalls.length > 8 && (
            <span className="text-[9px] text-muted/50 px-1 self-center">
              +{activeToolCalls.length - 8} more
            </span>
          )}
        </div>
      )}
    </div>
  );
};
