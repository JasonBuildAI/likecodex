'use client';

import { useEffect, useRef } from 'react';
import { fetchCacheMetrics, fetchConfig, fetchDoctor, fetchSessions } from '@/lib/api';
import { useAppStore } from '@/lib/store';
import { ExtensionLoader } from '@/ide/extensions/extensionLoader';

export function useAppInit() {
  const setConfig = useAppStore((s) => s.setConfig);
  const setSessions = useAppStore((s) => s.setSessions);
  const setCacheHitRate = useAppStore((s) => s.setCacheHitRate);
  const intervalRef = useRef<ReturnType<typeof setInterval> | null>(null);

  // Load extensions on mount
  useEffect(() => {
    ExtensionLoader.loadExtensions();
  }, []);

  // Initialization
  useEffect(() => {
    fetchConfig().then(setConfig);
    fetchSessions().then(setSessions);
    fetchDoctor().then(() => {
      // Doctor result stored separately
    });
    fetchCacheMetrics().then((metrics) => {
      const rate = metrics.recent_hit_rate ?? metrics.hit_rate;
      setCacheHitRate(typeof rate === 'number' ? rate : null);
    });

    intervalRef.current = setInterval(() => {
      fetchCacheMetrics().then((metrics) => {
        const rate = metrics.recent_hit_rate ?? metrics.hit_rate;
        setCacheHitRate(typeof rate === 'number' ? rate : null);
      });
    }, 15000);

    return () => {
      if (intervalRef.current) {
        clearInterval(intervalRef.current);
      }
    };
  }, [setConfig, setSessions, setCacheHitRate]);
}
