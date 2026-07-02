'use client';

import { useState, useEffect, useRef } from 'react';

interface RenderRecord {
  componentName: string;
  renderCount: number;
  lastRenderTime: number;
  averageTime: number;
  suggestion?: string;
}

const DEV_ONLY = typeof window !== 'undefined' && process.env.NODE_ENV === 'development';

export function RenderAnalyzer() {
  const [records, setRecords] = useState<RenderRecord[]>([]);
  const [enabled, setEnabled] = useState(DEV_ONLY);
  const [sortBy, setSortBy] = useState<'count' | 'time'>('count');
  const originalNotifyRef = useRef<typeof (window as any).__REACT_DEVTOOLS_GLOBAL_HOOK__?.onCommitFiberRoot | null>(null);

  useEffect(() => {
    if (!enabled || !DEV_ONLY) return;

    // Track render counts via a global registry
    const renderMap = new Map<string, { count: number; totalTime: number; lastTime: number }>();

    // Monkey-patch React DevTools hook to track renders
    const hook = (window as any).__REACT_DEVTOOLS_GLOBAL_HOOK__;
    if (hook?.onCommitFiberRoot) {
      originalNotifyRef.current = hook.onCommitFiberRoot;
      hook.onCommitFiberRoot = (rendererID: any, root: any, ...args: any[]) => {
        try {
          // Try to extract component name from fiber tree
          const fiber = root?.current;
          if (fiber) {
            let node = fiber;
            while (node) {
              const name = node.type?.displayName || node.type?.name || node.elementType?.displayName || '';
              if (name && !name.startsWith('_') && name !== 'Anonymous') {
                const prev = renderMap.get(name) || { count: 0, totalTime: 0, lastTime: 0 };
                renderMap.set(name, {
                  count: prev.count + 1,
                  totalTime: prev.totalTime + (prev.lastTime ? performance.now() - prev.lastTime : 0),
                  lastTime: performance.now(),
                });
                break;
              }
              node = node.child;
            }
          }
        } catch {
          // ignore
        }
        originalNotifyRef.current?.(rendererID, root, ...args);
      };
    }

    // Poll for updates
    const interval = setInterval(() => {
      const result: RenderRecord[] = [];
      renderMap.forEach((data, componentName) => {
        const avgTime = data.count > 0 ? data.totalTime / data.count : 0;
        let suggestion: string | undefined;
        if (data.count > 50) {
          suggestion = 'Consider using React.memo() or useMemo()';
        } else if (avgTime > 16) {
          suggestion = `Slow render (${avgTime.toFixed(1)}ms). Consider code splitting or virtualization.`;
        } else if (data.count > 20) {
          suggestion = 'Consider useCallback() for handlers passed as props';
        }
        result.push({
          componentName,
          renderCount: data.count,
          lastRenderTime: data.lastTime,
          averageTime: avgTime,
          suggestion,
        });
      });
      result.sort((a, b) => sortBy === 'count' ? b.renderCount - a.renderCount : b.averageTime - a.averageTime);
      setRecords(result.slice(0, 50));
    }, 2000);

    return () => {
      clearInterval(interval);
      if (hook && originalNotifyRef.current) {
        hook.onCommitFiberRoot = originalNotifyRef.current;
      }
    };
  }, [enabled, sortBy]);

  return (
    <div className="flex flex-col h-full">
      <div className="p-3 border-b border-border">
        <div className="flex items-center justify-between mb-2">
          <h2 className="text-sm font-semibold">Render Analyzer</h2>
          <div className="flex items-center gap-2">
            {!DEV_ONLY && (
              <span className="text-[10px] text-amber-400 bg-amber-500/10 px-1.5 py-0.5 rounded">
                Dev only
              </span>
            )}
            <label className="flex items-center gap-1 text-[10px] text-muted cursor-pointer">
              <input
                type="checkbox"
                checked={enabled}
                onChange={(e) => setEnabled(e.target.checked)}
                className="h-3 w-3 rounded border-border accent-primary"
              />
              Enable
            </label>
          </div>
        </div>
        {enabled && (
          <div className="flex gap-1">
            <button
              onClick={() => setSortBy('count')}
              className={`px-2 py-0.5 text-[10px] rounded transition ${
                sortBy === 'count' ? 'bg-primary text-white' : 'bg-accent/10 hover:bg-accent/20 text-muted'
              }`}
            >
              By Count
            </button>
            <button
              onClick={() => setSortBy('time')}
              className={`px-2 py-0.5 text-[10px] rounded transition ${
                sortBy === 'time' ? 'bg-primary text-white' : 'bg-accent/10 hover:bg-accent/20 text-muted'
              }`}
            >
              By Time
            </button>
          </div>
        )}
      </div>

      <div className="flex-1 overflow-y-auto">
        {!enabled ? (
          <div className="text-xs text-muted text-center py-8">Render analyzer is disabled. Toggle enable to start tracking.</div>
        ) : records.length === 0 ? (
          <div className="text-xs text-muted text-center py-8">Collecting render data... (ensure React DevTools is active)</div>
        ) : (
          <div className="divide-y divide-border/50">
            {records.map((rec) => (
              <div key={rec.componentName} className="px-3 py-2">
                <div className="flex items-center justify-between mb-0.5">
                  <span className="text-xs font-medium truncate max-w-[200px]">{rec.componentName}</span>
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] font-mono text-muted">{rec.renderCount}x</span>
                    <span className={`text-[10px] font-mono ${
                      rec.averageTime > 16 ? 'text-red-400' : rec.averageTime > 8 ? 'text-amber-400' : 'text-muted'
                    }`}>
                      {rec.averageTime.toFixed(1)}ms
                    </span>
                  </div>
                </div>
                {/* Mini bar for render count */}
                <div className="h-1 bg-accent/10 rounded-full overflow-hidden">
                  <div
                    className="h-full rounded-full bg-blue-500/60"
                    style={{ width: `${Math.min((rec.renderCount / (records[0]?.renderCount || 1)) * 100, 100)}%` }}
                  />
                </div>
                {rec.suggestion && (
                  <div className="text-[9px] text-amber-400/80 mt-0.5">{rec.suggestion}</div>
                )}
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
