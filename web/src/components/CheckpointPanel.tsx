'use client';

import { fetchCheckpoints, rewindCheckpoint } from '@/lib/api';
import { useAppStore } from '@/lib/store';
import { useEffect, useState } from 'react';

interface Checkpoint {
  id: string;
  label: string;
  created_at: number;
  files?: string[];
}

export function CheckpointPanel() {
  const [checkpoints, setCheckpoints] = useState<Checkpoint[]>([]);
  const [loading, setLoading] = useState(false);
  const [rewinding, setRewinding] = useState<string | null>(null);
  const addToast = useAppStore((s) => s.addToast);

  const load = async () => {
    setLoading(true);
    try {
      const data = await fetchCheckpoints();
      setCheckpoints(data);
    } catch {
      setCheckpoints([]);
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    load();
  }, []);

  const rewind = async (id: string | null, mode: string) => {
    setRewinding(id);
    try {
      const result = await rewindCheckpoint(id, mode as 'code' | 'conversation' | 'both' | 'fork');
      addToast({ type: 'success', message: String(result.message || 'Rewind successful') });
      await load();
    } catch (err) {
      addToast({ type: 'error', message: `Rewind failed: ${err instanceof Error ? err.message : err}` });
    } finally {
      setRewinding(null);
    }
  };

  return (
    <div className="text-sm">
      <div className="flex items-center justify-between mb-2">
        <h4 className="font-semibold">Checkpoints</h4>
        <button
          type="button"
          onClick={load}
          disabled={loading}
          className="text-xs text-primary hover:underline disabled:opacity-50"
        >
          {loading ? 'Loading...' : 'Refresh'}
        </button>
      </div>
      {loading && checkpoints.length === 0 ? (
        <div className="flex items-center gap-2 text-xs text-muted py-2">
          <div className="h-3 w-3 animate-spin rounded-full border border-primary border-t-transparent" />
          Loading checkpoints...
        </div>
      ) : null}
      <ul className="space-y-2 max-h-48 overflow-y-auto">
        {checkpoints.map((cp) => (
          <li key={cp.id} className="border border-border rounded p-2">
            <div className="text-xs truncate">{cp.label || cp.id}</div>
            {cp.files && cp.files.length > 0 && (
              <div className="text-[10px] text-muted truncate mt-0.5">
                {cp.files.slice(0, 2).join(', ')}{cp.files.length > 2 ? '...' : ''}
              </div>
            )}
            <div className="flex flex-wrap gap-1 mt-1">
              <button
                type="button"
                className="text-xs px-2 py-0.5 rounded border border-border hover:bg-primary/10 disabled:opacity-50"
                onClick={() => rewind(cp.id, 'code')}
                disabled={rewinding === cp.id}
              >
                {rewinding === cp.id ? '...' : 'Code'}
              </button>
              <button
                type="button"
                className="text-xs px-2 py-0.5 rounded border border-border hover:bg-primary/10 disabled:opacity-50"
                onClick={() => rewind(cp.id, 'both')}
                disabled={rewinding === cp.id}
              >
                {rewinding === cp.id ? '...' : 'Both'}
              </button>
              <button
                type="button"
                className="text-xs px-2 py-0.5 rounded border border-border hover:bg-primary/10 disabled:opacity-50"
                onClick={() => rewind(cp.id, 'fork')}
                disabled={rewinding === cp.id}
              >
                {rewinding === cp.id ? '...' : 'Fork'}
              </button>
            </div>
          </li>
        ))}
        {!loading && checkpoints.length === 0 && (
          <li className="text-xs text-muted">No checkpoints yet.</li>
        )}
      </ul>
    </div>
  );
}
