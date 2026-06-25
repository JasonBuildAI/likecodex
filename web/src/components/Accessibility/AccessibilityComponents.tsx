'use client';

import React from 'react';
import { useAccessibility } from '@/hooks/useI18n';

// ─────────────────────────────────────────────
// SkipLinks - Skip to content for keyboard users
// ─────────────────────────────────────────────
export const SkipLinks: React.FC = () => (
  <nav className="sr-only" aria-label="Skip navigation">
    <a
      href="#main-content"
      className="absolute left-4 top-4 z-[300] px-4 py-2 rounded-lg bg-purple-600 text-white text-sm font-medium opacity-0 focus:opacity-100 focus:not-sr-only transition-opacity"
    >
      跳到主内容
    </a>
    <a
      href="#chat-input"
      className="absolute left-4 top-14 z-[300] px-4 py-2 rounded-lg bg-purple-600 text-white text-sm font-medium opacity-0 focus:opacity-100 focus:not-sr-only transition-opacity"
    >
      跳到输入框
    </a>
    <a
      href="#sidebar"
      className="absolute left-4 top-24 z-[300] px-4 py-2 rounded-lg bg-purple-600 text-white text-sm font-medium opacity-0 focus:opacity-100 focus:not-sr-only transition-opacity"
    >
      跳到侧边栏
    </a>
  </nav>
);

// ─────────────────────────────────────────────
// AccessibilitySettings - Settings panel
// ─────────────────────────────────────────────
interface AccessibilitySettingsProps {
  isOpen: boolean;
  onClose: () => void;
}

export const AccessibilitySettings: React.FC<AccessibilitySettingsProps> = ({ isOpen, onClose }) => {
  const { prefersReducedMotion, highContrast, fontSize, setFontSize, cycleFontSize } = useAccessibility();

  if (!isOpen) return null;

  return (
    <div className="fixed inset-0 z-[100] flex items-center justify-center bg-black/40" onClick={onClose}>
      <div
        className="w-full max-w-sm rounded-xl bg-[#1e1e2e] border border-white/10 p-6"
        onClick={(e) => e.stopPropagation()}
        role="dialog"
        aria-label="无障碍设置"
      >
        <h2 className="text-lg font-semibold text-white mb-4">无障碍设置</h2>

        {/* Font size */}
        <div className="mb-4">
          <label className="text-sm text-gray-400 mb-2 block">字体大小</label>
          <div className="flex gap-2">
            {(['small', 'medium', 'large'] as const).map((size) => (
              <button
                key={size}
                onClick={() => setFontSize(size)}
                className={`px-3 py-1.5 rounded-lg text-sm transition-all ${
                  fontSize === size
                    ? 'bg-purple-500/20 text-purple-300 border border-purple-500/30'
                    : 'text-gray-400 border border-white/10 hover:border-white/20'
                }`}
              >
                {size === 'small' ? '小' : size === 'medium' ? '中' : '大'}
              </button>
            ))}
          </div>
        </div>

        {/* Reduced motion status */}
        <div className="mb-4 flex items-center justify-between">
          <span className="text-sm text-gray-400">减少动画</span>
          <span className={`text-xs ${prefersReducedMotion ? 'text-emerald-400' : 'text-gray-500'}`}>
            {prefersReducedMotion ? '已启用（系统）' : '未启用'}
          </span>
        </div>

        {/* High contrast status */}
        <div className="mb-6 flex items-center justify-between">
          <span className="text-sm text-gray-400">高对比度</span>
          <span className={`text-xs ${highContrast ? 'text-emerald-400' : 'text-gray-500'}`}>
            {highContrast ? '已启用（系统）' : '未启用'}
          </span>
        </div>

        {/* Close button */}
        <button
          onClick={onClose}
          className="w-full py-2 rounded-lg text-sm font-medium text-white bg-purple-600 hover:bg-purple-500 transition-colors"
        >
          关闭
        </button>
      </div>
    </div>
  );
};

// ─────────────────────────────────────────────
// AriaLiveRegion - For screen reader announcements
// ─────────────────────────────────────────────
interface AriaLiveRegionProps {
  message: string;
  politeness?: 'polite' | 'assertive';
}

export const AriaLiveRegion: React.FC<AriaLiveRegionProps> = ({ message, politeness = 'polite' }) => (
  <div
    aria-live={politeness}
    aria-atomic="true"
    className="sr-only"
  >
    {message}
  </div>
);
