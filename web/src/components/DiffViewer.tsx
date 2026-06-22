'use client';

import dynamic from 'next/dynamic';
import { useState } from 'react';

const MonacoDiff = dynamic(
  () => import('@monaco-editor/react').then((mod) => {
    const { DiffEditor } = mod;
    return function MonacoDiffWrapper({ original, modified }: { original: string; modified: string }) {
      return (
        <DiffEditor
          height="100%"
          original={original}
          modified={modified}
          language="text"
          theme="vs-dark"
          options={{
            readOnly: true,
            renderSideBySide: true,
            minimap: { enabled: false },
            scrollBeyondLastLine: false,
            fontSize: 12,
            lineNumbers: 'on',
            folding: true,
            wordWrap: 'on',
          }}
          loading={
            <div className="flex items-center justify-center h-full text-sm text-muted">
              Loading diff editor...
            </div>
          }
        />
      );
    };
  }),
  {
    ssr: false,
    loading: () => (
      <div className="flex items-center justify-center h-full text-sm text-muted">
        Loading diff editor...
      </div>
    ),
  }
);

interface DiffViewerProps {
  oldText?: string;
  newText?: string;
  before?: string;
  after?: string;
}

export function DiffViewer({
  oldText,
  newText,
  before,
  after,
}: DiffViewerProps) {
  const left = oldText ?? before ?? '';
  const right = newText ?? after ?? '';
  const [sideBySide, setSideBySide] = useState(true);

  if (!left && !right) {
    return (
      <div className="text-sm text-muted p-4 text-center">
        Diff will appear when files change.
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between mb-2 px-1">
        <h2 className="text-sm font-semibold">Diff</h2>
        <button
          onClick={() => setSideBySide(!sideBySide)}
          className="text-xs text-primary hover:underline"
        >
          {sideBySide ? 'Inline' : 'Side by side'}
        </button>
      </div>
      <div className="flex-1 min-h-0 rounded-lg border border-border overflow-hidden">
        <MonacoDiff original={left} modified={right} />
      </div>
    </div>
  );
}
