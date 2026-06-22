'use client';

import { memo, useCallback, useEffect, useRef, useState } from 'react';
import { inlineEditCode } from '@/lib/api';
import { useAppStore } from '@/lib/store';
import { writeWorkspaceFile } from '@/lib/api';

export interface InlineEditState {
  visible: boolean;
  code: string;
  language: string;
  filePath: string;
  fullContent: string;
  loading: boolean;
  modifiedCode: string | null;
  error: string | null;
}

interface InlineEditInputProps {
  state: InlineEditState;
  onClose: () => void;
  onApply: (modified: string) => void;
}

export const InlineEditInput = memo(function InlineEditInput({
  state,
  onClose,
  onApply,
}: InlineEditInputProps) {
  const [instruction, setInstruction] = useState('');
  const [loading, setLoading] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const abortRef = useRef<AbortController | null>(null);
  const addToast = useAppStore((s) => s.addToast);

  // Reset when hidden
  useEffect(() => {
    if (!state.visible) {
      setLoading(false);
      setInstruction('');
    }
  }, [state.visible]);

  // Focus input when shown
  useEffect(() => {
    if (state.visible && !loading) {
      inputRef.current?.focus();
    }
  }, [state.visible, loading]);

  // Cleanup abort on unmount
  useEffect(() => {
    return () => {
      abortRef.current?.abort();
    };
  }, []);

  const handleSubmit = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      if (!instruction.trim() || loading) return;

      setLoading(true);
      abortRef.current?.abort();
      abortRef.current = new AbortController();

      try {
        const result = await inlineEditCode(
          {
            code: state.code,
            instruction: instruction.trim(),
            language: state.language,
            full_content: state.fullContent,
            file_path: state.filePath,
          },
          abortRef.current.signal
        );

        if (result) {
          onApply(result.modified);
          setInstruction('');
          addToast({ type: 'success', message: 'AI edit complete' });
        }
      } catch (err) {
        if (err instanceof DOMException && err.name === 'AbortError') return;
        const msg = err instanceof Error ? err.message : String(err);
        addToast({ type: 'error', message: `Inline edit failed: ${msg}` });
      } finally {
        setLoading(false);
      }
    },
    [state.code, state.language, state.fullContent, state.filePath, instruction, loading, onApply, addToast]
  );

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        onClose();
      }
    },
    [onClose]
  );

  if (!state.visible) return null;

  return (
    <div className="border-t border-border bg-surface/80 backdrop-blur-sm shrink-0">
      <form onSubmit={handleSubmit} className="flex items-center gap-2 px-3 py-2">
        <div className="flex items-center gap-1.5 shrink-0">
          <span className="text-[10px] font-medium text-primary bg-primary/10 px-1.5 py-0.5 rounded">
            AI Edit
          </span>
          <span className="text-[10px] text-muted/60 max-w-[200px] truncate" title={state.filePath}>
            {state.filePath || 'selection'}
          </span>
        </div>
        <div className="flex-1 relative">
          <input
            ref={inputRef}
            type="text"
            value={instruction}
            onChange={(e) => setInstruction(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={loading ? 'AI is thinking...' : 'Describe the edit you want (Enter to submit, Esc to cancel)...'}
            disabled={loading}
            className="w-full rounded-md border border-border bg-background px-3 py-1.5 text-xs
                       focus:outline-none focus:ring-2 focus:ring-primary/50
                       disabled:opacity-60 disabled:cursor-wait
                       placeholder:text-muted/40"
          />
        </div>
        <button
          type="submit"
          disabled={loading || !instruction.trim()}
          className="rounded-md bg-primary px-3 py-1.5 text-[11px] font-medium text-white
                     hover:bg-blue-600 disabled:opacity-50 shrink-0 transition-colors"
        >
          {loading ? (
            <span className="flex items-center gap-1">
              <span className="h-1.5 w-1.5 rounded-full bg-white animate-pulse" />
              ...
            </span>
          ) : (
            'Apply'
          )}
        </button>
        <button
          type="button"
          onClick={onClose}
          className="text-[11px] text-muted hover:text-foreground px-1.5 py-1 shrink-0 transition-colors"
        >
          Cancel
        </button>
      </form>

      {state.error && (
        <div className="px-3 pb-2 text-[10px] text-red-400">{state.error}</div>
      )}
    </div>
  );
});
