'use client';

import { useEffect } from 'react';
import { subscribeEvents } from '@/lib/api';
import { useAppStore } from '@/lib/store';

export function useEventSubscription() {
  const addMessage = useAppStore((s) => s.addMessage);
  const appendToLastMessage = useAppStore((s) => s.appendToLastMessage);
  const upsertToolDispatch = useAppStore((s) => s.upsertToolDispatch);
  const addPendingPermission = useAppStore((s) => s.addPendingPermission);
  const removePendingPermission = useAppStore((s) => s.removePendingPermission);
  const addPendingAsk = useAppStore((s) => s.addPendingAsk);
  const removePendingAsk = useAppStore((s) => s.removePendingAsk);
  const setPlanMode = useAppStore((s) => s.setPlanMode);
  const setPlanSteps = useAppStore((s) => s.setPlanSteps);
  const updatePlanStep = useAppStore((s) => s.updatePlanStep);
  const setActiveDiff = useAppStore((s) => s.setActiveDiff);
  const addToast = useAppStore((s) => s.addToast);

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
      onDiff: (before, after) => {
        setActiveDiff({ before, after });
      },
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
}
