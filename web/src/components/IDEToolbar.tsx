'use client';

import React from 'react';
import { useAppStore } from '@/lib/store';

/**
 * IDE top toolbar: logo, panel tabs, mode selector, cache indicator
 *
 * Phase 7.6: Debug Toolbar
 * - Future: Add debug controls (step over, step into, step out, continue)
 * - Add breakpoint toggle button (F9)
 * - Add thread/process selector dropdown
 * - Add debug session status indicator (running/paused/stopped)
 * - Wire into the debug adapter protocol (DAP) backend
 */
export const IDEToolbar: React.FC = () => {
  const cacheHitRate = useAppStore((s) => s.cacheHitRate);
  const planModeActive = useAppStore((s) => s.planModeActive);
  const collaborationMode = useAppStore((s) => s.collaborationMode);
  const setCollaborationMode = useAppStore((s) => s.setCollaborationMode);
  const toggleSidebar = useAppStore((s) => s.toggleSidebar);
  const setCommandPaletteOpen = useAppStore((s) => s.setCommandPaletteOpen);

  const cacheLabel = cacheHitRate !== null ? `${Math.round(cacheHitRate * 100)}%` : '--';

  return (
    <header className="border-b border-border px-3 py-1.5 flex items-center justify-between bg-surface shrink-0">
      <div className="flex items-center gap-2">
        <button
          onClick={toggleSidebar}
          className="p-1 rounded hover:bg-accent/10 transition-colors"
          title="Toggle sidebar (Ctrl+B)"
        >
          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
          </svg>
        </button>
        <h1 className="text-sm font-semibold">LikeCodex</h1>
      </div>

      <div className="flex items-center gap-1.5 text-xs text-muted">
        {/* Plan mode badge */}
        {planModeActive && (
          <span className="px-2 py-0.5 rounded bg-amber-500/20 text-amber-200 text-[10px] font-medium">PLAN</span>
        )}

        {/* Collaboration mode */}
        <select
          className="bg-transparent border border-border rounded px-1.5 py-0.5 text-[10px]"
          value={collaborationMode}
          onChange={(e) => setCollaborationMode(e.target.value as 'normal' | 'plan' | 'goal')}
        >
          <option value="normal">normal</option>
          <option value="plan">plan</option>
          <option value="goal">goal</option>
        </select>

        {/* Command palette */}
        <button
          onClick={() => setCommandPaletteOpen(true)}
          className="px-1.5 py-0.5 rounded border border-border text-[10px] hover:bg-accent/10 transition-colors"
          title="Command palette (Ctrl+K)"
        >
          Cmd
        </button>

        {/* Cache indicator */}
        <span className="flex items-center gap-1 text-[10px]" title="Cache hit rate">
          <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
          </svg>
          {cacheLabel}
        </span>
      </div>
    </header>
  );
};
