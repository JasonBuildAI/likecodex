'use client';

import { memo, useState, useCallback, useMemo } from 'react';
import { AnimatePresence, motion } from 'framer-motion';
import { cn } from '@/lib/utils';
import { staggerContainer, staggerItem, fadeIn, scaleIn } from '@/lib/animations';
import { useBackgroundStore, type BackgroundTask } from '@/stores/backgroundStore';

// ── Helpers ────────────────────────────────────────────────────────────

const statusConfig: Record<BackgroundTask['status'], { label: string; color: string; bg: string; dot: string }> = {
  pending:    { label: 'Pending',    color: 'text-yellow-400',  bg: 'bg-yellow-500/20 border-yellow-500/30',  dot: 'bg-yellow-400' },
  running:    { label: 'Running',    color: 'text-blue-400',    bg: 'bg-blue-500/20 border-blue-500/30',      dot: 'bg-blue-400' },
  paused:     { label: 'Paused',     color: 'text-orange-400',  bg: 'bg-orange-500/20 border-orange-500/30',  dot: 'bg-orange-400' },
  completed:  { label: 'Completed',  color: 'text-emerald-400', bg: 'bg-emerald-500/20 border-emerald-500/30', dot: 'bg-emerald-400' },
  failed:     { label: 'Failed',     color: 'text-red-400',     bg: 'bg-red-500/20 border-red-500/30',        dot: 'bg-red-400' },
  cancelled:  { label: 'Cancelled',  color: 'text-gray-400',    bg: 'bg-gray-500/20 border-gray-500/30',      dot: 'bg-gray-400' },
};

