'use client';

import { useState, useMemo } from 'react';

// ── Types ──────────────────────────────────────────────────────────────

export interface PerfMetric {
  name: string;
  value: number;
  unit: string;
  trend?: 'up' | 'down' | 'stable';
  threshold?: number;
  history?: number[];
}

interface PerfDashboardProps {
  metrics: PerfMetric[];
  /** Refresh interval in ms */
  refreshInterval?: number;
  onRefresh?: () => void;
  onExport?: () => void;
}

// ── Helpers ────────────────────────────────────────────────────────────

function formatValue(value: number, unit: string): string {
  if (unit === 'ms') {
    if (value < 1000) return `${value.toFixed(0)}ms`;
    return `${(value / 1000).toFixed(1)}s`;
  }
  if (unit === 'bytes') {
    if (value < 1024) return `${value}B`;
    if (value < 1024 * 1024) return `${(value / 1024).toFixed(1)}KB`;
    return `${(value / (1024 * 1024)).toFixed(1)}MB`;
  }
  if (unit === '%') return `${value.toFixed(1)}%`;
  if (unit === 'count') return value.toFixed(0);
  return `${value} ${unit}`;
}

function getStatusColor(value: number, threshold?: number): string {
  if (threshold === undefined) return 'text-foreground';
  if (value <= threshold * 0.6) return 'text-green-400';
  if (value <= threshold * 0.85) return 'text-yellow-400';
  return 'text-red-400';
}

function getStatusDot(value: number, threshold?: number): string {
  if (threshold === undefined) return 'bg-blue-500';
  if (value <= threshold * 0.6) return 'bg-green-500';
  if (value <= threshold * 0.85) return 'bg-yellow-500';
  return 'bg-red-500 animate-pulse';
}

// ── Sparkline ──────────────────────────────────────────────────────────

function Sparkline({ data, width = 80, height = 24 }: { data: number[]; width?: number; height?: number }) {
  if (data.length < 2) return null;

  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;

  const points = data.map((v, i) => {
    const x = (i / (data.length - 1)) * (width - 2) + 1;
    const y = height - 2 - ((v - min) / range) * (height - 4);
    return `${x},${y}`;
  });

  return (
    <svg width={width} height={height} className="shrink-0">
      <polyline
        points={points.join(' ')}
        fill="none"
        stroke="currentColor"
        strokeWidth={1.5}
        strokeLinecap="round"
        strokeLinejoin="round"
        className="text-primary/50"
      />
    </svg>
  );
}

// ── Main Component ─────────────────────────────────────────────────────

