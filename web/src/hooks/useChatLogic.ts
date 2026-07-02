'use client';

import { useCallback, useRef } from 'react';
import { streamChat, fetchSessions } from '@/lib/api';
import { useAppStore } from '@/lib/store';

export function useChatLogic() {
  const abortRef = useRef<AbortController | null>(null);
  const isStreaming = useAppStore((s) => s.isStreaming);
  const currentSessionId = useAppStore((s) => s.currentSessionId);
  const agentMode = useAppStore((s) => s.agentMode);
  const selectedSkill = useAppStore((s) => s.skillDetail);

  const addMessage = useAppStore((s) => s.addMessage);
  const appendToLastMessage = useAppStore((s) => s.appendToLastMessage);
  const upsertToolDispatch = useAppStore((s) => s.upsertToolDispatch);
  const setIsStreaming = useAppStore((s) => s.setIsStreaming);
  const setTasks = useAppStore((s) => s.setTasks);
  const updateTask = useAppStore((s) => s.updateTask);
  const setCurrentTaskId = useAppStore((s) => s.setCurrentTaskId);
  const setSessions = useAppStore((s) => s.setSessions);
  const addPendingPermission = useAppStore((s) => s.addPendingPermission);
  const addPendingAsk = useAppStore((s) => s.addPendingAsk);
  const removePendingAsk = useAppStore((s) => s.removePendingAsk);
  const setPlanMode = useAppStore((s) => s.setPlanMode);
  const setPlanSteps = useAppStore((s) => s.setPlanSteps);
  const updatePlanStep = useAppStore((s) => s.updatePlanStep);
  const addToast = useAppStore((s) => s.addToast);
  const setCurrentSessionId = useAppStore((s) => s.setCurrentSessionId);

  const runPrompt = useCallback(async (prompt: string) => {
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

    const { openFiles, activeFilePath } = useAppStore.getState();
    const activeFiles = openFiles
      .filter((f) => f.path === activeFilePath || f.modified)
      .map((f) => f.path)
      .slice(0, 5);

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
        abortRef.current.signal,
        agentMode,
        activeFiles,
        selectedSkill?.name
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
    setPlanMode, updatePlanStep, addToast, agentMode, selectedSkill,
  ]);

  const cancelPrompt = useCallback(() => {
    abortRef.current?.abort();
    setIsStreaming(false);
  }, [setIsStreaming]);

  return { runPrompt, cancelPrompt, abortRef };
}
