'use client';

import type { Message } from '@/lib/store';
import { useAppStore } from '@/lib/store';
import { ToolCallCard } from '@/components/ToolCallCard';

interface ChatMessagesProps {
  messages: Message[];
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
