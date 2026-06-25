'use client';

import React, { useState, useRef, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useAppStore } from '@/lib/store';
import { fadeInUp, scaleIn } from '@/lib/animations';

// ── Types ──────────────────────────────────────────────────────────────
type AgentMode = 'ask' | 'agent' | 'manual';

interface ModeConfig {
  label: string;
  description: string;
  activeClass: string;
  glowClass: string;
  icon: React.ReactNode;
}

// ── Mode Configuration ──────────────────────────────────────────────────
const MODE_CONFIG: Record<AgentMode, ModeConfig> = {
  ask: {
    label: 'Ask',
    description: 'Read-only Q&A — no code changes',
    activeClass: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30',
    glowClass: 'from-emerald-500/20',
    icon: (
      <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z" />
      </svg>
    ),
  },
  agent: {
    label: 'Agent',
    description: 'Autonomous execution with full tool access',
    activeClass: 'bg-blue-500/20 text-blue-400 border-blue-500/30',
    glowClass: 'from-blue-500/20',
    icon: (
      <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
      </svg>
    ),
  },
  manual: {
    label: 'Manual',
    description: 'Confirm each action before execution',
    activeClass: 'bg-amber-500/20 text-amber-400 border-amber-500/30',
    glowClass: 'from-amber-500/20',
    icon: (
      <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 15l-2 5L9 9l11 4-5 2zm0 0l5 5M7.188 2.239l.777 2.897M5.136 7.965l-2.898-.777M13.95 4.05l-2.122 2.122m-5.657 5.656l-2.12 2.122" />
      </svg>
    ),
  },
};

const MODE_ORDER: AgentMode[] = ['ask', 'agent', 'manual'];

// ── Component ───────────────────────────────────────────────────────────
export const ModeCapsule: React.FC = () => {
  const agentMode = useAppStore((s) => s.agentMode);
  const setAgentMode = useAppStore((s) => s.setAgentMode);

  const cycleMode = useCallback(() => {
    const idx = MODE_ORDER.indexOf(agentMode);
    const next = MODE_ORDER[(idx + 1) % MODE_ORDER.length];
    setAgentMode(next);
  }, [agentMode, setAgentMode]);

  return (
    <div className="flex items-center justify-center mb-3">
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
        className="inline-flex items-center gap-1 bg-background/80 backdrop-blur-md border border-border rounded-full px-1.5 py-1 shadow-lg"
      >
        {MODE_ORDER.map((mode) => {
          const config = MODE_CONFIG[mode];
          const isActive = agentMode === mode;

          return (
            <motion.button
              key={mode}
              type="button"
              onClick={() => setAgentMode(mode)}
              title={config.description}
              whileHover={{ scale: 1.05 }}
              whileTap={{ scale: 0.95 }}
              className={`relative flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium transition-all ${
                isActive
                  ? `${config.activeClass} shadow-md`
                  : 'text-muted hover:text-foreground hover:bg-accent/10'
              }`}
            >
              {isActive && (
                <motion.div
                  layoutId="modeGlow"
                  className={`absolute inset-0 rounded-full bg-gradient-to-r ${config.glowClass} to-transparent opacity-50`}
                  transition={{ type: 'spring', stiffness: 300, damping: 25 }}
                />
              )}
              <span className="relative z-10 flex items-center gap-1.5">
                {config.icon}
                <span>{config.label}</span>
              </span>
            </motion.button>
          );
        })}
      </motion.div>
    </div>
  );
};

export default ModeCapsule;
