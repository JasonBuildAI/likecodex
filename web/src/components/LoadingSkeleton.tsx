'use client';

import { memo } from 'react';

// ── Skeleton base ───────────────────────────────────────────────────────
interface SkeletonProps {
  className?: string;
}

function Skeleton({ className = '' }: SkeletonProps) {
  return (
    <div
      className={`animate-shimmer rounded-md ${className}`}
    />
  );
}

// ── Message Skeleton ────────────────────────────────────────────────────
export const MessageSkeleton = memo(function MessageSkeleton({
  isUser = false,
}: {
  isUser?: boolean;
}) {
  return (
    <div
      className={`flex gap-3 ${isUser ? 'flex-row-reverse' : ''} mb-4`}
    >
      {/* Avatar */}
      <Skeleton className="w-7 h-7 rounded-full shrink-0" />

      {/* Content */}
      <div
        className={`flex-1 space-y-2 ${
          isUser ? 'items-end' : 'items-start'
        }`}
      >
        <Skeleton className="h-3 w-16" />
        <Skeleton className="h-4 w-full max-w-[80%]" />
        <Skeleton className="h-4 w-full max-w-[60%]" />
        {!isUser && (
          <>
            <Skeleton className="h-4 w-full max-w-[70%]" />
            <Skeleton className="h-20 w-full rounded-lg" />
          </>
        )}
      </div>
    </div>
  );
});

// ── Chat Panel Skeleton ────────────────────────────────────────────────
export function ChatPanelSkeleton() {
  return (
    <div className="p-4 space-y-6">
      <MessageSkeleton />
      <MessageSkeleton isUser />
      <MessageSkeleton />
      <MessageSkeleton isUser />
      <MessageSkeleton />
    </div>
  );
}

// ── Sidebar Skeleton ────────────────────────────────────────────────────
export function SidebarSkeleton() {
  return (
    <div className="p-3 space-y-3">
      <Skeleton className="h-4 w-24" />
      <div className="space-y-2 mt-4">
        {[1, 2, 3, 4, 5].map((i) => (
          <div key={i} className="flex items-center gap-2">
            <Skeleton className="h-4 w-4" />
            <Skeleton className="h-3 flex-1" />
          </div>
        ))}
      </div>
      <div className="mt-6 space-y-2">
        <Skeleton className="h-4 w-20" />
        {[1, 2, 3].map((i) => (
          <div key={i} className="space-y-1">
            <Skeleton className="h-3 w-full" />
            <Skeleton className="h-3 w-3/4" />
          </div>
        ))}
      </div>
    </div>
  );
}

// ── Tool Call Card Skeleton ─────────────────────────────────────────────
export function ToolCallSkeleton() {
  return (
    <div className="rounded-lg border border-border/50 p-3 space-y-2">
      <div className="flex items-center gap-2">
        <Skeleton className="h-4 w-4 rounded" />
        <Skeleton className="h-3 w-24" />
      </div>
      <Skeleton className="h-12 w-full rounded" />
    </div>
  );
}

// ── Stats Card Skeleton ─────────────────────────────────────────────────
export function StatsCardSkeleton() {
  return (
    <div className="rounded-lg border border-border/50 p-4 space-y-3">
      <Skeleton className="h-3 w-20" />
      <Skeleton className="h-8 w-16" />
      <Skeleton className="h-2 w-full" />
    </div>
  );
}

// ── Editor Skeleton ─────────────────────────────────────────────────────
export function EditorSkeleton() {
  return (
    <div className="h-full flex flex-col">
      {/* Tabs */}
      <div className="flex items-center gap-1 px-2 py-1 border-b border-border/50 bg-surface/30">
        <Skeleton className="h-6 w-32 rounded" />
        <Skeleton className="h-6 w-24 rounded" />
      </div>
      {/* Editor lines */}
      <div className="flex-1 p-4 space-y-2">
        {[1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map((i) => (
          <div key={i} className="flex items-center gap-4">
            <Skeleton className="h-3 w-8 shrink-0" />
            <Skeleton
              className="h-3"
              style={{ width: `${Math.random() * 40 + 30}%` }}
            />
          </div>
        ))}
      </div>
    </div>
  );
}
