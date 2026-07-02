'use client';

import { memo, useState, useRef, useCallback, useEffect, useMemo } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { cn } from '@/lib/utils';
import { fadeIn, scaleIn } from '@/lib/animations';
import { useBackgroundStore, type BackgroundTask } from '@/stores/backgroundStore';

// ── Status helpers ─────────────────────────────────────────────────────

const statusConfig: Record<BackgroundTask['status'], { color: string; dot: string }> = {
  pending:    { color: 'text-yellow-400',  dot: 'bg-yellow-400' },
  running:    { color: 'text-blue-400',    dot: 'bg-blue-400' },
  paused:     { color: 'text-orange-400',  dot: 'bg-orange-400' },
  completed:  { color: 'text-emerald-400', dot: 'bg-emerald-400' },
  failed:     { color: 'text-red-400',     dot: 'bg-red-400' },
  cancelled:  { color: 'text-gray-400',    dot: 'bg-gray-400' },
};

function formatDuration(start: number, end?: number): string {
  const ms = (end ?? Date.now()) - start;
  if (ms < 1000) return `${Math.round(ms)}ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
  const min = Math.floor(ms / 60000);
  const sec = Math.floor((ms % 60000) / 1000);
  return `${min}m ${sec}s`;
}

// ── Dropdown component ─────────────────────────────────────────────────

export const BackgroundTasksDropdown = memo(function BackgroundTasksDropdown() {
  const [open, setOpen] = useState(false);
  const [hasNewCompletion, setHasNewCompletion] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);
  const prevCompletedCountRef = useRef(0);

  const tasks = useBackgroundStore((s) => s.tasks);
  const setPanelOpen = useBackgroundStore((s) => s.setPanelOpen);

  const activeCount = useMemo(
    () => tasks.filter((t) => t.status === 'pending' || t.status === 'running' || t.status === 'paused').length,
    [tasks],
  );

  // Detect new completions for notification dot
  useEffect(() => {
    const completedCount = tasks.filter((t) => t.status === 'completed').length;
    if (completedCount > prevCompletedCountRef.current) {
      setHasNewCompletion(true);
    }
    prevCompletedCountRef.current = completedCount;
  }, [tasks]);

  // Close dropdown on outside click
  useEffect(() => {
    if (!open) return;
    const handleClick = (e: MouseEvent) => {
      if (containerRef.current && !containerRef.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, [open]);

  const toggle = useCallback(() => {
    setOpen((v) => !v);
    setHasNewCompletion(false);
  }, []);

  const handleViewAll = useCallback(() => {
    setOpen(false);
    setPanelOpen(true);
  }, [setPanelOpen]);

  // Sorted: active tasks first, then by newest
  const sortedTasks = useMemo(
    () =>
      [...tasks]
        .sort((a, b) => {
          const aActive = a.status === 'pending' || a.status === 'running' || a.status === 'paused' ? 0 : 1;
          const bActive = b.status === 'pending' || b.status === 'running' || b.status === 'paused' ? 0 : 1;
          if (aActive !== bActive) return aActive - bActive;
          return b.created_at - a.created_at;
        })
        .slice(0, 5),
    [tasks],
  );

  return (
    <div ref={containerRef} className="relative">
      {/* Trigger button */}
      <button
        type="button"
        onClick={toggle}
        className="relative flex items-center gap-1.5 rounded-md px-2 py-1 text-[10px] text-muted transition-colors hover:bg-accent/10 hover:text-foreground"
        title="Background tasks"
      >
        {/* Icon */}
        <svg className="h-3.5 w-3.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
          <line x1="12" y1="8" x2="12" y2="16" />
          <line x1="8" y1="12" x2="16" y2="12" />
        </svg>

        {/* Active count */}
        {activeCount > 0 && <span className="font-medium text-foreground">{activeCount}</span>}

        {/* Notification dot */}
        {hasNewCompletion && activeCount === 0 && (
          <span className="absolute -right-0.5 -top-0.5 h-2 w-2 rounded-full bg-emerald-400 ring-1 ring-background" />
        )}
      </button>

      {/* Dropdown menu */}
      <AnimatePresence>
        {open && (
          <motion.div
            variants={fadeIn}
            initial="hidden"
            animate="visible"
            exit="exit"
            className="absolute bottom-full left-0 z-50 mb-1.5 w-72 overflow-hidden rounded-lg border border-border bg-surface shadow-2xl"
          >
            {/* Header */}
            <div className="border-b border-border px-3 py-2">
              <p className="text-[11px] font-semibold text-foreground">
                Background Tasks
                {tasks.length > 0 && (
                  <span className="ml-1.5 text-[10px] font-normal text-muted">({tasks.length})</span>
                )}
              </p>
            </div>

            {/* Task list */}
            <div className="max-h-60 overflow-y-auto">
              {sortedTasks.length === 0 ? (
                <div className="flex flex-col items-center py-6">
                  <svg className="mb-2 h-6 w-6 text-muted/40" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
                    <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
                    <line x1="12" y1="8" x2="12" y2="16" />
                    <line x1="8" y1="12" x2="16" y2="12" />
                  </svg>
                  <p className="text-[11px] text-muted/60">No background tasks</p>
                </div>
              ) : (
                <div className="space-y-0.5 p-1.5">
                  {sortedTasks.map((task) => {
                    const cfg = statusConfig[task.status];
                    return (
                      <motion.div
                        key={task.id}
                        variants={scaleIn}
                        initial="hidden"
                        animate="visible"
                        className="flex items-center gap-2 rounded-md px-2 py-1.5 transition-colors hover:bg-accent/5"
                      >
                        <span className={cn('h-1.5 w-1.5 shrink-0 rounded-full', cfg.dot)} />
                        <span className="flex-1 truncate text-[11px] text-foreground">{task.name}</span>
                        <span className={cn('shrink-0 text-[10px] font-medium', cfg.color)}>
                          {task.status}
                        </span>
                        {task.started_at && (
                          <span className="shrink-0 text-[9px] text-muted/60">
                            {formatDuration(task.started_at, task.completed_at)}
                          </span>
                        )}
                      </motion.div>
                    );
                  })}
                </div>
              )}
            </div>

            {/* Footer — View All */}
            <div className="border-t border-border px-3 py-1.5">
              <button
                type="button"
                onClick={handleViewAll}
                className="w-full rounded py-1 text-center text-[10px] font-medium text-primary transition-colors hover:bg-primary-500/10"
              >
                View All
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
});
