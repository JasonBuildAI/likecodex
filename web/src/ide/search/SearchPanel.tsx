'use client';

/**
 * SearchPanel — Global file content search (Ctrl+Shift+F).
 *
 * Uses the git search API to find text in files.
 */

import { useState, useCallback, useRef, useEffect } from 'react';
import { useGitStore } from '@/ide/git/gitStore';

export function SearchPanel() {
  const {
    searchResults,
    isSearching,
    searchQuery,
    search,
  } = useGitStore();

  const [input, setInput] = useState('');
  const debounceRef = useRef<ReturnType<typeof setTimeout> | null>(null);

  const handleSearch = useCallback((value: string) => {
    setInput(value);
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      search(value);
    }, 300);
  }, [search]);

  useEffect(() => {
    return () => {
      if (debounceRef.current) clearTimeout(debounceRef.current);
    };
  }, []);

  // Group results by file
  const groupedResults: Record<string, typeof searchResults> = {};
  for (const r of searchResults) {
    if (!groupedResults[r.path]) groupedResults[r.path] = [];
    groupedResults[r.path].push(r);
  }

  return (
    <div className="flex flex-col h-full">
      {/* Search input */}
      <div className="p-2 border-b border-gray-700 shrink-0">
        <input
          type="text"
          value={input}
          onChange={(e) => handleSearch(e.target.value)}
          placeholder="搜索文件内容..."
          className="w-full bg-gray-800 text-gray-200 text-xs border border-gray-700 rounded px-2 py-1.5 focus:outline-none focus:border-blue-500"
          autoFocus
        />
        <div className="flex items-center justify-between mt-1.5">
          <span className="text-[10px] text-gray-500">
            {isSearching ? '搜索中...' : `${searchResults.length} 个结果`}
          </span>
          {searchQuery && (
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

      {/* Results */}
      <div className="flex-1 overflow-y-auto min-h-0">
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
                  // Open file in editor at line
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
