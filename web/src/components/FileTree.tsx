'use client';

import { memo, useCallback, useEffect, useState, useRef } from 'react';
import { useAppStore } from '@/lib/store';
import type { FileNode } from '@/lib/store';
import { fetchWorkspaceTree, fetchWorkspaceFile, fetchFileSymbols } from '@/lib/api';
import type { FileSymbol } from '@/lib/api';

// ── Context menu types ─────────────────────────────────────────────
interface ContextMenuState {
  visible: boolean;
  x: number;
  y: number;
  node: FileNode | null;
}

interface DragState {
  dragNode: FileNode | null;
  overNode: FileNode | null;
}

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

const SymbolIcon = memo(function SymbolIcon({ kind }: { kind: string }) {
  const iconMap: Record<string, string> = {
    function: '\u0192', class: 'C', method: 'm',
    variable: 'v', interface: 'I', type: 'T',
    struct: 'S', enum: 'E', trait: 't',
    const: 'k',
  };
  const icon = iconMap[kind.toLowerCase()] || '\u2022';
  const colorMap: Record<string, string> = {
    function: 'text-yellow-400', class: 'text-blue-400', method: 'text-green-400',
    variable: 'text-purple-400', interface: 'text-cyan-400', type: 'text-teal-400',
    struct: 'text-orange-400', enum: 'text-pink-400', trait: 'text-indigo-400',
    const: 'text-amber-400',
  };
  const color = colorMap[kind.toLowerCase()] || 'text-gray-400';
  return <span className={`font-mono text-[10px] w-4 text-center shrink-0 ${color}`}>{icon}</span>;
});

// ── Symbol row component ────────────────────────────────────────────────
const SymbolRow = memo(function SymbolRow({
  symbol,
  filePath,
  depth,
  onSymbolClick,
}: {
  symbol: FileSymbol;
  filePath: string;
  depth: number;
  onSymbolClick: (path: string, line: number) => void;
}) {
  return (
    <div
      className="flex items-center gap-1 px-2 py-0.5 cursor-pointer text-[10px] hover:bg-accent/5 select-none truncate text-muted/70"
      style={{ paddingLeft: `${8 + depth * 14 + 12}px` }}
      onClick={() => onSymbolClick(filePath, symbol.line)}
      title={`${symbol.kind}: ${symbol.name} (line ${symbol.line})`}
    >
      <SymbolIcon kind={symbol.kind} />
      <span className="truncate">{symbol.name}</span>
      <span className="ml-auto text-[9px] opacity-40 shrink-0">:{symbol.line}</span>
    </div>
  );
});

