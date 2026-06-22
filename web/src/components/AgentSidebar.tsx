'use client';

import { memo, useCallback } from 'react';
import type { SessionSummary, Task } from '@/lib/store';
import { useAppStore } from '@/lib/store';
import { createNewSession, fetchSessions } from '@/lib/api';

// ── Agent status badge ────────────────────────────────────────────────
function getAgentStatus(session: SessionSummary, tasks: Task[], activeSessionId: string | null) {
  // Check if any task for this session is running
  const sessionTasks = tasks.filter((t) => t.id === session.id);
  const isRunning = sessionTasks.some((t) => t.status === 'running');
  const isFailed = sessionTasks.some((t) => t.status === 'failed');
  const isActive = session.id === activeSessionId;

  if (isRunning) return { label: 'running', color: 'bg-blue-500 animate-pulse', textColor: 'text-blue-400' };
  if (isFailed) return { label: 'failed', color: 'bg-red-500', textColor: 'text-red-400' };
  if (isActive) return { label: 'active', color: 'bg-green-500', textColor: 'text-green-400' };
  return { label: 'idle', color: 'bg-muted/40', textColor: 'text-muted' };
}

interface AgentSidebarProps {
  sessions: SessionSummary[];
  tasks: Task[];
  activeSessionId: string | null;
  onSessionSelect: (id: string) => void;
}

export const AgentSidebar = memo(function AgentSidebar({
  sessions,
  tasks,
  activeSessionId,
  onSessionSelect,
}: AgentSidebarProps) {
  const setSessions = useAppStore((s) => s.setSessions);
  const setCurrentSessionId = useAppStore((s) => s.setCurrentSessionId);
  const setMessages = useAppStore((s) => s.setMessages);
  const addToast = useAppStore((s) => s.addToast);

  const handleNewAgent = useCallback(async () => {
    try {
      const r = await createNewSession();
      setCurrentSessionId(r.session_id);
      setMessages([]);
      addToast({ type: 'success', message: 'New agent session created' });
      fetchSessions().then(setSessions);
    } catch {
      addToast({ type: 'error', message: 'Failed to create session' });
    }
  }, [setCurrentSessionId, setMessages, addToast, setSessions]);

  // Sort sessions: most recent first
  const sorted = [...sessions].sort((a, b) => {
    const ta = a.updated_at || a.created_at || '';
    const tb = b.updated_at || b.created_at || '';
    return tb.localeCompare(ta);
  });

  return (
    <div className="flex flex-col h-full">
      {/* Header with New Agent button */}
      <div className="flex items-center justify-between px-2 py-1.5">
        <span className="text-[10px] font-semibold uppercase tracking-wider text-muted/60">
          Agents
        </span>
        <button
          onClick={handleNewAgent}
          className="flex items-center gap-1 px-2 py-0.5 rounded text-[10px] bg-blue-500/20 text-blue-400 hover:bg-blue-500/30 transition-colors"
          title="New Agent (Ctrl+N)"
        >
          <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
          </svg>
          New
        </button>
      </div>

      {/* Agent list */}
      <div className="flex-1 overflow-y-auto px-1">
        {sorted.length === 0 ? (
          <div className="text-center py-8 text-muted/50">
            <svg className="h-8 w-8 mx-auto mb-2 opacity-40" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
            </svg>
            <p className="text-[10px]">No agents yet</p>
            <p className="text-[9px] mt-1">Start a conversation to create one</p>
          </div>
        ) : (
          sorted.map((session) => {
            const status = getAgentStatus(session, tasks, activeSessionId);
            const isActive = session.id === activeSessionId;
            const title = session.metadata?.title as string
              || (session.metadata?.first_prompt as string)?.slice(0, 40)
              || `Agent ${session.id.slice(0, 8)}`;

            return (
              <button
                key={session.id}
                onClick={() => onSessionSelect(session.id)}
                className={`w-full text-left px-2 py-1.5 rounded-md mb-0.5 transition-colors group ${
                  isActive
                    ? 'bg-primary/15 border border-primary/30'
                    : 'hover:bg-accent/10 border border-transparent'
                }`}
              >
                <div className="flex items-center gap-1.5">
                  {/* Status dot */}
                  <span className={`h-1.5 w-1.5 rounded-full shrink-0 ${status.color}`} />
                  {/* Title */}
                  <span className={`text-[11px] truncate flex-1 ${isActive ? 'text-foreground font-medium' : 'text-foreground/80'}`}>
                    {title}
                  </span>
                </div>
                {/* Meta row */}
                <div className="flex items-center gap-1 mt-0.5 ml-3">
                  <span className={`text-[9px] ${status.textColor}`}>{status.label}</span>
                  {session.created_at && (
                    <span className="text-[9px] text-muted/40">
                      {new Date(session.created_at).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}
                    </span>
                  )}
                </div>
              </button>
            );
          })
        )}
      </div>
    </div>
  );
});
