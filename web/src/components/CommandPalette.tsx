'use client';

import { useEffect, useRef, useState } from 'react';
import { useAppStore } from '@/lib/store';

interface Command {
  id: string;
  label: string;
  description: string;
  action: () => void;
  shortcut?: string;
}

export function CommandPalette() {
  const open = useAppStore((s) => s.commandPaletteOpen);
  const setOpen = useAppStore((s) => s.setCommandPaletteOpen);
  const toggleSidebar = useAppStore((s) => s.toggleSidebar);
  const setSettingsOpen = useAppStore((s) => s.setSettingsOpen);
  const [query, setQuery] = useState('');
  const [selectedIndex, setSelectedIndex] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    if (open) {
      setQuery('');
      setSelectedIndex(0);
      setTimeout(() => inputRef.current?.focus(), 50);
    }
  }, [open]);

  const commands: Command[] = [
    { id: 'new-session', label: 'New Session', description: 'Create a new conversation session', shortcut: 'Ctrl+N', action: () => {
      setOpen(false);
      import('@/lib/api').then(({ createNewSession }) => createNewSession().then((r) => {
        useAppStore.getState().setCurrentSessionId(r.session_id);
        useAppStore.getState().addToast({ type: 'success', message: 'New session created' });
      }));
    }},
    { id: 'toggle-sidebar', label: 'Toggle Sidebar', description: 'Show or hide the sidebar panel', shortcut: 'Ctrl+B', action: () => { toggleSidebar(); setOpen(false); }},
    { id: 'settings', label: 'Settings', description: 'Open settings panel', shortcut: 'Ctrl+S', action: () => { setSettingsOpen(true); setOpen(false); }},
    { id: 'toggle-theme', label: 'Toggle Theme', description: 'Switch between dark and light theme', action: () => {
      const store = useAppStore.getState();
      store.setTheme(store.theme === 'dark' ? 'light' : 'dark');
      setOpen(false);
    }},
    { id: 'approval-auto', label: 'Approval: Auto', description: 'Set approval mode to auto', action: () => { useAppStore.getState().setApprovalMode('auto'); setOpen(false); }},
    { id: 'approval-yolo', label: 'Approval: YOLO', description: 'Set approval mode to yolo (no confirmations)', action: () => { useAppStore.getState().setApprovalMode('yolo'); setOpen(false); }},
    { id: 'compact-context', label: 'Compact Context', description: 'Manually compact conversation context', action: () => {
      const sid = useAppStore.getState().currentSessionId;
      if (sid) import('@/lib/api').then(({ compactSession }) => compactSession(sid));
      setOpen(false);
    }},
    { id: 'code-search', label: 'Code Symbol Search', description: 'Search symbols in the codebase', shortcut: 'Ctrl+Shift+F', action: () => { setOpen(false); }},
  ];

  const filtered = query
    ? commands.filter((c) => c.label.toLowerCase().includes(query.toLowerCase()) || c.description.toLowerCase().includes(query.toLowerCase()))
    : commands;

  useEffect(() => {
    setSelectedIndex(0);
  }, [query]);

  const execute = (cmd: Command) => {
    cmd.action();
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setSelectedIndex((i) => Math.min(i + 1, filtered.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setSelectedIndex((i) => Math.max(i - 1, 0));
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (filtered[selectedIndex]) execute(filtered[selectedIndex]);
    } else if (e.key === 'Escape') {
      setOpen(false);
    }
  };

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-[9998] flex items-start justify-center pt-[20vh]">
      <div className="fixed inset-0 bg-black/50" onClick={() => setOpen(false)} />
      <div className="relative z-10 w-full max-w-lg rounded-xl bg-surface border border-border shadow-2xl overflow-hidden">
        <div className="p-3 border-b border-border">
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Type a command..."
            className="w-full bg-transparent text-sm outline-none placeholder:text-muted"
          />
        </div>
        <div className="max-h-64 overflow-y-auto p-1">
          {filtered.map((cmd, i) => (
            <button
              key={cmd.id}
              onClick={() => execute(cmd)}
              className={`w-full text-left px-3 py-2 rounded-md flex items-center justify-between gap-3 ${
                i === selectedIndex ? 'bg-primary/20' : 'hover:bg-accent/10'
              }`}
            >
              <div>
                <div className="text-sm">{cmd.label}</div>
                <div className="text-xs text-muted">{cmd.description}</div>
              </div>
              {cmd.shortcut && (
                <kbd className="text-[10px] px-1.5 py-0.5 rounded bg-background border border-border text-muted shrink-0">
                  {cmd.shortcut}
                </kbd>
              )}
            </button>
          ))}
          {filtered.length === 0 && (
            <p className="text-sm text-muted text-center py-4">No commands found.</p>
          )}
        </div>
      </div>
    </div>
  );
}
