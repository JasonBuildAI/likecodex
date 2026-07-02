'use client';

import { useState, useEffect, useCallback } from 'react';
import { fetchCacheMetrics } from '@/lib/api';
import { useAppStore } from '@/lib/store';

interface CacheMetrics {
  hit_rate: number;
  size_bytes: number;
  entry_count: number;
  history?: Array<{ timestamp: string; hit_rate: number }>;
}

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

export function CacheDashboard() {
  const [metrics, setMetrics] = useState<CacheMetrics | null>(null);
  const [loading, setLoading] = useState(false);
  const [clearing, setClearing] = useState(false);
  const addToast = useAppStore((s) => s.addToast);

  const loadMetrics = useCallback(async () => {
    setLoading(true);
    try {
      const data = await fetchCacheMetrics();
      setMetrics(data as CacheMetrics);
    } catch {
      // silently fail
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadMetrics();
    const interval = setInterval(loadMetrics, 15000);
    return () => clearInterval(interval);
  }, [loadMetrics]);

  const handleClear = async () => {
    setClearing(true);
    try {
      const resp = await fetch('/api/ide/cache/clear', { method: 'POST' });
      if (resp.ok) {
        addToast({ type: 'success', message: 'Cache cleared' });
        loadMetrics();
      } else {
        addToast({ type: 'error', message: 'Failed to clear cache' });
      }
    } catch {
      addToast({ type: 'error', message: 'Failed to clear cache' });
    } finally {
      setClearing(false);
    }
  };

  const hitRatePct = metrics ? (metrics.hit_rate * 100).toFixed(1) : '--';

  // Mini sparkline chart from history
  const historyData = metrics?.history || [];
  const maxRate = Math.max(...historyData.map((h) => h.hit_rate), 0.01);

  return (
    <div className="flex flex-col h-full">
      <div className="p-3 border-b border-border">
        <div className="flex items-center justify-between mb-2">
          <h2 className="text-sm font-semibold">Cache Dashboard</h2>
          <div className="flex gap-1">
            <button
              onClick={loadMetrics}
              disabled={loading}
              className="px-2 py-0.5 text-[10px] rounded bg-accent/10 hover:bg-accent/20 transition disabled:opacity-50"
            >
              {loading ? '...' : 'Refresh'}
            </button>
            <button
              onClick={handleClear}
              disabled={clearing}
              className="px-2 py-0.5 text-[10px] rounded bg-red-500/10 text-red-400 hover:bg-red-500/20 transition disabled:opacity-50"
            >
              {clearing ? '...' : 'Clear Cache'}
            </button>
          </div>
        </div>
      </div>

      <div className="flex-1 overflow-y-auto p-3 space-y-4">
        {loading && !metrics ? (
          <div className="flex items-center justify-center py-8">
            <div className="h-4 w-4 animate-spin rounded-full border-2 border-primary border-t-transparent" />
          </div>
        ) : !metrics ? (
          <div className="text-xs text-muted text-center py-4">No cache metrics available.</div>
        ) : (
          <>
            {/* Hit rate gauge */}
            <div>
              <div className="flex items-center justify-between mb-1">
                <span className="text-xs font-medium text-muted">Hit Rate</span>
                <span className="text-lg font-mono font-bold">{hitRatePct}%</span>
              </div>
              <div className="h-3 bg-accent/10 rounded-full overflow-hidden">
                <div
                  className={`h-full rounded-full transition-all duration-700 ${
                    metrics.hit_rate > 0.6 ? 'bg-green-500' : metrics.hit_rate > 0.3 ? 'bg-amber-500' : 'bg-red-500'
                  }`}
                  style={{ width: `${hitRatePct}%` }}
                />
              </div>
            </div>

            {/* Stats cards */}
            <div className="grid grid-cols-2 gap-2">
              <div className="rounded-lg bg-accent/5 p-3">
                <div className="text-[10px] text-muted mb-0.5">Cache Size</div>
                <div className="text-sm font-mono font-medium">{formatBytes(metrics.size_bytes)}</div>
              </div>
              <div className="rounded-lg bg-accent/5 p-3">
                <div className="text-[10px] text-muted mb-0.5">Entries</div>
                <div className="text-sm font-mono font-medium">{metrics.entry_count.toLocaleString()}</div>
              </div>
            </div>

            {/* Mini trend chart */}
            {historyData.length > 1 && (
              <div>
                <div className="text-[10px] text-muted mb-1">Hit Rate Trend (recent)</div>
                <div className="h-16 bg-accent/5 rounded-lg p-2">
                  <svg viewBox={`0 0 ${historyData.length} 100`} className="w-full h-full" preserveAspectRatio="none">
                    <polyline
                      points={historyData.map((h, i) => `${i},${100 - (h.hit_rate / maxRate) * 90}`).join(' ')}
                      fill="none"
                      stroke="rgb(59, 130, 246)"
                      strokeWidth="2"
                      vectorEffect="non-scaling-stroke"
                    />
                    <polygon
                      points={`0,100 ${historyData.map((h, i) => `${i},${100 - (h.hit_rate / maxRate) * 90}`).join(' ')} ${historyData.length - 1},100`}
                      fill="rgba(59, 130, 246, 0.1)"
                    />
                  </svg>
                </div>
              </div>
            )}

            {/* Summary */}
            <div className="rounded-lg bg-accent/5 p-3 text-[10px] text-muted space-y-1">
              <div className="flex justify-between">
                <span>Total requests</span>
                <span className="font-mono">{metrics.entry_count}</span>
              </div>
              <div className="flex justify-between">
                <span>Cache effectiveness</span>
                <span className={`font-mono ${metrics.hit_rate > 0.5 ? 'text-green-400' : 'text-amber-400'}`}>
                  {metrics.hit_rate > 0.5 ? 'Good' : 'Low'}
                </span>
              </div>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
