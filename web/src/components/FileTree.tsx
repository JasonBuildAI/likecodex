'use client';

import { memo, useCallback, useEffect, useState } from 'react';
import { useAppStore } from '@/lib/store';
import type { FileNode } from '@/lib/store';
import { fetchWorkspaceTree, fetchWorkspaceFile } from '@/lib/api';

// ── Icon helpers ────────────────────────────────────────────────────────
const FileIcon = memo(function FileIcon({ name, isDir }: { name: string; isDir: boolean }) {
  if (isDir) {
    return <span className="text-amber-400 shrink-0">&#128193;</span>;
  }
  const ext = name.split('.').pop()?.toLowerCase();
  const iconMap: Record<string, string> = {
    ts: '\uD83D\uDFE6', tsx: '\u269B\uFE0F',
    js: '\uD83D\uDFE8', jsx: '\u269B\uFE0F',
    py: '\uD83D\uDFE3', rs: '\uD83E\uDFA0',
    css: '\uD83C\uDFA8', scss: '\uD83C\uDFA8',
    html: '\uD83C\uDF10', json: '\uD83D\uDCCB',
    md: '\uD83D\uDCDD', yaml: '\uD83D\uDCC4', yml: '\uD83D\uDCC4',
    toml: '\u2699\uFE0F', lock: '\uD83D\uDD12',
    gitignore: '\uD83D\uDD12', env: '\uD83D\uDD10',
    svg: '\uD83D\uDDBC\uFE0F', png: '\uD83D\uDDBC\uFE0F', jpg: '\uD83D\uDDBC\uFE0F',
  };
  return <span className="shrink-0">{iconMap[ext || ''] || '\uD83D\uDCC4'}</span>;
});

// ── Tree node component ─────────────────────────────────────────────────
const TreeNode = memo(function TreeNode({
  node,
  depth,
  onFileClick,
}: {
  node: FileNode;
  depth: number;
  onFileClick: (path: string) => void;
}) {
  const [expanded, setExpanded] = useState(depth < 1);
  const [children, setChildren] = useState<FileNode[] | null>(node.children || null);
  const activeFilePath = useAppStore((s) => s.activeFilePath);
  const isActive = activeFilePath === node.path;

  const handleToggle = useCallback(async () => {
    if (node.type === 'directory') {
      if (!expanded && !children) {
        const tree = await fetchWorkspaceTree(node.path);
        if (tree && tree.type === 'directory' && tree.children) {
          setChildren(tree.children);
        }
      }
      setExpanded((v) => !v);
    } else {
      onFileClick(node.path);
    }
  }, [node, expanded, children, onFileClick]);

  const handleDoubleClick = useCallback(() => {
    if (node.type === 'file') onFileClick(node.path);
  }, [node, onFileClick]);

  if (node.type === 'directory' && node.name === '.' && node.children) {
    // Root node - render children directly
    return (
      <>
        {node.children.map((child) => (
          <TreeNode
            key={child.path}
            node={child}
            depth={0}
            onFileClick={onFileClick}
          />
        ))}
      </>
    );
  }

  return (
    <>
      <div
        className={`flex items-center gap-1 px-2 py-0.5 cursor-pointer text-xs hover:bg-accent/10 select-none truncate ${
          isActive ? 'bg-primary/15 text-primary font-medium' : 'text-muted'
        }`}
        style={{ paddingLeft: `${8 + depth * 14}px` }}
        onClick={handleToggle}
        onDoubleClick={handleDoubleClick}
        title={node.path}
      >
        {node.type === 'directory' && (
          <span className="text-[10px] w-3 text-center shrink-0">
            {expanded ? '\u25BC' : '\u25B6'}
          </span>
        )}
        {node.type === 'file' && <span className="w-3 shrink-0" />}
        <FileIcon name={node.name} isDir={node.type === 'directory'} />
        <span className="truncate">{node.name}</span>
        {node.type === 'file' && typeof node.size === 'number' && (
          <span className="ml-auto text-[10px] opacity-50 shrink-0">
            {node.size > 1024 ? `${(node.size / 1024).toFixed(1)}k` : `${node.size}B`}
          </span>
        )}
      </div>
      {node.type === 'directory' && expanded && children && (
        <div>
          {children
            .filter((c) => c.type === 'directory')
            .concat(children.filter((c) => c.type === 'file'))
            .map((child) => (
              <TreeNode
                key={child.path}
                node={child}
                depth={depth + 1}
                onFileClick={onFileClick}
              />
            ))}
        </div>
      )}
      {node.type === 'directory' && expanded && !children && (
        <div
          className="text-[10px] text-muted/50 italic px-2 py-1"
          style={{ paddingLeft: `${8 + (depth + 1) * 14}px` }}
        >
          Loading...
        </div>
      )}
    </>
  );
});

// ── Main FileTree component ────────────────────────────────────────────
export function FileTree() {
  const fileTree = useAppStore((s) => s.fileTree);
  const fileTreeLoading = useAppStore((s) => s.fileTreeLoading);
  const setFileTree = useAppStore((s) => s.setFileTree);
  const setFileTreeLoading = useAppStore((s) => s.setFileTreeLoading);
  const openFile = useAppStore((s) => s.openFile);
  const addToast = useAppStore((s) => s.addToast);

  // Load initial file tree
  useEffect(() => {
    if (!fileTree) {
      setFileTreeLoading(true);
      fetchWorkspaceTree('.').then((tree) => {
        if (tree) setFileTree(tree);
        setFileTreeLoading(false);
      });
    }
  }, [fileTree, setFileTree, setFileTreeLoading]);

  const handleFileClick = useCallback(
    async (path: string) => {
      const data = await fetchWorkspaceFile(path);
      if (data) {
        openFile({ path: data.path, name: data.name, content: data.content });
      } else {
        addToast({ type: 'error', message: `Failed to read ${path}` });
      }
    },
    [openFile, addToast]
  );

  if (fileTreeLoading && !fileTree) {
    return (
      <div className="flex items-center justify-center h-full text-xs text-muted">
        Loading files...
      </div>
    );
  }

  if (!fileTree) {
    return (
      <div className="flex items-center justify-center h-full text-xs text-muted">
        No workspace found
      </div>
    );
  }

  return (
    <div className="overflow-y-auto h-full py-1 select-none">
      <div className="px-3 py-1.5 text-[10px] font-semibold uppercase tracking-wider text-muted/60 border-b border-border mb-1">
        Explorer
      </div>
      <TreeNode node={fileTree} depth={0} onFileClick={handleFileClick} />
    </div>
  );
}
