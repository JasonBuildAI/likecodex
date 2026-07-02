'use client';

import { memo, useState, useCallback, useEffect, useRef } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useCollaborationStore, type Collaborator } from '@/stores/collaborationStore';
import { useAppStore } from '@/lib/store';

// ── Types ──────────────────────────────────────────────────────────────

interface CollaborationPanelProps {
  /** Called when the panel is minimized */
  onMinimize?: () => void;
  /** Called when ShareDialog should open */
  onOpenShare?: () => void;
}

// ── Constants ──────────────────────────────────────────────────────────

const CONNECTION_LABELS: Record<string, string> = {
  connected: 'Connected',
  connecting: 'Connecting...',
  disconnected: 'Disconnected',
};

const CONNECTION_COLORS: Record<string, string> = {
  connected: 'bg-green-500',
  connecting: 'bg-yellow-500 animate-pulse',
  disconnected: 'bg-red-500',
};

// ── Sub-components ─────────────────────────────────────────────────────

/** Single collaborator row with avatar, name, and cursor info */
const CollaboratorRow = memo(function CollaboratorRow({
  collaborator,
  isSelf,
}: {
  collaborator: Collaborator;
  isSelf: boolean;
}) {
  const initials = collaborator.name
    .split(' ')
    .map((s) => s[0])
    .join('')
    .toUpperCase()
    .slice(0, 2);

  return (
    <motion.div
      initial={{ opacity: 0, x: -12 }}
      animate={{ opacity: 1, x: 0 }}
      exit={{ opacity: 0, x: -12 }}
      transition={{ type: 'spring', stiffness: 300, damping: 28 }}
      className={`flex items-center gap-2.5 px-2.5 py-2 rounded-lg transition-colors ${
        isSelf ? 'bg-primary/5' : 'hover:bg-accent/10'
      }`}
    >
      {/* Avatar */}
      <div className="relative shrink-0">
        {collaborator.avatar ? (
          <img
            src={collaborator.avatar}
            alt={collaborator.name}
            className="h-7 w-7 rounded-full object-cover"
          />
        ) : (
          <div
            className={`h-7 w-7 rounded-full flex items-center justify-center text-[10px] font-semibold ${
              collaborator.isOnline
                ? 'bg-primary/20 text-primary'
                : 'bg-accent/10 text-muted'
            }`}
          >
            {initials}
          </div>
        )}
        {/* Online indicator */}
        {collaborator.isOnline && (
          <span className="absolute -bottom-0.5 -right-0.5 h-2.5 w-2.5 rounded-full bg-green-500 border-2 border-surface" />
        )}
      </div>

      {/* Name and status */}
      <div className="flex-1 min-w-0">
        <div className="flex items-center gap-1.5">
          <span className="text-xs font-medium text-foreground truncate">
            {collaborator.name}
          </span>
          {isSelf && (
            <span className="text-[9px] text-muted bg-accent/10 px-1 rounded">you</span>
          )}
        </div>
        {collaborator.cursorPosition && (
          <span className="text-[10px] text-muted/60 truncate block" title={`Line ${collaborator.cursorPosition.line}, Column ${collaborator.cursorPosition.column}`}>
            Ln {collaborator.cursorPosition.line}, Col {collaborator.cursorPosition.column}
          </span>
        )}
      </div>

      {/* Online dot */}
      <span
        className={`h-1.5 w-1.5 rounded-full shrink-0 ${
          collaborator.isOnline ? 'bg-green-500' : 'bg-muted/30'
        }`}
        title={collaborator.isOnline ? 'Online' : 'Offline'}
      />
    </motion.div>
  );
});

/** Connection status bar */
const ConnectionBadge = memo(function ConnectionBadge({
  status,
}: {
  status: 'disconnected' | 'connecting' | 'connected';
}) {
  return (
    <div className="flex items-center gap-1.5">
      <span className={`h-2 w-2 rounded-full ${CONNECTION_COLORS[status]}`} />
      <span className="text-[10px] text-muted font-medium">{CONNECTION_LABELS[status]}</span>
    </div>
  );
});

// ── Main Panel ─────────────────────────────────────────────────────────

