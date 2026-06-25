'use client';

import React, { Suspense, lazy, useMemo, useState, useEffect, useCallback, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

// ─────────────────────────────────────────────
// LazyComponent - Lazy load with fallback
// ─────────────────────────────────────────────
export function createLazyComponent<T extends React.ComponentType<any>>(
  loader: () => Promise<{ default: T } | T>,
  fallback?: React.ReactNode
) {
  const LazyComponent = lazy(() =>
    loader().then(m => ({ default: (m as any).default || m }))
  );

  const Wrapped: React.FC<React.ComponentProps<T>> = (props) => (
    <Suspense fallback={fallback || <DefaultFallback />}>
      <LazyComponent {...props} />
    </Suspense>
  );

  Wrapped.displayName = `LazyComponent(${LazyComponent.displayName || 'Anonymous'})`;
  return Wrapped;
}

// ─────────────────────────────────────────────
// Default fallback
// ─────────────────────────────────────────────
const DefaultFallback: React.FC = () => (
  <div className="flex items-center justify-center p-8">
    <motion.div
      animate={{ rotate: 360 }}
      transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
      className="w-6 h-6 border-2 border-purple-500/30 border-t-purple-500 rounded-full"
    />
  </div>
);

// ─────────────────────────────────────────────
// Skeleton loader
// ─────────────────────────────────────────────
export const Skeleton: React.FC<{ className?: string }> = ({ className = '' }) => (
  <div className={`animate-pulse bg-white/[0.04] rounded ${className}`} />
);

export const MessageSkeleton: React.FC = () => (
  <div className="flex gap-3 p-4">
    <Skeleton className="w-8 h-8 rounded-full flex-shrink-0" />
    <div className="flex-1 space-y-2">
      <Skeleton className="h-4 w-3/4" />
      <Skeleton className="h-4 w-1/2" />
      <Skeleton className="h-20 w-full" />
    </div>
  </div>
);

// ─────────────────────────────────────────────
// useDebounce hook
// ─────────────────────────────────────────────
export function useDebounce<T>(value: T, delay: number): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);
  return debounced;
}

// ─────────────────────────────────────────────
// useThrottle hook
// ─────────────────────────────────────────────
export function useThrottle<T extends (...args: any[]) => any>(fn: T, limit: number): T {
  const lastRun = useRef(0);
  const timerRef = useRef<NodeJS.Timeout | null>(null);

  return useCallback(
    (...args: Parameters<T>) => {
      const now = Date.now();
      const remaining = limit - (now - lastRun.current);

      if (remaining <= 0) {
        lastRun.current = now;
        fn(...args);
      } else if (!timerRef.current) {
        timerRef.current = setTimeout(() => {
          lastRun.current = Date.now();
          timerRef.current = null;
          fn(...args);
        }, remaining);
      }
    },
    [fn, limit]
  ) as T;
}

// ─────────────────────────────────────────────
// useIntersectionObserver - for infinite scroll / lazy loading
// ─────────────────────────────────────────────
export function useIntersectionObserver(
  options: IntersectionObserverInit = {}
) {
  const [isIntersecting, setIsIntersecting] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const element = ref.current;
    if (!element) return;

    const observer = new IntersectionObserver(([entry]) => {
      setIsIntersecting(entry.isIntersecting);
    }, {
      threshold: 0.1,
      rootMargin: '100px',
      ...options,
    });

    observer.observe(element);
    return () => observer.disconnect();
  }, [options]);

  return { ref, isIntersecting };
}

// ─────────────────────────────────────────────
// useRAF - requestAnimationFrame hook
// ─────────────────────────────────────────────
export function useRAF(callback: () => void, isActive: boolean = true) {
  const rafRef = useRef<number>();

  useEffect(() => {
    if (!isActive) return;

    const tick = () => {
      callback();
      rafRef.current = requestAnimationFrame(tick);
    };

    rafRef.current = requestAnimationFrame(tick);
    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
  }, [callback, isActive]);
}

// ─────────────────────────────────────────────
// VirtualList - simplified virtual scrolling
// ─────────────────────────────────────────────
interface VirtualListProps<T> {
  items: T[];
  itemHeight: number;
  height: number;
  renderItem: (item: T, index: number) => React.ReactNode;
  overscan?: number;
}

export function VirtualList<T>({
  items,
  itemHeight,
  height,
  renderItem,
  overscan = 5,
}: VirtualListProps<T>) {
  const [scrollTop, setScrollTop] = useState(0);
  const containerRef = useRef<HTMLDivElement>(null);

  const { startIndex, endIndex, totalHeight } = useMemo(() => {
    const total = items.length * itemHeight;
    const start = Math.max(0, Math.floor(scrollTop / itemHeight) - overscan);
    const end = Math.min(
      items.length,
      Math.ceil((scrollTop + height) / itemHeight) + overscan
    );
    return { startIndex: start, endIndex: end, totalHeight: total };
  }, [items.length, itemHeight, scrollTop, height, overscan]);

  const handleScroll = useCallback((e: React.UIEvent<HTMLDivElement>) => {
    setScrollTop(e.currentTarget.scrollTop);
  }, []);

  const visibleItems = useMemo(
    () => items.slice(startIndex, endIndex),
    [items, startIndex, endIndex]
  );

  return (
    <div
      ref={containerRef}
      onScroll={handleScroll}
      style={{ height, overflowY: 'auto' }}
      className="scrollbar-thin"
    >
      <div style={{ height: totalHeight, position: 'relative' }}>
        <div style={{ transform: `translateY(${startIndex * itemHeight}px)` }}>
          {visibleItems.map((item, i) => (
            <div key={startIndex + i} style={{ height: itemHeight }}>
              {renderItem(item, startIndex + i)}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

// ─────────────────────────────────────────────
// PerformanceMonitor - track render times (dev only)
// ─────────────────────────────────────────────
export function useRenderTime(name: string) {
  const startTime = useRef(performance.now());

  useEffect(() => {
    const renderTime = performance.now() - startTime.current;
    if (process.env.NODE_ENV === 'development' && renderTime > 16) {
      console.warn(`[Perf] ${name} took ${renderTime.toFixed(2)}ms to render`);
    }
    startTime.current = performance.now();
  });
}

export default { createLazyComponent, VirtualList, Skeleton, useDebounce, useThrottle };
