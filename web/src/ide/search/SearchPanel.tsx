'use client';

/**
 * SearchPanel — Global file content search (Ctrl+Shift+F) with search history,
 * result preview, and replace functionality.
 *
 * Supports:
 * - Git file content search (original)
 * - Composer pending changes search (Phase 3.12)
 * - Search history management
 * - Result preview with context lines
 * - Find & Replace in workspace
 */

import { useState, useCallback, useRef, useEffect, useMemo } from 'react';
import { useGitStore } from '@/ide/git/gitStore';
import { useComposerStore, type FileChange } from '@/ide/composer/composerStore';

type SearchTab = 'git' | 'composer';

interface SearchHistoryEntry {
  query: string;
  timestamp: number;
  tab: SearchTab;
  resultCount: number;
}

interface ReplaceResult {
  path: string;
  success: boolean;
  replacements: number;
  error?: string;
}

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
  const [replaceInput, setReplaceInput] = useState('');
  const [activeTab, setActiveTab] = useState<SearchTab>('git');
  const [statusFilter, setStatusFilter] = useState<string>('all');
  const [showReplace, setShowReplace] = useState(false);
  const [showHistory, setShowHistory] = useState(false);
  const [searchHistory, setSearchHistory] = useState<SearchHistoryEntry[]>(() => {
    try {
      const saved = localStorage.getItem('likecodex_search_history');
      return saved ? JSON.parse(saved) : [];
    } catch {
      return [];
    }
  });
  const [replaceResults, setReplaceResults] = useState<ReplaceResult[]>([]);
  const [isReplacing, setIsReplacing] = useState(false);
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Save search history to localStorage
  useEffect(() => {
    localStorage.setItem('likecodex_search_history', JSON.stringify(searchHistory.slice(0, 50)));
  }, [searchHistory]);

  const addToHistory = useCallback((query: string, tab: SearchTab, resultCount: number) => {
    if (!query.trim()) return;
    setSearchHistory((prev) => {
      const filtered = prev.filter((e) => e.query !== query || e.tab !== tab);
      return [{ query, timestamp: Date.now(), tab, resultCount }, ...filtered].slice(0, 50);
    });
  }, []);

  const clearHistory = useCallback(() => {
    setSearchHistory([]);
    localStorage.removeItem('likecodex_search_history');
  }, []);

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

  // Auto-add to history when search completes
  useEffect(() => {
    if (searchQuery && !isSearching) {
      addToHistory(searchQuery, 'git', searchResults.length);
    }
  }, [searchQuery, isSearching, searchResults.length, addToHistory]);

  // Auto-add composer search to history
  const composerSearchResults = useMemo(() => {
    if (activeTab !== 'composer' || !input.trim()) return [];
    const q = input.toLowerCase();

    const changes = Array.from(composerChanges.values());

    const filtered = statusFilter === 'all'
      ? changes
      : changes.filter((c) => {
          if (statusFilter === 'pending') return c.accepted === null;
          if (statusFilter === 'accepted') return c.accepted === true;
          if (statusFilter === 'rejected') return c.accepted === false;
          return true;
        });

    const results: Array<{
      filePath: string;
      changeType: string;
      accepted: boolean | null;
      matches: Array<{ line: number; content: string; side: 'original' | 'modified' }>;
    }> = [];

    for (const change of filtered) {
      const fileMatches: Array<{ line: number; content: string; side: 'original' | 'modified' }> = [];

      if (change.filePath.toLowerCase().includes(q)) {
        fileMatches.push({ line: 0, content: change.filePath, side: 'modified' });
      }

      if (change.originalContent) {
        change.originalContent.split('\n').forEach((line, idx) => {
          if (line.toLowerCase().includes(q)) {
            fileMatches.push({ line: idx + 1, content: line.trim(), side: 'original' });
          }
        });
      }

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

  // ── Replace functionality ───────────────────────────────────────────
  const handleReplace = useCallback(async () => {
    if (!input.trim() || !replaceInput.trim() || isReplacing) return;
    setIsReplacing(true);
    setReplaceResults([]);

    try {
      const resp = await fetch('/api/ide/search/replace', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          query: input,
          replacement: replaceInput,
          paths: Object.keys(groupedResults),
        }),
      });

      if (resp.ok) {
        const data = await resp.json();
        setReplaceResults(data.results || []);
      } else {
        setReplaceResults([{ path: '', success: false, replacements: 0, error: `HTTP ${resp.status}` }]);
      }
    } catch (err) {
      setReplaceResults([{ path: '', success: false, replacements: 0, error: String(err) }]);
    } finally {
      setIsReplacing(false);
    }
  }, [input, replaceInput, isReplacing]);

  // Switch tab
  const switchTab = useCallback((tab: SearchTab) => {
    setActiveTab(tab);
    if (tab === 'git' && input) {
      search(input);
    }
  }, [input, search]);

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

  const hasResults = activeTab === 'git'
    ? Object.keys(groupedResults).length > 0
    : composerSearchResults.length > 0;

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
        <div className="relative">
          <input
            ref={inputRef}
            type="text"
            value={input}
            onChange={(e) => handleSearch(e.target.value)}
            onFocus={() => setShowHistory(true)}
            onBlur={() => setTimeout(() => setShowHistory(false), 200)}
            placeholder={activeTab === 'git' ? '搜索文件内容...' : '搜索待变更内容...'}
            className="w-full bg-gray-800 text-gray-200 text-xs border border-gray-700 rounded px-2 py-1.5 focus:outline-none focus:border-blue-500 pr-7"
            autoFocus
          />
          <button
            onClick={() => setShowHistory(!showHistory)}
            className="absolute right-1 top-1/2 -translate-y-1/2 text-gray-500 hover:text-gray-300"
            title="Search History"
          >
            ⌚
          </button>
        </div>

        {/* Search history dropdown */}
        {showHistory && searchHistory.length > 0 && (
          <div className="mt-1 bg-gray-800 border border-gray-700 rounded max-h-[150px] overflow-y-auto">
            <div className="flex items-center justify-between px-2 py-1 border-b border-gray-700">
              <span className="text-[9px] text-gray-500">Recent Searches</span>
              <button onClick={clearHistory} className="text-[9px] text-gray-500 hover:text-white">Clear</button>
            </div>
            {searchHistory.slice(0, 10).map((entry, i) => (
              <button
                key={i}
                className="w-full text-left px-2 py-1 text-[10px] text-gray-400 hover:bg-gray-700/50 flex items-center gap-2"
                onMouseDown={() => {
                  setInput(entry.query);
                  if (entry.tab !== activeTab) switchTab(entry.tab);
                  else handleSearch(entry.query);
                }}
              >
                <span className="text-gray-600 shrink-0">⌚</span>
                <span className="truncate flex-1">{entry.query}</span>
                <span className="text-gray-600 shrink-0">{entry.resultCount}</span>
              </button>
            ))}
          </div>
        )}

        {/* Replace toggle & input */}
        {activeTab === 'git' && (
          <div className="mt-1.5">
            <button
              onClick={() => setShowReplace(!showReplace)}
              className={`text-[10px] px-2 py-0.5 rounded transition-colors ${
                showReplace ? 'bg-orange-600/30 text-orange-300' : 'text-gray-500 hover:text-gray-300'
              }`}
            >
              {showReplace ? '▾ Replace' : '▸ Replace'}
            </button>
            {showReplace && (
              <div className="flex gap-1 mt-1">
                <input
                  type="text"
                  value={replaceInput}
                  onChange={(e) => setReplaceInput(e.target.value)}
                  placeholder="Replace with..."
                  className="flex-1 bg-gray-800 text-gray-200 text-[10px] border border-orange-700 rounded px-2 py-1 focus:outline-none focus:border-orange-500"
                />
                <button
                  onClick={handleReplace}
                  disabled={!input.trim() || !replaceInput.trim() || isReplacing || !hasResults}
                  className="px-2 py-1 bg-orange-600 text-white text-[10px] rounded hover:bg-orange-700 disabled:opacity-40"
                >
                  {isReplacing ? '...' : 'Replace All'}
                </button>
              </div>
            )}
          </div>
        )}

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

      {/* Replace results feedback */}
      {replaceResults.length > 0 && (
        <div className="px-2 py-1 bg-orange-900/20 border-b border-orange-800/30 max-h-[100px] overflow-y-auto">
          <div className="text-[9px] text-orange-400 mb-1">Replace Results:</div>
          {replaceResults.map((r, i) => (
            <div key={i} className={`text-[9px] ${r.success ? 'text-green-400' : 'text-red-400'}`}>
              {r.path ? `${r.path}: ${r.replacements} replacements` : r.error || 'Unknown'}
            </div>
          ))}
        </div>
      )}

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
                    className="px-3 py-1 hover:bg-gray-800/50 cursor-pointer group"
                    onClick={() => {
                      window.dispatchEvent(
                        new CustomEvent('likecodex:open-file', {
                          detail: { path: m.path, line: m.line },
                        })
                      );
                    }}
                  >
                    <div className="flex items-center gap-2">
                      <span className="text-[10px] text-gray-600 mr-2 shrink-0">{m.line}</span>
                      <span className="text-xs text-gray-400 font-mono truncate flex-1">
                        {highlightMatch(m.content, searchQuery)}
                      </span>
                      {/* Preview button */}
                      <span className="text-[9px] text-gray-600 opacity-0 group-hover:opacity-100 transition-opacity shrink-0">
                        ▶
                      </span>
                    </div>
                    {/* Context preview (show 1 extra line from content) */}
                    {m.content.length > 80 && (
                      <div className="text-[9px] text-gray-600 pl-8 truncate">
                        {m.content.slice(0, 120)}
                        {m.content.length > 120 && '...'}
                      </div>
                    )}
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
                    className="px-3 py-1 hover:bg-gray-800/50 cursor-pointer group"
                    onClick={() => {
                      window.dispatchEvent(
                        new CustomEvent('likecodex:open-file', {
                          detail: { path: result.filePath, line: match.line },
                        })
                      );
                    }}
                  >
                    <div className="flex items-center gap-2">
                      <span className="text-[10px] text-gray-600 mr-2 shrink-0">{match.line}</span>
                      <span className="text-[10px] text-gray-500 mr-1 shrink-0">
                        [{match.side === 'original' ? '原' : '新'}]
                      </span>
                      <span className="text-xs text-gray-400 font-mono truncate flex-1">
                        {highlightMatch(match.content, input)}
                      </span>
                      <span className="text-[9px] text-gray-600 opacity-0 group-hover:opacity-100 transition-opacity shrink-0">▶</span>
                    </div>
                    {match.content.length > 80 && (
                      <div className="text-[9px] text-gray-600 pl-8 truncate">
                        {match.content.slice(0, 120)}
                        {match.content.length > 120 && '...'}
                      </div>
                    )}
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
