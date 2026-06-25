'use client';

import React, { useState, memo } from 'react';
import { motion, AnimatePresence } from 'framer-motion';

interface CodeBlockProps {
  language: string;
  code: string;
  filename?: string;
}

// ── Syntax highlighting (basic, regex-based) ────────────────────────────
function highlightCode(code: string, language: string): React.ReactNode {
  // Basic keyword highlighting for common languages
  const keywords: Record<string, string[]> = {
    javascript: ['const', 'let', 'var', 'function', 'return', 'if', 'else', 'for', 'while', 'class', 'extends', 'import', 'export', 'default', 'async', 'await', 'new', 'try', 'catch', 'throw', 'typeof', 'instanceof'],
    typescript: ['const', 'let', 'var', 'function', 'return', 'if', 'else', 'for', 'while', 'class', 'extends', 'import', 'export', 'default', 'async', 'await', 'new', 'try', 'catch', 'throw', 'typeof', 'instanceof', 'interface', 'type', 'enum', 'namespace', 'public', 'private', 'protected', 'readonly', 'static'],
    python: ['def', 'class', 'return', 'if', 'elif', 'else', 'for', 'while', 'import', 'from', 'as', 'try', 'except', 'finally', 'with', 'lambda', 'yield', 'async', 'await', 'raise', 'pass', 'break', 'continue', 'global', 'nonlocal'],
    rust: ['fn', 'let', 'mut', 'pub', 'struct', 'enum', 'impl', 'trait', 'use', 'mod', 'crate', 'self', 'super', 'async', 'await', 'return', 'if', 'else', 'match', 'for', 'while', 'loop', 'break', 'continue', 'unsafe', 'const', 'static', 'ref', 'move'],
    go: ['func', 'var', 'const', 'type', 'struct', 'interface', 'package', 'import', 'return', 'if', 'else', 'for', 'range', 'switch', 'case', 'default', 'defer', 'go', 'chan', 'select', 'break', 'continue'],
  };

  const langKeywords = keywords[language.toLowerCase()] || keywords.typescript;
  const lines = code.split('\n');

  return lines.map((line, lineIdx) => {
    // Tokenize the line
    const tokens: React.ReactNode[] = [];
    let remaining = line;
    let tokenIdx = 0;

    while (remaining.length > 0) {
      // Match strings
      const strMatch = remaining.match(/^["'`][^"'`]*["'`]/);
      if (strMatch) {
        tokens.push(
          <span key={`${lineIdx}-${tokenIdx++}`} className="text-emerald-400">
            {strMatch[0]}
          </span>
        );
        remaining = remaining.slice(strMatch[0].length);
        continue;
      }

      // Match comments
      const commentMatch = remaining.match(/^(\/\/|#|\/\*|\*\/).*$/);
      if (commentMatch) {
        tokens.push(
          <span key={`${lineIdx}-${tokenIdx++}`} className="text-muted/60 italic">
            {commentMatch[0]}
          </span>
        );
        remaining = '';
        continue;
      }

      // Match numbers
      const numMatch = remaining.match(/^\d+\.?\d*/);
      if (numMatch) {
        tokens.push(
          <span key={`${lineIdx}-${tokenIdx++}`} className="text-amber-400">
            {numMatch[0]}
          </span>
        );
        remaining = remaining.slice(numMatch[0].length);
        continue;
      }

      // Match keywords
      let matched = false;
      for (const kw of langKeywords) {
        if (remaining.startsWith(kw)) {
          const after = remaining[kw.length];
          if (!after || /[\s\W]/.test(after)) {
            tokens.push(
              <span key={`${lineIdx}-${tokenIdx++}`} className="text-purple-400 font-medium">
                {kw}
              </span>
            );
            remaining = remaining.slice(kw.length);
            matched = true;
            break;
          }
        }
      }
      if (matched) continue;

      // Match function calls
      const fnMatch = remaining.match(/^([a-zA-Z_][a-zA-Z0-9_]*)\s*\(/);
      if (fnMatch) {
        tokens.push(
          <span key={`${lineIdx}-${tokenIdx++}`} className="text-blue-400">
            {fnMatch[1]}
          </span>
        );
        tokens.push('(');
        remaining = remaining.slice(fnMatch[1].length + 1);
        continue;
      }

      // Regular character
      tokens.push(<span key={`${lineIdx}-${tokenIdx++}`}>{remaining[0]}</span>);
      remaining = remaining.slice(1);
    }

    return (
      <div key={lineIdx} className="table-row">
        <span className="table-cell pr-4 text-right text-muted/30 select-none text-[11px] w-8">
          {lineIdx + 1}
        </span>
        <span className="table-cell whitespace-pre-wrap break-all">
          {tokens}
        </span>
      </div>
    );
  });
}

// ── CodeBlock Component ──────────────────────────────────────────────────
export const EnhancedCodeBlock = memo(function EnhancedCodeBlock({
  language,
  code,
  filename,
}: CodeBlockProps) {
  const [copied, setCopied] = useState(false);
  const [collapsed, setCollapsed] = useState(code.split('\n').length > 20);
  const isLong = code.split('\n').length > 20;

  const handleCopy = () => {
    navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const displayCode = collapsed ? code.split('\n').slice(0, 15).join('\n') + '\n...' : code;

  return (
    <div className="my-3 rounded-lg overflow-hidden border border-border/50 bg-background/50">
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-1.5 bg-surface/60 border-b border-border/50">
        <div className="flex items-center gap-2">
          {filename && (
            <span className="text-[10px] text-muted/80">{filename}</span>
          )}
          <span className="text-[10px] font-medium text-muted uppercase tracking-wider">
            {language || 'code'}
          </span>
          <span className="text-[10px] text-muted/50">
            {code.split('\n').length} lines
          </span>
        </div>
        <div className="flex items-center gap-2">
          {/* Collapse toggle */}
          {isLong && (
            <button
              onClick={() => setCollapsed(!collapsed)}
              className="flex items-center gap-1 text-[10px] text-muted hover:text-foreground transition-colors"
              title={collapsed ? 'Expand' : 'Collapse'}
            >
              <svg className={`h-3 w-3 transition-transform ${collapsed ? '' : 'rotate-180'}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
              </svg>
              {collapsed ? 'Expand' : 'Collapse'}
            </button>
          )}
          {/* Copy button */}
          <button
            onClick={handleCopy}
            className="flex items-center gap-1 text-[10px] text-muted hover:text-foreground transition-colors"
            title="Copy to clipboard"
          >
            <AnimatePresence mode="wait">
              {copied ? (
                <motion.span
                  key="copied"
                  initial={{ opacity: 0, scale: 0.8 }}
                  animate={{ opacity: 1, scale: 1 }}
                  exit={{ opacity: 0, scale: 0.8 }}
                  className="flex items-center gap-1 text-emerald-400"
                >
                  <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                  </svg>
                  Copied!
                </motion.span>
              ) : (
                <motion.span
                  key="copy"
                  initial={{ opacity: 0, scale: 0.8 }}
                  animate={{ opacity: 1, scale: 1 }}
                  exit={{ opacity: 0, scale: 0.8 }}
                  className="flex items-center gap-1"
                >
                  <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
                  </svg>
                  Copy
                </motion.span>
              )}
            </AnimatePresence>
          </button>
        </div>
      </div>

      {/* Code content */}
      <div className="p-3 overflow-x-auto">
        <div className="table w-full text-xs">
          {highlightCode(displayCode, language)}
        </div>
      </div>

      {/* Expand overlay */}
      {collapsed && isLong && (
        <div className="relative">
          <button
            onClick={() => setCollapsed(false)}
            className="w-full py-1.5 text-center text-[10px] text-primary-400 hover:text-primary-300 hover:bg-primary/10 transition-colors"
          >
            Show {code.split('\n').length - 15} more lines...
          </button>
        </div>
      )}
    </div>
  );
});

export default EnhancedCodeBlock;
