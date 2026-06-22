'use client';

/**
 * ComposerPanel — Multi-file AI editing panel.
 *
 * Layout:
 * - Header with status indicator
 * - Message history (user + assistant messages)
 * - File change tabs + Diff preview
 * - Accept/Reject buttons
 * - Input area with @ mention support
 */

import { useState, useRef, useEffect, useCallback } from 'react';
import { DiffViewer } from '@/components/DiffViewer';
import { useComposerStore, type FileChange } from './composerStore';
import type { ContextMention } from '@/ide/context/types';
import { MentionPicker } from '@/ide/context/MentionPicker';
import { fetchContextMentions } from '@/lib/api';

export function ComposerPanel() {
  const {
    isOpen,
    messages,
    status,
    streamingContent,
    fileChanges,
    activeChangePath,
    error,
    toggleComposer,
    sendMessage,
    cancelStream,
    acceptChange,
    rejectChange,
    acceptAll,
    rejectAll,
    setActiveChange,
    clearComposer,
  } = useComposerStore();

  const [input, setInput] = useState('');
  const [showMentions, setShowMentions] = useState(false);
  const [mentionQuery, setMentionQuery] = useState('');
  const [mentionPos, setMentionPos] = useState({ top: 0, left: 0 });
  const [mentions, setMentions] = useState<ContextMention[]>([]);
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const scrollRef = useRef<HTMLDivElement>(null);

  // Auto-scroll on new messages
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages, streamingContent]);

  // Cmd+I shortcut
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'i') {
        e.preventDefault();
        toggleComposer();
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [toggleComposer]);

  const handleInputChange = useCallback(
    (e: React.ChangeEvent<HTMLTextAreaElement>) => {
      const value = e.target.value;
      setInput(value);

      // @ mention detection
      const cursor = e.target.selectionStart;
      const beforeCursor = value.slice(0, cursor);
      const atIndex = beforeCursor.lastIndexOf('@');

      if (
        atIndex !== -1 &&
        (atIndex === 0 || beforeCursor[atIndex - 1] === ' ' || beforeCursor[atIndex - 1] === '\n')
      ) {
        const query = beforeCursor.slice(atIndex + 1);
        if (!query.includes(' ') && !query.includes('\n') && query.length <= 50) {
          setShowMentions(true);
          setMentionQuery(query);

          // Calculate position
          const textarea = e.target;
          const rect = textarea.getBoundingClientRect();
          setMentionPos({
            top: rect.top + 40,
            left: rect.left + 20,
          });
          return;
        }
      }
      setShowMentions(false);
    },
    []
  );

  const handleMentionSelect = useCallback((mention: ContextMention) => {
    const textarea = textareaRef.current;
    if (!textarea) return;

    const cursor = textarea.selectionStart;
    const beforeCursor = input.slice(0, cursor);
    const atIndex = beforeCursor.lastIndexOf('@');
    if (atIndex === -1) return;

    const afterCursor = input.slice(cursor);
    const tag = `@[${mention.label}](${mention.id}) `;
    const newValue = beforeCursor.slice(0, atIndex) + tag + afterCursor;

    setInput(newValue);
    setShowMentions(false);

    const newCursor = atIndex + tag.length;
    setTimeout(() => {
      textarea.focus();
      textarea.setSelectionRange(newCursor, newCursor);
    }, 0);
  }, [input]);

  const handleSubmit = useCallback(() => {
    if (!input.trim() || status === 'planning' || status === 'executing') return;

    // Parse @ mentions from input
    const mentionRegex = /@\[([^\]]+)\]\(([^)]+)\)/g;
    const parsedMentions: ContextMention[] = [];
    let match;
    while ((match = mentionRegex.exec(input)) !== null) {
      parsedMentions.push({
        id: match[2],
        type: 'file',
        label: match[1],
        icon: '',
        content: '',
        tokenEstimate: 0,
        relevanceScore: 0,
      });
    }

    // Strip @ mention tags for display
    const cleanInput = input.replace(/@\[([^\]]+)\]\(([^)]+)\)/g, '@$1');

    sendMessage(cleanInput, parsedMentions);
    setInput('');
  }, [input, status, sendMessage]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'Enter') {
        e.preventDefault();
        handleSubmit();
      }
    },
    [handleSubmit]
  );

  if (!isOpen) return null;

  const statusText =
    status === 'planning' ? 'AI 正在分析...' :
    status === 'awaiting_approval' ? '等待确认' :
    status === 'executing' ? '正在修改...' :
    status === 'done' ? '修改完成' :
    status === 'error' ? '出错' : '就绪';

  const statusColor =
    status === 'planning' || status === 'executing' ? 'text-yellow-400' :
    status === 'done' ? 'text-green-400' :
    status === 'error' ? 'text-red-400' : 'text-gray-400';

  const changesArray = Array.from(fileChanges.entries());
  const activeChange = activeChangePath ? fileChanges.get(activeChangePath) : null;
  const acceptedCount = Array.from(fileChanges.values()).filter((c) => c.accepted === true).length;
  const pendingCount = Array.from(fileChanges.values()).filter((c) => c.accepted === null).length;

  return (
    <div className="w-[560px] h-full bg-[#1a1a2e] border-l border-gray-700 flex flex-col">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-gray-700 shrink-0">
        <div className="flex items-center gap-2">
          <h2 className="text-sm font-semibold text-white">Composer</h2>
          <span className={`text-xs ${statusColor}`}>{statusText}</span>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={clearComposer}
            className="text-xs text-gray-400 hover:text-white px-2 py-0.5 rounded hover:bg-gray-700"
            title="清除对话"
          >
            Clear
          </button>
          <button
            onClick={toggleComposer}
            className="text-gray-400 hover:text-white text-lg leading-none px-1"
            title="关闭 (Cmd+I)"
          >
            ×
          </button>
        </div>
      </div>

      {/* Message History */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto p-3 space-y-3 min-h-0">
        {messages.length === 0 && !streamingContent && (
          <div className="text-center text-gray-500 text-sm py-8">
            描述你想要的修改，AI 将自动编辑多个文件。
            <br />
            使用 <span className="text-blue-400">@</span> 引用文件。
          </div>
        )}

        {messages.map((msg) => (
          <div
            key={msg.id}
            className={`p-2.5 rounded-lg text-sm ${
              msg.role === 'user'
                ? 'bg-blue-900/30 ml-8 border border-blue-800/50'
                : 'bg-gray-800/80 mr-4 border border-gray-700'
            }`}
          >
            <div className="text-xs text-gray-500 mb-1">
              {msg.role === 'user' ? 'You' : 'AI'}
            </div>
            <div className="text-gray-200 whitespace-pre-wrap">{msg.content}</div>
            {msg.fileChanges && msg.fileChanges.length > 0 && (
              <div className="mt-2 flex flex-wrap gap-1">
                {msg.fileChanges.map((p) => (
                  <span key={p} className="text-[10px] px-1.5 py-0.5 bg-gray-700 rounded text-gray-300">
                    {p.split('/').pop()}
                  </span>
                ))}
              </div>
            )}
          </div>
        ))}

        {/* Streaming content */}
        {streamingContent && (
          <div className="p-2.5 rounded-lg text-sm bg-gray-800/80 mr-4 border border-gray-700">
            <div className="text-xs text-gray-500 mb-1">AI (typing...)</div>
            <div className="text-gray-200 whitespace-pre-wrap">{streamingContent}</div>
          </div>
        )}

        {/* Error display */}
        {error && (
          <div className="p-2.5 rounded-lg text-sm bg-red-900/30 border border-red-800/50 text-red-300">
            Error: {error}
          </div>
        )}

        {/* File Changes Preview */}
        {changesArray.length > 0 && (
          <div className="border border-gray-700 rounded-lg overflow-hidden mt-3">
            {/* File tabs */}
            <div className="flex border-b border-gray-700 overflow-x-auto bg-gray-800/50">
              {changesArray.map(([path, change]) => (
                <button
                  key={path}
                  onClick={() => setActiveChange(path)}
                  className={`px-3 py-1.5 text-xs whitespace-nowrap border-r border-gray-700 transition-colors ${
                    activeChangePath === path ? 'bg-gray-700 text-white' : 'text-gray-400 hover:text-gray-200'
                  } ${
                    change.accepted === true
                      ? 'border-b-2 border-b-green-500'
                      : change.accepted === false
                        ? 'border-b-2 border-b-red-500 opacity-60'
                        : ''
                  }`}
                >
                  <span className="mr-1">
                    {change.changeType === 'create' ? '+' : change.changeType === 'delete' ? '-' : '~'}
                  </span>
                  {path.split('/').pop()}
                </button>
              ))}
            </div>

            {/* Diff content */}
            <div className="h-[280px] bg-[#1e1e2e]">
              {activeChange && (
                <DiffViewer
                  oldText={activeChange.originalContent}
                  newText={activeChange.modifiedContent}
                  language={activeChange.language}
                  title={activeChange.filePath}
                  onAccept={
                    activeChange.accepted === null
                      ? () => acceptChange(activeChange.filePath)
                      : undefined
                  }
                  onReject={
                    activeChange.accepted === null
                      ? () => rejectChange(activeChange.filePath)
                      : undefined
                  }
                />
              )}
            </div>

            {/* Action bar */}
            <div className="flex items-center justify-between px-3 py-2 border-t border-gray-700 bg-gray-800/50">
              <div className="flex gap-2">
                {pendingCount > 0 && (
                  <>
                    <button
                      onClick={() => acceptAll()}
                      className="px-3 py-1 bg-green-600 text-white text-xs rounded hover:bg-green-700 transition-colors"
                    >
                      全部接受 ({pendingCount})
                    </button>
                    <button
                      onClick={() => rejectAll()}
                      className="px-3 py-1 bg-gray-600 text-white text-xs rounded hover:bg-gray-700 transition-colors"
                    >
                      全部拒绝
                    </button>
                  </>
                )}
              </div>
              <span className="text-xs text-gray-500">
                {acceptedCount} / {fileChanges.size} 已接受
              </span>
            </div>
          </div>
        )}
      </div>

      {/* Input Area */}
      <div className="border-t border-gray-700 p-3 shrink-0 relative">
        <div className="flex gap-2">
          <textarea
            ref={textareaRef}
            value={input}
            onChange={handleInputChange}
            onKeyDown={handleKeyDown}
            placeholder="描述修改需求... (@ 引用文件, Cmd+Enter 发送)"
            rows={2}
            className="flex-1 bg-gray-800 text-gray-200 text-sm rounded-lg px-3 py-2 border border-gray-700 focus:border-blue-500 focus:outline-none resize-none placeholder-gray-500"
            disabled={status === 'planning' || status === 'executing'}
          />
        </div>
        <div className="flex items-center justify-between mt-2">
          <span className="text-[10px] text-gray-600">
            {input.length > 0 && `${input.length} chars`}
          </span>
          <div className="flex gap-2">
            {(status === 'planning' || status === 'executing') && (
              <button
                onClick={cancelStream}
                className="px-3 py-1 bg-red-600/80 text-white text-xs rounded hover:bg-red-700 transition-colors"
              >
                停止
              </button>
            )}
            <button
              onClick={handleSubmit}
              disabled={!input.trim() || status === 'planning' || status === 'executing'}
              className="px-4 py-1 bg-blue-600 text-white text-xs rounded hover:bg-blue-700 transition-colors disabled:opacity-40 disabled:cursor-not-allowed"
            >
              发送 (⌘↵)
            </button>
          </div>
        </div>

        {/* Mention Picker */}
        {showMentions && (
          <MentionPicker
            triggerPosition={mentionPos}
            query={mentionQuery}
            onSelect={handleMentionSelect}
            onClose={() => setShowMentions(false)}
          />
        )}
      </div>
    </div>
  );
}
