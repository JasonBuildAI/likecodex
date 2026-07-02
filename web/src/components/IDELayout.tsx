'use client';

import React from 'react';
import { IDEToolbar } from './IDEToolbar';
import { IDESidebar } from './IDESidebar';

interface IDELayoutProps {
  leftPanelContent?: React.ReactNode;
  centerContent?: React.ReactNode;
  rightPanelContent?: React.ReactNode;
  sidebarLabel?: string;
  toolbarContent?: React.ReactNode;
}

/**
 * Three-column IDE layout: sidebar | editor + terminal | chat panel
 */
export const IDELayout: React.FC<IDELayoutProps> = ({
  leftPanelContent,
  centerContent,
  rightPanelContent,
}) => {
  return (
    <main className="flex h-screen flex-col bg-background">
      <IDEToolbar />
      <div className="flex flex-1 min-h-0">
        {/* Left sidebar */}
        <IDESidebar>
          {leftPanelContent}
        </IDESidebar>

        {/* Center: Editor + Terminal */}
        <section className="flex-1 flex flex-col min-w-0">
          {centerContent}
        </section>

        {/* Right panel: Chat */}
        {rightPanelContent}
      </div>
    </main>
  );
};
