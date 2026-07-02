'use client';

import { useState, useCallback, useMemo } from 'react';
import type { PlanStep } from '@/lib/store';

// ── Props ──────────────────────────────────────────────────────────────

interface PlanEditorProps {
  steps: PlanStep[];
  onReorder: (steps: PlanStep[]) => void;
  onUpdate: (stepId: string, description: string) => void;
  onToggleExecute: (stepId: string, execute: boolean) => void;
  onExecuteAll: () => void;
  readOnly?: boolean;
}

// ── Drag state ─────────────────────────────────────────────────────────

interface DragState {
  dragIndex: number;
  dropIndex: number;
}

// ── Status colors ──────────────────────────────────────────────────────

const STATUS_STYLES: Record<string, { dot: string; text: string; bg: string }> = {
  pending: { dot: 'bg-gray-400', text: 'text-gray-400', bg: 'bg-gray-500/5' },
  running: { dot: 'bg-yellow-500 animate-pulse', text: 'text-yellow-400', bg: 'bg-yellow-500/5' },
  completed: { dot: 'bg-green-500', text: 'text-green-400', bg: 'bg-green-500/5' },
  failed: { dot: 'bg-red-500', text: 'text-red-400', bg: 'bg-red-500/5' },
  skipped: { dot: 'bg-gray-500', text: 'text-gray-500', bg: 'bg-gray-500/5' },
};

// ── Main Component ─────────────────────────────────────────────────────

