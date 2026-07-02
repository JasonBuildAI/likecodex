/**
 * Hook unit tests
 *
 * Tests usePageLogic / useFileManagement / useAgentInteraction / useChatCore.
 */
import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act } from '@testing-library/react';
import React from 'react';

// ── Mocks ──────────────────────────────────────────────────────────────

vi.mock('@/lib/api', () => ({
  fetchSessions: vi.fn().mockResolvedValue([]),
  createNewSession: vi.fn().mockResolvedValue({ session_id: 'new-session-1' }),
  fetchSessionEvents: vi.fn().mockResolvedValue([]),
  resumeSession: vi.fn().mockResolvedValue(undefined),
  forkSession: vi.fn().mockResolvedValue({ session_id: 'forked-session-1' }),
  deleteSession: vi.fn().mockResolvedValue(undefined),
  streamChat: vi.fn(),
  subscribeEvents: vi.fn().mockReturnValue(() => {}),
}));

// ══════════════════════════════════════════════════════════════════════
// 1. usePageLogic
// ══════════════════════════════════════════════════════════════════════

describe('usePageLogic', () => {
  it('returns default state', async () => {
    const { usePageLogic } = await import('@/hooks/usePageLogic');
    const { result } = renderHook(() => usePageLogic());

    expect(result.current.chatOpen).toBe(true);
    expect(result.current.diffOpen).toBe(false);
    expect(result.current.terminalOpen).toBe(false);
    expect(result.current.leftPanel).toBe('files');
    expect(result.current.debugOpen).toBe(false);
    expect(result.current.ideSettingsOpen).toBe(false);
  });

  it('toggles chat', async () => {
    const { usePageLogic } = await import('@/hooks/usePageLogic');
    const { result } = renderHook(() => usePageLogic());

    act(() => result.current.toggleChat());
    expect(result.current.chatOpen).toBe(false);

    act(() => result.current.toggleChat());
    expect(result.current.chatOpen).toBe(true);
  });

  it('sets chat open explicitly', async () => {
    const { usePageLogic } = await import('@/hooks/usePageLogic');
    const { result } = renderHook(() => usePageLogic());

    act(() => result.current.setChatOpen(false));
    expect(result.current.chatOpen).toBe(false);

    act(() => result.current.setChatOpen(true));
    expect(result.current.chatOpen).toBe(true);
  });

  it('toggles diff', async () => {
    const { usePageLogic } = await import('@/hooks/usePageLogic');
    const { result } = renderHook(() => usePageLogic());

    act(() => result.current.toggleDiff());
    expect(result.current.diffOpen).toBe(true);
  });

  it('sets diff open explicitly', async () => {
    const { usePageLogic } = await import('@/hooks/usePageLogic');
    const { result } = renderHook(() => usePageLogic());

    act(() => result.current.setDiffOpen(true));
    expect(result.current.diffOpen).toBe(true);
  });

  it('toggles terminal', async () => {
    const { usePageLogic } = await import('@/hooks/usePageLogic');
    const { result } = renderHook(() => usePageLogic());

    act(() => result.current.toggleTerminal());
    expect(result.current.terminalOpen).toBe(true);
  });

  it('sets terminal open explicitly', async () => {
    const { usePageLogic } = await import('@/hooks/usePageLogic');
    const { result } = renderHook(() => usePageLogic());

    act(() => result.current.setTerminalOpen(true));
    expect(result.current.terminalOpen).toBe(true);

    act(() => result.current.setTerminalOpen(false));
    expect(result.current.terminalOpen).toBe(false);
  });

  it('sets left panel (toggles if same)', async () => {
    const { usePageLogic } = await import('@/hooks/usePageLogic');
    const { result } = renderHook(() => usePageLogic());

    act(() => result.current.setLeftPanel('agents'));
    expect(result.current.leftPanel).toBe('agents');

    act(() => result.current.setLeftPanel('agents'));
    expect(result.current.leftPanel).toBeNull();
  });

  it('sets debug open', async () => {
    const { usePageLogic } = await import('@/hooks/usePageLogic');
    const { result } = renderHook(() => usePageLogic());

    act(() => result.current.setDebugOpen(true));
    expect(result.current.debugOpen).toBe(true);

    act(() => result.current.setDebugOpen(false));
    expect(result.current.debugOpen).toBe(false);
  });

  it('sets IDE settings open', async () => {
    const { usePageLogic } = await import('@/hooks/usePageLogic');
    const { result } = renderHook(() => usePageLogic());

    act(() => result.current.setIdeSettingsOpen(true));
    expect(result.current.ideSettingsOpen).toBe(true);

    act(() => result.current.setIdeSettingsOpen(false));
    expect(result.current.ideSettingsOpen).toBe(false);
  });
});

// ══════════════════════════════════════════════════════════════════════
// 2. useAgentInteraction
// ══════════════════════════════════════════════════════════════════════

