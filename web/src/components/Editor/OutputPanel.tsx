'use client';

import { useState, useEffect, useRef, useCallback } from 'react';

interface LogEntry {
  id: string;
  timestamp: number;
  level: 'info' | 'warn' | 'error' | 'debug';
  message: string;
  source?: string;
}

type LogFilter = 'all' | 'info' | 'warn' | 'error';

const LEVEL_COLORS: Record<string, string> = {
  info: 'text-blue-400',
  warn: 'text-amber-400',
  error: 'text-red-400',
  debug: 'text-muted',
};

const LEVEL_BG: Record<string, string> = {
  info: '',
  warn: 'bg-amber-500/5',
  error: 'bg-red-500/10',
  debug: '',
};

export function OutputPanel() {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [filter, setFilter] = useState<LogFilter>('all');
  const [connected, setConnected] = useState(false);
  const [autoScroll, setAutoScroll] = useState(true);
  const scrollRef = useRef<HTMLDivElement>(null);
  const wsRef = useRef<WebSocket | null>(null);

  useEffect(() => {
    // Connect to SSE or WebSocket for engine logs
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const ws = new WebSocket(`${protocol}//${window.location.host}/api/ws/logs`);
    wsRef.current = ws;

    ws.onopen = () => setConnected(true);
    ws.onclose = () => setConnected(false);
    ws.onerror = () => setConnected(false);

    ws.onmessage = (event) => {
      try {
        const data = JSON.parse(event.data);
        const entry: LogEntry = {
          id: `log-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
          timestamp: data.timestamp || Date.now(),
          level: data.level || 'info',
          message: data.message || event.data,
          source: data.source,
        };
        setLogs((prev) => [...prev.slice(-999), entry]);
      } catch {
        // Plain text message
        setLogs((prev) => [...prev.slice(-999), {
          id: `log-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
          timestamp: Date.now(),
          level: 'info',
          message: event.data,
        }]);
      }
    };

    return () => {
      ws.close();
    };
  }, []);

  // Auto scroll
  useEffect(() => {
    if (autoScroll && scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [logs, autoScroll]);

  const filtered = filter === 'all'
    ? logs
    : logs.filter((l) => l.level === filter || (filter === 'error' && l.level === 'error') || (filter === 'warn' && l.level === 'warn'));

  const formatTime = (ts: number) => {
    const d = new Date(ts);
    return `${d.getHours().toString().padStart(2, '0')}:${d.getMinutes().toString().padStart(2, '0')}:${d.getSeconds().toString().padStart(2, '0')}.${d.getMilliseconds().toString().padStart(3, '0')}`;
  };

  const handleClear = () => setLogs([]);

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="px-3 py-1.5 border-b border-border flex items-center justify-between shrink-0">
        <div className="flex items-center gap-2">
          <h2 className="text-xs font-semibold">Output</h2>
          <span className={`inline-block h-1.5 w-1.5 rounded-full ${connected ? 'bg-green-500' : 'bg-red-500'}`} />
        </div>
        <div className="flex items-center gap-1">
          <div className="flex gap-0.5">
            {(['all', 'info', 'warn', 'error'] as const).map((f) => (
              <button key={f} onClick={() => setFilter(f)}
                className={`px-1.5 py-0.5 text-[9px] rounded transition ${
                  filter === f ? 'bg-primary text-white' : 'bg-accent/10 hover:bg-accent/20 text-muted'
                }`}
              >{f}</button>
            ))}
          </div>
          <label className="flex items-center gap-0.5 text-[9px] text-muted cursor-pointer ml-1">
            <input type="checkbox" checked={autoScroll} onChange={(e) => setAutoScroll(e.target.checked)}
              className="h-2.5 w-2.5 accent-primary"
            />
            Auto
          </label>
          <button onClick={handleClear} className="px-1.5 py-0.5 text-[9px] rounded bg-accent/10 hover:bg-accent/20 text-muted transition ml-1">
            Clear
          </button>
        </div>
      </div>

      {/* Log output */}
      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto font-mono text-[11px] leading-relaxed bg-background"
        style={{ fontFamily: "'Cascadia Code', 'Fira Code', 'Consolas', monospace" }}
      >
        {filtered.length === 0 ? (
          <div className="text-[10px] text-muted/50 p-3">No log output. {connected ? 'Waiting for engine logs...' : 'Disconnected.'}</div>
        ) : (
          filtered.map((log) => (
            <div key={log.id} className={`px-3 py-0.5 hover:bg-accent/5 ${LEVEL_BG[log.level] || ''}`}>
              <span className="text-muted/50">{formatTime(log.timestamp)}</span>
              {' '}
              <span className={`font-medium ${LEVEL_COLORS[log.level]}`}>
                {log.level.toUpperCase().padEnd(5)}
              </span>
              {' '}
              {log.source && <span className="text-muted/50">[{log.source}] </span>}
              <span className="text-foreground/80">{log.message}</span>
            </div>
          ))
        )}
      </div>

      {/* Status bar */}
      <div className="px-3 py-1 border-t border-border text-[9px] text-muted flex justify-between shrink-0">
        <span>{connected ? 'Connected' : 'Disconnected'}</span>
        <span>{filtered.length} entries</span>
      </div>
    </div>
  );
}
