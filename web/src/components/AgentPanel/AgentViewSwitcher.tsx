'use client';

import { type AgentViewMode } from '@/lib/store';

// ── Props ──────────────────────────────────────────────────────────────

interface AgentViewSwitcherProps {
  currentMode: AgentViewMode;
  onChange: (mode: AgentViewMode) => void;
  /** Optional counts shown next to each tab */
  counts?: {
    chat?: number;
    agent?: number;
  };
}

// ── Tab definitions ────────────────────────────────────────────────────

interface TabDef {
  mode: AgentViewMode;
  label: string;
  icon: string;
  description: string;
}

const TABS: TabDef[] = [
  {
    mode: 'chat',
    label: 'Chat',
    icon: '💬',
    description: 'Conversation view with AI responses',
  },
  {
    mode: 'agent',
    label: 'Agent',
    icon: '🤖',
    description: 'Agent activity, tool calls, and plans',
  },
  {
    mode: 'mixed',
    label: 'Mixed',
    icon: '🔄',
    description: 'Combined chat and agent activity',
  },
];

// ── Main Component ─────────────────────────────────────────────────────

export function AgentViewSwitcher({
  currentMode,
  onChange,
  counts,
}: AgentViewSwitcherProps) {
  return (
    <div className="flex items-stretch bg-background/50 border border-border/30 rounded-lg overflow-hidden">
      {TABS.map((tab) => {
        const isActive = currentMode === tab.mode;
        const count = tab.mode === 'chat'
          ? counts?.chat
          : tab.mode === 'agent'
            ? counts?.agent
            : undefined;

        return (
          <button
            key={tab.mode}
            onClick={() => onChange(tab.mode)}
            title={tab.description}
            className={`flex items-center gap-1.5 px-3 py-1.5 text-[10px] font-medium transition-all relative ${
              isActive
                ? 'bg-primary/10 text-primary shadow-sm'
                : 'text-muted/50 hover:text-muted hover:bg-accent/5'
            }`}
          >
            {/* Active indicator bar */}
            {isActive && (
              <span className="absolute bottom-0 left-1 right-1 h-0.5 bg-primary rounded-full" />
            )}

            {/* Icon */}
            <span className="text-xs leading-none">{tab.icon}</span>

            {/* Label */}
            <span>{tab.label}</span>

            {/* Optional count badge */}
            {count !== undefined && count > 0 && (
              <span className={`text-[8px] px-1 py-0.5 rounded-full ${
                isActive
                  ? 'bg-primary/20 text-primary'
                  : 'bg-muted/20 text-muted/60'
              }`}>
                {count}
              </span>
            )}
          </button>
        );
      })}
    </div>
  );
}

export default AgentViewSwitcher;
