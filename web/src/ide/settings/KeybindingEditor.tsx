'use client';

import { useState, useEffect, useCallback } from 'react';
import type { Keybinding, KeybindingConflict } from './types';

/**
 * KeybindingEditor — Visual editor for keyboard shortcuts.
 * Users can click "修改" to record a new key combination.
 */
export function KeybindingEditor() {
  const [keybindings, setKeybindings] = useState<Keybinding[]>([]);
  const [conflicts, setConflicts] = useState<KeybindingConflict[]>([]);
  const [recording, setRecording] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const loadKeybindings = useCallback(async () => {
    setLoading(true);
    try {
      const resp = await fetch('/api/ide/settings/keybindings');
      if (resp.ok) {
        const data = await resp.json();
        setKeybindings(data.keybindings || []);
        setConflicts(data.conflicts || []);
      }
    } catch {
      // Best-effort
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadKeybindings();
  }, [loadKeybindings]);

  const handleKeyDown = useCallback((e: React.KeyboardEvent) => {
    if (!recording) return;
    e.preventDefault();

    const keys: string[] = [];
    if (e.ctrlKey || e.metaKey) keys.push('Ctrl');
    if (e.shiftKey) keys.push('Shift');
    if (e.altKey) keys.push('Alt');

    if (e.key !== 'Control' && e.key !== 'Shift' && e.key !== 'Alt' && e.key !== 'Meta') {
      const keyName = e.key === ' ' ? 'Space' : e.key.length === 1 ? e.key.toUpperCase() : e.key;
      keys.push(keyName);

      // Save the new keybinding
      fetch('/api/ide/settings/keybindings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ id: recording, keys }),
      }).then(() => {
        loadKeybindings();
      });

      setKeybindings((prev) =>
        prev.map((kb) =>
          kb.id === recording ? { ...kb, keys } : kb
        )
      );
      setRecording(null);
    }
  }, [recording, loadKeybindings]);

  const handleReset = useCallback(async () => {
    try {
      await fetch('/api/ide/settings/keybindings/reset', { method: 'POST' });
      loadKeybindings();
    } catch {
      // Best-effort
    }
  }, [loadKeybindings]);

  if (loading) {
    return <div className="p-4 text-xs text-muted">Loading keybindings...</div>;
  }

  return (
    <div tabIndex={0} onKeyDown={handleKeyDown} className="outline-none">
      {/* Conflicts warning */}
      {conflicts.length > 0 && (
        <div className="mb-3 p-2 bg-red-900/20 border border-red-700/50 rounded text-xs text-red-300">
          ⚠ {conflicts.length} keybinding conflict(s) detected:
          {conflicts.map((c) => (
            <div key={c.keys} className="mt-1">
              <span className="font-mono">{c.keys}</span>: {c.bindings.map((b) => b.label).join(', ')}
            </div>
          ))}
        </div>
      )}

      {/* Keybinding list */}
      <div className="space-y-0.5">
        {keybindings.map((kb) => (
          <div key={kb.id} className="flex items-center justify-between py-1.5 px-2 rounded hover:bg-accent/5">
            <div>
              <span className="text-sm text-foreground">{kb.label}</span>
              <span className="text-[10px] text-muted ml-2">{kb.when}</span>
            </div>
            <div className="flex items-center gap-2">
              {recording === kb.id ? (
                <span className="text-xs text-yellow-400 animate-pulse">按下快捷键...</span>
              ) : (
                <div className="flex gap-0.5">
                  {kb.keys.map((key, i) => (
                    <kbd
                      key={i}
                      className="px-1.5 py-0.5 bg-accent/20 border border-border text-xs rounded font-mono"
                    >
                      {key}
                    </kbd>
                  ))}
                </div>
              )}
              <button
                onClick={() => setRecording(recording === kb.id ? null : kb.id)}
                className="px-2 py-0.5 text-[10px] bg-accent/20 rounded hover:bg-accent/40 transition-colors"
              >
                {recording === kb.id ? '取消' : '修改'}
              </button>
            </div>
          </div>
        ))}
      </div>

      {/* Reset button */}
      <button
        onClick={handleReset}
        className="mt-4 px-3 py-1.5 text-xs bg-red-600/20 text-red-400 rounded hover:bg-red-600/40 transition-colors"
      >
        ↺ Reset All to Defaults
      </button>
    </div>
  );
}
