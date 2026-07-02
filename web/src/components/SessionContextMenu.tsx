'use client';

import React, { useEffect, useRef, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useSessionStore } from '@/stores/sessionStore';

// ── Types ──────────────────────────────────────────────────────────────

export interface ContextMenuAction {
  label: string;
  icon?: React.ReactNode;
  shortcut?: string;
  danger?: boolean;
  divider?: boolean;
  action: (sessionId: string) => void;
}

interface SessionContextMenuProps {
  /** 自定义操作列表，不传则使用默认 */
  actions?: ContextMenuAction[];
  onClose?: () => void;
}

// ── Default Icons ──────────────────────────────────────────────────────

const CloseIcon = () => (
  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
  </svg>
);

const CloseOthersIcon = () => (
  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M9.75 9.75l4.5 4.5m0-4.5l-4.5 4.5M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
  </svg>
);

const CloseAllIcon = () => (
  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
  </svg>
);

const RenameIcon = () => (
  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L10.582 16.07a4.5 4.5 0 01-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 011.13-1.897l8.932-8.931zm0 0L19.5 7.125M18 14v4.75A2.25 2.25 0 0115.75 21H5.25A2.25 2.25 0 013 18.75V8.25A2.25 2.25 0 015.25 6H10" />
  </svg>
);

const CopyIcon = () => (
  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M15.666 3.888A2.25 2.25 0 0013.5 2.25h-3c-1.03 0-1.9.693-2.166 1.638m7.332 0c.055.194.084.4.084.612v0a.75.75 0 01-.75.75H9a.75.75 0 01-.75-.75v0c0-.212.03-.418.084-.612m7.332 0c.646.049 1.288.11 1.927.184 1.1.128 1.907 1.077 1.907 2.185V19.5a2.25 2.25 0 01-2.25 2.25H6.75A2.25 2.25 0 014.5 19.5V6.257c0-1.108.806-2.057 1.907-2.185a48.208 48.208 0 011.927-.184" />
  </svg>
);

const ForkIcon = () => (
  <svg className="w-3.5 h-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
    <path strokeLinecap="round" strokeLinejoin="round" d="M7.5 21L3 16.5m0 0L7.5 12M3 16.5h13.5m0-13.5L21 7.5m0 0L16.5 12M21 7.5H7.5" />
  </svg>
);

// ── Default Actions ────────────────────────────────────────────────────

const defaultActions: ContextMenuAction[] = [
  { label: '关闭', icon: <CloseIcon />, action: (id) => useSessionStore.getState().removeSession(id) },
  { label: '关闭其他', icon: <CloseOthersIcon />, action: (id) => {
    const { sessions, setActiveSession } = useSessionStore.getState();
    const toRemove = sessions.filter((s) => s.id !== id).map((s) => s.id);
    toRemove.forEach((sid) => useSessionStore.getState().removeSession(sid));
  }},
  { label: '关闭全部', icon: <CloseAllIcon />, action: () => {
    const { sessions } = useSessionStore.getState();
    sessions.forEach((s) => useSessionStore.getState().removeSession(s.id));
  }},
  { label: '', icon: undefined, divider: true, action: () => {} },
  { label: '重命名', icon: <RenameIcon />, action: (id) => useSessionStore.getState().setRenamingSession(id) },
  { label: '复制 ID', icon: <CopyIcon />, action: (id) => navigator.clipboard.writeText(id) },
  { label: '创建 Fork', icon: <ForkIcon />, action: (id) => {
    // Fork 事件通过 window.dispatchEvent 抛出，由外部 handler 消费
    window.dispatchEvent(new CustomEvent('likecodex:fork-session', { detail: { sessionId: id } }));
  }},
];

// ── Component ──────────────────────────────────────────────────────────

