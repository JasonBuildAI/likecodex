'use client';

import { memo, useState } from 'react';
import { ToolCall } from '@/lib/store';

export const ToolCallCard = memo(function ToolCallCard({ call }: { call: ToolCall }) {
  const [expanded, setExpanded] = useState(false);
  const argsStr = JSON.stringify(call.arguments, null, 2);
  const isLong = argsStr.length > 200;

  return (
    <div className="rounded border border-border bg-background p-3 text-sm">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-2 w-full text-left"
      >
        <span
          className={`inline-block w-2 h-2 rounded-full ${
            call.arguments?.partial ? 'bg-yellow-500 animate-pulse' : 'bg-green-500'
          }`}
        />
        <span className="font-medium">{call.name}</span>
        {isLong && (
          <span className="text-xs text-muted ml-auto">
            {expanded ? 'Collapse' : 'Expand'}
          </span>
        )}
      </button>
      <pre className="text-xs text-muted mt-1 overflow-auto max-h-32">
        {isLong && !expanded ? argsStr.slice(0, 150) + '...' : argsStr}
      </pre>
    </div>
  );
});
