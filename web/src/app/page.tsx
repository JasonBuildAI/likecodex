'use client';

import { useState, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
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
import { SkillAutocomplete } from '@/components/Skills/SkillAutocomplete';
import { SkillDetailView } from '@/components/Skills/SkillDetailView';
import { SkillInstallDialog } from '@/components/Skills/SkillInstallDialog';
import { FileTree } from '@/components/FileTree';
import { EditorPanel } from '@/components/EditorPanel';
import { StatusBar } from '@/components/StatusBar';
import { Header } from '@/components/layout/Header';
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
import { AgentSidebar } from '@/components/AgentSidebar';
import { ShortcutHelpPanel } from '@/components/ShortcutHelp';
import { OnboardingTooltips } from '@/components/Onboarding';
import { createNewSession, fetchSessionEvents, fetchSessions } from '@/lib/api';
import { useAppStore, type Skill } from '@/lib/store';
import { useAppInit } from '@/hooks/useAppInit';
import { useEventSubscription } from '@/hooks/useEventSubscription';
import { useChatLogic } from '@/hooks/useChatLogic';

export default function Home() {
  const [input, setInput] = useState('');
  const [inputHistory, setInputHistory] = useState<string[]>([]);
  const [historyIndex, setHistoryIndex] = useState(-1);
  const [chatOpen, setChatOpen] = useState(true);
  const [diffOpen, setDiffOpen] = useState(false);
  const [terminalOpen, setTerminalOpen] = useState(false);
  const [leftPanel, setLeftPanel] = useState<'files' | 'agents' | 'sessions' | 'search' | 'git' | 'tests' | 'skills'>('files');
  const [debugOpen, setDebugOpen] = useState(false);
  const [ideSettingsOpen, setIdeSettingsOpen] = useState(false);
  const [showSkillAutocomplete, setShowSkillAutocomplete] = useState(false);
  const [skillAutocompleteQuery, setSkillAutocompleteQuery] = useState('');
  const [skillAutocompleteIndex, setSkillAutocompleteIndex] = useState(0);
  const [selectedSkill, setSelectedSkill] = useState<Skill | null>(null);
  const [showInstallDialog, setShowInstallDialog] = useState(false);
  const [showMentions, setShowMentions] = useState(false);
  const [mentionQuery, setMentionQuery] = useState('');
  const [mentionPos, setMentionPos] = useState({ top: 0, left: 0 });
  const [mentions, setMentions] = useState<ContextMention[]>([]);
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);
  const scrollRef = useRef<HTMLDivElement | null>(null);

  // Extract store slices
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
  const activeFilePath = useAppStore((s) => s.activeFilePath);
  const composerOpen = useComposerStore((s) => s.isOpen);
  const toggleComposer = useComposerStore((s) => s.toggleComposer);
  const agentMode = useAppStore((s) => s.agentMode);
  const skills = useAppStore((s) => s.skills);
  const skillDetail = useAppStore((s) => s.skillDetail);
  const setSkillDetail = useAppStore((s) => s.setSkillDetail);
  const setCollaborationMode = useAppStore((s) => s.setCollaborationMode);
  const setCurrentSessionId = useAppStore((s) => s.setCurrentSessionId);
  const setMessages = useAppStore((s) => s.setMessages);
  const addToast = useAppStore((s) => s.addToast);
  const setSessions = useAppStore((s) => s.setSessions);
  const setAgentMode = useAppStore((s) => s.setAgentMode);
  const setActiveDiff = useAppStore((s) => s.setActiveDiff);

  // Initialize hooks
  useAppInit();
  useEventSubscription();
  const { runPrompt, cancelPrompt } = useChatLogic();

  // Keyboard shortcuts
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
      if (e.key === 'Escape') {
        useAppStore.getState().setCommandPaletteOpen(false);
        useAppStore.getState().setSettingsOpen(false);
        return;
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [setCurrentSessionId, setMessages, setSessions, addToast]);

  const handleSessionSelect = async (sessionId: string) => {
    setCurrentSessionId(sessionId);
    useAppStore.getState().setIsStreaming(false);
    useAppStore.getState().setPlanSteps([]);
    const events = await fetchSessionEvents(sessionId);
    setMessages(events);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!input.trim() || isStreaming) return;
    setInputHistory((prev) => [input, ...prev].slice(0, 50));
    setHistoryIndex(-1);
    const prompt = input;
    setInput('');
    await runPrompt(prompt);
  };

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
      e.preventDefault();
      if (!input.trim() || isStreaming) return;
      setInputHistory((prev) => [input, ...prev].slice(0, 50));
      setHistoryIndex(-1);
      const prompt = input;
      setInput('');
      runPrompt(prompt);
      return;
    }
    if (showSkillAutocomplete) {
      if (e.key === 'ArrowDown') { e.preventDefault(); setSkillAutocompleteIndex(i => Math.min(i + 1, 7)); return; }
      if (e.key === 'ArrowUp') { e.preventDefault(); setSkillAutocompleteIndex(i => Math.max(0, i - 1)); return; }
      if (e.key === 'Enter' || e.key === 'Tab') {
        e.preventDefault();
        const allSkills = useAppStore.getState().skills;
        const filtered = allSkills.filter(s => s.enabled !== false).filter(s => !skillAutocompleteQuery || s.name.toLowerCase().includes(skillAutocompleteQuery.toLowerCase())).slice(0, 8);
        const idx = skillAutocompleteIndex;
        const selected = filtered[idx];
        if (selected) {
          const cursor = textareaRef.current?.selectionStart || input.length;
          const beforeCursor = input.slice(0, cursor);
          const slashIdx = beforeCursor.lastIndexOf('/');
          if (slashIdx !== -1) {
            const afterCursor = input.slice(cursor);
            const tag = '/' + selected.name + ' ';
            setInput(input.slice(0, slashIdx) + tag + afterCursor);
          }
          setSelectedSkill(selected);
        }
        setShowSkillAutocomplete(false);
        setSkillAutocompleteIndex(0);
        return;
      }
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
        if (next < 0) { setInput(''); return -1; }
        setInput(inputHistory[next] || '');
        return next;
      });
    }
  };

  const handleInputChange = (e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const value = e.target.value;
    setInput(value);
    const cursor = e.target.selectionStart;
    const beforeCursor = value.slice(0, cursor);
    const slashIndex = beforeCursor.lastIndexOf('/');
    if (slashIndex !== -1 && (slashIndex === 0 || beforeCursor[slashIndex - 1] === ' ' || beforeCursor[slashIndex - 1] === '\n')) {
      const query = beforeCursor.slice(slashIndex + 1);
      if (!query.includes(' ') && !query.includes('\n') && query.length <= 50) {
        setShowSkillAutocomplete(true);
        setSkillAutocompleteQuery(query);
        setShowMentions(false);
        return;
      }
    }
    setShowSkillAutocomplete(false);
    // @ mention detection — Phase 3.3: file picker via @mention
    // Phase 5.10 enhancement notes:
    // - Added fuzzy matching via MentionPicker API search
    // - Added relevance scores and token estimates per result
    // - Added type-based icons (file, folder, symbol, git, issue)
    // - TODO: Multi-token @mentions (e.g. @file:path/to/file.ts)
    // - TODO: Recent/priority mentions showing first
    // - TODO: Inline context preview on hover (expandable snippet)
    // - TODO: Mention history (recently used references)
    const atCursor = value.slice(0, cursor);
    const atIndex = atCursor.lastIndexOf('@');
    if (atIndex !== -1 && (atIndex === 0 || atCursor[atIndex - 1] === ' ' || atCursor[atIndex - 1] === '\n')) {
      const query = atCursor.slice(atIndex + 1);
      if (!query.includes(' ') && !query.includes('\n') && query.length <= 50) {
        setShowMentions(true);
        setMentionQuery(query);
        const rect = textareaRef.current?.getBoundingClientRect();
        if (rect) {
          setMentionPos({ top: rect.bottom + 4, left: rect.left + 16 });
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
    setInput(input.slice(0, atIndex) + mentionTag + afterCursor);
    setShowMentions(false);
    setTimeout(() => {
      if (textareaRef.current) {
        const newCursor = atIndex + mentionTag.length;
        textareaRef.current.focus();
        textareaRef.current.setSelectionRange(newCursor, newCursor);
      }
    }, 0);
  };

  const hasDiff = activeDiff?.before || activeDiff?.after;

  return (
    <main className="flex h-screen flex-col bg-background">
      <Header
        leftPanel={leftPanel}
        setLeftPanel={setLeftPanel}
        chatOpen={chatOpen}
        setChatOpen={setChatOpen}
        terminalOpen={terminalOpen}
        setTerminalOpen={setTerminalOpen}
        debugOpen={debugOpen}
        setDebugOpen={setDebugOpen}
        setIdeSettingsOpen={setIdeSettingsOpen}
        runPrompt={runPrompt}
      />
      <SetupBanner />
      <div className="flex flex-1 min-h-0">
        {/* Left Panel */}
        <aside className="w-56 border-r border-border bg-surface/30 overflow-y-auto shrink-0 flex flex-col">
          {leftPanel === 'files' ? <FileTree /> :
           leftPanel === 'agents' ? <AgentSidebar sessions={sessions} tasks={tasks} activeSessionId={currentSessionId} onSessionSelect={handleSessionSelect} /> :
           leftPanel === 'sessions' ? (
            <div className="p-2 overflow-y-auto">
              <div className="text-[10px] font-semibold uppercase tracking-wider text-muted/60 mb-2 px-1">History</div>
              <TaskTimeline tasks={tasks} planSteps={planSteps} sessions={sessions} activeSessionId={currentSessionId} onSessionSelect={handleSessionSelect} />
              <div className="mt-3"><CheckpointPanel /></div>
            </div>
           ) : leftPanel === 'search' ? <SearchPanel /> :
             leftPanel === 'git' ? <GitPanel /> :
             leftPanel === 'tests' ? <TestRunnerPanel /> :
             skillDetail ? <SkillDetailView skill={skillDetail} onBack={() => setSkillDetail(null)} /> : <SkillPanel />}
        </aside>
        {/* Center: Editor + Diff + Terminal */}
        <section className="flex-1 flex flex-col min-w-0">
          {debugOpen && <DebugToolbar />}
          <div className={`flex-1 min-h-0`}><EditorPanel /></div>
          {diffOpen && hasDiff && (
            <div className="h-1/3 min-h-[120px] border-t border-border flex flex-col">
              <div className="flex items-center justify-between px-3 py-1 bg-surface/50 shrink-0">
                <span className="text-[10px] font-semibold text-muted/60 uppercase tracking-wider">Changes</span>
                <button onClick={() => { setDiffOpen(false); setActiveDiff(null); }} className="text-[10px] text-muted hover:text-foreground">Close</button>
              </div>
              <div className="flex-1 min-h-0"><DiffViewer before={activeDiff?.before} after={activeDiff?.after} /></div>
            </div>
          )}
          {terminalOpen && (
            <div className="h-1/3 min-h-[120px] border-t border-border flex flex-col">
              <div className="flex items-center justify-between px-3 py-1 bg-surface/50 shrink-0">
                <span className="text-[10px] font-semibold text-muted/60 uppercase tracking-wider">Terminal</span>
                <button onClick={() => setTerminalOpen(false)} className="text-[10px] text-muted hover:text-foreground">Close</button>
              </div>
              <div className="flex-1 min-h-0"><TerminalPanel /></div>
            </div>
          )}
        </section>
        {/* Right Panel: Chat */}
        {chatOpen && (
          <motion.aside initial={{ opacity: 0, x: 50 }} animate={{ opacity: 1, x: 0 }} exit={{ opacity: 0, x: 50 }}
            transition={{ type: 'spring', stiffness: 200, damping: 25 }}
            className="w-[480px] border-l border-border bg-surface flex flex-col shrink-0 relative">
            <div className="flex items-center justify-between px-4 py-2 border-b border-border bg-surface/50 shrink-0">
              <div className="flex items-center gap-2">
                <motion.button whileHover={{ scale: 1.02 }} whileTap={{ scale: 0.98 }}
                  className="flex items-center gap-1.5 text-xs text-muted hover:text-foreground transition-colors px-2 py-1 rounded hover:bg-accent/10">
                  <span>{currentSessionId ? 'likecodex' : 'New Agent'}</span>
                  <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" /></svg>
                </motion.button>
                <button className="flex items-center gap-1.5 text-xs text-muted hover:text-foreground transition-colors px-2 py-1 rounded hover:bg-accent/10">
                  <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9.75 17L9 20l-1 1h8l-1-1-.75-3M3 13h18M5 17h14a2 2 0 002-2V5a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z" />
                  </svg>
                  <span>Local</span>
                  <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" /></svg>
                </button>
              </div>
              <div className="flex items-center gap-1.5">
                <span className="flex items-center gap-1 text-[10px] text-muted/60" title="Cache hit rate">
                  <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" /></svg>
                  {cacheLabel}
                </span>
                <ShortcutHelpPanel />
                <motion.button whileHover={{ scale: 1.05 }} whileTap={{ scale: 0.95 }}
                  onClick={() => setIdeSettingsOpen(true)}
                  className="p-1.5 rounded hover:bg-accent/10 text-muted hover:text-foreground transition-colors" title="Settings (Ctrl+,)">
                  <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.065 2.572c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.572 1.065c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.065-2.572c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                  </svg>
                </motion.button>
              </div>
            </div>
            <div ref={scrollRef} className="flex-1 overflow-y-auto p-4"><ChatMessages scrollRef={scrollRef} /></div>
            {/* Input Area */}
            <div className="absolute bottom-0 left-0 right-0 p-4 bg-gradient-to-t from-surface via-surface to-transparent">
              <form onSubmit={handleSubmit} className="max-w-2xl mx-auto">
                {/* ── Mode capsule selector ──
                 *  Phase 5.12: Enhanced with descriptions, tooltips, and active indicator.
                 *  - ask: Q&A only, no code changes
                 *  - agent: Full AI agent with autonomous actions
                 *  - manual: Step-by-step with approval per action */}
                <div className="flex items-center justify-center mb-3">
                  <div className="inline-flex items-center gap-1 bg-background/80 backdrop-blur-sm border border-border rounded-full px-1.5 py-1 shadow-lg">
                    {([
                      { mode: 'ask' as const, label: 'Ask', desc: 'Q&A, no code changes' },
                      { mode: 'agent' as const, label: 'Agent', desc: 'Autonomous actions' },
                      { mode: 'manual' as const, label: 'Manual', desc: 'Step-by-step approval' },
                    ]).map(({ mode, label, desc }) => {
                      const isActive = agentMode === mode;
                      const colorMap = { ask: 'bg-emerald-500/20 text-emerald-400 border-emerald-500/30', agent: 'bg-blue-500/20 text-blue-400 border-blue-500/30', manual: 'bg-amber-500/20 text-amber-400 border-amber-500/30' };
                      return (
                        <button key={mode} type="button" onClick={() => setAgentMode(mode)}
                          title={desc}
                          className={`group relative flex items-center gap-1.5 px-3 py-1.5 rounded-full text-xs font-medium transition-all ${isActive ? `${colorMap[mode]} shadow-md` : 'text-muted hover:text-foreground hover:bg-accent/10'}`}>
                          {isActive && (
                            <span className="absolute -top-1 -right-1 w-2 h-2 rounded-full bg-current animate-pulse" />
                          )}
                          <span>{label}</span>
                          {/* Tooltip on hover */}
                          <span className="absolute -bottom-8 left-1/2 -translate-x-1/2 px-2 py-0.5 rounded bg-surface border border-border text-[9px] text-muted whitespace-nowrap opacity-0 group-hover:opacity-100 transition-opacity pointer-events-none z-10 shadow-lg">
                            {desc}
                          </span>
                        </button>
                      );
                    })}
                  </div>
                </div>
                <div className="relative group">
                  <div className="absolute inset-0 bg-gradient-to-r from-blue-500/20 via-purple-500/20 to-pink-500/20 rounded-2xl blur-xl opacity-0 group-hover:opacity-100 transition-opacity duration-500" />
                  <div className="relative bg-background/90 backdrop-blur-sm border border-border rounded-2xl shadow-2xl overflow-hidden">
                    <textarea ref={textareaRef} value={input} onChange={handleInputChange} onKeyDown={handleKeyDown}
                      placeholder={agentMode === 'ask' ? 'Ask questions without making changes...' : agentMode === 'manual' ? 'Describe your task (each step requires approval)...' : 'What would you like to build? Use @ to reference files'}
                      className="w-full bg-transparent px-4 py-3.5 pr-24 text-sm focus:outline-none resize-none min-h-[56px] max-h-[200px] placeholder:text-muted/60"
                      rows={1} disabled={isStreaming} />
                    <div className="flex items-center justify-between px-3 pb-2">
                      <div className="flex items-center gap-2">
                        <button type="button" className="p-1.5 rounded-full hover:bg-accent/10 text-muted hover:text-foreground transition-colors" title="Add context">
                          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6v6m0 0v6m0-6h6m-6 0H6" /></svg>
                        </button>
                        {activeFilePath && (
                          <div className="flex items-center gap-1.5 px-2 py-1 rounded-full bg-primary/10 text-primary text-xs">
                            <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" /></svg>
                            <span className="truncate max-w-[120px]">{activeFilePath.split('/').pop()}</span>
                          </div>
                        )}
                      </div>
                      <div className="flex items-center gap-2">
                        <button type="submit" disabled={isStreaming || !input.trim()}
                          className={`p-2.5 rounded-full text-white shadow-lg transition-all transform hover:scale-105 active:scale-95 disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:scale-100 ${agentMode === 'ask' ? 'bg-emerald-600 hover:bg-emerald-700' : agentMode === 'manual' ? 'bg-amber-600 hover:bg-amber-700' : 'bg-blue-600 hover:bg-blue-700'}`}>
                          {isStreaming ? (
                            <svg className="h-5 w-5 animate-spin" fill="none" viewBox="0 0 24 24"><circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" /><path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" /></svg>
                          ) : (
                            <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 19l9 2-9-18-9 18 9-2zm0 0v-8" /></svg>
                          )}
                        </button>
                      </div>
                    </div>
                  </div>
                </div>
                <div className="mt-3 text-center">
                  <button type="button" onClick={() => setInput('/plan ')}
                    className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full border border-border bg-background/50 hover:bg-accent/10 text-xs text-muted hover:text-foreground transition-colors">
                    <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5H7a2 2 0 00-2 2v12a2 2 0 002 2h10a2 2 0 002-2V7a2 2 0 00-2-2h-2M9 5a2 2 0 002 2h2a2 2 0 002-2M9 5a2 2 0 012-2h2a2 2 0 012 2" /></svg>
                    Plan New Idea
                    <kbd className="ml-1 px-1.5 py-0.5 rounded bg-accent/20 text-[10px]">⇧Tab</kbd>
                  </button>
                </div>
              </form>
            </div>
          </motion.aside>
        )}
      </div>
      <ComposerPanel />
      {!composerOpen && (
        <button onClick={toggleComposer} className="fixed bottom-12 right-4 z-50 px-3 py-1.5 bg-blue-600 text-white text-xs rounded-full shadow-lg hover:bg-blue-700 transition-colors">✨ Composer</button>
      )}
      <SkillAutocomplete skills={skills} query={skillAutocompleteQuery} visible={showSkillAutocomplete} selectedIndex={skillAutocompleteIndex}
        onSelect={(skill) => {
          const cursor = textareaRef.current?.selectionStart || input.length;
          const beforeCursor = input.slice(0, cursor);
          const slashIdx = beforeCursor.lastIndexOf('/');
          if (slashIdx !== -1) {
            const afterCursor = input.slice(cursor);
            setInput(input.slice(0, slashIdx) + '/' + skill.name + ' ' + afterCursor);
          }
          setSelectedSkill(skill);
          setShowSkillAutocomplete(false);
          setSkillAutocompleteIndex(0);
          setTimeout(() => textareaRef.current?.focus(), 0);
        }} />
      {showInstallDialog && <SkillInstallDialog onClose={() => setShowInstallDialog(false)} />}
      {showMentions && <MentionPicker triggerPosition={mentionPos} query={mentionQuery} onSelect={handleMentionSelect} onClose={() => setShowMentions(false)} />}
      <IDESettingsPanel open={ideSettingsOpen} onClose={() => setIdeSettingsOpen(false)} />
      <StatusBar />
      <PermissionModal requests={pendingPermissions} onResponded={(id) => useAppStore.getState().removePendingPermission(id)} />
      <AskModal requests={pendingAskRequests} onResponded={(id) => useAppStore.getState().removePendingAsk(id)} />
      <SettingsPanel />
      <CommandPalette />
      <OnboardingTooltips />
    </main>
  );
}
