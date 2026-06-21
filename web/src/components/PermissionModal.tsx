'use client';

import { PermissionRequest } from '@/lib/store';
import { respondPermission } from '@/lib/api';
import { useState } from 'react';

interface PermissionModalProps {
  requests: PermissionRequest[];
  onResponded: (requestId: string) => void;
}

export function PermissionModal({ requests, onResponded }: PermissionModalProps) {
  const current = requests[0];
  const [scope, setScope] = useState<'once' | 'session' | 'prefix'>('once');
  if (!current) return null;

  const handle = async (approved: boolean) => {
    await respondPermission(current.requestId, approved, approved ? scope : 'once');
    onResponded(current.requestId);
    setScope('once');
  };

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-surface border border-border rounded-lg p-6 max-w-lg w-full">
        <h3 className="text-lg font-semibold mb-2">Permission Required</h3>
        <p className="text-sm text-muted mb-4">
          Tool <strong>{current.tool}</strong> requires your approval.
        </p>
        <pre className="text-xs bg-background p-3 rounded mb-4 overflow-auto max-h-40">
          {JSON.stringify(current.arguments || {}, null, 2)}
        </pre>
        <div className="mb-4 text-sm">
          <label className="block text-muted mb-1">If approved:</label>
          <select
            value={scope}
            onChange={(e) => setScope(e.target.value as 'once' | 'session' | 'prefix')}
            className="w-full rounded border border-border bg-background px-2 py-1"
          >
            <option value="once">Allow once</option>
            <option value="session">Allow for session</option>
            <option value="prefix">Allow similar (prefix)</option>
          </select>
        </div>
        <div className="flex gap-2 justify-end">
          <button
            type="button"
            onClick={() => handle(false)}
            className="px-4 py-2 rounded border border-border text-sm hover:bg-background"
          >
            Deny
          </button>
          <button
            type="button"
            onClick={() => handle(true)}
            className="px-4 py-2 rounded bg-primary text-white text-sm hover:bg-blue-600"
          >
            Approve
          </button>
        </div>
      </div>
    </div>
  );
}
