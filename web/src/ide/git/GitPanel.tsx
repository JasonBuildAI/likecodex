'use client';

/**
 * GitPanel — Version control panel with changes list, diff preview, commit area.
 *
 * Features:
 * - Staged/unstaged changes list
 * - Stage/unstage/discard individual files
 * - Diff preview with Monaco DiffEditor
 * - Commit message input + AI generation button
 * - Branch switcher
 * - Commit history timeline
 */

import { useState, useEffect, useCallback } from 'react';
import { DiffViewer } from '@/components/DiffViewer';
import { useGitStore } from './gitStore';

const CHANGE_ICONS: Record<string, string> = {
  modified: 'M',
  added: 'A',
  deleted: 'D',
  untracked: 'U',
  renamed: 'R',
  'both-added': '!',
};

const CHANGE_COLORS: Record<string, string> = {
  modified: 'text-yellow-400',
  added: 'text-green-400',
  deleted: 'text-red-400',
  untracked: 'text-blue-400',
  renamed: 'text-purple-400',
  'both-added': 'text-orange-400',
};

export function GitPanel() {
  const {
    changes,
    currentBranch,
    isRepo,
    commits,
    branches,
    selectedDiff,
    selectedPath,
    isLoading,
    error,
    searchQuery,
    searchResults,
    isSearching,
    refreshStatus,
    refreshLog,
    refreshBranches,
    selectFile,
    stageFile,
    unstageFile,
    stageAll,
    commit,
    discardChanges,
    checkoutBranch,
    search,
    pull,
    push: gitPushAction,
    fetch: gitFetchAction,
    stashPush,
    stashPop,
    loadHunks,
    stageHunk: stageHunkAction,
    hunks,
    selectedHunk,
  } = useGitStore();

  const [commitMessage, setCommitMessage] = useState('');
  const [view, setView] = useState<'changes' | 'history' | 'branches'>('changes');
  const [newBranchName, setNewBranchName] = useState('');
  const [showNewBranch, setShowNewBranch] = useState(false);
  const [filterText, setFilterText] = useState('');
  const [expandedChanges, setExpandedChanges] = useState<Set<string>>(new Set());
  const [actionFeedback, setActionFeedback] = useState<string | null>(null);
  const [confirmDiscard, setConfirmDiscard] = useState<string | null>(null);

  // Auto-refresh on mount
  useEffect(() => {
    refreshStatus();
    refreshBranches();
  }, [refreshStatus, refreshBranches]);

  // Auto-refresh every 5s when viewing changes
  useEffect(() => {
    if (view !== 'changes') return;
    const timer = setInterval(() => refreshStatus(), 5000);
    return () => clearInterval(timer);
  }, [view, refreshStatus]);

  const allChanges = changes.filter((c) => c.staged);
  const allUnstaged = changes.filter((c) => !c.staged);

  const filterFn = (c: { path: string }) =>
    !filterText || c.path.toLowerCase().includes(filterText.toLowerCase());

  const stagedChanges = allChanges.filter(filterFn);
  const unstagedChanges = allUnstaged.filter(filterFn);

  const toggleExpand = (path: string) => {
    setExpandedChanges((prev) => {
      const next = new Set(prev);
      if (next.has(path)) next.delete(path);
      else next.add(path);
      return next;
    });
  };

  const handleSelectFile = (path: string, staged: boolean) => {
    selectFile(path, staged);
    loadHunks(path, staged);
    toggleExpand(path);
  };

  const handleCommit = useCallback(async () => {
    if (!commitMessage.trim()) return;
    const success = await commit(commitMessage);
    if (success) {
      setCommitMessage('');
    }
  }, [commitMessage, commit]);

  const handleStageAllUnstaged = useCallback(async () => {
    await stageAll();
  }, [stageAll]);

  const handleQuickAction = useCallback(async (action: string) => {
    let result: { success: boolean; output?: string; error?: string } = { success: false };
    switch (action) {
      case 'pull': result = await pull(); break;
      case 'push': result = await gitPushAction(); break;
      case 'fetch': result = await gitFetchAction(); break;
      case 'stash': result = await stashPush('Auto-stash from dashboard'); break;
      case 'stash-pop': result = await stashPop(); break;
    }
    setActionFeedback(result.success ? `${action} 成功` : `${action} 失败: ${result.error || ''}`);
    setTimeout(() => setActionFeedback(null), 3000);
  }, [pull, gitPushAction, gitFetchAction, stashPush, stashPop]);

  // Discard with confirmation
  const handleDiscard = useCallback(async (path: string) => {
    await discardChanges(path);
    setConfirmDiscard(null);
    setActionFeedback(`已丢弃 ${path} 的变更`);
    setTimeout(() => setActionFeedback(null), 3000);
  }, [discardChanges]);

  if (!isRepo) {
    return (
      <div className="p-4 text-center text-sm text-gray-500">
        <p>当前目录不是 Git 仓库</p>
        <p className="text-xs mt-2">请在项目根目录初始化 Git 仓库</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-gray-700 shrink-0">
        <div className="flex items-center gap-2">
          <span className="text-xs font-semibold text-white">Git</span>
          <span className="text-[10px] text-blue-400 bg-blue-900/30 px-1.5 py-0.5 rounded flex items-center gap-1">
            <span className={`h-1.5 w-1.5 rounded-full ${currentBranch ? 'bg-green-400' : 'bg-red-400'}`} />
            {currentBranch || 'unknown'}
          </span>
        </div>
        <div className="flex gap-0.5">
          {/* Quick action buttons */}
          <button
            onClick={() => handleQuickAction('fetch')}
            className="px-1.5 py-0.5 text-[10px] text-gray-400 hover:text-white hover:bg-gray-700 rounded transition-colors"
            title="获取远程更新 (Fetch)"
          >
            ↓ Fetch
          </button>
          <button
            onClick={() => handleQuickAction('pull')}
            className="px-1.5 py-0.5 text-[10px] text-gray-400 hover:text-white hover:bg-gray-700 rounded transition-colors"
            title="拉取远程更新 (Pull)"
          >
            ↩ Pull
          </button>
          <button
            onClick={() => handleQuickAction('push')}
            className="px-1.5 py-0.5 text-[10px] text-gray-400 hover:text-white hover:bg-gray-700 rounded transition-colors"
            title="推送提交 (Push)"
          >
            ↪ Push
          </button>
          <button
            onClick={() => handleQuickAction('stash')}
            className="px-1.5 py-0.5 text-[10px] text-gray-400 hover:text-white hover:bg-gray-700 rounded transition-colors"
            title="暂存变更 (Stash)"
          >
            ⊞ Stash
          </button>
          <div className="w-px h-3 bg-gray-600 mx-0.5 self-center" />
          {(['changes', 'history', 'branches'] as const).map((v) => (
            <button
              key={v}
              onClick={() => {
                setView(v);
                if (v === 'history') refreshLog();
                if (v === 'branches') refreshBranches();
              }}
              className={`px-2 py-0.5 text-[10px] rounded transition-colors ${
                view === v ? 'bg-blue-600 text-white' : 'text-gray-400 hover:bg-gray-700'
              }`}
            >
              {v === 'changes' ? '变更' : v === 'history' ? '历史' : '分支'}
            </button>
          ))}
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="px-3 py-1 text-[10px] text-red-400 bg-red-900/20 border-b border-red-800/30">
          {error}
        </div>
      )}

      {/* Action feedback */}
      {actionFeedback && (
        <div className="px-3 py-1 text-[10px] text-green-400 bg-green-900/20 border-b border-green-800/30 animate-pulse">
          {actionFeedback}
        </div>
      )}

      {/* Discard confirmation dialog */}
      {confirmDiscard && (
        <div className="px-3 py-2 bg-red-900/20 border-b border-red-800/30">
          <div className="text-[10px] text-red-300 mb-1">
            确定要丢弃 {confirmDiscard} 的变更吗？此操作不可撤销。
          </div>
          <div className="flex gap-2">
            <button
              onClick={() => handleDiscard(confirmDiscard)}
              className="px-2 py-0.5 bg-red-600 text-white text-[10px] rounded hover:bg-red-700"
            >
              确认丢弃
            </button>
            <button
              onClick={() => setConfirmDiscard(null)}
              className="px-2 py-0.5 bg-gray-700 text-gray-300 text-[10px] rounded hover:bg-gray-600"
            >
              取消
            </button>
          </div>
        </div>
      )}

      {/* Content */}
      {view === 'changes' && (
        <>
          {/* Changes list */}
          <div className="flex-1 overflow-y-auto min-h-0">
            {/* Search / filter bar */}
            <div className="px-2 py-1 border-b border-gray-700">
              <input
                type="text"
                value={filterText}
                onChange={(e) => setFilterText(e.target.value)}
                placeholder="过滤文件..."
                className="w-full bg-gray-800 text-gray-200 text-[10px] border border-gray-700 rounded px-2 py-0.5 focus:outline-none focus:border-blue-500 placeholder-gray-600"
              />
            </div>

            {/* Staged changes */}
            {stagedChanges.length > 0 && (
              <div className="border-b border-gray-700">
                <div className="flex items-center justify-between px-3 py-1 bg-gray-800/50">
                  <span className="text-[10px] text-gray-400 font-medium uppercase tracking-wider">
                    暂存 ({stagedChanges.length})
                  </span>
                  <button
                    onClick={() => stagedChanges.forEach((c) => unstageFile(c.path))}
                    className="text-[10px] text-gray-500 hover:text-white"
                  >
                    全部取消暂存
                  </button>
                </div>
                {stagedChanges.map((c) => (
                  <ChangeItem
                    key={c.path}
                    change={c}
                    selected={selectedPath === c.path}
                    onClick={() => handleSelectFile(c.path, true)}
                    actionIcon="−"
                    actionTitle="取消暂存"
                    onAction={() => unstageFile(c.path)}
                    isExpanded={expandedChanges.has(c.path)}
                  />
                ))}
              </div>
            )}

            {/* Unstaged changes */}
            <div>
              <div className="flex items-center justify-between px-3 py-1 bg-gray-800/50">
                <span className="text-[10px] text-gray-400 font-medium uppercase tracking-wider">
                  变更 ({unstagedChanges.length})
                </span>
                {unstagedChanges.length > 0 && (
                  <button
                    onClick={handleStageAllUnstaged}
                    className="text-[10px] text-gray-500 hover:text-white"
                  >
                    全部暂存
                  </button>
                )}
              </div>
              {unstagedChanges.length === 0 && stagedChanges.length === 0 && (
                <div className="px-3 py-6 text-center text-xs text-gray-500">
                  {filterText ? '没有匹配的变更' : '没有未提交的变更'}
                </div>
              )}
              {unstagedChanges.map((c) => (
                <ChangeItem
                  key={c.path}
                  change={c}
                  selected={selectedPath === c.path}
                  onClick={() => handleSelectFile(c.path, false)}
                  actionIcon="+"
                  actionTitle="暂存"
                  onAction={() => stageFile(c.path)}
                  onDiscard={
                    c.changeType !== 'untracked'
                      ? () => setConfirmDiscard(c.path)
                      : undefined
                  }
                  isExpanded={expandedChanges.has(c.path)}
                  hunks={selectedPath === c.path ? hunks?.hunks : undefined}
                  onStageHunk={(idx) => stageHunkAction(c.path, idx)}
                />
              ))}
            </div>
          </div>

          {/* Diff preview */}
          {selectedDiff && (
            <div className="h-[200px] border-t border-gray-700 shrink-0">
              <DiffViewer
                oldText={selectedDiff.originalContent}
                newText={selectedDiff.modifiedContent}
                language={detectLang(selectedDiff.path)}
                title={selectedDiff.path}
              />
            </div>
          )}

          {/* Commit area */}
          <div className="border-t border-gray-700 p-2 shrink-0">
            <textarea
              value={commitMessage}
              onChange={(e) => setCommitMessage(e.target.value)}
              onKeyDown={(e) => {
                if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
                  e.preventDefault();
                  handleCommit();
                }
              }}
              placeholder="提交信息 (Ctrl+Enter 提交)"
              className="w-full bg-gray-800 text-gray-200 text-xs border border-gray-700 rounded px-2 py-1.5 resize-none focus:outline-none focus:border-blue-500"
              rows={2}
              disabled={stagedChanges.length === 0}
            />
            <button
              onClick={handleCommit}
              disabled={!commitMessage.trim() || stagedChanges.length === 0}
              className="w-full mt-1.5 px-3 py-1.5 bg-green-600 text-white text-xs rounded hover:bg-green-700 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
            >
              提交 ({stagedChanges.length} 个文件已暂存)
            </button>
          </div>
        </>
      )}

      {/* History view */}
      {view === 'history' && (
        <div className="flex-1 overflow-y-auto min-h-0">
          {commits.length === 0 ? (
            <div className="px-3 py-6 text-center text-xs text-gray-500">
              加载中...
            </div>
          ) : (
            commits.map((c) => (
              <div
                key={c.hash}
                className="px-3 py-2 border-b border-gray-800 hover:bg-gray-800/50 cursor-pointer"
              >
                <div className="flex items-center gap-2">
                  <span className="text-[10px] text-gray-500 font-mono">{c.shortHash}</span>
                  <span className="text-xs text-gray-200 flex-1 truncate">{c.message}</span>
                </div>
                <div className="text-[10px] text-gray-500 mt-0.5">
                  {c.author} · {c.date}
                </div>
              </div>
            ))
          )}
        </div>
      )}

      {/* Branches view */}
      {view === 'branches' && (
        <div className="flex-1 overflow-y-auto min-h-0">
          {showNewBranch && (
            <div className="px-3 py-2 border-b border-gray-700 bg-gray-800/50">
              <input
                type="text"
                value={newBranchName}
                onChange={(e) => setNewBranchName(e.target.value)}
                placeholder="新分支名称"
                className="w-full bg-gray-800 text-gray-200 text-xs border border-gray-700 rounded px-2 py-1 focus:outline-none focus:border-blue-500"
                autoFocus
              />
              <div className="flex gap-2 mt-1.5">
                <button
                  onClick={async () => {
                    if (newBranchName.trim()) {
                      await useGitStore.getState().createBranch(newBranchName.trim());
                      setNewBranchName('');
                      setShowNewBranch(false);
                    }
                  }}
                  className="flex-1 px-2 py-1 bg-blue-600 text-white text-xs rounded hover:bg-blue-700"
                >
                  创建
                </button>
                <button
                  onClick={() => setShowNewBranch(false)}
                  className="px-2 py-1 bg-gray-700 text-gray-300 text-xs rounded hover:bg-gray-600"
                >
                  取消
                </button>
              </div>
            </div>
          )}

          {!showNewBranch && (
            <button
              onClick={() => setShowNewBranch(true)}
              className="w-full px-3 py-2 text-xs text-blue-400 hover:bg-gray-800/50 border-b border-gray-800"
            >
              + 新建分支
            </button>
          )}

          {branches.map((b) => (
            <div
              key={b.name}
              className={`px-3 py-2 border-b border-gray-800 hover:bg-gray-800/50 ${
                b.current ? 'bg-blue-900/20' : ''
              }`}
            >
              <div className="flex items-center gap-2">
                {b.current && <span className="text-green-400 text-xs">●</span>}
                <span className={`text-xs flex-1 truncate ${b.current ? 'text-blue-300' : 'text-gray-300'}`}>
                  {b.name}
                </span>
                {!b.current && !b.remote && (
                  <button
                    onClick={() => checkoutBranch(b.name)}
                    className="text-[10px] text-gray-500 hover:text-white"
                  >
                    切换
                  </button>
                )}
              </div>
              {b.lastCommit && (
                <div className="text-[10px] text-gray-600 truncate mt-0.5">{b.lastCommit}</div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Helper components ──────────────────────────────────────────────

function ChangeItem({
  change,
  selected,
  onClick,
  actionIcon,
  actionTitle,
  onAction,
  onDiscard,
  isExpanded,
  hunks,
  onStageHunk,
}: {
  change: { path: string; changeType: string; staged: boolean };
  selected: boolean;
  onClick: () => void;
  actionIcon: string;
  actionTitle: string;
  onAction: () => void;
  onDiscard?: () => void;
  isExpanded?: boolean;
  hunks?: { header: string; content: string }[] | null;
  onStageHunk?: (index: number) => void;
}) {
  const changeTypeLabel: Record<string, string> = {
    modified: '修改', added: '新增', deleted: '删除',
    untracked: '未跟踪', renamed: '重命名', 'both-added': '冲突',
  };

  const [hunkLoading, setHunkLoading] = useState<number | null>(null);

  const handleStageHunk = useCallback(async (index: number) => {
    if (!onStageHunk) return;
    setHunkLoading(index);
    await onStageHunk(index);
    setHunkLoading(null);
  }, [onStageHunk]);

  return (
    <>
      <div
        onClick={onClick}
        className={`flex items-center px-3 py-1 cursor-pointer border-b border-gray-800/50 ${
          selected ? 'bg-blue-900/30' : 'hover:bg-gray-800/50'
        } ${isExpanded ? 'border-l-2 border-l-blue-500' : ''}`}
      >
        <span
          className={`text-[10px] w-4 font-mono ${
            CHANGE_COLORS[change.changeType] || 'text-gray-400'
          }`}
        >
          {CHANGE_ICONS[change.changeType] || '?'}
        </span>
        <span className="text-xs text-gray-300 flex-1 truncate ml-1" title={change.path}>
          {change.path.split('/').pop()}
        </span>
        <span className="text-[10px] text-gray-600 ml-1 mr-2 hidden sm:inline">
          {change.path.split('/').slice(0, -1).join('/')}
        </span>
        <span className="text-[9px] text-gray-500 mr-1 hidden md:inline">
          {changeTypeLabel[change.changeType] || change.changeType}
        </span>
        <div className="flex items-center gap-1">
          {onDiscard && (
            <button
              onClick={(e) => {
                e.stopPropagation();
                onDiscard();
              }}
              className="text-[10px] text-red-500 hover:text-red-400 px-1"
              title="丢弃变更"
            >
              ✕
            </button>
          )}
          <button
            onClick={(e) => {
              e.stopPropagation();
              onAction();
            }}
            className={`text-xs px-1 ${
              actionIcon === '+'
                ? 'text-green-400 hover:text-green-300'
                : 'text-yellow-400 hover:text-yellow-300'
            }`}
            title={actionTitle}
          >
            {actionIcon === '+' ? '▸ 暂存' : '◂ 取消'}
          </button>
        </div>
      </div>

      {/* Hunks display when expanded */}
      {isExpanded && hunks && hunks.length > 0 && (
        <div className="bg-gray-900/50 border-b border-gray-800">
          <div className="text-[9px] text-gray-500 px-4 py-1 uppercase tracking-wider">
            逐块暂存 ({hunks.length} 个区块)
          </div>
          {hunks.map((hunk, i) => (
            <div key={i} className="px-4 py-1 border-t border-gray-800/50 flex items-start gap-2">
              <div className="flex-1 min-w-0">
                <div className="text-[9px] text-gray-500 font-mono truncate">
                  {hunk.header}
                </div>
                <pre className="text-[10px] text-gray-400 font-mono mt-0.5 overflow-x-auto max-h-[80px]">
                  {hunk.content.split('\n').slice(0, 8).map((l, j) => (
                    <div key={j} className={
                      l.startsWith('+') ? 'text-green-400' :
                      l.startsWith('-') ? 'text-red-400' :
                      l.startsWith('@@') ? 'text-yellow-400' :
                      'text-gray-500'
                    }>{l}</div>
                  ))}
                  {hunk.content.split('\n').length > 8 && (
                    <div className="text-gray-600">... {hunk.content.split('\n').length - 8} 行更多</div>
                  )}
                </pre>
              </div>
              {onStageHunk && !change.staged && (
                <button
                  onClick={() => handleStageHunk(i)}
                  disabled={hunkLoading === i}
                  className="shrink-0 px-1.5 py-0.5 bg-green-700/50 text-green-300 text-[9px] rounded hover:bg-green-700 disabled:opacity-40 mt-1"
                >
                  {hunkLoading === i ? '...' : '暂存此块'}
                </button>
              )}
            </div>
          ))}
        </div>
      )}
    </>
  );
}

function detectLang(path: string): string {
  const ext = path.split('.').pop()?.toLowerCase();
  const map: Record<string, string> = {
    ts: 'typescript', tsx: 'typescript',
    js: 'javascript', jsx: 'javascript',
    py: 'python', rs: 'rust', go: 'go',
    json: 'json', css: 'css', html: 'html',
    md: 'markdown', yaml: 'yaml', yml: 'yaml',
  };
  return map[ext || ''] || 'plaintext';
}
