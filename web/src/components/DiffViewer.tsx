'use client';

interface DiffViewerProps {
  oldText?: string;
  newText?: string;
}

export function DiffViewer({ oldText = '', newText = '' }: DiffViewerProps) {
  return (
    <div className="bg-surface border border-border rounded-lg p-4">
      <h2 className="text-sm font-semibold mb-3">Diff</h2>
      <div className="grid grid-cols-2 gap-4 text-xs">
        <pre className="bg-red-950/30 p-2 rounded border border-red-900/50 overflow-auto">{oldText}</pre>
        <pre className="bg-green-950/30 p-2 rounded border border-green-900/50 overflow-auto">{newText}</pre>
      </div>
    </div>
  );
}
