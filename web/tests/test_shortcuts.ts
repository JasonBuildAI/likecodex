/**
 * Shortcut registry & conflict detector tests.
 *
 * Tests ShortcutRegistry / ShortcutConflictDetector (pure classes, no DOM needed).
 */
import { describe, it, expect, beforeEach, vi } from 'vitest';

// ── Test imports ───────────────────────────────────────────────────────

let ShortcutRegistry: typeof import('@/lib/keyboard/ShortcutRegistry').ShortcutRegistry;
let ShortcutConflictDetector: typeof import('@/lib/keyboard/ShortcutConflictDetector').ShortcutConflictDetector;
let globalShortcutRegistry: import('@/lib/keyboard/ShortcutRegistry').ShortcutRegistry;

beforeEach(async () => {
  const mod = await import('@/lib/keyboard/ShortcutRegistry');
  ShortcutRegistry = mod.ShortcutRegistry;
  globalShortcutRegistry = mod.globalShortcutRegistry;

  const cdm = await import('@/lib/keyboard/ShortcutConflictDetector');
  ShortcutConflictDetector = cdm.ShortcutConflictDetector;

  // Clear global registry before each test
  globalShortcutRegistry.clear();
});

// ══════════════════════════════════════════════════════════════════════
// ShortcutRegistry
// ══════════════════════════════════════════════════════════════════════

describe('ShortcutRegistry', () => {
  it('starts empty', () => {
    const reg = new ShortcutRegistry();
    expect(reg.getAll()).toHaveLength(0);
  });

  it('registers a shortcut', () => {
    const reg = new ShortcutRegistry();
    const handler = vi.fn();
    reg.register({
      id: 'test-1',
      combo: { key: 'k', ctrl: true },
      handler,
      context: 'global',
      priority: 10,
      description: 'Test shortcut',
      enabled: true,
    });

    const all = reg.getAll();
    expect(all).toHaveLength(1);
    expect(all[0].id).toBe('test-1');
  });

  it('replaces lower-priority shortcut with same combo', () => {
    const reg = new ShortcutRegistry();
    const handler1 = vi.fn();
    const handler2 = vi.fn();

    reg.register({
      id: 'low-priority',
      combo: { key: 'k', ctrl: true },
      handler: handler1,
      context: 'global',
      priority: 5,
      description: 'Low priority',
      enabled: true,
    });

    reg.register({
      id: 'high-priority',
      combo: { key: 'k', ctrl: true },
      handler: handler2,
      context: 'global',
      priority: 10,
      description: 'High priority',
      enabled: true,
    });

    expect(reg.getAll()).toHaveLength(1);
    expect(reg.getHandler('ctrl+k')?.id).toBe('high-priority');
  });

  it('skips lower-priority shortcut when higher already registered', () => {
    const reg = new ShortcutRegistry();
    const handler1 = vi.fn();
    const handler2 = vi.fn();

    reg.register({
      id: 'high-priority',
      combo: { key: 'k', ctrl: true },
      handler: handler2,
      context: 'global',
      priority: 10,
      description: 'High priority',
      enabled: true,
    });

    // Try to register lower priority – should be skipped
    reg.register({
      id: 'low-priority',
      combo: { key: 'k', ctrl: true },
      handler: handler1,
      context: 'global',
      priority: 5,
      description: 'Low priority',
      enabled: true,
    });

    const handler = reg.getHandler('ctrl+k');
    expect(handler?.id).toBe('high-priority');
  });

  it('unregisters a shortcut by id', () => {
    const reg = new ShortcutRegistry();
    reg.register({
      id: 'test-1',
      combo: { key: 'x' },
      handler: vi.fn(),
      context: 'global',
      priority: 0,
      description: 'Test',
      enabled: true,
    });

    reg.unregister('test-1');
    expect(reg.getAll()).toHaveLength(0);
  });

  it('detects conflicts with same combo', () => {
    const reg = new ShortcutRegistry();
    reg.register({
      id: 'a',
      combo: { key: 's', ctrl: true },
      handler: vi.fn(),
      context: 'global',
      priority: 10,
      description: 'Shortcut A',
      enabled: true,
    });
    reg.register({
      id: 'b',
      combo: { key: 's', ctrl: true },
      handler: vi.fn(),
      context: 'global',
      priority: 5,
      description: 'Shortcut B',
      enabled: true,
    });

    const conflicts = reg.getConflicts();
    expect(conflicts).toHaveLength(1);
    expect(conflicts[0].combo).toBe('ctrl+s');
    expect(conflicts[0].handlers).toHaveLength(2);
  });

  it('no conflicts when all combos are unique', () => {
    const reg = new ShortcutRegistry();
    reg.register({
      id: 'a',
      combo: { key: 'a', ctrl: true },
      handler: vi.fn(),
      context: 'global',
      priority: 0,
      description: 'A',
      enabled: true,
    });
    reg.register({
      id: 'b',
      combo: { key: 'b', ctrl: true },
      handler: vi.fn(),
      context: 'global',
      priority: 0,
      description: 'B',
      enabled: true,
    });

    expect(reg.getConflicts()).toHaveLength(0);
  });

  it('start/stop binds and unbinds keydown listener', () => {
    const addSpy = vi.spyOn(window, 'addEventListener');
    const removeSpy = vi.spyOn(window, 'removeEventListener');

    const reg = new ShortcutRegistry();
    reg.register({
      id: 'test',
      combo: { key: 'x' },
      handler: vi.fn(),
      context: 'global',
      priority: 0,
      description: 'Test',
      enabled: true,
    });

    reg.start();
    expect(addSpy).toHaveBeenCalledWith('keydown', expect.any(Function));

    reg.stop();
    expect(removeSpy).toHaveBeenCalledWith('keydown', expect.any(Function));

    addSpy.mockRestore();
    removeSpy.mockRestore();
  });

  it('is idempotent on repeated start', () => {
    const addSpy = vi.spyOn(window, 'addEventListener');
    const reg = new ShortcutRegistry();

    reg.start();
    reg.start();
    reg.start();

    expect(addSpy).toHaveBeenCalledTimes(1);
    addSpy.mockRestore();
  });

  it('clears all shortcuts', () => {
    const reg = new ShortcutRegistry();
    reg.register({
      id: 'a',
      combo: { key: 'a' },
      handler: vi.fn(),
      context: 'global',
      priority: 0,
      description: 'A',
      enabled: true,
    });
    reg.register({
      id: 'b',
      combo: { key: 'b' },
      handler: vi.fn(),
      context: 'global',
      priority: 0,
      description: 'B',
      enabled: true,
    });

    reg.clear();
    expect(reg.getAll()).toHaveLength(0);
  });
});

