'use client';

import { useState, useEffect, useSyncExternalStore, useCallback, useRef } from 'react';
import { i18n, type Locale } from '@/lib/i18n';

// ─────────────────────────────────────────────
// useI18n - React hook for internationalization
// ─────────────────────────────────────────────
export function useI18n() {
  const locale = useSyncExternalStore(
    (cb) => i18n.subscribe(cb),
    () => i18n.getLocale(),
    () => 'zh' as Locale
  );

  const t = useCallback((key: string) => i18n.t(key), [locale]);
  const setLocale = useCallback((l: Locale) => i18n.setLocale(l), []);

  return { t, locale, setLocale };
}

// ─────────────────────────────────────────────
// useAccessibility - A11y utilities
// ─────────────────────────────────────────────
export function useAccessibility() {
  const [prefersReducedMotion, setPrefersReducedMotion] = useState(false);
  const [highContrast, setHighContrast] = useState(false);
  const [fontSize, setFontSize] = useState<'small' | 'medium' | 'large'>('medium');

  useEffect(() => {
    const motionMQ = window.matchMedia('(prefers-reduced-motion: reduce)');
    const contrastMQ = window.matchMedia('(prefers-contrast: high)');

    const updateMotion = () => setPrefersReducedMotion(motionMQ.matches);
    const updateContrast = () => setHighContrast(contrastMQ.matches);

    updateMotion();
    updateContrast();

    motionMQ.addEventListener('change', updateMotion);
    contrastMQ.addEventListener('change', updateContrast);

    // Load saved font size
    const saved = localStorage.getItem('likecodex_font_size') as 'small' | 'medium' | 'large' | null;
    if (saved) setFontSize(saved);

    return () => {
      motionMQ.removeEventListener('change', updateMotion);
      contrastMQ.removeEventListener('change', updateContrast);
    };
  }, []);

  // Apply font size to document
  useEffect(() => {
    const sizes = { small: '14px', medium: '16px', large: '18px' };
    document.documentElement.style.fontSize = sizes[fontSize];
    localStorage.setItem('likecodex_font_size', fontSize);
  }, [fontSize]);

  // Apply high contrast class
  useEffect(() => {
    if (highContrast) {
      document.documentElement.classList.add('high-contrast');
    } else {
      document.documentElement.classList.remove('high-contrast');
    }
  }, [highContrast]);

  const cycleFontSize = useCallback(() => {
    setFontSize(prev => prev === 'small' ? 'medium' : prev === 'medium' ? 'large' : 'small');
  }, []);

  return {
    prefersReducedMotion,
    highContrast,
    fontSize,
    setFontSize,
    cycleFontSize,
  };
}

// ─────────────────────────────────────────────
// useFocusTrap - Trap focus within an element
// ─────────────────────────────────────────────
export function useFocusTrap<T extends HTMLElement>(isActive: boolean) {
  const ref = useRef<T>(null);

  useEffect(() => {
    if (!isActive || !ref.current) return;

    const element = ref.current;
    const focusable = element.querySelectorAll<HTMLElement>(
      'button, [href], input, select, textarea, [tabindex]:not([tabindex="-1"])'
    );
    const first = focusable[0];
    const last = focusable[focusable.length - 1];

    if (first) first.focus();

    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key !== 'Tab') return;

      if (e.shiftKey) {
        if (document.activeElement === first) {
          e.preventDefault();
          last?.focus();
        }
      } else {
        if (document.activeElement === last) {
          e.preventDefault();
          first?.focus();
        }
      }
    };

    element.addEventListener('keydown', handleKeyDown);
    return () => element.removeEventListener('keydown', handleKeyDown);
  }, [isActive]);

  return ref;
}
