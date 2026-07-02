'use client';

import { useCallback } from 'react';
import {
  createNewSession,
  fetchSessions,
  fetchSessionEvents,
  resumeSession,
  forkSession,
  deleteSession,
} from '@/lib/api';
import { useAppStore } from '@/lib/store';

export function useFileManagement() {
  const sessions = useAppStore((s) => s.sessions);
  const currentSessionId = useAppStore((s) => s.currentSessionId);

  const setCurrentSessionId = useAppStore((s) => s.setCurrentSessionId);
  const setMessages = useAppStore((s) => s.setMessages);
  const setSessions = useAppStore((s) => s.setSessions);
  const addToast = useAppStore((s) => s.addToast);
  const setIsStreaming = useAppStore((s) => s.setIsStreaming);
  const setPlanSteps = useAppStore((s) => s.setPlanSteps);

  const refreshSessions = useCallback(async () => {
    try {
      const list = await fetchSessions();
      setSessions(list);
    } catch (err) {
      addToast({ type: 'error', message: `Failed to fetch sessions: ${err}` });
    }
  }, [setSessions, addToast]);

  const handleNewSession = useCallback(async () => {
    try {
      const result = await createNewSession();
      setCurrentSessionId(result.session_id);
      setMessages([]);
      setPlanSteps([]);
      addToast({ type: 'success', message: 'New session created' });
      await refreshSessions();
    } catch (err) {
      addToast({ type: 'error', message: `Failed to create session: ${err}` });
    }
  }, [setCurrentSessionId, setMessages, setPlanSteps, addToast, refreshSessions]);

  const handleSessionSelect = useCallback(async (sessionId: string) => {
    setCurrentSessionId(sessionId);
    setIsStreaming(false);
    setPlanSteps([]);
    try {
      const events = await fetchSessionEvents(sessionId);
      setMessages(events);
    } catch (err) {
      addToast({ type: 'error', message: `Failed to load session: ${err}` });
    }
  }, [setCurrentSessionId, setIsStreaming, setPlanSteps, setMessages, addToast]);

  const handleResumeSession = useCallback(async (sessionId: string) => {
    try {
      await resumeSession(sessionId);
      await handleSessionSelect(sessionId);
    } catch (err) {
      addToast({ type: 'error', message: `Failed to resume session: ${err}` });
    }
  }, [handleSessionSelect, addToast]);

  const handleForkSession = useCallback(async (sessionId: string, label?: string) => {
    try {
      const result = await forkSession(sessionId, label);
      setCurrentSessionId(result.session_id);
      setMessages([]);
      setPlanSteps([]);
      addToast({ type: 'success', message: `Session forked: ${result.session_id.slice(0, 8)}` });
      await refreshSessions();
    } catch (err) {
      addToast({ type: 'error', message: `Failed to fork session: ${err}` });
    }
  }, [setCurrentSessionId, setMessages, setPlanSteps, addToast, refreshSessions]);

  const handleDeleteSession = useCallback(async (sessionId: string) => {
    try {
      await deleteSession(sessionId);
      if (currentSessionId === sessionId) {
        setCurrentSessionId(null);
        setMessages([]);
        setPlanSteps([]);
      }
      addToast({ type: 'success', message: 'Session deleted' });
      await refreshSessions();
    } catch (err) {
      addToast({ type: 'error', message: `Failed to delete session: ${err}` });
    }
  }, [currentSessionId, setCurrentSessionId, setMessages, setPlanSteps, addToast, refreshSessions]);

  return {
    sessions,
    currentSessionId,
    refreshSessions,
    handleNewSession,
    handleSessionSelect,
    handleResumeSession,
    handleForkSession,
    handleDeleteSession,
  };
}
