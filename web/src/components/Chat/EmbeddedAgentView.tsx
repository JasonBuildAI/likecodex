'use client';

import { memo, useState, useCallback, useRef, useEffect } from 'react';
import { useAppStore, type AgentMode } from '@/lib/store';
import { streamChat } from '@/lib/api';
import { useAgentViewMode } from '@/hooks/useAgentViewMode';

// ── Mode config (compact) ──────────────────────────────────────────────
const MODE_BUTTONS: Record<AgentMode, { label: string; shortLabel: string; color: string }> = {
  ask: { label: 'Ask', shortLabel: 'A', color: 'text-emerald-400 border-emerald-500/30 bg-emerald-500/10' },
  agent: { label: 'Agent', shortLabel: 'Ag', color: 'text-blue-400 border-blue-500/30 bg-blue-500/10' },
  manual: { label: 'Manual', shortLabel: 'M', color: 'text-amber-400 border-amber-500/30 bg-amber-500/10' },
};

// ── Component ──────────────────────────────────────────────────────────
export const EmbeddedAgentView = memo(function EmbeddedAgentView() {
  const agentMode = useAppStore((s) => s.agentMode);
  const setAgentMode = useAppStore((s) => s.setAgentMode);
  const {
    isStreaming,
    setIsStreaming,
    addMessage,
    appendToLastMessage,
    upsertToolDispatch,
    currentSessionId,
  } = useAppStore();
  const { mode: viewMode, setMode: setViewMode } = useAgentViewMode();

  const [input, setInput] = useState('');
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const abortRef = useRef<AbortController | null>(null);

  // Auto-focus input on mount
  useEffect(() => {
    inputRef.current?.focus();
  }, []);

  // Send message
  const handleSend = useCallback(async () => {
    const prompt = input.trim();
    if (!prompt || isStreaming) return;

    setInput('');
    setIsStreaming(true);

    addMessage({
      id: `user-${Date.now()}`,
      role: 'user',
      content: prompt,
      timestamp: Date.now(),
    });

    const controller = new AbortController();
    abortRef.current = controller;

    try {
      await streamChat(
        prompt,
        currentSessionId,
        {
          onMessage: addMessage,
          onAppend: appendToLastMessage,
          onUpsertToolDispatch: upsertToolDispatch,
          onStreamFinished: () => setIsStreaming(false),
        },
        controller.signal,
        agentMode,
      );
    } catch (err) {
      console.warn('[EmbeddedAgentView] streamChat failed:', err);
      setIsStreaming(false);
    }
  }, [input, isStreaming, currentSessionId, agentMode, addMessage, appendToLastMessage, upsertToolDispatch, setIsStreaming]);

  // Stop streaming
  const handleStop = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    setIsStreaming(false);
  }, [setIsStreaming]);

  // Keyboard: Enter to send, Shift+Enter for newline
  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        handleSend();
      }
    },
    [handleSend]
  );

  const isCompact = viewMode === 'chat';

  return (
    <div
      className={`flex flex-col border border-border rounded-lg bg-surface overflow-hidden ${
        isCompact ? 'h-auto min-h-[120px]' : 'h-full min-h-[200px]'
      }`}
    >
      {/* ── Header: mode switcher + view toggle ──────────────────── */}
      <div className="flex items-center gap-1 px-2 py-1.5 border-b border-border/60">
        {(Object.keys(MODE_BUTTONS) as AgentMode[]).map((mode) => {
          const cfg = MODE_BUTTONS[mode];
          const isActive = agentMode === mode;
          return (
            <button
              key={mode}
              onClick={() => setAgentMode(mode)}
              title={cfg.label}
              className={`px-2 py-1 rounded text-[10px] font-medium border transition-all ${
                isActive
                  ? cfg.color
                  : 'text-muted border-transparent hover:text-foreground hover:bg-accent/10'
              }`}
            >
              {isCompact ? cfg.shortLabel : cfg.label}
            </button>
          );
        })}

        {/* Spacer */}
        <div className="flex-1" />

        {/* View mode toggle */}
        <button
          onClick={() => setViewMode(viewMode === 'agent' ? 'chat' : 'agent')}
          title={`Switch to ${viewMode === 'agent' ? 'chat' : 'agent'} view`}
          className="text-[9px] text-muted hover:text-foreground px-1.5 py-0.5 rounded hover:bg-accent/10 transition-colors"
        >
          {viewMode === 'agent' ? '◧' : '◨'}
        </button>
      </div>

      {/* ── Messages preview (only in non-compact mode) ──────────── */}
      {!isCompact && <MessagePreview />}

      {/* ── Input area ───────────────────────────────────────────── */}
      <div className="flex items-end gap-2 px-2 py-2 border-t border-border/60">
        <textarea
          ref={inputRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask or instruct…"
          rows={1}
          disabled={isStreaming}
          className={`flex-1 resize-none rounded-md border border-border/60 bg-background/60 px-2.5 py-1.5 text-xs text-foreground placeholder:text-muted/50 focus:outline-none focus:ring-1 focus:ring-primary/40 disabled:opacity-50 transition-colors ${
            isCompact ? 'max-h-16' : 'max-h-32'
          }`}
        />

        {isStreaming ? (
          <button
            type="button"
            onClick={handleStop}
            className="shrink-0 h-7 px-3 rounded-md bg-red-500/20 text-red-400 text-[10px] font-medium border border-red-500/30 hover:bg-red-500/30 transition-colors"
          >
            Stop
          </button>
        ) : (
          <button
            type="button"
            onClick={handleSend}
            disabled={!input.trim()}
            className="shrink-0 h-7 px-3 rounded-md bg-primary text-white text-[10px] font-medium hover:bg-blue-600 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            Send
          </button>
        )}
      </div>
    </div>
  );
});

// ── Message preview sub-component ──────────────────────────────────────
const MessagePreview = memo(function MessagePreview() {
  const messages = useAppStore((s) => s.messages);
  const scrollRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom
  useEffect(() => {
    const el = scrollRef.current;
    if (el) el.scrollTop = el.scrollHeight;
  }, [messages.length]);

  // Show last 5 messages
  const visible = messages.slice(-5);

  if (visible.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center px-4 py-6">
        <p className="text-[11px] text-muted/50">Start a conversation…</p>
      </div>
    );
  }

  return (
    <div
      ref={scrollRef}
      className="flex-1 overflow-y-auto px-3 py-2 space-y-2 scrollbar-thin min-h-0"
    >
      {visible.map((msg) => (
        <div key={msg.id} className="text-[11px]">
          <span
            className={`inline-block px-1.5 py-0.5 rounded text-[9px] font-medium mr-1.5 ${
              msg.role === 'user'
                ? 'bg-blue-500/10 text-blue-400'
                : msg.role === 'tool'
                  ? 'bg-purple-500/10 text-purple-400'
                  : 'bg-accent/10 text-muted'
            }`}
          >
            {msg.role}
          </span>
          <span className="text-foreground/80 line-clamp-3">
            {msg.content || '…'}
          </span>
        </div>
      ))}
    </div>
  );
});
