'use client';

/**
 * DebugToolbar — Debug control toolbar with breakpoints and step controls.
 * Also includes LSP Diagnostics Panel showing errors/warnings grouped by file.
 *
 * Full DAP integration would require WebSocket connection to a debug adapter
 * (debugpy, vscode-js-debug, etc.). For now, this provides the UI and
 * breakpoint/watch/callstack management with DAP integration placeholders.
 */

import { useState, useCallback, useEffect, useRef } from 'react';
import { lspDiagnostics, type LSPDiagnostic } from '@/lib/api';
import { useAppStore } from '@/lib/store';
import type { Breakpoint, DebugStatus, StackFrame, Variable } from './types';

type SeverityFilter = 'all' | 'error' | 'warning' | 'info';
type DebugTab = 'controls' | 'diagnostics' | 'breakpoints' | 'watches' | 'callstack';

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

  // Breakpoint management state
  const [newBpFile, setNewBpFile] = useState('');
  const [newBpLine, setNewBpLine] = useState('');
  const [newBpCondition, setNewBpCondition] = useState('');

  // Watch expressions state
  const [watchExpressions, setWatchExpressions] = useState<Array<{ id: string; expr: string; value: string }>>([]);
  const [newWatchExpr, setNewWatchExpr] = useState('');

  // Call stack state
  const [callStack, setCallStack] = useState<StackFrame[]>([]);

  // ── Debug Controls ──────────────────────────────────────────────────
  const handleContinue = useCallback(() => {
    setStatus('running');
    // DAP "continue" request placeholder
  }, []);

  const handleStepOver = useCallback(() => {
    // DAP "next" request placeholder
  }, []);

  const handleStepInto = useCallback(() => {
    // DAP "stepIn" request placeholder
  }, []);

  const handleStepOut = useCallback(() => {
    // DAP "stepOut" request placeholder
  }, []);

  const handleStop = useCallback(() => {
    setStatus('stopped');
    setCallStack([]);
    setWatchExpressions([]);
  }, []);

  const handleRestart = useCallback(() => {
    setStatus('running');
    // DAP "restart" request placeholder
  }, []);

  const statusColor =
    status === 'running' ? 'text-green-400' :
    status === 'paused' ? 'text-yellow-400' :
    'text-gray-500';

  const statusText =
    status === 'running' ? '● 运行中' :
    status === 'paused' ? '⏸ 已暂停' :
    '■ 已停止';

  // ── Breakpoint Management ───────────────────────────────────────────
  const addBreakpoint = useCallback(() => {
    const line = parseInt(newBpLine, 10);
    if (!newBpFile || isNaN(line) || line < 1) return;

    const bp: Breakpoint = {
      id: `bp-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
      filePath: newBpFile,
      line,
      enabled: true,
      condition: newBpCondition || undefined,
    };
    setBreakpoints((prev) => [...prev, bp]);
    setNewBpFile('');
    setNewBpLine('');
    setNewBpCondition('');
  }, [newBpFile, newBpLine, newBpCondition]);

  const removeBreakpoint = useCallback((id: string) => {
    setBreakpoints((prev) => prev.filter((bp) => bp.id !== id));
  }, []);

  const toggleBreakpoint = useCallback((id: string) => {
    setBreakpoints((prev) =>
      prev.map((bp) => (bp.id === id ? { ...bp, enabled: !bp.enabled } : bp))
    );
  }, []);

  const handleEditorLineClick = useCallback((filePath: string, line: number) => {
    // Toggle breakpoint at the given line (called from editor gutter)
    const existing = breakpoints.find((bp) => bp.filePath === filePath && bp.line === line);
    if (existing) {
      removeBreakpoint(existing.id);
    } else {
      const bp: Breakpoint = {
        id: `bp-${Date.now()}`,
        filePath,
        line,
        enabled: true,
      };
      setBreakpoints((prev) => [...prev, bp]);
    }
  }, [breakpoints, removeBreakpoint]);

  // ── Watch Expressions ───────────────────────────────────────────────
  const addWatchExpression = useCallback(() => {
    if (!newWatchExpr.trim()) return;
    const id = `watch-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`;
    setWatchExpressions((prev) => [...prev, { id, expr: newWatchExpr.trim(), value: '...' }]);
    setNewWatchExpr('');

    // Simulate evaluation (DAP evaluate request placeholder)
    // In full DAP: send "evaluate" request with expression
    setTimeout(() => {
      setWatchExpressions((prev) =>
        prev.map((w) =>
          w.id === id ? { ...w, value: `<evaluate "${w.expr}" via DAP>` } : w
        )
      );
    }, 500);
  }, [newWatchExpr]);

  const removeWatchExpression = useCallback((id: string) => {
    setWatchExpressions((prev) => prev.filter((w) => w.id !== id));
  }, []);

  const refreshWatches = useCallback(() => {
    setWatchExpressions((prev) =>
      prev.map((w) => ({ ...w, value: 'refreshing...' }))
    );
    // In full DAP: re-evaluate all expressions
    setTimeout(() => {
      setWatchExpressions((prev) =>
        prev.map((w) => ({ ...w, value: `<${w.expr}> (DAP evaluate)` }))
      );
    }, 300);
  }, []);

  // ── Call Stack ──────────────────────────────────────────────────────
  // Simulated call stack for UI demo
  const mockCallStack: StackFrame[] = [
    { id: 1, name: 'main()', filePath: 'src/index.ts', line: 42, column: 5 },
    { id: 2, name: 'handleRequest()', filePath: 'src/handler.ts', line: 18, column: 3 },
    { id: 3, name: 'processData()', filePath: 'src/processor.ts', line: 55, column: 7 },
  ];

  const [selectedFrame, setSelectedFrame] = useState<number | null>(null);

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

  useEffect(() => {
    if (activeTab === 'diagnostics') {
      fetchDiagnostics();
    }
  }, [activeTab, fetchDiagnostics]);

  const filteredDiagnostics = diagnostics.filter((d) => {
    if (severityFilter === 'all') return true;
    return d.severity === severityFilter;
  });

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

  const debugTabButton = (tab: DebugTab, label: string, badge?: React.ReactNode) => (
    <button
      onClick={() => setActiveTab(tab)}
      className={`px-2 py-1 text-[10px] flex items-center gap-1 ${
        activeTab === tab ? 'text-white border-b-2 border-blue-400' : 'text-gray-500 hover:text-gray-300'
      }`}
    >
      {label}
      {badge}
    </button>
  );

  return (
    <div className="flex flex-col h-full">
      {/* Tab bar */}
      <div className="flex items-center border-b border-gray-700 shrink-0 overflow-x-auto">
        {debugTabButton('controls', 'Debug')}
        {debugTabButton('diagnostics', 'Problems',
          <span className="flex gap-0.5">
            {severityBadge('error')}
            {severityBadge('warning')}
          </span>
        )}
        {debugTabButton('breakpoints', `BPs (${breakpoints.length})`)}
        {debugTabButton('watches', 'Watches')}
        {debugTabButton('callstack', 'Call Stack')}
      </div>

      {/* ── Controls Tab ──────────────────────────────────────────────── */}
      {activeTab === 'controls' && (
        <div className="flex items-center gap-1 px-2 py-1 bg-[#2d2d2d] shrink-0">
          <button onClick={handleContinue} disabled={status !== 'paused'}
            className="p-1 text-green-400 hover:bg-gray-700 rounded disabled:opacity-30" title="继续 (F5)">▶</button>
          <button onClick={handleStepOver} disabled={status !== 'paused'}
            className="p-1 text-blue-400 hover:bg-gray-700 rounded disabled:opacity-30" title="单步跳过 (F10)">⏭</button>
          <button onClick={handleStepInto} disabled={status !== 'paused'}
            className="p-1 text-blue-400 hover:bg-gray-700 rounded disabled:opacity-30" title="单步进入 (F11)">⬇</button>
          <button onClick={handleStepOut} disabled={status !== 'paused'}
            className="p-1 text-blue-400 hover:bg-gray-700 rounded disabled:opacity-30" title="单步跳出 (Shift+F11)">⬆</button>
          <button onClick={handleRestart}
            className="p-1 text-gray-400 hover:bg-gray-700 rounded" title="重新启动">⟳</button>
          <button onClick={handleStop} disabled={status === 'stopped'}
            className="p-1 text-red-400 hover:bg-gray-700 rounded disabled:opacity-30" title="停止 (Shift+F5)">■</button>
          <span className={`text-[10px] ml-2 ${statusColor}`}>{statusText}</span>
          {/* Quick BP toggle */}
          <button
            onClick={() => setActiveTab('breakpoints')}
            className="ml-auto text-[10px] text-gray-400 hover:text-white px-2 py-0.5 rounded hover:bg-gray-700"
          >
            🔴 {breakpoints.length}
          </button>
        </div>
      )}

      {/* ── Breakpoints Tab ────────────────────────────────────────────── */}
      {activeTab === 'breakpoints' && (
        <div className="flex flex-col flex-1 min-h-0">
          {/* Add breakpoint form */}
          <div className="px-2 py-1.5 border-b border-gray-700 space-y-1 shrink-0">
            <div className="text-[9px] text-gray-500 font-semibold uppercase tracking-wider">Add Breakpoint</div>
            <div className="flex gap-1">
              <input
                type="text"
                value={newBpFile}
                onChange={(e) => setNewBpFile(e.target.value)}
                placeholder="File path..."
                className="flex-1 bg-gray-800 text-gray-200 text-[10px] border border-gray-700 rounded px-1.5 py-0.5 focus:outline-none focus:border-blue-500"
              />
              <input
                type="number"
                value={newBpLine}
                onChange={(e) => setNewBpLine(e.target.value)}
                placeholder="Line"
                min={1}
                className="w-14 bg-gray-800 text-gray-200 text-[10px] border border-gray-700 rounded px-1.5 py-0.5 focus:outline-none focus:border-blue-500"
              />
              <button
                onClick={addBreakpoint}
                disabled={!newBpFile || !newBpLine}
                className="px-1.5 py-0.5 bg-red-700 text-white text-[10px] rounded hover:bg-red-600 disabled:opacity-40"
              >
                + BP
              </button>
            </div>
            <input
              type="text"
              value={newBpCondition}
              onChange={(e) => setNewBpCondition(e.target.value)}
              placeholder="Condition (optional)"
              className="w-full bg-gray-800 text-gray-200 text-[10px] border border-gray-700 rounded px-1.5 py-0.5 focus:outline-none focus:border-blue-500"
            />
          </div>

          {/* Breakpoints list */}
          <div className="flex-1 overflow-y-auto min-h-0">
            {breakpoints.length === 0 && (
              <div className="px-3 py-6 text-center text-[10px] text-gray-500">No breakpoints set</div>
            )}
            {breakpoints.map((bp) => (
              <div key={bp.id} className="flex items-center gap-1 px-2 py-1 hover:bg-gray-800/30 text-[10px]">
                <input
                  type="checkbox"
                  checked={bp.enabled}
                  onChange={() => toggleBreakpoint(bp.id)}
                  className="w-2.5 h-2.5"
                />
                <span className={`${bp.enabled ? 'text-red-400' : 'text-gray-600'}`}>🔴</span>
                <span className="text-blue-400 truncate flex-1">{bp.filePath}</span>
                <span className="text-gray-500 shrink-0">:{bp.line}</span>
                <button
                  onClick={() => removeBreakpoint(bp.id)}
                  className="text-gray-600 hover:text-red-400 px-0.5"
                >
                  ×
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Watches Tab ────────────────────────────────────────────────── */}
      {activeTab === 'watches' && (
        <div className="flex flex-col flex-1 min-h-0">
          {/* Add watch form */}
          <div className="px-2 py-1.5 border-b border-gray-700 shrink-0">
            <div className="flex items-center gap-1 mb-1">
              <span className="text-[9px] text-gray-500 font-semibold uppercase tracking-wider">Watch Expressions</span>
              <button
                onClick={refreshWatches}
                disabled={watchExpressions.length === 0}
                className="ml-auto text-[9px] text-gray-500 hover:text-white px-1 py-0.5 rounded hover:bg-gray-700 disabled:opacity-40"
              >
                ⟳
              </button>
            </div>
            <div className="flex gap-1">
              <input
                type="text"
                value={newWatchExpr}
                onChange={(e) => setNewWatchExpr(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && addWatchExpression()}
                placeholder="Add expression..."
                className="flex-1 bg-gray-800 text-gray-200 text-[10px] border border-gray-700 rounded px-1.5 py-0.5 focus:outline-none focus:border-blue-500"
              />
              <button
                onClick={addWatchExpression}
                disabled={!newWatchExpr.trim()}
                className="px-1.5 py-0.5 bg-blue-700 text-white text-[10px] rounded hover:bg-blue-600 disabled:opacity-40"
              >
                +
              </button>
            </div>
          </div>

          {/* Watch list */}
          <div className="flex-1 overflow-y-auto min-h-0">
            {watchExpressions.length === 0 && (
              <div className="px-3 py-6 text-center text-[10px] text-gray-500">
                No watch expressions. Add variables to watch.
              </div>
            )}
            {watchExpressions.map((w) => (
              <div key={w.id} className="flex items-center gap-1 px-2 py-1 hover:bg-gray-800/30 text-[10px] group">
                <span className="text-yellow-400 font-mono shrink-0">{w.expr}</span>
                <span className="text-gray-600 mx-1">=</span>
                <span className="text-green-400 font-mono truncate flex-1">{w.value}</span>
                <button
                  onClick={() => removeWatchExpression(w.id)}
                  className="text-gray-600 hover:text-red-400 px-0.5 opacity-0 group-hover:opacity-100"
                >
                  ×
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Call Stack Tab ─────────────────────────────────────────────── */}
      {activeTab === 'callstack' && (
        <div className="flex flex-col flex-1 min-h-0">
          <div className="px-2 py-1 border-b border-gray-700 shrink-0">
            <span className="text-[9px] text-gray-500 font-semibold uppercase tracking-wider">Call Stack</span>
          </div>
          <div className="flex-1 overflow-y-auto min-h-0">
            {status === 'stopped' && (
              <div className="px-3 py-6 text-center text-[10px] text-gray-500">
                Debugger is stopped. Start debugging to see the call stack.
              </div>
            )}
            {status !== 'stopped' && callStack.length === 0 && (
              <div className="px-3 py-4 text-center text-[10px] text-gray-500">
                {/* Show mock call stack for UI demo */}
                <div className="text-[9px] text-gray-600 mb-2 italic">(DAP integration placeholder - showing demo data)</div>
                {mockCallStack.map((frame) => (
                  <div
                    key={frame.id}
                    className={`flex items-center gap-1 px-2 py-1 text-[10px] cursor-pointer hover:bg-gray-800/30 ${
                      selectedFrame === frame.id ? 'bg-gray-800/50' : ''
                    }`}
                    onClick={() => {
                      setSelectedFrame(frame.id);
                      window.dispatchEvent(new CustomEvent('navigate-to-line', {
                        detail: { path: frame.filePath, line: frame.line },
                      }));
                    }}
                  >
                    <span className="text-blue-400 font-mono shrink-0">{frame.name}</span>
                    <span className="text-gray-600 mx-1">at</span>
                    <span className="text-gray-400 truncate flex-1">{frame.filePath}</span>
                    <span className="text-gray-500 shrink-0">:{frame.line}</span>
                  </div>
                ))}
              </div>
            )}
            {callStack.length > 0 && callStack.map((frame) => (
              <div
                key={frame.id}
                className={`flex items-center gap-1 px-2 py-1 text-[10px] cursor-pointer hover:bg-gray-800/30 ${
                  selectedFrame === frame.id ? 'bg-gray-800/50' : ''
                }`}
                onClick={() => {
                  setSelectedFrame(frame.id);
                  window.dispatchEvent(new CustomEvent('navigate-to-line', {
                    detail: { path: frame.filePath, line: frame.line },
                  }));
                }}
              >
                <span className="text-blue-400 font-mono shrink-0">{frame.name}</span>
                <span className="text-gray-600 mx-1">at</span>
                <span className="text-gray-400 truncate flex-1">{frame.filePath}</span>
                <span className="text-gray-500 shrink-0">:{frame.line}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* ── Diagnostics Tab ──────────────────────────────────────────── */}
      {activeTab === 'diagnostics' && (
        <div className="flex flex-col flex-1 min-h-0">
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

          <div className="flex-1 overflow-y-auto min-h-0">
            {Object.entries(groupedByFile).length === 0 && (
              <div className="px-3 py-6 text-center text-[10px] text-gray-500">
                {diagnosticsLoading ? 'Running diagnostics...' : 'No problems detected'}
              </div>
            )}
            {Object.entries(groupedByFile).map(([file, diags]) => (
              <div key={file}>
                <div className="flex items-center px-2 py-0.5 cursor-pointer hover:bg-gray-800/50 border-b border-gray-800/30"
                  onClick={() => toggleFile(file)}>
                  <span className="text-[9px] text-gray-500 mr-1">
                    {expandedFiles.has(file) ? '▼' : '▶'}
                  </span>
                  <span className="text-[10px] text-blue-400 truncate flex-1">{file}</span>
                  <span className="text-[9px] text-gray-500">
                    {diags.filter(d => d.severity === 'error').length}E {' '}
                    {diags.filter(d => d.severity === 'warning').length}W
                  </span>
                </div>
                {expandedFiles.has(file) && diags.map((diag, i) => (
                  <div key={i} className="flex items-start gap-1.5 px-2 py-0.5 pl-6 cursor-pointer hover:bg-gray-800/30 text-[10px]"
                    onClick={() => handleDiagnosticClick(diag)}>
                    <span className="mt-0.5 shrink-0">{severityIcon(diag.severity)}</span>
                    <div className="min-w-0 flex-1">
                      <span className={`${
                        diag.severity === 'error' ? 'text-red-300' :
                        diag.severity === 'warning' ? 'text-yellow-300' : 'text-blue-300'
                      }`}>{diag.message}</span>
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
