'use client';

import dynamic from 'next/dynamic';
import { useState } from 'react';

const MonacoDiff = dynamic(
  () => import('@monaco-editor/react').then((mod) => {
    const { DiffEditor } = mod;
    return function MonacoDiffWrapper({
      original,
      modified,
      language,
      sideBySide,
    }: {
      original: string;
      modified: string;
      language: string;
      sideBySide: boolean;
    }) {
      return (
        <DiffEditor
          height="100%"
          original={original}
          modified={modified}
          language={language}
          theme="vs-dark"
          options={{
            readOnly: true,
            renderSideBySide: sideBySide,
            minimap: { enabled: false },
            scrollBeyondLastLine: false,
            fontSize: 12,
            lineNumbers: 'on',
            folding: true,
            wordWrap: 'on',
            padding: { top: 4 },
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

function detectLanguage(filename: string): string {
  const ext = filename.split('.').pop()?.toLowerCase();
  const map: Record<string, string> = {
    ts: 'typescript', tsx: 'typescript',
    js: 'javascript', jsx: 'javascript',
    py: 'python', rs: 'rust', go: 'go',
    json: 'json', css: 'css', scss: 'scss',
    html: 'html', md: 'markdown', yaml: 'yaml', yml: 'yaml',
    sh: 'shell', sql: 'sql', toml: 'ini',
  };
  return map[ext || ''] || 'plaintext';
}

interface DiffViewerProps {
  oldText?: string;
  newText?: string;
  before?: string;
  after?: string;
  language?: string;
  title?: string;
  onAccept?: () => void;
  onReject?: () => void;
}

export function DiffViewer({
  oldText,
  newText,
  before,
  after,
  language,
  title,
  onAccept,
  onReject,
}: DiffViewerProps) {
  const left = oldText ?? before ?? '';
  const right = newText ?? after ?? '';
  const [sideBySide, setSideBySide] = useState(true);
  const detectedLang = language || 'plaintext';

  if (!left && !right) {
    return (
      <div className="text-sm text-muted p-4 text-center">
        Diff will appear when files change.
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between mb-2 px-1 shrink-0">
        <div className="flex items-center gap-2">
          <h2 className="text-sm font-semibold">{title || 'Diff'}</h2>
          {onAccept && (
            <button
              onClick={onAccept}
              className="rounded-md bg-green-600/80 hover:bg-green-600 px-2 py-0.5 text-[10px] font-medium text-white transition-colors"
            >
              Accept
            </button>
          )}
          {onReject && (
            <button
              onClick={onReject}
              className="rounded-md bg-red-600/80 hover:bg-red-600 px-2 py-0.5 text-[10px] font-medium text-white transition-colors"
            >
              Reject
            </button>
          )}
        </div>
        <button
          onClick={() => setSideBySide(!sideBySide)}
          className="text-xs text-primary hover:underline"
        >
          {sideBySide ? 'Inline' : 'Side by side'}
        </button>
      </div>
      <div className="flex-1 min-h-0 rounded-lg border border-border overflow-hidden">
        <MonacoDiff original={left} modified={right} language={detectedLang} sideBySide={sideBySide} />
      </div>
    </div>
  );
}
