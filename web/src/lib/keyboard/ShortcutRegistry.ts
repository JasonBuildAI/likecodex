'use client';

export type KeyCombo = {
  key: string;
  ctrl?: boolean;
  meta?: boolean;
  shift?: boolean;
  alt?: boolean;
};

export type ShortcutContext = 'global' | 'input' | 'chat' | 'editor' | 'terminal' | 'modal';

export interface ShortcutHandler {
  id: string;
  combo: KeyCombo;
  handler: (e: KeyboardEvent) => void | boolean;
  context: ShortcutContext;
  priority: number;
  description: string;
  enabled: boolean;
}

function comboToString(combo: KeyCombo): string {
  const parts: string[] = [];
  if (combo.ctrl) parts.push('Ctrl');
  if (combo.meta) parts.push('Meta');
  if (combo.shift) parts.push('Shift');
  if (combo.alt) parts.push('Alt');
  parts.push(combo.key.toLowerCase());
  return parts.join('+');
}

function matchesCombo(e: KeyboardEvent, combo: KeyCombo): boolean {
  const key = e.key.toLowerCase();
  const comboKey = combo.key.toLowerCase();
  const ctrlMatch = !!combo.ctrl === (e.ctrlKey || e.metaKey);
  const metaMatch = !!combo.meta === e.metaKey;
  const shiftMatch = !!combo.shift === e.shiftKey;
  const altMatch = !!combo.alt === e.altKey;
  const keyMatch = key === comboKey;
  return keyMatch && ctrlMatch && metaMatch && shiftMatch && altMatch;
}

function getActiveContext(): ShortcutContext {
  if (document.activeElement?.tagName === 'INPUT' || document.activeElement?.tagName === 'TEXTAREA') {
    return 'input';
  }
  if (document.activeElement?.closest('[data-context="chat"]')) return 'chat';
  if (document.activeElement?.closest('[data-context="editor"]')) return 'editor';
  if (document.activeElement?.closest('[data-context="terminal"]')) return 'terminal';
  if (document.activeElement?.closest('[data-context="modal"]')) return 'modal';
  return 'global';
}

/**
 * Centralized keyboard shortcut registry.
 * Supports priority-based execution, context awareness, and conflict detection.
 */
export class ShortcutRegistry {
  private shortcuts: Map<string, ShortcutHandler> = new Map();
  private boundHandler: ((e: KeyboardEvent) => void) | null = null;
  private isListening = false;

  register(handler: ShortcutHandler): void {
    const key = comboToString(handler.combo);
    const existing = this.shortcuts.get(key);
    if (existing && existing.priority >= handler.priority) {
      console.warn(
        `[ShortcutRegistry] Skipping "${key}" (${handler.description}): higher priority handler already registered`,
      );
      return;
    }
    this.shortcuts.set(key, handler);
  }

  unregister(id: string): void {
    for (const [key, handler] of this.shortcuts) {
      if (handler.id === id) {
        this.shortcuts.delete(key);
        return;
      }
    }
  }

  getHandler(key: string): ShortcutHandler | undefined {
    return this.shortcuts.get(key);
  }

  getAll(): ShortcutHandler[] {
    return Array.from(this.shortcuts.values());
  }

  getConflicts(): Array<{ combo: string; handlers: ShortcutHandler[] }> {
    const grouped = new Map<string, ShortcutHandler[]>();
    for (const handler of this.shortcuts.values()) {
      const key = comboToString(handler.combo);
      const list = grouped.get(key) || [];
      list.push(handler);
      grouped.set(key, list);
    }
    const conflicts: Array<{ combo: string; handlers: ShortcutHandler[] }> = [];
    for (const [combo, handlers] of grouped) {
      if (handlers.length > 1) {
        conflicts.push({ combo, handlers });
      }
    }
    return conflicts;
  }

  start(): void {
    if (this.isListening) return;
    this.isListening = true;
    this.boundHandler = (e: KeyboardEvent) => {
      const context = getActiveContext();
      const sorted = Array.from(this.shortcuts.values())
        .filter((h) => h.enabled)
        .sort((a, b) => b.priority - a.priority);

      for (const handler of sorted) {
        if (!matchesCombo(e, handler.combo)) continue;
        if (handler.context !== 'global' && handler.context !== context) continue;

        const result = handler.handler(e);
        if (result !== false) {
          e.preventDefault();
          e.stopPropagation();
          return;
        }
      }
    };
    window.addEventListener('keydown', this.boundHandler);
  }

  stop(): void {
    if (!this.isListening || !this.boundHandler) return;
    window.removeEventListener('keydown', this.boundHandler);
    this.isListening = false;
    this.boundHandler = null;
  }

  clear(): void {
    this.shortcuts.clear();
  }
}

/** Singleton instance for global use */
export const globalShortcutRegistry = new ShortcutRegistry();
