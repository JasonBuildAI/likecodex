'use client';

import { useCallback, useRef } from 'react';
import { lspDefinition, lspReferences, lspHover } from '@/lib/api';

/**
 * Hook for LSP operations (Go to Definition, Find References, Hover)
 */
export function useLSP() {
  const loadingRef = useRef(false);

  const goToDefinition = useCallback(
    async (filePath: string, line: number, symbol: string) => {
      if (loadingRef.current) return null;
      loadingRef.current = true;
      try {
        return await lspDefinition(filePath, line, symbol);
      } finally {
        loadingRef.current = false;
      }
    },
    []
  );

  const findReferences = useCallback(
    async (filePath: string, line: number, symbol: string) => {
      if (loadingRef.current) return null;
      loadingRef.current = true;
      try {
        return await lspReferences(filePath, line, symbol);
      } finally {
        loadingRef.current = false;
      }
    },
    []
  );

  const getHover = useCallback(
    async (filePath: string, line: number, symbol: string) => {
      if (loadingRef.current) return null;
      loadingRef.current = true;
      try {
        return await lspHover(filePath, line, symbol);
      } finally {
        loadingRef.current = false;
      }
    },
    []
  );

  return {
    goToDefinition,
    findReferences,
    getHover,
    isLoading: () => loadingRef.current,
  };
}
