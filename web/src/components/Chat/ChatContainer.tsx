'use client';

import React, { useRef, useCallback, useState } from 'react';
import { motion } from 'framer-motion';
import { useAppStore } from '@/lib/store';
import { ChatToolbar } from './ChatToolbar';
import { ChatMessageList } from './ChatMessageList';
import { ChatInputPanel } from './ChatInputPanel';

interface ChatContainerProps {
  onOpenSettings?: () => void;
  cacheLabel?: string;
}

export const ChatContainer: React.FC<ChatContainerProps> = ({
  onOpenSettings,
  cacheLabel: externalCacheLabel,
}) => {
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const currentSessionId = useAppStore((s) => s.currentSessionId);
  const cacheHitRate = useAppStore((s) => s.cacheHitRate);
  const [inputHistory, setInputHistory] = useState<string[]>([]);

  const cacheLabel = externalCacheLabel ?? (
    cacheHitRate !== null ? `${(cacheHitRate * 100).toFixed(0)}%` : ''
  );

  const handleOpenSettings = useCallback(() => {
    if (onOpenSettings) {
      onOpenSettings();
    } else {
      useAppStore.getState().setSettingsOpen(true);
    }
  }, [onOpenSettings]);

  const handleSubmit = useCallback((prompt: string) => {
    // Dispatch custom event for the page-level handler to pick up
    window.dispatchEvent(
      new CustomEvent('likecodex:submit', { detail: { prompt } })
    );
  }, []);

  return (
    <motion.aside
      initial={{ opacity: 0, x: 50 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: 50 }}
      transition={{ type: 'spring', stiffness: 200, damping: 25 }}
      className="w-[480px] border-l border-border bg-surface flex flex-col shrink-0 relative"
    >
      {/* Toolbar */}
      <ChatToolbar
        currentSessionId={currentSessionId}
        cacheLabel={cacheLabel}
        onOpenSettings={handleOpenSettings}
      />

      {/* Message list with scrolling */}
      <div
        ref={scrollRef}
        className="flex-1 overflow-y-auto p-4"
      >
        <ChatMessageList scrollRef={scrollRef} />
      </div>

      {/* Input Panel */}
      <ChatInputPanel
        onSubmit={handleSubmit}
        inputHistory={inputHistory}
      />
    </motion.aside>
  );
};

export default ChatContainer;