// ══════════════════════════════════════════════════════════════════════
// ShortcutConflictDetector
// ══════════════════════════════════════════════════════════════════════

describe('ShortcutConflictDetector', () => {
  it('analyze returns conflicts for duplicate combos', () => {
    const handlers = [
      {
        id: 'a',
        combo: { key: 's', ctrl: true },
        handler: vi.fn(),
        context: 'global' as const,
        priority: 10,
        description: 'A',
        enabled: true,
      },
      {
        id: 'b',
        combo: { key: 's', ctrl: true },
        handler: vi.fn(),
        context: 'global' as const,
        priority: 5,
        description: 'B',
        enabled: true,
      },
    ];

    const conflicts = ShortcutConflictDetector.analyze(handlers);
    expect(conflicts).toHaveLength(1);
    expect(conflicts[0].combo).toBe('ctrl+s');
  });

  it('analyze returns empty for no conflicts', () => {
    const handlers = [
      {
        id: 'a',
        combo: { key: 'a', ctrl: true },
        handler: vi.fn(),
        context: 'global' as const,
        priority: 10,
        description: 'A',
        enabled: true,
      },
      {
        id: 'b',
        combo: { key: 'b', ctrl: true },
        handler: vi.fn(),
        context: 'global' as const,
        priority: 5,
        description: 'B',
        enabled: true,
      },
    ];

    expect(ShortcutConflictDetector.analyze(handlers)).toHaveLength(0);
  });

  it('suggestResolutions returns suggestions for lower-priority handlers', () => {
    const handlers = [
      {
        id: 'high',
        combo: { key: 's', ctrl: true },
        handler: vi.fn(),
        context: 'global' as const,
        priority: 10,
        description: 'High priority',
        enabled: true,
      },
      {
        id: 'low',
        combo: { key: 's', ctrl: true },
        handler: vi.fn(),
        context: 'global' as const,
        priority: 5,
        description: 'Low priority',
        enabled: true,
      },
      {
        id: 'medium',
        combo: { key: 's', ctrl: true },
        handler: vi.fn(),
        context: 'global' as const,
        priority: 7,
        description: 'Medium priority',
        enabled: true,
      },
    ];

    const conflicts = ShortcutConflictDetector.analyze(handlers);
    const solutions = ShortcutConflictDetector.suggestResolutions(conflicts[0]);

    // The highest priority handler should be kept
    expect(solutions[0].keep.id).toBe('high');
    // Each solution should have a suggestion
    solutions.forEach((s) => {
      expect(s.suggestion).toBeTruthy();
      expect(s.suggestion).not.toBe('(unavailable)');
    });
  });

  it('checkConflict returns null when no conflict', () => {
    const existing = [
      {
        id: 'a',
        combo: { key: 'a', ctrl: true },
        handler: vi.fn(),
        context: 'global' as const,
        priority: 10,
        description: 'A',
        enabled: true,
      },
    ];

    const newHandler = {
      id: 'b',
      combo: { key: 'b', ctrl: true },
      handler: vi.fn(),
      context: 'global' as const,
      priority: 5,
      description: 'B',
      enabled: true,
    };

    expect(ShortcutConflictDetector.checkConflict(newHandler, existing)).toBeNull();
  });

  it('checkConflict returns conflicting handler', () => {
    const existing = [
      {
        id: 'a',
        combo: { key: 's', ctrl: true },
        handler: vi.fn(),
        context: 'global' as const,
        priority: 10,
        description: 'A',
        enabled: true,
      },
    ];

    const newHandler = {
      id: 'b',
      combo: { key: 's', ctrl: true },
      handler: vi.fn(),
      context: 'global' as const,
      priority: 5,
      description: 'B',
      enabled: true,
    };

    const conflict = ShortcutConflictDetector.checkConflict(newHandler, existing);
    expect(conflict).not.toBeNull();
    expect(conflict?.id).toBe('a');
  });

  it('generateReport returns no-conflict message', () => {
    const report = ShortcutConflictDetector.generateReport([]);
    expect(report).toContain('No conflicts detected');
  });

  it('generateReport returns detailed conflict info', () => {
    const handlers = [
      {
        id: 'a',
        combo: { key: 'x' },
        handler: vi.fn(),
        context: 'global' as const,
        priority: 10,
        description: 'Save',
        enabled: true,
      },
      {
        id: 'b',
        combo: { key: 'x' },
        handler: vi.fn(),
        context: 'global' as const,
        priority: 5,
        description: 'Export',
        enabled: true,
      },
    ];

    const report = ShortcutConflictDetector.generateReport(handlers);
    expect(report).toContain('conflict(s) detected');
    expect(report).toContain('Save');
    expect(report).toContain('Export');
    expect(report).toContain('Suggestion');
  });
});

// ══════════════════════════════════════════════════════════════════════
// Global singleton
// ══════════════════════════════════════════════════════════════════════

describe('globalShortcutRegistry singleton', () => {
  it('is a ShortcutRegistry instance', () => {
    expect(globalShortcutRegistry).toBeInstanceOf(ShortcutRegistry);
  });

  it('can be used to register shortcuts', () => {
    globalShortcutRegistry.register({
      id: 'global-test',
      combo: { key: 'g' },
      handler: vi.fn(),
      context: 'global',
      priority: 0,
      description: 'Global test',
      enabled: true,
    });

    expect(globalShortcutRegistry.getHandler('g')).toBeDefined();
  });
});
