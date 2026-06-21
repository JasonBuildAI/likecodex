'use client';

import { fetchCheckpoints, rewindCheckpoint } from '@/lib/api';
import { useEffect, useState } from 'react';

interface Checkpoint {
  id: string;
  label: string;
  created_at: number;
}

export function CheckpointPanel() {
  const [checkpoints, setCheckpoints] = useState<Checkpoint[]>([]);
  const [message, setMessage] = useState('');

  const load = () => {
    fetchCheckpoints().then(setCheckpoints).catch(() => setCheckpoints([]));
  };

  useEffect(() => {
    load();
  }, []);

  const rewind = async (id: string | null, mode: string) => {
    const result = await rewindCheckpoint(id, mode as 'code' | 'conversation' | 'both' | 'fork');
    setMessage(String(result.message || JSON.stringify(result)));
    load();
  };

  return (
    <div className="text-sm">
      <div className="flex items-center justify-between mb-2">
        <h4 className="font-semibold">Checkpoints</h4>
        <button type="button" onClick={load} className="text-xs text-primary">
          Refresh
        </button>
      </div>
      {message ? <p className="text-xs text-muted mb-2">{message}</p> : null}
      <ul className="space-y-2 max-h-48 overflow-y-auto">
        {checkpoints.map((cp) => (
          <li key={cp.id} className="border border-border rounded p-2">
            <div className="text-xs truncate">{cp.label || cp.id}</div>
            <div className="flex flex-wrap gap-1 mt-1">
              <button
                type="button"
                className="text-xs px-2 py-0.5 rounded border border-border"
                onClick={() => rewind(cp.id, 'code')}
              >
                Code
              </button>
              <button
                type="button"
                className="text-xs px-2 py-0.5 rounded border border-border"
                onClick={() => rewind(cp.id, 'both')}
              >
                Both
              </button>
              <button
                type="button"
                className="text-xs px-2 py-0.5 rounded border border-border"
                onClick={() => rewind(cp.id, 'fork')}
              >
                Fork
              </button>
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
