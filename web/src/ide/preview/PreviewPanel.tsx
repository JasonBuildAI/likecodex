'use client';

import React, { useCallback, useEffect, useRef, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { usePreviewStore, useDeviceDimensions } from './previewStore';
import { PreviewToolbar } from './PreviewToolbar';
import { PreviewConsole } from './PreviewConsole';

// ── Spinner ────────────────────────────────────────────────────────────

const Spinner = () => (
  <motion.div
    className="flex flex-col items-center gap-3 text-muted"
    initial={{ opacity: 0 }}
    animate={{ opacity: 1 }}
    exit={{ opacity: 0 }}
    transition={{ duration: 0.2 }}
  >
    <motion.div
      className="w-8 h-8 border-2 border-primary/30 border-t-primary rounded-full"
      animate={{ rotate: 360 }}
      transition={{ repeat: Infinity, duration: 0.8, ease: 'linear' }}
    />
    <span className="text-xs">加载中…</span>
  </motion.div>
);

// ── Main Component ─────────────────────────────────────────────────────

export const PreviewPanel: React.FC = () => {
  const { url, isOpen, isLoading, setLoading, setOpen } = usePreviewStore();
  const { width: deviceWidth } = useDeviceDimensions();
  const iframeRef = useRef<HTMLIFrameElement>(null);
  const [showConsole, setShowConsole] = useState(false);
  const iframeKey = useRef(0);

  // Reset loading state when URL changes (iframe onLoad will clear it)
  useEffect(() => {
    if (url) {
      setLoading(true);
      iframeKey.current += 1;
    }
  }, [url, setLoading]);

  const handleIframeLoad = useCallback(() => {
    setLoading(false);
  }, [setLoading]);

  const handleRefresh = useCallback(() => {
    if (iframeRef.current) {
      iframeRef.current.src = iframeRef.current.src;
      setLoading(true);
    }
  }, [setLoading]);

  const handleClose = useCallback(() => {
    setOpen(false);
  }, [setOpen]);

  if (!isOpen) return null;

  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          key="preview-panel"
          initial={{ opacity: 0, x: 320 }}
          animate={{ opacity: 1, x: 0 }}
          exit={{ opacity: 0, x: 320 }}
          transition={{ type: 'spring', stiffness: 300, damping: 30 }}
          className="flex flex-col h-full bg-background border-l border-border overflow-hidden"
          style={{ minWidth: 400, maxWidth: 780 }}
        >
          {/* ── Toolbar ──────────────────────────────────────────── */}
          <PreviewToolbar onRefresh={handleRefresh} onClose={handleClose} />

          {/* ── Preview Area ────────────────────────────────────── */}
          <div className="flex-1 flex items-center justify-center p-4 overflow-auto bg-gray-900/90">
            {url ? (
              <div
                className="relative bg-white rounded-lg shadow-2xl overflow-hidden transition-all duration-300"
                style={{
                  width: '100%',
                  maxWidth: deviceWidth > 0 ? deviceWidth : undefined,
                  aspectRatio: `${deviceWidth} / ${Math.max(Math.round(deviceWidth * 0.625), 600)}`,
                }}
              >
                {/* Loading overlay */}
                <AnimatePresence>
                  {isLoading && (
                    <motion.div
                      key="spinner"
                      initial={{ opacity: 0 }}
                      animate={{ opacity: 1 }}
                      exit={{ opacity: 0 }}
                      transition={{ duration: 0.15 }}
                      className="absolute inset-0 flex items-center justify-center bg-black/50 z-10"
                    >
                      <Spinner />
                    </motion.div>
                  )}
                </AnimatePresence>

                <iframe
                  ref={iframeRef}
                  key={iframeKey.current}
                  src={url}
                  title="预览"
                  onLoad={handleIframeLoad}
                  className="w-full h-full border-0"
                  sandbox="allow-scripts allow-same-origin allow-forms allow-popups"
                />
              </div>
            ) : (
              <div className="flex flex-col items-center gap-3 text-muted">
                <svg
                  width="48"
                  height="48"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="1.5"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  className="opacity-40"
                >
                  <rect x="2" y="3" width="20" height="14" rx="2" ry="2" />
                  <line x1="8" y1="21" x2="16" y2="21" />
                  <line x1="12" y1="17" x2="12" y2="21" />
                </svg>
                <span className="text-sm">在地址栏输入 URL 开始预览</span>
              </div>
            )}
          </div>

          {/* ── Console toggle ───────────────────────────────────── */}
          <button
            type="button"
            onClick={() => setShowConsole((v) => !v)}
            className="flex items-center justify-center gap-1.5 px-3 py-1.5
                       text-xs text-muted hover:text-foreground
                       border-t border-border
                       transition-colors duration-fast"
          >
            <svg
              width="12"
              height="12"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
              className={`transition-transform duration-200 ${showConsole ? 'rotate-180' : ''}`}
            >
              <polyline points="6 9 12 15 18 9" />
            </svg>
            Console
          </button>

          {/* ── Console panel ────────────────────────────────── */}
          <AnimatePresence>
            {showConsole && (
              <motion.div
                initial={{ height: 0, opacity: 0 }}
                animate={{ height: 160, opacity: 1 }}
                exit={{ height: 0, opacity: 0 }}
                transition={{ duration: 0.2 }}
                className="overflow-hidden border-t border-border"
              >
                <PreviewConsole />
              </motion.div>
            )}
          </AnimatePresence>
        </motion.div>
      )}
    </AnimatePresence>
  );
};

export default PreviewPanel;
