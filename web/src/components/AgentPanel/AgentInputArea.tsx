'use client';

import React, { useRef, useEffect } from 'react';
import { useAppStore, type AgentMode, type AgentViewMode } from '@/lib/store';

// ── Mode configuration ─────────────────────────────────────────────────
const MODE_CONFIG: Record<AgentMode, { label: string; tooltip: string; icon: React.ReactNode; activeClass: string }> = {
  ask: {
    label: 'Ask',
    tooltip: 'Ask mode: read-only Q&A, no code changes',
    icon: (
      <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
      </svg>
    ),
    activeClass: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
  },
  agent: {
    label: 'Agent',
    tooltip: 'Agent mode: autonomous execution with full tool access',
    icon: (
      <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
      </svg>
    ),
    activeClass: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
  },
  manual: {
    label: 'Manual',
    tooltip: 'Manual mode: confirm each action before execution',
    icon: (
      <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 15l-2 5L9 9l11 4-5 2zm0 0l5 5M7.188 2.239l.777 2.897M5.136 7.965l-2.898-.777M13.95 4.05l-2.122 2.122m-5.657 5.656l-2.12 2.122" />
      </svg>
    ),
    activeClass: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
  },
};

const VIEW_MODE_CONFIG: Record<AgentViewMode, { label: string; icon: string }> = {
  chat: { label: 'Chat', icon: '💬' },
  agent: { label: 'Agent', icon: '🤖' },
  mixed: { label: 'Mixed', icon: '🔀' },
};

// ── Props ──────────────────────────────────────────────────────────────
interface AgentInputAreaProps {
  value: string;
  onChange: (value: string) => void;
  onSend: () => void;
  isStreaming: boolean;
  activeFilePath?: string | null;
}

// ── Component ──────────────────────────────────────────────────────────
export const AgentInputArea: React.FC<AgentInputAreaProps> = ({
  value,
  onChange,
  onSend,
  isStreaming,
  activeFilePath,
}) => {
  const agentMode = useAppStore((s) => s.agentMode);
  const setAgentMode = useAppStore((s) => s.setAgentMode);
  const agentViewMode = useAppStore((s) => s.agentViewMode);
  const setAgentViewMode = useAppStore((s) => s.setAgentViewMode);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-focus
  useEffect(() => {
    textareaRef.current?.focus();
  }, [agentMode]);

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
      e.preventDefault();
      if (value.trim() && !isStreaming) onSend();
      return;
    }
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      if (value.trim() && !isStreaming) onSend();
      return;
    }
  };

  const placeholderText = agentMode === 'ask'
    ? 'Ask questions without making changes...'
    : agentMode === 'manual'
      ? 'Describe your task (each step requires approval)...'
      : 'What would you like to build? Use @ to reference files';

  return (
    <div className="p-4 bg-gradient-to-t from-surface via-surface to-transparent">
      <div className="max-w-2xl mx-auto">
        {/* Mode selector capsule */}
        <div className="flex items-center justify-center mb-3">
          <div className="inline-flex items-center gap-1 bg-background/80 backdrop-blur-sm border border-border rounded-full px-1.5 py-1 shadow-lg">
            {(Object.keys(MODE_CONFIG) as AgentMode[]).map((mode) => {
              const cfg = MODE_CONFIG[mode];
              const isActive = agentMode === mode;
              return (
                <button
                  key={mode}
                  type="button"
                  onClick={() => setAgentMode(mode)}
                  title={cfg.tooltip}
                  className={`flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium transition-all ${
                    isActive
                      ? `${cfg.activeClass} shadow-md`
                      : 'text-muted hover:text-foreground hover:bg-accent/10'
                  }`}
                >
                  {cfg.icon}
                  <span>{cfg.label}</span>
                </button>
              );
            })}
          </div>
        </div>

        {/* Main input box */}
        <div className="relative group">
          <div className="absolute inset-0 bg-gradient-to-r from-blue-500/20 via-purple-500/20 to-pink-500/20 rounded-2xl blur-xl opacity-0 group-hover:opacity-100 transition-opacity duration-500" />
          <div className="relative bg-background/90 backdrop-blur-sm border border-border rounded-2xl shadow-2xl overflow-hidden">
            <textarea
              ref={textareaRef}
              value={value}
              onChange={(e) => onChange(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder={placeholderText}
              className="w-full bg-transparent px-4 py-3.5 pr-24 text-sm focus:outline-none resize-none min-h-[56px] max-h-[200px] placeholder:text-muted/60"
              rows={1}
              disabled={isStreaming}
            />

            {/* Action buttons row */}
            <div className="flex items-center justify-between px-3 pb-2">
              <div className="flex items-center gap-2">
                {/* View mode toggle */}
                <div className="flex items-center gap-0.5 bg-background/60 rounded-full border border-border/60 p-0.5">
                  {(Object.keys(VIEW_MODE_CONFIG) as AgentViewMode[]).map((vm) => {
                    const vc = VIEW_MODE_CONFIG[vm];
                    const isVmActive = agentViewMode === vm;
                    return (
                      <button
                        key={vm}
                        type="button"
                        onClick={() => setAgentViewMode(vm)}
                        title={`${vc.label} view`}
                        className={`px-2 py-1 rounded-full text-[10px] font-medium transition-all ${
                          isVmActive
                            ? 'bg-primary/20 text-primary'
                            : 'text-muted/50 hover:text-muted'
                        }`}
                      >
                        {vc.icon} {vc.label}
                      </button>
                    );
                  })}
                </div>

                {/* Active file indicator */}
                {activeFilePath && (
                  <div className="flex items-center gap-1.5 px-2 py-1 rounded-full bg-primary/10 text-primary text-xs max-w-[150px]">
                    <svg className="h-3 w-3 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
                    </svg>
                    <span className="truncate">{activeFilePath.split('/').pop()}</span>
                  </div>
                )}
              </div>

              <div className="flex items-center gap-2">
                {/* Send / Stop button */}
                <button
                  type="button"
                  onClick={isStreaming ? () => {} : onSend}
                  disabled={!isStreaming && !value.trim()}
                  className={`p-2.5 rounded-full text-white shadow-lg transition-all transform hover:scale-105 active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:scale-100 ${
                    isStreaming
                      ? 'bg-red-600 hover:bg-red-700 animate-pulse'
                      : agentMode === 'ask'
                        ? 'bg-emerald-600 hover:bg-emerald-700'
                        : agentMode === 'manual'
                          ? 'bg-amber-600 hover:bg-amber-700'
                          : 'bg-blue-600 hover:bg-blue-700'
                  }`}
                >
                  {isStreaming ? (
                    <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                    </svg>
                  ) : (
                    <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" />
                    </svg>
                  )}
                </button>
              </div>
            </div>
          </div>
        </div>

        {/* Quick actions hint */}
        {!isStreaming && (
          <div className="mt-3 text-center">
            <button
              type="button"
              className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full border border-border bg-background/50 hover:bg-accent/10 text-xs text-muted hover:text-foreground transition-colors"
            >
              <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" />
              </svg>
              Plan New Idea
              <kbd className="ml-1 px-1.5 py-0.5 rounded bg-accent/20 text-[10px]">/plan</kbd>
            </button>
          </div>
        )}

        {/* Bottom hint */}
        <div className="mt-2 text-center text-[11px] text-muted/50">
          Use <kbd className="px-1.5 py-0.5 rounded bg-accent/10 text-[10px]">/model</kbd> to pick the best model for your task
        </div>
      </div>
    </div>
  );
};
