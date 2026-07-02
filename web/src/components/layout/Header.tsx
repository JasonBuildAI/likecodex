'use client';

import { useAppStore } from '@/lib/store';

interface HeaderProps {
  leftPanel: string;
  setLeftPanel: (panel: 'files' | 'agents' | 'sessions' | 'search' | 'git' | 'tests' | 'skills') => void;
  chatOpen: boolean;
  setChatOpen: (open: boolean) => void;
  terminalOpen: boolean;
  setTerminalOpen: (open: boolean) => void;
  debugOpen: boolean;
  setDebugOpen: (open: boolean) => void;
  setIdeSettingsOpen: (open: boolean) => void;
  runPrompt: (prompt: string) => Promise<void>;
}

export function Header({
  leftPanel,
  setLeftPanel,
  chatOpen,
  setChatOpen,
  terminalOpen,
  setTerminalOpen,
  debugOpen,
  setDebugOpen,
  setIdeSettingsOpen,
  runPrompt,
}: HeaderProps) {
  const planModeActive = useAppStore((s) => s.planModeActive);
  const collaborationMode = useAppStore((s) => s.collaborationMode);
  const setCollaborationMode = useAppStore((s) => s.setCollaborationMode);
  const cacheHitRate = useAppStore((s) => s.cacheHitRate);

  const cacheLabel = cacheHitRate !== null ? `${Math.round(cacheHitRate * 100)}%` : '--';

  return (
    <header className="border-b border-border px-3 py-1.5 flex items-center justify-between bg-surface shrink-0">
      <div className="flex items-center gap-2">
        <button
          onClick={() => useAppStore.getState().toggleSidebar()}
          className="p-1 rounded hover:bg-accent/10 transition-colors"
          title="Toggle sidebar (Ctrl+B)"
        >
          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
          </svg>
        </button>
        <h1 className="text-sm font-semibold">LikeCodex</h1>
      </div>
      <div className="flex items-center gap-1.5 text-xs text-muted">
        <div className="flex gap-0.5 mr-2">
          {(['files', 'agents', 'sessions', 'search', 'git', 'tests', 'skills'] as const).map((tab) => (
            <button
              key={tab}
              onClick={() => setLeftPanel(tab)}
              className={`px-2 py-0.5 rounded text-[10px] transition-colors ${leftPanel === tab ? 'bg-primary/20 text-primary' : 'hover:bg-accent/10'}`}
            >
              {tab === 'files' ? 'Files' : tab === 'agents' ? 'Agents' : tab === 'sessions' ? 'History' : tab === 'search' ? 'Search' : tab === 'git' ? 'Git' : tab === 'tests' ? 'Tests' : 'Skills'}
            </button>
          ))}
        </div>
        <span className="text-border mx-0.5">|</span>
        {planModeActive ? (
          <span className="px-2 py-0.5 rounded bg-amber-500/20 text-amber-200 text-[10px] font-medium">PLAN</span>
        ) : null}
        <select
          className="bg-transparent border border-border rounded px-1.5 py-0.5 text-[10px]"
          value={collaborationMode}
          onChange={(e) => {
            const mode = e.target.value as 'normal' | 'plan' | 'goal';
            setCollaborationMode(mode);
            if (mode === 'plan') runPrompt('/plan');
            if (mode === 'goal') runPrompt('/goal Continue autonomously on the active task');
            if (mode === 'normal') runPrompt('/exit_plan');
          }}
        >
          <option value="normal">normal</option>
          <option value="plan">plan</option>
          <option value="goal">goal</option>
        </select>
        <button onClick={() => setChatOpen(!chatOpen)}
          className={`px-1.5 py-0.5 rounded border text-[10px] transition-colors ${chatOpen ? 'border-primary text-primary' : 'border-border'}`}>Chat</button>
        <button onClick={() => setTerminalOpen(!terminalOpen)}
          className={`px-1.5 py-0.5 rounded border text-[10px] transition-colors ${terminalOpen ? 'border-primary text-primary' : 'border-border'}`}>Terminal</button>
        <button onClick={() => setDebugOpen(!debugOpen)}
          className={`px-1.5 py-0.5 rounded border text-[10px] transition-colors ${debugOpen ? 'border-primary text-primary' : 'border-border'}`}>Debug</button>
        <button onClick={() => useAppStore.getState().setCommandPaletteOpen(true)}
          className="px-1.5 py-0.5 rounded border border-border text-[10px] hover:bg-accent/10 transition-colors">Cmd</button>
        <span className="text-border mx-0.5">|</span>
        <span className="flex items-center gap-1 text-[10px]" title="Cache hit rate">
          <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
          </svg>
          {cacheLabel}
        </span>
      </div>
    </header>
  );
}
