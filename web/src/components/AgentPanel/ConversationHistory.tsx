'use client';

import React from 'react';
import { useAgentStore } from '@/store/agentStore';

// ── Relative time helper (no date-fns dependency) ──────────────────────
function formatRelativeTime(date: Date): string {
  const now = Date.now();
  const diffMs = now - date.getTime();
  const diffSec = Math.floor(diffMs / 1000);
  const diffMin = Math.floor(diffSec / 60);
  const diffHour = Math.floor(diffMin / 60);
  const diffDay = Math.floor(diffHour / 24);

  if (diffSec < 60) return 'just now';
  if (diffMin < 60) return `${diffMin}m ago`;
  if (diffHour < 24) return `${diffHour}h ago`;
  if (diffDay < 7) return `${diffDay}d ago`;
  return date.toLocaleDateString(undefined, { month: 'short', day: 'numeric' });
}

// ── Component ──────────────────────────────────────────────────────────
export const ConversationHistory: React.FC = () => {
  const { conversations, activeConversationId, setActiveConversation } = useAgentStore();

  if (conversations.length === 0) {
    return (
      <div className="flex-1 flex items-center justify-center p-4">
        <div className="text-center text-muted/50">
          <svg
            className="h-8 w-8 mx-auto mb-2 opacity-40"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={1.5}
              d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"
            />
          </svg>
          <p className="text-[11px]">No conversations yet</p>
          <p className="text-[10px] mt-1">Start chatting to create one</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex-1 overflow-y-auto">
      <div className="px-3 py-2 text-[10px] font-semibold uppercase tracking-wider text-muted/60">
        Recent Conversations
      </div>

      {conversations.map((conv) => {
        const isActive = activeConversationId === conv.id;

        return (
          <button
            key={conv.id}
            onClick={() => setActiveConversation(conv.id)}
            className={`w-full px-3 py-2 text-left transition-colors group ${
              isActive
                ? 'bg-primary/15 border-l-2 border-l-primary'
                : 'hover:bg-accent/10 border-l-2 border-l-transparent'
            }`}
          >
            <div className="flex items-start justify-between gap-2">
              <div className="flex-1 min-w-0">
                <div className="text-[11px] text-foreground truncate">
                  {conv.title}
                </div>
                <div className="text-[10px] text-muted/50 mt-0.5">
                  {formatRelativeTime(conv.lastMessageAt)} &middot; {conv.messageCount} msgs
                </div>
              </div>
              <span
                className={`text-[9px] px-1.5 py-0.5 rounded capitalize shrink-0 ${
                  conv.mode === 'ask'
                    ? 'bg-emerald-500/10 text-emerald-400'
                    : conv.mode === 'agent'
                    ? 'bg-blue-500/10 text-blue-400'
                    : 'bg-amber-500/10 text-amber-400'
                }`}
              >
                {conv.mode}
              </span>
            </div>
          </button>
        );
      })}
    </div>
  );
};
