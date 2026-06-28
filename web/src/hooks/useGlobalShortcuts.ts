'use client';

import { useEffect, useCallback, useRef, useMemo } from 'react';
import { useAppStore } from '@/lib/store';

// ── Types ──────────────────────────────────────────────────────────────
export type ShortcutHandler = (e: KeyboardEvent) => void;

export interface ShortcutConfig {
  key: string;
  modifiers?: {
    ctrl?: boolean;
    meta?: boolean;
    shift?: boolean;
    alt?: boolean;
  };
  handler: ShortcutHandler;
  description?: string;
  preventDefault?: boolean;
}

// ── Default Shortcuts ──────────────────────────────────────────────────
const defaultShortcuts: ShortcutConfig[] = [
  {
    key: 'k',
    modifiers: { ctrl: true },
    handler: () => {
      const store = useAppStore.getState();
      store.setCommandPaletteOpen(true);
    },
    description: 'Open Command Palette',
    preventDefault: true,
  },
  {
    key: 'b',
    modifiers: { ctrl: true },
    handler: () => {
      const store = useAppStore.getState();
      store.toggleSidebar();
    },
    description: 'Toggle Sidebar',
    preventDefault: true,
  },
  {
    key: 'n',
    modifiers: { ctrl: true },
    handler: async () => {
      // Handled in page.tsx for session creation
    },
    description: 'New Session',
    preventDefault: true,
  },
  {
    key: ',',
    modifiers: { ctrl: true },
    handler: () => {
      // Will be handled by component state
    },
    description: 'Open Settings',
    preventDefault: true,
  },
  {
    key: '?',
    modifiers: {},
    handler: () => {
      const store = useAppStore.getState();
      store.setShortcutHelpOpen(true);
    },
    description: 'Show Keyboard Shortcuts',
    preventDefault: true,
  },
  {
    key: 'Escape',
    modifiers: {},
    handler: () => {
      const store = useAppStore.getState();
      store.setCommandPaletteOpen(false);
      store.setSettingsOpen(false);
      store.setShortcutHelpOpen(false);
    },
    description: 'Close Modals',
    preventDefault: false,
  },
];

// ── Helper Functions ───────────────────────────────────────────────────
function isInputFocused(): boolean {
  const activeElement = document.activeElement;
  if (!activeElement) return false;
  
  const tagName = activeElement.tagName.toLowerCase();
  return (
    tagName === 'input' ||
    tagName === 'textarea' ||
    tagName === 'select' ||
    activeElement.getAttribute('contenteditable') === 'true'
  );
}

function matchesShortcut(e: KeyboardEvent, config: ShortcutConfig): boolean {
  // Check key
  if (e.key.toLowerCase() !== config.key.toLowerCase()) return false;
  
  // Check modifiers
  const mods = config.modifiers || {};
  if (mods.ctrl && !e.ctrlKey) return false;
  if (mods.meta && !e.metaKey) return false;
  if (mods.shift && !e.shiftKey) return false;
  if (mods.alt && !e.altKey) return false;
  
  // Ensure no extra modifiers
  if (!mods.ctrl && e.ctrlKey) return false;
  if (!mods.meta && e.metaKey) return false;
  if (!mods.shift && e.shiftKey) return false;
  if (!mods.alt && e.altKey) return false;
  
  return true;
}

// ── Hook ───────────────────────────────────────────────────────────────
/**
 * Global keyboard shortcuts manager
 * Automatically handles input focus detection and prevents conflicts
 */
export function useGlobalShortcuts(customShortcuts?: ShortcutConfig[]) {
  // Use ref to avoid recreating shortcuts array on every render
  const shortcutsRef = useRef<ShortcutConfig[]>([]);
  shortcutsRef.current = [...defaultShortcuts, ...(customShortcuts || [])];

  // Stable event handler: always reads the latest shortcuts from ref
  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    // Skip if typing in input/textarea
    if (isInputFocused()) return;

    // Find matching shortcut
    const matchingShortcut = shortcutsRef.current.find(config => matchesShortcut(e, config));
    
    if (matchingShortcut) {
      if (matchingShortcut.preventDefault) {
        e.preventDefault();
      }
      matchingShortcut.handler(e);
    }
  }, []);

  // Bind once on mount, unbind on unmount — never re-binds
  useEffect(() => {
    window.addEventListener('keydown', handleKeyDown);
    
    return () => {
      window.removeEventListener('keydown', handleKeyDown);
    };
  }, [handleKeyDown]);

  // Expose getShortcuts for help panel (stable reference)
  const displayShortcuts = useMemo(
    () =>
      shortcutsRef.current.map(s => ({
        keys: `${s.modifiers?.ctrl ? 'Ctrl+' : ''}${s.modifiers?.meta ? 'Cmd+' : ''}${s.modifiers?.shift ? 'Shift+' : ''}${s.modifiers?.alt ? 'Alt+' : ''}${s.key.toUpperCase()}`,
        description: s.description || '',
      })),
    // customShortcuts changes rarely; re-memoize only when it changes
    // eslint-disable-next-line react-hooks/exhaustive-deps
    [customShortcuts],
  );

  return {
    shortcuts: displayShortcuts,
  };
}

// ── Export for direct usage ────────────────────────────────────────────
export { isInputFocused, matchesShortcut };
export default useGlobalShortcuts;
