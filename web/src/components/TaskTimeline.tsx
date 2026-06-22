'use client';

import { memo, useState } from 'react';
import type { PlanStep, SessionSummary, Task } from '@/lib/store';
import { useAppStore } from '@/lib/store';
import { forkSession, deleteSession, summarizeSession, compactSession, createNewSession } from '@/lib/api';

interface TaskTimelineProps {
  tasks: Task[];
  planSteps?: PlanStep[];
  sessions?: SessionSummary[];
  activeSessionId?: string | null;
  onSessionSelect?: (sessionId: string) => void;
}

export const TaskTimeline = memo(function TaskTimeline({
  tasks,
  planSteps = [],
  sessions = [],
  activeSessionId = null,
  onSessionSelect,
}: TaskTimelineProps) {
  const [contextMenu, setContextMenu] = useState<{ sessionId: string; x: number; y: number } | null>(null);
  const addToast = useAppStore((s) => s.addToast);
  const setSessions = useAppStore((s) => s.setSessions);
  const setCurrentSessionId = useAppStore((s) => s.setCurrentSessionId);

  const formatDate = (dateStr?: string) => {
    if (!dateStr) return '';
    const d = new Date(dateStr);
    return d.toLocaleString('zh-CN', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
  };

  const handleContextMenu = (e: React.MouseEvent, sessionId: string) => {
    e.preventDefault();
    setContextMenu({ sessionId, x: e.clientX, y: e.clientY });
  };

  const closeContextMenu = () => setContextMenu(null);

  const handleNewSession = async () => {
    try {
      const result = await createNewSession();
      addToast({ type: 'success', message: 'New session created' });
      const { fetchSessions } = await import('@/lib/api');
      const sessions = await fetchSessions();
      setSessions(sessions);
      setCurrentSessionId(result.session_id);
    } catch (err) {
      addToast({ type: 'error', message: `Failed: ${err instanceof Error ? err.message : err}` });
    }
  };

  const handleFork = async (sessionId: string) => {
    try {
      const result = await forkSession(sessionId);
      addToast({ type: 'success', message: `Forked to ${result.session_id.slice(0, 8)}...` });
      const { fetchSessions } = await import('@/lib/api');
      setSessions(await fetchSessions());
    } catch (err) {
      addToast({ type: 'error', message: `Fork failed: ${err instanceof Error ? err.message : err}` });
    }
    closeContextMenu();
  };

  const handleDelete = async (sessionId: string) => {
    if (!confirm('Delete this session?')) return;
    try {
      await deleteSession(sessionId);
      addToast({ type: 'success', message: 'Session deleted' });
      const { fetchSessions } = await import('@/lib/api');
      setSessions(await fetchSessions());
      if (activeSessionId === sessionId) {
        setCurrentSessionId(null);
      }
    } catch (err) {
      addToast({ type: 'error', message: `Delete failed: ${err instanceof Error ? err.message : err}` });
    }
    closeContextMenu();
  };

  const handleSummarize = async (sessionId: string) => {
    try {
      const summary = await summarizeSession(sessionId);
      addToast({
        type: 'info',
        message: `${summary.message_count} msgs, ${summary.user_turns} user turns, ${summary.assistant_turns} assistant`,
      });
    } catch (err) {
      addToast({ type: 'error', message: `Summarize failed: ${err instanceof Error ? err.message : err}` });
    }
    closeContextMenu();
  };

  const handleCompact = async (sessionId: string) => {
    try {
      await compactSession(sessionId);
      addToast({ type: 'success', message: 'Context compaction triggered' });
    } catch (err) {
      addToast({ type: 'error', message: `Compact failed: ${err instanceof Error ? err.message : err}` });
    }
    closeContextMenu();
  };

  return (
    <div className="space-y-4">
      {/* Session list */}
      <section className="bg-surface border border-border rounded-lg p-3">
        <div className="flex items-center justify-between mb-2">
          <h2 className="text-sm font-semibold">Sessions</h2>
          <button
            onClick={handleNewSession}
            className="text-xs text-primary hover:underline"
            title="New session"
          >
            + New
          </button>
        </div>
        {sessions.length === 0 && <p className="text-sm text-muted">No sessions yet.</p>}
        <ul className="space-y-1">
          {sessions.map((session) => (
            <li key={session.id}>
              <button
                type="button"
                onClick={() => onSessionSelect?.(session.id)}
                onContextMenu={(e) => handleContextMenu(e, session.id)}
                className={`w-full text-left text-xs truncate rounded px-2 py-1.5 hover:bg-background transition-colors ${
                  activeSessionId === session.id ? 'bg-background ring-1 ring-primary' : ''
                }`}
                title={session.id}
              >
                <span className="text-muted">{formatDate(session.created_at || session.updated_at)}</span>
                <span className="ml-2 font-mono text-[10px] opacity-50">{session.id.slice(0, 8)}</span>
              </button>
            </li>
          ))}
        </ul>
      </section>

      {/* Tasks */}
      <section className="bg-surface border border-border rounded-lg p-3">
        <h2 className="text-sm font-semibold mb-2">Tasks</h2>
        {tasks.length === 0 && <p className="text-sm text-muted">No tasks yet.</p>}
        <ul className="space-y-1.5">
          {tasks.map((task) => (
            <li key={task.id} className="text-sm flex items-start gap-1.5">
              <span
                className={`inline-block w-2 h-2 rounded-full mt-1.5 shrink-0 ${
                  task.status === 'running'
                    ? 'bg-yellow-500 animate-pulse'
                    : task.status === 'completed'
                      ? 'bg-green-500'
                      : 'bg-red-500'
                }`}
              />
              <span className="truncate text-xs">{task.prompt}</span>
            </li>
          ))}
        </ul>
      </section>

      {/* Plan */}
      {planSteps.length > 0 && (
        <section className="bg-surface border border-border rounded-lg p-3">
          <h2 className="text-sm font-semibold mb-2">Plan</h2>
          <ul className="space-y-1.5">
            {planSteps.map((step) => (
              <li key={step.id} className="text-xs flex items-start gap-1.5">
                <span
                  className={`inline-block w-1.5 h-1.5 rounded-full mt-1 shrink-0 ${
                    step.status === 'completed' ? 'bg-green-500' :
                    step.status === 'in_progress' ? 'bg-yellow-500 animate-pulse' :
                    'bg-muted'
                  }`}
                />
                <span>{step.description}</span>
              </li>
            ))}
          </ul>
        </section>
      )}

      {/* Context menu */}
      {contextMenu && (
        <>
          <div className="fixed inset-0 z-50" onClick={closeContextMenu} />
          <div
            className="fixed z-50 bg-surface border border-border rounded-lg shadow-xl py-1 min-w-[140px]"
            style={{ left: contextMenu.x, top: contextMenu.y }}
          >
            <button
              onClick={() => handleFork(contextMenu.sessionId)}
              className="w-full text-left px-3 py-1.5 text-xs hover:bg-accent/10"
            >
              Fork session
            </button>
            <button
              onClick={() => handleSummarize(contextMenu.sessionId)}
              className="w-full text-left px-3 py-1.5 text-xs hover:bg-accent/10"
            >
              Summarize
            </button>
            <button
              onClick={() => handleCompact(contextMenu.sessionId)}
              className="w-full text-left px-3 py-1.5 text-xs hover:bg-accent/10"
            >
              Compact context
            </button>
            <hr className="my-1 border-border" />
            <button
              onClick={() => handleDelete(contextMenu.sessionId)}
              className="w-full text-left px-3 py-1.5 text-xs text-red-400 hover:bg-red-500/10"
            >
              Delete
            </button>
          </div>
        </>
      )}
    </div>
  );
});