export const SessionContextMenu: React.FC<SessionContextMenuProps> = ({
  actions = defaultActions,
  onClose,
}) => {
  const menuRef = useRef<HTMLDivElement>(null);
  const sessionId = useSessionStore((s) => s.contextMenuSessionId);
  const position = useSessionStore((s) => s.contextMenuPosition);
  const isOpen = sessionId !== null && position !== null;

  const close = useCallback(() => {
    useSessionStore.getState().closeContextMenu();
    onClose?.();
  }, [onClose]);

  // 点击外部关闭
  useEffect(() => {
    if (!isOpen) return;
    const handleClickOutside = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        close();
      }
    };
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') close();
    };
    // 延迟注册避免触发菜单打开时的点击事件
    const timer = setTimeout(() => {
      document.addEventListener('mousedown', handleClickOutside);
      document.addEventListener('keydown', handleEscape);
    }, 0);
    return () => {
      clearTimeout(timer);
      document.removeEventListener('mousedown', handleClickOutside);
      document.removeEventListener('keydown', handleEscape);
    };
  }, [isOpen, close]);

  // 菜单位置自适应 (避免溢出视口)
  const adjustedPosition = useCallback(() => {
    if (!position) return { x: 0, y: 0 };
    const menuWidth = 180;
    const menuHeight = actions.filter((a) => !a.divider).length * 32 + 8;
    const vw = window.innerWidth;
    const vh = window.innerHeight;
    return {
      x: Math.min(position.x, vw - menuWidth - 16),
      y: Math.min(position.y, vh - menuHeight - 16),
    };
  }, [position, actions.length]);

  if (!isOpen) return null;

  const pos = adjustedPosition();

  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          ref={menuRef}
          initial={{ opacity: 0, scale: 0.95, y: -4 }}
          animate={{ opacity: 1, scale: 1, y: 0 }}
          exit={{ opacity: 0, scale: 0.95, y: -4 }}
          transition={{ type: 'spring', stiffness: 400, damping: 30 }}
          style={{
            position: 'fixed',
            left: pos.x,
            top: pos.y,
            zIndex: 9999,
          }}
          className="min-w-[160px] py-1.5 bg-gray-800 border border-gray-700 rounded-lg shadow-2xl shadow-black/50"
        >
          {actions.map((item, idx) => {
            if (item.divider) {
              return (
                <div
                  key={`divider-${idx}`}
                  className="mx-2 my-1 h-px bg-gray-700"
                />
              );
            }
            return (
              <ContextMenuItem
                key={`${item.label}-${idx}`}
                label={item.label}
                icon={item.icon}
                shortcut={item.shortcut}
                danger={item.danger}
                onClick={(e) => {
                  e.stopPropagation();
                  item.action(sessionId!);
                  close();
                }}
              />
            );
          })}
        </motion.div>
      )}
    </AnimatePresence>
  );
};

// ── Menu Item ──────────────────────────────────────────────────────────

interface ContextMenuItemProps {
  label: string;
  icon?: React.ReactNode;
  shortcut?: string;
  danger?: boolean;
  onClick: (e: React.MouseEvent) => void;
}

const ContextMenuItem: React.FC<ContextMenuItemProps> = ({
  label,
  icon,
  shortcut,
  danger,
  onClick,
}) => (
  <motion.button
    whileHover={{ x: 2 }}
    onClick={onClick}
    className={`
      w-full flex items-center gap-2.5 px-3 py-1.5 text-xs text-left transition-colors
      ${danger
        ? 'text-red-400 hover:bg-red-500/10'
        : 'text-gray-300 hover:bg-gray-700/60 hover:text-white'
      }
    `}
  >
    {icon && (
      <span className="flex-shrink-0 w-4 flex items-center justify-center text-gray-400">
        {icon}
      </span>
    )}
    <span className="flex-1 truncate">{label}</span>
    {shortcut && (
      <span className="flex-shrink-0 text-[10px] text-gray-500 ml-4">
        {shortcut}
      </span>
    )}
  </motion.button>
);

export default SessionContextMenu;
