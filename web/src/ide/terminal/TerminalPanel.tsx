'use client';

/**
 * TerminalPanel — AI-powered terminal panel.
 *
 * Features:
 * - Multi-tab terminal sessions
 * - Command input with history (↑↓)
 * - AI command suggestion (Cmd+K)
 * - Error auto-diagnosis
 */

import { useState, useRef, useEffect, useCallback } from 'react';
import { useTerminalStore, type TerminalSession } from './terminalStore';

export function TerminalPanel() {
  const {
    sessions,
    activeSessionId,
    showAIInput,
    isExecuting,
    createSession,
    closeSession,
    setActiveSession,
    executeCommand,
    toggleAIInput,
    suggestCommand,
  } = useTerminalStore();

  const [input, setInput] = useState('');
  const [historyIdx, setHistoryIdx] = useState(-1);
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  const activeSession = sessions.find((s) => s.id === activeSessionId);

  // Auto-scroll to bottom
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [activeSession?.lines]);

  // Create initial session
  useEffect(() => {
    if (sessions.length === 0) {
      createSession();
    }
  }, [sessions.length, createSession]);

  const handleSubmit = useCallback(() => {
    if (!input.trim() || isExecuting) return;
    executeCommand(input.trim());
    setInput('');
    setHistoryIdx(-1);
  }, [input, isExecuting, executeCommand]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLInputElement>) => {
      if (e.key === 'Enter') {
        e.preventDefault();
        handleSubmit();
      } else if (e.key === 'ArrowUp') {
        e.preventDefault();
        if (!activeSession || activeSession.history.length === 0) return;
        const newIdx = Math.min(historyIdx + 1, activeSession.history.length - 1);
        setHistoryIdx(newIdx);
        setInput(activeSession.history[newIdx] || '');
      } else if (e.key === 'ArrowDown') {
        e.preventDefault();
        if (!activeSession) return;
        const newIdx = Math.max(historyIdx - 1, -1);
        setHistoryIdx(newIdx);
        setInput(newIdx === -1 ? '' : activeSession.history[newIdx] || '');
      } else if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        toggleAIInput();
      }
    },
    [handleSubmit, historyIdx, activeSession, toggleAIInput]
  );

  if (!activeSession) {
    return (
      <div className="flex items-center justify-center h-full text-sm text-gray-500">
        <button
          onClick={() => createSession()}
          className="px-3 py-1 bg-blue-600 text-white text-xs rounded hover:bg-blue-700"
        >
          + 新建终端
        </button>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full bg-[#1e1e2e]">
      {/* Tab bar */}
      <div className="flex items-center h-7 bg-[#181825] px-1 gap-0.5 shrink-0">
        {sessions.map((s) => (
          <div
            key={s.id}
            onClick={() => setActiveSession(s.id)}
            className={`px-2.5 py-0.5 text-[10px] rounded-t cursor-pointer transition-colors flex items-center gap-1 ${
              s.id === activeSessionId
                ? 'bg-[#1e1e2e] text-blue-300'
                : 'text-gray-500 hover:text-gray-300'
            }`}
          >
            {s.name}
            {s.isRunning && (
              <span className="h-1.5 w-1.5 rounded-full bg-green-400 animate-pulse" />
            )}
            {sessions.length > 1 && (
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  closeSession(s.id);
                }}
                className="ml-1 text-gray-600 hover:text-red-400"
              >
                ×
              </button>
            )}
          </div>
        ))}
        <button
          onClick={() => createSession()}
          className="ml-auto text-xs text-gray-500 hover:text-white px-2"
          title="新建终端"
        >
          +
        </button>
      </div>

      {/* Terminal output */}
      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto p-2 font-mono text-xs leading-relaxed min-h-0"
      >
        {activeSession.lines.map((line, i) => (
          <div
            key={i}
            className={
              line.type === 'input'
                ? 'text-blue-300'
                : line.type === 'error'
                  ? 'text-red-400'
                  : line.type === 'system'
                    ? 'text-gray-500'
                    : 'text-gray-300'
            }
          >
            {line.type === 'input' ? `$ ${line.content}` : line.content}
          </div>
        ))}
        {activeSession.isRunning && (
          <div className="text-yellow-400 animate-pulse">▊</div>
        )}
      </div>

      {/* AI Command Input */}
      {showAIInput && (
        <AICommandInput
          onSuggest={suggestCommand}
          onExecute={(cmd) => {
            executeCommand(cmd);
            toggleAIInput();
          }}
          onClose={toggleAIInput}
        />
      )}

      {/* Command input */}
      <div className="flex items-center gap-2 px-2 py-1.5 border-t border-gray-700 shrink-0">
        <span className="text-xs text-green-400 font-mono shrink-0">
          {activeSession.cwd.split(/[\\/]/).pop() || '~'}$
        </span>
        <input
          ref={inputRef}
          type="text"
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          disabled={isExecuting}
          placeholder="输入命令... (↑↓ 历史, Cmd+K AI 建议)"
          className="flex-1 bg-transparent text-gray-200 text-xs font-mono focus:outline-none placeholder-gray-600 disabled:opacity-50"
          autoFocus
        />
      </div>
    </div>
  );
}

// ── AI Command Input ──────────────────────────────────────────────

function AICommandInput({
  onSuggest,
  onExecute,
  onClose,
}: {
  onSuggest: (desc: string) => Promise<string | null>;
  onExecute: (cmd: string) => void;
  onClose: () => void;
}) {
  const [description, setDescription] = useState('');
  const [suggestedCmd, setSuggestedCmd] = useState('');
  const [isLoading, setIsLoading] = useState(false);

  const handleGenerate = useCallback(async () => {
    if (!description.trim()) return;
    setIsLoading(true);
    const cmd = await onSuggest(description.trim());
    setIsLoading(false);
    if (cmd) setSuggestedCmd(cmd);
  }, [description, onSuggest]);

  return (
    <div className="border-t border-gray-700 bg-[#252535] p-2 shrink-0">
      {!suggestedCmd ? (
        <div className="flex gap-2">
          <input
            type="text"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                handleGenerate();
              }
              if (e.key === 'Escape') onClose();
            }}
            placeholder="描述你想执行的命令... (Enter 生成, Esc 取消)"
            className="flex-1 bg-[#1e1e2e] text-gray-200 text-xs border border-gray-600 rounded px-2 py-1 focus:outline-none focus:border-blue-500"
            autoFocus
            disabled={isLoading}
          />
          <button
            onClick={handleGenerate}
            disabled={isLoading || !description.trim()}
            className="px-3 py-1 bg-blue-600 text-white text-xs rounded hover:bg-blue-700 disabled:opacity-40"
          >
            {isLoading ? '生成中...' : '生成'}
          </button>
        </div>
      ) : (
        <div>
          <div className="text-[10px] text-gray-500 mb-1">AI 建议的命令:</div>
          <div className="flex items-center gap-2">
            <code className="flex-1 bg-[#1e1e2e] text-green-400 px-2 py-1 rounded text-xs font-mono">
              {suggestedCmd}
            </code>
            <button
              onClick={() => onExecute(suggestedCmd)}
              className="px-2.5 py-1 bg-green-600 text-white text-xs rounded hover:bg-green-700"
            >
              运行
            </button>
            <button
              onClick={() => setSuggestedCmd('')}
              className="px-2.5 py-1 bg-gray-600 text-white text-xs rounded hover:bg-gray-700"
            >
              重试
            </button>
            <button
              onClick={onClose}
              className="px-2.5 py-1 text-gray-400 text-xs hover:text-white"
            >
              取消
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
