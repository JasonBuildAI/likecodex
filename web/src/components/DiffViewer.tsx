'use client';

import dynamic from 'next/dynamic';
import { useState, useMemo, useCallback } from 'react';

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

/** Compute simple diff stats from two texts */
function computeDiffStats(oldText: string, newText: string) {
  if (oldText === newText) {
    return { added: 0, removed: 0, modified: 0 };
  }

  const oldLines = oldText.split('\n');
  const newLines = newText.split('\n');

  let added = 0;
  let removed = 0;

  // Simple LCS-based stat computation
  const maxLen = Math.max(oldLines.length, newLines.length);
  let i = 0, j = 0;
  while (i < oldLines.length || j < newLines.length) {
    if (i >= oldLines.length) {
      added += newLines.length - j;
      break;
    }
    if (j >= newLines.length) {
      removed += oldLines.length - i;
      break;
    }
    if (oldLines[i] === newLines[j]) {
      i++;
      j++;
    } else {
      // Try to find matching line
      let found = false;
      for (let k = 1; k <= 3 && i + k < oldLines.length; k++) {
        if (oldLines[i + k] === newLines[j]) {
          removed += k;
          i += k;
          found = true;
          break;
        }
      }
      if (!found) {
        for (let k = 1; k <= 3 && j + k < newLines.length; k++) {
          if (oldLines[i] === newLines[j + k]) {
            added += k;
            j += k;
            found = true;
            break;
          }
        }
      }
      if (!found) {
        removed++;
        added++;
        i++;
        j++;
      }
    }
  }

  return { added, removed, modified: Math.min(added, removed) };
}

interface DiffViewerProps {
  oldText?: string;
  newText?: string;
  before?: string;
  after?: string;
  language?: string;
  title?: string;
  filename?: string;
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
  filename,
  onAccept,
  onReject,
}: DiffViewerProps) {
  const left = oldText ?? before ?? '';
  const right = newText ?? after ?? '';
  const [sideBySide, setSideBySide] = useState(true);
  const [currentChange, setCurrentChange] = useState(0);
  const detectedLang = language || (filename ? detectLanguage(filename) : 'plaintext');

  const stats = useMemo(() => computeDiffStats(left, right), [left, right]);
  const totalChanges = stats.added + stats.removed;

  const toggleMode = useCallback(() => setSideBySide((prev) => !prev), []);

  const goToPrevChange = useCallback(() => {
    setCurrentChange((prev) => Math.max(0, prev - 1));
  }, []);

  const goToNextChange = useCallback(() => {
    setCurrentChange((prev) => Math.min(totalChanges - 1, prev + 1));
  }, [totalChanges]);

  if (!left && !right) {
    return (
      <div className="text-sm text-muted p-4 text-center">
        Diff will appear when files change.
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      {/* Title + Actions */}
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
          onClick={toggleMode}
          className="text-xs text-primary hover:underline"
        >
          {sideBySide ? 'Inline' : 'Side by side'}
        </button>
      </div>

      {/* Change Stats */}
      {totalChanges > 0 && (
        <div className="flex items-center gap-3 px-1 pb-2 shrink-0">
          <span className="text-xs text-green-400">+{stats.added}</span>
          <span className="text-xs text-red-400">-{stats.removed}</span>
          <span className="text-xs text-yellow-400">~{stats.modified}</span>
          <span className="text-xs text-muted-foreground ml-auto">
            {totalChanges} change{totalChanges !== 1 ? 's' : ''}
          </span>
          {/* Navigation */}
          {totalChanges > 1 && (
            <div className="flex items-center gap-1">
              <button
                onClick={goToPrevChange}
                disabled={currentChange === 0}
                className="text-xs px-1 py-0.5 rounded bg-gray-700 hover:bg-gray-600 disabled:opacity-30 disabled:cursor-not-allowed"
                title="Previous change"
              >
                ▲
              </button>
              <span className="text-xs text-muted-foreground">
                {currentChange + 1}/{totalChanges}
              </span>
              <button
                onClick={goToNextChange}
                disabled={currentChange >= totalChanges - 1}
                className="text-xs px-1 py-0.5 rounded bg-gray-700 hover:bg-gray-600 disabled:opacity-30 disabled:cursor-not-allowed"
                title="Next change"
              >
                ▼
              </button>
            </div>
          )}
        </div>
      )}

      {/* Diff Editor */}
      <div className="flex-1 min-h-0 rounded-lg border border-border overflow-hidden">
        <MonacoDiff original={left} modified={right} language={detectedLang} sideBySide={sideBySide} />
      </div>
    </div>
  );
}
