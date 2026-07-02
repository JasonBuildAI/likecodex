'use client';

import { useState, useCallback } from 'react';

// ── Types ──────────────────────────────────────────────────────────────

export interface ReviewComment {
  id: string;
  file: string;
  line: number;
  content: string;
  author: string;
  resolved: boolean;
  createdAt: string;
}

export interface ReviewFile {
  path: string;
  status: 'added' | 'modified' | 'removed';
  diff: string;
  comments: ReviewComment[];
}

interface CodeReviewPanelProps {
  files: ReviewFile[];
  onAddComment: (file: string, line: number, content: string) => void;
  onResolveComment: (commentId: string) => void;
  onSubmitReview: (approved: boolean, summary: string) => void;
}

// ── Main Component ─────────────────────────────────────────────────────

export function CodeReviewPanel({
  files,
  onAddComment,
  onResolveComment,
  onSubmitReview,
}: CodeReviewPanelProps) {
  const [selectedFile, setSelectedFile] = useState<string>(files[0]?.path || '');
  const [expandedFiles, setExpandedFiles] = useState<Set<string>>(new Set(files.map((f) => f.path)));
  const [newComment, setNewComment] = useState<{ file: string; line: number; text: string } | null>(null);
  const [reviewSummary, setReviewSummary] = useState('');
  const [reviewDecision, setReviewDecision] = useState<'approve' | 'request_changes' | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const currentFile = files.find((f) => f.path === selectedFile);

  // ── Handlers ─────────────────────────────────────────────────────────

  const toggleFile = useCallback((path: string) => {
    setExpandedFiles((prev) => {
      const next = new Set(prev);
      if (next.has(path)) next.delete(path);
      else next.add(path);
      return next;
    });
  }, []);

  const handleAddComment = useCallback(
    (file: string, line: number) => {
      setNewComment({ file, line, text: '' });
    },
    []
  );

  const handleSubmitComment = useCallback(() => {
    if (newComment && newComment.text.trim()) {
      onAddComment(newComment.file, newComment.line, newComment.text.trim());
      setNewComment(null);
    }
  }, [newComment, onAddComment]);

  const handleSubmitReview = useCallback(async () => {
    if (!reviewDecision) return;
    setSubmitting(true);
    try {
      await onSubmitReview(reviewDecision === 'approve', reviewSummary);
    } finally {
      setSubmitting(false);
    }
  }, [reviewDecision, reviewSummary, onSubmitReview]);

  const totalComments = files.reduce((sum, f) => sum + f.comments.length, 0);
  const unresolvedComments = files.reduce(
    (sum, f) => sum + f.comments.filter((c) => !c.resolved).length,
    0
  );

  return (
    <div className="flex flex-col h-full border border-border/30 rounded-lg bg-surface/30 overflow-hidden">
      {/* Header */}
      <div className="px-4 py-3 border-b border-border/30">
        <div className="flex items-center justify-between">
          <span className="text-[10px] font-medium text-muted uppercase tracking-wider">
            Code Review
          </span>
          <div className="flex items-center gap-2 text-[9px]">
            <span className="text-muted/50">{files.length} files</span>
            <span className="text-muted/50">·</span>
            <span className={unresolvedComments > 0 ? 'text-yellow-400' : 'text-green-400'}>
              {unresolvedComments} unresolved
            </span>
          </div>
        </div>
      </div>

      {/* Split: file list + diff */}
      <div className="flex flex-1 overflow-hidden">
        {/* File sidebar */}
        <div className="w-52 border-r border-border/20 overflow-y-auto shrink-0">
          {files.map((file) => (
            <div key={file.path}>
              <button
                onClick={() => {
                  setSelectedFile(file.path);
                  toggleFile(file.path);
                }}
                className={`w-full text-left px-3 py-1.5 text-[10px] hover:bg-accent/5 transition-colors ${
                  selectedFile === file.path ? 'bg-primary/5 text-primary' : 'text-foreground/80'
                }`}
              >
                <div className="flex items-center gap-1.5">
                  <span className={`text-[9px] ${
                    file.status === 'added' ? 'text-green-400' :
                    file.status === 'removed' ? 'text-red-400' : 'text-amber-400'
                  }`}>
                    {file.status === 'added' ? '+' : file.status === 'removed' ? '-' : '~'}
                  </span>
                  <span className="truncate flex-1" title={file.path}>
                    {file.path.split('/').pop()}
                  </span>
                  {file.comments.length > 0 && (
                    <span className="text-[8px] text-yellow-400/70">
                      ({file.comments.length})
                    </span>
                  )}
                </div>
              </button>
            </div>
          ))}
        </div>

        {/* Diff / comment area */}
        <div className="flex-1 flex flex-col overflow-hidden">
          {/* File header */}
          <div className="px-3 py-1.5 border-b border-border/20 bg-background/20">
            <span className="text-[9px] text-muted/50 font-mono">{selectedFile}</span>
          </div>

          {/* Diff content */}
          <div className="flex-1 overflow-y-auto p-2">
            {currentFile ? (
              <div className="space-y-1">
                <pre className="text-[9px] font-mono text-muted/80 whitespace-pre-wrap leading-relaxed">
                  {currentFile.diff.split('\n').map((line, i) => {
                    const lineNum = i + 1;
                    const isAddition = line.startsWith('+');
                    const isDeletion = line.startsWith('-');
                    const isHunk = line.startsWith('@@');

                    return (
                      <div
                        key={i}
                        className={`flex group hover:bg-accent/5 ${
                          isAddition ? 'bg-green-500/10' :
                          isDeletion ? 'bg-red-500/10' :
                          isHunk ? 'bg-blue-500/10' : ''
                        }`}
                        onDoubleClick={() => handleAddComment(selectedFile, lineNum)}
                      >
                        <span className="text-[8px] text-muted/30 w-8 text-right shrink-0 select-none pr-2 border-r border-border/20">
                          {lineNum}
                        </span>
                        <span className="flex-1 px-2">{line}</span>
                        <button
                          onClick={() => handleAddComment(selectedFile, lineNum)}
                          className="opacity-0 group-hover:opacity-100 text-[8px] text-muted/30 hover:text-muted/60 px-1 transition-opacity shrink-0"
                          title="Add comment"
                        >
                          +
                        </button>
                      </div>
                    );
                  })}
                </pre>

                {/* New comment input */}
                {newComment && newComment.file === selectedFile && (
                  <div className="mt-2 p-2 rounded border border-primary/30 bg-primary/5">
                    <div className="text-[8px] text-muted/50 mb-1">
                      Comment on line {newComment.line}
                    </div>
                    <textarea
                      autoFocus
                      value={newComment.text}
                      onChange={(e) => setNewComment({ ...newComment, text: e.target.value })}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) handleSubmitComment();
                        if (e.key === 'Escape') setNewComment(null);
                      }}
                      placeholder="Write a comment..."
                      className="w-full text-[9px] bg-background border border-border rounded px-2 py-1 text-foreground outline-none min-h-[40px] resize-vertical"
                    />
                    <div className="flex items-center gap-1 mt-1 justify-end">
                      <button
                        onClick={() => setNewComment(null)}
                        className="text-[8px] px-1.5 py-0.5 rounded text-muted/60 hover:text-muted"
                      >
                        Cancel
                      </button>
                      <button
                        onClick={handleSubmitComment}
                        disabled={!newComment.text.trim()}
                        className="text-[8px] px-1.5 py-0.5 rounded bg-primary/80 text-white hover:bg-primary disabled:opacity-30"
                      >
                        Comment
                      </button>
                    </div>
                  </div>
                )}

                {/* Existing comments for this file */}
                {currentFile.comments.map((comment) => (
                  <div
                    key={comment.id}
                    className={`mt-1 p-2 rounded border ${
                      comment.resolved
                        ? 'border-green-500/20 bg-green-500/5 opacity-60'
                        : 'border-yellow-500/20 bg-yellow-500/5'
                    }`}
                  >
                    <div className="flex items-center justify-between mb-0.5">
                      <span className="text-[8px] font-medium text-foreground/70">
                        {comment.author} — line {comment.line}
                      </span>
                      {!comment.resolved && (
                        <button
                          onClick={() => onResolveComment(comment.id)}
                          className="text-[8px] text-green-400 hover:text-green-300"
                        >
                          Resolve
                        </button>
                      )}
                    </div>
                    <p className="text-[9px] text-muted/70">{comment.content}</p>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-center py-8 text-muted/50 text-[10px]">
                Select a file to review
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Review submission bar */}
      <div className="px-3 py-2 border-t border-border/30 bg-background/20">
        <div className="flex items-start gap-2">
          <textarea
            value={reviewSummary}
            onChange={(e) => setReviewSummary(e.target.value)}
            placeholder="Review summary (optional)..."
            className="flex-1 text-[9px] bg-background border border-border rounded px-2 py-1 text-foreground outline-none min-h-[32px] resize-vertical"
          />
          <div className="flex flex-col gap-1 shrink-0">
            <button
              onClick={() => setReviewDecision('request_changes')}
              className={`text-[9px] px-2 py-1 rounded border transition-colors ${
                reviewDecision === 'request_changes'
                  ? 'bg-red-500/20 text-red-400 border-red-500/30'
                  : 'border-border/40 text-muted/60 hover:text-muted'
              }`}
            >
              Request Changes
            </button>
            <button
              onClick={() => setReviewDecision('approve')}
              className={`text-[9px] px-2 py-1 rounded border transition-colors ${
                reviewDecision === 'approve'
                  ? 'bg-green-500/20 text-green-400 border-green-500/30'
                  : 'border-border/40 text-muted/60 hover:text-muted'
              }`}
            >
              Approve
            </button>
            <button
              onClick={handleSubmitReview}
              disabled={!reviewDecision || submitting}
              className="text-[9px] px-3 py-1 rounded bg-primary/80 text-white hover:bg-primary disabled:opacity-30 transition-colors"
            >
              {submitting ? 'Submitting...' : 'Submit Review'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default CodeReviewPanel;
