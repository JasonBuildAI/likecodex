'use client';

import { useState, useCallback, useMemo } from 'react';

// ── Types ──────────────────────────────────────────────────────────────

export interface PRFile {
  path: string;
  additions: number;
  deletions: number;
  status: 'added' | 'modified' | 'removed' | 'renamed';
}

export interface PRReview {
  id: string;
  author: string;
  body: string;
  state: 'approved' | 'changes_requested' | 'commented' | 'pending';
  submittedAt: string;
}

export interface PullRequestData {
  number: number;
  title: string;
  description: string;
  author: string;
  sourceBranch: string;
  targetBranch: string;
  state: 'open' | 'merged' | 'closed';
  createdAt: string;
  updatedAt: string;
  files: PRFile[];
  reviews: PRReview[];
  checks: { name: string; status: 'passing' | 'failing' | 'pending'; description?: string }[];
}

interface PRPanelProps {
  pr: PullRequestData;
  onMerge?: () => void;
  onClose?: () => void;
  onRequestChanges?: () => void;
  onApprove?: () => void;
  onAddComment?: (body: string) => void;
}

// ── Helpers ────────────────────────────────────────────────────────────

function formatCount(n: number): string {
  return n > 0 ? `+${n}` : String(n);
}

// ── Main Component ─────────────────────────────────────────────────────

