'use client';

import { memo, useCallback, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import type { Message } from '@/lib/store';
import { useAppStore } from '@/lib/store';
import { ToolCallCard } from '@/components/ToolCallCard';
import {
  AgentActivity,
  extractActivities,
  type ActivityEntry,
} from '@/components/AgentActivity';
import i18n from '@/lib/i18n';

// ── ReasoningBlock ──────────────────────────────────────────────────────
const ReasoningBlock = memo(function ReasoningBlock({
  content,
}: {
  content: string;
}) {
  const [isExpanded, setIsExpanded] = useState(false);
  const tokens = content.split(' ').length;

  return (
    <motion.div
      initial={{ opacity: 0, y: -5 }}
      animate={{ opacity: 1, y: 0 }}
      className="rounded-lg border border-amber-500/30 bg-gradient-to-r from-amber-500/10 to-amber-500/5 overflow-hidden shadow-sm"
    >
      <button
        onClick={() => setIsExpanded(!isExpanded)}
        className="flex w-full items-center justify-between px-3 py-2 text-left text-xs font-medium text-amber-600 dark:text-amber-400 hover:bg-amber-500/10 transition-all-smooth"
      >
        <span className="flex items-center gap-1.5">
          <svg
            className="h-3.5 w-3.5"
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z"
            />
          </svg>
          {i18n.t('chat.thinking')}
          <span className="text-[9px] text-amber-400/60 ml-1">
            (~{tokens} tokens)
          </span>
        </span>
        <div className="flex items-center gap-2">
          <span className="text-[9px] text-amber-400/60">
            {isExpanded ? 'Click to collapse' : 'Click to expand'}
          </span>
          <svg
            className={`h-3 w-3 transition-transform duration-200 ${
              isExpanded ? 'rotate-180' : ''
            }`}
            fill="none"
            viewBox="0 0 24 24"
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth={2}
              d="M19 9l-7 7-7-7"
            />
          </svg>
        </div>
      </button>
      <AnimatePresence>
        {isExpanded && (
          <motion.div
            initial={{ height: 0, opacity: 0 }}
            animate={{ height: 'auto', opacity: 1 }}
            exit={{ height: 0, opacity: 0 }}
            transition={{ duration: 0.2, ease: 'easeInOut' }}
            className="overflow-hidden"
          >
            <div className="border-t border-amber-500/20 px-3 py-2 text-xs text-amber-800 dark:text-amber-200/80 whitespace-pre-wrap max-h-64 overflow-y-auto leading-relaxed">
              {content}
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  );
});

// ── FileReferenceCard ───────────────────────────────────────────────────
const FileReferenceCard = memo(function FileReferenceCard({
  filePath,
  lineRange,
}: {
  filePath: string;
  lineRange?: [number, number];
}) {
  const fileName = filePath.split('/').pop() || filePath;
  const dirPath = filePath.substring(0, filePath.lastIndexOf('/'));

  return (
    <motion.div
      whileHover={{ scale: 1.02 }}
      whileTap={{ scale: 0.98 }}
      className="inline-flex items-center gap-1.5 px-2 py-1 rounded-md bg-blue-500/10 border border-blue-500/20 text-blue-400 text-xs cursor-pointer hover:bg-blue-500/20 transition-all-smooth"
    >
      <svg
        className="h-3 w-3"
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={2}
          d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z"
        />
      </svg>
      <span className="font-medium">{fileName}</span>
      {lineRange && (
        <span className="text-[10px] text-blue-400/70">
          :{lineRange[0]}-{lineRange[1]}
        </span>
      )}
    </motion.div>
  );
});

// ── CodeBlock ───────────────────────────────────────────────────────────
const CodeBlock = memo(function CodeBlock({
  language,
  code,
}: {
  language: string;
  code: string;
}) {
  const [copied, setCopied] = useState(false);
  const addToast = useAppStore((s) => s.addToast);
  const openFiles = useAppStore((s) => s.openFiles);
  const activeFilePath = useAppStore((s) => s.activeFilePath);
  const updateFileContent = useAppStore((s) => s.updateFileContent);
  const openFile = useAppStore((s) => s.openFile);
  const setActiveFile = useAppStore((s) => s.setActiveFile);

  const handleCopy = useCallback(() => {
    navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
    addToast({ type: 'info', message: i18n.t('chat.copyDone') });
  }, [code, addToast]);

  const handleInsertAtCursor = useCallback(() => {
    if (activeFilePath) {
      const activeFile = openFiles.find(f => f.path === activeFilePath);
      if (activeFile) {
        updateFileContent(activeFilePath, activeFile.content + '\n' + code);
        addToast({ type: 'success', message: 'Code appended to ' + activeFilePath.split('/').pop() });
      }
    } else {
      addToast({ type: 'info', message: 'Open a file first to insert code' });
    }
  }, [activeFilePath, openFiles, updateFileContent, code, addToast]);

  const handleInsertNewFile = useCallback(() => {
    const ext = language === 'typescript' ? 'ts' : language === 'javascript' ? 'js' : language === 'python' ? 'py' : language === 'rust' ? 'rs' : language === 'go' ? 'go' : language;
    const name = `snippet-${Date.now()}.${ext}`;
    const path = `/tmp/${name}`;
    openFile({ name, path, content: code, language, modified: true });
    setActiveFile(path);
    addToast({ type: 'success', message: `Opened as ${name}` });
  }, [language, code, openFile, setActiveFile, addToast]);

  return (
    <motion.div
      initial={{ opacity: 0, y: 5 }}
      animate={{ opacity: 1, y: 0 }}
      className="my-3 rounded-lg overflow-hidden border border-border/50"
    >
      {/* Header */}
      <div className="flex items-center justify-between px-3 py-1.5 bg-surface/60 border-b border-border/50">
        <span className="text-[10px] font-medium text-muted uppercase tracking-wider">
          {language || 'code'}
        </span>
        <div className="flex items-center gap-1">
          {/* Insert at active editor */}
          <motion.button
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            onClick={handleInsertAtCursor}
            className="flex items-center gap-1 text-[10px] text-muted hover:text-foreground transition-colors px-1.5 py-0.5 rounded hover:bg-accent/10"
            title="Append to active file"
          >
            <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.232 5.232l3.536 3.536m-2.036-5.036a2.5 2.5 0 113.536 3.536L6.5 21.036H3v-3.572L16.732 3.732z" />
            </svg>
            <span>Insert</span>
          </motion.button>
          {/* Open as new file */}
          <motion.button
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            onClick={handleInsertNewFile}
            className="flex items-center gap-1 text-[10px] text-muted hover:text-foreground transition-colors px-1.5 py-0.5 rounded hover:bg-accent/10"
            title="Open as new file in editor"
          >
            <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
            </svg>
            <span>{i18n.t('common.save')}</span>
          </motion.button>
          {/* Copy */}
          <motion.button
            whileHover={{ scale: 1.05 }}
            whileTap={{ scale: 0.95 }}
            onClick={handleCopy}
            className="flex items-center gap-1 text-[10px] text-muted hover:text-foreground transition-colors"
            title={i18n.t('chat.copy')}
          >
            {copied ? (
              <svg
                className="h-3 w-3 text-green-400"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M5 13l4 4L19 7"
                />
              </svg>
            ) : (
              <svg
                className="h-3 w-3"
                fill="none"
                viewBox="0 0 24 24"
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  strokeWidth={2}
                  d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"
                />
              </svg>
            )}
            {copied ? i18n.t('chat.copyDone') : i18n.t('chat.copy')}
          </motion.button>
        </div>
      </div>
      {/* Code content */}
      <pre className="p-3 bg-background/50 overflow-x-auto">
        <code className="text-xs text-foreground whitespace-pre-wrap break-all font-mono">
          {code}
        </code>
      </pre>
    </motion.div>
  );
});

// ── MessageContent ──────────────────────────────────────────────────────
const MessageContent = memo(function MessageContent({
  content,
}: {
  content: string;
}) {
  const lines = content.split('\n');
  const elements: React.ReactNode[] = [];
  let inCodeBlock = false;
  let codeLanguage = '';
  let codeContent = '';
  let key = 0;

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];

    if (line.startsWith('```')) {
      if (!inCodeBlock) {
        inCodeBlock = true;
        codeLanguage = line.slice(3).trim();
        codeContent = '';
      } else {
        inCodeBlock = false;
        elements.push(
          <CodeBlock
            key={key++}
            language={codeLanguage}
            code={codeContent.trim()}
          />
        );
        codeLanguage = '';
        codeContent = '';
      }
      continue;
    }

    if (inCodeBlock) {
      codeContent += line + '\n';
      continue;
    }

    let parsedLine = line;
    const parts: React.ReactNode[] = [];
    let lastIndex = 0;

    const mentionRegex = /@\[([^\]]+)\]\(([^)]+)\)/g;
    let match;
    while ((match = mentionRegex.exec(line)) !== null) {
      if (match.index > lastIndex) {
        parts.push(line.substring(lastIndex, match.index));
      }

      const filePath = match[2];
      const lineRangeMatch = filePath.match(/:(\d+)-(\d+)$/);
      if (lineRangeMatch) {
        const basePath = filePath.replace(/:(\d+)-(\d+)$/, '');
        parts.push(
          <FileReferenceCard
            key={key++}
            filePath={basePath}
            lineRange={[parseInt(lineRangeMatch[1]), parseInt(lineRangeMatch[2])]}
          />
        );
      } else {
        parts.push(
          <FileReferenceCard key={key++} filePath={filePath} />
        );
      }

      lastIndex = match.index + match[0].length;
    }

    if (lastIndex < line.length) {
      parts.push(line.substring(lastIndex));
    }

    if (parts.length === 0) {
      parts.push(line);
    }

    elements.push(
      <div key={key++} className="min-h-[1em]">
        {parts}
      </div>
    );
  }

  if (inCodeBlock && codeContent) {
    elements.push(
      <CodeBlock
        key={key++}
        language={codeLanguage}
        code={codeContent.trim()}
      />
    );
  }

  return <>{elements}</>;
});

