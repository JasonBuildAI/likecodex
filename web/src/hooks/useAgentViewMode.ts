'use client';

import { useState, useEffect, useCallback } from 'react';
import type { AgentViewMode } from '@/lib/store';

// ── Types ──────────────────────────────────────────────────────────────
interface AgentViewModeState {
  /** Current active view mode */
  mode: AgentViewMode;
  /** Whether the view mode is locked by user preference */
  isLocked: boolean;
  /** Manually set and lock a specific view mode */
  setMode: (mode: AgentViewMode) => void;
  /** Unlock auto-switching based on screen size */
  unlock: () => void;
  /** Toggle lock on current mode */
  toggleLock: () => void;
}

// ── Constants ──────────────────────────────────────────────────────────
const STORAGE_KEY = 'likecodex_agent_view_mode';
const LOCK_KEY = 'likecodex_agent_view_locked';

/** Breakpoints for automatic view switching */
const BREAKPOINTS = {
  chat: 640,   // sm: below → chat
  agent: 1024, // lg: below → agent, above → mixed
} as const;

// ── Helpers ────────────────────────────────────────────────────────────
function getStoredMode(): AgentViewMode | null {
  if (typeof window === 'undefined') return null;
  const stored = localStorage.getItem(STORAGE_KEY);
  if (stored === 'chat' || stored === 'agent' || stored === 'mixed') {
    return stored;
  }
  return null;
}

function getStoredLock(): boolean {
  if (typeof window === 'undefined') return false;
  return localStorage.getItem(LOCK_KEY) === 'true';
}

function getModeForWidth(width: number): AgentViewMode {
  if (width < BREAKPOINTS.chat) return 'chat';
  if (width < BREAKPOINTS.agent) return 'agent';
  return 'mixed';
}

// ── Hook ───────────────────────────────────────────────────────────────
/**
 * Hook to manage Agent view mode with automatic screen-size detection
 * and persistent user preferences.
 *
 * Supports three modes:
 * - 'chat': Pure chat view
 * - 'agent': Pure agent activity view
 * - 'mixed': Chat + agent activity combined (default on large screens)
 *
 * - Auto-switches based on window width when unlocked
 * - Persists manual selection to localStorage
 * - Supports locking a preferred mode
 */
export function useAgentViewMode(): AgentViewModeState {
  const [mode, setModeState] = useState<AgentViewMode>(() => {
    const stored = getStoredMode();
    const locked = getStoredLock();
    if (locked && stored) return stored;
    if (typeof window !== 'undefined') return getModeForWidth(window.innerWidth);
    return 'mixed';
  });

  const [isLocked, setIsLocked] = useState<boolean>(() => getStoredLock());

  // Listen for window resize when not locked
  useEffect(() => {
    if (isLocked) return;

    const handleResize = () => {
      setModeState(getModeForWidth(window.innerWidth));
    };

    window.addEventListener('resize', handleResize);
    // Set initial value on mount
    handleResize();

    return () => window.removeEventListener('resize', handleResize);
  }, [isLocked]);

  const setMode = useCallback((newMode: AgentViewMode) => {
    setModeState(newMode);
    setIsLocked(true);
    if (typeof window !== 'undefined') {
      localStorage.setItem(STORAGE_KEY, newMode);
      localStorage.setItem(LOCK_KEY, 'true');
    }
  }, []);

  const unlock = useCallback(() => {
    setIsLocked(false);
    if (typeof window !== 'undefined') {
      localStorage.setItem(LOCK_KEY, 'false');
      setModeState(getModeForWidth(window.innerWidth));
    }
  }, []);

  const toggleLock = useCallback(() => {
    if (isLocked) {
      unlock();
    } else {
      if (typeof window !== 'undefined') {
        localStorage.setItem(STORAGE_KEY, mode);
        localStorage.setItem(LOCK_KEY, 'true');
      }
      setIsLocked(true);
    }
  }, [isLocked, mode, unlock]);

  return { mode, isLocked, setMode, unlock, toggleLock };
}
'use client';

