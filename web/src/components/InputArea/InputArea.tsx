'use client';

import React, { useState, useRef, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useAppStore } from '@/lib/store';
import { ModeCapsule } from './ModeCapsule';

interface InputAreaProps {
  onSubmit: (prompt: string) => void;
  inputHistory: string[];
  placeholder?: string;
}

// ── Auto-resize Textarea Hook ───────────────────────────────────────────
function useAutoResize(value: string) {
  const ref = useRef<HTMLTextAreaElement>(null);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    el.style.height = 'auto';
    el.style.height = `${Math.min(el.scrollHeight, 200)}px`;
  }, [value]);
  return ref;
}

// ── InputArea Component ─────────────────────────────────────────────────
export const InputArea: React.FC<InputAreaProps> = ({ onSubmit, inputHistory, placeholder }) => {
  const [input, setInput] = useState('');
  const [historyIndex, setHistoryIndex] = useState(-1);
  const [isFocused, setIsFocused] = useState(false);
  const agentMode = useAppStore((s) => s.agentMode);
  const isStreaming = useAppStore((s) => s.isStreaming);
  const activeFilePath = useAppStore((s) => s.activeFilePath);
  const openFiles = useAppStore((s) => s.openFiles);
  const textareaRef = useAutoResize(input);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isStreaming) return;
    onSubmit(input);
    setInput('');
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    // Ctrl/Cmd + Enter to submit
    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
      e.preventDefault();
      handleSubmit(e as any);
      return;
    }
    // Escape to blur
    if (e.key === 'Escape') {
      textareaRef.current?.blur();
      return;
    }
    // Arrow up for history (when input is empty)
    if (e.key === 'ArrowUp' && input === '') {
      e.preventDefault();
      setHistoryIndex((prev) => {
        const next = Math.min(prev + 1, inputHistory.length - 1);
        if (inputHistory[next] !== undefined) setInput(inputHistory[next]);
        return next;
      });
      return;
    }
    // Arrow down for history
    if (e.key === 'ArrowDown' && historyIndex >= 0) {
      e.preventDefault();
      setHistoryIndex((prev) => {
        const next = prev - 1;
        if (next < 0) {
          setInput('');
          return -1;
        }
        setInput(inputHistory[next] || '');
        return next;
      });
    }
  };

  const handleStop = () => {
    // Emit a stop event
    window.dispatchEvent(new CustomEvent('likecodex:stop'));
  };

  // Static class maps (Tailwind JIT can't parse dynamic class names)
  const modeGlowMap = {
    ask: 'from-emerald-500/20 via-purple-500/20 to-pink-500/20',
    agent: 'from-blue-500/20 via-purple-500/20 to-pink-500/20',
    manual: 'from-amber-500/20 via-purple-500/20 to-pink-500/20',
  };
  const modeBorderColor = {
    ask: 'rgb(16 185 129 / 0.5)',
    agent: 'rgb(59 130 246 / 0.5)',
    manual: 'rgb(245 158 11 / 0.5)',
  };

  const defaultPlaceholder =
    agentMode === 'ask'
      ? 'Ask questions without making changes...'
      : agentMode === 'manual'
        ? 'Describe your task (each step requires approval)...'
        : 'What would you like to build? Use @ to reference files';

  // Modified files pills
  const modifiedFiles = openFiles.filter((f) => f.modified).slice(0, 3);

  return (
    <div className="absolute bottom-0 left-0 right-0 p-4 bg-gradient-to-t from-surface via-surface to-transparent">
      <form onSubmit={handleSubmit} className="max-w-2xl mx-auto">
        {/* Mode Selector */}
        <ModeCapsule />

        {/* Main Input Box */}
        <div className="relative group">
          {/* Gradient glow on focus */}
          <motion.div
            animate={{
              opacity: isFocused ? 0.6 : 0,
            }}
            transition={{ duration: 0.3 }}
            className={`absolute inset-0 bg-gradient-to-r ${modeGlowMap[agentMode]} rounded-2xl blur-xl`}
          />

          {/* Input container */}
          <motion.div
            animate={{
              borderColor: isFocused
                ? modeBorderColor[agentMode]
                : 'rgb(42 42 42)',
            }}
            className="relative bg-background/90 backdrop-blur-md border rounded-2xl shadow-2xl overflow-hidden"
          >
            {/* Textarea */}
            <textarea
              ref={textareaRef}
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={handleKeyDown}
              onFocus={() => setIsFocused(true)}
              onBlur={() => setIsFocused(false)}
              placeholder={placeholder || defaultPlaceholder}
              className="w-full bg-transparent px-4 py-3.5 pr-24 text-sm focus:outline-none resize-none min-h-[56px] max-h-[200px] placeholder:text-muted/60"
              rows={1}
              disabled={isStreaming}
            />

            {/* Modified files pills */}
            {modifiedFiles.length > 0 && (
              <div className="flex items-center gap-1.5 px-4 pb-1 flex-wrap">
                {modifiedFiles.map((f) => (
                  <motion.span
                    key={f.path}
                    initial={{ opacity: 0, scale: 0.8 }}
                    animate={{ opacity: 1, scale: 1 }}
                    className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-primary/10 text-primary text-[10px] font-medium"
                  >
                    <svg className="h-2.5 w-2.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                    </svg>
                    <span className="truncate max-w-[100px]">{f.name}</span>
                    <span className="text-amber-400">●</span>
                  </motion.span>
                ))}
              </div>
            )}

            {/* Action buttons row */}
            <div className="flex items-center justify-between px-3 pb-2">
              <div className="flex items-center gap-2">
                {/* Add context button */}
                <button
                  type="button"
                  className="p-1.5 rounded-full hover:bg-accent/10 text-muted hover:text-foreground transition-colors"
                  title="Add context (@files, #issues, etc.)"
                >
                  <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
                  </svg>
                </button>

                {/* Active file indicator */}
                {activeFilePath && (
                  <motion.div
                    initial={{ opacity: 0, x: -10 }}
                    animate={{ opacity: 1, x: 0 }}
                    className="flex items-center gap-1.5 px-2 py-1 rounded-full bg-primary/10 text-primary text-xs"
                  >
                    <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                    </svg>
                    <span className="truncate max-w-[120px]">{activeFilePath.split('/').pop()}</span>
                  </motion.div>
                )}
              </div>

              <div className="flex items-center gap-2">
                {/* Stop button (when streaming) */}
                <AnimatePresence>
                  {isStreaming && (
                    <motion.button
                      initial={{ opacity: 0, scale: 0.8 }}
                      animate={{ opacity: 1, scale: 1 }}
                      exit={{ opacity: 0, scale: 0.8 }}
                      type="button"
                      onClick={handleStop}
                      className="p-2.5 rounded-full bg-red-600 hover:bg-red-700 text-white shadow-lg transition-all"
                      title="Stop generation"
                    >
                      <svg className="h-4 w-4" fill="currentColor" viewBox="0 0 24 24">
                        <rect x="6" y="6" width="12" height="12" rx="2" />
                      </svg>
                    </motion.button>
                  )}
                </AnimatePresence>

                {/* Send button */}
                <motion.button
                  type="submit"
                  disabled={isStreaming || !input.trim()}
                  whileHover={{ scale: (isStreaming || !input.trim()) ? 1 : 1.05 }}
                  whileTap={{ scale: (isStreaming || !input.trim()) ? 1 : 0.95 }}
                  className={`p-2.5 rounded-full text-white shadow-lg transition-all disabled:opacity-50 disabled:cursor-not-allowed ${
                    agentMode === 'ask'
                      ? 'bg-emerald-600 hover:bg-emerald-700'
                      : agentMode === 'manual'
                        ? 'bg-amber-600 hover:bg-amber-700'
                        : 'bg-blue-600 hover:bg-blue-700'
                  }`}
                >
                  {isStreaming ? (
                    <svg className="h-5 w-5 animate-spin" fill="none" viewBox="0 0 24 24">
                      <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                      <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
                    </svg>
                  ) : (
                    <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
                    </svg>
                  )}
                </motion.button>
              </div>
            </div>
          </motion.div>
        </div>

        {/* Quick actions hint */}
        {!isStreaming && (
          <div className="mt-3 text-center">
            <button
              type="button"
              onClick={() => setInput('/plan ')}
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full border border-border bg-background/50 hover:bg-accent/10 text-xs text-muted hover:text-foreground transition-colors"
            >
              <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
              </svg>
              Plan New Idea
              <kbd className="ml-1 px-1.5 py-0.5 rounded bg-accent/20 text-[10px]">Tab</kbd>
            </button>
          </div>
        )}

        {/* Bottom hint */}
        <div className="mt-2 text-center text-[11px] text-muted/50">
          Use <kbd className="px-1.5 py-0.5 rounded bg-accent/10 text-[10px]">/model</kbd> to pick the best model ·{' '}
          <kbd className="px-1.5 py-0.5 rounded bg-accent/10 text-[10px]">Ctrl+Enter</kbd> to send
        </div>
      </form>
    </div>
  );
};

export default InputArea;
