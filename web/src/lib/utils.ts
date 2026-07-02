/**
 * Utility functions for LikeCodex UI
 */

import { clsx } from 'clsx';
import { twMerge } from 'tailwind-merge';

// ── Class Name Merger ──────────────────────────────────────────────────
// Uses clsx for conditional classes + tailwind-merge for conflict resolution
export function cn(...inputs: Parameters<typeof clsx>): string {
  return twMerge(clsx(inputs));
}

// ── Formatting Utilities ───────────────────────────────────────────────

export function formatBytes(bytes: number, decimals: number = 2): string {
  if (bytes === 0) return '0 B';
  const k = 1024;
  const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(decimals)) + ' ' + sizes[i];
}

export function formatDuration(ms: number): string {
  if (ms < 1000) return `${Math.round(ms)}ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
  const min = Math.floor(ms / 60000);
  const sec = Math.floor((ms % 60000) / 1000);
  return `${min}m ${sec}s`;
}

export function truncate(str: string, maxLen: number): string {
  if (str.length <= maxLen) return str;
  return str.slice(0, maxLen - 3) + '...';
}

// ── ID Generator ───────────────────────────────────────────────────────

let _idCounter = 0;
export function generateId(prefix: string = 'id'): string {
  _idCounter += 1;
  return `${prefix}-${Date.now().toString(36)}-${_idCounter.toString(36)}`;
}

// ── Delay/Sleep ────────────────────────────────────────────────────────

export function sleep(ms: number): Promise<void> {
  return new Promise((resolve) => setTimeout(resolve, ms));
}

// ── Clamp ──────────────────────────────────────────────────────────────

export function clamp(value: number, min: number, max: number): number {
  return Math.min(Math.max(value, min), max);
}
