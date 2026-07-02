'use client';

/**
 * GitSearchPanel — Search across git commits, diffs, and file changes.
 *
 * Key features:
 * - Search commit messages, authors, and file changes
 * - Search across diffs (code content search in git history)
 * - Results grouped by commit with diff snippets
 * - Filter by author, date range, file path
 * - Keyboard shortcuts (Ctrl+Shift+F to focus)
 */

import { useState, useCallback, useEffect, useRef } from 'react';

interface SearchHit {
  commitHash: string;
  shortHash: string;
  message: string;
  author: string;
  date: string;
  file: string;
  line: number;
  content: string;
  matchType: 'commit' | 'diff' | 'file';
}

interface SearchFilters {
  author: string;
  filePattern: string;
  since: string;
  until: string;
  maxResults: number;
}

export function GitSearchPanel() {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<SearchHit[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showFilters, setShowFilters] = useState(false);
  const [filters, setFilters] = useState<SearchFilters>({
    author: '',
    filePattern: '',
    since: '',
    until: '',
    maxResults: 50,
  });
  const inputRef = useRef<HTMLInputElement>(null);
  const searchTimeoutRef = useRef<ReturnType<typeof setTimeout>>();

  const performSearch = useCallback(async (q: string, f: SearchFilters) => {
    if (!q.trim()) {
      setResults([]);
      return;
    }

    setIsLoading(true);
    setError(null);

    const params = new URLSearchParams();
    params.set('q', q);
    if (f.author) params.set('author', f.author);
    if (f.filePattern) params.set('file', f.filePattern);
    if (f.since) params.set('since', f.since);
    if (f.until) params.set('until', f.until);
    params.set('max', String(f.maxResults));

    try {
      const resp = await fetch(`/api/ide/git/search-commits?${params}`);
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = await resp.json();
      setResults(data.results || []);
    } catch (err) {
      setError(String(err));
      setResults([]);
    } finally {
      setIsLoading(false);
    }
  }, []);

  // Debounced search
  const handleQueryChange = useCallback(
    (value: string) => {
      setQuery(value);
      if (searchTimeoutRef.current) clearTimeout(searchTimeoutRef.current);
      searchTimeoutRef.current = setTimeout(() => {
        performSearch(value, filters);
      }, 300);
    },
    [filters, performSearch]
  );

  useEffect(() => {
    return () => {
      if (searchTimeoutRef.current) clearTimeout(searchTimeoutRef.current);
    };
  }, []);

  // Render hit row
  const renderHit = (hit: SearchHit, idx: number) => (
    <div
      key={`${hit.commitHash}-${hit.file}-${hit.line}-${idx}`}
      className="border-b border-gray-800/50 hover:bg-gray-800/30"
    >
      <div className="px-3 py-1.5">
        <div className="flex items-center gap-1.5">
          <span className="text-[10px] text-gray-500 font-mono">{hit.shortHash}</span>
          <span
            className={`text-[9px] px-1 rounded ${
              hit.matchType === 'commit'
                ? 'bg-blue-900/30 text-blue-300'
                : hit.matchType === 'diff'
                  ? 'bg-green-900/30 text-green-300'
                  : 'bg-yellow-900/30 text-yellow-300'
            }`}
          >
            {hit.matchType === 'commit' ? '提交' : hit.matchType === 'diff' ? '代码' : '文件'}
          </span>
          {hit.file && (
            <span className="text-[10px] text-purple-300 truncate max-w-[200px]" title={hit.file}>
              {hit.file}
            </span>
          )}
        </div>
        <div className="text-xs text-gray-200 mt-0.5">{hit.message}</div>
        {hit.content && (
          <div className="text-[10px] text-gray-400 mt-0.5 bg-gray-900/50 px-1.5 py-0.5 rounded font-mono truncate">
            <span className="text-gray-500 mr-1">L{hit.line}:</span>
            {hit.content}
          </div>
        )}
        <div className="text-[9px] text-gray-600 mt-0.5">{hit.author} · {hit.date}</div>
      </div>
    </div>
  );

  // Group results by commit
  const groupedResults: { hash: string; hits: SearchHit[] }[] = [];
  const seenHashes = new Set<string>();
  for (const hit of results) {
    if (!seenHashes.has(hit.commitHash)) {
      seenHashes.add(hit.commitHash);
      groupedResults.push({ hash: hit.commitHash, hits: [hit] });
    } else {
      const group = groupedResults.find((g) => g.hash === hit.commitHash);
      if (group) group.hits.push(hit);
    }
  }

  return (
    <div className="flex flex-col h-full">
      {/* Search bar */}
      <div className="px-2 py-1.5 border-b border-gray-700 space-y-1">
        <div className="flex items-center gap-1">
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => handleQueryChange(e.target.value)}
            placeholder="搜索提交信息、代码变更... (支持正则)"
            className="flex-1 bg-gray-800 text-gray-200 text-xs border border-gray-700 rounded px-2 py-1 focus:outline-none focus:border-blue-500 placeholder-gray-600 font-mono"
            autoFocus
          />
          <button
            onClick={() => setShowFilters(!showFilters)}
            className={`px-2 py-1 text-[10px] rounded ${
              showFilters ? 'bg-blue-600 text-white' : 'bg-gray-700 text-gray-300 hover:bg-gray-600'
            }`}
            title="高级搜索"
          >
            筛选
          </button>
        </div>

        {/* Filters */}
        {showFilters && (
          <div className="grid grid-cols-2 gap-1.5 p-1.5 bg-gray-800/50 rounded">
            <input
              type="text"
              value={filters.author}
              onChange={(e) => {
                const newFilters = { ...filters, author: e.target.value };
                setFilters(newFilters);
                if (query.trim()) performSearch(query, newFilters);
              }}
              placeholder="作者"
              className="bg-gray-800 text-gray-200 text-[10px] border border-gray-700 rounded px-1.5 py-0.5 focus:outline-none focus:border-blue-500"
            />
            <input
              type="text"
              value={filters.filePattern}
              onChange={(e) => {
                const newFilters = { ...filters, filePattern: e.target.value };
                setFilters(newFilters);
                if (query.trim()) performSearch(query, newFilters);
              }}
              placeholder="文件路径模式"
              className="bg-gray-800 text-gray-200 text-[10px] border border-gray-700 rounded px-1.5 py-0.5 focus:outline-none focus:border-blue-500"
            />
            <input
              type="date"
              value={filters.since}
              onChange={(e) => {
                const newFilters = { ...filters, since: e.target.value };
                setFilters(newFilters);
                if (query.trim()) performSearch(query, newFilters);
              }}
              className="bg-gray-800 text-gray-200 text-[10px] border border-gray-700 rounded px-1.5 py-0.5 focus:outline-none focus:border-blue-500"
              title="开始日期"
            />
            <input
              type="date"
              value={filters.until}
              onChange={(e) => {
                const newFilters = { ...filters, until: e.target.value };
                setFilters(newFilters);
                if (query.trim()) performSearch(query, newFilters);
              }}
              className="bg-gray-800 text-gray-200 text-[10px] border border-gray-700 rounded px-1.5 py-0.5 focus:outline-none focus:border-blue-500"
              title="结束日期"
            />
          </div>
        )}
      </div>

      {/* Status */}
      <div className="px-3 py-1 text-[10px] text-gray-500 border-b border-gray-800">
        {isLoading
          ? '搜索中...'
          : query
            ? `找到 ${results.length} 个结果`
            : '输入搜索关键词来查找提交和变更'}
      </div>

      {/* Error */}
      {error && (
        <div className="px-3 py-1 text-[10px] text-red-400 bg-red-900/20">
          搜索出错: {error}
        </div>
      )}

      {/* Results */}
      <div className="flex-1 overflow-y-auto min-h-0">
        {groupedResults.length === 0 && !isLoading && query && (
          <div className="px-3 py-6 text-center text-xs text-gray-500">
            没有匹配结果
          </div>
        )}
        {groupedResults.map((group) => (
          <div key={group.hash} className="border-b border-gray-700/50">
            <div className="px-3 py-1 bg-gray-800/30 text-[10px] text-gray-500 font-mono">
              {group.hits[0].shortHash} — {group.hits.length} 个匹配
            </div>
            {group.hits.slice(0, 5).map((hit, i) => renderHit(hit, i))}
            {group.hits.length > 5 && (
              <div className="px-3 py-1 text-[9px] text-gray-600 text-center">
                +{group.hits.length - 5} 更多匹配
              </div>
            )}
          </div>
        ))}
      </div>
    </div>
  );
}
