'use client';

/**
 * SearchPanel — Global file content search (Ctrl+Shift+F) with Composer change search.
 *
 * Supports:
 * - Git file content search (original)
 * - Composer pending changes search (Phase 3.12)
 */

import { useState, useCallback, useRef, useEffect, useMemo } from 'react';
import { useGitStore } from '@/ide/git/gitStore';
import { useComposerStore, type FileChange } from '@/ide/composer/composerStore';

type SearchTab = 'git' | 'composer';

export function SearchPanel() {
  const {
    searchResults,
    isSearching,
    searchQuery,
    search,
  } = useGitStore();

  const {
    fileChanges: composerChanges,
  } = useComposerStore();

  const [input, setInput] = useState('');
  const [activeTab, setActiveTab] = useState<SearchTab>('git');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const handleSearch = useCallback((value: string) => {
    setInput(value);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      if (activeTab === 'git') {
        search(value);
      }
    }, 300);
  }, [search, activeTab]);

  useEffect(() => {
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, []);

  // Switch tab — auto-trigger search if switching to git
  const switchTab = useCallback((tab: SearchTab) => {
    setActiveTab(tab);
    if (tab === 'git' && input) {
      search(input);
    }
  }, [input, search]);

  // ===== Composer change search =====
  const composerSearchResults = useMemo(() => {
    if (activeTab !== 'composer' || !input.trim()) return [];
    const q = input.toLowerCase();

    const changes = Array.from(composerChanges.values());

    // Filter by status
    const filtered = statusFilter === 'all'
      ? changes
      : changes.filter((c) => {
          if (statusFilter === 'pending') return c.accepted === null;
          if (statusFilter === 'accepted') return c.accepted === true;
          if (statusFilter === 'rejected') return c.accepted === false;
          return true;
        });

    // Search in file path and content
    const results: Array<{
      filePath: string;
      changeType: string;
      accepted: boolean | null;
      matches: Array<{ line: number; content: string; side: 'original' | 'modified' }>;
    }> = [];

    for (const change of filtered) {
      const fileMatches: Array<{ line: number; content: string; side: 'original' | 'modified' }> = [];

      // Check file path
      if (change.filePath.toLowerCase().includes(q)) {
        fileMatches.push({ line: 0, content: change.filePath, side: 'modified' });
      }

      // Search in original content
      if (change.originalContent) {
        change.originalContent.split('\n').forEach((line, idx) => {
          if (line.toLowerCase().includes(q)) {
            fileMatches.push({ line: idx + 1, content: line.trim(), side: 'original' });
          }
        });
      }

      // Search in modified content
      if (change.modifiedContent) {
        change.modifiedContent.split('\n').forEach((line, idx) => {
          if (line.toLowerCase().includes(q)) {
            fileMatches.push({ line: idx + 1, content: line.trim(), side: 'modified' });
          }
        });
      }

      if (fileMatches.length > 0) {
        results.push({
          filePath: change.filePath,
          changeType: change.changeType,
          accepted: change.accepted,
          matches: fileMatches,
        });
      }
    }

    return results;
  }, [composerChanges, input, activeTab, statusFilter]);

  // ===== Git search results grouping =====
  const groupedResults: Record<string, typeof searchResults> = {};
  for (const r of searchResults) {
    if (!groupedResults[r.path]) groupedResults[r.path] = [];
    groupedResults[r.path].push(r);
  }

  const statusBadge = (accepted: boolean | null) => {
    if (accepted === null) return <span className="text-[10px] text-yellow-400">待审</span>;
    if (accepted === true) return <span className="text-[10px] text-green-400">已接受</span>;
    return <span className="text-[10px] text-red-400">已拒绝</span>;
  };

  return (
    <div className="flex flex-col h-full">
      {/* Tab bar */}
      <div className="flex border-b border-gray-700 shrink-0">
        <button
          onClick={() => switchTab('git')}
          className={`flex-1 text-xs py-1.5 px-2 transition-colors ${
            activeTab === 'git'
              ? 'text-blue-400 border-b-2 border-blue-400 bg-gray-800/50'
              : 'text-gray-500 hover:text-gray-300 hover:bg-gray-800/20'
          }`}
        >
          文件搜索
        </button>
        <button
          onClick={() => switchTab('composer')}
          className={`flex-1 text-xs py-1.5 px-2 transition-colors ${
            activeTab === 'composer'
              ? 'text-blue-400 border-b-2 border-blue-400 bg-gray-800/50'
              : 'text-gray-500 hover:text-gray-300 hover:bg-gray-800/20'
          }`}
        >
          Composer变更
        </button>
      </div>

      {/* Search input */}
      <div className="p-2 border-b border-gray-700 shrink-0">
        <input
          type="text"
          value={input}
          onChange={(e) => handleSearch(e.target.value)}
          placeholder={activeTab === 'git' ? '搜索文件内容...' : '搜索待变更内容...'}
          className="w-full bg-gray-800 text-gray-200 text-xs border border-gray-700 rounded px-2 py-1.5 focus:outline-none focus:border-blue-500"
          autoFocus
        />
        <div className="flex items-center justify-between mt-1.5">
          <span className="text-[10px] text-gray-500">
            {activeTab === 'git'
              ? isSearching ? '搜索中...' : `${searchResults.length} 个结果`
              : `${composerSearchResults.length} 个结果`
            }
          </span>
          <div className="flex items-center gap-2">
            {activeTab === 'composer' && (
              <select
                value={statusFilter}
                onChange={(e) => setStatusFilter(e.target.value)}
                className="bg-gray-800 text-gray-400 text-[10px] border border-gray-700 rounded px-1 py-0.5"
              >
                <option value="all">全部状态</option>
                <option value="pending">待审</option>
                <option value="accepted">已接受</option>
                <option value="rejected">已拒绝</option>
              </select>
            )}
            {searchQuery && activeTab === 'git' && (
              <button
                onClick={() => {
                  setInput('');
                  search('');
                }}
                className="text-[10px] text-gray-500 hover:text-white"
              >
                清除
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Results */}
      <div className="flex-1 overflow-y-auto min-h-0">
        {/* Git search results */}
        {activeTab === 'git' && (
          <>
            {Object.keys(groupedResults).length === 0 && searchQuery && !isSearching && (
              <div className="px-3 py-6 text-center text-xs text-gray-500">
                未找到匹配结果
              </div>
            )}
            {Object.entries(groupedResults).map(([path, matches]) => (
              <div key={path} className="border-b border-gray-800/50">
                <div className="px-3 py-1.5 bg-gray-800/30 flex items-center gap-1">
                  <span className="text-[10px] text-blue-400">📄</span>
                  <span className="text-xs text-gray-300 flex-1 truncate">{path}</span>
                  <span className="text-[10px] text-gray-500">{matches.length}</span>
                </div>
                {matches.map((m, i) => (
                  <div
                    key={i}
                    className="px-3 py-1 hover:bg-gray-800/50 cursor-pointer"
                    onClick={() => {
                      window.dispatchEvent(
                        new CustomEvent('likecodex:open-file', {
                          detail: { path: m.path, line: m.line },
                        })
                      );
                    }}
                  >
                    <span className="text-[10px] text-gray-600 mr-2">{m.line}</span>
                    <span className="text-xs text-gray-400 font-mono truncate">
                      {highlightMatch(m.content, searchQuery)}
                    </span>
                  </div>
                ))}
              </div>
            ))}
          </>
        )}

        {/* Composer change search results */}
        {activeTab === 'composer' && (
          <>
            {composerSearchResults.length === 0 && input.trim() && (
              <div className="px-3 py-6 text-center text-xs text-gray-500">
                未找到匹配变更
              </div>
            )}
            {composerSearchResults.length === 0 && !input.trim() && (
              <div className="px-3 py-6 text-center text-xs text-gray-500">
                输入搜索词查找 Composer 变更内容
              </div>
            )}
            {composerSearchResults.map((result, idx) => (
              <div key={idx} className="border-b border-gray-800/50">
                <div className="px-3 py-1.5 bg-gray-800/30 flex items-center gap-1">
                  <span className="text-[10px] text-blue-400">📄</span>
                  <span className="text-xs text-gray-300 flex-1 truncate">{result.filePath}</span>
                  <span className="text-[10px] text-gray-500 mr-1">{result.matches.length}</span>
                  {statusBadge(result.accepted)}
                </div>
                <div className="px-2 py-1 text-[10px] text-gray-500">
                  {result.changeType === 'create' ? '创建' : result.changeType === 'delete' ? '删除' : '修改'}
                </div>
                {result.matches.slice(0, 5).map((match, mi) => (
                  <div
                    key={mi}
                    className="px-3 py-1 hover:bg-gray-800/50 cursor-pointer"
                    onClick={() => {
                      window.dispatchEvent(
                        new CustomEvent('likecodex:open-file', {
                          detail: { path: result.filePath, line: match.line },
                        })
                      );
                    }}
                  >
                    <span className="text-[10px] text-gray-600 mr-2">{match.line}</span>
                    <span className="text-[10px] text-gray-500 mr-1">
                      [{match.side === 'original' ? '原' : '新'}]
                    </span>
                    <span className="text-xs text-gray-400 font-mono truncate">
                      {highlightMatch(match.content, input)}
                    </span>
                  </div>
                ))}
                {result.matches.length > 5 && (
                  <div className="px-3 py-1 text-[10px] text-gray-600">
                    +{result.matches.length - 5} 更多匹配
                  </div>
                )}
              </div>
            ))}
          </>
        )}
      </div>
    </div>
  );
}

function highlightMatch(text: string, query: string): React.ReactNode {
  if (!query) return text;
  const idx = text.toLowerCase().indexOf(query.toLowerCase());
  if (idx === -1) return text;
  return (
    <>
      {text.slice(0, idx)}
      <span className="bg-yellow-600/30 text-yellow-300">{text.slice(idx, idx + query.length)}</span>
      {text.slice(idx + query.length)}
    </>
  );
}
