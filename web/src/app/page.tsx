'use client';

import { useCallback, useEffect, useRef, useState } from 'react';
import { ChatMessages } from '@/components/Chat';
import { DiffViewer } from '@/components/DiffViewer';
import { PermissionModal } from '@/components/PermissionModal';
import { AskModal } from '@/components/AskModal';
import { CheckpointPanel } from '@/components/CheckpointPanel';
import { SetupBanner } from '@/components/SetupBanner';
import { TaskTimeline } from '@/components/TaskTimeline';
import { SettingsPanel } from '@/components/SettingsPanel';
import { CommandPalette } from '@/components/CommandPalette';
import { CodeGraphSearch } from '@/components/CodeGraphSearch';
import { SkillPanel } from '@/components/SkillPanel';
import { FileTree } from '@/components/FileTree';
import { EditorPanel } from '@/components/EditorPanel';
import { StatusBar } from '@/components/StatusBar';
import { MentionPicker } from '@/ide/context/MentionPicker';
import type { ContextMention } from '@/ide/context/types';
import { ComposerPanel } from '@/ide/composer/ComposerPanel';
import { useComposerStore } from '@/ide/composer/composerStore';
import { GitPanel } from '@/ide/git/GitPanel';
import { SearchPanel } from '@/ide/search/SearchPanel';
import { TerminalPanel } from '@/ide/terminal/TerminalPanel';
import { TestRunnerPanel } from '@/ide/debug/TestRunnerPanel';
import { DebugToolbar } from '@/ide/debug/DebugToolbar';
import { IDESettingsPanel } from '@/ide/settings/IDESettingsPanel';
import { ExtensionLoader } from '@/ide/extensions/extensionLoader';
import { AgentSidebar } from '@/components/AgentSidebar';
import {
  fetchCacheMetrics,
  fetchConfig,
  fetchDoctor,
  fetchSessionEvents,
  fetchSessions,
  streamChat,
  subscribeEvents,
  createNewSession,
} from '@/lib/api';
import { useAppStore } from '@/lib/store';

