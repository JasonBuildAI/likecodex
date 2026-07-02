'use client';

import React, {
  useRef,
  useState,
  useCallback,
  useEffect,
} from 'react';
import { motion, AnimatePresence, LayoutGroup } from 'framer-motion';
import { useSessionStore, type SessionInfo } from '@/stores/sessionStore';
import { SessionContextMenu, type ContextMenuAction } from './SessionContextMenu';

// ── Status Indicator ───────────────────────────────────────────────────

const StatusDot: React.FC<{ status: SessionInfo['status'] }> = ({ status }) => {
  const colors: Record<SessionInfo['status'], string> = {
    active: 'bg-emerald-500',
    streaming: 'bg-blue-500',
    error: 'bg-red-500',
    idle: 'bg-gray-500',
  };
  const animate = status === 'streaming';

  return (
    <motion.span
      className={`inline-block w-2 h-2 rounded-full ${colors[status]} flex-shrink-0`}
      animate={animate ? { scale: [1, 1.3, 1], opacity: [1, 0.7, 1] } : undefined}
      transition={animate ? { repeat: Infinity, duration: 1.2, ease: 'easeInOut' } : undefined}
    />
  );
};

// ── Close Button ───────────────────────────────────────────────────────

const CloseButton: React.FC<{ onClick: (e: React.MouseEvent) => void }> = ({ onClick }) => (
  <motion.button
    whileHover={{ scale: 1.15 }}
    whileTap={{ scale: 0.9 }}
    onClick={(e) => {
      e.stopPropagation();
      onClick(e);
    }}
    className="p-0.5 rounded hover:bg-gray-600/50 text-gray-400 hover:text-gray-200 transition-colors flex-shrink-0"
    title="关闭会话"
  >
    <svg className="w-3 h-3" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
    </svg>
  </motion.button>
);

// ── New Session Button ─────────────────────────────────────────────────

const NewSessionButton: React.FC<{ onClick: () => void }> = ({ onClick }) => (
  <motion.button
    whileHover={{ scale: 1.08 }}
    whileTap={{ scale: 0.92 }}
    onClick={onClick}
    className="flex items-center justify-center w-7 h-7 rounded-md text-gray-400 hover:text-white hover:bg-gray-700/60 transition-colors flex-shrink-0"
    title="新建会话"
  >
    <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
      <path strokeLinecap="round" strokeLinejoin="round" d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
    </svg>
  </motion.button>
);

// ── Session Tab ────────────────────────────────────────────────────────

interface SessionTabProps {
  session: SessionInfo;
  isActive: boolean;
  isDragging: boolean;
  onActivate: () => void;
  onClose: (e: React.MouseEvent) => void;
  onContextMenu: (e: React.MouseEvent) => void;
  onDragStart: (e: React.DragEvent) => void;
  onDragOver: (e: React.DragEvent) => void;
  onDragEnd: (e: React.DragEvent) => void;
  onDrop: (e: React.DragEvent) => void;
  onRename: (name: string) => void;
  isRenaming: boolean;
  onStartRename: () => void;
  onCancelRename: () => void;
}

