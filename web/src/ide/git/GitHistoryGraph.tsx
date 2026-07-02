'use client';

/**
 * GitHistoryGraph — Branch topology graph and commit timeline visualization.
 *
 * Features:
 * - SVG-based branch topology showing commit graph
 * - Commit timeline with author/date display
 * - File list on selection
 * - Branch labels
 */

import { useState, useMemo } from 'react';

interface CommitNode {
  hash: string;
  shortHash: string;
  message: string;
  author: string;
  date: string;
  files?: string[];
  branch?: string;
  parents: string[];
  refs?: string[];
}

interface GitHistoryGraphProps {
  commits: CommitNode[];
  branches?: { name: string; current: boolean }[];
  onSelectCommit?: (hash: string) => void;
  selectedHash?: string | null;
}

export function GitHistoryGraph({ commits, branches, onSelectCommit, selectedHash }: GitHistoryGraphProps) {
  const [selectedCommit, setSelectedCommit] = useState<string | null>(selectedHash || null);
  const [expandedCommit, setExpandedCommit] = useState<string | null>(null);
  const [filter, setFilter] = useState('');

  const filteredCommits = useMemo(() => {
    if (!filter.trim()) return commits;
    const q = filter.toLowerCase();
    return commits.filter(
      (c) =>
        c.message.toLowerCase().includes(q) ||
        c.author.toLowerCase().includes(q) ||
        c.shortHash.toLowerCase().includes(q) ||
        (c.files && c.files.some((f) => f.toLowerCase().includes(q)))
    );
  }, [commits, filter]);

  const handleSelect = (hash: string) => {
    setSelectedCommit(hash === selectedCommit ? null : hash);
    setExpandedCommit(hash === expandedCommit ? null : hash);
    if (onSelectCommit) onSelectCommit(hash);
  };

  if (!commits || commits.length === 0) {
    return (
      <div className="px-3 py-6 text-center text-xs text-gray-500">
        暂无提交记录
      </div>
    );
  }

  const currentBranch = branches?.find((b) => b.current)?.name || '';

  return (
    <div className="flex flex-col h-full">
      {/* Filter bar */}
      <div className="px-2 py-1 border-b border-gray-700">
        <input
          type="text"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          placeholder="搜索提交信息/作者/文件..."
          className="w-full bg-gray-800 text-gray-200 text-[10px] border border-gray-700 rounded px-2 py-0.5 focus:outline-none focus:border-blue-500 placeholder-gray-600"
        />
      </div>

      {/* Commit list */}
      <div className="flex-1 overflow-y-auto min-h-0">
        {/* Branch refs header */}
        {branches && branches.length > 0 && (
          <div className="px-3 py-1.5 border-b border-gray-800 flex flex-wrap gap-1">
            {branches.map((b) => (
              <span
                key={b.name}
                className={`text-[9px] px-1.5 py-0.5 rounded-full ${
                  b.current
                    ? 'bg-blue-900/50 text-blue-300 border border-blue-700'
                    : 'bg-gray-800 text-gray-400 border border-gray-700'
                }`}
              >
                {b.current ? '● ' : ''}{b.name}
              </span>
            ))}
          </div>
        )}

        {filteredCommits.length === 0 && (
          <div className="px-3 py-6 text-center text-xs text-gray-500">
            没有匹配的提交
          </div>
        )}

        {filteredCommits.map((commit, idx) => {
          const isSelected = selectedCommit === commit.hash;
          const isExpanded = expandedCommit === commit.hash;

          return (
            <div key={commit.hash}>
              <div
                onClick={() => handleSelect(commit.hash)}
                className={`flex items-start px-3 py-2 cursor-pointer border-b border-gray-800/50 hover:bg-gray-800/30 transition-colors ${
                  isSelected ? 'bg-blue-900/20 border-l-2 border-l-blue-500' : ''
                }`}
              >
                {/* SVG branch topology indicator */}
                <div className="flex flex-col items-center mr-2 shrink-0">
                  {/* Branch line */}
                  <svg width="16" height="28" viewBox="0 0 16 28" className="overflow-visible">
                    {idx < filteredCommits.length - 1 && (
                      <line
                        x1="8"
                        y1="0"
                        x2="8"
                        y2="20"
                        stroke="#4a5568"
                        strokeWidth="1.5"
                      />
                    )}
                    {idx === 0 && (
                      <>
                        <circle cx="8" cy="14" r="4" fill="#3b82f6" stroke="#60a5fa" strokeWidth="1" />
                        <circle cx="8" cy="14" r="2" fill="#60a5fa" />
                      </>
                    )}
                    {idx > 0 && (
                      <circle cx="8" cy="14" r="3" fill="#2d3748" stroke="#4a5568" strokeWidth="1" />
                    )}
                  </svg>
                  {/* Vertical spacer */}
                </div>

                {/* Commit info */}
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2">
                    <span className="text-[10px] text-gray-500 font-mono shrink-0">
                      {commit.shortHash}
                    </span>
                    {commit.refs && commit.refs.length > 0 && (
                      <span className="text-[9px] text-yellow-400 bg-yellow-900/30 px-1 rounded">
                        {commit.refs[0]}
                      </span>
                    )}
                    <span className="text-xs text-gray-200 flex-1 truncate">
                      {commit.message}
                    </span>
                  </div>
                  <div className="flex items-center gap-2 mt-0.5">
                    <span className="text-[10px] text-gray-500">{commit.author}</span>
                    <span className="text-[10px] text-gray-600">·</span>
                    <span className="text-[10px] text-gray-600">{commit.date}</span>
                  </div>

                  {/* File list (when expanded) */}
                  {isExpanded && commit.files && commit.files.length > 0 && (
                    <div className="mt-1.5 pl-0 border-l-0 border-gray-700">
                      <div className="text-[9px] text-gray-500 uppercase tracking-wider mb-0.5">
                        变更文件 ({commit.files.length})
                      </div>
                      <div className="space-y-0.5 max-h-[100px] overflow-y-auto">
                        {commit.files.slice(0, 20).map((file, fi) => (
                          <div key={fi} className="text-[10px] text-gray-400 font-mono truncate pl-1">
                            {file}
                          </div>
                        ))}
                        {commit.files.length > 20 && (
                          <div className="text-[9px] text-gray-600 pl-1">
                            ... 还有 {commit.files.length - 20} 个文件
                          </div>
                        )}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
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
