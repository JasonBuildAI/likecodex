'use client';
import { useState, useCallback } from 'react';

type LeftPanel = 'files' | 'agents' | 'sessions' | 'search' | 'git' | 'tests' | 'skills' | null;

interface PageState {
  chatOpen: boolean;
  diffOpen: boolean;
  terminalOpen: boolean;
  leftPanel: LeftPanel;
  debugOpen: boolean;
  ideSettingsOpen: boolean;
  composerOpen: boolean;
}

export function usePageLogic() {
  const [state, setState] = useState<PageState>({
    chatOpen: true,
    diffOpen: false,
    terminalOpen: false,
    leftPanel: 'files',
    debugOpen: false,
    ideSettingsOpen: false,
    composerOpen: false,
  });

  const toggleChat = useCallback(() => setState(s => ({...s, chatOpen: !s.chatOpen})), []);
  const setChatOpen = useCallback((open: boolean) => setState(s => ({...s, chatOpen: open})), []);
  const toggleDiff = useCallback(() => setState(s => ({...s, diffOpen: !s.diffOpen})), []);
  const setDiffOpen = useCallback((open: boolean) => setState(s => ({...s, diffOpen: open})), []);
  const toggleTerminal = useCallback(() => setState(s => ({...s, terminalOpen: !s.terminalOpen})), []);
  const setTerminalOpen = useCallback((open: boolean) => setState(s => ({...s, terminalOpen: open})), []);
  const setLeftPanel = useCallback((panel: LeftPanel) => setState(s => ({...s, leftPanel: s.leftPanel === panel ? null : panel})), []);
  const setDebugOpen = useCallback((open: boolean) => setState(s => ({...s, debugOpen: open})), []);
  const setIdeSettingsOpen = useCallback((open: boolean) => setState(s => ({...s, ideSettingsOpen: open})), []);

  return { ...state, toggleChat, setChatOpen, toggleDiff, setDiffOpen, toggleTerminal, setTerminalOpen, setLeftPanel, setDebugOpen, setIdeSettingsOpen };
}
