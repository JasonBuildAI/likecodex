'use client';

import React, { useState, useCallback, useRef, useEffect } from 'react';

export type SplitDirection = 'horizontal' | 'vertical';

interface SplitPaneProps {
  direction: SplitDirection;
  defaultRatio?: number;
  minRatio?: number;
  maxRatio?: number;
  left: React.ReactNode;
  right: React.ReactNode;
  className?: string;
  onRatioChange?: (ratio: number) => void;
}

/**
 * Split panel component.
 * Supports horizontal (left/right) and vertical (top/bottom) splits with a draggable divider.
 */
export function SplitPane({
  direction = 'horizontal',
  defaultRatio = 0.5,
  minRatio = 0.15,
  maxRatio = 0.85,
  left,
  right,
  className = '',
  onRatioChange,
}: SplitPaneProps) {
  const [ratio, setRatio] = useState(defaultRatio);
  const [isDragging, setIsDragging] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  useEffect(() => {
    if (!isDragging) return;

    const handleMouseMove = (e: MouseEvent) => {
      if (!containerRef.current) return;
      const rect = containerRef.current.getBoundingClientRect();
      let newRatio: number;

      if (direction === 'horizontal') {
        newRatio = (e.clientX - rect.left) / rect.width;
      } else {
        newRatio = (e.clientY - rect.top) / rect.height;
      }

      newRatio = Math.max(minRatio, Math.min(maxRatio, newRatio));
      setRatio(newRatio);
    };

    const handleMouseUp = () => {
      setIsDragging(false);
      onRatioChange?.(ratio);
    };

    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseup', handleMouseUp);
    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isDragging, direction, minRatio, maxRatio, ratio, onRatioChange]);

  const isHorizontal = direction === 'horizontal';

  return (
    <div
      ref={containerRef}
      className={`flex ${isHorizontal ? 'flex-row' : 'flex-col'} ${className}`}
      style={{ userSelect: isDragging ? 'none' : undefined }}
    >
      <div
        className="overflow-auto"
        style={isHorizontal ? { width: `${ratio * 100}%` } : { height: `${ratio * 100}%` }}
      >
        {left}
      </div>

      <div
        onMouseDown={handleMouseDown}
        className={`shrink-0 relative z-10 flex items-center justify-center transition-colors ${
          isHorizontal
            ? 'w-1.5 cursor-col-resize hover:bg-primary/20'
            : 'h-1.5 cursor-row-resize hover:bg-primary/20'
        } ${isDragging ? 'bg-primary/30' : 'bg-border/50'}`}
      >
        <div
          className={`rounded-full bg-muted/40 ${
            isHorizontal ? 'w-0.5 h-6' : 'w-6 h-0.5'
          }`}
        />
      </div>

      <div
        className="overflow-auto"
        style={isHorizontal ? { width: `${(1 - ratio) * 100}%` } : { height: `${(1 - ratio) * 100}%` }}
      >
        {right}
      </div>
    </div>
  );
}
'use client';

import React, { useState, useCallback, useRef, useEffect } from 'react';

export type SplitDirection = 'horizontal' | 'vertical';

interface SplitPaneProps {
  direction: SplitDirection;
  defaultRatio?: number;
  minRatio?: number;
  maxRatio?: number;
  left: React.ReactNode;
  right: React.ReactNode;
  className?: string;
  onRatioChange?: (ratio: number) => void;
}

/**
 * Split panel component.
 * Supports horizontal (left/right) and vertical (top/bottom) splits with a draggable divider.
 */
export function SplitPane({
  direction = 'horizontal',
  defaultRatio = 0.5,
  minRatio = 0.15,
  maxRatio = 0.85,
  left,
  right,
  className = '',
  onRatioChange,
}: SplitPaneProps) {
  const [ratio, setRatio] = useState(defaultRatio);
  const [isDragging, setIsDragging] = useState(false);
  const containerRef = useRef<HTMLDivElement>(null);

  const handleMouseDown = useCallback((e: React.MouseEvent) => {
    e.preventDefault();
    setIsDragging(true);
  }, []);

  useEffect(() => {
    if (!isDragging) return;

    const handleMouseMove = (e: MouseEvent) => {
      if (!containerRef.current) return;
      const rect = containerRef.current.getBoundingClientRect();
      let newRatio: number;

      if (direction === 'horizontal') {
        newRatio = (e.clientX - rect.left) / rect.width;
      } else {
        newRatio = (e.clientY - rect.top) / rect.height;
      }

      newRatio = Math.max(minRatio, Math.min(maxRatio, newRatio));
      setRatio(newRatio);
    };

    const handleMouseUp = () => {
      setIsDragging(false);
      onRatioChange?.(ratio);
    };

    window.addEventListener('mousemove', handleMouseMove);
    window.addEventListener('mouseup', handleMouseUp);
    return () => {
      window.removeEventListener('mousemove', handleMouseMove);
      window.removeEventListener('mouseup', handleMouseUp);
    };
  }, [isDragging, direction, minRatio, maxRatio, ratio, onRatioChange]);

  const isHorizontal = direction === 'horizontal';

  return (
    <div
      ref={containerRef}
      className={`flex ${isHorizontal ? 'flex-row' : 'flex-col'} ${className}`}
      style={{ userSelect: isDragging ? 'none' : undefined }}
    >
      {/* First pane */}
      <div
        className="overflow-auto"
        style={isHorizontal ? { width: `${ratio * 100}%` } : { height: `${ratio * 100}%` }}
      >
        {left}
      </div>

      {/* Divider */}
      <div
        onMouseDown={handleMouseDown}
        className={`shrink-0 relative z-10 flex items-center justify-center transition-colors ${
          isHorizontal
            ? 'w-1.5 cursor-col-resize hover:bg-primary/20'
            : 'h-1.5 cursor-row-resize hover:bg-primary/20'
        } ${isDragging ? 'bg-primary/30' : 'bg-border/50'}`}
      >
        <div
          className={`rounded-full bg-muted/40 ${
            isHorizontal ? 'w-0.5 h-6' : 'w-6 h-0.5'
          }`}
        />
      </div>

      {/* Second pane */}
      <div
        className="overflow-auto"
        style={isHorizontal ? { width: `${(1 - ratio) * 100}%` } : { height: `${(1 - ratio) * 100}%` }}
      >
        {right}
      </div>
    </div>
  );
}
