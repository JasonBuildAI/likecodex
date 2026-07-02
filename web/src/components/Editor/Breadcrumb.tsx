'use client';

import { useMemo } from 'react';
import { useAppStore } from '@/lib/store';

interface BreadcrumbSegment {
  label: string;
  type: 'project' | 'directory' | 'file' | 'symbol';
  onClick?: () => void;
}

export function Breadcrumb() {
  const activeFilePath = useAppStore((s) => s.activeFilePath);
  const openFiles = useAppStore((s) => s.openFiles);
  const setActiveFile = useAppStore((s) => s.setActiveFile);

  const segments = useMemo<BreadcrumbSegment[]>(() => {
    if (!activeFilePath) return [];

    const parts = activeFilePath.split('/');
    const projectName = parts[0] || 'project';

    const result: BreadcrumbSegment[] = [
      {
        label: projectName,
        type: 'project',
      },
    ];

    // Add directory segments
    for (let i = 1; i < parts.length - 1; i++) {
      const dirPath = parts.slice(0, i + 1).join('/');
      result.push({
        label: parts[i],
        type: 'directory',
        onClick: () => {
          // Find a file in this directory to navigate there
          const file = openFiles.find((f) => f.path.startsWith(dirPath + '/'));
          if (file) setActiveFile(file.path);
        },
      });
    }

    // Add file segment
    const fileName = parts[parts.length - 1];
    if (fileName) {
      result.push({
        label: fileName,
        type: 'file',
        onClick: () => activeFilePath && setActiveFile(activeFilePath),
      });
    }

    return result;
  }, [activeFilePath, openFiles, setActiveFile]);

  if (segments.length === 0) return null;

  return (
    <nav className="flex items-center gap-0.5 px-2 py-1 text-[11px] text-muted bg-surface/30 border-b border-border overflow-x-auto shrink-0 select-none">
      {segments.map((seg, i) => (
        <span key={`${seg.label}-${i}`} className="flex items-center gap-0.5 whitespace-nowrap">
          {i > 0 && (
            <span className="text-muted/30 mx-0.5 text-[9px]">/</span>
          )}
          <span
            onClick={seg.onClick}
            className={`px-1 py-0.5 rounded transition-colors ${
              seg.type === 'file'
                ? 'text-foreground font-medium'
                : seg.type === 'symbol'
                  ? 'text-amber-400 font-mono'
                  : 'text-muted hover:text-foreground'
            } ${seg.onClick ? 'cursor-pointer hover:bg-accent/10' : ''}`}
          >
            {seg.label}
          </span>
        </span>
      ))}
    </nav>
  );
}
