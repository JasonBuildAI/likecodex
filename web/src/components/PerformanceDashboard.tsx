'use client';

import { useEffect, useMemo } from 'react';
import { motion } from 'framer-motion';
import { useMetricsStore } from '@/stores/metricsStore';
import type { MetricsData } from '@/stores/metricsStore';

// ── Variants ───────────────────────────────────────────────────────────

const containerVariants = {
  hidden: { opacity: 0 },
  visible: {
    opacity: 1,
    transition: { staggerChildren: 0.08, delayChildren: 0.1 },
  },
};

const cardVariants = {
  hidden: { opacity: 0, y: 24, scale: 0.97 },
  visible: {
    opacity: 1,
    y: 0,
    scale: 1,
    transition: { type: 'spring', stiffness: 260, damping: 24 },
  },
};

// ── Ring Progress (Circular gauge) ────────────────────────────────────

function RingProgress({ value, size = 120, strokeWidth = 8, label }: {
  value: number;
  size?: number;
  strokeWidth?: number;
  label: string;
}) {
  const radius = (size - strokeWidth) / 2;
  const circumference = 2 * Math.PI * radius;
  const clamped = Math.min(100, Math.max(0, value));
  const offset = circumference - (clamped / 100) * circumference;

  const color =
    clamped >= 80 ? 'stroke-emerald-400' :
    clamped >= 50 ? 'stroke-amber-400' :
    'stroke-rose-400';

  return (
    <div className="flex flex-col items-center gap-2">
      <svg width={size} height={size} className="-rotate-90">
        {/* Background ring */}
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="currentColor"
          strokeWidth={strokeWidth}
          className="text-white/8"
        />
        {/* Foreground ring */}
        <motion.circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          className={color}
          strokeDasharray={circumference}
          initial={{ strokeDashoffset: circumference }}
          animate={{ strokeDashoffset: offset }}
          transition={{ duration: 1.2, ease: 'easeOut' }}
        />
      </svg>
      <div className="absolute flex flex-col items-center justify-center" style={{ width: size, height: size }}>
        <span className="text-2xl font-bold text-white tabular-nums">
          {clamped.toFixed(1)}<span className="text-sm text-gray-400">%</span>
        </span>
        <span className="text-xs text-gray-500 mt-0.5">{label}</span>
      </div>
    </div>
  );
}

// ── Stat Card ──────────────────────────────────────────────────────────

function StatCard({ title, children, className = '' }: {
  title: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <motion.div
      variants={cardVariants}
      className={`group relative overflow-hidden rounded-xl bg-gray-800/80 p-5 border border-white/5
        hover:border-white/10 hover:bg-gray-800 transition-all duration-300 ${className}`}
    >
      {/* Top accent line */}
      <div className="absolute top-0 left-4 right-4 h-px bg-gradient-to-r from-transparent via-white/10 to-transparent
        group-hover:via-white/20 transition-all duration-300" />
      <h3 className="text-xs font-semibold uppercase tracking-widest text-gray-500 mb-4">
        {title}
      </h3>
      {children}
    </motion.div>
  );
}

// ── Metric Row ─────────────────────────────────────────────────────────

function MetricRow({ label, value, suffix = '', accent = false }: {
  label: string;
  value: string | number;
  suffix?: string;
  accent?: boolean;
}) {
  return (
    <div className="flex items-center justify-between py-1.5">
      <span className="text-sm text-gray-400">{label}</span>
      <span className={`text-sm font-mono font-semibold tabular-nums ${accent ? 'text-purple-400' : 'text-gray-200'}`}>
        {value}{suffix}
      </span>
    </div>
  );
}

function MetricRowLatency({ label, value, unit = 'ms' }: {
  label: string;
  value: number;
  unit?: string;
}) {
  return (
    <div className="flex items-center justify-between py-1.5">
      <span className="text-sm text-gray-400">{label}</span>
      <div className="flex items-center gap-1.5">
        <div className={`w-1.5 h-1.5 rounded-full ${
          value < 100 ? 'bg-emerald-400' :
          value < 500 ? 'bg-amber-400' :
          'bg-rose-400'
        }`} />
        <span className="text-sm font-mono font-semibold tabular-nums text-gray-200">
          {value.toFixed(1)}{unit}
        </span>
      </div>
    </div>
  );
}

