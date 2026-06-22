'use client';

/**
 * TestRunnerPanel — Test discovery, execution, and results display.
 *
 * Features:
 * - Auto-discover test files (pytest, vitest, cargo test)
 * - Run all tests or individual tests
 * - Real-time SSE status updates
 * - Pass/fail/skip status with error details
 * - AI error analysis on failed tests
 */

import { useState, useEffect, useCallback } from 'react';
import type { TestFile, TestCase, TestStatus } from './types';

export function TestRunnerPanel() {
  const [testFiles, setTestFiles] = useState<TestFile[]>([]);
  const [isRunning, setIsRunning] = useState(false);
  const [isDiscovering, setIsDiscovering] = useState(false);
  const [filter, setFilter] = useState('');
  const [passedCount, setPassedCount] = useState(0);
  const [failedCount, setFailedCount] = useState(0);
  const [totalCount, setTotalCount] = useState(0);
  const [expandedFiles, setExpandedFiles] = useState<Set<string>>(new Set());
  const [selectedError, setSelectedError] = useState<{ name: string; message: string; stack: string } | null>(null);
  const [aiAnalysis, setAiAnalysis] = useState<string | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);

  const discoverTests = useCallback(async () => {
    setIsDiscovering(true);
    try {
      const resp = await fetch('/api/ide/tests/discover');
      if (resp.ok) {
        const data = await resp.json();
        const files: TestFile[] = (data.testFiles || []).map((tf: TestFile) => ({
          path: tf.path,
          framework: tf.framework,
          tests: (tf.tests || []).map((t: TestCase) => ({
            ...t,
            status: 'pending' as TestStatus,
            duration: 0,
            errorMessage: '',
            errorStack: '',
          })),
        }));
        setTestFiles(files);
        setTotalCount(files.reduce((sum, f) => sum + f.tests.length, 0));
        setPassedCount(0);
        setFailedCount(0);
      }
    } catch {
      // Best-effort
    } finally {
      setIsDiscovering(false);
    }
  }, []);

  // Auto-discover on mount
  useEffect(() => {
    discoverTests();
  }, [discoverTests]);

  const updateTestStatus = useCallback((testId: string, status: TestStatus, duration?: number, error?: string, stack?: string) => {
    setTestFiles((prev) =>
      prev.map((tf) => ({
        ...tf,
        tests: tf.tests.map((t) =>
          t.id === testId
            ? {
                ...t,
                status,
                duration: duration ?? t.duration,
                errorMessage: error ?? t.errorMessage,
                errorStack: stack ?? t.errorStack,
              }
            : t
        ),
      }))
    );
  }, []);

  const runAllTests = useCallback(async () => {
    setIsRunning(true);
    setPassedCount(0);
    setFailedCount(0);

    // Reset all test statuses
    setTestFiles((prev) =>
      prev.map((tf) => ({
        ...tf,
        tests: tf.tests.map((t) => ({ ...t, status: 'pending' as TestStatus })),
      }))
    );

    try {
      const resp = await fetch('/api/ide/tests/run', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ filter }),
      });

      if (!resp.ok || !resp.body) return;

      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let passed = 0;
      let failed = 0;

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value, { stream: true });
        for (const line of chunk.split('\n')) {
          if (!line.startsWith('data: ')) continue;
          const dataStr = line.slice(6).trim();
          if (dataStr === '[DONE]') continue;

          try {
            const data = JSON.parse(dataStr);
            switch (data.type) {
              case 'start':
                setTotalCount(data.count);
                break;
              case 'test_start':
                updateTestStatus(data.testId, 'running');
                break;
              case 'test_result':
                updateTestStatus(data.testId, data.status, data.duration, data.error, data.stack);
                if (data.status === 'passed') passed++;
                if (data.status === 'failed') failed++;
                setPassedCount(passed);
                setFailedCount(failed);
                break;
              case 'done':
                setPassedCount(data.passed);
                setFailedCount(data.failed);
                break;
            }
          } catch {
            // Ignore parse errors
          }
        }
      }
    } catch {
      // Best-effort
    } finally {
      setIsRunning(false);
    }
  }, [filter, updateTestStatus]);

  const toggleFile = useCallback((path: string) => {
    setExpandedFiles((prev) => {
      const next = new Set(prev);
      if (next.has(path)) next.delete(path);
      else next.add(path);
      return next;
    });
  }, []);

  const analyzeError = useCallback(async (testName: string, errorMessage: string, errorStack: string) => {
    setIsAnalyzing(true);
    setAiAnalysis(null);
    try {
      const resp = await fetch('/api/ide/debug/analyze', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          errorMessage,
          stackTrace: errorStack,
          relevantCode: '',
          filePath: '',
        }),
      });
      if (resp.ok) {
        const data = await resp.json();
        setAiAnalysis(`**根因**: ${data.root_cause}\n\n**修复**: ${data.fix}\n\n**预防**: ${data.prevention}`);
      }
    } catch {
      setAiAnalysis('分析失败');
    } finally {
      setIsAnalyzing(false);
    }
  }, []);

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center gap-2 px-3 py-2 border-b border-gray-700 shrink-0">
        <span className="text-xs font-semibold text-white">测试</span>
        <div className="flex gap-1 ml-2">
          <button
            onClick={runAllTests}
            disabled={isRunning}
            className="px-2 py-0.5 bg-green-600 text-white text-[10px] rounded hover:bg-green-700 disabled:opacity-40"
          >
            {isRunning ? '运行中...' : '▶ 全部运行'}
          </button>
          <button
            onClick={discoverTests}
            disabled={isDiscovering}
            className="px-2 py-0.5 bg-gray-600 text-white text-[10px] rounded hover:bg-gray-700 disabled:opacity-40"
          >
            {isDiscovering ? '...' : '⟳ 刷新'}
          </button>
        </div>
        <div className="ml-auto text-[10px] text-gray-400">
          {passedCount}/{totalCount} 通过
          {failedCount > 0 && <span className="text-red-400 ml-1">{failedCount} 失败</span>}
        </div>
      </div>

      {/* Filter */}
      <div className="px-2 py-1 border-b border-gray-700 shrink-0">
        <input
          type="text"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          placeholder="过滤测试..."
          className="w-full bg-gray-800 text-gray-200 text-[10px] border border-gray-700 rounded px-2 py-0.5 focus:outline-none focus:border-blue-500"
        />
      </div>

      {/* Test list */}
      <div className="flex-1 overflow-y-auto min-h-0">
        {testFiles.length === 0 && (
          <div className="px-3 py-6 text-center text-xs text-gray-500">
            {isDiscovering ? '发现测试中...' : '未找到测试文件'}
          </div>
        )}

        {testFiles
          .filter((tf) => !filter || tf.tests.some((t) => t.name.toLowerCase().includes(filter.toLowerCase())))
          .map((tf) => (
            <div key={tf.path}>
              {/* File header */}
              <div
                onClick={() => toggleFile(tf.path)}
                className="flex items-center px-3 py-1 cursor-pointer hover:bg-gray-800/50 border-b border-gray-800/30"
              >
                <span className="text-[10px] text-gray-500 mr-1">
                  {expandedFiles.has(tf.path) ? '▼' : '▶'}
                </span>
                <span className="text-[10px] text-blue-400 mr-1">📄</span>
                <span className="text-xs text-gray-300 flex-1 truncate">{tf.path}</span>
                <span className="text-[10px] text-gray-600">{tf.framework}</span>
                <span className="text-[10px] ml-2">
                  {tf.tests.filter((t) => t.status === 'passed').length}/{tf.tests.length}
                </span>
              </div>

              {/* Test cases */}
              {expandedFiles.has(tf.path) &&
                tf.tests
                  .filter((t) => !filter || t.name.toLowerCase().includes(filter.toLowerCase()))
                  .map((t) => (
                    <div
                      key={t.id}
                      className="px-3 py-0.5 pl-8 hover:bg-gray-800/30 cursor-pointer"
                      onClick={() => {
                        if (t.status === 'failed' && t.errorMessage) {
                          setSelectedError({ name: t.name, message: t.errorMessage, stack: t.errorStack });
                          setAiAnalysis(null);
                        }
                      }}
                    >
                      <span className="text-[10px] mr-2">
                        {t.status === 'passed' && <span className="text-green-400">✅</span>}
                        {t.status === 'failed' && <span className="text-red-400">❌</span>}
                        {t.status === 'running' && <span className="text-yellow-400 animate-pulse">⏳</span>}
                        {t.status === 'pending' && <span className="text-gray-600">⬜</span>}
                        {t.status === 'skipped' && <span className="text-gray-500">⏭️</span>}
                      </span>
                      <span className={`text-xs ${t.status === 'failed' ? 'text-red-300' : 'text-gray-400'}`}>
                        {t.name}
                      </span>
                      {t.duration > 0 && (
                        <span className="text-[10px] text-gray-600 ml-2">{t.duration}ms</span>
                      )}
                    </div>
                  ))}
            </div>
          ))}
      </div>

      {/* Error detail */}
      {selectedError && (
        <div className="border-t border-gray-700 p-2 max-h-[200px] overflow-y-auto shrink-0 bg-gray-900/50">
          <div className="flex items-center justify-between mb-1">
            <span className="text-[10px] text-red-400 font-mono">{selectedError.name}</span>
            <button
              onClick={() => {
                setSelectedError(null);
                setAiAnalysis(null);
              }}
              className="text-[10px] text-gray-500 hover:text-white"
            >
              ×
            </button>
          </div>
          <pre className="text-[10px] text-red-300 font-mono whitespace-pre-wrap mb-2">
            {selectedError.message}
          </pre>
          <button
            onClick={() => analyzeError(selectedError.name, selectedError.message, selectedError.stack)}
            disabled={isAnalyzing}
            className="px-2 py-1 bg-blue-600 text-white text-[10px] rounded hover:bg-blue-700 disabled:opacity-40"
          >
            {isAnalyzing ? 'AI 分析中...' : '💡 AI 分析'}
          </button>
          {aiAnalysis && (
            <div className="mt-2 p-2 bg-blue-900/20 rounded text-[10px] text-blue-200 whitespace-pre-wrap">
              {aiAnalysis}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
