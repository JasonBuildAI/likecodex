'use client';

import { useAppStore } from '@/lib/store';

export function Chat() {
  const messages = useAppStore((s) => s.messages);

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
          <div className="whitespace-pre-wrap text-sm">{msg.content}</div>
        </div>
      ))}
    </div>
  );
}
