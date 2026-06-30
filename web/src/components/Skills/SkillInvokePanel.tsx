'use client';

import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import type { Skill } from '@/lib/store';

interface InvokeResult {
  skill: string;
  mode: string;
  result?: string;
  body?: string;
}

export function SkillInvokePanel({
  result,
  skill,
  onClose,
}: {
  result: InvokeResult;
  skill: Skill;
  onClose: () => void;
}) {
  const content = result.mode === 'subagent' ? result.result || '' : result.body || '';

  return (
    <div className="rounded border border-border bg-surface overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-border bg-surface-hover">
        <div className="flex items-center gap-2">
          <span className="text-xs font-medium">▶ {result.skill}</span>
          <span className="text-[9px] px-1.5 py-0.5 rounded bg-primary/10 text-primary">
            {result.mode}
          </span>
        </div>
        <button
          onClick={onClose}
          className="text-muted hover:text-foreground text-sm leading-none"
        >
          ×
        </button>
      </div>

      {/* Content */}
      <div className="p-3 max-h-96 overflow-y-auto">
        {content ? (
          <div className="prose prose-sm prose-invert max-w-none">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>
              {content}
            </ReactMarkdown>
          </div>
        ) : (
          <p className="text-xs text-muted italic">No output.</p>
        )}
      </div>
    </div>
  );
}