export const CollaborationPanel = memo(function CollaborationPanel({
  onMinimize,
  onOpenShare,
}: CollaborationPanelProps) {
  const isEnabled = useCollaborationStore((s) => s.isEnabled);
  const roomId = useCollaborationStore((s) => s.roomId);
  const connectionStatus = useCollaborationStore((s) => s.connectionStatus);
  const collaborators = useCollaborationStore((s) => s.collaborators);
  const shareLink = useCollaborationStore((s) => s.shareLink);
  const userName = useCollaborationStore((s) => s.userName);
  const leaveRoom = useCollaborationStore((s) => s.leaveRoom);
  const joinRoom = useCollaborationStore((s) => s.joinRoom);
  const setShareLink = useCollaborationStore((s) => s.setShareLink);
  const addToast = useAppStore((s) => s.addToast);

  const [isMinimized, setIsMinimized] = useState(false);
  const [showInviteInput, setShowInviteInput] = useState(false);
  const [inviteCopied, setInviteCopied] = useState(false);
  const inviteInputRef = useRef<HTMLInputElement>(null);

  // Reset minimize when enabled
  useEffect(() => {
    if (isEnabled) {
      setIsMinimized(false);
    }
  }, [isEnabled]);

  // ── Handle Join Room ───────────────────────────────────────────────
  const handleJoinRoom = useCallback(() => {
    const newRoomId = `room-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 6)}`;
    joinRoom(newRoomId);

    // Simulate connection delay, then mock a collaborator
    const link = `https://likecodex.dev/collab/${newRoomId}`;
    setShareLink(link);

    setTimeout(() => {
      useCollaborationStore.getState().setConnectionStatus('connected');
      useCollaborationStore.getState().addCollaborator({
        id: `user-${Date.now()}`,
        name: userName,
        isOnline: true,
      });
      addToast({ type: 'success', message: 'Joined collaboration room' });
    }, 1200);
  }, [joinRoom, setShareLink, userName, addToast]);

  // ── Handle Leave Room ──────────────────────────────────────────────
  const handleLeave = useCallback(() => {
    leaveRoom();
    setInviteCopied(false);
    setShowInviteInput(false);
    addToast({ type: 'info', message: 'Left collaboration room' });
  }, [leaveRoom, addToast]);

  // ── Handle Invite Copy ─────────────────────────────────────────────
  const handleCopyInvite = useCallback(async () => {
    if (!shareLink) return;
    try {
      await navigator.clipboard.writeText(shareLink);
      setInviteCopied(true);
      addToast({ type: 'success', message: 'Invite link copied' });
      setTimeout(() => setInviteCopied(false), 2000);
    } catch {
      inviteInputRef.current?.select();
      addToast({ type: 'info', message: 'Select the invite link manually' });
    }
  }, [shareLink, addToast]);

  // ── Handle Minimize ────────────────────────────────────────────────
  const handleMinimize = useCallback(() => {
    setIsMinimized(true);
    onMinimize?.();
  }, [onMinimize]);

  // If not enabled, show a simple "Start Collaboration" CTA
  if (!isEnabled && !isMinimized) {
    return (
      <motion.div
        initial={{ opacity: 0, y: 10 }}
        animate={{ opacity: 1, y: 0 }}
        className="rounded-xl border border-border/60 bg-surface/50 p-4"
      >
        <div className="flex flex-col items-center gap-3 text-center">
          <div className="h-10 w-10 rounded-full bg-primary/10 flex items-center justify-center">
            <svg className="h-5 w-5 text-primary" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0zm6 3a2 2 0 11-4 0 2 2 0 014 0zM7 10a2 2 0 11-4 0 2 2 0 014 0z" />
            </svg>
          </div>
          <div>
            <h4 className="text-xs font-semibold text-foreground">Collaboration</h4>
            <p className="text-[10px] text-muted mt-0.5">
              Share your session and work together in real-time
            </p>
          </div>
          <div className="flex gap-2 w-full">
            <motion.button
              type="button"
              whileHover={{ scale: 1.02 }}
              whileTap={{ scale: 0.98 }}
              onClick={handleJoinRoom}
              className="flex-1 px-3 py-1.5 rounded-lg bg-primary hover:bg-blue-600 text-white text-xs font-medium transition-colors"
            >
              Start Collaboration
            </motion.button>
            {onOpenShare && (
              <button
                type="button"
                onClick={onOpenShare}
                className="px-3 py-1.5 rounded-lg border border-border text-xs text-muted hover:text-foreground hover:bg-accent/10 transition-colors"
                title="Open share dialog"
              >
                <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8.684 13.342C8.886 12.938 9 12.482 9 12c0-.482-.114-.938-.316-1.342m0 2.684a3 3 0 110-2.684m0 2.684l6.632 3.316m-6.632-6l6.632-3.316m0 0a3 3 0 105.367-2.684 3 3 0 00-5.367 2.684zm0 9.316a3 3 0 105.368 2.684 3 3 0 00-5.368-2.684z" />
                </svg>
              </button>
            )}
          </div>
        </div>
      </motion.div>
    );
  }

  // Minimized state
  if (isMinimized) {
    return null;
  }

  // Disconnected (but was previously enabled)
  if (connectionStatus === 'disconnected' && !roomId) {
    return (
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        className="rounded-xl border border-border/60 bg-surface/50 p-4"
      >
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2">
            <span className="h-2 w-2 rounded-full bg-red-500" />
            <span className="text-xs text-muted font-medium">Disconnected</span>
          </div>
          <button
            type="button"
            onClick={handleJoinRoom}
            className="px-2.5 py-1 rounded-lg bg-primary/10 text-primary text-[10px] font-medium hover:bg-primary/20 transition-colors"
          >
            Reconnect
          </button>
        </div>
      </motion.div>
    );
  }

  // ── Active collaboration panel ─────────────────────────────────────
  const onlineCount = collaborators.filter((c) => c.isOnline).length;

  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: 10 }}
      className="rounded-xl border border-border/60 bg-surface/50 overflow-hidden"
    >
      {/* Room header */}
      <div className="flex items-center justify-between px-3 py-2.5 border-b border-border/60 bg-background/20">
        <div className="flex items-center gap-2 min-w-0">
          {/* Connection status */}
          <ConnectionBadge status={connectionStatus} />
          {onlineCount > 0 && (
            <span className="text-[10px] text-muted/70">
              {onlineCount} online
            </span>
          )}
        </div>
        <div className="flex items-center gap-1">
          {/* Share button */}
          <button
            type="button"
            onClick={onOpenShare}
            className="p-1.5 rounded hover:bg-accent/10 text-muted hover:text-foreground transition-colors"
            title="Share session"
          >
            <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8.684 13.342C8.886 12.938 9 12.482 9 12c0-.482-.114-.938-.316-1.342m0 2.684a3 3 0 110-2.684m0 2.684l6.632 3.316m-6.632-6l6.632-3.316m0 0a3 3 0 105.367-2.684 3 3 0 00-5.367 2.684zm0 9.316a3 3 0 105.368 2.684 3 3 0 00-5.368-2.684z" />
            </svg>
          </button>
          {/* Minimize button */}
          <button
            type="button"
            onClick={handleMinimize}
            className="p-1.5 rounded hover:bg-accent/10 text-muted hover:text-foreground transition-colors"
            title="Minimize"
          >
            <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
            </svg>
          </button>
        </div>
      </div>

      {/* Room info */}
      <div className="px-3 py-2 border-b border-border/40 bg-background/10">
        <div className="flex items-center gap-1.5 text-[10px] text-muted/70">
          <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M7 20l4-16 4 16m-6-2h4" />
          </svg>
          <span className="truncate font-mono">
            {roomId || 'No room'}
          </span>
        </div>
      </div>

      {/* Collaborators list */}
      <div className="py-1.5">
        <div className="px-3 py-1 flex items-center justify-between">
          <span className="text-[10px] font-medium text-muted uppercase tracking-wider">
            Collaborators
          </span>
          <span className="text-[9px] text-muted/50">
            {collaborators.length} total
          </span>
        </div>
        <div className="max-h-48 overflow-y-auto scrollbar-thin">
          <AnimatePresence>
            {collaborators.length === 0 ? (
              <motion.div
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                className="px-3 py-4 text-center"
              >
                <p className="text-[10px] text-muted/50">No collaborators yet</p>
                <p className="text-[9px] text-muted/40 mt-0.5">
                  Share the invite link to add people
                </p>
              </motion.div>
            ) : (
              collaborators.map((col) => (
                <CollaboratorRow
                  key={col.id}
                  collaborator={col}
                  isSelf={col.name === userName}
                />
              ))
            )}
          </AnimatePresence>
        </div>
      </div>

      {/* Invite link section */}
      <div className="border-t border-border/40 px-3 py-2">
        {showInviteInput ? (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            className="space-y-2 overflow-hidden"
          >
            <div className="flex gap-1.5">
              <input
                ref={inviteInputRef}
                type="text"
                readOnly
                value={shareLink || ''}
                placeholder="No link generated"
                className="flex-1 px-2 py-1.5 rounded bg-background/60 border border-border text-[10px] font-mono text-foreground truncate outline-none focus:border-primary/50"
              />
              <button
                type="button"
                onClick={handleCopyInvite}
                className={`px-2 py-1.5 rounded text-[10px] font-medium transition-colors shrink-0 ${
                  inviteCopied
                    ? 'bg-green-500/20 text-green-400 border border-green-500/30'
                    : 'bg-accent/10 text-muted hover:text-foreground border border-border'
                }`}
              >
                {inviteCopied ? 'Copied' : 'Copy'}
              </button>
            </div>
            <button
              type="button"
              onClick={() => setShowInviteInput(false)}
              className="text-[9px] text-muted/60 hover:text-muted transition-colors"
            >
              Hide invite link
            </button>
          </motion.div>
        ) : (
          <button
            type="button"
            onClick={() => setShowInviteInput(true)}
            className="w-full flex items-center justify-center gap-1.5 px-2 py-1.5 rounded-lg border border-dashed border-border/60 text-[10px] text-muted hover:text-foreground hover:border-border hover:bg-accent/5 transition-colors"
          >
            <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6v6m0 0v6m0-6h6m-6 0H6" />
            </svg>
            Show Invite Link
          </button>
        )}
      </div>

      {/* Footer actions */}
      <div className="flex items-center justify-between px-3 py-2 border-t border-border/60 bg-background/20">
        <span className="text-[9px] text-muted/50">
          Room • {roomId?.slice(0, 8) || '—'}
        </span>
        <motion.button
          type="button"
          whileHover={{ scale: 1.02 }}
          whileTap={{ scale: 0.98 }}
          onClick={handleLeave}
          className="px-2.5 py-1 rounded-lg border border-red-500/30 text-[10px] text-red-400 hover:bg-red-500/10 transition-colors"
        >
          Leave Room
        </motion.button>
      </div>
    </motion.div>
  );
});

export default CollaborationPanel;
