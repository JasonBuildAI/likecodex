'use client';

/**
 * DebugToolbar — Debug control toolbar with breakpoints and step controls.
 * Also includes LSP Diagnostics Panel showing errors/warnings grouped by file.
 *
 * This is a simplified debug toolbar. Full DAP integration would require
 * WebSocket connection to a debug adapter (debugpy, vscode-js-debug, etc.).
 * For now, this provides the UI and breakpoint management.
 */

import { useState, useCallback, useEffect, useRef } from 'react';
import { lspDiagnostics, type LSPDiagnostic } from '@/lib/api';
import { useAppStore } from '@/lib/store';
import type { Breakpoint, DebugStatus } from './types';

type SeverityFilter = 'all' | 'error' | 'warning' | 'info';
type DebugTab = 'controls' | 'diagnostics';

export function DebugToolbar() {
  const [status, setStatus] = useState<DebugStatus>('stopped');
  const [breakpoints, setBreakpoints] = useState<Breakpoint[]>([]);
  const [showBreakpoints, setShowBreakpoints] = useState(false);
  const [activeTab, setActiveTab] = useState<DebugTab>('controls');
  const [diagnostics, setDiagnostics] = useState<LSPDiagnostic[]>([]);
  const [diagnosticsLoading, setDiagnosticsLoading] = useState(false);
  const [severityFilter, setSeverityFilter] = useState<SeverityFilter>('all');
  const [expandedFiles, setExpandedFiles] = useState<Set<string>>(new Set());
  const diagnosticsTimerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  // ── Debug Controls ──────────────────────────────────────────────────
  const handleContinue = useCallback(() => {
    setStatus('running');
    // In full implementation: send DAP "continue" request
  }, []);

  const handleStepOver = useCallback(() => {
    // DAP "next" request
  }, []);

  const handleStepInto = useCallback(() => {
    // DAP "stepIn" request
  }, []);

  const handleStepOut = useCallback(() => {
    // DAP "stepOut" request
  }, []);

  const handleStop = useCallback(() => {
    setStatus('stopped');
  }, []);

  const handleRestart = useCallback(() => {
    setStatus('running');
  }, []);

  const statusColor =
    status === 'running' ? 'text-green-400' :
    status === 'paused' ? 'text-yellow-400' :
    'text-gray-500';

  const statusText =
    status === 'running' ? '● 运行中' :
    status === 'paused' ? '⏸ 已暂停' :
    '■ 已停止';

  // ── Diagnostics ─────────────────────────────────────────────────────
  const fetchDiagnostics = useCallback(async () => {
    setDiagnosticsLoading(true);
    try {
      const data = await lspDiagnostics('.');
      if (data.diagnostics) {
        setDiagnostics(data.diagnostics);
      }
    } catch {
      // Best effort
    } finally {
      setDiagnosticsLoading(false);
    }
  }, []);

  // Auto-fetch on mount and periodically
  useEffect(() => {
    if (activeTab === 'diagnostics') {
      fetchDiagnostics();
    }
  }, [activeTab, fetchDiagnostics]);

  const filteredDiagnostics = diagnostics.filter((d) => {
    if (severityFilter === 'all') return true;
    return d.severity === severityFilter;
  });

  // Group by file
  const groupedByFile = filteredDiagnostics.reduce<Record<string, LSPDiagnostic[]>>((acc, d) => {
    const key = d.file || 'unknown';
    if (!acc[key]) acc[key] = [];
    acc[key].push(d);
    return acc;
  }, {});

  const toggleFile = useCallback((file: string) => {
    setExpandedFiles((prev) => {
      const next = new Set(prev);
      if (next.has(file)) next.delete(file);
      else next.add(file);
      return next;
    });
  }, []);

  const handleDiagnosticClick = useCallback((diag: LSPDiagnostic) => {
    if (diag.line > 0) {
      window.dispatchEvent(new CustomEvent('navigate-to-line', {
        detail: { path: diag.file, line: diag.line },
      }));
    }
  }, []);

  const severityIcon = (severity: string) => {
    switch (severity) {
      case 'error': return <span className="text-red-400">&#x2716;</span>;
      case 'warning': return <span className="text-yellow-400">&#x26A0;</span>;
      case 'info': return <span className="text-blue-400">&#x2139;</span>;
      default: return <span className="text-gray-400">&#x2022;</span>;
    }
  };

  const severityBadge = (severity: string) => {
    const count = diagnostics.filter(d => d.severity === severity).length;
    if (count === 0) return null;
    const colorMap: Record<string, string> = {
      error: 'bg-red-500/20 text-red-400',
      warning: 'bg-yellow-500/20 text-yellow-400',
      info: 'bg-blue-500/20 text-blue-400',
    };
    return (
      <span className={`text-[9px] px-1 py-0.5 rounded ${colorMap[severity] || ''}`}>
        {count}
      </span>
    );
  };

  return (
    <div className="flex flex-col h-full">
      {/* Tab bar */}
      <div className="flex items-center border-b border-gray-700 shrink-0">
        <button
          onClick={() => setActiveTab('controls')}
          className={`px-3 py-1 text-[10px] ${activeTab === 'controls' ? 'text-white border-b-2 border-blue-400' : 'text-gray-500 hover:text-gray-300'}`}
        >
          Debug
        </button>
        <button
          onClick={() => setActiveTab('diagnostics')}
          className={`px-3 py-1 text-[10px] flex items-center gap-1 ${activeTab === 'diagnostics' ? 'text-white border-b-2 border-blue-400' : 'text-gray-500 hover:text-gray-300'}`}
        >
          Problems
          <span className="flex gap-0.5">
            {severityBadge('error')}
            {severityBadge('warning')}
          </span>
        </button>
      </div>

      {activeTab === 'controls' && (
        <>
          {/* Debug control buttons */}
          <div className="flex items-center gap-1 px-2 py-1 bg-[#2d2d2d] shrink-0">
            <button
              onClick={handleContinue}
              disabled={status !== 'paused'}
              className="p-1 text-green-400 hover:bg-gray-700 rounded disabled:opacity-30"
              title="继续 (F5)"
            >
              ▶
            </button>
            <button
              onClick={handleStepOver}
              disabled={status !== 'paused'}
              className="p-1 text-blue-400 hover:bg-gray-700 rounded disabled:opacity-30"
              title="单步跳过 (F10)"
            >
              ⏭
            </button>
            <button
              onClick={handleStepInto}
              disabled={status !== 'paused'}
              className="p-1 text-blue-400 hover:bg-gray-700 rounded disabled:opacity-30"
              title="单步进入 (F11)"
            >
              ⬇
            </button>
            <button
              onClick={handleStepOut}
              disabled={status !== 'paused'}
              className="p-1 text-blue-400 hover:bg-gray-700 rounded disabled:opacity-30"
              title="单步跳出 (Shift+F11)"
            >
              ⬆
            </button>
            <button
              onClick={handleRestart}
              className="p-1 text-gray-400 hover:bg-gray-700 rounded"
              title="重新启动"
            >
              ⟳
            </button>
            <button
              onClick={handleStop}
              disabled={status === 'stopped'}
              className="p-1 text-red-400 hover:bg-gray-700 rounded disabled:opacity-30"
              title="停止 (Shift+F5)"
            >
              ■
            </button>

            {/* Status indicator */}
            <span className={`text-[10px] ml-2 ${statusColor}`}>
              {statusText}
            </span>

            {/* Breakpoints count */}
            <button
              onClick={() => setShowBreakpoints(!showBreakpoints)}
              className="ml-auto text-[10px] text-gray-400 hover:text-white px-2 py-0.5 rounded hover:bg-gray-700"
            >
              🔴 {breakpoints.length}
            </button>
          </div>

          {/* Breakpoints list */}
          {showBreakpoints && (
            <div className="border-t border-gray-700 px-2 py-1 max-h-32 overflow-y-auto shrink-0 bg-gray-900/30">
              <div className="text-[9px] text-gray-500 mb-1 font-semibold uppercase tracking-wider">Breakpoints</div>
              {breakpoints.length === 0 && (
                <div className="text-[10px] text-gray-600 italic px-1">No breakpoints set</div>
              )}
              {breakpoints.map((bp) => (
                <div key={bp.id} className="flex items-center text-[10px] text-gray-400 py-0.5 px-1 hover:bg-gray-800/50 rounded">
                  <span className="mr-1">🔴</span>
                  <span className="truncate flex-1">{bp.filePath}:{bp.line}</span>
                  <input
                    type="checkbox"
                    checked={bp.enabled}
                    onChange={() => {
                      setBreakpoints((prev) =>
                        prev.map((b) => (b.id === bp.id ? { ...b, enabled: !b.enabled } : b))
                      );
                    }}
                    className="w-2.5 h-2.5"
                  />
                </div>
              ))}
            </div>
          )}
        </>
      )}

      {/* ── Diagnostics Panel ──────────────────────────────────────────── */}
      {activeTab === 'diagnostics' && (
        <div className="flex flex-col flex-1 min-h-0">
          {/* Severity filter */}
          <div className="flex items-center gap-1 px-2 py-1 border-b border-gray-700 shrink-0">
            {(['all', 'error', 'warning', 'info'] as SeverityFilter[]).map((s) => (
              <button
                key={s}
                onClick={() => setSeverityFilter(s)}
                className={`text-[10px] px-1.5 py-0.5 rounded ${
                  severityFilter === s ? 'bg-gray-600 text-white' : 'text-gray-500 hover:text-gray-300'
                }`}
              >
                {s === 'all' ? 'All' : s.charAt(0).toUpperCase() + s.slice(1)}
                {s !== 'all' && (
                  <span className="ml-0.5">{diagnostics.filter(d => d.severity === s).length}</span>
                )}
              </button>
            ))}
            <button
              onClick={fetchDiagnostics}
              disabled={diagnosticsLoading}
              className="ml-auto text-[10px] text-gray-500 hover:text-white px-1.5 py-0.5 rounded hover:bg-gray-700"
            >
              {diagnosticsLoading ? '...' : '⟳'}
            </button>
          </div>

          {/* Diagnostics list */}
          <div className="flex-1 overflow-y-auto min-h-0">
            {Object.entries(groupedByFile).length === 0 && (
              <div className="px-3 py-6 text-center text-[10px] text-gray-500">
                {diagnosticsLoading ? 'Running diagnostics...' : 'No problems detected'}
              </div>
            )}
            {Object.entries(groupedByFile).map(([file, diags]) => (
              <div key={file}>
                {/* File header */}
                <div
                  className="flex items-center px-2 py-0.5 cursor-pointer hover:bg-gray-800/50 border-b border-gray-800/30"
                  onClick={() => toggleFile(file)}
                >
                  <span className="text-[9px] text-gray-500 mr-1">
                    {expandedFiles.has(file) ? '▼' : '▶'}
                  </span>
                  <span className="text-[10px] text-blue-400 truncate flex-1">{file}</span>
                  <span className="text-[9px] text-gray-500">
                    {diags.filter(d => d.severity === 'error').length}E {' '}
                    {diags.filter(d => d.severity === 'warning').length}W
                  </span>
                </div>

                {/* Diagnostics for this file */}
                {expandedFiles.has(file) && diags.map((diag, i) => (
                  <div
                    key={i}
                    className="flex items-start gap-1.5 px-2 py-0.5 pl-6 cursor-pointer hover:bg-gray-800/30 text-[10px]"
                    onClick={() => handleDiagnosticClick(diag)}
                  >
                    <span className="mt-0.5 shrink-0">{severityIcon(diag.severity)}</span>
                    <div className="min-w-0 flex-1">
                      <span className={`${
                        diag.severity === 'error' ? 'text-red-300' :
                        diag.severity === 'warning' ? 'text-yellow-300' :
                        'text-blue-300'
                      }`}>
                        {diag.message}
                      </span>
                      {diag.line > 0 && (
                        <span className="text-gray-600 ml-1">[{diag.line}:{diag.column}]</span>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
'use client';

/**
 * DebugToolbar — Debug control toolbar with breakpoints and step controls.
 *
 * This is a simplified debug toolbar. Full DAP integration would require
 * WebSocket connection to a debug adapter (debugpy, vscode-js-debug, etc.).
 * For now, this provides the UI and breakpoint management.
 */

import { useState, useCallback } from 'react';
import type { Breakpoint, DebugStatus } from './types';

export function DebugToolbar() {
  const [status, setStatus] = useState<DebugStatus>('stopped');
  const [breakpoints, setBreakpoints] = useState<Breakpoint[]>([]);
  const [showBreakpoints, setShowBreakpoints] = useState(false);

  const handleContinue = useCallback(() => {
    setStatus('running');
    // In full implementation: send DAP "continue" request
  }, []);

  const handleStepOver = useCallback(() => {
    // DAP "next" request
  }, []);

  const handleStepInto = useCallback(() => {
    // DAP "stepIn" request
  }, []);

  const handleStepOut = useCallback(() => {
    // DAP "stepOut" request
  }, []);

  const handleStop = useCallback(() => {
    setStatus('stopped');
  }, []);

  const handleRestart = useCallback(() => {
    setStatus('running');
  }, []);

  const statusColor =
    status === 'running' ? 'text-green-400' :
    status === 'paused' ? 'text-yellow-400' :
    'text-gray-500';

  const statusText =
    status === 'running' ? '● 运行中' :
    status === 'paused' ? '⏸ 已暂停' :
    '■ 已停止';

  return (
    <div className="flex items-center gap-1 px-2 py-1 bg-[#2d2d2d] border-b border-gray-700 shrink-0">
      {/* Debug control buttons */}
      <button
        onClick={handleContinue}
        disabled={status !== 'paused'}
        className="p-1 text-green-400 hover:bg-gray-700 rounded disabled:opacity-30"
        title="继续 (F5)"
      >
        ▶
      </button>
      <button
        onClick={handleStepOver}
        disabled={status !== 'paused'}
        className="p-1 text-blue-400 hover:bg-gray-700 rounded disabled:opacity-30"
        title="单步跳过 (F10)"
      >
        ⏭
      </button>
      <button
        onClick={handleStepInto}
        disabled={status !== 'paused'}
        className="p-1 text-blue-400 hover:bg-gray-700 rounded disabled:opacity-30"
        title="单步进入 (F11)"
      >
        ⬇
      </button>
      <button
        onClick={handleStepOut}
        disabled={status !== 'paused'}
        className="p-1 text-blue-400 hover:bg-gray-700 rounded disabled:opacity-30"
        title="单步跳出 (Shift+F11)"
      >
        ⬆
      </button>
      <button
        onClick={handleRestart}
        className="p-1 text-gray-400 hover:bg-gray-700 rounded"
        title="重新启动"
      >
        ⟳
      </button>
      <button
        onClick={handleStop}
        disabled={status === 'stopped'}
        className="p-1 text-red-400 hover:bg-gray-700 rounded disabled:opacity-30"
        title="停止 (Shift+F5)"
      >
        ■
      </button>

      {/* Status indicator */}
      <span className={`text-[10px] ml-2 ${statusColor}`}>
        {statusText}
      </span>

      {/* Breakpoints count */}
      <button
        onClick={() => setShowBreakpoints(!showBreakpoints)}
        className="ml-auto text-[10px] text-gray-400 hover:text-white px-2 py-0.5 rounded hover:bg-gray-700"
      >
        🔴 {breakpoints.length}
      </button>
    </div>
  );
}
