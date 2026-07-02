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
  const toggleDiff = useCallback(() => setState(s => ({...s, diffOpen: !s.diffOpen})), []);
  const toggleTerminal = useCallback(() => setState(s => ({...s, terminalOpen: !s.terminalOpen})), []);
  const setLeftPanel = useCallback((panel: LeftPanel) => setState(s => ({...s, leftPanel: s.leftPanel === panel ? null : panel})), []);

  return { ...state, toggleChat, toggleDiff, toggleTerminal, setLeftPanel };
}