export function PerfDashboard({
  metrics,
  onRefresh,
  onExport,
}: PerfDashboardProps) {
  const [viewMode, setViewMode] = useState<'grid' | 'list'>('grid');
  const [filter, setFilter] = useState<'all' | 'warning' | 'critical'>('all');
  const [lastUpdated] = useState(new Date().toLocaleTimeString());

  const filteredMetrics = useMemo(() => {
    if (filter === 'all') return metrics;
    if (filter === 'warning') {
      return metrics.filter((m) => m.threshold !== undefined && m.value > m.threshold * 0.6);
    }
    if (filter === 'critical') {
      return metrics.filter((m) => m.threshold !== undefined && m.value > m.threshold * 0.85);
    }
    return metrics;
  }, [metrics, filter]);

  const warningCount = metrics.filter(
    (m) => m.threshold !== undefined && m.value > m.threshold * 0.6 && m.value <= m.threshold * 0.85
  ).length;

  const criticalCount = metrics.filter(
    (m) => m.threshold !== undefined && m.value > m.threshold * 0.85
  ).length;

  if (metrics.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-full text-muted/50">
        <svg className="h-8 w-8 mb-2 opacity-40" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
        </svg>
        <p className="text-[10px]">No performance metrics available</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full border border-border/30 rounded-lg bg-surface/30 overflow-hidden">
      {/* Header */}
      <div className="px-4 py-3 border-b border-border/30">
        <div className="flex items-center justify-between mb-2">
          <span className="text-[10px] font-medium text-muted uppercase tracking-wider">
            Performance Dashboard
          </span>
          <div className="flex items-center gap-1.5">
            <button
              onClick={() => setViewMode(viewMode === 'grid' ? 'list' : 'grid')}
              className="text-[9px] px-1.5 py-0.5 rounded border border-border/30 text-muted/50 hover:text-muted"
            >
              {viewMode === 'grid' ? 'List' : 'Grid'}
            </button>
            {onRefresh && (
              <button
                onClick={onRefresh}
                className="text-[9px] px-1.5 py-0.5 rounded border border-border/30 text-muted/50 hover:text-muted"
                title="Refresh"
              >
                ↻
              </button>
            )}
            {onExport && (
              <button
                onClick={onExport}
                className="text-[9px] px-1.5 py-0.5 rounded border border-border/30 text-muted/50 hover:text-muted"
                title="Export"
              >
                ↓
              </button>
            )}
          </div>
        </div>

        {/* Summary chips */}
        <div className="flex items-center gap-2">
          <span className="text-[9px] text-muted/50">{metrics.length} metrics</span>
          {warningCount > 0 && (
            <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-yellow-500/10 text-yellow-400 border border-yellow-500/20">
              {warningCount} warning
            </span>
          )}
          {criticalCount > 0 && (
            <span className="text-[9px] px-1.5 py-0.5 rounded-full bg-red-500/10 text-red-400 border border-red-500/20">
              {criticalCount} critical
            </span>
          )}
          <span className="text-[8px] text-muted/40 ml-auto">Updated {lastUpdated}</span>
        </div>

        {/* Filter tabs */}
        <div className="flex gap-1 mt-2">
          {(['all', 'warning', 'critical'] as const).map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`text-[8px] px-2 py-0.5 rounded-full border transition-colors capitalize ${
                filter === f
                  ? 'bg-primary/10 text-primary border-primary/20'
                  : 'border-border/30 text-muted/50 hover:text-muted'
              }`}
            >
              {f}
              {f === 'warning' && warningCount > 0 && ` (${warningCount})`}
              {f === 'critical' && criticalCount > 0 && ` (${criticalCount})`}
            </button>
          ))}
        </div>
      </div>

      {/* Metrics content */}
      <div className="flex-1 overflow-y-auto p-3">
        {viewMode === 'grid' ? (
          <div className="grid grid-cols-2 gap-2">
            {filteredMetrics.map((metric) => (
              <div
                key={metric.name}
                className="p-3 rounded-lg border border-border/20 bg-background/40 hover:bg-background/60 transition-colors"
              >
                <div className="flex items-center justify-between mb-1.5">
                  <span className="text-[9px] text-muted/60 truncate" title={metric.name}>
                    {metric.name}
                  </span>
                  <span className={`inline-block h-1.5 w-1.5 rounded-full ${getStatusDot(metric.value, metric.threshold)}`} />
                </div>
                <div className="flex items-baseline gap-1">
                  <span className={`text-sm font-semibold font-mono ${getStatusColor(metric.value, metric.threshold)}`}>
                    {formatValue(metric.value, metric.unit)}
                  </span>
                  {metric.threshold !== undefined && (
                    <span className="text-[8px] text-muted/40">
                      / {formatValue(metric.threshold, metric.unit)}
                    </span>
                  )}
                  {metric.trend === 'up' && <span className="text-[9px] text-red-400">↑</span>}
                  {metric.trend === 'down' && <span className="text-[9px] text-green-400">↓</span>}
                </div>
                {metric.history && metric.history.length > 1 && (
                  <div className="mt-1.5 text-muted/40">
                    <Sparkline data={metric.history} />
                  </div>
                )}
              </div>
            ))}
          </div>
        ) : (
          <div className="space-y-0.5">
            {filteredMetrics.map((metric) => (
              <div
                key={metric.name}
                className="flex items-center gap-3 px-3 py-2 rounded hover:bg-accent/5 transition-colors"
              >
                <span className={`inline-block h-1.5 w-1.5 rounded-full shrink-0 ${getStatusDot(metric.value, metric.threshold)}`} />
                <span className="text-[10px] text-foreground/80 flex-1">{metric.name}</span>
                <span className={`text-[10px] font-mono font-medium ${getStatusColor(metric.value, metric.threshold)}`}>
                  {formatValue(metric.value, metric.unit)}
                </span>
                {metric.threshold !== undefined && (
                  <span className="text-[8px] text-muted/40 w-12 text-right">
                    / {formatValue(metric.threshold, metric.unit)}
                  </span>
                )}
                {metric.trend === 'up' && <span className="text-[9px] text-red-400">↑</span>}
                {metric.trend === 'down' && <span className="text-[9px] text-green-400">↓</span>}
                {metric.history && metric.history.length > 1 && (
                  <Sparkline data={metric.history} width={48} height={20} />
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

export default PerfDashboard;