import { useState, useEffect, useCallback } from 'react';

// ── Types ──────────────────────────────────────────────────────────────
export type AgentViewMode = 'full' | 'compact' | 'embedded';

interface AgentViewModeState {
  /** Current active view mode */
  mode: AgentViewMode;
  /** Whether the view mode is locked by user preference */
  isLocked: boolean;
  /** Manually set and lock a specific view mode */
  setMode: (mode: AgentViewMode) => void;
  /** Unlock auto-switching based on screen size */
  unlock: () => void;
  /** Toggle lock on current mode */
  toggleLock: () => void;
}

// ── Constants ──────────────────────────────────────────────────────────
const STORAGE_KEY = 'likecodex_agent_view_mode';
const LOCK_KEY = 'likecodex_agent_view_locked';

/** Breakpoints for automatic view switching */
const BREAKPOINTS = {
  compact: 640,  // sm: below → compact
  embedded: 1024, // lg: below → embedded, above → full
} as const;

// ── Helpers ────────────────────────────────────────────────────────────
function getStoredMode(): AgentViewMode | null {
  if (typeof window === 'undefined') return null;
  const stored = localStorage.getItem(STORAGE_KEY);
  if (stored === 'full' || stored === 'compact' || stored === 'embedded') {
    return stored;
  }
  return null;
}

function getStoredLock(): boolean {
  if (typeof window === 'undefined') return false;
  return localStorage.getItem(LOCK_KEY) === 'true';
}

function getModeForWidth(width: number): AgentViewMode {
  if (width < BREAKPOINTS.compact) return 'compact';
  if (width < BREAKPOINTS.embedded) return 'embedded';
  return 'full';
}

// ── Hook ───────────────────────────────────────────────────────────────
/**
 * Hook to manage Agent view mode with automatic screen-size detection
 * and persistent user preferences.
 *
 * - Auto-switches based on window width when unlocked
 * - Persists manual selection to localStorage
 * - Supports locking a preferred mode
 */
export function useAgentViewMode(): AgentViewModeState {
  const [mode, setModeState] = useState<AgentViewMode>(() => {
    const stored = getStoredMode();
    const locked = getStoredLock();
    if (locked && stored) return stored;
    if (typeof window !== 'undefined') return getModeForWidth(window.innerWidth);
    return 'full';
  });

  const [isLocked, setIsLocked] = useState<boolean>(() => getStoredLock());

  // Listen for window resize when not locked
  useEffect(() => {
    if (isLocked) return;

    const handleResize = () => {
      setModeState(getModeForWidth(window.innerWidth));
    };

    window.addEventListener('resize', handleResize);
    // Set initial value on mount
    handleResize();

    return () => window.removeEventListener('resize', handleResize);
  }, [isLocked]);

  const setMode = useCallback((newMode: AgentViewMode) => {
    setModeState(newMode);
    setIsLocked(true);
    if (typeof window !== 'undefined') {
      localStorage.setItem(STORAGE_KEY, newMode);
      localStorage.setItem(LOCK_KEY, 'true');
    }
  }, []);

  const unlock = useCallback(() => {
    setIsLocked(false);
    if (typeof window !== 'undefined') {
      localStorage.setItem(LOCK_KEY, 'false');
      setModeState(getModeForWidth(window.innerWidth));
    }
  }, []);

  const toggleLock = useCallback(() => {
    if (isLocked) {
      unlock();
    } else {
      if (typeof window !== 'undefined') {
        localStorage.setItem(STORAGE_KEY, mode);
        localStorage.setItem(LOCK_KEY, 'true');
      }
      setIsLocked(true);
    }
  }, [isLocked, mode, unlock]);

  return { mode, isLocked, setMode, unlock, toggleLock };
}
