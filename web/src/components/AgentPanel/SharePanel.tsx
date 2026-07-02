'use client';

import { useState, useCallback } from 'react';

// ── Types ──────────────────────────────────────────────────────────────

interface ShareData {
  token: string;
  sessionId: string;
  url: string;
  expiresAt: string;
  hasPassword: boolean;
}

interface SharePanelProps {
  sessionId: string;
  /** If provided, shows existing share data */
  existingShare?: ShareData | null;
  onCreateShare: (expiryHours: number, password?: string) => Promise<ShareData>;
  onRevokeShare: (token: string) => Promise<void>;
  onExportMarkdown: () => string;
  onExportJSON: () => string;
  onClose?: () => void;
}

// ── Main Component ─────────────────────────────────────────────────────

export function SharePanel({
  sessionId,
  existingShare,
  onCreateShare,
  onRevokeShare,
  onExportMarkdown,
  onExportJSON,
  onClose,
}: SharePanelProps) {
  const [activeTab, setActiveTab] = useState<'share' | 'export'>('share');
  const [expiryHours, setExpiryHours] = useState(24);
  const [password, setPassword] = useState('');
  const [usePassword, setUsePassword] = useState(false);
  const [share, setShare] = useState<ShareData | null>(existingShare || null);
  const [loading, setLoading] = useState(false);
  const [copied, setCopied] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // ── Handlers ─────────────────────────────────────────────────────────

  const handleCreate = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await onCreateShare(expiryHours, usePassword ? password : undefined);
      setShare(result);
    } catch (e) {
      setError((e as Error).message || 'Failed to create share link');
    } finally {
      setLoading(false);
    }
  }, [expiryHours, password, usePassword, onCreateShare]);

  const handleRevoke = useCallback(async () => {
    if (!share) return;
    setLoading(true);
    setError(null);
    try {
      await onRevokeShare(share.token);
      setShare(null);
    } catch (e) {
      setError((e as Error).message || 'Failed to revoke share link');
    } finally {
      setLoading(false);
    }
  }, [share, onRevokeShare]);

  const handleCopy = useCallback(async (text: string) => {
    try {
      await navigator.clipboard.writeText(text);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // Fallback
      const ta = document.createElement('textarea');
      ta.value = text;
      document.body.appendChild(ta);
      ta.select();
      document.execCommand('copy');
      document.body.removeChild(ta);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  }, []);

  const handleExportMD = useCallback(() => {
    const md = onExportMarkdown();
    handleCopy(md);
  }, [onExportMarkdown, handleCopy]);

  const handleExportJSON = useCallback(() => {
    const json = onExportJSON();
    handleCopy(json);
  }, [onExportJSON, handleCopy]);

  // ── Render ───────────────────────────────────────────────────────────

  return (
    <div className="space-y-3">
      {/* Header */}
      <div className="flex items-center justify-between px-1">
        <span className="text-[10px] font-medium text-muted uppercase tracking-wider">
          Share & Export
        </span>
        {onClose && (
          <button
            onClick={onClose}
            className="text-muted/50 hover:text-muted p-0.5"
          >
            <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        )}
      </div>

      {/* Tabs */}
      <div className="flex border-b border-border/30">
        <button
          onClick={() => setActiveTab('share')}
          className={`text-[9px] px-3 py-1.5 border-b-2 transition-colors ${
            activeTab === 'share'
              ? 'border-primary text-primary'
              : 'border-transparent text-muted/50 hover:text-muted'
          }`}
        >
          Share Link
        </button>
        <button
          onClick={() => setActiveTab('export')}
          className={`text-[9px] px-3 py-1.5 border-b-2 transition-colors ${
            activeTab === 'export'
              ? 'border-primary text-primary'
              : 'border-transparent text-muted/50 hover:text-muted'
          }`}
        >
          Export
        </button>
      </div>

      {/* Error */}
      {error && (
        <div className="text-[9px] text-red-400 bg-red-500/10 border border-red-500/20 rounded px-2 py-1">
          {error}
        </div>
      )}

      {/* Success feedback */}
      {copied && (
        <div className="text-[9px] text-green-400 bg-green-500/10 border border-green-500/20 rounded px-2 py-1">
          Copied to clipboard!
        </div>
      )}

      {/* Share tab */}
      {activeTab === 'share' && (
        <div className="space-y-3 px-1">
          {share ? (
            <div className="space-y-2">
              <div className="bg-background/50 border border-border/20 rounded p-2">
                <div className="flex items-center justify-between mb-1">
                  <span className="text-[9px] text-muted/50">Share URL</span>
                  <button
                    onClick={() => handleCopy(share.url)}
                    className="text-[9px] text-primary hover:text-primary/80"
                  >
                    {copied ? 'Copied!' : 'Copy'}
                  </button>
                </div>
                <code className="text-[9px] font-mono text-foreground/80 break-all">
                  {share.url}
                </code>
              </div>
              <div className="flex items-center justify-between text-[9px] text-muted/50">
                <span>Expires: {share.expiresAt}</span>
                {share.hasPassword && <span>🔒 Password protected</span>}
              </div>
              <button
                onClick={handleRevoke}
                disabled={loading}
                className="w-full text-[9px] px-2 py-1 rounded border border-red-500/30 text-red-400 hover:bg-red-500/10 disabled:opacity-50 transition-colors"
              >
                {loading ? 'Revoking...' : 'Revoke Share Link'}
              </button>
            </div>
          ) : (
            <div className="space-y-2">
              {/* Expiry selector */}
              <div>
                <label className="text-[9px] text-muted/50 block mb-1">Expires after</label>
                <select
                  value={expiryHours}
                  onChange={(e) => setExpiryHours(Number(e.target.value))}
                  className="w-full text-[10px] bg-background border border-border rounded px-2 py-1 text-foreground outline-none"
                >
                  <option value={1}>1 hour</option>
                  <option value={6}>6 hours</option>
                  <option value={24}>24 hours</option>
                  <option value={72}>3 days</option>
                  <option value={168}>7 days</option>
                  <option value={720}>30 days</option>
                </select>
              </div>

              {/* Password toggle */}
              <div className="flex items-center gap-2">
                <input
                  type="checkbox"
                  id="use-password"
                  checked={usePassword}
                  onChange={(e) => setUsePassword(e.target.checked)}
                  className="rounded border-border bg-background"
                />
                <label htmlFor="use-password" className="text-[9px] text-muted/70">
                  Password protect
                </label>
              </div>

              {usePassword && (
                <input
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="Enter password..."
                  className="w-full text-[10px] bg-background border border-border rounded px-2 py-1 text-foreground outline-none"
                />
              )}

              <button
                onClick={handleCreate}
                disabled={loading || (usePassword && !password.trim())}
                className="w-full text-[9px] px-2 py-1.5 rounded bg-primary/80 text-white hover:bg-primary disabled:opacity-30 disabled:cursor-not-allowed transition-colors"
              >
                {loading ? 'Creating...' : 'Create Share Link'}
              </button>
            </div>
          )}
        </div>
      )}

      {/* Export tab */}
      {activeTab === 'export' && (
        <div className="space-y-2 px-1">
          <p className="text-[9px] text-muted/50">
            Export this session as Markdown or JSON and copy to clipboard.
          </p>
          <div className="grid grid-cols-2 gap-2">
            <button
              onClick={handleExportMD}
              className="flex items-center justify-center gap-1.5 px-3 py-2 rounded border border-border/40 text-muted/70 hover:text-foreground hover:bg-background transition-colors text-[10px]"
            >
              <span>📝</span>
              <span>Export MD</span>
            </button>
            <button
              onClick={handleExportJSON}
              className="flex items-center justify-center gap-1.5 px-3 py-2 rounded border border-border/40 text-muted/70 hover:text-foreground hover:bg-background transition-colors text-[10px]"
            >
              <span>📋</span>
              <span>Export JSON</span>
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

export default SharePanel;
