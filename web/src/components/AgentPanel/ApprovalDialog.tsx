'use client';

import { memo, useState, useEffect, useCallback } from 'react';
import { type PermissionRequest } from '@/lib/store';
import { respondPermission } from '@/lib/api';

// ── Types ──────────────────────────────────────────────────────────────
export interface ApprovalItem {
  request: PermissionRequest;
  /** Preview snippet of the change (e.g. diff or command) */
  preview?: string;
}

interface ApprovalDialogProps {
  items: ApprovalItem[];
  /** Called with each requestId after it has been responded to */
  onResponded: (requestId: string, approved: boolean) => void;
  /** Called when the dialog is dismissed or all items are handled */
  onDone: () => void;
}

// ── Helpers ────────────────────────────────────────────────────────────
function getToolIcon(tool: string): string {
  if (tool.includes('edit') || tool.includes('write') || tool.includes('create')) return '✏️';
  if (tool.includes('run') || tool.includes('execute') || tool.includes('shell')) return '⚡';
  if (tool.includes('delete')) return '🗑️';
  return '🔧';
}

function extractFilePath(args: Record<string, unknown>): string | null {
  const raw = args.file_path || args.path || args.target;
  if (typeof raw === 'string' && raw.length > 0) return raw;
  return null;
}

// ── Single item row ────────────────────────────────────────────────────
const ApprovalItemRow = memo(function ApprovalItemRow({
  item,
  decision,
  onDecide,
}: {
  item: ApprovalItem;
  decision: 'approved' | 'denied' | null;
  onDecide: (approved: boolean) => void;
}) {
  const filePath = extractFilePath(item.request.arguments || {});
  const icon = getToolIcon(item.request.tool || '');

  return (
    <div
      className={`rounded-lg border p-3 transition-colors ${
        decision === 'approved'
          ? 'border-green-500/30 bg-green-500/5'
          : decision === 'denied'
            ? 'border-red-500/30 bg-red-500/5 opacity-60'
            : 'border-border/60 bg-background/60'
      }`}
    >
      {/* Header */}
      <div className="flex items-center gap-2 mb-1.5">
        <span className="text-sm">{icon}</span>
        <span className="text-xs font-medium text-foreground">
          {item.request.tool || 'Unknown tool'}
        </span>
        {filePath && (
          <span className="text-[10px] text-muted truncate ml-auto" title={filePath}>
            {filePath}
          </span>
        )}
        {decision && (
          <span
            className={`text-[9px] px-1.5 py-0.5 rounded border ${
              decision === 'approved'
                ? 'bg-green-500/10 text-green-400 border-green-500/20'
                : 'bg-red-500/10 text-red-400 border-red-500/20'
            }`}
          >
            {decision === 'approved' ? '✓ Approved' : '✗ Denied'}
          </span>
        )}
      </div>

      {/* Description */}
      <p className="text-[11px] text-muted mb-2 line-clamp-2">
        {item.request.description || 'No description'}
      </p>

      {/* Preview */}
      {item.preview && (
        <pre className="text-[10px] text-muted/80 bg-background/50 rounded p-2 mb-2 overflow-auto max-h-24 whitespace-pre-wrap break-all">
          {item.preview}
        </pre>
      )}

      {/* Per-item actions (only when no decision yet) */}
      {!decision && (
        <div className="flex gap-2 justify-end">
          <button
            type="button"
            onClick={() => onDecide(false)}
            className="px-2.5 py-1 rounded border border-border text-[10px] text-muted hover:text-foreground hover:bg-background transition-colors"
          >
            Deny
          </button>
          <button
            type="button"
            onClick={() => onDecide(true)}
            className="px-2.5 py-1 rounded bg-primary/80 text-white text-[10px] hover:bg-primary transition-colors"
          >
            Approve
          </button>
        </div>
      )}
    </div>
  );
});

