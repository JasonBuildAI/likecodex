'use client';

/**
 * TerminalPanel — AI-powered terminal panel.
 *
 * Features:
 * - Multi-tab terminal sessions
 * - Command input with history (↑↓)
 * - AI command suggestion (Cmd+K)
 * - Error auto-diagnosis
 *
 * == Phase 6: xterm.js Terminal Integration Plan ==
 * Replace the current <div>-based output display with a full-featured xterm.js
 * terminal instance for each session:
 *
 * 1. Install: npm install xterm @xterm/xterm @xterm/addon-fit @xterm/addon-web-links
 * 2. Each TerminalSession gets an xterm.Terminal instance attached in a ref
 * 3. Terminal.fitAddon handles resize; Terminal.webLinksAddon enables clickable URLs
 * 4. Input is captured from xterm.js key events rather than a separate <input>
 * 5. The backend streams output lines into terminal.write() in real time
 * 6. xterm.js search addon provides in-terminal Ctrl+F find
 * 7. The AI bars (AICommandInput, error diagnosis) remain as overlay panels
 *    docked below the xterm container
 *
 * Implementation steps:
 * - src/ide/terminal/xterm-manager.ts — createTerminal(), resizeHandler(), disposeTerminal()
 * - src/ide/terminal/TerminalPanel.tsx — embed <div ref={terminalRef}> instead of raw <div> lines
 * - src/ide/terminal/terminalStore.ts — store Terminal instance references, wire fitAddon
 */