export function PlanEditor({
  steps,
  onReorder,
  onUpdate,
  onToggleExecute,
  onExecuteAll,
  readOnly = false,
}: PlanEditorProps) {
  const [dragState, setDragState] = useState<DragState | null>(null);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [editValue, setEditValue] = useState('');

  const executionMap = useMemo(() => {
    const map = new Map<string, boolean>();
    steps.forEach((s) => map.set(s.id, s.status !== 'skipped'));
    return map;
  }, [steps]);

  // ── Drag handlers ────────────────────────────────────────────────────

  const handleDragStart = useCallback(
    (index: number) => (e: React.DragEvent) => {
      if (readOnly) return;
      setDragState({ dragIndex: index, dropIndex: index });
      e.dataTransfer.effectAllowed = 'move';
      e.dataTransfer.setData('text/plain', String(index));
    },
    [readOnly]
  );

  const handleDragOver = useCallback(
    (index: number) => (e: React.DragEvent) => {
      if (readOnly || !dragState) return;
      e.preventDefault();
      e.dataTransfer.dropEffect = 'move';
      setDragState((prev) => (prev ? { ...prev, dropIndex: index } : null));
    },
    [readOnly, dragState]
  );

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      if (readOnly || !dragState) return;
      e.preventDefault();
      const newSteps = [...steps];
      const [moved] = newSteps.splice(dragState.dragIndex, 1);
      newSteps.splice(dragState.dropIndex, 0, moved);
      onReorder(newSteps);
      setDragState(null);
    },
    [readOnly, dragState, steps, onReorder]
  );

  const handleDragEnd = useCallback(() => {
    setDragState(null);
  }, []);

  // ── Edit handlers ────────────────────────────────────────────────────

  const startEditing = useCallback((stepId: string, description: string) => {
    setEditingId(stepId);
    setEditValue(description);
  }, []);

  const saveEdit = useCallback(() => {
    if (editingId && editValue.trim()) {
      onUpdate(editingId, editValue.trim());
    }
    setEditingId(null);
    setEditValue('');
  }, [editingId, editValue, onUpdate]);

  const cancelEdit = useCallback(() => {
    setEditingId(null);
    setEditValue('');
  }, []);

  // ── Derived counts ───────────────────────────────────────────────────

  const pendingCount = steps.filter((s) => s.status === 'pending').length;
  const completedCount = steps.filter((s) => s.status === 'completed').length;
  const failedCount = steps.filter((s) => s.status === 'failed').length;

  return (
    <div className="space-y-2">
      {/* Header */}
      <div className="flex items-center justify-between px-1">
        <span className="text-[10px] font-medium text-muted uppercase tracking-wider flex items-center gap-1.5">
          Plan
          <span className="text-[9px] font-normal text-muted/50">({steps.length} steps)</span>
        </span>
        {!readOnly && (
          <div className="flex items-center gap-1.5">
            {pendingCount > 0 && (
              <span className="text-[9px] text-muted/50">{pendingCount} pending</span>
            )}
            <button
              onClick={onExecuteAll}
              disabled={pendingCount === 0}
              className="text-[9px] px-2 py-0.5 rounded bg-primary/80 text-white hover:bg-primary disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
            >
              Execute All
            </button>
          </div>
        )}
      </div>

      {/* Progress summary */}
      <div className="flex items-center gap-2 px-1">
        {completedCount > 0 && (
          <span className="text-[9px] text-green-400">✓ {completedCount} done</span>
        )}
        {failedCount > 0 && (
          <span className="text-[9px] text-red-400">✗ {failedCount} failed</span>
        )}
        <div className="flex-1 h-1 bg-background rounded-full overflow-hidden">
          <div
            className="h-full bg-gradient-to-r from-blue-500 to-green-500 rounded-full transition-all"
            style={{ width: `${steps.length > 0 ? (completedCount / steps.length) * 100 : 0}%` }}
          />
        </div>
      </div>

      {/* Step list */}
      <div className="space-y-0.5" onDragEnd={handleDragEnd}>
        {steps.map((step, index) => {
          const style = STATUS_STYLES[step.status] || STATUS_STYLES.pending;
          const isDragging = dragState?.dragIndex === index;
          const isDropTarget = dragState && !isDragging && dragState.dropIndex === index;

          return (
            <div
              key={step.id}
              draggable={!readOnly}
              onDragStart={handleDragStart(index)}
              onDragOver={handleDragOver(index)}
              onDrop={handleDrop}
              className={`group flex items-start gap-2 px-2 py-1.5 rounded border transition-all ${
                isDragging
                  ? 'opacity-40 border-primary/30 bg-primary/5'
                  : isDropTarget
                    ? 'border-primary/40 bg-primary/10 scale-[1.01]'
                    : step.status === 'running'
                      ? 'border-yellow-500/20 bg-yellow-500/5'
                      : step.status === 'completed'
                        ? 'border-green-500/10 bg-green-500/5'
                        : step.status === 'failed'
                          ? 'border-red-500/10 bg-red-500/5'
                          : 'border-transparent bg-transparent hover:bg-accent/5'
              }`}
            >
              {/* Drag handle */}
              {!readOnly && (
                <span className="text-muted/20 group-hover:text-muted/50 cursor-grab active:cursor-grabbing transition-colors mt-0.5">
                  <svg className="h-3 w-3" viewBox="0 0 24 24" fill="currentColor">
                    <circle cx="9" cy="5" r="1.5" /><circle cx="15" cy="5" r="1.5" />
                    <circle cx="9" cy="12" r="1.5" /><circle cx="15" cy="12" r="1.5" />
                    <circle cx="9" cy="19" r="1.5" /><circle cx="15" cy="19" r="1.5" />
                  </svg>
                </span>
              )}

              {/* Step number */}
              <span className={`inline-flex items-center justify-center w-4 h-4 rounded-full text-[8px] font-bold shrink-0 mt-0.5 ${style.dot.replace('animate-pulse', '')}`}>
                {index + 1}
              </span>

              {/* Content */}
              <div className="flex-1 min-w-0">
                {editingId === step.id ? (
                  <div className="flex items-center gap-1">
                    <input
                      autoFocus
                      value={editValue}
                      onChange={(e) => setEditValue(e.target.value)}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter') saveEdit();
                        if (e.key === 'Escape') cancelEdit();
                      }}
                      className="flex-1 text-[10px] bg-background border border-border rounded px-1.5 py-0.5 text-foreground outline-none"
                    />
                    <button onClick={saveEdit} className="text-[9px] text-green-400 hover:text-green-300">✓</button>
                    <button onClick={cancelEdit} className="text-[9px] text-muted/50 hover:text-muted">✗</button>
                  </div>
                ) : (
                  <div className="flex items-center gap-1">
                    <span
                      className={`text-[10px] truncate flex-1 ${
                        step.status === 'completed'
                          ? 'text-muted/60 line-through'
                          : step.status === 'failed'
                            ? 'text-red-400'
                            : 'text-foreground/90'
                      }`}
                      onDoubleClick={() => !readOnly && startEditing(step.id, step.description)}
                      title={step.description}
                    >
                      {step.description}
                    </span>
                    {!readOnly && (
                      <button
                        onClick={() => startEditing(step.id, step.description)}
                        className="opacity-0 group-hover:opacity-100 text-[8px] text-muted/30 hover:text-muted/60 transition-all"
                      >
                        ✎
                      </button>
                    )}
                  </div>
                )}
              </div>

              {/* Execute toggle */}
              {!readOnly && (
                <button
                  onClick={() => onToggleExecute(step.id, !executionMap.get(step.id))}
                  className={`text-[9px] px-1.5 py-0.5 rounded border transition-colors ${
                    executionMap.get(step.id)
                      ? 'bg-primary/10 text-primary border-primary/20'
                      : 'bg-background/50 text-muted/40 border-border/30'
                  }`}
                >
                  {executionMap.get(step.id) ? 'Run' : 'Skip'}
                </button>
              )}
            </div>
          );
        })}
      </div>

      {/* Empty state */}
      {steps.length === 0 && (
        <div className="text-center py-6 text-muted/50 text-[10px]">
          No plan steps defined yet
        </div>
      )}
    </div>
  );
}

export default PlanEditor;
