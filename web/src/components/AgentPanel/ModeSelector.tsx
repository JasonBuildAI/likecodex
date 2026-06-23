'use client';

import React from 'react';
import { useAgentStore, type AgentMode } from '@/store/agentStore';

// ── Mode configuration ─────────────────────────────────────────────────
const MODE_CONFIG: Record<
  AgentMode,
  {
    label: string;
    description: string;
    activeClass: string;
    icon: React.ReactNode;
  }
> = {
  ask: {
    label: 'Ask',
    description: 'Ask questions without making changes',
    activeClass: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
    icon: (
      <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
      </svg>
    ),
  },
  agent: {
    label: 'Agent',
    description: 'Automatically execute safe operations',
    activeClass: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
    icon: (
      <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
      </svg>
    ),
  },
  manual: {
    label: 'Manual',
    description: 'Require approval for all operations',
    activeClass: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
    icon: (
      <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 15l-2 5L9 9l11 4-5 2zm0 0l5 5M7.188 2.239l.777 2.897M5.136 7.965l-2.898-.777M13.95 4.05l-2.122 2.122m-5.657 5.656l-2.12 2.122" />
      </svg>
    ),
  },
};

// ── Component ──────────────────────────────────────────────────────────
export const ModeSelector: React.FC = () => {
  const { currentMode, switchMode } = useAgentStore();

  return (
    <div className="flex items-center gap-1 p-2 border-b border-border">
      {(Object.keys(MODE_CONFIG) as AgentMode[]).map((mode) => {
        const config = MODE_CONFIG[mode];
        const isActive = currentMode === mode;

        return (
          <button
            key={mode}
            onClick={() => switchMode(mode)}
            title={config.description}
            className={`flex items-center gap-1.5 flex-1 justify-center px-3 py-2 rounded-lg text-xs font-medium transition-all border border-transparent ${
              isActive
                ? config.activeClass
                : 'text-muted hover:text-foreground hover:bg-accent/10'
            }`}
          >
            {config.icon}
            <span>{config.label}</span>
            {isActive && <span className="h-1.5 w-1.5 rounded-full bg-current" />}
          </button>
        );
      })}
    </div>
  );
};
