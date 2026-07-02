'use client';

import { create } from 'zustand';

// ── Types ──────────────────────────────────────────────────────────────

export interface MetricsData {
  cacheHitRate: number;
  recentHitRate: number;
  totalRequests: number;
  totalHitTokens: number;
  totalMissTokens: number;
  totalCost: number;
  sessionCost: number;
  avgLatency: number;
  p50Latency: number;
  p95Latency: number;
  p99Latency: number;
  activeSessions: number;
  modelName: string;
}

export interface MetricsStoreState {
  metrics: MetricsData | null;
  history: MetricsData[];
  isLoading: boolean;
  error: string | null;
  fetchMetrics: () => Promise<void>;
}

// ── Helpers ────────────────────────────────────────────────────────────

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || '/api';

function parseMetrics(raw: Record<string, unknown>): MetricsData {
  return {
    cacheHitRate: Number(raw.cache_hit_rate ?? raw.cacheHitRate ?? 0),
    recentHitRate: Number(raw.recent_hit_rate ?? raw.recentHitRate ?? 0),
    totalRequests: Number(raw.total_requests ?? raw.totalRequests ?? 0),
    totalHitTokens: Number(raw.total_hit_tokens ?? raw.totalHitTokens ?? 0),
    totalMissTokens: Number(raw.total_miss_tokens ?? raw.totalMissTokens ?? 0),
    totalCost: Number(raw.total_cost ?? raw.totalCost ?? 0),
    sessionCost: Number(raw.session_cost ?? raw.sessionCost ?? 0),
    avgLatency: Number(raw.avg_latency ?? raw.avgLatency ?? 0),
    p50Latency: Number(raw.p50_latency ?? raw.p50Latency ?? 0),
    p95Latency: Number(raw.p95_latency ?? raw.p95Latency ?? 0),
    p99Latency: Number(raw.p99_latency ?? raw.p99Latency ?? 0),
    activeSessions: Number(raw.active_sessions ?? raw.activeSessions ?? 0),
    modelName: String(raw.model_name ?? raw.modelName ?? 'unknown'),
  };
}

// ── Initial State ──────────────────────────────────────────────────────

const initialState: MetricsStoreState = {
  metrics: null,
  history: [],
  isLoading: false,
  error: null,
  fetchMetrics: async () => {},
};

// ── Store ──────────────────────────────────────────────────────────────

export const useMetricsStore = create<MetricsStoreState>((set, get) => ({
  ...initialState,

  fetchMetrics: async () => {
    // Prevent concurrent fetches
    if (get().isLoading) return;

    set({ isLoading: true, error: null });

    try {
      const resp = await fetch(`${API_BASE}/metrics`, {
        method: 'GET',
        headers: { 'Content-Type': 'application/json' },
      });

      if (!resp.ok) {
        throw new Error(`Metrics fetch failed: ${resp.status} ${resp.statusText}`);
      }

      const raw: Record<string, unknown> = await resp.json();
      const parsed = parseMetrics(raw);

      set((s) => ({
        metrics: parsed,
        history: [...s.history.slice(-59), parsed],
        isLoading: false,
        error: null,
      }));
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Unknown error';
      set({ isLoading: false, error: message });
    }
  },
}));
