'use client';

import { useMemo, useRef, useEffect, useState } from 'react';
import type { ToolCallStreamItem } from '@/lib/store';

// ── Props ──────────────────────────────────────────────────────────────

interface WaterfallChartProps {
  items: ToolCallStreamItem[];
  /** Total time range in ms (defaults to max end - min start) */
  timeRange?: number;
  /** Row height in px */
  rowHeight?: number;
}

interface LayoutBar {
  id: string;
  name: string;
  left: number;
  width: number;
  color: string;
  status: string;
  tooltip: string;
}

// ── Color palette ──────────────────────────────────────────────────────

const BAR_COLORS = [
  '#4f86e6', '#34d399', '#f472b6', '#a78bfa', '#fbbf24',
  '#60a5fa', '#fb923c', '#e879f9', '#22d3ee', '#f87171',
];

const STATUS_OPACITY: Record<string, number> = {
  completed: 1,
  running: 0.8,
  waiting_approval: 0.7,
  error: 0.6,
  cancelled: 0.4,
  pending: 0.3,
};

// ── Helpers ────────────────────────────────────────────────────────────

function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
  const m = Math.floor(ms / 60000);
  const s = Math.floor((ms % 60000) / 1000);
  return `${m}m ${s}s`;
}

// ── Main Component ─────────────────────────────────────────────────────

export function WaterfallChart({
  items,
  timeRange: propTimeRange,
  rowHeight = 28,
}: WaterfallChartProps) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [containerWidth, setContainerWidth] = useState(600);
  const [hoveredId, setHoveredId] = useState<string | null>(null);

  useEffect(() => {
    const el = containerRef.current;
    if (!el) return;
    const observer = new ResizeObserver((entries) => {
      for (const entry of entries) {
        setContainerWidth(entry.contentRect.width);
      }
    });
    observer.observe(el);
    return () => observer.disconnect();
  }, []);

  const { bars, timeStart, timeEnd } = useMemo(() => {
    if (items.length === 0) return { bars: [], timeStart: 0, timeEnd: 0 };

    const valid = items.filter((i) => i.startedAt > 0);
    if (valid.length === 0) return { bars: [], timeStart: 0, timeEnd: 0 };

    const minStart = Math.min(...valid.map((i) => i.startedAt));
    const maxEnd = Math.max(
      ...valid.map((i) => i.completedAt || Date.now())
    );
    const totalRange = propTimeRange || (maxEnd - minStart) || 1;

    const chartPadding = 80; // px reserved for tool labels on left

    const computed: LayoutBar[] = valid.map((item, idx) => {
      const startOffset = item.startedAt - minStart;
      const duration = item.completedAt
        ? item.completedAt - item.startedAt
        : Date.now() - item.startedAt;

      const left = chartPadding + (startOffset / totalRange) * (containerWidth - chartPadding - 16);
      const width = Math.max(4, (duration / totalRange) * (containerWidth - chartPadding - 16));

      return {
        id: item.id,
        name: item.call.name,
        left,
        width,
        color: BAR_COLORS[idx % BAR_COLORS.length],
        status: item.status,
        tooltip: `${item.call.name}\n${formatDuration(duration)}\n${item.status}`,
      };
    });

    return { bars: computed, timeStart: minStart, timeEnd: maxEnd };
  }, [items, propTimeRange, containerWidth]);

  const totalDuration = timeEnd - timeStart;

  if (items.length === 0) {
    return (
      <div className="text-center py-6 text-muted/50 text-[10px]">
        No tool calls to display
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {/* Header */}
      <div className="flex items-center justify-between px-1">
        <span className="text-[10px] font-medium text-muted uppercase tracking-wider">
          Waterfall
        </span>
        <span className="text-[9px] text-muted/50">
          {items.length} calls · {formatDuration(totalDuration)} total
        </span>
      </div>

      {/* Chart area */}
      <div
        ref={containerRef}
        className="relative overflow-x-hidden border border-border/20 rounded bg-background/30"
        style={{ height: items.length * rowHeight + 24 }}
      >
        {/* Time axis ticks */}
        <div className="absolute top-0 left-[80px] right-2 h-5 flex border-b border-border/20">
          {[0, 0.25, 0.5, 0.75, 1].map((fraction) => (
            <div
              key={fraction}
              className="absolute text-[8px] text-muted/40"
              style={{ left: `${fraction * 100}%`, transform: 'translateX(-50%)' }}
            >
              {formatDuration(totalDuration * fraction)}
            </div>
          ))}
        </div>

        {/* Bars */}
        {bars.map((bar, idx) => (
          <div
            key={bar.id}
            className="absolute flex items-center w-full transition-opacity"
            style={{
              top: idx * rowHeight + 20,
              height: rowHeight - 4,
              opacity: hoveredId && hoveredId !== bar.id ? 0.3 : 1,
            }}
            onMouseEnter={() => setHoveredId(bar.id)}
            onMouseLeave={() => setHoveredId(null)}
          >
            {/* Label */}
            <span
              className="absolute left-1 text-[9px] text-muted/70 truncate"
              style={{ width: '74px', textAlign: 'right', paddingRight: '6px' }}
              title={bar.name}
            >
              {bar.name}
            </span>
            {/* Bar */}
            <div
              className="h-full rounded-sm transition-all duration-200 cursor-pointer"
              style={{
                marginLeft: `${bar.left}px`,
                width: `${Math.max(4, bar.width)}px`,
                backgroundColor: bar.color,
                opacity: STATUS_OPACITY[bar.status] || 0.7,
                minWidth: '4px',
              }}
              title={bar.tooltip}
            />
            {/* Duration label */}
            <span className="ml-1 text-[8px] text-muted/40 whitespace-nowrap">
              {(bar.width > 40) && formatDuration(
                items.find((i) => i.id === bar.id)?.completedAt
                  ? items.find((i) => i.id === bar.id)!.completedAt! - items.find((i) => i.id === bar.id)!.startedAt
                  : Date.now() - items.find((i) => i.id === bar.id)!.startedAt
              )}
            </span>
          </div>
        ))}
      </div>

      {/* Legend */}
      <div className="flex items-center gap-3 px-1">
        {['completed', 'running', 'error', 'pending'].map((status) => (
          <div key={status} className="flex items-center gap-1">
            <span
              className="inline-block h-2 w-3 rounded-sm"
              style={{
                backgroundColor: BAR_COLORS[0],
                opacity: STATUS_OPACITY[status] || 0.5,
              }}
            />
            <span className="text-[9px] text-muted/50 capitalize">{status}</span>
          </div>
        ))}
      </div>
    </div>
  );
}

export default WaterfallChart;
