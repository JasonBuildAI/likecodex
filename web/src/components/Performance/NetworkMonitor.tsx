'use client';

import { useState, useEffect, useCallback } from 'react';

interface NetworkRequest {
  id: string;
  method: string;
  url: string;
  status: number;
  duration: number;
  requestBody?: string;
  responseBody?: string;
  timestamp: number;
}

const SLOW_THRESHOLD = 1000; // 1s

export function NetworkMonitor() {
  const [requests, setRequests] = useState<NetworkRequest[]>([]);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [filter, setFilter] = useState<'all' | 'slow' | 'error'>('all');

  // Mock: intercept fetch to collect requests
  useEffect(() => {
    const origFetch = window.fetch;
    window.fetch = async (input: RequestInfo | URL, init?: RequestInit) => {
      const start = performance.now();
      const id = `req-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
      const method = init?.method || 'GET';
      const url = typeof input === 'string' ? input : input instanceof URL ? input.href : input.url;

      try {
        const resp = await origFetch(input, init);
        const duration = performance.now() - start;
        const entry: NetworkRequest = {
          id, method, url, status: resp.status, duration,
          timestamp: Date.now(),
        };
        setRequests((prev) => [entry, ...prev].slice(0, 200));
        return resp;
      } catch (err) {
        const duration = performance.now() - start;
        setRequests((prev) => [{
          id, method, url, status: 0, duration,
          timestamp: Date.now(),
        }, ...prev].slice(0, 200));
        throw err;
      }
    };
    return () => {
      window.fetch = origFetch;
    };
  }, []);

  const filtered = requests.filter((r) => {
    if (filter === 'slow') return r.duration > SLOW_THRESHOLD;
    if (filter === 'error') return r.status >= 400 || r.status === 0;
    return true;
  });

  const selected = requests.find((r) => r.id === selectedId);

  const methodColor = (method: string) => {
    const map: Record<string, string> = {
      GET: 'text-green-500', POST: 'text-blue-500',
      PUT: 'text-amber-500', PATCH: 'text-yellow-500',
      DELETE: 'text-red-500',
    };
    return map[method] || 'text-muted';
  };

  const statusColor = (status: number) => {
    if (status === 0) return 'bg-red-500';
    if (status < 300) return 'bg-green-500';
    if (status < 400) return 'bg-amber-500';
    return 'bg-red-500';
  };

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="p-3 border-b border-border">
        <div className="flex items-center justify-between mb-2">
          <h2 className="text-sm font-semibold">Network Monitor</h2>
          <span className="text-[10px] text-muted">{requests.length} requests</span>
        </div>
        <div className="flex gap-1">
          {(['all', 'slow', 'error'] as const).map((f) => (
            <button
              key={f}
              onClick={() => setFilter(f)}
              className={`px-2 py-0.5 text-[10px] rounded transition ${
                filter === f ? 'bg-primary text-white' : 'bg-accent/10 hover:bg-accent/20 text-muted'
              }`}
            >
              {f === 'all' ? 'All' : f === 'slow' ? 'Slow' : 'Errors'}
            </button>
          ))}
        </div>
      </div>

      {/* Request list */}
      <div className="flex-1 overflow-y-auto divide-y divide-border/50">
        {filtered.length === 0 ? (
          <div className="text-xs text-muted text-center py-6">No network requests recorded.</div>
        ) : (
          filtered.map((req) => {
            const isSlow = req.duration > SLOW_THRESHOLD;
            const isError = req.status >= 400 || req.status === 0;
            return (
              <div
                key={req.id}
                onClick={() => setSelectedId(selectedId === req.id ? null : req.id)}
                className={`px-3 py-2 cursor-pointer transition-colors hover:bg-accent/5 ${
                  selectedId === req.id ? 'bg-accent/10' : ''
                } ${isError ? 'bg-red-500/5' : ''}`}
              >
                <div className="flex items-center gap-2">
                  <span className={`inline-block h-1.5 w-1.5 rounded-full ${statusColor(req.status)}`} />
                  <span className={`text-[10px] font-mono font-medium ${methodColor(req.method)}`}>
                    {req.method}
                  </span>
                  <span className="flex-1 text-xs truncate text-muted">{req.url.replace(/^https?:\/\/[^/]+/, '')}</span>
                  <span className={`text-[10px] font-mono ${isSlow ? 'text-amber-400 font-medium' : 'text-muted'}`}>
                    {req.duration.toFixed(0)}ms
                  </span>
                  <span className={`text-[10px] font-mono ${isError ? 'text-red-400' : 'text-muted'}`}>
                    {req.status || 'ERR'}
                  </span>
                </div>
              </div>
            );
          })
        )}
      </div>

      {/* Request detail */}
      {selected && (
        <div className="border-t border-border p-3 max-h-[200px] overflow-y-auto bg-surface/50">
          <div className="text-[10px] font-semibold text-muted mb-1">Request Details</div>
          <div className="text-[10px] font-mono text-muted space-y-0.5">
            <div><span className="text-muted/60">URL: </span>{selected.url}</div>
            <div><span className="text-muted/60">Duration: </span>{selected.duration.toFixed(2)}ms</div>
            <div><span className="text-muted/60">Status: </span>{selected.status || 'Connection Error'}</div>
          </div>
        </div>
      )}

      {/* Slow request alert */}
      {filtered.filter((r) => r.duration > SLOW_THRESHOLD).length > 0 && (
        <div className="px-3 py-1.5 bg-amber-500/10 border-t border-amber-500/20 text-[10px] text-amber-400">
          ⚠ {filtered.filter((r) => r.duration > SLOW_THRESHOLD).length} slow request(s) detected
        </div>
      )}
    </div>
  );
}
