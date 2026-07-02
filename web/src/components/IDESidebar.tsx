'use client';

import React from 'react';

interface IDESidebarProps {
  children: React.ReactNode;
}

/**
 * IDE left sidebar container with fixed width.
 */
export const IDESidebar: React.FC<IDESidebarProps> = ({ children }) => {
  return (
    <aside className="w-56 border-r border-border bg-surface/30 overflow-y-auto shrink-0 flex flex-col">
      {children}
    </aside>
  );
};
