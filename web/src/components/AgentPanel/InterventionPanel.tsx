'use client';

import { useState, useCallback, useEffect } from 'react';

// ── Types ──────────────────────────────────────────────────────────────

export interface InterventionStep {
  id: string;
  type: 'tool_call' | 'command' | 'file_edit' | 'decision';
  description: string;
  details?: string;
  status: 'pending' | 'approved' | 'modified' | 'skipped';
}

interface InterventionPanelProps {
  steps: InterventionStep[];
  onApprove: (stepId: string) => void;
  onModify: (stepId: string, modifiedDetails: string) => void;
  onSkip: (stepId: string) => void;
  onApproveAll: () => void;
  onRejectAll: () => void;
  readOnly?: boolean;
}

// ── Step icon mapping ──────────────────────────────────────────────────

const TYPE_ICONS: Record<string, string> = {
  tool_call: '🔧',
  command: '⚡',
  file_edit: '✏️',
  decision: '❓',
};

const TYPE_LABELS: Record<string, string> = {
  tool_call: 'Tool Call',
  command: 'Command',
  file_edit: 'File Edit',
  decision: 'Decision',
};

// ── Main Component ─────────────────────────────────────────────────────

export function InterventionPanel({
  steps,
  onApprove,
  onModify,
  onSkip,
  onApproveAll,
  onRejectAll,
  readOnly = false,
}: InterventionPanelProps) {
  const [modifyingId, setModifyingId] = useState<string | null>(null);
  const [modifyValue, setModifyValue] = useState('');
  const [decisions, setDecisions] = useState<Record<string, string>>({});

  // Track decisions locally
  useEffect(() => {
    const map: Record<string, string> = {};
    for (const step of steps) {
      map[step.id] = step.status;
    }
    setDecisions(map);
  }, [steps]);

  // ── Action handlers ──────────────────────────────────────────────────

  const handleApprove = useCallback(
    (stepId: string) => {
      setDecisions((prev) => ({ ...prev, [stepId]: 'approved' }));
      onApprove(stepId);
    },
    [onApprove]
  );

  const handleSkip = useCallback(
    (stepId: string) => {
      setDecisions((prev) => ({ ...prev, [stepId]: 'skipped' }));
      onSkip(stepId);
    },
    [onSkip]
  );

  const handleModify = useCallback(
    (stepId: string) => {
      if (!modifyValue.trim()) return;
      setDecisions((prev) => ({ ...prev, [stepId]: 'modified' }));
      onModify(stepId, modifyValue.trim());
      setModifyingId(null);
      setModifyValue('');
    },
    [modifyValue, onModify]
  );

  const startModify = useCallback((stepId: string, currentDetails?: string) => {
    setModifyingId(stepId);
    setModifyValue(currentDetails || '');
  }, []);

  const cancelModify = useCallback(() => {
    setModifyingId(null);
    setModifyValue('');
  }, []);

  // Keyboard shortcuts
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        if (modifyingId) {
          cancelModify();
        }
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [modifyingId, cancelModify]);

  const pendingCount = steps.filter((s) => s.status === 'pending').length;
  const allHandled = pendingCount === 0;

  if (steps.length === 0) {
    return (
      <div className="text-center py-6 text-muted/50 text-[10px]">
        No intervention steps pending
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {/* Header */}
      <div className="flex items-center justify-between px-1">
        <span className="text-[10px] font-medium text-muted uppercase tracking-wider">
          Intervention
          {pendingCount > 0 && (
            <span className="ml-1.5 text-[9px] font-normal text-yellow-400">
              ({pendingCount} pending)
            </span>
          )}
        </span>
        {!readOnly && !allHandled && (
          <div className="flex items-center gap-1">
            <button
              onClick={onRejectAll}
              className="text-[9px] px-2 py-0.5 rounded border border-border/40 text-muted/60 hover:text-muted hover:bg-background transition-colors"
            >
              Skip All
            </button>
            <button
              onClick={onApproveAll}
              className="text-[9px] px-2 py-0.5 rounded bg-primary/80 text-white hover:bg-primary transition-colors"
            >
              Approve All
            </button>
          </div>
        )}
      </div>

      {/* Step list */}
      <div className="space-y-1">
        {steps.map((step) => {
          const decision = decisions[step.id] || step.status;
          const isPending = decision === 'pending';
          const isApproved = decision === 'approved';
          const isSkipped = decision === 'skipped';
          const isModified = decision === 'modified';
          const isModifying = modifyingId === step.id;

          return (
            <div
              key={step.id}
              className={`rounded-lg border p-2.5 transition-all ${
                isApproved
                  ? 'border-green-500/20 bg-green-500/5'
                  : isSkipped
                    ? 'border-gray-500/20 bg-gray-500/5 opacity-60'
                    : isModified
                      ? 'border-blue-500/20 bg-blue-500/5'
                      : isPending
                        ? 'border-yellow-500/20 bg-yellow-500/5'
                        : 'border-border/30 bg-background/30'
              }`}
            >
              {/* Header row */}
              <div className="flex items-center gap-2 mb-1">
                <span className="text-xs">{TYPE_ICONS[step.type] || '🔧'}</span>
                <span className="text-[10px] font-medium text-muted/70">
                  {TYPE_LABELS[step.type] || step.type}
                </span>
                <span
                  className={`text-[9px] px-1.5 py-0.5 rounded border ml-auto ${
                    isApproved
                      ? 'bg-green-500/10 text-green-400 border-green-500/20'
                      : isSkipped
                        ? 'bg-gray-500/10 text-gray-400 border-gray-500/20'
                        : isModified
                          ? 'bg-blue-500/10 text-blue-400 border-blue-500/20'
                          : isPending
                            ? 'bg-yellow-500/10 text-yellow-400 border-yellow-500/20 animate-pulse'
                            : 'bg-gray-500/10 text-gray-400 border-gray-500/20'
                  }`}
                >
                  {isApproved ? '✓ Approved' : isSkipped ? '⏭ Skipped' : isModified ? '✎ Modified' : 'Pending'}
                </span>
              </div>

              {/* Description */}
              <p className="text-[10px] text-foreground/80 mb-1">{step.description}</p>

              {/* Details (modifiable) */}
              {isModifying ? (
                <div className="flex items-start gap-1 mt-1">
                  <textarea
                    autoFocus
                    value={modifyValue}
                    onChange={(e) => setModifyValue(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) {
                        handleModify(step.id);
                      }
                    }}
                    className="flex-1 text-[10px] bg-background border border-border rounded px-1.5 py-1 text-foreground outline-none min-h-[48px] resize-vertical"
                    placeholder="Modify the details..."
                  />
                  <div className="flex flex-col gap-0.5">
                    <button
                      onClick={() => handleModify(step.id)}
                      className="text-[9px] px-1.5 py-0.5 rounded bg-primary/80 text-white hover:bg-primary"
                    >
                      Save
                    </button>
                    <button
                      onClick={cancelModify}
                      className="text-[9px] px-1.5 py-0.5 rounded border border-border/40 text-muted/60 hover:text-muted"
                    >
                      Cancel
                    </button>
                  </div>
                </div>
              ) : step.details ? (
                <pre className="text-[9px] text-muted/60 bg-background/40 rounded p-1.5 mt-1 overflow-auto max-h-16 whitespace-pre-wrap break-all">
                  {step.details}
                </pre>
              ) : null}

              {/* Action buttons */}
              {isPending && !readOnly && (
                <div className="flex items-center gap-1.5 mt-2 justify-end">
                  {step.details && (
                    <button
                      onClick={() => startModify(step.id, step.details)}
                      className="text-[9px] px-2 py-0.5 rounded border border-border/40 text-muted/60 hover:text-muted hover:bg-background transition-colors"
                    >
                      Modify
                    </button>
                  )}
                  <button
                    onClick={() => handleSkip(step.id)}
                    className="text-[9px] px-2 py-0.5 rounded border border-border/40 text-muted/60 hover:text-muted hover:bg-background transition-colors"
                  >
                    Skip
                  </button>
                  <button
                    onClick={() => handleApprove(step.id)}
                    className="text-[9px] px-2 py-0.5 rounded bg-primary/80 text-white hover:bg-primary transition-colors"
                  >
                    Approve
                  </button>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

export default InterventionPanel;
