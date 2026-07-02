'use client';

import { useMemo, useState, useCallback } from 'react';

// ── Types ──────────────────────────────────────────────────────────────

interface ToolCallPreviewProps {
  toolName: string;
  parameters: Record<string, unknown>;
  /** If provided the component shows a diff between old and new */
  previousParameters?: Record<string, unknown>;
  onConfirm: (modified: Record<string, unknown>) => void;
  onReject: () => void;
  onModify: (parameters: Record<string, unknown>) => void;
  readOnly?: boolean;
}

// ── Helpers ────────────────────────────────────────────────────────────

function getValueType(value: unknown): string {
  if (value === null) return 'null';
  if (Array.isArray(value)) return 'array';
  return typeof value;
}

function formatValue(value: unknown): string {
  if (typeof value === 'string') {
    if (value.length > 200) return value.slice(0, 200) + '...';
    return value;
  }
  if (value === null) return 'null';
  if (typeof value === 'object') {
    return JSON.stringify(value, null, 2).slice(0, 500);
  }
  return String(value);
}

// ── Diff Row ───────────────────────────────────────────────────────────

function DiffRow({
  keyName,
  oldVal,
  newVal,
}: {
  keyName: string;
  oldVal: unknown;
  newVal: unknown;
}) {
  const isAdded = oldVal === undefined;
  const isRemoved = newVal === undefined;
  const isChanged = !isAdded && !isRemoved && oldVal !== newVal;
  const isSame = !isAdded && !isRemoved && oldVal === newVal;

  const rowClass = isAdded
    ? 'bg-green-500/10'
    : isRemoved
      ? 'bg-red-500/10'
      : isChanged
        ? 'bg-yellow-500/10'
        : '';

  return (
    <div className={`flex items-start gap-2 px-2 py-1 rounded ${rowClass}`}>
      <span className="text-[9px] font-mono text-muted/70 w-28 shrink-0 truncate" title={keyName}>
        {keyName}
      </span>
      <div className="flex-1 min-w-0">
        {isAdded ? (
          <span className="text-[9px] text-green-400">{formatValue(newVal)}</span>
        ) : isRemoved ? (
          <span className="text-[9px] text-red-400 line-through">{formatValue(oldVal)}</span>
        ) : isChanged ? (
          <div className="space-y-0.5">
            <span className="text-[9px] text-red-400 line-through block">{formatValue(oldVal)}</span>
            <span className="text-[9px] text-green-400 block">{formatValue(newVal)}</span>
          </div>
        ) : (
          <span className="text-[9px] text-muted/60">{formatValue(oldVal)}</span>
        )}
      </div>
      {isSame && (
        <span className="text-[8px] text-muted/30 shrink-0">=</span>
      )}
      {isChanged && !isAdded && !isRemoved && (
        <span className="text-[8px] text-yellow-400/60 shrink-0">≠</span>
      )}
    </div>
  );
}

// ── Main Component ─────────────────────────────────────────────────────

export function ToolCallPreview({
  toolName,
  parameters,
  previousParameters,
  onConfirm,
  onReject,
  onModify,
  readOnly = false,
}: ToolCallPreviewProps) {
  const [editing, setEditing] = useState(false);
  const [editJson, setEditJson] = useState('');
  const [parseError, setParseError] = useState<string | null>(null);

  const allKeys = useMemo(() => {
    const keys = new Set<string>();
    for (const k of Object.keys(parameters)) keys.add(k);
    if (previousParameters) {
      for (const k of Object.keys(previousParameters)) keys.add(k);
    }
    return Array.from(keys).sort();
  }, [parameters, previousParameters]);

  const hasDiff = previousParameters !== undefined;
  const paramCount = Object.keys(parameters).length;

  const startEditing = useCallback(() => {
    setEditJson(JSON.stringify(parameters, null, 2));
    setParseError(null);
    setEditing(true);
  }, [parameters]);

  const saveEdit = useCallback(() => {
    try {
      const parsed = JSON.parse(editJson);
      if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)) {
        setParseError('Root must be a JSON object');
        return;
      }
      setParseError(null);
      onModify(parsed as Record<string, unknown>);
      setEditing(false);
    } catch (e) {
      setParseError(`Invalid JSON: ${(e as Error).message}`);
    }
  }, [editJson, onModify]);

  const cancelEdit = useCallback(() => {
    setEditing(false);
    setParseError(null);
  }, []);

  return (
    <div className="space-y-2">
      {/* Header */}
      <div className="flex items-center justify-between px-1">
        <div className="flex items-center gap-2">
          <span className="text-[10px] font-medium text-muted uppercase tracking-wider">
            Preview
          </span>
          <span className="text-[9px] px-1.5 py-0.5 rounded bg-primary/10 text-primary border border-primary/20">
            {toolName}
          </span>
          <span className="text-[9px] text-muted/50">{paramCount} params</span>
        </div>
        {!readOnly && !editing && (
          <button
            onClick={startEditing}
            className="text-[9px] px-1.5 py-0.5 rounded border border-border/40 text-muted/50 hover:text-muted hover:bg-background transition-colors"
          >
            Edit JSON
          </button>
        )}
      </div>

      {/* Diff / Parameter view */}
      {editing ? (
        <div className="space-y-1">
          <textarea
            autoFocus
            value={editJson}
            onChange={(e) => {
              setEditJson(e.target.value);
              setParseError(null);
            }}
            className="w-full text-[10px] font-mono bg-background border border-border rounded p-2 text-foreground outline-none min-h-[120px] resize-vertical"
          />
          {parseError && (
            <p className="text-[9px] text-red-400">{parseError}</p>
          )}
          <div className="flex items-center gap-1 justify-end">
            <button
              onClick={cancelEdit}
              className="text-[9px] px-2 py-0.5 rounded border border-border/40 text-muted/60 hover:text-muted"
            >
              Cancel
            </button>
            <button
              onClick={saveEdit}
              className="text-[9px] px-2 py-0.5 rounded bg-primary/80 text-white hover:bg-primary"
            >
              Apply
            </button>
          </div>
        </div>
      ) : hasDiff ? (
        <div className="border border-border/20 rounded overflow-hidden">
          <div className="bg-background/50 px-2 py-1 border-b border-border/20">
            <span className="text-[9px] text-muted/50">Parameter diff</span>
          </div>
          <div className="divide-y divide-border/10 max-h-48 overflow-y-auto">
            {allKeys.map((key) => (
              <DiffRow
                key={key}
                keyName={key}
                oldVal={previousParameters?.[key]}
                newVal={parameters[key]}
              />
            ))}
          </div>
        </div>
      ) : (
        <div className="bg-background/30 border border-border/20 rounded p-2 max-h-48 overflow-y-auto">
          <pre className="text-[9px] font-mono text-muted/70 whitespace-pre-wrap break-all">
            {JSON.stringify(parameters, null, 2)}
          </pre>
        </div>
      )}

      {/* Action buttons */}
      {!readOnly && (
        <div className="flex items-center gap-1 justify-end px-1">
          <button
            onClick={onReject}
            className="text-[9px] px-2.5 py-1 rounded border border-border/40 text-muted/60 hover:text-muted hover:bg-background transition-colors"
          >
            Reject
          </button>
          {!editing && (
            <button
              onClick={() => onConfirm(parameters)}
              className="text-[9px] px-2.5 py-1 rounded bg-primary/80 text-white hover:bg-primary transition-colors"
            >
              Confirm
            </button>
          )}
        </div>
      )}
    </div>
  );
}

export default ToolCallPreview;
