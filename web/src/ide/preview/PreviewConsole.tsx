'use client';

import React, { useEffect, useRef, useState, useCallback } from 'react';

// ── Types ──────────────────────────────────────────────────────────────

interface ConsoleEntry {
  id: number;
  type: 'log' | 'warn' | 'error' | 'info';
  message: string;
  timestamp: number;
}

// ── Component ──────────────────────────────────────────────────────────

export const PreviewConsole: React.FC = () => {
  const [entries, setEntries] = useState<ConsoleEntry[]>([]);
  const [isCleared, setIsCleared] = useState(false);
  const listRef = useRef<HTMLDivElement>(null);
  const idCounter = useRef(0);

  // Auto-scroll to bottom when new entries arrive
  useEffect(() => {
    if (listRef.current) {
      listRef.current.scrollTop = listRef.current.scrollHeight;
    }
  }, [entries]);

  // Simulate intercepted console entries.
  // In production, you would use a proxy iframe / postMessage to capture
  // the iframe's console output.
  const addEntry = useCallback((type: ConsoleEntry['type'], message: string) => {
    idCounter.current += 1;
    setEntries((prev) => [
      ...prev,
      { id: idCounter.current, type, message, timestamp: Date.now() },
    ]);
  }, []);

  const handleClear = useCallback(() => {
    setEntries([]);
    setIsCleared(true);
    setTimeout(() => setIsCleared(false), 300);
  }, []);

  // ── Style helpers ────────────────────────────────────────────────────

  const typeStyles: Record<ConsoleEntry['type'], string> = {
    log: 'text-foreground',
    info: 'text-blue-400',
    warn: 'text-yellow-400',
    error: 'text-red-400',
  };

  const typeBadge: Record<ConsoleEntry['type'], string> = {
    log: 'LOG',
    info: 'INFO',
    warn: 'WARN',
    error: 'ERRO',
  };

  const formatTime = (ts: number) => {
    const d = new Date(ts);
    return `${d.getMinutes().toString().padStart(2, '0')}:${d.getSeconds().toString().padStart(2, '0')}.${d.getMilliseconds().toString().padStart(3, '0')}`;
  };

  return (
    <div className="flex flex-col h-full bg-gray-950 text-xs font-mono">
      {/* ── Header ──────────────────────────────────────────────── */}
      <div className="flex items-center justify-between px-3 py-1.5 border-b border-border bg-gray-900">
        <span className="text-muted text-[11px] font-sans">
          Console ({entries.length})
        </span>
        <button
          type="button"
          onClick={handleClear}
          className="px-2 py-0.5 rounded text-[10px] text-muted
                     hover:text-foreground hover:bg-surface
                     transition-colors duration-fast"
        >
          Clear
        </button>
      </div>

      {/* ── Entry List ──────────────────────────────────────────── */}
      <div
        ref={listRef}
        className="flex-1 overflow-y-auto px-2 py-1 space-y-0.5 scrollbar-thin"
      >
        {entries.length === 0 ? (
          <div className="flex items-center justify-center h-full text-muted text-[11px] font-sans">
            {isCleared ? '已清空' : '暂无控制台输出'}
          </div>
        ) : (
          entries.map((entry) => (
            <div
              key={entry.id}
              className="flex items-start gap-2 py-0.5 leading-5"
            >
              {/* Timestamp */}
              <span className="text-[10px] text-muted shrink-0 w-14 text-right select-none">
                {formatTime(entry.timestamp)}
              </span>
              {/* Badge */}
              <span
                className={`shrink-0 text-[10px] font-bold w-8 text-right select-none ${typeStyles[entry.type]}`}
              >
                {typeBadge[entry.type]}
              </span>
              {/* Message */}
              <span className={`break-all ${typeStyles[entry.type]}`}>
                {entry.message}
              </span>
            </div>
          ))
        )}

        {/* Auto-scroll anchor */}
        <div ref={(el) => el?.scrollIntoView({ block: 'end' })} />
      </div>
    </div>
  );
};

export default PreviewConsole;
