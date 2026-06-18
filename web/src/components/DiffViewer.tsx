'use client';

interface DiffViewerProps {
  before: string;
  after: string;
}

export function DiffViewer({ before, after }: DiffViewerProps) {
  return (
    <div className="bg-surface border border-border rounded-lg p-4 h-full flex flex-col">
      <h2 className="text-sm font-semibold mb-3">Diff</h2>
      <div className="grid grid-cols-2 gap-2 flex-1 min-h-0">
        <div className="flex flex-col min-h-0">
          <div className="text-xs text-muted mb-1">Before</div>
          <pre className="text-xs overflow-auto flex-1 bg-background p-2 rounded border border-border">
            {before || '(empty)'}
          </pre>
        </div>
        <div className="flex flex-col min-h-0">
          <div className="text-xs text-muted mb-1">After</div>
          <pre className="text-xs overflow-auto flex-1 bg-background p-2 rounded border border-border">
            {after || '(empty)'}
          </pre>
        </div>
      </div>
    </div>
  );
}
