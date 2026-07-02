'use client';

import React, { useState, useCallback, useRef, useEffect } from 'react';

export type DockPosition = 'left' | 'right' | 'bottom' | 'center';

export interface DockPanel {
  id: string;
  position: DockPosition;
  defaultSize: number;
  minSize: number;
  maxSize?: number;
  collapsible: boolean;
  collapsed: boolean;
  content: React.ReactNode;
  title: string;
  icon?: React.ReactNode;
}

interface DockLayoutProps {
  panels: DockPanel[];
  className?: string;
  onResize?: (id: string, size: number) => void;
  onToggle?: (id: string) => void;
}

/**
 * Draggable dock panel layout system.
 * Supports left, right, bottom, and center panels with resize handles.
 */
export function DockLayout({ panels, className = '', onResize, onToggle }: DockLayoutProps) {
  const centerPanel = panels.find((p) => p.position === 'center');
  const leftPanels = panels.filter((p) => p.position === 'left');
  const rightPanels = panels.filter((p) => p.position === 'right');
  const bottomPanels = panels.filter((p) => p.position === 'bottom');

  return (
    <div className={`flex flex-col h-full ${className}`}>
      <div className="flex flex-1 min-h-0">
        {/* Left panels */}
        {leftPanels.length > 0 && (
          <div className="flex flex-col border-r border-border shrink-0">
            {leftPanels.map((panel) => (
              <DockPanelWrapper
                key={panel.id}
                panel={panel}
                direction="horizontal"
                onResize={onResize}
                onToggle={onToggle}
              />
            ))}
          </div>
        )}

        {/* Center panel */}
        <div className="flex-1 min-w-0 min-h-0 overflow-auto">
          {centerPanel?.content}
        </div>

        {/* Right panels */}
        {rightPanels.length > 0 && (
          <div className="flex flex-col border-l border-border shrink-0">
            {rightPanels.map((panel) => (
              <DockPanelWrapper
                key={panel.id}
                panel={panel}
                direction="horizontal"
                onResize={onResize}
                onToggle={onToggle}
              />
            ))}
          </div>
        )}
      </div>

      {/* Bottom panels */}
      {bottomPanels.length > 0 && (
        <div className="flex flex-col border-t border-border shrink-0">
          {bottomPanels.map((panel) => (
            <DockPanelWrapper
              key={panel.id}
              panel={panel}
              direction="vertical"
              onResize={onResize}
              onToggle={onToggle}
            />
          ))}
        </div>
      )}
    </div>
  );
}

// ── Internal dock panel wrapper with resize handle ──────────────────

interface DockPanelWrapperProps {
  panel: DockPanel;
  direction: 'horizontal' | 'vertical';
  onResize?: (id: string, size: number) => void;
  onToggle?: (id: string) => void;
}

function DockPanelWrapper({ panel, direction, onResize, onToggle }: DockPanelWrapperProps) {
  const [size, setSize] = useState(panel.defaultSize);
  const [isResizing, setIsResizing] = useState(false);
  const panelRef = useRef<HTMLDivElement>(null);

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    setIsResizing(true);
  }, []);

  useEffect(() => {
    if (!isResizing) return;

    const handleMouseMove = (e: MouseEvent) => {
      if (!panelRef.current) return;
      const rect = panelRef.current.parentElement?.getBoundingClientRect();
      if (!rect) return;

      let newSize: number;
      if (direction === 'horizontal') {
        const isRight = panel.position === 'right';
        newSize = isRight ? rect.right - e.clientX : e.clientX - rect.left;
      } else {
        newSize = rect.bottom - e.clientY;
      }
      newSize = Math.max(panel.minSize, Math.min(newSize, panel.maxSize || 600));
      setSize(newSize);
    };

    const handleMouseUp = () => {
      setIsResizing(false);
      onResize?.(panel.id, size);
    };

    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseup', handleMouseUp);
    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isResizing, direction, panel, size, onResize]);

  if (panel.collapsed) {
    return (
      <div className="flex items-center">
        <button
          onClick={() => onToggle?.(panel.id)}
          className="p-1 hover:bg-accent/10 text-muted hover:text-foreground transition-colors"
          title={panel.title}
        >
          {panel.icon}
        </button>
      </div>
    );
  }

  const panelStyle: React.CSSProperties =
    direction === 'horizontal' ? { width: size, minWidth: panel.minSize, maxWidth: panel.maxSize } : { height: size, minHeight: panel.minSize, maxHeight: panel.maxSize };

  return (
    <div ref={panelRef} className="flex flex-col relative" style={panelStyle}>
      {/* Panel header */}
      <div className="flex items-center justify-between px-3 py-1.5 bg-surface/50 border-b border-border shrink-0">
        <span className="text-[10px] font-semibold text-muted/60 uppercase tracking-wider">{panel.title}</span>
        {panel.collapsible && (
          <button
            onClick={() => onToggle?.(panel.id)}
            className="p-0.5 rounded hover:bg-accent/10 text-muted hover:text-foreground transition-colors"
          >
            <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        )}
      </div>

      {/* Panel content */}
      <div className="flex-1 min-h-0 overflow-auto">{panel.content}</div>

      {/* Resize handle */}
      <div
        onMouseDown={handleMouseDown}
        className={`absolute top-0 bottom-0 z-10 w-1 cursor-col-resize hover:bg-primary/30 transition-colors ${
          direction === 'horizontal'
            ? panel.position === 'right' ? 'left-0' : 'right-0'
            : 'top-auto bottom-0 left-0 right-0 h-1 cursor-row-resize'
        } ${isResizing ? 'bg-primary/40' : ''}`}
      />
    </div>
  );
}
