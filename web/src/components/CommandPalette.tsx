'use client';

import { useEffect, useRef, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
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
    {
      id: 'new-session',
      label: 'New Session',
      description: 'Create a new conversation session',
      shortcut: 'Ctrl+N',
      action: () => {
        setOpen(false);
        import('@/lib/api').then(({ createNewSession }) =>
          createNewSession().then((r) => {
            useAppStore
              .getState()
              .setCurrentSessionId(r.session_id);
            useAppStore
              .getState()
              .addToast({
                type: 'success',
                message: 'New session created',
              });
          })
        );
      },
    },
    {
      id: 'toggle-sidebar',
      label: 'Toggle Sidebar',
      description: 'Show or hide the sidebar panel',
      shortcut: 'Ctrl+B',
      action: () => {
        toggleSidebar();
        setOpen(false);
      },
    },
    {
      id: 'settings',
      label: 'Settings',
      description: 'Open settings panel',
      shortcut: 'Ctrl+S',
      action: () => {
        setSettingsOpen(true);
        setOpen(false);
      },
    },
    {
      id: 'toggle-theme',
      label: 'Toggle Theme',
      description: 'Switch between dark and light theme',
      action: () => {
        const store = useAppStore.getState();
        store.setTheme(store.theme === 'dark' ? 'light' : 'dark');
        setOpen(false);
      },
    },
    {
      id: 'approval-auto',
      label: 'Approval: Auto',
      description: 'Set approval mode to auto',
      action: () => {
        useAppStore.getState().setApprovalMode('auto');
        setOpen(false);
      },
    },
    {
      id: 'approval-yolo',
      label: 'Approval: YOLO',
      description:
        'Set approval mode to yolo (no confirmations)',
      action: () => {
        useAppStore.getState().setApprovalMode('yolo');
        setOpen(false);
      },
    },
    {
      id: 'compact-context',
      label: 'Compact Context',
      description:
        'Manually compact conversation context',
      action: () => {
        const sid =
          useAppStore.getState().currentSessionId;
        if (sid)
          import('@/lib/api').then(({ compactSession }) =>
            compactSession(sid)
          );
        setOpen(false);
      },
    },
    {
      id: 'code-search',
      label: 'Code Symbol Search',
      description: 'Search symbols in the codebase',
      shortcut: 'Ctrl+Shift+F',
      action: () => {
        setOpen(false);
      },
    },
  ];

  // Fuzzy search filter
  const filtered = query
    ? commands.filter(
        (c) =>
          c.label
            .toLowerCase()
            .includes(query.toLowerCase()) ||
          c.description
            .toLowerCase()
            .includes(query.toLowerCase())
      )
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
      setSelectedIndex((i) =>
        Math.min(i + 1, filtered.length - 1)
      );
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setSelectedIndex((i) => Math.max(i - 1, 0));
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (filtered[selectedIndex])
        execute(filtered[selectedIndex]);
    } else if (e.key === 'Escape') {
      setOpen(false);
    }
  };

  return (
    <AnimatePresence>
      {open && (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          exit={{ opacity: 0 }}
          transition={{ duration: 0.15 }}
          className="fixed inset-0 z-[9998] flex items-start justify-center pt-[20vh]"
        >
          {/* Backdrop */}
          <motion.div
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            className="fixed inset-0 bg-black/60 backdrop-blur-sm"
            onClick={() => setOpen(false)}
          />

          {/* Panel */}
          <motion.div
            initial={{ opacity: 0, scale: 0.95, y: -20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.95, y: -20 }}
            transition={{
              type: 'spring',
              stiffness: 300,
              damping: 25,
            }}
            className="relative z-10 w-full max-w-lg rounded-xl bg-surface/95 backdrop-blur-xl border border-border/50 shadow-2xl overflow-hidden"
          >
            {/* Search input */}
            <div className="p-3 border-b border-border/50">
              <div className="flex items-center gap-2">
                <svg
                  className="h-4 w-4 text-muted shrink-0"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    strokeWidth={2}
                    d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"
                  />
                </svg>
                <input
                  ref={inputRef}
                  type="text"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  onKeyDown={handleKeyDown}
                  placeholder="Type a command..."
                  className="w-full bg-transparent text-sm outline-none placeholder:text-muted/60"
                />
              </div>
            </div>

            {/* Results */}
            <div className="max-h-64 overflow-y-auto p-1.5">
              {filtered.map((cmd, i) => (
                <motion.button
                  key={cmd.id}
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  transition={{
                    delay: i * 0.03,
                    duration: 0.15,
                  }}
                  onClick={() => execute(cmd)}
                  className={`w-full text-left px-3 py-2.5 rounded-lg flex items-center justify-between gap-3 transition-all-smooth ${
                    i === selectedIndex
                      ? 'bg-primary/20 text-foreground shadow-sm'
                      : 'hover:bg-accent/10 text-muted hover:text-foreground'
                  }`}
                >
                  <div className="min-w-0">
                    <div className="text-sm font-medium truncate">
                      {cmd.label}
                    </div>
                    <div className="text-xs text-muted/70 truncate">
                      {cmd.description}
                    </div>
                  </div>
                  {cmd.shortcut && (
                    <kbd className="text-[10px] px-1.5 py-0.5 rounded bg-background/80 border border-border/50 text-muted/60 shrink-0 font-mono">
                      {cmd.shortcut}
                    </kbd>
                  )}
                </motion.button>
              ))}
              {filtered.length === 0 && (
                <motion.p
                  initial={{ opacity: 0 }}
                  animate={{ opacity: 1 }}
                  className="text-sm text-muted text-center py-6"
                >
                  No commands found.
                </motion.p>
              )}
            </div>

            {/* Footer */}
            <div className="px-3 py-2 border-t border-border/50 bg-surface/30">
              <div className="flex items-center gap-3 text-[10px] text-muted/50">
                <span>
                  <kbd className="px-1 py-0.5 rounded bg-background/60 border border-border/30">
                    ↑↓
                  </kbd>{' '}
                  Navigate
                </span>
                <span>
                  <kbd className="px-1 py-0.5 rounded bg-background/60 border border-border/30">
                    ↵
                  </kbd>{' '}
                  Select
                </span>
                <span>
                  <kbd className="px-1 py-0.5 rounded bg-background/60 border border-border/30">
                    Esc
                  </kbd>{' '}
                  Close
                </span>
              </div>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}
