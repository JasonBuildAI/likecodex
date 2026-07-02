'use client';

import { useMemo, useState } from 'react';
import type { ToolCallStreamItem } from '@/lib/store';

// ── Props ──────────────────────────────────────────────────────────────

interface ToolCallStatsProps {
  items: ToolCallStreamItem[];
}

interface ToolStat {
  name: string;
  count: number;
  totalDuration: number;
  avgDuration: number;
  minDuration: number;
  maxDuration: number;
  errorCount: number;
}

// ── Helpers ────────────────────────────────────────────────────────────

function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
  const m = Math.floor(ms / 60000);
  const s = Math.floor((ms % 60000) / 1000);
  return `${m}m ${s}s`;
}

function formatPercent(fraction: number): string {
  return `${(fraction * 100).toFixed(1)}%`;
}

// ── Main Component ─────────────────────────────────────────────────────

export function ToolCallStats({ items }: ToolCallStatsProps) {
  const [sortBy, setSortBy] = useState<'count' | 'avgDuration' | 'totalDuration'>('totalDuration');
  const [viewMode, setViewMode] = useState<'table' | 'distribution'>('table');

  const completed = useMemo(
    () => items.filter((i) => i.status === 'completed' && i.completedAt),
    [items]
  );

  const toolStats = useMemo(() => {
    const map = new Map<string, ToolStat>();
    for (const item of completed) {
      const name = item.call.name;
      const dur = item.completedAt! - item.startedAt;
      const existing = map.get(name);
      if (existing) {
        existing.count += 1;
        existing.totalDuration += dur;
        existing.minDuration = Math.min(existing.minDuration, dur);
        existing.maxDuration = Math.max(existing.maxDuration, dur);
        existing.avgDuration = existing.totalDuration / existing.count;
        if (item.status === 'error') existing.errorCount += 1;
      } else {
        map.set(name, {
          name,
          count: 1,
          totalDuration: dur,
          avgDuration: dur,
          minDuration: dur,
          maxDuration: dur,
          errorCount: item.status === 'error' ? 1 : 0,
        });
      }
    }
    return Array.from(map.values()).sort((a, b) => b[sortBy] - a[sortBy]);
  }, [completed, sortBy]);

  const totalCalls = completed.length;
  const totalTime = useMemo(
    () => toolStats.reduce((sum, s) => sum + s.totalDuration, 0),
    [toolStats]
  );

  const categoryDistribution = useMemo(() => {
    const counts: Record<string, number> = {};
    for (const item of completed) {
      const cat = item.call.name.startsWith('search') || item.call.name.startsWith('grep') || item.call.name.startsWith('read')
        ? 'search'
        : item.call.name.startsWith('edit') || item.call.name.startsWith('write') || item.call.name.startsWith('create')
          ? 'edit'
          : item.call.name.startsWith('run') || item.call.name.startsWith('execute')
            ? 'command'
            : 'other';
      counts[cat] = (counts[cat] || 0) + 1;
    }
    return counts;
  }, [completed]);

  const maxCatCount = Math.max(...Object.values(categoryDistribution), 1);

  if (totalCalls === 0) {
    return (
      <div className="text-center py-6 text-muted/50 text-[10px]">
        No completed tool calls to analyze
      </div>
    );
  }

  return (
    <div className="space-y-3">
      {/* Header */}
      <div className="flex items-center justify-between px-1">
        <span className="text-[10px] font-medium text-muted uppercase tracking-wider">
          Tool Call Stats
        </span>
        <div className="flex items-center gap-2">
          <button
            onClick={() => setViewMode(viewMode === 'table' ? 'distribution' : 'table')}
            className="text-[9px] text-muted/50 hover:text-muted px-1.5 py-0.5 rounded border border-border/30 transition-colors"
          >
            {viewMode === 'table' ? 'Distribution' : 'Table'}
          </button>
        </div>
      </div>

      {/* Summary */}
      <div className="grid grid-cols-3 gap-2 px-1">
        <div className="p-2 rounded bg-background/50 border border-border/30">
          <div className="text-[9px] text-muted/50">Total Calls</div>
          <div className="text-sm font-semibold text-foreground">{totalCalls}</div>
        </div>
        <div className="p-2 rounded bg-background/50 border border-border/30">
          <div className="text-[9px] text-muted/50">Total Time</div>
          <div className="text-sm font-semibold text-foreground">{formatDuration(totalTime)}</div>
        </div>
        <div className="p-2 rounded bg-background/50 border border-border/30">
          <div className="text-[9px] text-muted/50">Unique Tools</div>
          <div className="text-sm font-semibold text-foreground">{toolStats.length}</div>
        </div>
      </div>

      {/* Distribution View */}
      {viewMode === 'distribution' && (
        <div className="px-1 space-y-1.5">
          {Object.entries(categoryDistribution).map(([cat, count]) => (
            <div key={cat} className="flex items-center gap-2">
              <span className="text-[9px] text-muted w-12 shrink-0 capitalize">{cat}</span>
              <div className="flex-1 h-3 bg-background rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all ${
                    cat === 'search' ? 'bg-blue-500' :
                    cat === 'edit' ? 'bg-emerald-500' :
                    cat === 'command' ? 'bg-amber-500' : 'bg-purple-500'
                  }`}
                  style={{ width: `${(count / maxCatCount) * 100}%` }}
                />
              </div>
              <span className="text-[9px] text-muted/60 w-10 text-right">{count}</span>
              <span className="text-[9px] text-muted/40 w-10 text-right">{formatPercent(count / totalCalls)}</span>
            </div>
          ))}
        </div>
      )}

      {/* Table View */}
      {viewMode === 'table' && (
        <div className="overflow-x-auto">
          <table className="w-full text-[10px]">
            <thead>
              <tr className="border-b border-border/30">
                <th className="text-left py-1 px-1.5 text-muted/50 font-medium">Tool</th>
                <th
                  className="text-right py-1 px-1.5 text-muted/50 font-medium cursor-pointer hover:text-muted"
                  onClick={() => setSortBy('count')}
                >
                  Calls {sortBy === 'count' ? '↓' : ''}
                </th>
                <th
                  className="text-right py-1 px-1.5 text-muted/50 font-medium cursor-pointer hover:text-muted"
                  onClick={() => setSortBy('totalDuration')}
                >
                  Total {sortBy === 'totalDuration' ? '↓' : ''}
                </th>
                <th
                  className="text-right py-1 px-1.5 text-muted/50 font-medium cursor-pointer hover:text-muted"
                  onClick={() => setSortBy('avgDuration')}
                >
                  Avg {sortBy === 'avgDuration' ? '↓' : ''}
                </th>
                <th className="text-right py-1 px-1.5 text-muted/50 font-medium">Min</th>
                <th className="text-right py-1 px-1.5 text-muted/50 font-medium">Max</th>
              </tr>
            </thead>
            <tbody>
              {toolStats.map((stat) => (
                <tr key={stat.name} className="border-b border-border/10 hover:bg-accent/5 transition-colors">
                  <td className="py-1 px-1.5 font-medium text-foreground">{stat.name}</td>
                  <td className="py-1 px-1.5 text-right text-muted">
                    {stat.count}
                    {stat.errorCount > 0 && (
                      <span className="text-red-400 ml-1">({stat.errorCount})</span>
                    )}
                  </td>
                  <td className="py-1 px-1.5 text-right font-mono text-muted">{formatDuration(stat.totalDuration)}</td>
                  <td className="py-1 px-1.5 text-right font-mono text-muted">{formatDuration(stat.avgDuration)}</td>
                  <td className="py-1 px-1.5 text-right font-mono text-muted/50">{formatDuration(stat.minDuration)}</td>
                  <td className="py-1 px-1.5 text-right font-mono text-muted/50">{formatDuration(stat.maxDuration)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}

export default ToolCallStats;
