'use client';

import { Message } from '@/lib/store';

function messageClass(role: Message['role']) {
  switch (role) {
    case 'user':
      return 'bg-primary/10 ml-auto';
    case 'system':
      return 'bg-surface border border-border';
    case 'tool':
      return 'bg-yellow-500/10 border border-yellow-500/30';
    default:
      return 'bg-surface';
  }
}

export function Chat() {
  return null;
}

export function ChatMessages({ messages }: { messages: Message[] }) {
  return (
    <div className="space-y-4">
      {messages.map((msg) => (
        <div key={msg.id} className={`max-w-4xl mx-auto rounded-lg p-4 ${messageClass(msg.role)}`}>
          <div className="text-xs text-muted mb-1 uppercase tracking-wide">
            {msg.eventType || msg.role}
          </div>
          <div className="whitespace-pre-wrap text-sm font-mono">{msg.content}</div>
          {msg.toolCalls?.map((tc) => (
            <div key={tc.id} className="mt-2 text-xs text-muted">
              {tc.name}: {JSON.stringify(tc.arguments)}
            </div>
          ))}
        </div>
      ))}
    </div>
  );
}
