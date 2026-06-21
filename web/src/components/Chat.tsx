'use client';

import { useState } from 'react';
import type { Message } from '@/lib/store';
import { useAppStore } from '@/lib/store';
import { ToolCallCard } from '@/components/ToolCallCard';

interface ChatMessagesProps {
  messages: Message[];
}

function ReasoningBlock({ content }: { content: string }) {
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
        <div className="border-t border-amber-500/20 px-3 py-2 text-xs text-amber-900/80 whitespace-pre-wrap">
          {content}
        </div>
      )}
    </div>
  );
}

export function ChatMessages({ messages }: ChatMessagesProps) {
  return (
    <div className="space-y-4">
      {messages.map((msg) => (
        <div
          key={msg.id}
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
      ))}
    </div>
  );
}

export function Chat() {
  const messages = useAppStore((s) => s.messages);
  return <ChatMessages messages={messages} />;
}