const SessionTab: React.FC<SessionTabProps> = ({
  session,
  isActive,
  isDragging,
  onActivate,
  onClose,
  onContextMenu,
  onDragStart,
  onDragOver,
  onDragEnd,
  onDrop,
  onRename,
  isRenaming,
  onStartRename,
  onCancelRename,
}) => {
  const inputRef = useRef<HTMLInputElement>(null);
  const [editValue, setEditValue] = useState(session.name);

  useEffect(() => {
    if (isRenaming && inputRef.current) {
      inputRef.current.focus();
      inputRef.current.select();
    }
  }, [isRenaming]);

  useEffect(() => {
    setEditValue(session.name);
  }, [session.name]);

  const handleRenameSubmit = useCallback(() => {
    const trimmed = editValue.trim();
    if (trimmed && trimmed !== session.name) {
      onRename(trimmed);
    }
    onCancelRename();
  }, [editValue, session.name, onRename, onCancelRename]);

  const handleRenameKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'Enter') {
        handleRenameSubmit();
      } else if (e.key === 'Escape') {
        setEditValue(session.name);
        onCancelRename();
      }
    },
    [handleRenameSubmit, session.name, onCancelRename]
  );

  return (
    <motion.div
      layout
      initial={{ opacity: 0, scale: 0.9, x: -10 }}
      animate={{
        opacity: 1,
        scale: 1,
        x: 0,
        transition: { type: 'spring', stiffness: 400, damping: 28 },
      }}
      exit={{ opacity: 0, scale: 0.9, x: 10, transition: { duration: 0.15 } }}
      draggable
      onDragStart={onDragStart}
      onDragOver={onDragOver}
      onDragEnd={onDragEnd}
      onDrop={onDrop}
      onClick={onActivate}
      onContextMenu={onContextMenu}
      onDoubleClick={onStartRename}
      style={{ opacity: isDragging ? 0.4 : 1 }}
      className={`
        group relative flex items-center gap-1.5 px-2.5 py-1.5 cursor-pointer select-none
        transition-colors rounded-t-md text-xs font-medium min-w-0 shrink-0
        ${isActive
          ? 'bg-gray-800 text-white shadow-sm border-t border-l border-r border-gray-700'
          : 'bg-gray-900/70 text-gray-400 hover:text-gray-200 hover:bg-gray-800/80 border-t border-l border-r border-transparent hover:border-gray-700/50'
        }
      `}
    >
      {/* 状态指示点 */}
      <StatusDot status={session.status} />

      {/* 会话名称 / 重命名输入 */}
      <div className="flex-1 min-w-0 max-w-[140px]">
        {isRenaming ? (
          <input
            ref={inputRef}
            type="text"
            value={editValue}
            onChange={(e) => setEditValue(e.target.value)}
            onBlur={handleRenameSubmit}
            onKeyDown={handleRenameKeyDown}
            onClick={(e) => e.stopPropagation()}
            className="w-full bg-gray-700 text-white text-[11px] px-1 py-0.5 rounded border border-blue-500/60 outline-none"
          />
        ) : (
          <span className="block truncate text-[11px]">{session.name}</span>
        )}
      </div>

      {/* 关闭按钮（hover 时显示或始终显示在当前活跃 tab） */}
      <div className={`flex-shrink-0 ${isActive ? 'opacity-100' : 'opacity-0 group-hover:opacity-100'} transition-opacity`}>
        <CloseButton onClick={onClose} />
      </div>
    </motion.div>
  );
};

// ── Tab Bar ────────────────────────────────────────────────────────────

interface SessionTabBarProps {
  /** 新建会话回调 */
  onNewSession?: () => void;
  /** 切换会话回调 */
  onSessionSelect?: (sessionId: string) => void;
  /** 自定义右键菜单操作，不传则使用默认 */
  contextMenuActions?: ContextMenuAction[];
  /** 自定义渲染每个 tab 右侧额外内容 */
  renderTabExtra?: (session: SessionInfo) => React.ReactNode;
}