// ── MessageBubble ───────────────────────────────────────────────────────
export const MessageBubble = memo(function MessageBubble({
  msg,
  index,
}: {
  msg: Message;
  index: number;
}) {
  const isUser = msg.role === 'user';
  const isAssistant = msg.role === 'assistant' || msg.role === 'system';

  return (
    <motion.div
      initial={{ opacity: 0, y: 20, scale: 0.98 }}
      animate={{ opacity: 1, y: 0, scale: 1 }}
      transition={{
        duration: 0.3,
        ease: [0.4, 0, 0.2, 1],
        delay: Math.min(index * 0.03, 0.15),
      }}
      className={`group relative ${isUser ? 'ml-8' : 'mr-4'}`}
    >
      {/* Avatar */}
      <div
        className={`absolute top-0 ${
          isUser ? '-left-8' : '-right-8'
        } flex items-start`}
      >
        <motion.div
          initial={{ scale: 0 }}
          animate={{ scale: 1 }}
          transition={{ type: 'spring', stiffness: 300, damping: 20 }}
          className={`w-7 h-7 rounded-full flex items-center justify-center text-xs font-semibold shadow-md ${
            isUser
              ? 'bg-gradient-to-br from-blue-500 to-purple-600 text-white'
              : 'bg-gradient-to-br from-emerald-500 to-teal-600 text-white'
          }`}
        >
          {isUser ? 'U' : 'AI'}
        </motion.div>
      </div>

      {/* Reasoning content - above the bubble */}
      {!isUser && msg.reasoningContent && (
        <div className="mb-2">
          <ReasoningBlock content={msg.reasoningContent} />
        </div>
      )}

      {/* Message content */}
      <motion.div
        whileHover={{ scale: 1.002 }}
        className={`rounded-2xl p-4 shadow-md backdrop-blur-sm transition-all-smooth hover:shadow-lg ${
          isUser
            ? 'bg-gradient-to-br from-blue-500/10 to-purple-500/10 border border-blue-500/20'
            : 'bg-surface/80 border border-border/50'
        }`}
      >
        {/* Role label */}
        <div className="flex items-center gap-2 mb-2">
          <span
            className={`text-[10px] font-semibold uppercase tracking-wider ${
              isUser ? 'text-blue-400' : 'text-emerald-400'
            }`}
          >
            {isUser ? 'You' : msg.role}
          </span>
          <span className="text-[10px] text-muted/50">
            {new Date(msg.timestamp).toLocaleTimeString([], {
              hour: '2-digit',
              minute: '2-digit',
            })}
          </span>
        </div>

        {/* Content */}
        {msg.content && (
          <div className="text-sm leading-relaxed whitespace-pre-wrap break-words">
            <MessageContent content={msg.content} />
          </div>
        )}

        {/* Tool calls */}
        {msg.toolCalls?.map((call) => (
          <div key={call.id || call.name} className="mt-3">
            <ToolCallCard call={call} />
          </div>
        ))}
      </motion.div>
    </motion.div>
  );
});

// ── ActivityGroup ───────────────────────────────────────────────────────
export const ActivityGroup = memo(function ActivityGroup({
  messages,
}: {
  messages: Message[];
}) {
  const activities: ActivityEntry[] = [];
  const resultMap = new Map<string, string>();

  for (const msg of messages) {
    if (msg.eventType === 'tool_result' && msg.toolCalls?.[0]) {
      const key = msg.toolCalls[0].id || msg.toolCalls[0].name;
      resultMap.set(key, msg.content);
    }
  }

  for (const msg of messages) {
    if ((msg.eventType === 'tool_call' || msg.eventType === 'tool_dispatch') && msg.toolCalls?.[0]) {
      const call = msg.toolCalls[0];
      const key = call.id || call.name;
      const isRunning = msg.eventType === 'tool_dispatch' || call.arguments?.partial === true;
      activities.push({
        call,
        isRunning,
        result: resultMap.get(key),
      });
    }
  }

  return <AgentActivity activities={activities} />;
});
