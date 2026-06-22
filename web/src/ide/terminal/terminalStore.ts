/**
 * Terminal Store — Zustand state for the AI-powered terminal.
 */

import { create } from 'zustand';

export interface TerminalLine {
  type: 'command' | 'output' | 'error' | 'system' | 'input';
  content: string;
  timestamp: number;
}

export interface TerminalSession {
  id: string;
  name: string;
  cwd: string;
  lines: TerminalLine[];
  isRunning: boolean;
  history: string[];
  historyIndex: number;
}

interface TerminalState {
  sessions: TerminalSession[];
  activeSessionId: string | null;
  showAIInput: boolean;
  isExecuting: boolean;

  createSession: () => string;
  closeSession: (id: string) => void;
  setActiveSession: (id: string) => void;
  executeCommand: (command: string) => Promise<void>;
  toggleAIInput: () => void;
  suggestCommand: (description: string) => Promise<string>;
  diagnoseError: (command: string, error: string) => Promise<string>;
}

export const useTerminalStore = create<TerminalState>((set, get) => ({
  sessions: [],
  activeSessionId: null,
  showAIInput: false,
  isExecuting: false,

  createSession: () => {
    const id = `term-${Date.now()}`;
    const session: TerminalSession = {
      id,
      name: `Terminal ${get().sessions.length + 1}`,
      cwd: '.',
      lines: [{
        type: 'system',
        content: 'Terminal ready. Type commands below.',
        timestamp: Date.now(),
      }],
      isRunning: false,
      history: [],
      historyIndex: -1,
    };
    set((state) => ({
      sessions: [...state.sessions, session],
      activeSessionId: id,
    }));
    return id;
  },

  closeSession: (id) => {
    set((state) => ({
      sessions: state.sessions.filter((s) => s.id !== id),
      activeSessionId: state.activeSessionId === id
        ? state.sessions[0]?.id || null
        : state.activeSessionId,
    }));
    // Notify backend
    fetch('/api/ide/terminal/close', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ sessionId: id }),
    }).catch(() => {});
  },

  setActiveSession: (id) => set({ activeSessionId: id }),

  executeCommand: async (command) => {
    const { activeSessionId, sessions } = get();
    if (!activeSessionId) return;

    const session = sessions.find((s) => s.id === activeSessionId);
    if (!session) return;

    // Add command to output
      set((state) => ({
      sessions: state.sessions.map((s) =>
        s.id === activeSessionId
          ? {
              ...s,
              isRunning: true,
              history: [command, ...s.history].slice(0, 100),
              lines: [
                ...s.lines,
                { type: 'input' as const, content: command, timestamp: Date.now() },
              ],
            }
          : s
      ),
      isExecuting: true,
    }));

    try {
      // Use streaming endpoint
      const resp = await fetch('/api/ide/terminal/stream', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ sessionId: activeSessionId, command }),
      });

      if (!resp.ok || !resp.body) {
        // Fallback to non-streaming
        const fallbackResp = await fetch('/api/ide/terminal/execute', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ sessionId: activeSessionId, command }),
        });
        const result = await fallbackResp.json();
        const lines: TerminalLine[] = [];
        if (result.output) lines.push({ type: 'output', content: result.output, timestamp: Date.now() });
        if (result.error) lines.push({ type: 'error', content: result.error, timestamp: Date.now() });
        lines.push({ type: 'system', content: `[Exit: ${result.exitCode}]`, timestamp: Date.now() });

        set((state) => ({
          sessions: state.sessions.map((s) =>
            s.id === activeSessionId
              ? { ...s, lines: [...s.lines, ...lines], isRunning: false, cwd: result.cwd || s.cwd }
              : s
          ),
          isExecuting: false,
        }));
        return;
      }

      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let accumulatedOutput = '';
      let accumulatedError = '';
      let exitCode = 0;

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value, { stream: true });
        for (const line of chunk.split('\n')) {
          if (!line.startsWith('data: ')) continue;
          const dataStr = line.slice(6).trim();
          if (dataStr === '[DONE]') continue;

          try {
            const data = JSON.parse(dataStr);
            if (data.type === 'output') {
              accumulatedOutput += data.content;
            } else if (data.type === 'error') {
              accumulatedError += data.content;
            } else if (data.type === 'done') {
              exitCode = data.exitCode || 0;
            }
          } catch {
            // Ignore parse errors
          }
        }
      }

      // Add all output at once
      const newLines: TerminalLine[] = [];
      if (accumulatedOutput) {
        newLines.push({ type: 'output', content: accumulatedOutput, timestamp: Date.now() });
      }
      if (accumulatedError) {
        newLines.push({ type: 'error', content: accumulatedError, timestamp: Date.now() });
      }
      newLines.push({ type: 'system', content: `[Exit: ${exitCode}]`, timestamp: Date.now() });

      set((state) => ({
        sessions: state.sessions.map((s) =>
          s.id === activeSessionId
            ? { ...s, lines: [...s.lines, ...newLines], isRunning: false }
            : s
        ),
        isExecuting: false,
      }));

      // Auto-diagnose if command failed
      if (exitCode !== 0 && accumulatedError) {
        const diagnosis = await get().diagnoseError(command, accumulatedError);
        if (diagnosis) {
          set((state) => ({
            sessions: state.sessions.map((s) =>
              s.id === activeSessionId
                ? {
                    ...s,
                    lines: [
                      ...s.lines,
                      { type: 'system' as const, content: `💡 AI 诊断: ${diagnosis}`, timestamp: Date.now() },
                    ],
                  }
                : s
            ),
          }));
        }
      }
    } catch (err) {
      set((state) => ({
        sessions: state.sessions.map((s) =>
          s.id === activeSessionId
            ? {
                ...s,
                lines: [
                  ...s.lines,
                  { type: 'error' as const, content: `Error: ${err}`, timestamp: Date.now() },
                ],
                isRunning: false,
              }
            : s
        ),
        isExecuting: false,
      }));
    }
  },

  toggleAIInput: () => set((s) => ({ showAIInput: !s.showAIInput })),

  suggestCommand: async (description) => {
    try {
      const resp = await fetch('/api/ide/terminal/suggest', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ description }),
      });
      if (!resp.ok) return '';
      const data = await resp.json();
      return data.command || '';
    } catch {
      return '';
    }
  },

  diagnoseError: async (command, error) => {
    try {
      const resp = await fetch('/api/ide/terminal/diagnose', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ command, error }),
      });
      if (!resp.ok) return '';
      const data = await resp.json();
      return data.diagnosis || '';
    } catch {
      return '';
    }
  },
}));
