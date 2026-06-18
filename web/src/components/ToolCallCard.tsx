'use client';

import { ToolCall } from '@/lib/store';

export function ToolCallCard({ call }: { call: ToolCall }) {
  return (
    <div className="rounded border border-border bg-background p-3 text-sm">
      <div className="font-medium">{call.name}</div>
      <pre className="text-xs text-muted mt-1 overflow-auto">
        {JSON.stringify(call.arguments, null, 2)}
      </pre>
    </div>
  );
}