// ── Main dialog ────────────────────────────────────────────────────────
export const ApprovalDialog = memo(function ApprovalDialog({
  items,
  onResponded,
  onDone,
}: ApprovalDialogProps) {
  // Track per-item decisions: requestId → 'approved' | 'denied'
  const [decisions, setDecisions] = useState<Record<string, 'approved' | 'denied'>>({});
  const [isSubmitting, setIsSubmitting] = useState(false);

  const pendingCount = items.filter((i) => !decisions[i.request.requestId]).length;
  const allHandled = pendingCount === 0;

  // Handle single item decision
  const handleDecide = useCallback(
    async (requestId: string, approved: boolean) => {
      setDecisions((prev) => ({
        ...prev,
        [requestId]: approved ? 'approved' : 'denied',
      }));
      try {
        await respondPermission(requestId, approved, 'once');
        onResponded(requestId, approved);
      } catch (err) {
        console.warn('[ApprovalDialog] respondPermission failed:', err);
        // Item is already marked in UI, so user can retry
      }
    },
    [onResponded]
  );

  // Approve all remaining
  const handleApproveAll = useCallback(async () => {
    if (isSubmitting) return;
    setIsSubmitting(true);
    try {
      const remaining = items.filter((i) => !decisions[i.request.requestId]);
      await Promise.all(
        remaining.map((i) => handleDecide(i.request.requestId, true))
      );
    } finally {
      setIsSubmitting(false);
    }
  }, [items, decisions, handleDecide, isSubmitting]);

  // Deny all remaining
  const handleDenyAll = useCallback(async () => {
    if (isSubmitting) return;
    setIsSubmitting(true);
    try {
      const remaining = items.filter((i) => !decisions[i.request.requestId]);
      await Promise.all(
        remaining.map((i) => handleDecide(i.request.requestId, false))
      );
    } finally {
      setIsSubmitting(false);
    }
  }, [items, decisions, handleDecide, isSubmitting]);

  // Keyboard shortcuts
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        if (!allHandled) {
          handleDenyAll();
        } else {
          onDone();
        }
      }
      // Enter to approve all (only when no input is focused)
      if (e.key === 'Enter' && !e.repeat) {
        const tag = (e.target as HTMLElement)?.tagName;
        if (tag !== 'INPUT' && tag !== 'TEXTAREA' && tag !== 'SELECT') {
          e.preventDefault();
          handleApproveAll();
        }
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [allHandled, handleApproveAll, handleDenyAll, onDone]);

  if (items.length === 0) return null;

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50 p-4">
      <div className="bg-surface border border-border rounded-xl shadow-2xl max-w-lg w-full max-h-[80vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-5 py-4 border-b border-border">
          <div>
            <h3 className="text-sm font-semibold text-foreground">
              Approval Required
            </h3>
            <p className="text-[11px] text-muted mt-0.5">
              {pendingCount > 0
                ? `${pendingCount} operation${pendingCount > 1 ? 's' : ''} pending review`
                : 'All operations reviewed'}
            </p>
          </div>
          <button
            type="button"
            onClick={onDone}
            className="text-muted hover:text-foreground transition-colors p-1"
            title="Close"
          >
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        {/* Items list */}
        <div className="flex-1 overflow-y-auto px-5 py-3 space-y-2 scrollbar-thin">
          {items.map((item) => (
            <ApprovalItemRow
              key={item.request.requestId}
              item={item}
              decision={decisions[item.request.requestId] ?? null}
              onDecide={(approved) => handleDecide(item.request.requestId, approved)}
            />
          ))}
        </div>

        {/* Footer actions */}
        <div className="flex items-center justify-between px-5 py-3 border-t border-border gap-2">
          <div className="text-[10px] text-muted/60">
            <kbd className="px-1 py-0.5 rounded bg-background/60 border border-border/40 text-[9px]">Enter</kbd>
            {' '}approve all{' · '}
            <kbd className="px-1 py-0.5 rounded bg-background/60 border border-border/40 text-[9px]">Esc</kbd>
            {' '}deny all
          </div>
          <div className="flex gap-2">
            {!allHandled && (
              <>
                <button
                  type="button"
                  onClick={handleDenyAll}
                  disabled={isSubmitting}
                  className="px-3 py-1.5 rounded border border-border text-xs text-muted hover:text-foreground hover:bg-background transition-colors disabled:opacity-50"
                >
                  Deny All
                </button>
                <button
                  type="button"
                  onClick={handleApproveAll}
                  disabled={isSubmitting}
                  className="px-3 py-1.5 rounded bg-primary text-white text-xs hover:bg-blue-600 transition-colors disabled:opacity-50"
                >
                  {isSubmitting ? 'Processing…' : 'Approve All'}
                </button>
              </>
            )}
            {allHandled && (
              <button
                type="button"
                onClick={onDone}
                className="px-3 py-1.5 rounded bg-primary text-white text-xs hover:bg-blue-600 transition-colors"
              >
                Done
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
});
