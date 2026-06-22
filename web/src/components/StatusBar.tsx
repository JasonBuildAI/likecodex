'use client';

import { memo } from 'react';
import { useAppStore } from '@/lib/store';

export const StatusBar = memo(function StatusBar() {
  const selectedModel = useAppStore((s) => s.selectedModel);
  const cacheHitRate = useAppStore((s) => s.cacheHitRate);
  const approvalMode = useAppStore((s) => s.approvalMode);
  const apiKey = useAppStore((s) => s.apiKey);
  const isStreaming = useAppStore((s) => s.isStreaming);
  const planModeActive = useAppStore((s) => s.planModeActive);

  const cacheLabel = cacheHitRate !== null ? `${Math.round(cacheHitRate * 100)}% cache` : '--';

  return (
    <div className="flex items-center gap-3 px-3 py-1.5 text-[10px] text-muted border-t border-border bg-surface/80">
      <span title="Model">{selectedModel}</span>
      <span className="text-border">|</span>
      {planModeActive && (
        <>
          <span className="text-amber-400 font-medium">Plan</span>
          <span className="text-border">|</span>
        </>
      )}
      <span title="Cache hit rate">{cacheLabel}</span>
      <span className="text-border">|</span>
      <span title="Approval mode" className="capitalize">{approvalMode}</span>
      <span className="text-border">|</span>
      <span className="flex items-center gap-1">
        <span className={`inline-block w-1.5 h-1.5 rounded-full ${isStreaming ? 'bg-yellow-500 animate-pulse' : 'bg-green-500'}`} />
        {isStreaming ? 'streaming' : 'idle'}
      </span>
      <span className="text-border">|</span>
      <span className={`flex items-center gap-1 ${apiKey ? 'text-green-500' : 'text-amber-500'}`}>
        <span className={`inline-block w-1.5 h-1.5 rounded-full ${apiKey ? 'bg-green-500' : 'bg-amber-500'}`} />
        {apiKey ? 'key ok' : 'no key'}
      </span>
    </div>
  );
});
