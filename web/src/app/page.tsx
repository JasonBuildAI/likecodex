'use client';

import { useEffect, useRef, useState } from 'react';
import { ChatMessages } from '@/components/Chat';
import { DiffViewer } from '@/components/DiffViewer';
import { PermissionModal } from '@/components/PermissionModal';
import { TaskTimeline } from '@/components/TaskTimeline';
import { createTask, fetchConfig, fetchSessions, subscribeEvents } from '@/lib/api';
import { useAppStore } from '@/lib/store';

export default function Home() {
  const [input, setInput] = useState('');
  const messages = useAppStore((s) => s.messages);
  const tasks = useAppStore((s) => s.tasks);
  const planSteps = useAppStore((s) => s.planSteps);
  const sessions = useAppStore((s) => s.sessions);
  const pendingPermissions = useAppStore((s) => s.pendingPermissions);
  const activeDiff = useAppStore((s) => s.activeDiff);
  const config = useAppStore((s) => s.config);
  const isStreaming = useAppStore((s) => s.isStreaming);
  const addMessage = useAppStore((s) => s.addMessage);
  const appendToLastMessage = useAppStore((s) => s.appendToLastMessage);
  const setIsStreaming = useAppStore((s) => s.setIsStreaming);
  const setTasks = useAppStore((s) => s.setTasks);
  const updateTask = useAppStore((s) => s.updateTask);
  const setCurrentTaskId = useAppStore((s) => s.setCurrentTaskId);
  const addPendingPermission = useAppStore((s) => s.addPendingPermission);
  const removePendingPermission = useAppStore((s) => s.removePendingPermission);
  const setPlanSteps = useAppStore((s) => s.setPlanSteps);
  const updatePlanStep = useAppStore((s) => s.updatePlanStep);
  const setActiveDiff = useAppStore((s) => s.setActiveDiff);
  const setSessions = useAppStore((s) => s.setSessions);
  const setConfig = useAppStore((s) => s.setConfig);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: 'smooth' });
  }, [messages]);

  useEffect(() => {
    fetchConfig().then(setConfig);
    fetchSessions().then(setSessions);
  }, [setConfig, setSessions]);

  useEffect(() => {
    const unsubscribe = subscribeEvents({
      onMessage: addMessage,
      onAppend: appendToLastMessage,
      onTaskStarted: (task) => {
        setTasks([...useAppStore.getState().tasks, task]);
        setCurrentTaskId(task.id);
      },
      onTaskCompleted: (taskId, failed) => {
        updateTask(taskId, { status: failed ? 'failed' : 'completed' });
        setIsStreaming(false);
        fetchSessions().then(setSessions);
      },
      onStreamFinished: () => setIsStreaming(false),
      onPermission: addPendingPermission,
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
    setTasks,
    setCurrentTaskId,
    updateTask,
    setIsStreaming,
    addPendingPermission,
    setPlanSteps,
    updatePlanStep,
    setActiveDiff,
    setSessions,
  ]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isStreaming) return;

    addMessage({
      id: `user-${Date.now()}`,
      role: 'user',
      content: input,
      timestamp: Date.now(),
    });
    setIsStreaming(true);
    setPlanSteps([]);

    try {
      const task = await createTask(input);
      setTasks([...useAppStore.getState().tasks, task]);
      setCurrentTaskId(task.id);
    } catch (err) {
      addMessage({
        id: `error-${Date.now()}`,
        role: 'system',
        content: `Failed to create task: ${err instanceof Error ? err.message : String(err)}`,
        timestamp: Date.now(),
      });
      setIsStreaming(false);
    }

    setInput('');
  };

  const approvalMode = (config as { approval?: { mode?: string } })?.approval?.mode || 'auto';
  const model = (config as { llm?: { model?: string } })?.llm?.model || 'unknown';

  return (
    <main className="flex h-screen flex-col">
      <header className="border-b border-border px-6 py-4 flex items-center justify-between bg-surface">
        <h1 className="text-xl font-semibold">LikeCodex</h1>
        <div className="text-sm text-muted flex gap-4">
          <span>{model}</span>
          <span>{approvalMode}</span>
        </div>
      </header>

      <div className="flex flex-1 min-h-0">
        <aside className="w-64 border-r border-border p-4 overflow-y-auto hidden md:block">
          <TaskTimeline tasks={tasks} planSteps={planSteps} sessions={sessions} />
        </aside>

        <section className="flex-1 flex flex-col min-w-0">
          <div ref={scrollRef} className="flex-1 overflow-y-auto p-6">
            {messages.length === 0 && (
              <div className="text-center text-muted mt-20">
                <p className="text-lg">What would you like to build?</p>
                <p className="text-sm mt-2">
                  Try: create a python script that prints 1..10 and run it
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
    </main>
  );
}