import { useState, useRef, useEffect, useCallback, useMemo } from 'react';
import { useTerminalStore, type TerminalSession } from './terminalStore';
import { getCompletions, applyCompletion, type CompletionItem } from './terminalCompletion';
import { TerminalShortcutsHelp } from './TerminalShortcutsHelp';

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
  const [showHistorySearch, setShowHistorySearch] = useState(false);
  const [historySearchQuery, setHistorySearchQuery] = useState('');
  const [historySearchIdx, setHistorySearchIdx] = useState(0);
  const [completions, setCompletions] = useState<CompletionItem[]>([]);
  const [completionIdx, setCompletionIdx] = useState(-1);
  const [showHelp, setShowHelp] = useState(false);
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const historySearchRef = useRef<HTMLInputElement>(null);

  const activeSession = sessions.find((s) => s.id === activeSessionId);

  // Filtered history from current session
  const filteredHistory = useMemo(() => {
    if (!activeSession) return [];
    if (!historySearchQuery.trim()) return activeSession.history;
    const q = historySearchQuery.toLowerCase();
    return activeSession.history.filter((cmd) => cmd.toLowerCase().includes(q));
  }, [activeSession, historySearchQuery]);

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

  // Focus history search input
  useEffect(() => {
    if (showHistorySearch && historySearchRef.current) {
      historySearchRef.current.focus();
    }
  }, [showHistorySearch]);

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
      } else if (e.key === 'Tab') {
        e.preventDefault();
        if (!activeSession) return;
        // Get completions if not already shown
        if (completions.length === 0) {
          const items = getCompletions(input, input.length, activeSession.history);
          setCompletions(items);
          setCompletionIdx(0);
          if (items.length > 0) {
            const result = applyCompletion(input, input.length, items[0]);
            setInput(result.text);
          }
        } else {
          // Cycle through completions
          const nextIdx = (completionIdx + 1) % completions.length;
          setCompletionIdx(nextIdx);
          const lastSpace = input.lastIndexOf(' ') + 1;
          const baseText = input.slice(0, lastSpace);
          setInput(baseText + completions[nextIdx].text + ' ');
        }
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
      } else if ((e.metaKey || e.ctrlKey) && e.key === 'r') {
        e.preventDefault();
        setShowHistorySearch(true);
        setHistorySearchQuery('');
        setHistorySearchIdx(0);
      } else if (e.key === 'Escape') {
        if (completions.length > 0) {
          e.preventDefault();
          setCompletions([]);
          setCompletionIdx(-1);
        }
      } else if ((e.metaKey || e.ctrlKey) && e.shiftKey && e.key === '/') {
        e.preventDefault();
        setShowHelp(true);
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
        <button
          onClick={() => setShowHelp(true)}
          className="text-xs text-gray-500 hover:text-white px-1"
          title="快捷键帮助 (Ctrl+Shift+/)"
        >
          ?
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

      {/* Completion popup */}
      {completions.length > 0 && (
        <div className="border-t border-gray-700 bg-[#252535] px-2 py-1 shrink-0">
          <div className="flex items-center gap-1.5 flex-wrap">
            {completions.map((item, i) => (
              <span
                key={i}
                className={`text-[10px] px-1.5 py-0.5 rounded cursor-pointer ${
                  i === completionIdx
                    ? 'bg-blue-600 text-white'
                    : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
                }`}
                onClick={() => {
                  const lastSpace = input.lastIndexOf(' ') + 1;
                  const baseText = input.slice(0, lastSpace);
                  setInput(baseText + item.text + ' ');
                  setCompletions([]);
                  setCompletionIdx(-1);
                }}
                title={item.description}
              >
                {item.text}
              </span>
            ))}
          </div>
          <div className="text-[9px] text-gray-500 mt-0.5">
            Tab 循环 · Enter 选择 · Esc 关闭
          </div>
        </div>
      )}

      {/* History search overlay (Ctrl+R) */}
      {showHistorySearch && (
        <div className="border-t border-gray-700 bg-[#252535] p-2 shrink-0">
          <div className="flex items-center gap-2">
            <span className="text-xs text-yellow-400 shrink-0">(reverse-i-search)`</span>
            <input
              ref={historySearchRef}
              type="text"
              value={historySearchQuery}
              onChange={(e) => {
                setHistorySearchQuery(e.target.value);
                setHistorySearchIdx(0);
              }}
              onKeyDown={(e) => {
                if (e.key === 'Escape') {
                  e.preventDefault();
                  setShowHistorySearch(false);
                  inputRef.current?.focus();
                } else if (e.key === 'Enter') {
                  e.preventDefault();
                  if (filteredHistory.length > 0) {
                    const cmd = filteredHistory[historySearchIdx];
                    setInput(cmd);
                    setShowHistorySearch(false);
                    inputRef.current?.focus();
                  }
                } else if (e.key === 'ArrowUp' || e.key === 'ArrowDown') {
                  e.preventDefault();
                  const direction = e.key === 'ArrowUp' ? -1 : 1;
                  setHistorySearchIdx((prev) => {
                    const max = filteredHistory.length - 1;
                    if (max < 0) return 0;
                    const next = prev + direction;
                    if (next < 0) return max;
                    if (next > max) return 0;
                    return next;
                  });
                }
              }}
              className="flex-1 bg-transparent text-gray-200 text-xs font-mono focus:outline-none"
              placeholder="搜索命令历史..."
            />
            <span className="text-xs text-yellow-400 shrink-0">'</span>
          </div>
          {filteredHistory.length > 0 && (
            <div className="mt-1">
              <div className="text-[10px] text-blue-300 bg-blue-900/30 px-1.5 py-0.5 rounded font-mono">
                {filteredHistory[historySearchIdx]}
              </div>
              <div className="text-[9px] text-gray-500 mt-0.5">
                {historySearchIdx + 1}/{filteredHistory.length} 匹配
              </div>
            </div>
          )}
          {filteredHistory.length === 0 && historySearchQuery && (
            <div className="text-[10px] text-gray-500 mt-1">无匹配结果</div>
          )}
        </div>
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

      {/* Help modal */}
      {showHelp && (
        <TerminalShortcutsHelp onClose={() => setShowHelp(false)} />
      )}
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
