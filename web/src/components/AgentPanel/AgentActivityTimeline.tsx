'use client';

import React, { useMemo } from 'react';
import type { ToolCallStreamItem } from '@/lib/store';

// ── Props ──────────────────────────────────────────────────────────────
interface AgentActivityTimelineProps {
  activeToolCalls: ToolCallStreamItem[];
  isStreaming: boolean;
  variant: 'full' | 'compact';
}

// ── Component ──────────────────────────────────────────────────────────
export const AgentActivityTimeline: React.FC<AgentActivityTimelineProps> = ({
  activeToolCalls,
  isStreaming,
  variant,
}) => {
  const runningCount = useMemo(
    () => activeToolCalls.filter((i) => i.status === 'running').length,
    [activeToolCalls]
  );

  const completedCount = useMemo(
    () => activeToolCalls.filter((i) => i.status === 'completed').length,
    [activeToolCalls]
  );

  const errorCount = useMemo(
    () => activeToolCalls.filter((i) => i.status === 'error').length,
    [activeToolCalls]
  );

  const totalDuration = useMemo(() => {
    if (activeToolCalls.length === 0) return 0;
    const first = activeToolCalls[0].startedAt;
    const last = activeToolCalls[activeToolCalls.length - 1];
    return (last.completedAt || Date.now()) - first;
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

  const formatTime = (ms: number): string => {
    if (ms < 1000) return `${ms}ms`;
    if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
    return `${Math.floor(ms / 60000)}m ${Math.floor((ms % 60000) / 1000)}s`;
  };

  return (
    <div className="space-y-2">
      {/* Summary bar */}
      <div className="flex items-center justify-between px-1">
        <span className="text-[10px] font-medium text-muted uppercase tracking-wider">
          Activity
          {isStreaming && (
            <span className="ml-2 inline-block h-1.5 w-1.5 rounded-full bg-blue-500 animate-pulse" />
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

      {/* Status indicators */}
      {variant === 'full' && activeToolCalls.length > 0 && (
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
