'use client';

import { memo, useState, useCallback, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useAppStore } from '@/lib/store';
import { useCollaborationStore } from '@/stores/collaborationStore';

// ── Types ──────────────────────────────────────────────────────────────

type SharePermission = 'readonly' | 'writable';
type ExpiryOption = '1h' | '1d' | '7d' | 'never';

interface ShareDialogProps {
  open: boolean;
  onClose: () => void;
}

const EXPIRY_LABELS: Record<ExpiryOption, string> = {
  '1h': '1 Hour',
  '1d': '1 Day',
  '7d': '7 Days',
  'never': 'Never',
};

const EXPIRY_VALUES: Record<ExpiryOption, number | null> = {
  '1h': 3600,
  '1d': 86400,
  '7d': 604800,
  'never': null,
};

// ── Helpers ────────────────────────────────────────────────────────────

function generateMockShareLink(
  sessionId: string,
  permission: SharePermission,
  expiry: ExpiryOption,
): string {
  const base = 'https://likecodex.dev/share';
  const token = `${sessionId.slice(0, 8)}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`;
  const params = new URLSearchParams({
    token,
    permission,
    expiry: EXPIRY_VALUES[expiry]?.toString() || '0',
  });
  return `${base}/${token}?${params.toString()}`;
}

// ── Sub-components ─────────────────────────────────────────────────────

const ExpiryOptionButton = memo(function ExpiryOptionButton({
  value,
  selected,
  onClick,
}: {
  value: ExpiryOption;
  selected: boolean;
  onClick: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`px-2.5 py-1 rounded text-[10px] font-medium transition-all ${
        selected
          ? 'bg-primary/20 text-primary border border-primary/30'
          : 'text-muted hover:text-foreground hover:bg-accent/10 border border-transparent'
      }`}
    >
      {EXPIRY_LABELS[value]}
    </button>
  );
});

const PermissionButton = memo(function PermissionButton({
  value,
  selected,
  onClick,
  icon,
  label,
  description,
}: {
  value: SharePermission;
  selected: boolean;
  onClick: () => void;
  icon: string;
  label: string;
  description: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`flex-1 flex items-center gap-2 px-3 py-2.5 rounded-lg border text-left transition-all ${
        selected
          ? 'bg-primary/10 border-primary/30'
          : 'bg-background/30 border-border/60 hover:border-border hover:bg-accent/5'
      }`}
    >
      <span className="text-base">{icon}</span>
      <div className="flex flex-col">
        <span className={`text-xs font-medium ${selected ? 'text-primary' : 'text-foreground'}`}>
          {label}
        </span>
        <span className="text-[10px] text-muted/70">{description}</span>
      </div>
    </button>
  );
});

// ── Main Dialog ─────────────────────────────────────────────────────────