// ── Token Bar ──────────────────────────────────────────────────────────

function TokenBar({ hit, miss }: { hit: number; miss: number }) {
  const total = hit + miss || 1;
  const hitPct = (hit / total) * 100;
  const missPct = (miss / total) * 100;

  return (
    <div className="mt-3">
      <div className="flex h-2.5 rounded-full bg-gray-700/50 overflow-hidden">
        <motion.div
          className="bg-emerald-500/70 rounded-l-full"
          initial={{ width: 0 }}
          animate={{ width: `${hitPct}%` }}
          transition={{ duration: 0.8, ease: 'easeOut' }}
        />
        <motion.div
          className="bg-rose-500/50 rounded-r-full"
          initial={{ width: 0 }}
          animate={{ width: `${missPct}%` }}
          transition={{ duration: 0.8, ease: 'easeOut', delay: 0.1 }}
        />
      </div>
      <div className="flex justify-between mt-1.5 text-xs text-gray-500">
        <span>命中 <span className="text-emerald-400 font-mono">{hitPct.toFixed(0)}%</span></span>
        <span>未命中 <span className="text-rose-400 font-mono">{missPct.toFixed(0)}%</span></span>
      </div>
    </div>
  );
}

// ── Loading Skeleton ───────────────────────────────────────────────────

function DashboardSkeleton() {
  return (
    <div className="grid grid-cols-1 md:grid-cols-2 gap-4 animate-pulse">
      {Array.from({ length: 6 }).map((_, i) => (
        <div key={i} className="rounded-xl bg-gray-800/60 p-5 border border-white/5 min-h-[160px]">
          <div className="h-3 w-24 bg-white/5 rounded mb-4" />
          <div className="space-y-3">
            <div className="h-4 w-3/4 bg-white/5 rounded" />
            <div className="h-4 w-1/2 bg-white/5 rounded" />
            <div className="h-4 w-2/3 bg-white/5 rounded" />
          </div>
        </div>
      ))}
    </div>
  );
}

// ── Error Banner ───────────────────────────────────────────────────────

function ErrorBanner({ message, onRetry }: { message: string; onRetry: () => void }) {
  return (
    <motion.div
      initial={{ opacity: 0, y: -12 }}
      animate={{ opacity: 1, y: 0 }}
      className="rounded-xl bg-rose-900/20 border border-rose-500/20 p-4 flex items-center gap-3"
    >
      <svg className="w-5 h-5 text-rose-400 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
        <path strokeLinecap="round" strokeLinejoin="round" d="M12 9v2m0 4h.01M21 12a9 9 0 1 1-18 0 9 9 0 0 1 18 0Z" />
      </svg>
      <div className="flex-1 min-w-0">
        <p className="text-sm text-rose-300 truncate">{message}</p>
      </div>
      <button
        onClick={onRetry}
        className="text-xs font-medium text-rose-300 hover:text-rose-200 underline underline-offset-2 shrink-0 transition-colors"
      >
        重试
      </button>
    </motion.div>
  );
}

// ── Empty State ────────────────────────────────────────────────────────

