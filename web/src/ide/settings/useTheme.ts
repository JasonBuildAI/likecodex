'use client';

import { useEffect, useState, useCallback } from 'react';

export type ThemeMode = 'dark' | 'light';

/**
 * useTheme — Manages IDE theme with CSS variables and localStorage persistence.
 */
export function useTheme() {
  const [theme, setThemeState] = useState<ThemeMode>(() => {
    if (typeof window === 'undefined') return 'dark';
    return (localStorage.getItem('likecodex-theme') as ThemeMode) || 'dark';
  });

  const [accentColor, setAccentColor] = useState<string>(() => {
    if (typeof window === 'undefined') return '#3b82f6';
    return localStorage.getItem('likecodex-accent') || '#3b82f6';
  });

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('likecodex-theme', theme);
  }, [theme]);

  useEffect(() => {
    document.documentElement.style.setProperty('--accent', accentColor);
    localStorage.setItem('likecodex-accent', accentColor);
  }, [accentColor]);

  const setTheme = useCallback((mode: ThemeMode) => {
    setThemeState(mode);
  }, []);

  const toggleTheme = useCallback(() => {
    setThemeState((prev) => (prev === 'dark' ? 'light' : 'dark'));
  }, []);

  return { theme, setTheme, toggleTheme, accentColor, setAccentColor };
}
