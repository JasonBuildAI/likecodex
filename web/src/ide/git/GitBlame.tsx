'use client';

/**
 * GitBlame — Inline Git blame display for file lines.
 *
 * Shows commit hash, author, and date for each line of a file.
 * Key features:
 * - Line-by-line annotation (author, date, commit hash)
 * - Hover to see full commit message
 * - Click to navigate to commit details
 * - Toggle blame on/off per file
 * - Color-coded by author
 */

import { useState, useEffect, useCallback, useRef } from 'react';

interface BlameEntry {
  line: number;
  commitHash: string;
  shortHash: string;
  author: string;
  date: string;
  message: string;
  lineContent: string;
}

interface GitBlameProps {
  filePath: string;
  onClose: () => void;
}

const AUTHOR_COLORS = [
  'text-red-400',
  'text-blue-400',
  'text-green-400',
  'text-yellow-400',
  'text-purple-400',
  'text-pink-400',
  'text-teal-400',
  'text-orange-400',
];

function getAuthorColor(author: string): string {
  let hash = 0;
  for (let i = 0; i < author.length; i++) {
    hash = author.charCodeAt(i) + ((hash << 5) - hash);
  }
  return AUTHOR_COLORS[Math.abs(hash) % AUTHOR_COLORS.length];
}

export function GitBlame({ filePath, onClose }: GitBlameProps) {
  const [blameData, setBlameData] = useState<BlameEntry[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [hoveredLine, setHoveredLine] = useState<number | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    let cancelled = false;
    setIsLoading(true);
    setError(null);

    fetch(`/api/ide/git/blame?path=${encodeURIComponent(filePath)}`)
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        return res.json();
      })
      .then((data) => {
        if (!cancelled) {
          setBlameData(data.entries || []);
          setIsLoading(false);
        }
      })
      .catch((err) => {
        if (!cancelled) {
          setError(err.message);
          setIsLoading(false);
        }
      });

    return () => { cancelled = true; };
  }, [filePath]);

  if (isLoading) {
    return (
      <div className="text-xs text-gray-500 p-2 text-center">
        加载 blame 信息...
      </div>
    );
  }

  if (error) {
    return (
      <div className="text-xs text-red-400 p-2">
        Blame 加载失败: {error}
        <button onClick={onClose} className="ml-2 text-gray-400 hover:text-white">关闭</button>
      </div>
    );
  }

  return (
    <div className="border-t border-gray-700 bg-[#1a1a2e]">
      <div className="flex items-center justify-between px-3 py-1 bg-gray-800/50">
        <span className="text-[10px] text-gray-400 font-medium">Git Blame: {filePath.split('/').pop()}</span>
        <button onClick={onClose} className="text-[10px] text-gray-500 hover:text-white">×</button>
      </div>
      <div ref={scrollRef} className="overflow-y-auto max-h-[300px]">
        <table className="w-full text-[10px] font-mono">
          <tbody>
            {blameData.map((entry) => (
              <tr
                key={entry.line}
                className="hover:bg-gray-800/50 border-b border-gray-800/30"
                onMouseEnter={() => setHoveredLine(entry.line)}
                onMouseLeave={() => setHoveredLine(null)}
              >
                <td className="pl-2 pr-1 text-gray-500 text-right select-none w-10">
                  {entry.line}
                </td>
                <td className={`px-1 whitespace-nowrap ${getAuthorColor(entry.author)}`}>
                  <span className="cursor-pointer hover:underline" title={entry.message}>
                    {entry.shortHash}
                  </span>
                </td>
                <td className="px-1 text-gray-400 whitespace-nowrap">
                  {entry.author}
                </td>
                <td className="px-1 text-gray-500 whitespace-nowrap">
                  {entry.date}
                </td>
                <td className="px-1 text-gray-300 truncate max-w-[300px]">
                  {hoveredLine === entry.line ? entry.message : entry.lineContent}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}