function EmptyState({ onRefresh }: { onRefresh: () => void }) {
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.96 }}
      animate={{ opacity: 1, scale: 1 }}
      className="flex flex-col items-center justify-center py-16 text-center"
    >
      <div className="w-16 h-16 rounded-full bg-gray-800/60 border border-white/5 flex items-center justify-center mb-4">
        <svg className="w-8 h-8 text-gray-500" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
          <path strokeLinecap="round" strokeLinejoin="round" d="M3 13.125C3 12.504 3.504 12 4.125 12h2.25c.621 0 1.125.504 1.125 1.125v6.75C7.5 20.496 6.996 21 6.375 21h-2.25A1.125 1.125 0 0 1 3 19.875v-6.75ZM9.75 8.625c0-.621.504-1.125 1.125-1.125h2.25c.621 0 1.125.504 1.125 1.125v11.25c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 0 1-1.125-1.125V8.625ZM16.5 4.125c0-.621.504-1.125 1.125-1.125h2.25C20.496 3 21 3.504 21 4.125v15.75c0 .621-.504 1.125-1.125 1.125h-2.25a1.125 1.125 0 0 1-1.125-1.125V4.125Z" />
        </svg>
      </div>
      <h4 className="text-sm font-medium text-gray-400 mb-1">暂无性能数据</h4>
      <p className="text-xs text-gray-600 mb-4 max-w-xs">
        启动 LikeCodex 后，性能指标将在此处自动显示。点击下方按钮手动刷新。
      </p>
      <button
        onClick={onRefresh}
        className="px-4 py-1.5 text-xs font-medium text-white bg-purple-600/80 hover:bg-purple-600 rounded-lg transition-colors"
      >
        刷新数据
      </button>
    </motion.div>
  );
}

// ── Main Dashboard ─────────────────────────────────────────────────────

