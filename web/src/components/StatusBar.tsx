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
  const collaborationMode = useAppStore((s) => s.collaborationMode);
  const theme = useAppStore((s) => s.theme);
  const openFiles = useAppStore((s) => s.openFiles);
  const activeFilePath = useAppStore((s) => s.activeFilePath);
  const currentSessionId = useAppStore((s) => s.currentSessionId);
  const messages = useAppStore((s) => s.messages);
  const agentMode = useAppStore((s) => s.agentMode);

  const cacheLabel = cacheHitRate !== null ? `${Math.round(cacheHitRate * 100)}% cache` : '--';
  const fileCount = openFiles.length;
  const msgCount = messages.length;
  const activeFileName = activeFilePath ? activeFilePath.split('/').pop() : '';

  return (
    <div className="flex items-center gap-3 px-3 py-1.5 text-[10px] text-muted border-t border-border bg-surface/80">
      {/* Left section: agent mode + streaming status */}
      <span className="flex items-center gap-1.5">
        <span className={`inline-block w-1.5 h-1.5 rounded-full ${isStreaming ? 'bg-yellow-500 animate-pulse' : 'bg-green-500'}`} />
        <span className="font-medium">{agentMode}</span>
        {isStreaming && <span className="text-yellow-400">streaming</span>}
      </span>
      <span className="text-border">|</span>

      {/* Model info */}
      <span title={`Model: ${selectedModel}`}>{selectedModel}</span>
      <span className="text-border">|</span>

      {/* Plan mode indicator */}
      {planModeActive && (
        <>
          <span className="text-amber-400 font-medium">Plan</span>
          <span className="text-border">|</span>
        </>
      )}

      {/* Collaboration mode */}
      {collaborationMode !== 'normal' && (
        <>
          <span className="text-blue-400 font-medium">{collaborationMode}</span>
          <span className="text-border">|</span>
        </>
      )}

      {/* Cache hit rate */}
      <span title="Cache hit rate">{cacheLabel}</span>
      <span className="text-border">|</span>

      {/* Approval mode */}
      <span title="Approval mode" className={`capitalize ${approvalMode === 'yolo' ? 'text-amber-400' : ''}`}>{approvalMode}</span>
      <span className="text-border">|</span>

      {/* API key status */}
      <span className={`flex items-center gap-1 ${apiKey ? 'text-green-500' : 'text-amber-500'}`} title={apiKey ? 'API key configured' : 'No API key'}>
        <span className={`inline-block w-1.5 h-1.5 rounded-full ${apiKey ? 'bg-green-500' : 'bg-amber-500'}`} />
        {apiKey ? 'key ok' : 'no key'}
      </span>
      <span className="text-border">|</span>

      {/* Open file / active file */}
      <span title={`${fileCount} file(s) open`}>
        {fileCount > 0 ? `${fileCount} file${fileCount > 1 ? 's' : ''}` : 'no files'}
      </span>
      {activeFileName && (
        <>
          <span className="text-border">|</span>
          <span title={`Active: ${activeFilePath}`} className="max-w-[120px] truncate">{activeFileName}</span>
        </>
      )}
      <span className="text-border">|</span>

      {/* Session + message count */}
      <span title="Session messages">{msgCount} msgs</span>
      {currentSessionId && (
        <>
          <span className="text-border">|</span>
          <span title={currentSessionId} className="max-w-[80px] truncate text-[9px] text-muted/60">sess:{currentSessionId.slice(0, 8)}</span>
        </>
      )}
      <span className="text-border">|</span>

      {/* Theme */}
      <span title={`Theme: ${theme}`} className="capitalize">{theme}</span>
    </div>
  );
});
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
