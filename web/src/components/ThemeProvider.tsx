'use client';

import { useEffect } from 'react';
import { useAppStore } from '@/lib/store';

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  const theme = useAppStore((s) => s.theme);

  useEffect(() => {
    const stored = localStorage.getItem('likecodex_theme') as 'dark' | 'light' | null;
    if (stored) {
      useAppStore.getState().setTheme(stored);
    }
  }, []);

  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('likecodex_theme', theme);
  }, [theme]);

  return <>{children}</>;
}