export function PRPanel({
  pr,
  onMerge,
  onClose,
  onRequestChanges,
  onApprove,
  onAddComment,
}: PRPanelProps) {
  const [activeTab, setActiveTab] = useState<'files' | 'reviews' | 'checks' | 'conversation'>('files');
  const [commentText, setCommentText] = useState('');

  const totalAdditions = useMemo(
    () => pr.files.reduce((sum, f) => sum + f.additions, 0),
    [pr.files]
  );
  const totalDeletions = useMemo(
    () => pr.files.reduce((sum, f) => sum + f.deletions, 0),
    [pr.files]
  );

  const handleAddComment = useCallback(() => {
    if (commentText.trim() && onAddComment) {
      onAddComment(commentText.trim());
      setCommentText('');
    }
  }, [commentText, onAddComment]);

  return (
    <div className="flex flex-col h-full border border-border/30 rounded-lg bg-surface/30 overflow-hidden">
      {/* Header */}
      <div className="px-4 py-3 border-b border-border/30">
        <div className="flex items-center justify-between mb-1">
          <div className="flex items-center gap-2">
            <span className="text-[10px] font-mono text-muted/50">#{pr.number}</span>
            <span
              className={`text-[9px] px-1.5 py-0.5 rounded-full border font-medium ${
                pr.state === 'open'
                  ? 'bg-green-500/10 text-green-400 border-green-500/30'
                  : pr.state === 'merged'
                    ? 'bg-purple-500/10 text-purple-400 border-purple-500/30'
                    : 'bg-red-500/10 text-red-400 border-red-500/30'
              }`}
            >
              {pr.state}
            </span>
          </div>
          {onClose && (
            <button onClick={onClose} className="text-muted/50 hover:text-muted p-0.5">
              <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
              </svg>
            </button>
          )}
        </div>
        <h3 className="text-sm font-semibold text-foreground">{pr.title}</h3>
        <p className="text-[10px] text-muted/60 mt-0.5">
          {pr.author} wants to merge {pr.sourceBranch} into {pr.targetBranch}
        </p>
        <div className="flex items-center gap-2 mt-1">
          <span className="text-[9px] text-green-400 font-mono">
            +{totalAdditions}
          </span>
          <span className="text-[9px] text-red-400 font-mono">
            -{totalDeletions}
          </span>
          <span className="text-[9px] text-muted/50">{pr.files.length} files</span>
        </div>
      </div>

      {/* Tabs */}
      <div className="flex border-b border-border/30 bg-background/20">
        {(['files', 'reviews', 'checks', 'conversation'] as const).map((tab) => (
          <button
            key={tab}
            onClick={() => setActiveTab(tab)}
            className={`text-[9px] px-3 py-1.5 border-b-2 transition-colors capitalize ${
              activeTab === tab
                ? 'border-primary text-primary'
                : 'border-transparent text-muted/50 hover:text-muted'
            }`}
          >
            {tab}
            {tab === 'reviews' && pr.reviews.length > 0 && (
              <span className="ml-1 text-[8px] text-muted/50">({pr.reviews.length})</span>
            )}
            {tab === 'checks' && pr.checks.length > 0 && (
              <span className="ml-1 text-[8px] text-muted/50">({pr.checks.length})</span>
            )}
          </button>
        ))}
      </div>

      {/* Content area */}
      <div className="flex-1 overflow-y-auto p-3 space-y-2">
        {/* Files tab */}
        {activeTab === 'files' && (
          <div className="space-y-0.5">
            {pr.files.map((file) => (
              <div
                key={file.path}
                className="flex items-center gap-2 px-2 py-1 rounded hover:bg-accent/5 transition-colors"
              >
                <span className={`text-[9px] w-12 shrink-0 ${
                  file.status === 'added' ? 'text-green-400' :
                  file.status === 'removed' ? 'text-red-400' :
                  file.status === 'renamed' ? 'text-blue-400' :
                  'text-amber-400'
                }`}>
                  {file.status}
                </span>
                <span className="text-[10px] text-foreground/80 truncate flex-1" title={file.path}>
                  {file.path}
                </span>
                <span className="text-[9px] text-green-400 font-mono">+{file.additions}</span>
                <span className="text-[9px] text-red-400 font-mono">-{file.deletions}</span>
              </div>
            ))}
          </div>
        )}

        {/* Reviews tab */}
        {activeTab === 'reviews' && (
          <div className="space-y-2">
            {pr.reviews.length === 0 ? (
              <p className="text-[10px] text-muted/50 text-center py-4">No reviews yet</p>
            ) : (
              pr.reviews.map((review) => (
                <div key={review.id} className="p-2 rounded border border-border/20 bg-background/30">
                  <div className="flex items-center justify-between mb-1">
                    <span className="text-[9px] font-medium text-foreground/80">{review.author}</span>
                    <span
                      className={`text-[8px] px-1.5 py-0.5 rounded-full border ${
                        review.state === 'approved'
                          ? 'bg-green-500/10 text-green-400 border-green-500/20'
                          : review.state === 'changes_requested'
                            ? 'bg-red-500/10 text-red-400 border-red-500/20'
                            : 'bg-gray-500/10 text-gray-400 border-gray-500/20'
                      }`}
                    >
                      {review.state.replace('_', ' ')}
                    </span>
                  </div>
                  <p className="text-[9px] text-muted/70 whitespace-pre-wrap">{review.body}</p>
                </div>
              ))
            )}
          </div>
        )}

        {/* Checks tab */}
        {activeTab === 'checks' && (
          <div className="space-y-1">
            {pr.checks.length === 0 ? (
              <p className="text-[10px] text-muted/50 text-center py-4">No checks run</p>
            ) : (
              pr.checks.map((check, i) => (
                <div
                  key={`${check.name}-${i}`}
                  className="flex items-center gap-2 px-2 py-1.5 rounded hover:bg-accent/5 transition-colors"
                >
                  <span className={`inline-block h-2 w-2 rounded-full ${
                    check.status === 'passing' ? 'bg-green-500' :
                    check.status === 'failing' ? 'bg-red-500' : 'bg-yellow-500 animate-pulse'
                  }`} />
                  <span className="text-[10px] text-foreground/80 flex-1">{check.name}</span>
                  <span className={`text-[8px] ${
                    check.status === 'passing' ? 'text-green-400' :
                    check.status === 'failing' ? 'text-red-400' : 'text-yellow-400'
                  }`}>
                    {check.status}
                  </span>
                </div>
              ))
            )}
          </div>
        )}

        {/* Conversation tab */}
        {activeTab === 'conversation' && (
          <div className="flex flex-col gap-2">
            <p className="text-[10px] text-muted/60">{pr.description || 'No description provided.'}</p>
            {onAddComment && (
              <div className="flex items-start gap-1.5 mt-2">
                <textarea
                  value={commentText}
                  onChange={(e) => setCommentText(e.target.value)}
                  placeholder="Leave a comment..."
                  className="flex-1 text-[10px] bg-background border border-border rounded px-2 py-1.5 text-foreground outline-none min-h-[48px] resize-vertical"
                />
                <button
                  onClick={handleAddComment}
                  disabled={!commentText.trim()}
                  className="text-[9px] px-2 py-1 rounded bg-primary/80 text-white hover:bg-primary disabled:opacity-30 transition-colors"
                >
                  Send
                </button>
              </div>
            )}
          </div>
        )}
      </div>

      {/* Action bar */}
      {pr.state === 'open' && (
        <div className="flex items-center gap-1.5 px-3 py-2 border-t border-border/30 bg-background/20 justify-end">
          {onClose && (
            <button
              onClick={onClose}
              className="text-[9px] px-2 py-1 rounded border border-border/40 text-muted/60 hover:text-muted transition-colors"
            >
              Close PR
            </button>
          )}
          {onRequestChanges && (
            <button
              onClick={onRequestChanges}
              className="text-[9px] px-2 py-1 rounded border border-red-500/30 text-red-400 hover:bg-red-500/10 transition-colors"
            >
              Request Changes
            </button>
          )}
          {onApprove && (
            <button
              onClick={onApprove}
              className="text-[9px] px-2 py-1 rounded bg-green-500/80 text-white hover:bg-green-500 transition-colors"
            >
              Approve
            </button>
          )}
          {onMerge && (
            <button
              onClick={onMerge}
              className="text-[9px] px-3 py-1 rounded bg-primary/80 text-white hover:bg-primary transition-colors"
            >
              Merge
            </button>
          )}
        </div>
      )}
    </div>
  );
}

export default PRPanel;