export default function Home() {
  const [input, setInput] = useState('');
  const [doctor, setDoctor] = useState<Awaited<ReturnType<typeof fetchDoctor>>>(null);
  const [inputHistory, setInputHistory] = useState<string[]>([]);
  const [historyIndex, setHistoryIndex] = useState(-1);
  const [chatOpen, setChatOpen] = useState(true);
  const [diffOpen, setDiffOpen] = useState(false);
  const [terminalOpen, setTerminalOpen] = useState(false);
  const [leftPanel, setLeftPanel] = useState<'files' | 'agents' | 'sessions' | 'search' | 'git' | 'tests' | 'skills'>('files');
  const [debugOpen, setDebugOpen] = useState(false);
  const [ideSettingsOpen, setIdeSettingsOpen] = useState(false);
  const [showMentions, setShowMentions] = useState(false);
  const [mentionQuery, setMentionQuery] = useState('');
  const [mentionPos, setMentionPos] = useState({ top: 0, left: 0 });
  const [mentions, setMentions] = useState<ContextMention[]>([]);
  const abortRef = useRef<AbortController | null>(null);
  const scrollRef = useRef<HTMLDivElement | null>(null);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);

  const messages = useAppStore((s) => s.messages);
  const tasks = useAppStore((s) => s.tasks);
  const planSteps = useAppStore((s) => s.planSteps);
  const sessions = useAppStore((s) => s.sessions);
  const pendingPermissions = useAppStore((s) => s.pendingPermissions);
  const pendingAskRequests = useAppStore((s) => s.pendingAskRequests);
  const activeDiff = useAppStore((s) => s.activeDiff);
  const cacheHitRate = useAppStore((s) => s.cacheHitRate);
  const planModeActive = useAppStore((s) => s.planModeActive);
  const collaborationMode = useAppStore((s) => s.collaborationMode);
  const isStreaming = useAppStore((s) => s.isStreaming);
  const currentSessionId = useAppStore((s) => s.currentSessionId);
  const openFiles = useAppStore((s) => s.openFiles);
  const activeFilePath = useAppStore((s) => s.activeFilePath);
  const composerOpen = useComposerStore((s) => s.isOpen);
  const toggleComposer = useComposerStore((s) => s.toggleComposer);

  const setCollaborationMode = useAppStore((s) => s.setCollaborationMode);
  const setPlanMode = useAppStore((s) => s.setPlanMode);
  const setCacheHitRate = useAppStore((s) => s.setCacheHitRate);
  const addMessage = useAppStore((s) => s.addMessage);
  const appendToLastMessage = useAppStore((s) => s.appendToLastMessage);
  const upsertToolDispatch = useAppStore((s) => s.upsertToolDispatch);
  const setIsStreaming = useAppStore((s) => s.setIsStreaming);
  const setTasks = useAppStore((s) => s.setTasks);
  const updateTask = useAppStore((s) => s.updateTask);
  const setCurrentTaskId = useAppStore((s) => s.setCurrentTaskId);
  const addPendingPermission = useAppStore((s) => s.addPendingPermission);
  const removePendingPermission = useAppStore((s) => s.removePendingPermission);
  const addPendingAsk = useAppStore((s) => s.addPendingAsk);
  const removePendingAsk = useAppStore((s) => s.removePendingAsk);
  const setPlanSteps = useAppStore((s) => s.setPlanSteps);
  const updatePlanStep = useAppStore((s) => s.updatePlanStep);
  const setActiveDiff = useAppStore((s) => s.setActiveDiff);
  const setSessions = useAppStore((s) => s.setSessions);
  const setConfig = useAppStore((s) => s.setConfig);
  const setCurrentSessionId = useAppStore((s) => s.setCurrentSessionId);
  const setMessages = useAppStore((s) => s.setMessages);
  const addToast = useAppStore((s) => s.addToast);
  const agentMode = useAppStore((s) => s.agentMode);
  const setAgentMode = useAppStore((s) => s.setAgentMode);

  // ── Load extensions on mount ──────────────────────────────────
  useEffect(() => {
    ExtensionLoader.loadExtensions();
  }, []);

  // ── Initialization ──────────────────────────────────────────────────
  useEffect(() => {
    fetchConfig().then(setConfig);
    fetchSessions().then(setSessions);
    fetchDoctor().then(setDoctor);
    fetchCacheMetrics().then((metrics) => {
      const rate = metrics.recent_hit_rate ?? metrics.hit_rate;
      setCacheHitRate(typeof rate === 'number' ? rate : null);
    });
    const interval = setInterval(() => {
      fetchCacheMetrics().then((metrics) => {
        const rate = metrics.recent_hit_rate ?? metrics.hit_rate;
        setCacheHitRate(typeof rate === 'number' ? rate : null);
      });
    }, 15000);
    return () => clearInterval(interval);
  }, [setConfig, setSessions, setCacheHitRate]);

  // ── Event subscription ──────────────────────────────────────────────
  useEffect(() => {
    const unsubscribe = subscribeEvents({
      onMessage: addMessage,
      onAppend: appendToLastMessage,
      onUpsertToolDispatch: upsertToolDispatch,
      onPermission: addPendingPermission,
      onPermissionResponded: (requestId) => removePendingPermission(requestId),
      onAsk: addPendingAsk,
      onAskResponded: (requestId) => removePendingAsk(requestId),
      onPlanModeChanged: (active) => setPlanMode(active),
      onPlanStep: (step) => {
        const existing = useAppStore.getState().planSteps;
        if (existing.find((s) => s.id === step.id)) {
          updatePlanStep(step.id, step);
        } else {
          setPlanSteps([...existing, step]);
        }
      },
      onDiff: (before, after) => {
        setActiveDiff({ before, after });
        setDiffOpen(true);
      },
      onError: (err) => {
        addToast({ type: 'error', message: err.message });
      },
    });
    return unsubscribe;
  }, [
    addMessage, appendToLastMessage, upsertToolDispatch,
    addPendingPermission, removePendingPermission, addPendingAsk, removePendingAsk,
    setPlanMode, setPlanSteps, updatePlanStep, setActiveDiff, addToast,
  ]);

  // ── Chat logic ──────────────────────────────────────────────────────
  const runPrompt = useCallback(async (prompt: string) => {
    if (!prompt.trim() || isStreaming) return;

    setInputHistory((prev) => [prompt, ...prev].slice(0, 50));
    setHistoryIndex(-1);

    addMessage({
      id: `user-${Date.now()}`,
      role: 'user',
      content: prompt,
      timestamp: Date.now(),
    });
    setIsStreaming(true);
    setPlanSteps([]);

    abortRef.current?.abort();
    abortRef.current = new AbortController();

    // Get active files from store to inject into context
    const { openFiles, activeFilePath } = useAppStore.getState();
    const activeFiles = openFiles
      .filter((f) => f.path === activeFilePath || f.modified)
      .map((f) => f.path)
      .slice(0, 5); // Limit to 5 files

    try {
      await streamChat(
        prompt,
        currentSessionId,
        {
          onMessage: addMessage,
          onAppend: appendToLastMessage,
          onUpsertToolDispatch: upsertToolDispatch,
          onTaskStarted: (task) => {
            setTasks([...useAppStore.getState().tasks, task]);
            setCurrentTaskId(task.id);
            if (!currentSessionId) setCurrentSessionId(task.id);
          },
          onTaskCompleted: (taskId, failed) => {
            updateTask(taskId, { status: failed ? 'failed' : 'completed' });
            fetchSessions().then(setSessions);
          },
          onStreamFinished: () => setIsStreaming(false),
          onPermission: addPendingPermission,
          onAsk: addPendingAsk,
          onAskResponded: (requestId) => removePendingAsk(requestId),
          onPlanModeChanged: (active) => setPlanMode(active),
          onPlanStep: (step) => {
            const existing = useAppStore.getState().planSteps;
            if (existing.find((s) => s.id === step.id)) {
              updatePlanStep(step.id, step);
            } else {
              setPlanSteps([...existing, step]);
            }
          },
        },
        abortRef.current.signal,
        agentMode,
        activeFiles
      );
    } catch (err) {
      addMessage({
        id: `error-${Date.now()}`,
        role: 'system',
        content: `Failed: ${err instanceof Error ? err.message : String(err)}`,
        timestamp: Date.now(),
      });
      setIsStreaming(false);
      addToast({ type: 'error', message: `Failed: ${err instanceof Error ? err.message : String(err)}` });
    }
  }, [
    isStreaming, currentSessionId, setCurrentSessionId, addMessage, setIsStreaming, setPlanSteps,
    appendToLastMessage, upsertToolDispatch, setTasks, setCurrentTaskId,
    updateTask, setSessions, addPendingPermission, addPendingAsk, removePendingAsk,
    setPlanMode, updatePlanStep, addToast, agentMode,
  ]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isStreaming) return;
    const prompt = input;
    setInput('');
    await runPrompt(prompt);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
      e.preventDefault();
      if (!input.trim() || isStreaming) return;
      const prompt = input;
      setInput('');
      runPrompt(prompt);
      return;
    }

    if (e.key === 'Escape') {
      useAppStore.getState().setCommandPaletteOpen(false);
      useAppStore.getState().setSettingsOpen(false);
      return;
    }

    if (e.key === 'ArrowUp' && input === '') {
      e.preventDefault();
      setHistoryIndex((prev) => {
        const next = Math.min(prev + 1, inputHistory.length - 1);
        if (inputHistory[next] !== undefined) setInput(inputHistory[next]);
        return next;
      });
      return;
    }
    if (e.key === 'ArrowDown' && historyIndex >= 0) {
      e.preventDefault();
      setHistoryIndex((prev) => {
        const next = prev - 1;
        if (next < 0) {
          setInput('');
          return -1;
        }
        setInput(inputHistory[next] || '');
        return next;
      });
    }
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const value = e.target.value;
    setInput(value);

    // @ mention detection
    const cursor = e.target.selectionStart;
    const beforeCursor = value.slice(0, cursor);
    const atIndex = beforeCursor.lastIndexOf('@');

    if (atIndex !== -1 && (atIndex === 0 || beforeCursor[atIndex - 1] === ' ' || beforeCursor[atIndex - 1] === '\n')) {
      const query = beforeCursor.slice(atIndex + 1);
      if (!query.includes(' ') && !query.includes('\n') && query.length <= 50) {
        setShowMentions(true);
        setMentionQuery(query);
        // Calculate position near cursor
        const rect = textareaRef.current?.getBoundingClientRect();
        if (rect) {
          setMentionPos({
            top: rect.bottom - 60,
            left: rect.left + 20,
          });
        }
        return;
      }
    }
    setShowMentions(false);
  };

  const handleMentionSelect = (mention: ContextMention) => {
    const cursor = textareaRef.current?.selectionStart || input.length;
    const beforeCursor = input.slice(0, cursor);
    const atIndex = beforeCursor.lastIndexOf('@');
    if (atIndex === -1) return;

    const afterCursor = input.slice(cursor);
    const mentionTag = `@[${mention.label}](${mention.id}) `;
    const newInput = input.slice(0, atIndex) + mentionTag + afterCursor;
    setInput(newInput);
    setShowMentions(false);

    // Focus back to textarea and position cursor after mention
    setTimeout(() => {
      if (textareaRef.current) {
        const newCursor = atIndex + mentionTag.length;
        textareaRef.current.focus();
        textareaRef.current.setSelectionRange(newCursor, newCursor);
      }
    }, 0);
  };

  // ── Global keyboard shortcuts ───────────────────────────────────────
  useEffect(() => {
    const handler = (e: KeyboardEvent) => {
      const isInput = document.activeElement?.tagName === 'INPUT' || document.activeElement?.tagName === 'TEXTAREA';
      if (e.key === 'k' && (e.ctrlKey || e.metaKey) && !e.shiftKey) {
        e.preventDefault();
        useAppStore.getState().setCommandPaletteOpen(true);
        return;
      }
      if (e.key === 'b' && (e.ctrlKey || e.metaKey)) {
        e.preventDefault();
        useAppStore.getState().toggleSidebar();
        return;
      }
      if (e.key === 'p' && (e.ctrlKey || e.metaKey) && e.shiftKey) {
        e.preventDefault();
        setIdeSettingsOpen(true);
        return;
      }
      if (e.key === ',' && (e.ctrlKey || e.metaKey)) {
        e.preventDefault();
        setIdeSettingsOpen(true);
        return;
      }
      if (e.key === 'n' && (e.ctrlKey || e.metaKey) && !isInput) {
        e.preventDefault();
        createNewSession().then((r) => {
          setCurrentSessionId(r.session_id);
          setMessages([]);
          addToast({ type: 'success', message: 'New session created' });
          fetchSessions().then(setSessions);
        });
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [setCurrentSessionId, setMessages, setSessions, addToast]);

  // ── Session handling ────────────────────────────────────────────────
  const handleSessionSelect = async (sessionId: string) => {
    setCurrentSessionId(sessionId);
    setIsStreaming(false);
    setPlanSteps([]);
    const events = await fetchSessionEvents(sessionId);
    setMessages(events);
  };

  const cacheLabel = cacheHitRate !== null ? `${Math.round(cacheHitRate * 100)}%` : '--';
  const hasDiff = activeDiff?.before || activeDiff?.after;

  // ── Render ──────────────────────────────────────────────────────────
  return (
    <main className="flex h-screen flex-col bg-background">
      {/* Header */}
      <header className="border-b border-border px-3 py-1.5 flex items-center justify-between bg-surface shrink-0">
        <div className="flex items-center gap-2">
          <button
            onClick={() => useAppStore.getState().toggleSidebar()}
            className="p-1 rounded hover:bg-accent/10 transition-colors"
            title="Toggle sidebar (Ctrl+B)"
          >
            <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 6h16M4 12h16M4 18h16" />
            </svg>
          </button>
          <h1 className="text-sm font-semibold">LikeCodex</h1>
        </div>

        <div className="flex items-center gap-1.5 text-xs text-muted">
          {/* Left panel tabs */}
          <div className="flex gap-0.5 mr-2">
            {(['files', 'agents', 'sessions', 'search', 'git', 'tests', 'skills'] as const).map((tab) => (
              <button
                key={tab}
                onClick={() => setLeftPanel(tab)}
                className={`px-2 py-0.5 rounded text-[10px] transition-colors ${
                  leftPanel === tab ? 'bg-primary/20 text-primary' : 'hover:bg-accent/10'
                }`}
              >
                {tab === 'files' ? 'Files' : tab === 'agents' ? 'Agents' : tab === 'sessions' ? 'History' : tab === 'search' ? 'Search' : tab === 'git' ? 'Git' : tab === 'tests' ? 'Tests' : 'Skills'}
              </button>
            ))}
          </div>

          <span className="text-border mx-0.5">|</span>

          {/* Plan mode badge */}
          {planModeActive ? (
            <span className="px-2 py-0.5 rounded bg-amber-500/20 text-amber-200 text-[10px] font-medium">PLAN</span>
          ) : null}

          {/* Collaboration mode */}
          <select
            className="bg-transparent border border-border rounded px-1.5 py-0.5 text-[10px]"
            value={collaborationMode}
            onChange={(e) => {
              const mode = e.target.value as 'normal' | 'plan' | 'goal';
              setCollaborationMode(mode);
              if (mode === 'plan') runPrompt('/plan');
              if (mode === 'goal') runPrompt('/goal Continue autonomously on the active task');
              if (mode === 'normal') runPrompt('/exit_plan');
            }}
          >
            <option value="normal">normal</option>
            <option value="plan">plan</option>
            <option value="goal">goal</option>
          </select>

          {/* Chat toggle */}
          <button
            onClick={() => setChatOpen(!chatOpen)}
            className={`px-1.5 py-0.5 rounded border text-[10px] transition-colors ${chatOpen ? 'border-primary text-primary' : 'border-border'}`}
            title="Toggle chat panel"
          >
            Chat
          </button>

          {/* Terminal toggle */}
          <button
            onClick={() => setTerminalOpen(!terminalOpen)}
            className={`px-1.5 py-0.5 rounded border text-[10px] transition-colors ${terminalOpen ? 'border-primary text-primary' : 'border-border'}`}
            title="Toggle terminal (Ctrl+J)"
          >
            Terminal
          </button>

          {/* Debug toggle */}
          <button
            onClick={() => setDebugOpen(!debugOpen)}
            className={`px-1.5 py-0.5 rounded border text-[10px] transition-colors ${debugOpen ? 'border-primary text-primary' : 'border-border'}`}
            title="Toggle debug toolbar"
          >
            Debug
          </button>

          {/* Command palette */}
          <button
            onClick={() => useAppStore.getState().setCommandPaletteOpen(true)}
            className="px-1.5 py-0.5 rounded border border-border text-[10px] hover:bg-accent/10 transition-colors"
            title="Command palette (Ctrl+K)"
          >
            Cmd
          </button>

          <span className="text-border mx-0.5">|</span>
          <span className="flex items-center gap-1 text-[10px]" title="Cache hit rate">
            <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
            </svg>
            {cacheLabel}
          </span>
        </div>
      </header>

      <SetupBanner doctor={doctor} />

      {/* Main content: 3-column layout */}
      <div className="flex flex-1 min-h-0">
        {/* Left Panel: File tree / Sessions / Search / Skills */}
        <aside className="w-56 border-r border-border bg-surface/30 overflow-y-auto shrink-0 flex flex-col">
          {leftPanel === 'files' ? (
            <FileTree />
          ) : leftPanel === 'agents' ? (
            <AgentSidebar
              sessions={sessions}
              tasks={tasks}
              activeSessionId={currentSessionId}
              onSessionSelect={handleSessionSelect}
            />
          ) : leftPanel === 'sessions' ? (
            <div className="p-2 overflow-y-auto">
              <div className="text-[10px] font-semibold uppercase tracking-wider text-muted/60 mb-2 px-1">
                History
              </div>
              <TaskTimeline
                tasks={tasks}
                planSteps={planSteps}
                sessions={sessions}
                activeSessionId={currentSessionId}
                onSessionSelect={handleSessionSelect}
              />
              <div className="mt-3">
                <CheckpointPanel />
              </div>
            </div>
          ) : leftPanel === 'search' ? (
            <SearchPanel />
          ) : leftPanel === 'git' ? (
            <GitPanel />
          ) : leftPanel === 'tests' ? (
            <TestRunnerPanel />
          ) : (
            <SkillPanel />
          )}
        </aside>

        {/* Center: Editor + Diff */}
        <section className="flex-1 flex flex-col min-w-0">
          {/* Debug toolbar */}
          {debugOpen && <DebugToolbar />}

          {/* Editor */}
          <div className={`flex-1 min-h-0 ${diffOpen && hasDiff ? '' : 'flex-1'}`}>
            <EditorPanel />
          </div>

          {/* Diff panel (collapsible bottom) */}
          {diffOpen && hasDiff && (
            <div className="h-1/3 min-h-[120px] border-t border-border flex flex-col">
              <div className="flex items-center justify-between px-3 py-1 bg-surface/50 shrink-0">
                <span className="text-[10px] font-semibold text-muted/60 uppercase tracking-wider">
                  Changes
                </span>
                <button
                  onClick={() => setDiffOpen(false)}
                  className="text-[10px] text-muted hover:text-foreground"
                >
                  Close
                </button>
              </div>
              <div className="flex-1 min-h-0">
                <DiffViewer before={activeDiff?.before} after={activeDiff?.after} />
              </div>
            </div>
          )}

          {/* Terminal panel (collapsible bottom) */}
          {terminalOpen && (
            <div className="h-1/3 min-h-[120px] border-t border-border flex flex-col">
              <div className="flex items-center justify-between px-3 py-1 bg-surface/50 shrink-0">
                <span className="text-[10px] font-semibold text-muted/60 uppercase tracking-wider">
                  Terminal
                </span>
                <button
                  onClick={() => setTerminalOpen(false)}
                  className="text-[10px] text-muted hover:text-foreground"
                >
                  Close
                </button>
              </div>
              <div className="flex-1 min-h-0">
                <TerminalPanel />
              </div>
            </div>
          )}
        </section>

        {/* Right Panel: Chat */}
        {chatOpen && (
          <aside className="w-[360px] border-l border-border bg-surface/30 flex flex-col shrink-0">
            {/* Chat messages */}
            <div ref={scrollRef} className="flex-1 overflow-y-auto p-3">
              <ChatMessages scrollRef={scrollRef} />
            </div>

            {/* Agent mode selector + Chat input */}
            <form onSubmit={handleSubmit} className="border-t border-border bg-surface/50 shrink-0">
              {/* Mode selector bar */}
              <div className="flex items-center gap-1 px-2 pt-2 pb-1">
                <div className="flex rounded-lg border border-border overflow-hidden">
                  {(['ask', 'agent', 'manual'] as const).map((mode) => {
                    const isActive = agentMode === mode;
                    const colors = {
                      ask: isActive ? 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30' : '',
                      agent: isActive ? 'bg-blue-500/20 text-blue-400 border-blue-500/30' : '',
                      manual: isActive ? 'bg-amber-500/20 text-amber-400 border-amber-500/30' : '',
                    };
                    const icons = {
                      ask: '💬',
                      agent: '🤖',
                      manual: '✋',
                    };
                    const labels = {
                      ask: 'Ask',
                      agent: 'Agent',
                      manual: 'Manual',
                    };
                    const tooltips = {
                      ask: 'Ask mode: read-only Q&A, no code changes',
                      agent: 'Agent mode: autonomous execution with full tool access',
                      manual: 'Manual mode: confirm each action before execution',
                    };
                    return (
                      <button
                        key={mode}
                        type="button"
                        onClick={() => setAgentMode(mode)}
                        title={tooltips[mode]}
                        className={`px-2 py-1 text-[10px] font-medium transition-all ${
                          isActive
                            ? colors[mode]
                            : 'text-muted hover:text-foreground hover:bg-accent/10'
                        }`}
                      >
                        <span className="mr-0.5">{icons[mode]}</span>
                        {labels[mode]}
                      </button>
                    );
                  })}
                </div>
                <div className="flex-1" />
                <span className="text-[9px] text-muted/50">
                  {agentMode === 'ask' ? 'Read-only' : agentMode === 'manual' ? 'Confirm each step' : 'Auto-execute'}
                </span>
              </div>
              {/* Input area */}
              <div className="flex gap-2 items-end px-2 pb-2">
                <textarea
                  ref={textareaRef}
                  value={input}
                  onChange={handleInputChange}
                  onKeyDown={handleKeyDown}
                  placeholder={
                    agentMode === 'ask'
                      ? 'Ask a question about your code...'
                      : agentMode === 'manual'
                        ? 'Describe your task (each step requires approval)...'
                        : 'Describe your task... Use @ to reference files'
                  }
                  className="flex-1 rounded-md border border-border bg-background px-3 py-2 text-xs focus:outline-none focus:ring-2 focus:ring-primary resize-none min-h-[36px] max-h-[160px]"
                  rows={1}
                  disabled={isStreaming}
                />
                <button
                  type="submit"
                  disabled={isStreaming || !input.trim()}
                  className={`rounded-md px-3 py-2 text-xs font-medium text-white shrink-0 transition-colors disabled:opacity-50 ${
                    agentMode === 'ask'
                      ? 'bg-emerald-600 hover:bg-emerald-700'
                      : agentMode === 'manual'
                        ? 'bg-amber-600 hover:bg-amber-700'
                        : 'bg-primary hover:bg-blue-600'
                  }`}
                >
                  {isStreaming ? (
                    <span className="flex items-center gap-1">
                      <span className="h-1.5 w-1.5 rounded-full bg-white animate-pulse" />
                      ...
                    </span>
                  ) : agentMode === 'ask' ? 'Ask' : 'Send'}
                </button>
              </div>
            </form>
          </aside>
        )}
      </div>

      {/* Composer Panel */}
      <ComposerPanel />

      {/* Composer toggle button */}
      {!composerOpen && (
        <button
          onClick={toggleComposer}
          className="fixed bottom-12 right-4 z-50 px-3 py-1.5 bg-blue-600 text-white text-xs rounded-full shadow-lg hover:bg-blue-700 transition-colors"
          title="Open Composer (Cmd+I)"
        >
          ✨ Composer
        </button>
      )}

      {/* @ Mention Picker */}
      {showMentions && (
        <MentionPicker
          triggerPosition={mentionPos}
          query={mentionQuery}
          onSelect={handleMentionSelect}
          onClose={() => setShowMentions(false)}
        />
      )}

      {/* IDE Settings Panel */}
      <IDESettingsPanel open={ideSettingsOpen} onClose={() => setIdeSettingsOpen(false)} />

      {/* Status bar */}
      <StatusBar />

      {/* Overlays */}
      <PermissionModal requests={pendingPermissions} onResponded={removePendingPermission} />
      <AskModal requests={pendingAskRequests} onResponded={removePendingAsk} />
      <SettingsPanel />
      <CommandPalette />
    </main>
  );
}