function formatDuration(start: number, end?: number): string {
  const ms = (end ?? Date.now()) - start;
  if (ms < 1000) return `${Math.round(ms)}ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
  const min = Math.floor(ms / 60000);
  const sec = Math.floor((ms % 60000) / 1000);
  return `${min}m ${sec}s`;
}

function formatTime(ts: number): string {
  return new Date(ts).toLocaleString('zh-CN', {
    month: 'short',
    day: 'numeric',
    hour: '2-digit',
    minute: '2-digit',
  });
}

function progressColor(pct: number): string {
  if (pct >= 100) return 'bg-emerald-500';
  if (pct >= 60) return 'bg-blue-500';
  if (pct >= 30) return 'bg-yellow-500';
  return 'bg-muted';
}

// ── Task Row ───────────────────────────────────────────────────────────

interface TaskRowProps {
  task: BackgroundTask;
}

const TaskRow = memo(function TaskRow({ task }: TaskRowProps) {
  const [expanded, setExpanded] = useState(false);
  const cancelTask = useBackgroundStore((s) => s.cancelTask);
  const pauseTask = useBackgroundStore((s) => s.pauseTask);
  const resumeTask = useBackgroundStore((s) => s.resumeTask);
  const removeTask = useBackgroundStore((s) => s.removeTask);

  const cfg = statusConfig[task.status];
  const isTerminal = task.status === 'completed' || task.status === 'failed' || task.status === 'cancelled';
  const isActive = task.status === 'pending' || task.status === 'running' || task.status === 'paused';

  const handleCancel = useCallback(() => cancelTask(task.id), [cancelTask, task.id]);
  const handlePause = useCallback(() => pauseTask(task.id), [pauseTask, task.id]);
  const handleResume = useCallback(() => resumeTask(task.id), [resumeTask, task.id]);
  const handleRemove = useCallback(() => removeTask(task.id), [removeTask, task.id]);

  return (
    <motion.div
      variants={staggerItem}
      layout
      className={cn(
        'rounded-lg border transition-colors',
        task.status === 'failed' ? 'border-red-500/20 bg-red-500/5' :
        task.status === 'completed' ? 'border-emerald-500/20 bg-emerald-500/5' :
        'border-border bg-surface',
      )}
    >
      {/* Header row — always visible */}
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        className="flex w-full items-center gap-3 px-3 py-2.5 text-left"
      >
        {/* Status dot */}
        <span className={cn('inline-block h-2 w-2 shrink-0 rounded-full', cfg.dot)} />

        {/* Task name */}
        <span className="flex-1 truncate text-xs font-medium text-foreground">
          {task.name}
        </span>

        {/* Status badge */}
        <span className={cn('inline-flex items-center gap-1 rounded-md border px-1.5 py-0.5 text-[10px] font-medium', cfg.bg, cfg.color)}>
          {task.status === 'running' && (
            <span className="inline-block h-1.5 w-1.5 animate-pulse rounded-full bg-current" />
          )}
          {cfg.label}
        </span>

        {/* Duration */}
        <span className="shrink-0 text-[10px] text-muted">
          {task.started_at ? formatDuration(task.started_at, task.completed_at) : '--'}
        </span>

        {/* Expand icon */}
        <motion.svg
          animate={{ rotate: expanded ? 180 : 0 }}
          transition={{ duration: 0.2 }}
          className="h-3 w-3 shrink-0 text-muted"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <polyline points="6 9 12 15 18 9" />
        </motion.svg>
      </button>

      {/* Progress bar */}
      {task.status !== 'pending' && (
        <div className="h-1 w-full bg-background">
          <motion.div
            className={cn('h-full transition-colors', progressColor(task.progress))}
            initial={{ width: 0 }}
            animate={{ width: `${task.progress}%` }}
            transition={{ duration: 0.5, ease: 'easeOut' }}
          />
        </div>
      )}

      {/* Expandable details */}
      <AnimatePresence>
        {expanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="overflow-hidden border-t border-border"
          >
            <div className="space-y-2 px-3 py-2.5">
              {/* Description */}
              {task.description && (
                <p className="text-[11px] leading-relaxed text-muted">{task.description}</p>
              )}

              {/* Metadata grid */}
              <div className="grid grid-cols-2 gap-1.5 text-[10px] text-muted">
                <div>
                  <span className="opacity-50">Created: </span>
                  <span>{formatTime(task.created_at)}</span>
                </div>
                {task.started_at && (
                  <div>
                    <span className="opacity-50">Started: </span>
                    <span>{formatTime(task.started_at)}</span>
                  </div>
                )}
                {task.completed_at && (
                  <div>
                    <span className="opacity-50">Completed: </span>
                    <span>{formatTime(task.completed_at)}</span>
                  </div>
                )}
                <div>
                  <span className="opacity-50">Progress: </span>
                  <span>{task.progress}%</span>
                </div>
                <div>
                  <span className="opacity-50">Duration: </span>
                  <span>{task.started_at ? formatDuration(task.started_at, task.completed_at) : '--'}</span>
                </div>
              </div>

              {/* Result / error */}
              {task.result && (
                <div className="rounded bg-emerald-500/10 p-2">
                  <p className="text-[10px] font-medium text-emerald-400">Result</p>
                  <pre className="mt-0.5 whitespace-pre-wrap break-all text-[10px] text-emerald-300/80">
                    {typeof task.result === 'string' ? task.result : JSON.stringify(task.result, null, 1)}
                  </pre>
                </div>
              )}
              {task.error && (
                <div className="rounded bg-red-500/10 p-2">
                  <p className="text-[10px] font-medium text-red-400">Error</p>
                  <pre className="mt-0.5 whitespace-pre-wrap break-all text-[10px] text-red-300/80">
                    {task.error}
                  </pre>
                </div>
              )}

              {/* Action buttons */}
              <div className="flex gap-2 pt-1">
                {isActive && (task.status === 'pending' || task.status === 'running') && (
                  <ActionButton onClick={handleCancel} variant="danger">
                    Cancel
                  </ActionButton>
                )}
                {task.status === 'running' && (
                  <ActionButton onClick={handlePause} variant="warning">
                    Pause
                  </ActionButton>
                )}
                {task.status === 'paused' && (
                  <ActionButton onClick={handleResume} variant="primary">
                    Resume
                  </ActionButton>
                )}
                {isTerminal && (
                  <ActionButton onClick={handleRemove} variant="ghost">
                    Clear
                  </ActionButton>
                )}
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
});

// ── Action Button ──────────────────────────────────────────────────────

interface ActionButtonProps {
  onClick: () => void;
  variant: 'primary' | 'danger' | 'warning' | 'ghost';
  children: React.ReactNode;
}

const ActionButton = memo(function ActionButton({ onClick, variant, children }: ActionButtonProps) {
  const base = 'rounded-md px-2.5 py-1 text-[10px] font-medium transition-colors';
  const variants: Record<string, string> = {
    primary: 'bg-blue-500/20 text-blue-400 hover:bg-blue-500/30',
    danger: 'bg-red-500/20 text-red-400 hover:bg-red-500/30',
    warning: 'bg-orange-500/20 text-orange-400 hover:bg-orange-500/30',
    ghost: 'bg-transparent text-muted hover:bg-accent/10 hover:text-foreground',
  };

  return (
    <button type="button" onClick={onClick} className={cn(base, variants[variant])}>
      {children}
    </button>
  );
});

// ── Empty State ────────────────────────────────────────────────────────

const EmptyState = memo(function EmptyState() {
  return (
    <motion.div
      variants={fadeIn}
      initial="hidden"
      animate="visible"
      className="flex flex-col items-center justify-center py-16"
    >
      <motion.div
        initial={{ scale: 0.8, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        transition={{ delay: 0.1, type: 'spring', stiffness: 200, damping: 20 }}
        className="mb-4 flex h-14 w-14 items-center justify-center rounded-2xl bg-surface ring-1 ring-border"
      >
        <svg className="h-6 w-6 text-muted" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round">
          <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
          <line x1="12" y1="8" x2="12" y2="16" />
          <line x1="8" y1="12" x2="16" y2="12" />
        </svg>
      </motion.div>
      <p className="text-sm font-medium text-muted">No background tasks</p>
    </motion.div>
  );
});

// ── Panel Header ───────────────────────────────────────────────────────

interface PanelHeaderProps {
  taskCount: number;
  onClose: () => void;
}

const PanelHeader = memo(function PanelHeader({ taskCount, onClose }: PanelHeaderProps) {
  return (
    <div className="flex items-center justify-between border-b border-border px-4 py-3">
      <div className="flex items-center gap-2">
        <h2 className="text-sm font-semibold text-foreground">Background Tasks</h2>
        <span className="inline-flex h-4 min-w-[1rem] items-center justify-center rounded-full bg-accent/10 px-1.5 text-[10px] font-medium text-accent">
          {taskCount}
        </span>
      </div>
      <button
        type="button"
        onClick={onClose}
        className="rounded-md p-1 text-muted transition-colors hover:bg-accent/10 hover:text-foreground"
      >
        <svg className="h-4 w-4" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
          <line x1="18" y1="6" x2="6" y2="18" />
          <line x1="6" y1="6" x2="18" y2="18" />
        </svg>
      </button>
    </div>
  );
});

// ── Main Panel ─────────────────────────────────────────────────────────

interface BackgroundTasksPanelProps {
  /** When true, render as a standalone dialog/overlay panel */
  standalone?: boolean;
  onClose?: () => void;
}

export const BackgroundTasksPanel = memo(function BackgroundTasksPanel({
  standalone = false,
  onClose,
}: BackgroundTasksPanelProps) {
  const tasks = useBackgroundStore((s) => s.tasks);
  const setPanelOpen = useBackgroundStore((s) => s.setPanelOpen);

  const handleClose = useCallback(() => {
    setPanelOpen(false);
    onClose?.();
  }, [setPanelOpen, onClose]);

  const sortedTasks = useMemo(
    () => [...tasks].sort((a, b) => b.created_at - a.created_at),
    [tasks],
  );

  const content = (
    <motion.div
      variants={staggerContainer}
      initial="hidden"
      animate="visible"
      className="space-y-1.5 px-4 pb-4"
    >
      {sortedTasks.length === 0 ? (
        <EmptyState />
      ) : (
        <AnimatePresence mode="popLayout">
          {sortedTasks.map((task) => (
            <TaskRow key={task.id} task={task} />
          ))}
        </AnimatePresence>
      )}
    </motion.div>
  );

  // ── Standalone overlay mode ──────────────────────────────────────
  if (standalone) {
    return (
      <AnimatePresence>
        <motion.div
          key="background-tasks-overlay"
          variants={scaleIn}
          initial="hidden"
          animate="visible"
          exit="exit"
          className="flex h-full flex-col overflow-hidden rounded-xl border border-border bg-background shadow-2xl"
        >
          <PanelHeader taskCount={tasks.length} onClose={handleClose} />
          <div className="flex-1 overflow-y-auto">{content}</div>
        </motion.div>
      </AnimatePresence>
    );
  }

  // ── Inline mode ──────────────────────────────────────────────────
  return (
    <div className="flex h-full flex-col overflow-hidden">
      <PanelHeader taskCount={tasks.length} onClose={handleClose} />
      <div className="flex-1 overflow-y-auto">{content}</div>
    </div>
  );
});
