'use client';

import { useState, useCallback } from 'react';
import { searchCodeGraph, searchIndex, searchCodeGraphCallers, searchCodeGraphViz } from '@/lib/api';
import { useAppStore, type SearchResult } from '@/lib/store';
import type { CodeGraphVizResult } from '@/lib/api';

type Tab = 'codegraph' | 'index' | 'callgraph';

export function CodeGraphSearch() {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState<SearchResult[]>([]);
  const [indexResults, setIndexResults] = useState<Array<{ path: string; language: string; size: number }>>([]);
  const [loading, setLoading] = useState(false);
  const [mode, setMode] = useState<Tab>('codegraph');
  const [vizData, setVizData] = useState<CodeGraphVizResult | null>(null);
  const [callersData, setCallersData] = useState<Array<{ path: string; line: number }>>([]);
  const [selectedSymbol, setSelectedSymbol] = useState<string>('');
  const [vizDepth, setVizDepth] = useState(2);
  const setActiveDiff = useAppStore((s) => s.setActiveDiff);

  const handleSearch = useCallback(async () => {
    if (!query.trim()) return;
    setLoading(true);
    setVizData(null);
    setCallersData([]);
    try {
      switch (mode) {
        case 'codegraph': {
          const data = await searchCodeGraph(query);
          setResults(data.results || []);
          setIndexResults([]);
          break;
        }
        case 'index': {
          const data = await searchIndex(query);
          setIndexResults(data.results || []);
          setResults([]);
          break;
        }
        case 'callgraph': {
          // Run both calls in parallel
          setSelectedSymbol(query.trim());
          const resultsPromise = searchCodeGraph(query).then(d => d.results || []);
          const vizPromise = searchCodeGraphViz(query.trim(), vizDepth);
          const [searchResults, viz] = await Promise.all([resultsPromise, vizPromise]);
          setResults(searchResults);
          setVizData(viz);
          break;
        }
      }
    } catch {
      setResults([]);
      setIndexResults([]);
      setVizData(null);
    } finally {
      setLoading(false);
    }
  }, [query, mode, vizDepth]);

  const handleSymbolClick = useCallback(async (name: string) => {
    const data = await searchCodeGraphCallers(name);
    setCallersData(data.callers || []);
  }, []);

  const handleNodeClick = useCallback((name: string) => {
    setQuery(name);
    setSelectedSymbol(name);
    searchCodeGraphViz(name, vizDepth).then(viz => setVizData(viz));
  }, [vizDepth]);

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

  const depthColor = (depth: number) => {
    const colors = ['text-blue-400', 'text-green-400', 'text-yellow-400', 'text-orange-400', 'text-red-400'];
    return colors[Math.min(depth, colors.length - 1)];
  };

  return (
    <div className="p-4">
      <h2 className="text-sm font-semibold mb-3">Code Search</h2>
      {/* Tab bar */}
      <div className="flex gap-1 mb-2">
        <button
          onClick={() => { setMode('codegraph'); setVizData(null); }}
          className={`text-xs px-2 py-1 rounded ${mode === 'codegraph' ? 'bg-primary text-white' : 'bg-accent/10'}`}
        >
          Symbols
        </button>
        <button
          onClick={() => { setMode('index'); setVizData(null); }}
          className={`text-xs px-2 py-1 rounded ${mode === 'index' ? 'bg-primary text-white' : 'bg-accent/10'}`}
        >
          Files
        </button>
        <button
          onClick={() => { setMode('callgraph'); setVizData(null); }}
          className={`text-xs px-2 py-1 rounded ${mode === 'callgraph' ? 'bg-primary text-white' : 'bg-accent/10'}`}
        >
          Call Graph
        </button>
      </div>

      {/* Search box */}
      <div className="flex gap-2 mb-3">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
          placeholder={
            mode === 'codegraph' ? 'Search symbols...' :
            mode === 'index' ? 'Search files...' :
            'Search function/class for call graph...'
          }
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

      {/* Call Graph Depth control */}
      {mode === 'callgraph' && (
        <div className="flex items-center gap-2 mb-2">
          <label className="text-[10px] text-muted">Depth:</label>
          {[1, 2, 3].map(d => (
            <button
              key={d}
              onClick={() => setVizDepth(d)}
              className={`text-[10px] px-1.5 py-0.5 rounded ${
                vizDepth === d ? 'bg-primary/20 text-primary' : 'bg-accent/5 text-muted'
              }`}
            >
              {d}
            </button>
          ))}
        </div>
      )}

      {/* Call Graph Visualization */}
      {mode === 'callgraph' && vizData && vizData.nodes.length > 0 && (
        <div className="mb-3 p-2 rounded bg-accent/5 border border-border">
          <div className="text-[10px] font-semibold mb-1 text-muted">
            Call Graph: {selectedSymbol}
            <span className="ml-2 text-muted/60 font-normal">
              ({vizData.nodes.length} nodes, {vizData.edges.length} edges)
            </span>
          </div>
          {/* Nodes list */}
          <div className="space-y-0.5 max-h-48 overflow-y-auto">
            {vizData.nodes.map((node, i) => (
              <div
                key={i}
                className="flex items-center gap-1.5 px-2 py-0.5 rounded text-[10px] cursor-pointer hover:bg-accent/10"
                onClick={() => handleNodeClick(node.name)}
                title={`${node.kind}: ${node.name} (${node.path}:${node.line})`}
              >
                <span className={`font-mono ${depthColor(node.depth)} shrink-0 w-3 text-center`}>
                  {node.depth === 0 ? '★' : `·${node.depth}`}
                </span>
                <span className="w-4 h-4 flex items-center justify-center rounded bg-primary/20 text-primary font-mono text-[9px] shrink-0">
                  {kindIcon(node.kind)}
                </span>
                <span className="font-medium truncate">{node.name}</span>
                <span className="text-muted/50 ml-auto shrink-0">{node.kind}</span>
              </div>
            ))}
          </div>
          {/* Edges list */}
          {vizData.edges.length > 0 && (
            <div className="mt-1 pt-1 border-t border-border/50">
              <div className="text-[9px] text-muted/60 mb-0.5">Call Relationships:</div>
              <div className="space-y-0.5 max-h-32 overflow-y-auto">
                {vizData.edges.slice(0, 20).map((edge, i) => (
                  <div key={i} className="text-[9px] text-muted/70 px-1">
                    <span
                      className="text-blue-400 cursor-pointer hover:underline"
                      onClick={() => handleNodeClick(edge.source)}
                    >{edge.source}</span>
                    <span className="mx-1">→</span>
                    <span
                      className="text-green-400 cursor-pointer hover:underline"
                      onClick={() => handleNodeClick(edge.target)}
                    >{edge.target}</span>
                  </div>
                ))}
                {vizData.edges.length > 20 && (
                  <div className="text-[9px] text-muted/40 px-1">
                    ... and {vizData.edges.length - 20} more
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      )}

      {/* Callers list (when clicking a symbol) */}
      {callersData.length > 0 && (
        <div className="mb-3 p-2 rounded bg-accent/5 border border-border">
          <div className="text-[10px] font-semibold mb-1 text-muted">
            Callers of: {selectedSymbol}
          </div>
          <div className="space-y-0.5 max-h-32 overflow-y-auto">
            {callersData.map((caller, i) => (
              <div key={i} className="flex items-center gap-1 px-2 py-0.5 text-[10px] text-muted/70">
                <span className="text-muted/40">📄</span>
                <span className="truncate">{caller.path}</span>
                <span className="ml-auto shrink-0">:{caller.line}</span>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Symbol/Index Results */}
      <div className="space-y-1 max-h-80 overflow-y-auto">
        {results.map((r, i) => (
          <div
            key={i}
            className="flex items-center gap-2 rounded p-2 hover:bg-accent/10 text-xs cursor-pointer"
            onClick={() => {
              setQuery(r.name);
              if (mode === 'codegraph') {
                handleSymbolClick(r.name);
              } else if (mode === 'callgraph') {
                handleNodeClick(r.name);
              }
            }}
          >
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
        {!loading && results.length === 0 && indexResults.length === 0 && !vizData && query && (
          <p className="text-xs text-muted text-center py-4">No results found.</p>
        )}
      </div>
    </div>
  );
}
