'use client';

import type { ShortcutHandler, KeyCombo } from './ShortcutRegistry';

export interface ConflictReport {
  combo: string;
  handlers: ShortcutHandler[];
}

export interface ConflictSolution {
  combo: string;
  /** Recommended handler to keep */
  keep: ShortcutHandler;
  /** Suggested new combo for the conflicting handler */
  suggestion: string;
}

/**
 * Shortcut conflict detector.
 * Analyzes registered shortcuts for potential conflicts and suggests resolutions.
 */
export class ShortcutConflictDetector {
  /**
   * Analyze a list of shortcuts and report all conflicts.
   */
  static analyze(handlers: ShortcutHandler[]): ConflictReport[] {
    const grouped = new Map<string, ShortcutHandler[]>();
    for (const handler of handlers) {
      const key = ShortcutConflictDetector.comboToString(handler.combo);
      const list = grouped.get(key) || [];
      list.push(handler);
      grouped.set(key, list);
    }
    const conflicts: ConflictReport[] = [];
    for (const [combo, hList] of grouped) {
      if (hList.length > 1) {
        conflicts.push({ combo, handlers: hList });
      }
    }
    return conflicts;
  }

  /**
   * Suggest resolutions for a specific conflict.
   * The handler with the highest priority is kept; others get a suggested alternative.
   */
  static suggestResolutions(conflict: ConflictReport): ConflictSolution[] {
    const sorted = [...conflict.handlers].sort((a, b) => b.priority - a.priority);
    const keep = sorted[0];
    const solutions: ConflictSolution[] = [];

    for (let i = 1; i < sorted.length; i++) {
      const handler = sorted[i];
      const suggestion = ShortcutConflictDetector.findAlternative(
        handler.combo,
        conflict.handlers.map((h) => h.combo),
      );
      solutions.push({
        combo: ShortcutConflictDetector.comboToString(handler.combo),
        keep,
        suggestion: suggestion ? ShortcutConflictDetector.comboToString(suggestion) : '(unavailable)',
      });
    }
    return solutions;
  }

  /**
   * Check if a new shortcut conflicts with existing ones.
   */
  static checkConflict(newHandler: ShortcutHandler, existing: ShortcutHandler[]): ShortcutHandler | null {
    const newKey = ShortcutConflictDetector.comboToString(newHandler.combo);
    for (const handler of existing) {
      if (ShortcutConflictDetector.comboToString(handler.combo) === newKey) {
        return handler;
      }
    }
    return null;
  }

  /**
   * Generate a human-readable summary of all conflicts.
   */
  static generateReport(handlers: ShortcutHandler[]): string {
    const conflicts = ShortcutConflictDetector.analyze(handlers);
    if (conflicts.length === 0) return '[ShortcutConflictDetector] No conflicts detected.';

    const lines: string[] = [`[ShortcutConflictDetector] ${conflicts.length} conflict(s) detected:`];
    for (const conflict of conflicts) {
      lines.push(`  - "${conflict.combo}" is bound by:`);
      for (const h of conflict.handlers) {
        lines.push(`      [${h.context}] "${h.description}" (priority: ${h.priority})`);
      }
      const solutions = ShortcutConflictDetector.suggestResolutions(conflict);
      for (const sol of solutions) {
        lines.push(`      → Suggestion: keep "${sol.keep.description}", move others to "${sol.suggestion}"`);
      }
    }
    return lines.join('\n');
  }

  // ── Private helpers ─────────────────────────────────────────────

  private static comboToString(combo: KeyCombo): string {
    const parts: string[] = [];
    if (combo.ctrl) parts.push('Ctrl');
    if (combo.meta) parts.push('Meta');
    if (combo.shift) parts.push('Shift');
    if (combo.alt) parts.push('Alt');
    parts.push(combo.key.toLowerCase());
    return parts.join('+');
  }

  private static findAlternative(combo: KeyCombo, used: KeyCombo[]): KeyCombo | null {
    const modifiers: (keyof KeyCombo)[] = ['ctrl', 'meta', 'shift', 'alt'];
    const keys = 'abcdefghijklmnopqrstuvwxyz0123456789'.split('');

    // Try adding Shift modifier
    if (!combo.shift) {
      const candidate: KeyCombo = { ...combo, shift: true };
      if (!used.some((u) => ShortcutConflictDetector.comboToString(u) === ShortcutConflictDetector.comboToString(candidate))) {
        return candidate;
      }
    }

    // Try different key with same modifiers
    for (const k of keys) {
      if (k === combo.key.toLowerCase()) continue;
      const candidate: KeyCombo = { ...combo, key: k };
      if (!used.some((u) => ShortcutConflictDetector.comboToString(u) === ShortcutConflictDetector.comboToString(candidate))) {
        return candidate;
      }
    }

    // Try different modifier combinations
    for (let i = 0; i < modifiers.length; i++) {
      const mod = modifiers[i];
      if (!combo[mod]) {
        const candidate: KeyCombo = { ...combo, [mod]: true };
        if (!used.some((u) => ShortcutConflictDetector.comboToString(u) === ShortcutConflictDetector.comboToString(candidate))) {
          return candidate;
        }
      }
    }

    return null;
  }
}
