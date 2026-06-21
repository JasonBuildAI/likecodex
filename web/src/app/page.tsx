'use client';

import { useEffect, useRef, useState } from 'react';
import { ChatMessages } from '@/components/Chat';
import { DiffViewer } from '@/components/DiffViewer';
import { PermissionModal } from '@/components/PermissionModal';
import { AskModal } from '@/components/AskModal';
import { CheckpointPanel } from '@/components/CheckpointPanel';
import { SetupBanner } from '@/components/SetupBanner';
import { TaskTimeline } from '@/components/TaskTimeline';
import { SettingsPanel } from '@/components/SettingsPanel';
import {
  fetchCacheMetrics,
  fetchConfig,
  fetchDoctor,
  fetchSessionEvents,
  fetchSessions,
  streamChat,
  subscribeEvents,
} from '@/lib/api';
import { useAppStore } from '@/lib/store';

export default function Home() {
  const [input, setInput] = useState('');
  const [doctor, setDoctor] = useState<Awaited<ReturnType<typeof fetchDoctor>>>(null);
  const abortRef = useRef<AbortController | null>(null);
  const messages = useAppStore((s) => s.messages);
  const tasks = useAppStore((s) => s.tasks);
  const planSteps = useAppStore((s) => s.planSteps);
  const sessions = useAppStore((s) => s.sessions);
  const pendingPermissions = useAppStore((s) => s.pendingPermissions);
  const pendingAskRequests = useAppStore((s) => s.pendingAskRequests);
  const activeDiff = useAppStore((s) => s.activeDiff);
  const config = useAppStore((s) => s.config);
  const cacheHitRate = useAppStore((s) => s.cacheHitRate);
  const planModeActive = useAppStore((s) => s.planModeActive);
  const collaborationMode = useAppStore((s) => s.collaborationMode);
  const setCollaborationMode = useAppStore((s) => s.setCollaborationMode);
  const setPlanMode = useAppStore((s) => s.setPlanMode);
  const setCacheHitRate = useAppStore((s) => s.setCacheHitRate);
  const isStreaming = useAppStore((s) => s.isStreaming);
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
  const currentSessionId = useAppStore((s) => s.currentSessionId);
  const setCurrentSessionId = useAppStore((s) => s.setCurrentSessionId);
  const setMessages = useAppStore((s) => s.setMessages);
  const selectedModel = useAppStore((s) => s.selectedModel);
  const apiKey = useAppStore((s) => s.apiKey);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' });
  }, [messages]);

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

  useEffect(() => {
    const unsubscribe = subscribeEvents({
      onMessage: addMessage,
      onAppend: appendToLastMessage,
      onUpsertToolDispatch: upsertToolDispatch,
      onPermission: addPendingPermission,
      onPermissionResponded: (requestId) => removePendingPermission(requestId),
      onAsk: addPendingAsk,
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
    });
    return unsubscribe;
  }, [
    addMessage,
    appendToLastMessage,
    upsertToolDispatch,
    addPendingPermission,
    removePendingPermission,
    addPendingAsk,
    setPlanMode,
    setPlanSteps,
    updatePlanStep,
    setActiveDiff,
  ]);

  const runPrompt = async (prompt: string) => {
    if (!prompt.trim() || isStreaming) return;

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
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isStreaming) return;
    const prompt = input;
    setInput('');
    await runPrompt(prompt);
  };

  const sendSlash = (cmd: string) => {
    void runPrompt(cmd);
  };

  const handleSessionSelect = async (sessionId: string) => {
    setCurrentSessionId(sessionId);
    setIsStreaming(false);
    setPlanSteps([]);
    const events = await fetchSessionEvents(sessionId);
    setMessages(events);
  };

  const approvalMode = (config as { approval?: { mode?: string } })?.approval?.mode || 'auto';
  const model = (config as { llm?: { model?: string } })?.llm?.model || 'deepseek-v4-flash';
  const cacheLabel =
    cacheHitRate !== null ? `${Math.round(cacheHitRate * 100)}% cache` : 'cache —';

  return (
    <main className="flex h-screen flex-col">
      <header className="border-b border-border px-6 py-4 flex items-center justify-between bg-surface">
        <h1 className="text-xl font-semibold">LikeCodex</h1>
        <div className="text-sm text-muted flex gap-4 items-center">
          {planModeActive ? (
            <span className="px-2 py-0.5 rounded bg-amber-500/20 text-amber-200 text-xs">Plan</span>
          ) : null}
          <select
            className="text-xs bg-transparent border border-border rounded px-1 py-0.5"
            value={collaborationMode}
            onChange={(e) => {
              const mode = e.target.value as 'normal' | 'plan' | 'goal';
              setCollaborationMode(mode);
              if (mode === 'plan') void runPrompt('/plan');
              if (mode === 'goal') void runPrompt('/goal Continue autonomously on the active task');
              if (mode === 'normal') void runPrompt('/exit_plan');
            }}
          >
            <option value="normal">normal</option>
            <option value="plan">plan</option>
            <option value="goal">goal</option>
          </select>
          <button
            type="button"
            className="text-xs underline"
            onClick={() => sendSlash('/plan')}
          >
            Toggle plan
          </button>
          <span>{selectedModel}</span>
          <span className={`inline-block h-2 w-2 rounded-full ${apiKey ? 'bg-green-500' : 'bg-amber-500'}`} title={apiKey ? 'API Key configured' : 'API Key not set'} />
          <span>{cacheLabel}</span>
          <span>{approvalMode}</span>
        </div>
      </header>

      <SetupBanner doctor={doctor} />

      <div className="flex flex-1 min-h-0">
        <aside className="w-64 border-r border-border p-4 overflow-y-auto hidden md:block">
          <TaskTimeline
            tasks={tasks}
            planSteps={planSteps}
            sessions={sessions}
            activeSessionId={currentSessionId}
            onSessionSelect={handleSessionSelect}
          />
          <div className="mt-6">
            <CheckpointPanel />
          </div>
        </aside>

        <section className="flex-1 flex flex-col min-w-0">
          <div ref={scrollRef} className="flex-1 overflow-y-auto p-6">
            {messages.length === 0 && (
              <div className="text-center text-muted mt-20">
                <p className="text-lg">What would you like to build?</p>
                <p className="text-sm mt-2">
                  Try: /plan then describe a refactor, or ask to fix failing tests
                </p>
              </div>
            )}
            <ChatMessages messages={messages} />
          </div>

          <form onSubmit={handleSubmit} className="border-t border-border p-4 bg-surface">
            <div className="max-w-4xl mx-auto flex gap-2">
              <input
                type="text"
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder="Describe your coding task..."
                className="flex-1 rounded-md border border-border bg-background px-4 py-3 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
              />
              <button
                type="submit"
                disabled={isStreaming || !input.trim()}
                className="rounded-md bg-primary px-6 py-3 text-sm font-medium text-white hover:bg-blue-600 disabled:opacity-50"
              >
                {isStreaming ? 'Running...' : 'Send'}
              </button>
            </div>
          </form>
        </section>

        <aside className="w-80 border-l border-border p-4 overflow-y-auto hidden lg:block">
          {activeDiff ? (
            <DiffViewer before={activeDiff.before} after={activeDiff.after} />
          ) : (
            <div className="text-sm text-muted">Diff will appear when files change.</div>
          )}
        </aside>
      </div>

      <PermissionModal
        requests={pendingPermissions}
        onResponded={removePendingPermission}
      />
      <AskModal requests={pendingAskRequests} onResponded={removePendingAsk} />
      <SettingsPanel />
    </main>
  );
}
