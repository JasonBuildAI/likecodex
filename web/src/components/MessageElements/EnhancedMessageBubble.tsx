'use client';

import React, { memo, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import type { Message } from '@/lib/store';
import { GradientAvatar } from '@/components/GradientAvatar';
import { EnhancedCodeBlock } from './EnhancedCodeBlock';
import { TypingIndicator } from './TypingIndicator';
import { fadeInUp, scaleInBounce } from '@/lib/animations';

// ── FileReferenceCard ────────────────────────────────────────────────────
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
    <motion.span
      whileHover={{ scale: 1.05 }}
      className="inline-flex items-center gap-1.5 px-2 py-1 rounded-md bg-blue-500/10 border border-blue-500/20 text-blue-400 text-xs cursor-pointer hover:bg-blue-500/20 transition-colors"
    >
      <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" />
      </svg>
      <span className="font-medium">{fileName}</span>
      {dirPath && <span className="text-[10px] text-muted/60">{dirPath}</span>}
      {lineRange && (
        <span className="text-[10px] text-blue-400/70">:{lineRange[0]}-{lineRange[1]}</span>
      )}
    </motion.span>
  );
});

// ── MessageContent parser ────────────────────────────────────────────────
const MessageContent = memo(function MessageContent({ content }: { content: string }) {
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
          <EnhancedCodeBlock key={key++} language={codeLanguage} code={codeContent.trim()} />
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
    const parts: React.ReactNode[] = [];
    let lastIndex = 0;
    const mentionRegex = /@\[([^\]]+)\]\(([^)]+)\)/g;
    let match;
    while ((match = mentionRegex.exec(line)) !== null) {
      if (match.index > lastIndex) {
        parts.push(line.substring(lastIndex, match.index));
      }
      parts.push(<FileReferenceCard key={key++} filePath={match[2]} />);
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
      <EnhancedCodeBlock key={key++} language={codeLanguage} code={codeContent.trim()} />
    );
  }

  return <>{elements}</>;
});

// ── Hover Actions ────────────────────────────────────────────────────────
interface HoverActionsProps {
  onCopy: () => void;
  onRegenerate?: () => void;
}

const HoverActions = memo(function HoverActions({ onCopy, onRegenerate }: HoverActionsProps) {
  const [copied, setCopied] = useState(false);

  const handleCopy = () => {
    onCopy();
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="absolute -bottom-3 right-4 flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
      <motion.button
        whileHover={{ scale: 1.1 }}
        whileTap={{ scale: 0.9 }}
        onClick={handleCopy}
        className="flex items-center gap-1 px-2 py-1 rounded-md bg-surface border border-border text-[10px] text-muted hover:text-foreground shadow-md"
        title="Copy message"
      >
        {copied ? (
          <svg className="h-3 w-3 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
          </svg>
        ) : (
          <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z" />
          </svg>
        )}
      </motion.button>

      {onRegenerate && (
        <motion.button
          whileHover={{ scale: 1.1 }}
          whileTap={{ scale: 0.9 }}
          onClick={onRegenerate}
          className="flex items-center gap-1 px-2 py-1 rounded-md bg-surface border border-border text-[10px] text-muted hover:text-foreground shadow-md"
          title="Regenerate"
        >
          <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m8.336 0a5.002 5.002 0 00-9.536-1.392M20 20v-5h-.582m-8.336 0a5.002 5.002 0 009.536 1.392" />
          </svg>
        </motion.button>
      )}
    </div>
  );
});

// ── Enhanced MessageBubble ───────────────────────────────────────────────
interface MessageBubbleProps {
  msg: Message;
  onRegenerate?: () => void;
  isStreaming?: boolean;
}

export const EnhancedMessageBubble = memo(function EnhancedMessageBubble({
  msg,
  onRegenerate,
  isStreaming,
}: MessageBubbleProps) {
  const isUser = msg.role === 'user';
  const isAssistant = msg.role === 'assistant' || msg.role === 'system';
  const isEmpty = isStreaming && !msg.content;

  const handleCopy = () => {
    navigator.clipboard.writeText(msg.content);
  };

  return (
    <motion.div
      variants={fadeInUp}
      initial="hidden"
      animate="visible"
      className={`group relative ${isUser ? 'ml-10' : 'mr-4'}`}
    >
      {/* Avatar */}
      <div className={`absolute top-0 ${isUser ? '-left-10' : '-left-10'} flex items-start`}>
        {isUser ? (
          <div className="w-8 h-8 rounded-full bg-gradient-to-br from-blue-500 to-purple-600 flex items-center justify-center text-xs font-semibold text-white shadow-md">
            U
          </div>
        ) : (
          <GradientAvatar size="sm" animated={true} />
        )}
      </div>

      {/* Message content */}
      <div
        className={`rounded-2xl p-4 shadow-md backdrop-blur-sm transition-all hover:shadow-lg ${
          isUser
            ? 'bg-gradient-to-br from-blue-500/10 to-purple-500/10 border border-blue-500/20'
            : 'bg-surface/80 border border-border/50'
        }`}
      >
        {/* Header row */}
        <div className="flex items-center justify-between mb-2">
          <div className="flex items-center gap-2">
            <span className={`text-[10px] font-semibold uppercase tracking-wider ${
              isUser ? 'text-blue-400' : 'text-emerald-400'
            }`}>
              {isUser ? 'You' : 'Agent'}
            </span>
            <span className="text-[10px] text-muted/50">
              {new Date(msg.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}
            </span>
          </div>

          {/* Feedback buttons (assistant only) */}
          {isAssistant && !isStreaming && (
            <div className="flex items-center gap-1 opacity-0 group-hover:opacity-100 transition-opacity">
              <button className="p-1 rounded hover:bg-accent/10 text-muted hover:text-foreground" title="Good response">
                <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14 10h4.764a2 2 0 011.789 2.894l-3.5 7A2 2 0 0115.265 21H6a2 2 0 01-2-2V11a2 2 0 012-2h4.5m0 0L12 2m-1.5 7h3" transform="rotate(180 12 12)" />
                </svg>
              </button>
              <button className="p-1 rounded hover:bg-accent/10 text-muted hover:text-foreground" title="Poor response">
                <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M14 10h4.764a2 2 0 011.789 2.894l-3.5 7A2 2 0 0115.265 21H6a2 2 0 01-2-2V11a2 2 0 012-2h4.5m0 0L12 2m-1.5 7h3" />
                </svg>
              </button>
            </div>
          )}
        </div>

        {/* Content */}
        {isEmpty ? (
          <TypingIndicator />
        ) : (
          msg.content && (
            <div className="text-sm leading-relaxed whitespace-pre-wrap break-words">
              <MessageContent content={msg.content} />
            </div>
          )
        )}

        {/* Reasoning content */}
        {msg.reasoningContent && (
          <div className="mt-3 p-3 rounded-lg bg-amber-500/5 border border-amber-500/20">
            <div className="flex items-center gap-1.5 text-xs text-amber-400 mb-1">
              <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
              </svg>
              <span className="font-medium">Reasoning</span>
            </div>
            <div className="text-xs text-amber-200/60 whitespace-pre-wrap max-h-64 overflow-y-auto">
              {msg.reasoningContent}
            </div>
          </div>
        )}
      </div>

      {/* Hover actions */}
      {!isStreaming && (
        <HoverActions onCopy={handleCopy} onRegenerate={isAssistant ? onRegenerate : undefined} />
      )}
    </motion.div>
  );
});

export default EnhancedMessageBubble;