export const ShareDialog = memo(function ShareDialog({ open, onClose }: ShareDialogProps) {
  const currentSessionId = useAppStore((s) => s.currentSessionId);
  const addToast = useAppStore((s) => s.addToast);
  const setShareLink = useCollaborationStore((s) => s.setShareLink);
  const enable = useCollaborationStore((s) => s.enable);

  const [permission, setPermission] = useState<SharePermission>('readonly');
  const [expiry, setExpiry] = useState<ExpiryOption>('1d');
  const [generatedLink, setGeneratedLink] = useState<string | null>(null);
  const [copied, setCopied] = useState(false);
  const [showPreview, setShowPreview] = useState(false);
  const linkInputRef = useRef<HTMLInputElement>(null);

  // Reset state when dialog opens
  useEffect(() => {
    if (open) {
      setPermission('readonly');
      setExpiry('1d');
      setGeneratedLink(null);
      setCopied(false);
      setShowPreview(false);
    }
  }, [open]);

  // ── Generate Link ──────────────────────────────────────────────────
  const handleGenerateLink = useCallback(() => {
    const sessionId = currentSessionId || `session-${Date.now().toString(36)}`;
    const link = generateMockShareLink(sessionId, permission, expiry);

    setGeneratedLink(link);
    setShareLink(link);
    enable();
    setShowPreview(true);
  }, [currentSessionId, permission, expiry, setShareLink, enable]);

  // ── Copy Link ──────────────────────────────────────────────────────
  const handleCopyLink = useCallback(async () => {
    if (!generatedLink) return;

    try {
      await navigator.clipboard.writeText(generatedLink);
      setCopied(true);
      addToast({ type: 'success', message: 'Share link copied to clipboard' });
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback: select the input text manually
      linkInputRef.current?.select();
      addToast({ type: 'info', message: 'Select the link manually (Ctrl+C)' });
    }
  }, [generatedLink, addToast]);

  // ── Regenerate ─────────────────────────────────────────────────────
  const handleRegenerate = useCallback(() => {
    handleGenerateLink();
  }, [handleGenerateLink]);

  // ── Escape key ─────────────────────────────────────────────────────
  useEffect(() => {
    if (!open) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [open, onClose]);

  // ── Render ─────────────────────────────────────────────────────────
  return (
    <AnimatePresence>
      {open && (
        <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
          {/* Overlay */}
          <motion.div
            key="share-overlay"
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
            transition={{ duration: 0.2 }}
            className="absolute inset-0 bg-black/60"
            onClick={onClose}
          />

          {/* Dialog */}
          <motion.div
            key="share-dialog"
            initial={{ opacity: 0, scale: 0.92, y: 20 }}
            animate={{ opacity: 1, scale: 1, y: 0 }}
            exit={{ opacity: 0, scale: 0.92, y: 20 }}
            transition={{ type: 'spring', stiffness: 300, damping: 28 }}
            className="relative bg-surface border border-border rounded-xl shadow-2xl max-w-lg w-full max-h-[85vh] flex flex-col overflow-hidden"
          >
            {/* Header */}
            <div className="flex items-center justify-between px-5 py-4 border-b border-border shrink-0">
              <div>
                <h3 className="text-sm font-semibold text-foreground">Share Session</h3>
                <p className="text-[11px] text-muted mt-0.5">
                  Invite others to collaborate on this session
                </p>
              </div>
              <button
                type="button"
                onClick={onClose}
                className="text-muted hover:text-foreground transition-colors p-1 rounded hover:bg-accent/10"
                title="Close"
              >
                <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>

            {/* Body */}
            <div className="flex-1 overflow-y-auto px-5 py-4 space-y-5 scrollbar-thin">
              {/* Permission Selection */}
              <div>
                <label className="text-[11px] font-medium text-muted uppercase tracking-wider mb-2 block">
                  Permission
                </label>
                <div className="flex gap-2">
                  <PermissionButton
                    value="readonly"
                    selected={permission === 'readonly'}
                    onClick={() => setPermission('readonly')}
                    icon="👁️"
                    label="Read-only"
                    description="View session content only"
                  />
                  <PermissionButton
                    value="writable"
                    selected={permission === 'writable'}
                    onClick={() => setPermission('writable')}
                    icon="✏️"
                    label="Writable"
                    description="Can edit and contribute"
                  />
                </div>
              </div>

              {/* Expiry Selection */}
              <div>
                <label className="text-[11px] font-medium text-muted uppercase tracking-wider mb-2 block">
                  Expires In
                </label>
                <div className="flex gap-1.5 flex-wrap">
                  {(Object.keys(EXPIRY_LABELS) as ExpiryOption[]).map((opt) => (
                    <ExpiryOptionButton
                      key={opt}
                      value={opt}
                      selected={expiry === opt}
                      onClick={() => setExpiry(opt)}
                    />
                  ))}
                </div>
              </div>

              {/* Generate Button */}
              <motion.button
                type="button"
                whileHover={{ scale: 1.01 }}
                whileTap={{ scale: 0.98 }}
                onClick={handleGenerateLink}
                className="w-full flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg bg-primary hover:bg-blue-600 text-white text-xs font-medium transition-colors"
              >
                <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" />
                </svg>
                Generate Share Link
              </motion.button>

              {/* Generated Link */}
              <AnimatePresence>
                {generatedLink && (
                  <motion.div
                    initial={{ opacity: 0, height: 0 }}
                    animate={{ opacity: 1, height: 'auto' }}
                    exit={{ opacity: 0, height: 0 }}
                    transition={{ duration: 0.25 }}
                    className="space-y-3 overflow-hidden"
                  >
                    {/* Link copy area */}
                    <div>
                      <label className="text-[11px] font-medium text-muted uppercase tracking-wider mb-2 block">
                        Share Link
                      </label>
                      <div className="flex gap-2">
                        <input
                          ref={linkInputRef}
                          type="text"
                          readOnly
                          value={generatedLink}
                          className="flex-1 px-3 py-2 rounded-lg bg-background/60 border border-border text-xs text-foreground font-mono truncate outline-none focus:border-primary/50"
                        />
                        <motion.button
                          type="button"
                          whileTap={{ scale: 0.95 }}
                          onClick={handleCopyLink}
                          className={`px-3 py-2 rounded-lg text-xs font-medium transition-colors shrink-0 ${
                            copied
                              ? 'bg-green-500/20 text-green-400 border border-green-500/30'
                              : 'bg-accent/10 text-muted hover:text-foreground border border-border hover:bg-accent/20'
                          }`}
                          title="Copy to clipboard"
                        >
                          {copied ? (
                            <span className="flex items-center gap-1">
                              <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                              </svg>
                              Copied
                            </span>
                          ) : (
                            <span className="flex items-center gap-1">
                              <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                              </svg>
                              Copy
                            </span>
                          )}
                        </motion.button>
                      </div>
                    </div>

                    {/* Regenerate */}
                    <button
                      type="button"
                      onClick={handleRegenerate}
                      className="text-[10px] text-muted hover:text-foreground underline underline-offset-2 transition-colors"
                    >
                      Regenerate link
                    </button>

                    {/* Share Preview */}
                    <motion.div
                      initial={{ opacity: 0, y: 8 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: 0.15 }}
                      className="rounded-lg border border-border/60 bg-background/30 p-3 space-y-2"
                    >
                      <div className="flex items-center justify-between">
                        <span className="text-[10px] font-medium text-muted uppercase tracking-wider">
                          Preview
                        </span>
                        <button
                          type="button"
                          onClick={() => setShowPreview(!showPreview)}
                          className="text-[10px] text-muted hover:text-foreground transition-colors"
                        >
                          {showPreview ? 'Hide' : 'Show'}
                        </button>
                      </div>

                      {showPreview && (
                        <div className="space-y-2">
                          <div className="flex items-center gap-2 text-xs text-foreground">
                            <span className="text-muted text-[10px]">Session:</span>
                            <span className="font-medium truncate">
                              {currentSessionId
                                ? currentSessionId.slice(0, 12) + '...'
                                : 'Current session'}
                            </span>
                          </div>
                          <div className="flex items-center gap-3 text-[10px] text-muted">
                            <span className="flex items-center gap-1">
                              <span className="inline-block h-1.5 w-1.5 rounded-full bg-green-500" />
                              {permission === 'readonly' ? 'Read-only' : 'Writable'}
                            </span>
                            <span>
                              Expires: {EXPIRY_LABELS[expiry]}
                            </span>
                          </div>
                          <div className="pt-1 border-t border-border/40">
                            <p className="text-[10px] text-muted/60 italic">
                              Recipients with this link can{' '}
                              {permission === 'readonly'
                                ? 'view the session content and messages.'
                                : 'view, edit, and contribute to the session in real-time.'}
                            </p>
                          </div>
                        </div>
                      )}
                    </motion.div>
                  </motion.div>
                )}
              </AnimatePresence>
            </div>

            {/* Footer */}
            <div className="flex items-center justify-between px-5 py-3 border-t border-border bg-background/20 shrink-0">
              <span className="text-[10px] text-muted/50">
                Session sharing is disabled when not in a room
              </span>
              <button
                type="button"
                onClick={onClose}
                className="px-3 py-1.5 rounded-lg border border-border text-xs text-muted hover:text-foreground hover:bg-accent/10 transition-colors"
              >
                Close
              </button>
            </div>
          </motion.div>
        </div>
      )}
    </AnimatePresence>
  );
});

export default ShareDialog;