describe('useAgentInteraction', () => {
  beforeEach(() => {
    // Reset store state
    const { useAppStore } = require('@/lib/store');
    useAppStore.setState({
      isStreaming: false,
      skills: [],
      agentMode: 'agent',
    });
  });

  it('returns default state', async () => {
    const { useAgentInteraction } = await import('@/hooks/useAgentInteraction');
    const { result } = renderHook(() => useAgentInteraction());

    expect(result.current.input).toBe('');
    expect(result.current.inputHistory).toEqual([]);
    expect(result.current.historyIndex).toBe(-1);
    expect(result.current.showSkillAutocomplete).toBe(false);
    expect(result.current.selectedSkill).toBeNull();
    expect(result.current.showMentions).toBe(false);
  });

  it('submits prompt and updates history', async () => {
    const { useAgentInteraction } = await import('@/hooks/useAgentInteraction');
    const { result } = renderHook(() => useAgentInteraction());
    const onSubmit = vi.fn();

    act(() => {
      result.current.setInput('test prompt');
    });

    act(() => {
      result.current.submitPrompt('test prompt', onSubmit);
    });

    expect(onSubmit).toHaveBeenCalledWith('test prompt', undefined);
    expect(result.current.input).toBe('');
    expect(result.current.inputHistory).toEqual(['test prompt']);
  });

  it('does not submit empty prompt', async () => {
    const { useAgentInteraction } = await import('@/hooks/useAgentInteraction');
    const { result } = renderHook(() => useAgentInteraction());
    const onSubmit = vi.fn();

    act(() => {
      result.current.submitPrompt('', onSubmit);
    });

    expect(onSubmit).not.toHaveBeenCalled();
  });

  it('does not submit when streaming', async () => {
    const { useAppStore } = require('@/lib/store');
    useAppStore.setState({ isStreaming: true });

    const { useAgentInteraction } = await import('@/hooks/useAgentInteraction');
    const { result } = renderHook(() => useAgentInteraction());
    const onSubmit = vi.fn();

    act(() => {
      result.current.submitPrompt('hello', onSubmit);
    });

    expect(onSubmit).not.toHaveBeenCalled();
  });

  it('inserts skill tag at cursor position', async () => {
    const { useAgentInteraction } = await import('@/hooks/useAgentInteraction');
    const { result } = renderHook(() => useAgentInteraction());

    act(() => {
      result.current.setInput('run /');
    });

    const skill = { name: 'test-skill', description: 'A test skill' };

    act(() => {
      result.current.insertSkillTag(skill as any);
    });

    expect(result.current.input).toBe('run /test-skill ');
    expect(result.current.selectedSkill?.name).toBe('test-skill');
    expect(result.current.showSkillAutocomplete).toBe(false);
  });

  it('handles mention selection', async () => {
    const { useAgentInteraction } = await import('@/hooks/useAgentInteraction');
    const { result } = renderHook(() => useAgentInteraction());

    act(() => {
      result.current.setInput('hello @user');
    });

    const mention = { id: 'file-1', label: 'File1', type: 'file' };

    act(() => {
      result.current.handleMentionSelect(mention as any);
    });

    expect(result.current.input).toContain('@[File1](file-1)');
    expect(result.current.showMentions).toBe(false);
  });
});

// ══════════════════════════════════════════════════════════════════════
// 3. useChatCore (basic smoke tests)
// ══════════════════════════════════════════════════════════════════════

describe('useChatCore', () => {
  beforeEach(() => {
    const { useAppStore } = require('@/lib/store');
    useAppStore.setState({
      isStreaming: false,
      currentSessionId: null,
      agentMode: 'agent',
      messages: [],
      tasks: [],
      planSteps: [],
      openFiles: [],
      activeFilePath: null,
    });
  });

  it('returns expected API shape', async () => {
    const { useChatCore } = await import('@/hooks/useChatCore');
    const { result } = renderHook(() => useChatCore());

    expect(result.current).toHaveProperty('runPrompt');
    expect(result.current).toHaveProperty('cancelPrompt');
    expect(result.current).toHaveProperty('isStreaming');
    expect(result.current).toHaveProperty('subscribe');
    expect(typeof result.current.runPrompt).toBe('function');
    expect(typeof result.current.cancelPrompt).toBe('function');
    expect(typeof result.current.subscribe).toBe('function');
  });

  it('subscribe returns cleanup function', async () => {
    const { useChatCore } = await import('@/hooks/useChatCore');
    const { result } = renderHook(() => useChatCore());

    const cleanup = result.current.subscribe();
    expect(typeof cleanup).toBe('function');
    cleanup();
  });

  it('cancelPrompt aborts and resets streaming state', async () => {
    const { useAppStore } = require('@/lib/store');
    useAppStore.setState({ isStreaming: true });

    const { useChatCore } = await import('@/hooks/useChatCore');
    const { result } = renderHook(() => useChatCore());

    act(() => {
      result.current.cancelPrompt();
    });

    expect(useAppStore.getState().isStreaming).toBe(false);
  });
});
