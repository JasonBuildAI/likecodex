'use client';

import React, { createContext, useContext, useEffect, useState } from 'react';
import { useAppStore } from '@/lib/store';

type ThemeMode = 'dark' | 'light' | 'system';

interface ThemeContextValue {
  theme: 'dark' | 'light';
  themeMode: ThemeMode;
  toggleTheme: () => void;
  setTheme: (theme: 'dark' | 'light') => void;
  setThemeMode: (mode: ThemeMode) => void;
  fontSize: number;
  setFontSize: (size: number) => void;
  lineHeight: number;
  setLineHeight: (lh: number) => void;
}

const ThemeContext = createContext<ThemeContextValue | undefined>(undefined);

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const theme = useAppStore((s) => s.theme);
  const setTheme = useAppStore((s) => s.setTheme);
  const [themeMode, setThemeModeState] = useState<ThemeMode>('dark');
  const [fontSize, setFontSizeState] = useState(14);
  const [lineHeight, setLineHeightState] = useState(1.6);

  // Load saved preferences
  useEffect(() => {
    if (typeof window === 'undefined') return;

    // Theme mode
    const savedMode = localStorage.getItem('likecodex_theme_mode') as ThemeMode | null;
    if (savedMode) {
      setThemeModeState(savedMode);
    }

    // Font size
    const savedFontSize = localStorage.getItem('likecodex_font_size');
    if (savedFontSize) {
      setFontSizeState(parseInt(savedFontSize, 10));
    }

    // Line height
    const savedLineHeight = localStorage.getItem('likecodex_line_height');
    if (savedLineHeight) {
      setLineHeightState(parseFloat(savedLineHeight));
    }
  }, []);

  // System theme detection
  useEffect(() => {
    if (typeof window === 'undefined') return;

    const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');

    const handleChange = (e: MediaQueryListEvent) => {
      if (themeMode === 'system') {
        setTheme(e.matches ? 'dark' : 'light');
      }
    };

    mediaQuery.addEventListener('change', handleChange);
    return () => mediaQuery.removeEventListener('change', handleChange);
  }, [themeMode, setTheme]);

  // Apply theme mode
  useEffect(() => {
    if (typeof window === 'undefined') return;

    if (themeMode === 'system') {
      const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
      setTheme(prefersDark ? 'dark' : 'light');
    }
  }, [themeMode, setTheme]);

  // Apply theme class to document with transition
  useEffect(() => {
    if (typeof document !== 'undefined') {
      const root = document.documentElement;

      // Add transition class for smooth theme changes
      root.classList.add('theme-transitioning');
      const timeout = setTimeout(() => {
        root.classList.remove('theme-transitioning');
      }, 300);

      if (theme === 'light') {
        root.classList.remove('dark');
        root.classList.add('light');
      } else {
        root.classList.remove('light');
        root.classList.add('dark');
      }

      localStorage.setItem('likecodex_theme', theme);

      return () => clearTimeout(timeout);
    }
  }, [theme]);

  // Apply font size and line height
  useEffect(() => {
    if (typeof document !== 'undefined') {
      document.documentElement.style.setProperty('--font-size', `${fontSize}px`);
      document.documentElement.style.setProperty('--line-height', String(lineHeight));
      localStorage.setItem('likecodex_font_size', String(fontSize));
      localStorage.setItem('likecodex_line_height', String(lineHeight));
    }
  }, [fontSize, lineHeight]);

  const toggleTheme = () => {
    setTheme(theme === 'dark' ? 'light' : 'dark');
  };

  const handleSetThemeMode = (mode: ThemeMode) => {
    setThemeModeState(mode);
    localStorage.setItem('likecodex_theme_mode', mode);
  };

  const handleSetTheme = (t: 'dark' | 'light') => {
    setTheme(t);
    // Switch out of system mode when user manually selects
    if (themeMode === 'system') {
      setThemeModeState(t);
    }
  };

  return (
    <ThemeContext.Provider
      value={{
        theme,
        themeMode,
        toggleTheme,
        setTheme: handleSetTheme,
        setThemeMode: handleSetThemeMode,
        fontSize,
        setFontSize: setFontSizeState,
        lineHeight,
        setLineHeight: setLineHeightState,
      }}
    >
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  const ctx = useContext(ThemeContext);
  if (!ctx) {
    throw new Error('useTheme must be used within ThemeProvider');
  }
  return ctx;
}
'use client';

import React, { createContext, useContext, useEffect } from 'react';
import { useAppStore } from '@/lib/store';

interface ThemeContextValue {
  theme: 'dark' | 'light';
  toggleTheme: () => void;
  setTheme: (theme: 'dark' | 'light') => void;
}

const ThemeContext = createContext<ThemeContextValue | undefined>(undefined);

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const theme = useAppStore((s) => s.theme);
  const setTheme = useAppStore((s) => s.setTheme);

  useEffect(() => {
    // Load theme from localStorage on mount
    const saved = typeof window !== 'undefined'
      ? (localStorage.getItem('likecodex_theme') as 'dark' | 'light' | null)
      : null;
    if (saved && saved !== theme) {
      setTheme(saved);
    }
  }, []);

  useEffect(() => {
    // Apply theme class to document
    if (typeof document !== 'undefined') {
      const root = document.documentElement;
      if (theme === 'light') {
        root.classList.remove('dark');
        root.classList.add('light');
      } else {
        root.classList.remove('light');
        root.classList.add('dark');
      }
      localStorage.setItem('likecodex_theme', theme);
    }
  }, [theme]);

  const toggleTheme = () => {
    setTheme(theme === 'dark' ? 'light' : 'dark');
  };

  return (
    <ThemeContext.Provider value={{ theme, toggleTheme, setTheme }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  const ctx = useContext(ThemeContext);
  if (!ctx) {
    throw new Error('useTheme must be used within ThemeProvider');
  }
  return ctx;
}
