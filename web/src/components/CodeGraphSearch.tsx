'use client';

// ── Phase 7.2: Symbol Navigation Tree ─────────────────────────────────
// Future: Render symbols in a tree view (package → file → class → method)
// with expand/collapse, breadcrumb navigation, and click-to-scroll.
// See also: crates/likecodex-indexer/src/lib.rs (CodeGraph struct)
//           packages/likecodex-engine/likecodex_engine/tools/codegraph.py
// ─────────────────────────────────────────────────────────────────────────

import { useState } from 'react';
import { searchCodeGraph, searchIndex } from '@/lib/api';
import { useAppStore, type SearchResult } from '@/lib/store';

export function CodeGraphSearch() {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<SearchResult[]>([]);
  const [indexResults, setIndexResults] = useState<Array<{ path: string; language: string; size: number }>>([]);
  const [loading, setLoading] = useState(false);
  const [mode, setMode] = useState<'codegraph' | 'index'>('codegraph');
  const setActiveDiff = useAppStore((s) => s.setActiveDiff);

  const handleSearch = async () => {
    if (!query.trim()) return;
    setLoading(true);
    try {
      if (mode === 'codegraph') {
        const data = await searchCodeGraph(query);
        setResults(data.results || []);
        setIndexResults([]);
      } else {
        const data = await searchIndex(query);
        setIndexResults(data.results || []);
        setResults([]);
      }
    } catch {
      setResults([]);
      setIndexResults([]);
    } finally {
      setLoading(false);
    }
  };

  const kindIcon = (kind: string) => {
    switch (kind.toLowerCase()) {
      case 'function': return 'ƒ';
      case 'class': return 'C';
      case 'method': return 'm';
      case 'variable': return 'v';
      case 'interface': return 'I';
      default: return '•';
    }
  };

  return (
    <div className="p-4">
      <h2 className="text-sm font-semibold mb-3">Code Search</h2>
      <div className="flex gap-1 mb-2">
        <button
          onClick={() => setMode('codegraph')}
          className={`text-xs px-2 py-1 rounded ${mode === 'codegraph' ? 'bg-primary text-white' : 'bg-accent/10'}`}
        >
          Symbols
        </button>
        <button
          onClick={() => setMode('index')}
          className={`text-xs px-2 py-1 rounded ${mode === 'index' ? 'bg-primary text-white' : 'bg-accent/10'}`}
        >
          Files
        </button>
      </div>
      <div className="flex gap-2 mb-3">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
          placeholder={mode === 'codegraph' ? 'Search symbols...' : 'Search files...'}
          className="flex-1 rounded border border-border bg-background px-3 py-1.5 text-xs focus:outline-none focus:border-primary"
        />
        <button
          onClick={handleSearch}
          disabled={loading}
          className="rounded bg-primary px-3 py-1.5 text-xs text-white hover:bg-blue-600 disabled:opacity-50"
        >
          {loading ? '...' : 'Search'}
        </button>
      </div>

      <div className="space-y-1 max-h-80 overflow-y-auto">
        {results.map((r, i) => (
          <div key={i} className="flex items-center gap-2 rounded p-2 hover:bg-accent/10 text-xs">
            <span className="w-5 h-5 flex items-center justify-center rounded bg-primary/20 text-primary font-mono text-[10px] shrink-0">
              {kindIcon(r.kind)}
            </span>
            <div className="min-w-0 flex-1">
              <span className="font-medium">{r.name}</span>
              <span className="text-muted ml-1.5">{r.kind}</span>
              <div className="text-[10px] text-muted truncate">{r.path}{r.line ? `:${r.line}` : ''}</div>
            </div>
          </div>
        ))}
        {indexResults.map((r, i) => (
          <div key={i} className="flex items-center gap-2 rounded p-2 hover:bg-accent/10 text-xs">
            <span className="text-muted truncate flex-1">{r.path}</span>
            <span className="text-[10px] text-muted shrink-0">{r.language}</span>
            <span className="text-[10px] text-muted shrink-0">{r.size}B</span>
          </div>
        ))}
        {!loading && results.length === 0 && indexResults.length === 0 && query && (
          <p className="text-xs text-muted text-center py-4">No results found.</p>
        )}
      </div>
    </div>
  );
}
