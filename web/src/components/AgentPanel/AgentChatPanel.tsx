'use client';

import React, { useRef, useEffect } from 'react';
import { useAppStore, type AgentViewMode } from '@/lib/store';
import { ToolCallStream } from './ToolCallStream';
import { AgentInputArea } from './AgentInputArea';
import { AgentActivityTimeline } from './AgentActivityTimeline';
import { ChatMessages } from '@/components/Chat';

// ── Props ──────────────────────────────────────────────────────────────
interface AgentChatPanelProps {
  messages: ReturnType<typeof useAppStore.getState>['messages'];
  activeToolCalls: ReturnType<typeof useAppStore.getState>['activeToolCalls'];
  isStreaming: boolean;
  agentMode: ReturnType<typeof useAppStore.getState>['agentMode'];
  viewMode: AgentViewMode;
  cacheLabel: string;
  currentSessionId: string | null;
  activeFilePath: string | null;
  input: string;
  onInputChange: (value: string) => void;
  onSendMessage: () => void;
}

const VIEW_MODE_TABS: { key: AgentViewMode; label: string; icon: string }[] = [
  { key: 'chat', label: 'Chat', icon: '💬' },
  { key: 'agent', label: 'Agent Activity', icon: '⚡' },
  { key: 'mixed', label: 'Mixed', icon: '🔀' },
];

// ── Chat header sub-component ──────────────────────────────────────────
const AgentChatHeader: React.FC<{
  cacheLabel: string;
  viewMode: AgentViewMode;
  onViewModeChange: (mode: AgentViewMode) => void;
  onToggleToolCallLog: () => void;
  isToolCallLogVisible: boolean;
}> = ({ cacheLabel, viewMode, onViewModeChange, onToggleToolCallLog, isToolCallLogVisible }) => {
  return (
    <div className="flex items-center justify-between px-4 py-2 border-b border-border bg-surface/50 shrink-0">
      <div className="flex items-center gap-2">
        {/* View mode tabs */}
        <div className="flex items-center gap-0.5 bg-background/60 rounded-lg p-0.5 border border-border/60">
          {VIEW_MODE_TABS.map((tab) => {
            const isActive = viewMode === tab.key;
            return (
              <button
                key={tab.key}
                onClick={() => onViewModeChange(tab.key)}
                className={`px-2.5 py-1 rounded-md text-[10px] font-medium transition-all ${
                  isActive
                    ? 'bg-primary/20 text-primary shadow-sm'
                    : 'text-muted/60 hover:text-muted hover:bg-accent/10'
                }`}
              >
                {tab.icon} {tab.label}
              </button>
            );
          })}
        </div>
      </div>

      <div className="flex items-center gap-2">
        {/* Tool call log toggle */}
        <button
          onClick={onToggleToolCallLog}
          className={`px-2 py-1 rounded text-[10px] font-medium transition-colors ${
            isToolCallLogVisible
              ? 'bg-accent/20 text-foreground'
              : 'text-muted hover:text-foreground hover:bg-accent/10'
          }`}
          title="Toggle tool call log"
        >
          🛠 Tools
        </button>

        {/* Cache indicator */}
        <span className="flex items-center gap-1 text-[10px] text-muted/60" title="Cache hit rate">
          <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
          </svg>
          {cacheLabel}
        </span>
      </div>
    </div>
  );
};

// ── Main Agent Chat Panel ──────────────────────────────────────────────
export const AgentChatPanel: React.FC<AgentChatPanelProps> = ({
  messages,
  activeToolCalls,
  isStreaming,
  agentMode,
  viewMode,
  cacheLabel,
  currentSessionId,
  activeFilePath,
  input,
  onInputChange,
  onSendMessage,
}) => {
  const agentViewMode = useAppStore((s) => s.agentViewMode);
  const setAgentViewMode = useAppStore((s) => s.setAgentViewMode);
  const isToolCallLogVisible = useAppStore((s) => s.isToolCallLogVisible);
  const toggleToolCallLog = useAppStore((s) => s.toggleToolCallLog);
  const scrollRef = useRef<HTMLDivElement>(null);

  // Auto-scroll
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages.length, messages[messages.length - 1]?.content]);

  return (
    <aside className="w-[480px] border-l border-border bg-surface flex flex-col shrink-0 relative">
      {/* Header */}
      <AgentChatHeader
        cacheLabel={cacheLabel}
        viewMode={viewMode}
        onViewModeChange={setAgentViewMode}
        onToggleToolCallLog={toggleToolCallLog}
        isToolCallLogVisible={isToolCallLogVisible}
      />

      {/* Content area depending on view mode */}
      <div className="flex-1 overflow-y-auto min-h-0">
        {agentViewMode === 'agent' ? (
          /* Pure Agent View: full screen activity timeline + tool calls */
          <div className="p-4 space-y-4">
            {/* Reasoning panel (placeholder for reasoning content) */}
            {isStreaming && (
              <div className="px-3 py-2 rounded-lg bg-accent/10 border border-border/40">
                <div className="flex items-center gap-2 mb-1">
                  <span className="inline-block h-2 w-2 rounded-full bg-blue-500 animate-pulse" />
                  <span className="text-[10px] font-medium text-blue-400">AI is thinking...</span>
                </div>
                <div className="text-xs text-muted">
                  Processing your request with tools available
                </div>
              </div>
            )}

            {/* Tool calls stream */}
            {activeToolCalls.length > 0 && (
              <ToolCallStream items={activeToolCalls} />
            )}
            
            {/* Activity timeline */}
            <AgentActivityTimeline
              activeToolCalls={activeToolCalls}
              isStreaming={isStreaming}
              variant="full"
            />
          </div>
        ) : agentViewMode === 'mixed' ? (
          /* Mixed View: chat on top, agent activity below */
          <div className="flex flex-col h-full">
            {/* Chat messages (top 60%) */}
            <div ref={scrollRef} className="flex-[3] overflow-y-auto p-4 border-b border-border/40">
              <ChatMessages scrollRef={scrollRef} />
            </div>

            {/* Agent activity panel (bottom 40%) - only visible when streaming or has tool calls */}
            {(isStreaming || activeToolCalls.length > 0 || isToolCallLogVisible) && (
              <div className="flex-[2] overflow-y-auto p-3 bg-background/30">
                {activeToolCalls.length > 0 && (
                  <ToolCallStream items={activeToolCalls} />
                )}
                <AgentActivityTimeline
                  activeToolCalls={activeToolCalls}
                  isStreaming={isStreaming}
                  variant="compact"
                />
              </div>
            )}
          </div>
        ) : (
          /* Pure Chat View */
          <div ref={scrollRef} className="h-full overflow-y-auto p-4">
            <ChatMessages scrollRef={scrollRef} />
          </div>
        )}
      </div>

      {/* Input area */}
      <AgentInputArea
        value={input}
        onChange={onInputChange}
        onSend={onSendMessage}
        isStreaming={isStreaming}
        activeFilePath={activeFilePath}
      />
    </aside>
  );
};
