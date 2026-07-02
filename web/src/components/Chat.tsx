'use client';

import { memo, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { useVirtualizer } from '@tanstack/react-virtual';
import { motion, AnimatePresence } from 'framer-motion';
import type { Message } from '@/lib/store';
import { useAppStore } from '@/lib/store';
import { ToolCallCard } from '@/components/ToolCallCard';
import {
  AgentActivity,
  extractActivities,
  type ActivityEntry,
} from '@/components/AgentActivity';

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
          Reasoning
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

  const handleCopy = useCallback(() => {
    navigator.clipboard.writeText(code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }, [code]);

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
        <motion.button
          whileHover={{ scale: 1.05 }}
          whileTap={{ scale: 0.95 }}
          onClick={handleCopy}
          className="flex items-center gap-1 text-[10px] text-muted hover:text-foreground transition-colors"
          title="Copy to clipboard"
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
          {copied ? 'Copied!' : 'Copy'}
        </motion.button>
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
  // Parse content for special patterns
  const lines = content.split('\n');
  const elements: React.ReactNode[] = [];
  let inCodeBlock = false;
  let codeLanguage = '';
  let codeContent = '';
  let key = 0;

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];

    // Check for code block start/end
    if (line.startsWith('```')) {
      if (!inCodeBlock) {
        // Start of code block
        inCodeBlock = true;
        codeLanguage = line.slice(3).trim();
        codeContent = '';
      } else {
        // End of code block
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

    // Parse inline patterns
    let parsedLine = line;
    const parts: React.ReactNode[] = [];
    let lastIndex = 0;

    // Find @file references
    const mentionRegex = /@\[([^\]]+)\]\(([^)]+)\)/g;
    let match;
    while ((match = mentionRegex.exec(line)) !== null) {
      // Add text before mention
      if (match.index > lastIndex) {
        parts.push(line.substring(lastIndex, match.index));
      }

      // Add file reference card
      const filePath = match[2];
      parts.push(
        <FileReferenceCard key={key++} filePath={filePath} />
      );

      lastIndex = match.index + match[0].length;
    }

    // Add remaining text
    if (lastIndex < line.length) {
      parts.push(line.substring(lastIndex));
    }

    // If no mentions found, just add the line as-is
    if (parts.length === 0) {
      parts.push(line);
    }

    elements.push(
      <div key={key++} className="min-h-[1em]">
        {parts}
      </div>
    );
  }

  // Handle unclosed code block
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
const MessageBubble = memo(function MessageBubble({
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
const ActivityGroup = memo(function ActivityGroup({
  messages,
}: {
  messages: Message[];
}) {
  const activities = useMemo(
    () => extractActivities(messages),
    [messages]
  );
  return <AgentActivity activities={activities} />;
});

// ── ChatMessages (virtualized) ──────────────────────────────────────────
interface ChatMessagesProps {
  scrollRef: React.RefObject<HTMLDivElement | null>;
}

export const ChatMessages = memo(function ChatMessages({
  scrollRef,
}: ChatMessagesProps) {
  const messages = useAppStore((s) => s.messages);

  // Pre-process: group consecutive tool messages into activity blocks
  const groupedItems = useMemo(() => {
    const items: Array<
      | { type: 'message'; msg: Message }
      | { type: 'activity'; messages: Message[] }
    > = [];
    let toolBuffer: Message[] = [];

    for (const msg of messages) {
      if (
        msg.eventType === 'tool_call' ||
        msg.eventType === 'tool_dispatch' ||
        msg.eventType === 'tool_result'
      ) {
        toolBuffer.push(msg);
      } else {
        if (toolBuffer.length > 0) {
          items.push({ type: 'activity', messages: [...toolBuffer] });
          toolBuffer = [];
        }
        items.push({ type: 'message', msg });
      }
    }
    if (toolBuffer.length > 0) {
      items.push({ type: 'activity', messages: toolBuffer });
    }
    return items;
  }, [messages]);

  const estimateSize = useCallback(() => 80, []);

  const prevLengthRef = useRef(groupedItems.length);

  const virtualizer = useVirtualizer({
    count: groupedItems.length,
    getScrollElement: () => scrollRef.current,
    estimateSize,
    overscan: 5,
  });

  // Auto-scroll to bottom on new items
  useEffect(() => {
    if (
      groupedItems.length > prevLengthRef.current &&
      scrollRef.current
    ) {
      const el = scrollRef.current;
      const isNearBottom =
        el.scrollHeight - el.scrollTop - el.clientHeight < 200;
      if (isNearBottom) {
        virtualizer.scrollToIndex(groupedItems.length - 1, {
          align: 'end',
        });
      }
    }
    prevLengthRef.current = groupedItems.length;
  }, [groupedItems.length, virtualizer, scrollRef]);

  if (groupedItems.length === 0) {
    return (
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        className="flex items-center justify-center h-full"
      >
        <div className="text-center text-muted">
          <motion.p
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
            className="text-lg"
          >
            What would you like to build?
          </motion.p>
          <motion.p
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
            className="text-sm mt-2"
          >
            Try: /plan then describe a refactor, or ask to fix failing tests
          </motion.p>
        </div>
      </motion.div>
    );
  }

  return (
    <div
      style={{
        height: `${virtualizer.getTotalSize()}px`,
        width: '100%',
        position: 'relative',
      }}
    >
      {virtualizer.getVirtualItems().map((virtualItem) => {
        const item = groupedItems[virtualItem.index];
        return (
          <div
            key={
              item.type === 'message'
                ? item.msg.id
                : `activity-${virtualItem.index}`
            }
            style={{
              position: 'absolute',
              top: 0,
              left: 0,
              width: '100%',
              transform: `translateY(${virtualItem.start}px)`,
            }}
            ref={virtualizer.measureElement}
            data-index={virtualItem.index}
          >
            <div className="px-1 py-1.5">
              {item.type === 'message' ? (
                <MessageBubble
                  msg={item.msg}
                  index={virtualItem.index}
                />
              ) : (
                <ActivityGroup messages={item.messages} />
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
});

// ── Legacy Chat (kept for compatibility) ────────────────────────────────
export function Chat() {
  const messages = useAppStore((s) => s.messages);

  return (
    <div className="space-y-4">
      <AnimatePresence>
        {messages.map((msg) => (
          <motion.div
            key={msg.id}
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            exit={{ opacity: 0, y: -10 }}
            transition={{ duration: 0.2 }}
          >
            <MessageBubble msg={msg} index={0} />
          </motion.div>
        ))}
      </AnimatePresence>
    </div>
  );
}
