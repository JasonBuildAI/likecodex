'use client';

import { memo, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useVirtualizer } from '@tanstack/react-virtual';
import type { Message } from '@/lib/store';
import { useAppStore } from '@/lib/store';
import { ToolCallCard } from '@/components/ToolCallCard';
import { AgentActivity, extractActivities, type ActivityEntry } from '@/components/AgentActivity';

// ── ReasoningBlock ─────────────────────────────────────────────────────
const ReasoningBlock = memo(function ReasoningBlock({ content }: { content: string }) {
  const [isExpanded, setIsExpanded] = useState(false);

  return (
    <div className="my-2 rounded border border-amber-500/30 bg-amber-500/5">
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="flex w-full items-center justify-between px-3 py-2 text-left text-xs font-medium text-amber-700 hover:bg-amber-500/10"
      >
        <span className="flex items-center gap-1.5">
          <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
          </svg>
          Reasoning
        </span>
        <svg
          className={`h-3 w-3 transition-transform ${isExpanded ? 'rotate-180' : ''}`}
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </button>
      {isExpanded && (
        <div className="border-t border-amber-500/20 px-3 py-2 text-xs text-amber-900/80 whitespace-pre-wrap max-h-64 overflow-y-auto">
          {content}
        </div>
      )}
    </div>
  );
});

// ── MessageBubble ──────────────────────────────────────────────────────
const MessageBubble = memo(function MessageBubble({ msg }: { msg: Message }) {
  return (
    <div
      className={`rounded-lg p-4 ${
        msg.role === 'user' ? 'bg-primary/10' : 'bg-surface'
      }`}
    >
      <div className="text-xs text-muted mb-1 uppercase">{msg.role}</div>
      {msg.content ? (
        <div className="whitespace-pre-wrap text-sm">{msg.content}</div>
      ) : null}
      {msg.reasoningContent && (
        <ReasoningBlock content={msg.reasoningContent} />
      )}
      {msg.toolCalls?.map((call) => (
        <div key={call.id || call.name} className="mt-2">
          <ToolCallCard call={call} />
        </div>
      ))}
    </div>
  );
});

// ── ActivityGroup: renders a group of tool calls as Agent activity ────
const ActivityGroup = memo(function ActivityGroup({ messages }: { messages: Message[] }) {
  const activities = useMemo(() => extractActivities(messages), [messages]);
  return <AgentActivity activities={activities} />;
});

// ── ChatMessages (virtualized) ─────────────────────────────────────────
interface ChatMessagesProps {
  scrollRef: React.RefObject<HTMLDivElement | null>;
}

export const ChatMessages = memo(function ChatMessages({ scrollRef }: ChatMessagesProps) {
  const messages = useAppStore((s) => s.messages);
  // Pre-process: group consecutive tool messages into activity blocks
  const groupedItems = useMemo(() => {
    const items: Array<{ type: 'message'; msg: Message } | { type: 'activity'; messages: Message[] }> = [];
    let toolBuffer: Message[] = [];

    for (const msg of messages) {
      if (msg.eventType === 'tool_call' || msg.eventType === 'tool_dispatch' || msg.eventType === 'tool_result') {
        toolBuffer.push(msg);
      } else {
        if (toolBuffer.length > 0) {
          items.push({ type: 'activity', messages: [...toolBuffer] });
          toolBuffer = [];
        }
        items.push({ type: 'message', msg });
      }
    }
    if (toolBuffer.length > 0) {
      items.push({ type: 'activity', messages: toolBuffer });
    }
    return items;
  }, [messages]);

  const estimateSize = useCallback(() => 80, []);
  const prevLengthRef = useRef(groupedItems.length);

  const virtualizer = useVirtualizer({
    count: groupedItems.length,
    getScrollElement: () => scrollRef.current,
    estimateSize,
    overscan: 5,
  });

  // Auto-scroll to bottom on new items
  useEffect(() => {
    if (groupedItems.length > prevLengthRef.current && scrollRef.current) {
      const el = scrollRef.current;
      const isNearBottom = el.scrollHeight - el.scrollTop - el.clientHeight < 200;
      if (isNearBottom) {
        virtualizer.scrollToIndex(groupedItems.length - 1, { align: 'end' });
      }
    }
    prevLengthRef.current = groupedItems.length;
  }, [groupedItems.length, virtualizer, scrollRef]);

  if (groupedItems.length === 0) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center text-muted">
          <p className="text-lg">What would you like to build?</p>
          <p className="text-sm mt-2">
            Try: /plan then describe a refactor, or ask to fix failing tests
          </p>
        </div>
      </div>
    );
  }

  return (
    <div
      style={{
        height: `${virtualizer.getTotalSize()}px`,
        width: '100%',
        position: 'relative',
      }}
    >
      {virtualizer.getVirtualItems().map((virtualItem) => {
        const item = groupedItems[virtualItem.index];
        return (
          <div
            key={item.type === 'message' ? item.msg.id : `activity-${virtualItem.index}`}
            style={{
              position: 'absolute',
              top: 0,
              left: 0,
              width: '100%',
              transform: `translateY(${virtualItem.start}px)`,
            }}
            ref={virtualizer.measureElement}
            data-index={virtualItem.index}
          >
            <div className="px-1 py-1.5">
              {item.type === 'message' ? (
                <MessageBubble msg={item.msg} />
              ) : (
                <ActivityGroup messages={item.messages} />
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
});

// ── Legacy Chat (kept for compatibility) ───────────────────────────────
export function Chat() {
  const messages = useAppStore((s) => s.messages);
  return (
    <div className="space-y-4">
      {messages.map((msg) => (
        <MessageBubble key={msg.id} msg={msg} />
      ))}
    </div>
  );
}