export function PerformanceDashboard() {
  const { metrics, isLoading, error, fetchMetrics } = useMetricsStore();

  // Auto-fetch on mount
  useEffect(() => {
    fetchMetrics();
  }, [fetchMetrics]);

  // ── Derived token stats ────────────────────────────────────────────
  const totalTokens = useMemo(() => {
    if (!metrics) return 0;
    return metrics.totalHitTokens + metrics.totalMissTokens;
  }, [metrics]);

  // ── Loading ────────────────────────────────────────────────────────
  if (isLoading && !metrics) {
    return (
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-white">性能仪表盘</h2>
          <span className="text-xs text-gray-500">正在加载…</span>
        </div>
        <DashboardSkeleton />
      </div>
    );
  }

  // ── Error (no cached data) ─────────────────────────────────────────
  if (error && !metrics) {
    return (
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-white">性能仪表盘</h2>
          <button
            onClick={fetchMetrics}
            className="text-xs font-medium text-purple-400 hover:text-purple-300 transition-colors"
          >
            重试
          </button>
        </div>
        <ErrorBanner message={error} onRetry={fetchMetrics} />
      </div>
    );
  }

  // ── Empty ──────────────────────────────────────────────────────────
  if (!metrics) {
    return (
      <div className="space-y-4">
        <div className="flex items-center justify-between">
          <h2 className="text-lg font-semibold text-white">性能仪表盘</h2>
        </div>
        <EmptyState onRefresh={fetchMetrics} />
      </div>
    );
  }

  // ── Data present ───────────────────────────────────────────────────
  return (
    <div className="space-y-4">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-lg font-semibold text-white">性能仪表盘</h2>
          {metrics.modelName !== 'unknown' && (
            <p className="text-xs text-gray-500 mt-0.5">模型: {metrics.modelName}</p>
          )}
        </div>
        <button
          onClick={fetchMetrics}
          disabled={isLoading}
          className="flex items-center gap-1.5 px-3 py-1.5 text-xs font-medium text-gray-400
            bg-gray-800/60 hover:bg-gray-700/60 hover:text-gray-200 rounded-lg
            border border-white/5 hover:border-white/10 transition-all duration-200
            disabled:opacity-40 disabled:cursor-not-allowed"
        >
          <svg
            className={`w-3.5 h-3.5 ${isLoading ? 'animate-spin' : ''}`}
            fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="M16.023 9.348h4.992v-.001M2.985 19.644v-4.992m0 0h4.992m-4.993 0 3.181 3.183a8.25 8.25 0 0 0 13.803-3.7M4.031 9.865a8.25 8.25 0 0 1 13.803-3.7l3.181 3.182" />
          </svg>
          {isLoading ? '刷新中…' : '刷新'}
        </button>
      </div>

      {/* Error overlay when cached data exists */}
      {error && <ErrorBanner message={error} onRetry={fetchMetrics} />}

      {/* Cards Grid */}
      <motion.div
        variants={containerVariants}
        initial="hidden"
        animate="visible"
        className="grid grid-cols-1 md:grid-cols-2 gap-4"
      >
        {/* ── 1. Cache Hit Rate ── */}
        <StatCard title="缓存命中率">
          <div className="flex items-center justify-center py-2">
            <div className="relative flex items-center justify-center">
              <RingProgress value={metrics.cacheHitRate} label="全局命中率" />
            </div>
          </div>
          <div className="flex justify-center gap-6 mt-2 text-xs text-gray-500">
            <span>
              近期: <span className="font-mono text-gray-300">{metrics.recentHitRate.toFixed(1)}%</span>
            </span>
          </div>
        </StatCard>

        {/* ── 2. Token Statistics ── */}
        <StatCard title="Token 统计">
          <MetricRow label="总 Token 数" value={totalTokens.toLocaleString()} />
          <MetricRow label="输入 Token" value={metrics.totalHitTokens.toLocaleString()} accent />
          <MetricRow label="输出 Token" value={metrics.totalMissTokens.toLocaleString()} accent />
          <div className="border-t border-white/5 my-2" />
          <MetricRow label="命中 Token" value={metrics.totalHitTokens.toLocaleString()} />
          <MetricRow label="未命中 Token" value={metrics.totalMissTokens.toLocaleString()} />
          <TokenBar hit={metrics.totalHitTokens} miss={metrics.totalMissTokens} />
        </StatCard>

        {/* ── 3. Request & Session Stats ── */}
        <StatCard title="请求统计">
          <div className="grid grid-cols-2 gap-4">
            <div className="flex flex-col items-center justify-center p-3 rounded-lg bg-gray-900/40">
              <span className="text-2xl font-bold text-white tabular-nums">
                {metrics.totalRequests.toLocaleString()}
              </span>
              <span className="text-xs text-gray-500 mt-1">总请求数</span>
            </div>
            <div className="flex flex-col items-center justify-center p-3 rounded-lg bg-gray-900/40">
              <span className="text-2xl font-bold text-white tabular-nums">
                {metrics.activeSessions}
              </span>
              <span className="text-xs text-gray-500 mt-1">活跃会话</span>
            </div>
          </div>
        </StatCard>

        {/* ── 4. Latency Statistics ── */}
        <StatCard title="延迟统计">
          <MetricRowLatency label="平均响应" value={metrics.avgLatency} />
          <div className="border-t border-white/5 my-1.5" />
          <MetricRowLatency label="P50" value={metrics.p50Latency} />
          <MetricRowLatency label="P95" value={metrics.p95Latency} />
          <MetricRowLatency label="P99" value={metrics.p99Latency} />
          <div className="mt-3 pt-2 border-t border-white/5">
            <div className="flex items-center gap-1.5 text-[11px] text-gray-600">
              <div className="w-2 h-2 rounded-full bg-emerald-400" />
              &lt;100ms
              <div className="w-2 h-2 rounded-full bg-amber-400 ml-3" />
              100-500ms
              <div className="w-2 h-2 rounded-full bg-rose-400 ml-3" />
              &gt;500ms
            </div>
          </div>
        </StatCard>

        {/* ── 5. Cost Statistics ── */}
        <StatCard title="成本统计" className="md:col-span-2">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div className="flex flex-col p-3 rounded-lg bg-gray-900/40">
              <span className="text-xs text-gray-500 mb-1">总成本</span>
              <span className="text-2xl font-bold text-white tabular-nums">
                ${metrics.totalCost.toFixed(4)}
              </span>
            </div>
            <div className="flex flex-col p-3 rounded-lg bg-gray-900/40">
              <span className="text-xs text-gray-500 mb-1">本次会话成本</span>
              <span className="text-2xl font-bold text-purple-400 tabular-nums">
                ${metrics.sessionCost.toFixed(4)}
              </span>
            </div>
          </div>
        </StatCard>
      </motion.div>
    </div>
  );
}

export default PerformanceDashboard;
