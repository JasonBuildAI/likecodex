'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { ChatMessages } from '@/components/Chat';
import { DiffViewer } from '@/components/DiffViewer';
import { PermissionModal } from '@/components/PermissionModal';
import { AskModal } from '@/components/AskModal';
import { CheckpointPanel } from '@/components/CheckpointPanel';
import { SetupBanner } from '@/components/SetupBanner';
import { TaskTimeline } from '@/components/TaskTimeline';
import { SettingsPanel } from '@/components/SettingsPanel';
import { CommandPalette } from '@/components/CommandPalette';
import { CodeGraphSearch } from '@/components/CodeGraphSearch';
import { SkillPanel } from '@/components/SkillPanel';
import { Sidebar } from '@/components/Sidebar';
import { StatusBar } from '@/components/StatusBar';
import {
  fetchCacheMetrics,
  fetchConfig,
  fetchDoctor,
  fetchSessionEvents,
  fetchSessions,
  streamChat,
  subscribeEvents,
  createNewSession,
} from '@/lib/api';
import { useAppStore } from '@/lib/store';

export default function Home() {
  const [input, setInput] = useState('');
  const [doctor, setDoctor] = useState<Awaited<ReturnType<typeof fetchDoctor>>>(null);
  const [sidebarView, setSidebarView] = useState<'sessions' | 'search' | 'skills'>('sessions');
  const [inputHistory, setInputHistory] = useState<string[]>([]);
  const [historyIndex, setHistoryIndex] = useState(-1);
  const abortRef = useRef<AbortController | null>(null);
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);

  const messages = useAppStore((s) => s.messages);
  const tasks = useAppStore((s) => s.tasks);
  const planSteps = useAppStore((s) => s.planSteps);
  const sessions = useAppStore((s) => s.sessions);
  const pendingPermissions = useAppStore((s) => s.pendingPermissions);
  const pendingAskRequests = useAppStore((s) => s.pendingAskRequests);
  const activeDiff = useAppStore((s) => s.activeDiff);
  const cacheHitRate = useAppStore((s) => s.cacheHitRate);
  const planModeActive = useAppStore((s) => s.planModeActive);
  const collaborationMode = useAppStore((s) => s.collaborationMode);
  const isStreaming = useAppStore((s) => s.isStreaming);
  const currentSessionId = useAppStore((s) => s.currentSessionId);
  const sidebarOpen = useAppStore((s) => s.sidebarOpen);

  const setCollaborationMode = useAppStore((s) => s.setCollaborationMode);
  const setPlanMode = useAppStore((s) => s.setPlanMode);
  const setCacheHitRate = useAppStore((s) => s.setCacheHitRate);
  const addMessage = useAppStore((s) => s.addMessage);
  const appendToLastMessage = useAppStore((s) => s.appendToLastMessage);
  const upsertToolDispatch = useAppStore((s) => s.upsertToolDispatch);
  const setIsStreaming = useAppStore((s) => s.setIsStreaming);
  const setTasks = useAppStore((s) => s.setTasks);
  const updateTask = useAppStore((s) => s.updateTask);
  const setCurrentTaskId = useAppStore((s) => s.setCurrentTaskId);
  const addPendingPermission = useAppStore((s) => s.addPendingPermission);
  const removePendingPermission = useAppStore((s) => s.removePendingPermission);
  const addPendingAsk = useAppStore((s) => s.addPendingAsk);
  const removePendingAsk = useAppStore((s) => s.removePendingAsk);
  const setPlanSteps = useAppStore((s) => s.setPlanSteps);
  const updatePlanStep = useAppStore((s) => s.updatePlanStep);
  const setActiveDiff = useAppStore((s) => s.setActiveDiff);
  const setSessions = useAppStore((s) => s.setSessions);
  const setConfig = useAppStore((s) => s.setConfig);
  const setCurrentSessionId = useAppStore((s) => s.setCurrentSessionId);
  const setMessages = useAppStore((s) => s.setMessages);
  const toggleSidebar = useAppStore((s) => s.toggleSidebar);
  const setCommandPaletteOpen = useAppStore((s) => s.setCommandPaletteOpen);
  const addToast = useAppStore((s) => s.addToast);

  // ── Initialization ──────────────────────────────────────────────────
  useEffect(() => {
    fetchConfig().then(setConfig);
    fetchSessions().then(setSessions);
    fetchDoctor().then(setDoctor);
    fetchCacheMetrics().then((metrics) => {
      const rate = metrics.recent_hit_rate ?? metrics.hit_rate;
      setCacheHitRate(typeof rate === 'number' ? rate : null);
    });
    const interval = setInterval(() => {
      fetchCacheMetrics().then((metrics) => {
        const rate = metrics.recent_hit_rate ?? metrics.hit_rate;
        setCacheHitRate(typeof rate === 'number' ? rate : null);
      });
    }, 15000);
    return () => clearInterval(interval);
  }, [setConfig, setSessions, setCacheHitRate]);

  // ── Event subscription ──────────────────────────────────────────────
  useEffect(() => {
    const unsubscribe = subscribeEvents({
      onMessage: addMessage,
      onAppend: appendToLastMessage,
      onUpsertToolDispatch: upsertToolDispatch,
      onPermission: addPendingPermission,
      onPermissionResponded: (requestId) => removePendingPermission(requestId),
      onAsk: addPendingAsk,
      onAskResponded: (requestId) => removePendingAsk(requestId),
      onPlanModeChanged: (active) => setPlanMode(active),
      onPlanStep: (step) => {
        const existing = useAppStore.getState().planSteps;
        if (existing.find((s) => s.id === step.id)) {
          updatePlanStep(step.id, step);
        } else {
          setPlanSteps([...existing, step]);
        }
      },
      onDiff: (before, after) => setActiveDiff({ before, after }),
      onError: (err) => {
        addToast({ type: 'error', message: err.message });
      },
    });
    return unsubscribe;
  }, [
    addMessage, appendToLastMessage, upsertToolDispatch,
    addPendingPermission, removePendingPermission, addPendingAsk, removePendingAsk,
    setPlanMode, setPlanSteps, updatePlanStep, setActiveDiff, addToast,
  ]);

  // ── Chat logic ──────────────────────────────────────────────────────
  const runPrompt = useCallback(async (prompt: string) => {
    if (!prompt.trim() || isStreaming) return;

    // Save to input history
    setInputHistory((prev) => [prompt, ...prev].slice(0, 50));
    setHistoryIndex(-1);

    addMessage({
      id: `user-${Date.now()}`,
      role: 'user',
      content: prompt,
      timestamp: Date.now(),
    });
    setIsStreaming(true);
    setPlanSteps([]);

    abortRef.current?.abort();
    abortRef.current = new AbortController();

    try {
      await streamChat(
        prompt,
        currentSessionId,
        {
          onMessage: addMessage,
          onAppend: appendToLastMessage,
          onUpsertToolDispatch: upsertToolDispatch,
          onTaskStarted: (task) => {
            setTasks([...useAppStore.getState().tasks, task]);
            setCurrentTaskId(task.id);
            if (!currentSessionId) setCurrentSessionId(task.id);
          },
          onTaskCompleted: (taskId, failed) => {
            updateTask(taskId, { status: failed ? 'failed' : 'completed' });
            fetchSessions().then(setSessions);
          },
          onStreamFinished: () => setIsStreaming(false),
          onPermission: addPendingPermission,
          onAsk: addPendingAsk,
          onAskResponded: (requestId) => removePendingAsk(requestId),
          onPlanModeChanged: (active) => setPlanMode(active),
          onPlanStep: (step) => {
            const existing = useAppStore.getState().planSteps;
            if (existing.find((s) => s.id === step.id)) {
              updatePlanStep(step.id, step);
            } else {
              setPlanSteps([...existing, step]);
            }
          },
        },
        abortRef.current.signal
      );
    } catch (err) {
      addMessage({
        id: `error-${Date.now()}`,
        role: 'system',
        content: `Failed: ${err instanceof Error ? err.message : String(err)}`,
        timestamp: Date.now(),
      });
      setIsStreaming(false);
      addToast({ type: 'error', message: `Failed: ${err instanceof Error ? err.message : String(err)}` });
    }
  }, [
    isStreaming, currentSessionId, setCurrentSessionId, addMessage, setIsStreaming, setPlanSteps,
    appendToLastMessage, upsertToolDispatch, setTasks, setCurrentTaskId,
    updateTask, setSessions, addPendingPermission, addPendingAsk, removePendingAsk,
    setPlanMode, updatePlanStep, addToast,
  ]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isStreaming) return;
    const prompt = input;
    setInput('');
    await runPrompt(prompt);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    // Ctrl+Enter to send
    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
      e.preventDefault();
      if (!input.trim() || isStreaming) return;
      const prompt = input;
      setInput('');
      runPrompt(prompt);
      return;
    }

    // Escape to close panels
    if (e.key === 'Escape') {
      useAppStore.getState().setCommandPaletteOpen(false);
      useAppStore.getState().setSettingsOpen(false);
      return;
    }

    // Up arrow for history
    if (e.key === 'ArrowUp' && input === '') {
      e.preventDefault();
      setHistoryIndex((prev) => {
        const next = Math.min(prev + 1, inputHistory.length - 1);
        if (inputHistory[next] !== undefined) setInput(inputHistory[next]);
        return next;
      });
      return;
    }
    if (e.key === 'ArrowDown' && historyIndex >= 0) {
      e.preventDefault();
      setHistoryIndex((prev) => {
        const next = prev - 1;
        if (next < 0) {
          setInput('');
          return -1;
        }
        setInput(inputHistory[next] || '');
        return next;
      });
    }
  };

  // ── Global keyboard shortcuts ───────────────────────────────────────
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const isInput = document.activeElement?.tagName === 'INPUT' || document.activeElement?.tagName === 'TEXTAREA';
      if (e.key === 'k' && (e.ctrlKey || e.metaKey) && !e.shiftKey) {
        e.preventDefault();
        setCommandPaletteOpen(true);
        return;
      }
      if (e.key === 'b' && (e.ctrlKey || e.metaKey)) {
        e.preventDefault();
        toggleSidebar();
        return;
      }
      if (e.key === 'n' && (e.ctrlKey || e.metaKey) && !isInput) {
        e.preventDefault();
        createNewSession().then((r) => {
          setCurrentSessionId(r.session_id);
          setMessages([]);
          addToast({ type: 'success', message: 'New session created' });
          fetchSessions().then(setSessions);
        });
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [setCommandPaletteOpen, toggleSidebar, setCurrentSessionId, setMessages, setSessions, addToast]);

  // ── Session handling ────────────────────────────────────────────────
  const handleSessionSelect = async (sessionId: string) => {
    setCurrentSessionId(sessionId);
    setIsStreaming(false);
    setPlanSteps([]);
    const events = await fetchSessionEvents(sessionId);
    setMessages(events);
  };

  const cacheLabel = cacheHitRate !== null ? `${Math.round(cacheHitRate * 100)}%` : '--';

  // ── Sidebar content ─────────────────────────────────────────────────
  const sidebarContent = (() => {
    switch (sidebarView) {
      case 'search':
        return <CodeGraphSearch />;
      case 'skills':
        return <SkillPanel />;
      default:
        return (
          <>
            <TaskTimeline
              tasks={tasks}
              planSteps={planSteps}
              sessions={sessions}
              activeSessionId={currentSessionId}
              onSessionSelect={handleSessionSelect}
            />
            <div className="mt-4">
              <CheckpointPanel />
            </div>
          </>
        );
    }
  })();

  return (
    <main className="flex h-screen flex-col">
      {/* Header */}
      <header className="border-b border-border px-4 py-3 flex items-center justify-between bg-surface shrink-0">
        <div className="flex items-center gap-3">
          <button
            onClick={toggleSidebar}
            className="p-1 rounded hover:bg-accent/10 transition-colors"
            title="Toggle sidebar (Ctrl+B)"
          >
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
            </svg>
          </button>
          <h1 className="text-base font-semibold">LikeCodex</h1>
        </div>

        <div className="flex items-center gap-2 text-xs text-muted">
          {/* Plan mode badge */}
          {planModeActive ? (
            <span className="px-2 py-0.5 rounded bg-amber-500/20 text-amber-200 text-[10px] font-medium">
              PLAN
            </span>
          ) : null}

          {/* Collaboration mode */}
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

          {/* Quick actions */}
          <button
            onClick={() => setSidebarView(sidebarView === 'search' ? 'sessions' : 'search')}
            className={`px-1.5 py-0.5 rounded border text-[10px] transition-colors ${sidebarView === 'search' ? 'border-primary text-primary' : 'border-border'}`}
            title="Search (Ctrl+Shift+F)"
          >
            Search
          </button>
          <button
            onClick={() => setCommandPaletteOpen(true)}
            className="px-1.5 py-0.5 rounded border border-border text-[10px] hover:bg-accent/10 transition-colors"
            title="Command palette (Ctrl+K)"
          >
            Cmd
          </button>

          <span className="text-border mx-0.5">|</span>
          <span className="flex items-center gap-1" title="Cache hit rate">
            <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
            </svg>
            {cacheLabel}
          </span>
        </div>
      </header>

      <SetupBanner doctor={doctor} />

      {/* Main content */}
      <div className="flex flex-1 min-h-0">
        {/* Sidebar */}
        <Sidebar>
          {/* Sidebar nav */}
          <div className="flex gap-1 mb-3 pb-2 border-b border-border">
            <button
              onClick={() => setSidebarView('sessions')}
              className={`flex-1 text-[10px] py-1 rounded transition-colors ${sidebarView === 'sessions' ? 'bg-primary/20 text-primary' : 'hover:bg-accent/10'}`}
            >
              Sessions
            </button>
            <button
              onClick={() => setSidebarView('search')}
              className={`flex-1 text-[10px] py-1 rounded transition-colors ${sidebarView === 'search' ? 'bg-primary/20 text-primary' : 'hover:bg-accent/10'}`}
            >
              Search
            </button>
            <button
              onClick={() => setSidebarView('skills')}
              className={`flex-1 text-[10px] py-1 rounded transition-colors ${sidebarView === 'skills' ? 'bg-primary/20 text-primary' : 'hover:bg-accent/10'}`}
            >
              Skills
            </button>
          </div>
          {sidebarContent}
        </Sidebar>

        {/* Chat area */}
        <section className="flex-1 flex flex-col min-w-0">
          <div ref={scrollRef} className="flex-1 overflow-y-auto p-4">
            <ChatMessages scrollRef={scrollRef} />
          </div>

          <form onSubmit={handleSubmit} className="border-t border-border p-3 bg-surface">
            <div className="max-w-4xl mx-auto flex gap-2 items-end">
              <textarea
                ref={textareaRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                onKeyDown={handleKeyDown}
                placeholder="Describe your coding task... (Ctrl+Enter to send)"
                className="flex-1 rounded-md border border-border bg-background px-4 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary resize-none min-h-[42px] max-h-[200px]"
                rows={1}
                disabled={isStreaming}
              />
              <button
                type="submit"
                disabled={isStreaming || !input.trim()}
                className="rounded-md bg-primary px-5 py-2.5 text-sm font-medium text-white hover:bg-blue-600 disabled:opacity-50 shrink-0 transition-colors"
              >
                {isStreaming ? (
                  <span className="flex items-center gap-1.5">
                    <span className="h-2 w-2 rounded-full bg-white animate-pulse" />
                    Running
                  </span>
                ) : 'Send'}
              </button>
            </div>
          </form>

          {/* Status bar */}
          <StatusBar />
        </section>

        {/* Diff panel */}
        <aside className="w-80 border-l border-border overflow-y-auto hidden lg:flex flex-col">
          <div className="flex-1 min-h-0">
            <DiffViewer before={activeDiff?.before} after={activeDiff?.after} />
          </div>
        </aside>
      </div>

      {/* Overlays */}
      <PermissionModal requests={pendingPermissions} onResponded={removePendingPermission} />
      <AskModal requests={pendingAskRequests} onResponded={removePendingAsk} />
      <SettingsPanel />
      <CommandPalette />
    </main>
  );
}
