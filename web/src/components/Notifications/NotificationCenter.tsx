'use client';

import { useState, useCallback, useMemo } from 'react';

// ── Types ──────────────────────────────────────────────────────────────

export interface Notification {
  id: string;
  type: 'info' | 'success' | 'warning' | 'error';
  title: string;
  message: string;
  timestamp: number;
  read: boolean;
  action?: {
    label: string;
    onClick: () => void;
  };
}

interface NotificationCenterProps {
  notifications: Notification[];
  onMarkRead: (id: string) => void;
  onMarkAllRead: () => void;
  onClear: (id: string) => void;
  onClearAll: () => void;
  onClose?: () => void;
}

// ── Type config ────────────────────────────────────────────────────────

const TYPE_CONFIG: Record<string, { icon: string; dot: string; border: string; bg: string }> = {
  info: {
    icon: 'ℹ️',
    dot: 'bg-blue-500',
    border: 'border-blue-500/20',
    bg: 'bg-blue-500/5',
  },
  success: {
    icon: '✅',
    dot: 'bg-green-500',
    border: 'border-green-500/20',
    bg: 'bg-green-500/5',
  },
  warning: {
    icon: '⚠️',
    dot: 'bg-yellow-500',
    border: 'border-yellow-500/20',
    bg: 'bg-yellow-500/5',
  },
  error: {
    icon: '❌',
    dot: 'bg-red-500',
    border: 'border-red-500/20',
    bg: 'bg-red-500/5',
  },
};

// ── Helpers ────────────────────────────────────────────────────────────

function formatTimeAgo(timestamp: number): string {
  const diff = Date.now() - timestamp;
  const mins = Math.floor(diff / 60000);
  if (mins < 1) return 'just now';
  if (mins < 60) return `${mins}m ago`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  return `${days}d ago`;
}

// ── Main Component ─────────────────────────────────────────────────────

export function NotificationCenter({
  notifications,
  onMarkRead,
  onMarkAllRead,
  onClear,
  onClearAll,
  onClose,
}: NotificationCenterProps) {
  const [filter, setFilter] = useState<'all' | 'unread' | keyof typeof TYPE_CONFIG>('all');

  const filtered = useMemo(() => {
    if (filter === 'all') return notifications;
    if (filter === 'unread') return notifications.filter((n) => !n.read);
    return notifications.filter((n) => n.type === filter);
  }, [notifications, filter]);

  const unreadCount = useMemo(
    () => notifications.filter((n) => !n.read).length,
    [notifications]
  );

  const handleNotificationClick = useCallback(
    (n: Notification) => {
      if (!n.read) onMarkRead(n.id);
      if (n.action) n.action.onClick();
    },
    [onMarkRead]
  );

  return (
    <div className="flex flex-col h-full border border-border/30 rounded-lg bg-surface/30 overflow-hidden max-w-sm">
      {/* Header */}
      <div className="px-4 py-3 border-b border-border/30">
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2">
            <span className="text-[10px] font-medium text-muted uppercase tracking-wider">
              Notifications
            </span>
            {unreadCount > 0 && (
              <span className="text-[8px] px-1.5 py-0.5 rounded-full bg-primary/20 text-primary font-medium">
                {unreadCount}
              </span>
            )}
          </div>
          <div className="flex items-center gap-1">
            {unreadCount > 0 && (
              <button
                onClick={onMarkAllRead}
                className="text-[8px] text-primary hover:text-primary/80 px-1.5 py-0.5 rounded"
              >
                Mark all read
              </button>
            )}
            {notifications.length > 0 && (
              <button
                onClick={onClearAll}
                className="text-[8px] text-muted/50 hover:text-muted px-1.5 py-0.5 rounded"
              >
                Clear all
              </button>
            )}
            {onClose && (
              <button onClick={onClose} className="text-muted/50 hover:text-muted p-0.5 ml-1">
                <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            )}
          </div>
        </div>

        {/* Filter chips */}
        <div className="flex flex-wrap gap-1">
          {(['all', 'unread', 'info', 'success', 'warning', 'error'] as const).map((f) => {
            const count = f === 'all'
              ? notifications.length
              : f === 'unread'
                ? unreadCount
                : notifications.filter((n) => n.type === f).length;

            return (
              <button
                key={f}
                onClick={() => setFilter(f)}
                className={`text-[8px] px-2 py-0.5 rounded-full border transition-colors capitalize ${
                  filter === f
                    ? 'bg-primary/10 text-primary border-primary/20'
                    : 'border-border/30 text-muted/50 hover:text-muted'
                }`}
              >
                {f}{count > 0 ? ` (${count})` : ''}
              </button>
            );
          })}
        </div>
      </div>

      {/* Notification list */}
      <div className="flex-1 overflow-y-auto">
        {filtered.length === 0 ? (
          <div className="flex flex-col items-center justify-center py-8 text-muted/40">
            <svg className="h-8 w-8 mb-2" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M15 17h5l-1.405-1.405A2.032 2.032 0 0118 14.158V11a6.002 6.002 0 00-4-5.659V5a2 2 0 10-4 0v.341C7.67 6.165 6 8.388 6 11v3.159c0 .538-.214 1.055-.595 1.436L4 17h5m6 0v1a3 3 0 11-6 0v-1m6 0H9" />
            </svg>
            <p className="text-[10px]">No notifications</p>
          </div>
        ) : (
          <div className="divide-y divide-border/10">
            {filtered.map((n) => {
              const config = TYPE_CONFIG[n.type] || TYPE_CONFIG.info;

              return (
                <div
                  key={n.id}
                  onClick={() => handleNotificationClick(n)}
                  className={`px-4 py-2.5 cursor-pointer transition-colors ${
                    !n.read ? config.bg : ''
                  } hover:bg-accent/5`}
                >
                  <div className="flex items-start gap-2.5">
                    {/* Read indicator */}
                    {!n.read ? (
                      <span className={`inline-block h-2 w-2 rounded-full shrink-0 mt-1 ${config.dot}`} />
                    ) : (
                      <span className="inline-block h-2 w-2 rounded-full shrink-0 mt-1 bg-transparent border border-border/30" />
                    )}

                    {/* Icon */}
                    <span className="text-xs shrink-0 mt-0.5">{config.icon}</span>

                    {/* Content */}
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center justify-between gap-1">
                        <span className={`text-[10px] font-medium truncate ${!n.read ? 'text-foreground' : 'text-muted/70'}`}>
                          {n.title}
                        </span>
                        <span className="text-[8px] text-muted/40 shrink-0">{formatTimeAgo(n.timestamp)}</span>
                      </div>
                      <p className={`text-[9px] mt-0.5 line-clamp-2 ${!n.read ? 'text-muted/80' : 'text-muted/50'}`}>
                        {n.message}
                      </p>

                      {/* Action button */}
                      {n.action && (
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            n.action?.onClick();
                          }}
                          className="text-[8px] text-primary hover:text-primary/80 mt-1"
                        >
                          {n.action.label}
                        </button>
                      )}
                    </div>

                    {/* Clear button */}
                    <button
                      onClick={(e) => {
                        e.stopPropagation();
                        onClear(n.id);
                      }}
                      className="text-muted/20 hover:text-muted/60 shrink-0 mt-0.5 opacity-0 group-hover:opacity-100 transition-opacity"
                      title="Dismiss"
                    >
                      <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                      </svg>
                    </button>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

export default NotificationCenter;
