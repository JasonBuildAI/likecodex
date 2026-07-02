'use client';

import React, { useCallback, type KeyboardEvent } from 'react';
import { motion } from 'framer-motion';
import { usePreviewStore, DEFAULT_DEVICES, useDeviceDimensions } from './previewStore';

// ── Icons (inline SVG components to avoid external icon deps) ───────────

const GoIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="9 18 15 12 9 6" />
  </svg>
);

const RefreshIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="23 4 23 10 17 10" />
    <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10" />
  </svg>
);

const CloseIcon = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <line x1="18" y1="6" x2="6" y2="18" />
    <line x1="6" y1="6" x2="18" y2="18" />
  </svg>
);

const ChevronDownIcon = () => (
  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="6 9 12 15 18 9" />
  </svg>
);

// ── Props ──────────────────────────────────────────────────────────────

interface PreviewToolbarProps {
  onRefresh?: () => void;
  onClose?: () => void;
}

// ── Component ──────────────────────────────────────────────────────────

export const PreviewToolbar: React.FC<PreviewToolbarProps> = ({
  onRefresh,
  onClose,
}) => {
  const { url, setUrl, selectedDevice, setDevice, setLoading } = usePreviewStore();
  const [inputValue, setInputValue] = React.useState(url);
  const [showDeviceMenu, setShowDeviceMenu] = React.useState(false);
  const { width: deviceWidth, height: deviceHeight } = useDeviceDimensions();
  const menuRef = React.useRef<HTMLDivElement>(null);

  React.useEffect(() => {
    setInputValue(url);
  }, [url]);

  // Close device menu on outside click
  React.useEffect(() => {
    if (!showDeviceMenu) return;
    const handleClick = (e: MouseEvent) => {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setShowDeviceMenu(false);
      }
    };
    document.addEventListener('mousedown', handleClick);
    return () => document.removeEventListener('mousedown', handleClick);
  }, [showDeviceMenu]);

  const navigate = useCallback(() => {
    const trimmed = inputValue.trim();
    if (!trimmed) return;
    let normalized = trimmed;
    if (!/^https?:\/\//i.test(normalized)) {
      normalized = `https://${normalized}`;
    }
    setUrl(normalized);
    setLoading(true);
  }, [inputValue, setUrl, setLoading]);

  const handleKeyDown = useCallback(
    (e: KeyboardEvent<HTMLInputElement>) => {
      if (e.key === 'Enter') {
        navigate();
      }
    },
    [navigate],
  );

  const handleDeviceSelect = useCallback(
    (name: string) => {
      setDevice(name);
      setShowDeviceMenu(false);
    },
    [setDevice],
  );

  return (
    <motion.div
      initial={{ opacity: 0, y: -8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.2 }}
      className="flex items-center gap-2 px-3 py-2 bg-background border-b border-border"
    >
      {/* ── URL Bar ─────────────────────────────────────────────── */}
      <div className="flex-1 flex items-center gap-1">
        <input
          type="text"
          value={inputValue}
          onChange={(e) => setInputValue(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="输入 URL 或地址…"
          className="flex-1 px-3 py-1.5 bg-surface border border-border rounded-md
                     text-foreground text-sm placeholder-muted
                     focus:outline-none focus:ring-1 focus:ring-primary/50 focus:border-primary/50
                     transition-colors duration-fast"
        />
        <button
          type="button"
          onClick={navigate}
          title="前往"
          className="p-1.5 rounded-md text-muted hover:text-foreground hover:bg-surface
                     transition-colors duration-fast"
        >
          <GoIcon />
        </button>
      </div>

      {/* ── Device Selector ─────────────────────────────────────── */}
      <div className="relative" ref={menuRef}>
        <button
          type="button"
          onClick={() => setShowDeviceMenu((v) => !v)}
          title={`${selectedDevice} (${deviceWidth}×${deviceHeight})`}
          className="flex items-center gap-1.5 px-2.5 py-1.5 rounded-md
                     text-xs text-muted hover:text-foreground hover:bg-surface
                     border border-border
                     transition-colors duration-fast whitespace-nowrap"
        >
          <span>{selectedDevice}</span>
          <span className="text-[10px] opacity-60">
            {deviceWidth}×{deviceHeight}
          </span>
          <ChevronDownIcon />
        </button>

        {showDeviceMenu && (
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
            transition={{ duration: 0.15 }}
            className="absolute right-0 top-full mt-1 z-50 w-44
                       bg-surface border border-border rounded-lg shadow-xl
                       overflow-hidden"
          >
            {DEFAULT_DEVICES.map((d) => (
              <button
                key={d.name}
                type="button"
                onClick={() => handleDeviceSelect(d.name)}
                className={`w-full flex items-center justify-between px-3 py-2 text-xs
                             transition-colors duration-fast
                             ${selectedDevice === d.name
                               ? 'bg-primary/10 text-primary'
                               : 'text-muted hover:bg-surface/80 hover:text-foreground'
                             }`}
              >
                <span>{d.name}</span>
                <span className="opacity-50">
                  {d.width}×{d.height}
                </span>
              </button>
            ))}
          </motion.div>
        )}
      </div>

      {/* ── Refresh ────────────────────────────────────────────── */}
      <button
        type="button"
        onClick={onRefresh}
        title="刷新"
        className="p-1.5 rounded-md text-muted hover:text-foreground hover:bg-surface
                   transition-colors duration-fast"
      >
        <RefreshIcon />
      </button>

      {/* ── Close ──────────────────────────────────────────────── */}
      <button
        type="button"
        onClick={onClose}
        title="关闭预览"
        className="p-1.5 rounded-md text-muted hover:text-red-400 hover:bg-red-500/10
                   transition-colors duration-fast"
      >
        <CloseIcon />
      </button>
    </motion.div>
  );
};

export default PreviewToolbar;
