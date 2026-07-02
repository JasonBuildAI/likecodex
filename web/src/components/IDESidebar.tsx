'use client';

import React from 'react';

interface IDESidebarProps {
  children: React.ReactNode;
}

/**
 * IDE left sidebar container with fixed width.
 *
 * Phase 7.6: Debug Panel Sidebar
 * - Future: Add debug-specific panels in sidebar:
 *   - Call Stack panel (thread frames)
 *   - Breakpoints list panel
 *   - Watches panel (Phase 7.7)
 * - Toggle between file-tree view and debug view via toolbar
 */
export const IDESidebar: React.FC<IDESidebarProps> = ({ children }) => {
  return (
    <aside className="w-56 border-r border-border bg-surface/30 overflow-y-auto shrink-0 flex flex-col">
      {children}
    </aside>
  );
};