// ── Tree node component ─────────────────────────────────────────────────
const TreeNode = memo(function TreeNode({
  node,
  depth,
  onFileClick,
  onContextMenu,
  filterQuery,
  dragState,
  onDragStart,
  onDragOver,
  onDragEnd,
  onDrop,
}: {
  node: FileNode;
  depth: number;
  onFileClick: (path: string) => void;
  onContextMenu: (e: React.MouseEvent, node: FileNode) => void;
  filterQuery: string;
  dragState: DragState;
  onDragStart: (node: FileNode) => void;
  onDragOver: (e: React.DragEvent, node: FileNode) => void;
  onDragEnd: () => void;
  onDrop: (e: React.DragEvent, targetNode: FileNode) => void;
}) {
  const [expanded, setExpanded] = useState(depth < 1);
  const [symbolsExpanded, setSymbolsExpanded] = useState(false);
  const [children, setChildren] = useState<FileNode[] | null>(node.children || null);
  const [symbols, setSymbols] = useState<FileSymbol[] | null>(null);
  const [symbolsLoading, setSymbolsLoading] = useState(false);
  const [isRenaming, setIsRenaming] = useState(false);
  const [renameValue, setRenameValue] = useState(node.name);
  const activeFilePath = useAppStore((s) => s.activeFilePath);
  const isActive = activeFilePath === node.path;

  // Filter check
  const matchesFilter = !filterQuery || node.name.toLowerCase().includes(filterQuery.toLowerCase());
  const hasMatchingChildren = children?.some(
    (c) => c.name.toLowerCase().includes(filterQuery.toLowerCase()) ||
    (c.type === 'directory' && c.children?.some((cc) => cc.name.toLowerCase().includes(filterQuery.toLowerCase())))
  );

  // If filtering and this node doesn't match and has no matching children, hide
  if (filterQuery && !matchesFilter && node.type === 'file') return null;
  if (filterQuery && !matchesFilter && node.type === 'directory' && !hasMatchingChildren) return null;

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

  const handleSymbolClick = useCallback(
    async (path: string, line: number) => {
      if (path) {
        const data = await fetchWorkspaceFile(path);
        if (data) {
          const store = useAppStore.getState();
          store.openFile({ path: data.path, name: data.name, content: data.content });
          window.dispatchEvent(new CustomEvent('navigate-to-line', { detail: { path, line } }));
        }
      }
    },
    []
  );

  const handleSymbolsToggle = useCallback(async (e: React.MouseEvent) => {
    e.stopPropagation();
    if (!symbolsExpanded && !symbols) {
      setSymbolsLoading(true);
      const syms = await fetchFileSymbols(node.path);
      setSymbols(syms);
      setSymbolsLoading(false);
    }
    setSymbolsExpanded((v) => !v);
  }, [symbolsExpanded, symbols, node.path]);

  const handleRenameSubmit = useCallback(async () => {
    if (renameValue.trim() && renameValue !== node.name) {
      try {
        await fetch('/api/workspace/rename', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ oldPath: node.path, newName: renameValue.trim() }),
        });
        // Refresh tree
        const tree = await fetchWorkspaceTree('.');
        if (tree) useAppStore.getState().setFileTree(tree);
      } catch {
        // Best-effort
      }
    }
    setIsRenaming(false);
  }, [renameValue, node.name, node.path]);

  // Drag handlers
  const handleDragStart = useCallback((e: React.DragEvent) => {
    e.dataTransfer.setData('text/plain', node.path);
    e.dataTransfer.effectAllowed = 'move';
    onDragStart(node);
  }, [node, onDragStart]);

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = 'move';
    onDragOver(e, node);
  }, [node, onDragOver]);

  const handleDrop = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    onDrop(e, node);
  }, [node, onDrop]);

  const isDragOver = dragState.overNode?.path === node.path;
  const isDragging = dragState.dragNode?.path === node.path;

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
            onContextMenu={onContextMenu}
            filterQuery={filterQuery}
            dragState={dragState}
            onDragStart={onDragStart}
            onDragOver={onDragOver}
            onDragEnd={onDragEnd}
            onDrop={onDrop}
          />
        ))}
      </>
    );
  }

  return (
    <>
      <div
        className={`flex items-center gap-1 px-2 py-0.5 cursor-pointer text-xs select-none truncate group ${
          isActive ? 'bg-primary/15 text-primary font-medium' : 'text-muted hover:bg-accent/10'
        } ${isDragOver ? 'bg-blue-900/30 border-t border-blue-500' : ''} ${isDragging ? 'opacity-50' : ''}`}
        style={{ paddingLeft: `${8 + depth * 14}px` }}
        onClick={handleToggle}
        onDoubleClick={handleDoubleClick}
        onContextMenu={(e) => onContextMenu(e, node)}
        title={node.path}
        draggable={!isRenaming}
        onDragStart={handleDragStart}
        onDragOver={handleDragOver}
        onDragEnd={onDragEnd}
        onDrop={handleDrop}
      >
        {node.type === 'directory' && (
          <span className="text-[10px] w-3 text-center shrink-0">
            {expanded ? '\u25BC' : '\u25B6'}
          </span>
        )}
        {node.type === 'file' && (
          <span
            className="text-[10px] w-3 text-center shrink-0 cursor-pointer hover:text-primary"
            onClick={node.type === 'file' ? handleSymbolsToggle : undefined}
          >
            {symbolsExpanded ? '\u25BC' : '\u25B6'}
          </span>
        )}
        <FileIcon name={node.name} isDir={node.type === 'directory'} />
        {isRenaming ? (
          <input
            type="text"
            value={renameValue}
            onChange={(e) => setRenameValue(e.target.value)}
            onBlur={handleRenameSubmit}
            onKeyDown={(e) => { if (e.key === 'Enter') handleRenameSubmit(); if (e.key === 'Escape') setIsRenaming(false); }}
            className="flex-1 bg-background border border-primary rounded px-1 py-0 text-xs outline-none min-w-0"
            autoFocus
            onClick={(e) => e.stopPropagation()}
          />
        ) : (
          <span className="truncate">{node.name}</span>
        )}
        {node.type === 'file' && typeof node.size === 'number' && (
          <span className="ml-auto text-[10px] opacity-50 shrink-0">
            {node.size > 1024 ? `${(node.size / 1024).toFixed(1)}k` : `${node.size}B`}
          </span>
        )}
      </div>
      {/* File symbols section */}
      {node.type === 'file' && symbolsExpanded && (
        <div>
          {symbolsLoading && (
            <div
              className="text-[9px] text-muted/50 italic px-2 py-0.5"
              style={{ paddingLeft: `${8 + depth * 14 + 12}px` }}
            >
              Loading symbols...
            </div>
          )}
          {symbols && symbols.length === 0 && (
            <div
              className="text-[9px] text-muted/40 italic px-2 py-0.5"
              style={{ paddingLeft: `${8 + depth * 14 + 12}px` }}
            >
              No symbols found
            </div>
          )}
          {symbols && symbols.map((sym, i) => (
            <SymbolRow
              key={`${sym.name}-${sym.line}-${i}`}
              symbol={sym}
              filePath={node.path}
              depth={depth + 1}
              onSymbolClick={handleSymbolClick}
            />
          ))}
        </div>
      )}
      {/* Directory children */}
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
                onContextMenu={onContextMenu}
                filterQuery={filterQuery}
                dragState={dragState}
                onDragStart={onDragStart}
                onDragOver={onDragOver}
                onDragEnd={onDragEnd}
                onDrop={onDrop}
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

  const [contextMenu, setContextMenu] = useState<ContextMenuState>({ visible: false, x: 0, y: 0, node: null });
  const [filterQuery, setFilterQuery] = useState('');
  const [dragState, setDragState] = useState<DragState>({ dragNode: null, overNode: null });
  const [showCreateInput, setShowCreateInput] = useState(false);
  const [createType, setCreateType] = useState<'file' | 'directory'>('file');
  const [createName, setCreateName] = useState('');
  const contextMenuRef = useRef<HTMLDivElement>(null);

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

  // Close context menu on click outside
  useEffect(() => {
    const handler = () => setContextMenu((prev) => ({ ...prev, visible: false }));
    document.addEventListener('click', handler);
    return () => document.removeEventListener('click', handler);
  }, []);

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

  // ── Context menu handlers ─────────────────────────────────────────────
  const handleContextMenu = useCallback((e: React.MouseEvent, node: FileNode) => {
    e.preventDefault();
    e.stopPropagation();
    setContextMenu({
      visible: true,
      x: e.clientX,
      y: e.clientY,
      node,
    });
  }, []);

  const handleRename = useCallback(() => {
    setContextMenu((prev) => ({ ...prev, visible: false }));
    // Trigger rename mode - need to find the node in tree
    // For simplicity, we'll show a rename input in the context menu
    if (contextMenu.node) {
      setCreateName(contextMenu.node.name);
      setShowCreateInput(true);
    }
  }, [contextMenu.node]);

  const handleDelete = useCallback(async () => {
    setContextMenu((prev) => ({ ...prev, visible: false }));
    if (!contextMenu.node) return;
    if (!confirm(`Delete "${contextMenu.node.name}"?`)) return;
    try {
      await fetch('/api/workspace/delete', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: contextMenu.node.path }),
      });
      const tree = await fetchWorkspaceTree('.');
      if (tree) setFileTree(tree);
      addToast({ type: 'success', message: `Deleted ${contextMenu.node.name}` });
    } catch (err) {
      addToast({ type: 'error', message: `Failed to delete: ${err}` });
    }
  }, [contextMenu.node, setFileTree, addToast]);

  const handleCreateFile = useCallback(async () => {
    setContextMenu((prev) => ({ ...prev, visible: false }));
    if (!contextMenu.node) return;
    const dirPath = contextMenu.node.type === 'directory' ? contextMenu.node.path : contextMenu.node.path.split('/').slice(0, -1).join('/');
    const name = prompt('Enter file name:');
    if (!name) return;
    try {
      await fetch('/api/workspace/create', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: `${dirPath}/${name}`, type: 'file' }),
      });
      const tree = await fetchWorkspaceTree('.');
      if (tree) setFileTree(tree);
    } catch (err) {
      addToast({ type: 'error', message: `Failed to create: ${err}` });
    }
  }, [contextMenu.node, setFileTree, addToast]);

  const handleCreateDirectory = useCallback(async () => {
    setContextMenu((prev) => ({ ...prev, visible: false }));
    if (!contextMenu.node) return;
    const dirPath = contextMenu.node.type === 'directory' ? contextMenu.node.path : contextMenu.node.path.split('/').slice(0, -1).join('/');
    const name = prompt('Enter directory name:');
    if (!name) return;
    try {
      await fetch('/api/workspace/create', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ path: `${dirPath}/${name}`, type: 'directory' }),
      });
      const tree = await fetchWorkspaceTree('.');
      if (tree) setFileTree(tree);
    } catch (err) {
      addToast({ type: 'error', message: `Failed to create: ${err}` });
    }
  }, [contextMenu.node, setFileTree, addToast]);

  // ── Drag handlers ─────────────────────────────────────────────────────
  const handleDragStart = useCallback((node: FileNode) => {
    setDragState({ dragNode: node, overNode: null });
  }, []);

  const handleDragOver = useCallback((e: React.DragEvent, node: FileNode) => {
    setDragState((prev) => ({ ...prev, overNode: node }));
  }, []);

  const handleDragEnd = useCallback(() => {
    setDragState({ dragNode: null, overNode: null });
  }, []);

  const handleDrop = useCallback(async (e: React.DragEvent, targetNode: FileNode) => {
    e.preventDefault();
    const sourcePath = e.dataTransfer.getData('text/plain');
    if (!sourcePath || sourcePath === targetNode.path) {
      setDragState({ dragNode: null, overNode: null });
      return;
    }
    const targetDir = targetNode.type === 'directory' ? targetNode.path : targetNode.path.split('/').slice(0, -1).join('/');
    try {
      await fetch('/api/workspace/move', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ sourcePath, targetDir }),
      });
      const tree = await fetchWorkspaceTree('.');
      if (tree) setFileTree(tree);
    } catch (err) {
      addToast({ type: 'error', message: `Failed to move: ${err}` });
    }
    setDragState({ dragNode: null, overNode: null });
  }, [setFileTree, addToast]);

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
    <div className="overflow-y-auto h-full py-1 select-none" onContextMenu={(e) => {
      // Right-click on empty area shows root context menu
      if (!contextMenu.visible) {
        e.preventDefault();
        setContextMenu({
          visible: true,
          x: e.clientX,
          y: e.clientY,
          node: fileTree,
        });
      }
    }}>
      {/* Header with filter */}
      <div className="px-2 py-1 border-b border-border mb-1">
        <div className="flex items-center gap-1">
          <input
            type="text"
            value={filterQuery}
            onChange={(e) => setFilterQuery(e.target.value)}
            placeholder="Filter files..."
            className="flex-1 bg-background border border-border rounded px-2 py-0.5 text-[10px] focus:outline-none focus:border-primary placeholder:text-muted/40"
          />
          <button
            onClick={() => {
              setCreateType('file');
              setCreateName('');
              setShowCreateInput(true);
            }}
            className="text-[10px] text-muted hover:text-foreground px-1"
            title="New File"
          >
            📄+
          </button>
          <button
            onClick={() => {
              setCreateType('directory');
              setCreateName('');
              setShowCreateInput(true);
            }}
            className="text-[10px] text-muted hover:text-foreground px-1"
            title="New Folder"
          >
            📁+
          </button>
        </div>
        {/* Create file/folder input */}
        {showCreateInput && (
          <div className="flex gap-1 mt-1">
            <input
              type="text"
              value={createName}
              onChange={(e) => setCreateName(e.target.value)}
              placeholder={createType === 'file' ? 'filename.ts' : 'folder-name'}
              className="flex-1 bg-background border border-primary rounded px-2 py-0.5 text-[10px] focus:outline-none"
              autoFocus
              onKeyDown={async (e) => {
                if (e.key === 'Enter' && createName.trim()) {
                  try {
                    await fetch('/api/workspace/create', {
                      method: 'POST',
                      headers: { 'Content-Type': 'application/json' },
                      body: JSON.stringify({ path: createName.trim(), type: createType }),
                    });
                    const tree = await fetchWorkspaceTree('.');
                    if (tree) setFileTree(tree);
                    setShowCreateInput(false);
                    setCreateName('');
                  } catch (err) {
                    addToast({ type: 'error', message: `Failed: ${err}` });
                  }
                }
                if (e.key === 'Escape') setShowCreateInput(false);
              }}
            />
            <button
              onClick={() => setShowCreateInput(false)}
              className="text-[10px] text-muted hover:text-foreground px-1"
            >
              ✕
            </button>
          </div>
        )}
      </div>

      <div className="px-3 py-1.5 text-[10px] font-semibold uppercase tracking-wider text-muted/60 border-b border-border mb-1 flex items-center justify-between">
        <span>Explorer</span>
        {filterQuery && (
          <span className="text-[9px] text-muted/40 font-normal normal-case">Filtered</span>
        )}
      </div>

      <TreeNode
        node={fileTree}
        depth={0}
        onFileClick={handleFileClick}
        onContextMenu={handleContextMenu}
        filterQuery={filterQuery}
        dragState={dragState}
        onDragStart={handleDragStart}
        onDragOver={handleDragOver}
        onDragEnd={handleDragEnd}
        onDrop={handleDrop}
      />

      {/* Context menu */}
      {contextMenu.visible && contextMenu.node && (
        <div
          ref={contextMenuRef}
          className="fixed z-[9999] bg-surface border border-border rounded-lg shadow-xl py-1 min-w-[140px]"
          style={{ left: contextMenu.x, top: contextMenu.y }}
          onClick={() => setContextMenu((prev) => ({ ...prev, visible: false }))}
        >
          <button
            onClick={handleCreateFile}
            className="w-full text-left px-3 py-1.5 text-xs hover:bg-accent/10 transition-colors"
          >
            📄 New File
          </button>
          <button
            onClick={handleCreateDirectory}
            className="w-full text-left px-3 py-1.5 text-xs hover:bg-accent/10 transition-colors"
          >
            📁 New Folder
          </button>
          <div className="border-t border-border my-1" />
          <button
            onClick={handleRename}
            className="w-full text-left px-3 py-1.5 text-xs hover:bg-accent/10 transition-colors"
          >
            ✏️ Rename
          </button>
          <button
            onClick={handleDelete}
            className="w-full text-left px-3 py-1.5 text-xs text-red-500 hover:bg-red-500/10 transition-colors"
          >
            🗑️ Delete
          </button>
        </div>
      )}
    </div>
  );
}
