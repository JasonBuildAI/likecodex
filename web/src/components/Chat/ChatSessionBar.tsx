'use client';

import React, { useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useAppStore, type SessionSummary } from '@/lib/store';
import { fetchSessionEvents, fetchSessions, createNewSession } from '@/lib/api';
import i18n from '@/lib/i18n';

interface ChatSessionBarProps {
  sessions: SessionSummary[];
  currentSessionId: string | null;
  onSessionSelect: (sessionId: string) => void;
  onClose?: () => void;
}

export const ChatSessionBar: React.FC<ChatSessionBarProps> = ({
  sessions,
  currentSessionId,
  onSessionSelect,
  onClose,
}) => {
  const setMessages = useAppStore((s) => s.setMessages);
  const setSessions = useAppStore((s) => s.setSessions);
  const setCurrentSessionId = useAppStore((s) => s.setCurrentSessionId);
  const addToast = useAppStore((s) => s.addToast);
  const setIsStreaming = useAppStore((s) => s.setIsStreaming);
  const setPlanSteps = useAppStore((s) => s.setPlanSteps);

  const handleNewSession = useCallback(async () => {
    try {
      const result = await createNewSession();
      setCurrentSessionId(result.session_id);
      setMessages([]);
      setIsStreaming(false);
      setPlanSteps([]);
      addToast({ type: 'success', message: 'New session created' });
      const updated = await fetchSessions();
      setSessions(updated);
    } catch {
      addToast({ type: 'error', message: 'Failed to create session' });
    }
  }, [setCurrentSessionId, setMessages, setIsStreaming, setPlanSteps, addToast, setSessions]);

  const handleSelect = useCallback((sessionId: string) => {
    onSessionSelect(sessionId);
  }, [onSessionSelect]);

  const formatDate = (dateStr?: string) => {
    if (!dateStr) return '';
    try {
      const d = new Date(dateStr);
      return d.toLocaleDateString(undefined, {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      });
    } catch {
      return '';
    }
  };

  return (
    <div className="flex flex-col h-full bg-surface/30">
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-border shrink-0">
        <h3 className="text-xs font-semibold text-muted uppercase tracking-wider">
          {i18n.t('sidebar.explorer')}
        </h3>
        <div className="flex items-center gap-1">
          {onClose && (
            <button
              onClick={onClose}
              className="p-1 rounded hover:bg-accent/10 text-muted hover:text-foreground transition-colors"
              title={i18n.t('common.close')}
            >
              <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          )}
        </div>
      </div>

      {/* New Session Button */}
      <div className="px-2 py-2">
        <motion.button
          whileHover={{ scale: 1.02 }}
          whileTap={{ scale: 0.98 }}
          onClick={handleNewSession}
          className="w-full flex items-center justify-center gap-1.5 px-3 py-1.5 rounded-lg bg-primary/10 hover:bg-primary/20 text-primary text-xs font-medium transition-colors border border-primary/20"
        >
          <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
          </svg>
          New Session
        </motion.button>
      </div>

      {/* Session List */}
      <div className="flex-1 overflow-y-auto px-2 pb-2 space-y-0.5">
        <AnimatePresence>
          {sessions.length === 0 ? (
            <div className="flex items-center justify-center h-24">
              <p className="text-[11px] text-muted/50">{i18n.t('common.noResults')}</p>
            </div>
          ) : (
            sessions.map((session) => {
              const isActive = session.id === currentSessionId;
              const title = session.metadata?.name as string || session.id.slice(0, 8);
              return (
                <motion.button
                  key={session.id}
                  initial={{ opacity: 0, x: -10 }}
                  animate={{ opacity: 1, x: 0 }}
                  exit={{ opacity: 0, x: -10 }}
                  onClick={() => handleSelect(session.id)}
                  className={`w-full flex flex-col items-start gap-0.5 px-2.5 py-2 rounded-lg text-left transition-colors ${
                    isActive
                      ? 'bg-primary/10 border border-primary/20'
                      : 'hover:bg-accent/10 border border-transparent'
                  }`}
                >
                  <span className={`text-xs font-medium truncate w-full ${
                    isActive ? 'text-primary' : 'text-foreground'
                  }`}>
                    {title}
                  </span>
                  <span className="text-[10px] text-muted/60">
                    {formatDate(session.updated_at || session.created_at)}
                  </span>
                </motion.button>
              );
            })
          )}
        </AnimatePresence>
      </div>
    </div>
  );
};

export default ChatSessionBar;
