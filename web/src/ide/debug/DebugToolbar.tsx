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
