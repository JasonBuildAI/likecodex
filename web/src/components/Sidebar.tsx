'use client';

import { memo } from 'react';
import { useAppStore } from '@/lib/store';

interface SidebarProps {
  children: React.ReactNode;
}

export const Sidebar = memo(function Sidebar({ children }: SidebarProps) {
  const sidebarOpen = useAppStore((s) => s.sidebarOpen);

  return (
    <>
      {/* Desktop sidebar */}
      <aside
        className={`sidebar-transition hidden md:block border-r border-border overflow-y-auto bg-surface/50 ${
          sidebarOpen ? 'w-64' : 'w-0'
        }`}
      >
        {sidebarOpen && <div className="p-3 min-w-[16rem]">{children}</div>}
      </aside>

      {/* Mobile drawer overlay */}
      {sidebarOpen && (
        <div className="md:hidden fixed inset-0 z-40">
          <div
            className="absolute inset-0 bg-black/50"
            onClick={() => useAppStore.getState().setSidebarOpen(false)}
          />
          <div className="absolute left-0 top-0 bottom-0 w-72 bg-surface border-r border-border shadow-xl z-50 p-3 overflow-y-auto sidebar-transition">
            {children}
          </div>
        </div>
      )}
    </>
  );
});
