'use client';

import React, { useState, useMemo, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { modalBackdrop, modalContent, staggerContainer, staggerItem } from '@/lib/animations';

// ─────────────────────────────────────────────
// Types
// ─────────────────────────────────────────────
interface ShortcutItem {
  keys: string[];
  description: string;
  category: 'navigation' | 'editing' | 'agent' | 'view' | 'system';
  global?: boolean;
}

interface EnhancedShortcutHelpProps {
  isOpen: boolean;
  onClose: () => void;
}

// ─────────────────────────────────────────────
// Shortcut catalog
// ─────────────────────────────────────────────
const SHORTCUTS: ShortcutItem[] = [
  // Navigation
  { keys: ['Ctrl', 'K'], description: '打开命令面板', category: 'navigation', global: true },
  { keys: ['Ctrl', 'P'], description: '快速打开文件', category: 'navigation', global: true },
  { keys: ['Ctrl', 'Shift', 'P'], description: '显示所有命令', category: 'navigation', global: true },
  { keys: ['Ctrl', 'G'], description: '跳转到行', category: 'navigation' },
  { keys: ['Ctrl', 'Tab'], description: '切换标签页', category: 'navigation' },
  { keys: ['Alt', '←'], description: '后退导航', category: 'navigation' },
  { keys: ['Alt', '→'], description: '前进导航', category: 'navigation' },

  // Editing
  { keys: ['Ctrl', 'C'], description: '复制选中内容', category: 'editing', global: true },
  { keys: ['Ctrl', 'V'], description: '粘贴', category: 'editing', global: true },
  { keys: ['Ctrl', 'X'], description: '剪切选中内容', category: 'editing', global: true },
  { keys: ['Ctrl', 'Z'], description: '撤销', category: 'editing', global: true },
  { keys: ['Ctrl', 'Y'], description: '重做', category: 'editing', global: true },
  { keys: ['Ctrl', 'D'], description: '选中下一个匹配项', category: 'editing' },
  { keys: ['Ctrl', 'Shift', 'L'], description: '选中所有匹配项', category: 'editing' },
  { keys: ['Alt', '↑'], description: '向上移动行', category: 'editing' },
  { keys: ['Alt', '↓'], description: '向下移动行', category: 'editing' },
  { keys: ['Shift', 'Alt', 'F'], description: '格式化代码', category: 'editing' },

  // Agent
  { keys: ['Ctrl', 'Enter'], description: '发送消息（Agent模式）', category: 'agent' },
  { keys: ['Shift', 'Enter'], description: '换行', category: 'agent' },
  { keys: ['Esc'], description: '停止生成 / 关闭面板', category: 'agent' },
  { keys: ['Ctrl', 'I'], description: '打开Inline编辑', category: 'agent' },
  { keys: ['Ctrl', 'J'], description: '打开Agent面板', category: 'agent' },
  { keys: ['Ctrl', 'L'], description: '选中代码并提问', category: 'agent' },
  { keys: ['Tab'], description: '接受建议 / 切换模式', category: 'agent' },

  // View
  { keys: ['Ctrl', 'B'], description: '切换侧边栏', category: 'view', global: true },
  { keys: ['Ctrl', ','], description: '打开设置', category: 'view', global: true },
  { keys: ['Ctrl', 'N'], description: '新建会话', category: 'view', global: true },
  { keys: ['Ctrl', '\\'], description: '拆分编辑器', category: 'view' },
  { keys: ['Ctrl', '='], description: '放大字体', category: 'view' },
  { keys: ['Ctrl', '-'], description: '缩小字体', category: 'view' },
  { keys: ['Ctrl', '0'], description: '重置字体大小', category: 'view' },

  // System
  { keys: ['F1'], description: '显示帮助', category: 'system', global: true },
  { keys: ['F11'], description: '全屏切换', category: 'system', global: true },
  { keys: ['Ctrl', 'Shift', 'I'], description: '开发者工具', category: 'system' },
];

// ─────────────────────────────────────────────
// Category config
// ─────────────────────────────────────────────
const CATEGORY_CONFIG: Record<ShortcutItem['category'], { label: string; icon: string; color: string }> = {
  navigation: { label: '导航', icon: '🧭', color: 'text-blue-400' },
  editing: { label: '编辑', icon: '✏️', color: 'text-emerald-400' },
  agent: { label: 'Agent', icon: '🤖', color: 'text-purple-400' },
  view: { label: '视图', icon: '🖥️', color: 'text-amber-400' },
  system: { label: '系统', icon: '⚙️', color: 'text-gray-400' },
};

// ─────────────────────────────────────────────
// KeyCap component
// ─────────────────────────────────────────────
const KeyCap: React.FC<{ kbd: string }> = ({ kbd }) => {
  const isSpecial = ['Ctrl', 'Shift', 'Alt', 'Tab', 'Esc', 'Enter'].includes(kbd);
  return (
    <kbd
      className={`
        inline-flex items-center justify-center min-w-[28px] h-7 px-2
        rounded-md text-xs font-semibold font-mono
        transition-all
        ${isSpecial
          ? 'bg-white/[0.08] text-gray-300 border border-white/10'
          : 'bg-white/[0.12] text-white border border-white/20'
        }
        shadow-sm
      `}
    >
      {kbd}
    </kbd>
  );
};

// ─────────────────────────────────────────────
// ShortcutRow
// ─────────────────────────────────────────────
const ShortcutRow: React.FC<{ shortcut: ShortcutItem }> = ({ shortcut }) => {
  const cat = CATEGORY_CONFIG[shortcut.category];
  return (
    <motion.div
      variants={staggerItem}
      className="flex items-center justify-between gap-4 px-3 py-2.5 rounded-lg hover:bg-white/[0.04] transition-colors group"
    >
      <div className="flex items-center gap-3 min-w-0">
        <span className="text-sm flex-shrink-0">{cat.icon}</span>
        <span className="text-sm text-gray-300 truncate">{shortcut.description}</span>
        {shortcut.global && (
          <span className="flex-shrink-0 text-[10px] px-1.5 py-0.5 rounded bg-white/[0.06] text-gray-500 border border-white/5">
            global
          </span>
        )}
      </div>
      <div className="flex items-center gap-1 flex-shrink-0">
        {shortcut.keys.map((k, i) => (
          <React.Fragment key={i}>
            {i > 0 && <span className="text-gray-600 text-xs">+</span>}
            <KeyCap kbd={k} />
          </React.Fragment>
        ))}
      </div>
    </motion.div>
  );
};

// ─────────────────────────────────────────────
// CategorySection
// ─────────────────────────────────────────────
const CategorySection: React.FC<{
  category: ShortcutItem['category'];
  shortcuts: ShortcutItem[];
}> = ({ category, shortcuts }) => {
  const cat = CATEGORY_CONFIG[category];
  if (shortcuts.length === 0) return null;
  return (
    <motion.div variants={staggerItem} className="mb-6">
      <div className="flex items-center gap-2 mb-2 px-3">
        <span className="text-base">{cat.icon}</span>
        <h3 className={`text-sm font-semibold ${cat.color}`}>{cat.label}</h3>
        <span className="text-xs text-gray-600">({shortcuts.length})</span>
        <div className="flex-1 h-px bg-gradient-to-r from-white/10 to-transparent" />
      </div>
      <motion.div variants={staggerContainer} initial="hidden" animate="visible">
        {shortcuts.map((s, i) => (
          <ShortcutRow key={i} shortcut={s} />
        ))}
      </motion.div>
    </motion.div>
  );
};

// ─────────────────────────────────────────────
// Main EnhancedShortcutHelp
// ─────────────────────────────────────────────
export const EnhancedShortcutHelp: React.FC<EnhancedShortcutHelpProps> = ({ isOpen, onClose }) => {
  const [query, setQuery] = useState('');
  const [activeCategory, setActiveCategory] = useState<ShortcutItem['category'] | 'all'>('all');

  // Filtered shortcuts
  const filtered = useMemo(() => {
    const q = query.toLowerCase().trim();
    return SHORTCUTS.filter((s) => {
      const matchesQuery =
        !q ||
        s.description.toLowerCase().includes(q) ||
        s.keys.some((k) => k.toLowerCase().includes(q));
      const matchesCategory = activeCategory === 'all' || s.category === activeCategory;
      return matchesQuery && matchesCategory;
    });
  }, [query, activeCategory]);

  // Group by category
  const grouped = useMemo(() => {
    const map = new Map<ShortcutItem['category'], ShortcutItem[]>();
    for (const s of filtered) {
      if (!map.has(s.category)) map.set(s.category, []);
      map.get(s.category)!.push(s);
    }
    return map;
  }, [filtered]);

  // Escape to close
  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === 'Escape') {
        e.preventDefault();
        onClose();
      }
    },
    [onClose]
  );

  const categories: (ShortcutItem['category'] | 'all')[] = ['all', 'navigation', 'editing', 'agent', 'view', 'system'];

  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          variants={modalBackdrop}
          initial="hidden"
          animate="visible"
          exit="hidden"
          className="fixed inset-0 z-[100] flex items-center justify-center bg-black/60 backdrop-blur-sm"
          onClick={onClose}
          onKeyDown={handleKeyDown}
        >
          <motion.div
            variants={modalContent}
            className="w-full max-w-2xl max-h-[80vh] flex flex-col rounded-2xl bg-[#1e1e2e] border border-white/10 shadow-2xl overflow-hidden"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Header */}
            <div className="flex items-center justify-between px-6 py-4 border-b border-white/[0.06]">
              <div className="flex items-center gap-3">
                <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-purple-500/30 to-blue-500/30 flex items-center justify-center">
                  <svg className="w-4 h-4 text-purple-300" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M12 6V4m0 2a2 2 0 100 4m0-4a2 2 0 110 4m-6 8a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4m6 6v10" />
                  </svg>
                </div>
                <h2 className="text-lg font-semibold text-white">键盘快捷键</h2>
              </div>
              <button
                onClick={onClose}
                className="w-8 h-8 rounded-lg hover:bg-white/10 flex items-center justify-center text-gray-400 hover:text-white transition-colors"
              >
                <svg className="w-4 h-4" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
                  <path strokeLinecap="round" strokeLinejoin="round" d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            {/* Search */}
            <div className="px-6 py-3 border-b border-white/[0.04]">
              <div className="relative">
                <svg
                  className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-gray-500"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  strokeWidth={2}
                >
                  <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
                </svg>
                <input
                  type="text"
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="搜索快捷键..."
                  autoFocus
                  className="w-full pl-10 pr-4 py-2 text-sm bg-white/[0.04] border border-white/[0.08] rounded-lg text-white placeholder-gray-500 focus:outline-none focus:border-purple-500/40 focus:bg-white/[0.06] transition-all"
                />
                {query && (
                  <button
                    onClick={() => setQuery('')}
                    className="absolute right-3 top-1/2 -translate-y-1/2 text-gray-500 hover:text-white"
                  >
                    ✕
                  </button>
                )}
              </div>
            </div>

            {/* Category tabs */}
            <div className="flex items-center gap-1 px-6 py-2 border-b border-white/[0.04] overflow-x-auto">
              {categories.map((cat) => {
                const isActive = activeCategory === cat;
                const label = cat === 'all' ? '全部' : CATEGORY_CONFIG[cat as ShortcutItem['category']].label;
                const count = cat === 'all' ? SHORTCUTS.length : SHORTCUTS.filter((s) => s.category === cat).length;
                return (
                  <button
                    key={cat}
                    onClick={() => setActiveCategory(cat)}
                    className={`
                      px-3 py-1.5 rounded-md text-xs font-medium transition-all whitespace-nowrap
                      ${isActive
                        ? 'bg-purple-500/20 text-purple-300 border border-purple-500/30'
                        : 'text-gray-400 hover:text-white hover:bg-white/[0.04] border border-transparent'
                      }
                    `}
                  >
                    {label} <span className="opacity-50">({count})</span>
                  </button>
                );
              })}
            </div>

            {/* Shortcuts list */}
            <div className="flex-1 overflow-y-auto px-6 py-4">
              {filtered.length === 0 ? (
                <div className="flex flex-col items-center justify-center py-12 text-gray-500">
                  <svg className="w-10 h-10 mb-3 opacity-30" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                    <path strokeLinecap="round" strokeLinejoin="round" d="M9.172 16.172a4 4 0 015.656 0M9 10h.01M15 10h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  <p className="text-sm">没有找到匹配的快捷键</p>
                </div>
              ) : (
                <motion.div variants={staggerContainer} initial="hidden" animate="visible">
                  {(['navigation', 'editing', 'agent', 'view', 'system'] as const).map((cat) => (
                    <CategorySection
                      key={cat}
                      category={cat}
                      shortcuts={grouped.get(cat) || []}
                    />
                  ))}
                </motion.div>
              )}
            </div>

            {/* Footer */}
            <div className="px-6 py-3 border-t border-white/[0.06] flex items-center justify-between">
              <p className="text-xs text-gray-500">
                共 {SHORTCUTS.length} 个快捷键 · 显示 {filtered.length} 个
              </p>
              <div className="flex items-center gap-2 text-xs text-gray-500">
                <KeyCap kbd="Esc" />
                <span>关闭</span>
              </div>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
};

export default EnhancedShortcutHelp;
