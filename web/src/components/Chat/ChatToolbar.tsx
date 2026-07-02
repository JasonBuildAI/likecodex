'use client';

import React from 'react';
import { motion } from 'framer-motion';
import { useAppStore } from '@/lib/store';
import { ModelSelector } from '@/components/InputArea/ModelSelector';
import { ShortcutHelpPanel } from '@/components/ShortcutHelp';

interface ChatToolbarProps {
  currentSessionId: string | null;
  cacheLabel: string;
  onOpenSettings: () => void;
}

export const ChatToolbar: React.FC<ChatToolbarProps> = ({
  currentSessionId,
  cacheLabel,
  onOpenSettings,
}) => {
  return (
    <div className="flex items-center justify-between px-4 py-2 border-b border-border bg-surface/50 shrink-0">
      {/* Left side: Workspace & location */}
      <div className="flex items-center gap-2">
        {/* Workspace selector */}
        <motion.button
          whileHover={{ scale: 1.02 }}
          whileTap={{ scale: 0.98 }}
          className="flex items-center gap-1.5 text-xs text-muted hover:text-foreground transition-colors px-2 py-1 rounded hover:bg-accent/10"
        >
          <span>{currentSessionId ? 'likecodex' : 'New Agent'}</span>
          <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </motion.button>

        {/* Local/Remote indicator */}
        <motion.button
          whileHover={{ scale: 1.02 }}
          whileTap={{ scale: 0.98 }}
          className="flex items-center gap-1.5 text-xs text-muted hover:text-foreground transition-colors px-2 py-1 rounded hover:bg-accent/10"
        >
          <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
          </svg>
          <span>Local</span>
          <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
          </svg>
        </motion.button>

        {/* Divider */}
        <span className="text-border">|</span>

        {/* Model selector */}
        <ModelSelector />
      </div>

      {/* Right side: Indicators & settings */}
      <div className="flex items-center gap-1.5">
        {/* Cache indicator */}
        <span className="flex items-center gap-1 text-[10px] text-muted/60" title="Cache hit rate">
          <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
          </svg>
          {cacheLabel}
        </span>

        {/* Keyboard shortcuts help */}
        <ShortcutHelpPanel />

        {/* Settings button */}
        <motion.button
          whileHover={{ scale: 1.05 }}
          whileTap={{ scale: 0.95 }}
          onClick={onOpenSettings}
          className="p-1.5 rounded hover:bg-accent/10 text-muted hover:text-foreground transition-colors"
          title="Settings (Ctrl+,)"
        >
          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
          </svg>
        </motion.button>
      </div>
    </div>
  );
};

export default ChatToolbar;
