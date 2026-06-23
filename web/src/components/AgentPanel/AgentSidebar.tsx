'use client';

import React, { useState } from 'react';
import { useAgentStore } from '@/store/agentStore';
import { ModeSelector } from './ModeSelector';
import { ConversationHistory } from './ConversationHistory';

// ── Main Agent Sidebar Component ───────────────────────────────────────
export const AgentPanelSidebar: React.FC = () => {
  const { currentMode, isSidebarOpen, toggleSidebar, createConversation } = useAgentStore();
  const [inputValue, setInputValue] = useState('');

  // 根据模式动态生成占位符文本
  const getPlaceholderText = () => {
    switch (currentMode) {
      case 'ask':
        return 'Ask questions without making changes...';
      case 'agent':
        return 'Describe what you want to build or fix...';
      case 'manual':
        return 'Enter commands (will require approval)...';
      default:
        return 'Type a message...';
    }
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputValue.trim()) return;

    // 创建新对话并发送消息
    createConversation(inputValue.slice(0, 40), currentMode);

    // TODO: 发送消息到后端
    console.log('Sending message:', inputValue);
    setInputValue('');
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSubmit(e);
    }
  };

  // 折叠状态：显示展开按钮
  if (!isSidebarOpen) {
    return (
      <button
        onClick={toggleSidebar}
        className="fixed left-0 top-1/2 -translate-y-1/2 z-50 p-2 bg-surface rounded-r-lg border border-border border-l-0 hover:bg-accent/10 transition-colors"
        title="Open Agent Panel"
      >
        <svg className="h-4 w-4 text-muted" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
        </svg>
      </button>
    );
  }

  return (
    <div className="flex flex-col h-full w-80 bg-surface border-r border-border shrink-0">
      {/* 头部：标题 + 折叠按钮 */}
      <div className="flex items-center justify-between px-3 py-2 border-b border-border">
        <div className="flex items-center gap-2">
          <svg className="h-4 w-4 text-primary" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
          </svg>
          <span className="text-xs font-semibold text-foreground">Agent Panel</span>
        </div>
        <button
          onClick={toggleSidebar}
          className="p-1 rounded hover:bg-accent/10 text-muted hover:text-foreground transition-colors"
          title="Collapse panel"
        >
          <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
        </button>
      </div>

      {/* 模式选择器 */}
      <ModeSelector />

      {/* 工作区选择器 */}
      <div className="px-3 py-2 border-b border-border">
        <select className="w-full bg-background text-foreground text-[11px] rounded-md px-2 py-1.5 border border-border focus:border-primary outline-none transition-colors">
          <option>likecodex (Local)</option>
        </select>
      </div>

      {/* 输入区域 */}
      <div className="p-3 border-b border-border">
        <form onSubmit={handleSubmit}>
          <textarea
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder={getPlaceholderText()}
            className="w-full h-20 bg-background text-foreground text-sm rounded-lg p-3 resize-none border border-border focus:border-primary outline-none placeholder:text-muted/50 transition-colors"
          />

          <div className="flex items-center justify-between mt-2">
            <div className="flex items-center gap-2">
              {/* 附件按钮 */}
              <button
                type="button"
                className="p-1.5 rounded hover:bg-accent/10 text-muted hover:text-foreground transition-colors"
                title="Add attachment"
              >
                <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13" />
                </svg>
              </button>

              {/* 审批模式选择 */}
              <select className="text-[10px] bg-background text-muted rounded px-2 py-1 border border-border">
                <option>Auto</option>
                <option>Manual</option>
              </select>
            </div>

            <button
              type="submit"
              disabled={!inputValue.trim()}
              className="px-4 py-1.5 bg-primary text-primary-foreground text-xs font-medium rounded-md hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed transition-opacity"
            >
              Send
            </button>
          </div>
        </form>

        {/* Plan New Idea 快捷按钮 */}
        <button className="mt-2 w-full text-[11px] text-muted hover:text-foreground text-left px-2 py-1.5 rounded-md hover:bg-accent/10 transition-colors flex items-center gap-2">
          <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.663 17h4.673M12 3v1m6.364 1.636l-.707.707M21 12h-1M4 12H3m3.343-5.657l-.707-.707m2.828 9.9a5 5 0 117.072 0l-.548.547A3.374 3.374 0 0014 18.469V19a2 2 0 11-4 0v-.531c0-.895-.356-1.754-.988-2.386l-.548-.547z" />
          </svg>
          Plan New Idea
          <kbd className="ml-auto px-1.5 py-0.5 bg-accent/20 rounded text-[9px] text-muted">
            Shift+Tab
          </kbd>
        </button>
      </div>

      {/* 对话历史 */}
      <ConversationHistory />

      {/* 底部用户信息 */}
      <div className="p-3 border-t border-border bg-surface/50">
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-full bg-gradient-to-br from-primary to-accent flex items-center justify-center text-primary-foreground text-[10px] font-bold shrink-0">
            U
          </div>
          <div className="flex-1 min-w-0">
            <div className="text-[11px] text-foreground truncate">User</div>
            <div className="text-[10px] text-muted/50">Free Plan</div>
          </div>
          <button
            className="p-1 rounded hover:bg-accent/10 text-muted hover:text-foreground transition-colors"
            title="Settings"
          >
            <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
          </button>
        </div>
      </div>
    </div>
  );
};
