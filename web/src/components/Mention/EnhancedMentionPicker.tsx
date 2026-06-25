'use client';

import { useState, useEffect, useRef, useCallback, memo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { cn } from '@/lib/utils';

// ============================================================
// Types
// ============================================================

export type MentionType = 'file' | 'folder' | 'symbol' | 'issue' | 'git' | 'action';

export interface MentionItem {
  id: string;
  label: string;
  type: MentionType;
  description?: string;
  path?: string;
  icon?: string;
  badge?: string;
}

export interface MentionCategory {
  type: MentionType;
  label: string;
  items: MentionItem[];
}

interface EnhancedMentionPickerProps {
  query: string;
  onSelect: (item: MentionItem) => void;
  onClose: () => void;
  position?: { top: number; left: number };
  recentFiles?: string[];
}

// ============================================================
// Type Configuration
// ============================================================

const TYPE_CONFIG: Record<MentionType, { color: string; bg: string; icon: JSX.Element; label: string }> = {
  file: {
    color: 'text-blue-400',
    bg: 'bg-blue-500/10',
    label: 'Files',
    icon: (
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
        <polyline points="14 2 14 8 20 8" />
      </svg>
    ),
  },
  folder: {
    color: 'text-amber-400',
    bg: 'bg-amber-500/10',
    label: 'Folders',
    icon: (
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z" />
      </svg>
    ),
  },
  symbol: {
    color: 'text-purple-400',
    bg: 'bg-purple-500/10',
    label: 'Symbols',
    icon: (
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <circle cx="12" cy="12" r="3" />
        <path d="M12 1v6m0 10v6m-9-9h6m10 0h6" />
      </svg>
    ),
  },
  issue: {
    color: 'text-red-400',
    bg: 'bg-red-500/10',
    label: 'Issues',
    icon: (
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <circle cx="12" cy="12" r="10" />
        <line x1="12" y1="8" x2="12" y2="12" />
        <line x1="12" y1="16" x2="12.01" y2="16" />
      </svg>
    ),
  },
  git: {
    color: 'text-orange-400',
    bg: 'bg-orange-500/10',
    label: 'Git',
    icon: (
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <circle cx="18" cy="18" r="3" />
        <circle cx="6" cy="6" r="3" />
        <path d="M13 6h3a2 2 0 0 1 2 2v7M6 9v9" />
      </svg>
    ),
  },
  action: {
    color: 'text-emerald-400',
    bg: 'bg-emerald-500/10',
    label: 'Actions',
    icon: (
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
        <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2" />
      </svg>
    ),
  },
};

// ============================================================
// Mock Data (would be replaced by API results)
// ============================================================

const ACTIONS: MentionItem[] = [
  { id: 'act-1', label: 'Run Tests', type: 'action', description: 'Execute test suite', badge: 'Test' },
  { id: 'act-2', label: 'Build Project', type: 'action', description: 'Compile and bundle', badge: 'Build' },
  { id: 'act-3', label: 'Format Code', type: 'action', description: 'Run formatter', badge: 'Format' },
  { id: 'act-4', label: 'Lint', type: 'action', description: 'Run linter', badge: 'Lint' },
];

const GIT_ITEMS: MentionItem[] = [
  { id: 'git-1', label: 'main', type: 'git', description: 'Branch', badge: 'Branch' },
  { id: 'git-2', label: 'develop', type: 'git', description: 'Branch', badge: 'Branch' },
  { id: 'git-3', label: 'HEAD', type: 'git', description: 'Current commit', badge: 'Commit' },
];

// ============================================================
// File Extension Icon
// ============================================================

function getFileIcon(filename: string): JSX.Element {
  const ext = filename.split('.').pop()?.toLowerCase() || '';
  const iconMap: Record<string, { color: string; label: string }> = {
    ts: { color: 'text-blue-400', label: 'TS' },
    tsx: { color: 'text-cyan-400', label: 'TSX' },
    js: { color: 'text-yellow-400', label: 'JS' },
    jsx: { color: 'text-yellow-400', label: 'JSX' },
    py: { color: 'text-green-400', label: 'PY' },
    rs: { color: 'text-orange-400', label: 'RS' },
    css: { color: 'text-pink-400', label: 'CSS' },
    json: { color: 'text-amber-400', label: '{}' },
    md: { color: 'text-gray-400', label: 'MD' },
    html: { color: 'text-orange-400', label: '<>' },
  };
  const config = iconMap[ext] || { color: 'text-gray-400', label: '··' };
  return (
    <span className={cn('inline-flex items-center justify-center w-5 h-5 rounded text-[9px] font-bold bg-white/5', config.color)}>
      {config.label}
    </span>
  );
}

// ============================================================
// Mention Item Row
// ============================================================

const MentionRow = memo(({ item, isSelected, onClick, onMouseEnter }: {
  item: MentionItem;
  isSelected: boolean;
  onClick: () => void;
  onMouseEnter: () => void;
}) => {
  const config = TYPE_CONFIG[item.type];
  return (
    <button
      onClick={onClick}
      onMouseEnter={onMouseEnter}
      className={cn(
        'w-full flex items-center gap-3 px-3 py-2 rounded-lg text-left transition-all duration-100',
        isSelected ? 'bg-white/10 scale-[1.02]' : 'hover:bg-white/5'
      )}
    >
      {/* Icon */}
      <span className={cn('flex-shrink-0 w-7 h-7 rounded-md flex items-center justify-center', config.bg, config.color)}>
        {item.type === 'file' && item.path ? getFileIcon(item.path) : config.icon}
      </span>

      {/* Label + Description */}
      <span className="flex-1 min-w-0">
        <span className={cn('block text-sm font-medium truncate', isSelected ? 'text-white' : 'text-zinc-200')}>
          {item.label}
        </span>
        {item.description && (
          <span className="block text-xs text-zinc-500 truncate">{item.description}</span>
        )}
      </span>

      {/* Badge */}
      {item.badge && (
        <span className={cn('flex-shrink-0 px-1.5 py-0.5 rounded text-[10px] font-medium', config.bg, config.color)}>
          {item.badge}
        </span>
      )}

      {/* Selected indicator */}
      {isSelected && (
        <motion.span
          layoutId="mention-selected"
          className="flex-shrink-0 w-1 h-6 rounded-full bg-gradient-to-b from-purple-400 to-pink-400"
        />
      )}
    </button>
  );
});
MentionRow.displayName = 'MentionRow';

// ============================================================
// Category Section
// ============================================================

function CategorySection({ category, selectedIndex, onSelect, onHover }: {
  category: MentionCategory;
  selectedIndex: number;
  onSelect: (item: MentionItem) => void;
  onHover: (index: number) => void;
}) {
  const config = TYPE_CONFIG[category.type];
  return (
    <div className="mb-1">
      <div className="flex items-center gap-2 px-3 py-1.5">
        <span className={cn('text-[10px] font-bold uppercase tracking-wider', config.color)}>
          {config.label}
        </span>
        <span className="text-[10px] text-zinc-600">{category.items.length}</span>
        <div className="flex-1 h-px bg-white/5" />
      </div>
      {category.items.map((item, idx) => (
        <MentionRow
          key={item.id}
          item={item}
          isSelected={selectedIndex === idx}
          onClick={() => onSelect(item)}
          onMouseEnter={() => onHover(idx)}
        />
      ))}
    </div>
  );
}

// ============================================================
// Main Component
// ============================================================

function EnhancedMentionPickerImpl({
  query,
  onSelect,
  onClose,
  recentFiles = [],
}: EnhancedMentionPickerProps) {
  const [categories, setCategories] = useState<MentionCategory[]>([]);
  const [flatItems, setFlatItems] = useState<MentionItem[]>([]);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [loading, setLoading] = useState(false);
  const [activeCategoryIndex, setActiveCategoryIndex] = useState(0);
  const listRef = useRef<HTMLDivElement>(null);
  const debounceRef = useRef<NodeJS.Timeout | null>(null);

  // Search with debounce
  const performSearch = useCallback(async (q: string) => {
    setLoading(true);
    try {
      // Try API first
      const res = await fetch(`/api/ide/context/search?q=${encodeURIComponent(q)}`);
      const data = await res.json();

      const fileItems: MentionItem[] = (data.files || []).slice(0, 8).map((f: any) => ({
        id: `file-${f.path}`,
        label: f.name || f.path.split('/').pop(),
        type: 'file' as MentionType,
        description: f.path,
        path: f.path,
      }));

      const symbolItems: MentionItem[] = (data.symbols || []).slice(0, 5).map((s: any) => ({
        id: `sym-${s.name}`,
        label: s.name,
        type: 'symbol' as MentionType,
        description: s.type || s.kind,
        path: s.file,
      }));

      const cats: MentionCategory[] = [];

      // Recent files section (only when no query)
      if (!q && recentFiles.length > 0) {
        cats.push({
          type: 'file',
          label: 'Recent',
          items: recentFiles.slice(0, 5).map((path, i) => ({
            id: `recent-${i}`,
            label: path.split(/[\\/]/).pop() || path,
            type: 'file' as MentionType,
            description: path,
            path,
            badge: 'Recent',
          })),
        });
      }

      if (fileItems.length) cats.push({ type: 'file', label: 'Files', items: fileItems });
      if (symbolItems.length) cats.push({ type: 'symbol', label: 'Symbols', items: symbolItems });
      if (q.toLowerCase().includes('git') || q.toLowerCase().includes('branch')) {
        cats.push({ type: 'git', label: 'Git', items: GIT_ITEMS });
      }
      cats.push({ type: 'action', label: 'Actions', items: ACTIONS.filter(a => !q || a.label.toLowerCase().includes(q.toLowerCase())) });

      setCategories(cats.filter(c => c.items.length > 0));
      const flat = cats.flatMap(c => c.items);
      setFlatItems(flat);
      setSelectedIndex(0);
    } catch {
      // Fallback: actions only
      const fallbackCats: MentionCategory[] = [
        { type: 'action', label: 'Actions', items: ACTIONS },
      ];
      if (recentFiles.length > 0 && !query) {
        fallbackCats.unshift({
          type: 'file',
          label: 'Recent',
          items: recentFiles.slice(0, 5).map((path, i) => ({
            id: `recent-${i}`,
            label: path.split(/[\\/]/).pop() || path,
            type: 'file' as MentionType,
            description: path,
            path,
            badge: 'Recent',
          })),
        });
      }
      setCategories(fallbackCats);
      setFlatItems(fallbackCats.flatMap(c => c.items));
    } finally {
      setLoading(false);
    }
  }, [recentFiles, query]);

  useEffect(() => {
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => performSearch(query), 120);
    return () => { if (debounceRef.current) clearTimeout(debounceRef.current); };
  }, [query, performSearch]);

  // Keyboard navigation
  const handleKeyDown = useCallback((e: KeyboardEvent) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault();
      setSelectedIndex(prev => Math.min(prev + 1, flatItems.length - 1));
    } else if (e.key === 'ArrowUp') {
      e.preventDefault();
      setSelectedIndex(prev => Math.max(prev - 1, 0));
    } else if (e.key === 'Enter') {
      e.preventDefault();
      if (flatItems[selectedIndex]) onSelect(flatItems[selectedIndex]);
    } else if (e.key === 'Escape') {
      e.preventDefault();
      onClose();
    } else if (e.key === 'Tab') {
      e.preventDefault();
      // Cycle through categories
      setActiveCategoryIndex(prev => (prev + 1) % categories.length);
    }
  }, [flatItems, selectedIndex, onSelect, onClose, categories.length]);

  useEffect(() => {
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);

  // Scroll selected into view
  useEffect(() => {
    const container = listRef.current;
    if (!container) return;
    const selected = container.querySelector('[data-selected="true"]');
    if (selected) {
      selected.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
    }
  }, [selectedIndex]);

  // Track flat index across categories
  let globalIdx = 0;

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0, y: -8, scale: 0.96 }}
        animate={{ opacity: 1, y: 0, scale: 1 }}
        exit={{ opacity: 0, y: -8, scale: 0.96 }}
        transition={{ duration: 0.15, ease: [0.4, 0, 0.2, 1] }}
        className="absolute z-50 w-80 max-h-80 overflow-hidden rounded-xl border border-white/10 bg-zinc-900/95 backdrop-blur-xl shadow-2xl"
        style={{
          boxShadow: '0 20px 60px -10px rgba(0,0,0,0.5), 0 0 0 1px rgba(255,255,255,0.05)',
        }}
      >
        {/* Search status bar */}
        <div className="flex items-center gap-2 px-3 py-2 border-b border-white/5">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="text-zinc-500">
            <circle cx="11" cy="11" r="8" />
            <line x1="21" y1="21" x2="16.65" y2="16.65" />
          </svg>
          <span className="text-xs text-zinc-400 flex-1 truncate">
            {loading ? 'Searching...' : `"${query}"`}
          </span>
          <kbd className="text-[10px] text-zinc-500 px-1.5 py-0.5 rounded bg-white/5 border border-white/10">↑↓</kbd>
          <kbd className="text-[10px] text-zinc-500 px-1.5 py-0.5 rounded bg-white/5 border border-white/10">↵</kbd>
          <kbd className="text-[10px] text-zinc-500 px-1.5 py-0.5 rounded bg-white/5 border border-white/10">esc</kbd>
        </div>

        {/* Results */}
        <div ref={listRef} className="max-h-64 overflow-y-auto p-1.5 scrollbar-thin">
          {flatItems.length === 0 && !loading ? (
            <div className="flex flex-col items-center justify-center py-8 text-zinc-500">
              <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" className="mb-2 opacity-50">
                <circle cx="11" cy="11" r="8" />
                <line x1="21" y1="21" x2="16.65" y2="16.65" />
              </svg>
              <span className="text-sm">No results found</span>
            </div>
          ) : (
            categories.map((cat) => {
              const startIdx = globalIdx;
              const catItems = cat.items.map((item, idx) => {
                const flatIdx = startIdx + idx;
                globalIdx++;
                return null; // We render via CategorySection below
              });
              globalIdx = startIdx + cat.items.length;
              return null;
            })
          )}
          {/* Render categories with proper global index tracking */}
          {(() => {
            let gIdx = 0;
            return categories.map((cat) => {
              const startIdx = gIdx;
              gIdx += cat.items.length;
              return (
                <CategorySection
                  key={`${cat.type}-${cat.label}`}
                  category={cat}
                  selectedIndex={selectedIndex - startIdx}
                  onSelect={onSelect}
                  onHover={(idx) => setSelectedIndex(startIdx + idx)}
                />
              );
            });
          })()}
        </div>

        {/* Footer */}
        <div className="flex items-center justify-between px-3 py-1.5 border-t border-white/5 bg-white/[0.02]">
          <span className="text-[10px] text-zinc-600">
            {flatItems.length} results
          </span>
          <div className="flex items-center gap-2">
            {Object.values(TYPE_CONFIG).map((config) => (
              <span key={config.label} className={cn('w-1.5 h-1.5 rounded-full', config.bg.replace('/10', '/40'))} />
            ))}
          </div>
        </div>
      </motion.div>
    </AnimatePresence>
  );
}

export const EnhancedMentionPicker = memo(EnhancedMentionPickerImpl);
