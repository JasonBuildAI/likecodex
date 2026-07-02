'use client';

import React, { useRef, useState, useCallback, useEffect } from 'react';
import { motion, AnimatePresence, LayoutGroup } from 'framer-motion';
import { useAppStore, type OpenFile } from '@/lib/store';

// ── Context Menu ──────────────────────────────────────────────────────

interface ContextMenuState {
  visible: boolean;
  x: number;
  y: number;
  file: OpenFile | null;
}

const ContextMenu: React.FC<{
  state: ContextMenuState;
  onClose: () => void;
  onCloseOthers: (path: string) => void;
  onCloseAll: () => void;
  onCloseRight: (path: string) => void;
}> = ({ state, onClose, onCloseOthers, onCloseAll, onCloseRight }) => {
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        onClose();
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, [onClose]);

  if (!state.visible || !state.file) return null;

  const actions = [
    { label: 'Close', shortcut: 'Middle click', action: () => { useAppStore.getState().closeFile(state.file!.path); onClose(); } },
    { label: 'Close Others', shortcut: '', action: () => { onCloseOthers(state.file!.path); onClose(); } },
    { label: 'Close to the Right', shortcut: '', action: () => { onCloseRight(state.file!.path); onClose(); } },
    { label: 'Close All', shortcut: '', action: () => { onCloseAll(); onClose(); } },
  ];

  return (
    <div
      ref={ref}
      className="fixed z-[100] bg-surface border border-border rounded-lg shadow-xl py-1 min-w-[160px]"
      style={{ left: state.x, top: state.y }}
    >
      {actions.map((a) => (
        <button
          key={a.label}
          onClick={a.action}
          className="w-full flex items-center justify-between px-3 py-1.5 text-xs text-foreground hover:bg-accent/10 transition-colors text-left"
        >
          <span>{a.label}</span>
          {a.shortcut && <span className="text-[9px] text-muted ml-4">{a.shortcut}</span>}
        </button>
      ))}
    </div>
  );
};

// ── Tab Component ─────────────────────────────────────────────────────

const EditorTab: React.FC<{
  file: OpenFile;
  isActive: boolean;
  onSelect: () => void;
  onClose: () => void;
  onContextMenu: (e: React.MouseEvent) => void;
  onDragStart: (e: React.DragEvent) => void;
  onDragOver: (e: React.DragEvent) => void;
  onDragEnd: (e: React.DragEvent) => void;
  onDrop: (e: React.DragEvent) => void;
}> = ({ file, isActive, onSelect, onClose, onContextMenu, onDragStart, onDragOver, onDragEnd, onDrop }) => {
  return (
    <motion.div
      layout
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.95 }}
      draggable
      onDragStart={onDragStart}
      onDragOver={onDragOver}
      onDragEnd={onDragEnd}
      onDrop={onDrop}
      onClick={onSelect}
      onContextMenu={onContextMenu}
      onMouseDown={(e) => {
        if (e.button === 1) { e.preventDefault(); onClose(); }
      }}
      className={`group flex items-center gap-1 px-3 py-1.5 text-xs cursor-pointer border-r border-border shrink-0 select-none transition-colors ${
        isActive
          ? 'bg-background text-foreground border-t-2 border-t-primary'
          : 'bg-surface/50 text-muted hover:bg-accent/5'
      }`}
    >
      {file.modified && <span className="text-primary text-[10px]">&#9679;</span>}
      <span className="truncate max-w-[120px]">{file.name}</span>
      <button
        className="ml-1 text-muted/50 hover:text-foreground rounded p-0.5 leading-none text-[10px] hover:bg-accent/20 opacity-0 group-hover:opacity-100 transition-opacity"
        onClick={(e) => { e.stopPropagation(); onClose(); }}
        title="Close"
      >&#10005;</button>
    </motion.div>
  );
};

// ── Tab Bar ───────────────────────────────────────────────────────────

export function EditorTabBar() {
  const openFiles = useAppStore((s) => s.openFiles);
  const activeFilePath = useAppStore((s) => s.activeFilePath);
  const setActiveFile = useAppStore((s) => s.setActiveFile);
  const closeFile = useAppStore((s) => s.closeFile);
  const scrollRef = useRef<HTMLDivElement>(null);

  const [contextMenu, setContextMenu] = useState<ContextMenuState>({
    visible: false, x: 0, y: 0, file: null,
  });

  const dragIndexRef = useRef<number | null>(null);

  const reorderFiles = useCallback((fromIdx: number, toIdx: number) => {
    const { openFiles: files } = useAppStore.getState();
    const updated = [...files];
    const [moved] = updated.splice(fromIdx, 1);
    updated.splice(toIdx, 0, moved);
    useAppStore.setState({ openFiles: updated });
  }, []);

  const handleDragStart = (e: React.DragEvent, index: number) => {
    dragIndexRef.current = index;
    e.dataTransfer.effectAllowed = 'move';
    if (e.currentTarget instanceof HTMLElement) {
      e.dataTransfer.setDragImage(e.currentTarget, 0, 0);
    }
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
  };

  const handleDrop = (e: React.DragEvent, index: number) => {
    e.preventDefault();
    if (dragIndexRef.current !== null && dragIndexRef.current !== index) {
      reorderFiles(dragIndexRef.current, index);
    }
    dragIndexRef.current = null;
  };

  const handleDragEnd = () => { dragIndexRef.current = null; };

  const handleWheel = (e: React.WheelEvent) => {
    if (scrollRef.current) {
      scrollRef.current.scrollLeft += e.deltaY;
      e.preventDefault();
    }
  };

  const handleContextMenu = (e: React.MouseEvent, file: OpenFile) => {
    e.preventDefault();
    setContextMenu({ visible: true, x: e.clientX, y: e.clientY, file });
  };

  const closeOthers = (path: string) => {
    openFiles.forEach((f) => { if (f.path !== path) closeFile(f.path); });
  };

  const closeRight = (path: string) => {
    const idx = openFiles.findIndex((f) => f.path === path);
    if (idx >= 0) openFiles.slice(idx + 1).forEach((f) => closeFile(f.path));
  };

  const closeAll = () => { openFiles.forEach((f) => closeFile(f.path)); };

  if (openFiles.length === 0) return null;

  return (
    <>
      <div
        ref={scrollRef}
        onWheel={handleWheel}
        className="flex items-center bg-surface border-b border-border overflow-x-auto shrink-0 scrollbar-thin"
        style={{ scrollbarWidth: 'thin' }}
      >
        <LayoutGroup>
          <AnimatePresence mode="popLayout">
            {openFiles.map((file, index) => (
              <EditorTab
                key={file.path}
                file={file}
                isActive={file.path === activeFilePath}
                onSelect={() => setActiveFile(file.path)}
                onClose={() => closeFile(file.path)}
                onContextMenu={(e) => handleContextMenu(e, file)}
                onDragStart={(e) => handleDragStart(e, index)}
                onDragOver={handleDragOver}
                onDragEnd={handleDragEnd}
                onDrop={(e) => handleDrop(e, index)}
              />
            ))}
          </AnimatePresence>
        </LayoutGroup>
      </div>

      <ContextMenu
        state={contextMenu}
        onClose={() => setContextMenu((prev) => ({ ...prev, visible: false }))}
        onCloseOthers={closeOthers}
        onCloseAll={closeAll}
        onCloseRight={closeRight}
      />
    </>
  );
}
