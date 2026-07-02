'use client';

/**
 * GitHistoryGraph — Visual commit graph with branch topology.
 *
 * Renders a DAG-style commit graph showing branch/merge relationships.
 * Key features:
 * - SVG-based commit node graph with branch lines
 * - Branch topology visualization (color-coded lines)
 * - Click on commit node to view details
 * - Expandable commit detail panel
 * - Search within commit history
 * - Time-based grouping
 */

import { useState, useEffect, useMemo } from 'react';

interface GraphCommit {
  hash: string;
  shortHash: string;
  message: string;
  author: string;
  date: string;
  refs: string[];
  parents: string[];
  branchColor: number;
}

interface BranchPath {
  x: number;
  y0: number;
  y1: number;
  color: string;
}

const BRANCH_COLORS = [
  '#4fc3f7', '#81c784', '#ffb74d', '#e57373',
  '#ba68c8', '#4dd0e1', '#aed581', '#f06292',
  '#7986cb', '#4db6ac',
];

export function GitHistoryGraph() {
  const [commits, setCommits] = useState<GraphCommit[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [selectedHash, setSelectedHash] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState('');

  useEffect(() => {
    setIsLoading(true);
    fetch('/api/ide/git/log?count=100&format=graph')
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then((data) => {
        setCommits(data.commits || []);
        setIsLoading(false);
      })
      .catch((err) => {
        setError(err.message);
        setIsLoading(false);
      });
  }, []);

  const filteredCommits = useMemo(() => {
    if (!searchQuery.trim()) return commits;
    const q = searchQuery.toLowerCase();
    return commits.filter(
      (c) =>
        c.message.toLowerCase().includes(q) ||
        c.author.toLowerCase().includes(q) ||
        c.shortHash.toLowerCase().includes(q)
    );
  }, [commits, searchQuery]);

  const graphPaths = useMemo(() => {
    const paths: BranchPath[] = [];
    const nodeSpacing = 24;
    const branchX = new Map<number, number>();

    filteredCommits.forEach((commit, idx) => {
      const colorIdx = commit.branchColor % BRANCH_COLORS.length;
      if (!branchX.has(colorIdx)) {
        branchX.set(colorIdx, branchX.size * 16 + 8);
      }
      const x = branchX.get(colorIdx)!;
      const y = idx * nodeSpacing + 8;

      if (idx > 0) {
        paths.push({
          x,
          y0: y - nodeSpacing,
          y1: y,
          color: BRANCH_COLORS[colorIdx],
        });
      }
    });

    return paths;
  }, [filteredCommits]);

  if (isLoading) {
    return <div className="text-xs text-gray-500 p-4 text-center">加载提交历史...</div>;
  }

  if (error) {
    return <div className="text-xs text-red-400 p-4 text-center">加载失败: {error}</div>;
  }

  const selectedCommit = selectedHash
    ? commits.find((c) => c.hash === selectedHash)
    : null;

  return (
    <div className="flex flex-col h-full">
      {/* Search */}
      <div className="px-2 py-1 border-b border-gray-700">
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder="搜索提交信息/作者/hash..."
          className="w-full bg-gray-800 text-gray-200 text-[10px] border border-gray-700 rounded px-2 py-0.5 focus:outline-none focus:border-blue-500 placeholder-gray-600"
        />
      </div>

      <div className="flex-1 flex min-h-0">
        {/* Graph */}
        <div className="overflow-y-auto flex-1">
          {filteredCommits.length === 0 && (
            <div className="text-xs text-gray-500 p-4 text-center">
              {searchQuery ? '没有匹配的提交' : '暂无提交记录'}
            </div>
          )}
          {filteredCommits.map((commit, idx) => {
            const color = BRANCH_COLORS[commit.branchColor % BRANCH_COLORS.length];
            return (
              <div
                key={commit.hash}
                onClick={() =>
                  setSelectedHash(
                    selectedHash === commit.hash ? null : commit.hash
                  )
                }
                className={`flex items-stretch cursor-pointer border-b border-gray-800/50 hover:bg-gray-800/30 ${
                  selectedHash === commit.hash ? 'bg-blue-900/20' : ''
                }`}
              >
                {/* Graph lane */}
                <svg
                  width="32"
                  height="24"
                  className="shrink-0"
                >
                  {graphPaths
                    .filter((p) => p.y1 === idx * 24 + 8)
                    .map((p, i) => (
                      <line
                        key={i}
                        x1={p.x}
                        y1={0}
                        x2={p.x}
                        y2={24}
                        stroke={p.color}
                        strokeWidth="1.5"
                        opacity="0.4"
                      />
                    ))}
                  <circle
                    cx="16"
                    cy="12"
                    r="4"
                    fill={color}
                    stroke="#1e1e2e"
                    strokeWidth="1.5"
                  />
                </svg>

                {/* Commit info */}
                <div className="flex-1 py-1 pr-2 min-w-0">
                  <div className="flex items-center gap-1.5">
                    <span className="text-[10px] text-gray-500 font-mono shrink-0">
                      {commit.shortHash}
                    </span>
                    {commit.refs.map((ref, i) => (
                      <span
                        key={i}
                        className={`text-[9px] px-1 rounded ${
                          ref.startsWith('HEAD')
                            ? 'bg-yellow-800/40 text-yellow-300'
                            : ref.startsWith('origin/')
                              ? 'bg-purple-900/30 text-purple-300'
                              : 'bg-green-900/30 text-green-300'
                        }`}
                      >
                        {ref}
                      </span>
                    ))}
                    <span className="text-xs text-gray-200 truncate flex-1">
                      {commit.message}
                    </span>
                  </div>
                  <div className="text-[9px] text-gray-600 mt-0.5">
                    {commit.author} · {commit.date}
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        {/* Detail panel */}
        {selectedCommit && (
          <div className="w-64 border-l border-gray-700 p-2 overflow-y-auto shrink-0">
            <div className="text-[10px] text-gray-400 font-medium mb-2">提交详情</div>
            <div className="space-y-1.5">
              <div>
                <span className="text-[9px] text-gray-500">Hash:</span>
                <div className="text-[10px] text-gray-200 font-mono">{selectedCommit.hash}</div>
              </div>
              <div>
                <span className="text-[9px] text-gray-500">作者:</span>
                <div className="text-[10px] text-gray-200">{selectedCommit.author}</div>
              </div>
              <div>
                <span className="text-[9px] text-gray-500">日期:</span>
                <div className="text-[10px] text-gray-200">{selectedCommit.date}</div>
              </div>
              <div>
                <span className="text-[9px] text-gray-500">信息:</span>
                <div className="text-[10px] text-gray-200">{selectedCommit.message}</div>
              </div>
              {selectedCommit.refs.length > 0 && (
                <div>
                  <span className="text-[9px] text-gray-500">引用:</span>
                  <div className="flex flex-wrap gap-1 mt-0.5">
                    {selectedCommit.refs.map((ref, i) => (
                      <span
                        key={i}
                        className="text-[9px] px-1 bg-gray-700 text-gray-300 rounded"
                      >
                        {ref}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
