/**
 * Responsive breakpoints and media query utilities
 */

// ── Breakpoint Definitions ─────────────────────────────────────────────
export const breakpoints = {
  sm: 640,   // Small devices (phones)
  md: 768,   // Medium devices (tablets)
  lg: 1024,  // Large devices (desktops)
  xl: 1280,  // Extra large devices (large desktops)
  '2xl': 1536, // 2X large devices
} as const;

export type Breakpoint = keyof typeof breakpoints;

// ── Media Query Strings ────────────────────────────────────────────────
export const mediaQueries = {
  sm: `(min-width: ${breakpoints.sm}px)`,
  md: `(min-width: ${breakpoints.md}px)`,
  lg: `(min-width: ${breakpoints.lg}px)`,
  xl: `(min-width: ${breakpoints.xl}px)`,
  '2xl': `(min-width: ${breakpoints['2xl']}px)`,
  
  // Max-width queries
  smDown: `(max-width: ${breakpoints.sm - 1}px)`,
  mdDown: `(max-width: ${breakpoints.md - 1}px)`,
  lgDown: `(max-width: ${breakpoints.lg - 1}px)`,
  xlDown: `(max-width: ${breakpoints.xl - 1}px)`,
  '2xlDown': `(max-width: ${breakpoints['2xl'] - 1}px)`,
  
  // Range queries
  smToMd: `(min-width: ${breakpoints.sm}px) and (max-width: ${breakpoints.md - 1}px)`,
  mdToLg: `(min-width: ${breakpoints.md}px) and (max-width: ${breakpoints.lg - 1}px)`,
  lgToXl: `(min-width: ${breakpoints.lg}px) and (max-width: ${breakpoints.xl - 1}px)`,
  xlTo2xl: `(min-width: ${breakpoints.xl}px) and (max-width: ${breakpoints['2xl'] - 1}px)`,
} as const;

// ── Hook for Media Queries ─────────────────────────────────────────────
import { useState, useEffect } from 'react';

/**
 * Custom hook to check if a media query matches
 * @param query - Media query string or breakpoint name
 * @returns boolean indicating if the query matches
 * 
 * @example
 * const isMobile = useMediaQuery('smDown')
 * const isDesktop = useMediaQuery('(min-width: 1024px)')
 */
export function useMediaQuery(query: string | Breakpoint): boolean {
  const [matches, setMatches] = useState(false);

  useEffect(() => {
    // Resolve breakpoint name to media query string
    const mediaQueryString = query in breakpoints 
      ? mediaQueries[query as Breakpoint]
      : query;

    const mediaQueryList = window.matchMedia(mediaQueryString);
    
    // Set initial value
    setMatches(mediaQueryList.matches);

    // Listen for changes
    const handleChange = (event: MediaQueryListEvent) => {
      setMatches(event.matches);
    };

    // Modern browsers
    if (mediaQueryList.addEventListener) {
      mediaQueryList.addEventListener('change', handleChange);
    } else {
      // Legacy support
      mediaQueryList.addListener(handleChange);
    }

    // Cleanup
    return () => {
      if (mediaQueryList.removeEventListener) {
        mediaQueryList.removeEventListener('change', handleChange);
      } else {
        // Legacy support
        mediaQueryList.removeListener(handleChange);
      }
    };
  }, [query]);

  return matches;
}

// ── Convenience Hooks ──────────────────────────────────────────────────
export function useIsMobile(): boolean {
  return useMediaQuery('mdDown');
}

export function useIsTablet(): boolean {
  return useMediaQuery('smToMd');
}

export function useIsDesktop(): boolean {
  return useMediaQuery('lg');
}

export function useIsLargeDesktop(): boolean {
  return useMediaQuery('xl');
}

// ── Device Detection ───────────────────────────────────────────────────
export function isTouchDevice(): boolean {
  if (typeof window === 'undefined') return false;
  return (
    'ontouchstart' in window ||
    navigator.maxTouchPoints > 0 ||
    navigator.msMaxTouchPoints > 0
  );
}

export function isRetinaDisplay(): boolean {
  if (typeof window === 'undefined') return false;
  return window.devicePixelRatio >= 2;
}

// ── Orientation Detection ──────────────────────────────────────────────
export function useOrientation(): 'portrait' | 'landscape' {
  const [orientation, setOrientation] = useState<'portrait' | 'landscape'>('landscape');

  useEffect(() => {
    const handleOrientation = () => {
      setOrientation(
        window.innerHeight > window.innerWidth ? 'portrait' : 'landscape'
      );
    };

    handleOrientation();
    window.addEventListener('resize', handleOrientation);

    return () => window.removeEventListener('resize', handleOrientation);
  }, []);

  return orientation;
}

// ── Export All ─────────────────────────────────────────────────────────
export default {
  breakpoints,
  mediaQueries,
  useMediaQuery,
  useIsMobile,
  useIsTablet,
  useIsDesktop,
  useIsLargeDesktop,
  isTouchDevice,
  isRetinaDisplay,
  useOrientation,
};
