'use client';

import { useEffect } from 'react';
import { useAppStore } from '@/lib/store';
import { fetchConfig, fetchSessions, fetchCacheMetrics, fetchDoctor } from '@/lib/api';
import { ExtensionLoader } from '@/ide/extensions/extensionLoader';

/**
 * Hook for IDE initialization: loads config, sessions, cache metrics on mount.
 */
export function useIdeSettings() {
  const setConfig = useAppStore((s) => s.setConfig);
  const setSessions = useAppStore((s) => s.setSessions);
  const setCacheHitRate = useAppStore((s) => s.setCacheHitRate);

  useEffect(() => {
    ExtensionLoader.loadExtensions();
    fetchConfig().then(setConfig);
    fetchSessions().then(setSessions);
    fetchCacheMetrics().then((metrics) => {
      const rate = metrics.recent_hit_rate ?? metrics.hit_rate;
      setCacheHitRate(typeof rate === 'number' ? rate : null);
    });
    const interval = setInterval(() => {
      fetchCacheMetrics().then((metrics) => {
        const rate = metrics.recent_hit_rate ?? metrics.hit_rate;
        setCacheHitRate(typeof rate === 'number' ? rate : null);
      });
    }, 15000);
    return () => clearInterval(interval);
  }, [setConfig, setSessions, setCacheHitRate]);
}