export const SessionTabBar: React.FC<SessionTabBarProps> = ({
  onNewSession,
  onSessionSelect,
  contextMenuActions,
  renderTabExtra,
}) => {
  const scrollRef = useRef<HTMLDivElement>(null);
  const dragItemIndex = useRef<number | null>(null);
  const dragOverIndex = useRef<number | null>(null);

  const sessions = useSessionStore((s) => s.sessions);
  const sessionOrder = useSessionStore((s) => s.sessionOrder);
  const activeSessionId = useSessionStore((s) => s.activeSessionId);
  const renamingSessionId = useSessionStore((s) => s.renamingSessionId);
  const setActiveSession = useSessionStore((s) => s.setActiveSession);
  const removeSession = useSessionStore((s) => s.removeSession);
  const reorderSessions = useSessionStore((s) => s.reorderSessions);
  const renameSession = useSessionStore((s) => s.renameSession);
  const openContextMenu = useSessionStore((s) => s.openContextMenu);
  const setRenamingSession = useSessionStore((s) => s.setRenamingSession);

  // 按 sessionOrder 排序
  const orderedSessions = sessionOrder
    .map((id) => sessions.find((s) => s.id === id))
    .filter((s): s is SessionInfo => s !== undefined);

  // ── 会话切换 ─────────────────────────────────────────────────────────

  const handleActivate = useCallback(
    (id: string) => {
      setActiveSession(id);
      onSessionSelect?.(id);
    },
    [setActiveSession, onSessionSelect]
  );

  // ── 关闭 ─────────────────────────────────────────────────────────────

  const handleClose = useCallback(
    (e: React.MouseEvent, id: string) => {
      e.stopPropagation();
      removeSession(id);
    },
    [removeSession]
  );

  // ── 新建会话 ─────────────────────────────────────────────────────────

  const handleNewSession = useCallback(() => {
    onNewSession?.();
  }, [onNewSession]);

  // ── 右键菜单 ─────────────────────────────────────────────────────────

  const handleContextMenu = useCallback(
    (e: React.MouseEvent, id: string) => {
      e.preventDefault();
      openContextMenu(id, e.clientX, e.clientY);
    },
    [openContextMenu]
  );

  // ── 拖拽排序 ─────────────────────────────────────────────────────────

  const handleDragStart = useCallback(
    (e: React.DragEvent, index: number) => {
      dragItemIndex.current = index;
      e.dataTransfer.effectAllowed = 'move';
      // 设置 drag image 样式
      if (e.currentTarget instanceof HTMLElement) {
        e.dataTransfer.setDragImage(e.currentTarget, 0, 0);
      }
    },
    []
  );

  const handleDragOver = useCallback(
    (e: React.DragEvent, index: number) => {
      e.preventDefault();
      e.dataTransfer.dropEffect = 'move';
      dragOverIndex.current = index;
    },
    []
  );

  const handleDrop = useCallback(
    (e: React.DragEvent, index: number) => {
      e.preventDefault();
      if (
        dragItemIndex.current !== null &&
        dragItemIndex.current !== index
      ) {
        reorderSessions(dragItemIndex.current, index);
      }
      dragItemIndex.current = null;
      dragOverIndex.current = null;
    },
    [reorderSessions]
  );

  const handleDragEnd = useCallback(() => {
    dragItemIndex.current = null;
    dragOverIndex.current = null;
  }, []);

  // ── 重命名 ───────────────────────────────────────────────────────────

  const handleRename = useCallback(
    (id: string, name: string) => {
      renameSession(id, name);
    },
    [renameSession]
  );

  // 鼠标滚轮水平滚动
  const handleWheel = useCallback((e: React.WheelEvent) => {
    if (scrollRef.current) {
      scrollRef.current.scrollLeft += e.deltaY;
      e.preventDefault();
    }
  }, []);

  return (
    <>
      <div className="flex items-stretch bg-gray-900 border-b border-gray-700 select-none">
        {/* Tab 列表 - 水平滚动 */}
        <div
          ref={scrollRef}
          onWheel={handleWheel}
          className="flex-1 flex items-end gap-0 overflow-x-auto overflow-y-hidden scrollbar-thin scrollbar-thumb-gray-700 scrollbar-track-transparent pl-1"
          style={{ scrollbarWidth: 'thin' }}
        >
          <LayoutGroup>
            <AnimatePresence mode="popLayout">
              {orderedSessions.map((session, index) => {
                const isDragOver = dragOverIndex.current === index;
                return (
                  <React.Fragment key={session.id}>
                    {/* 拖拽插入指示器 */}
                    {isDragOver && dragItemIndex.current !== index && (
                      <motion.div
                        layoutId={`drop-indicator-${session.id}`}
                        className="w-0.5 h-6 bg-blue-500 rounded-full flex-shrink-0"
                        initial={{ opacity: 0 }}
                        animate={{ opacity: 1 }}
                        exit={{ opacity: 0 }}
                      />
                    )}
                    <SessionTab
                      session={session}
                      isActive={session.id === activeSessionId}
                      isDragging={dragItemIndex.current === index}
                      onActivate={() => handleActivate(session.id)}
                      onClose={(e) => handleClose(e, session.id)}
                      onContextMenu={(e) => handleContextMenu(e, session.id)}
                      onDragStart={(e) => handleDragStart(e, index)}
                      onDragOver={(e) => handleDragOver(e, index)}
                      onDragEnd={handleDragEnd}
                      onDrop={(e) => handleDrop(e, index)}
                      onRename={(name) => handleRename(session.id, name)}
                      isRenaming={renamingSessionId === session.id}
                      onStartRename={() => setRenamingSession(session.id)}
                      onCancelRename={() => setRenamingSession(null)}
                    />
                    {/* 自定义额外内容 */}
                    {renderTabExtra?.(session)}
                  </React.Fragment>
                );
              })}
            </AnimatePresence>
          </LayoutGroup>
        </div>

        {/* 新建会话按钮 */}
        <div className="flex items-center px-1.5 border-l border-gray-700/50">
          <NewSessionButton onClick={handleNewSession} />
        </div>
      </div>

      {/* 右键菜单 */}
      <SessionContextMenu actions={contextMenuActions} />
    </>
  );
};

export default SessionTabBar;
