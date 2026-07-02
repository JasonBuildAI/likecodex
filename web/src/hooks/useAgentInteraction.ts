'use client';

import { useState, useCallback, useRef } from 'react';
import { useAppStore, type Skill } from '@/lib/store';
import type { ContextMention } from '@/ide/context/types';

export function useAgentInteraction() {
  const [input, setInput] = useState('');
  const [inputHistory, setInputHistory] = useState<string[]>([]);
  const [historyIndex, setHistoryIndex] = useState(-1);
  const [showSkillAutocomplete, setShowSkillAutocomplete] = useState(false);
  const [skillAutocompleteQuery, setSkillAutocompleteQuery] = useState('');
  const [skillAutocompleteIndex, setSkillAutocompleteIndex] = useState(0);
  const [selectedSkill, setSelectedSkill] = useState<Skill | null>(null);
  const [showMentions, setShowMentions] = useState(false);
  const [mentionQuery, setMentionQuery] = useState('');
  const [mentionPos, setMentionPos] = useState({ top: 0, left: 0 });
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);

  const isStreaming = useAppStore((s) => s.isStreaming);
  const skills = useAppStore((s) => s.skills);
  const agentMode = useAppStore((s) => s.agentMode);

  const submitPrompt = useCallback((
    prompt: string,
    onSubmit: (text: string, skillName?: string) => void,
  ) => {
    if (!prompt.trim() || isStreaming) return;
    setInputHistory((prev) => [prompt, ...prev].slice(0, 50));
    setHistoryIndex(-1);
    setInput('');
    onSubmit(prompt, selectedSkill?.name);
    setSelectedSkill(null);
  }, [isStreaming, selectedSkill]);

  const handleInputChange = useCallback((e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const value = e.target.value;
    setInput(value);
    const cursor = e.target.selectionStart;
    const beforeCursor = value.slice(0, cursor);

    // Skill autocomplete via /slash
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

    // @mention detection
    const atCursor = value.slice(0, cursor);
    const atIndex = atCursor.lastIndexOf('@');
    if (atIndex !== -1 && (atIndex === 0 || beforeCursor[atIndex - 1] === ' ' || beforeCursor[atIndex - 1] === '\n')) {
      const query = beforeCursor.slice(atIndex + 1);
      if (!query.includes(' ') && !query.includes('\n') && query.length <= 50) {
        setShowMentions(true);
        setMentionQuery(query);
        const rect = textareaRef.current?.getBoundingClientRect();
        if (rect) setMentionPos({ top: rect.bottom + 4, left: rect.left + 16 });
        return;
      }
    }
    setShowMentions(false);
  }, []);

  const handleMentionSelect = useCallback((mention: ContextMention) => {
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
  }, [input]);

  const insertSkillTag = useCallback((skill: Skill) => {
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
  }, [input]);

  const handleKeyDown = useCallback((
    e: React.KeyboardEvent<HTMLTextAreaElement>,
    onSubmit: (text: string, skillName?: string) => void,
  ) => {
    // Submit: Ctrl+Enter / Cmd+Enter
    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
      e.preventDefault();
      submitPrompt(input, onSubmit);
      return;
    }

    // Skill autocomplete navigation
    if (showSkillAutocomplete) {
      const filtered = skills
        .filter(s => s.enabled !== false)
        .filter(s => !skillAutocompleteQuery || s.name.toLowerCase().includes(skillAutocompleteQuery.toLowerCase()))
        .slice(0, 8);
      if (e.key === 'ArrowDown') { e.preventDefault(); setSkillAutocompleteIndex(i => Math.min(i + 1, filtered.length - 1)); return; }
      if (e.key === 'ArrowUp') { e.preventDefault(); setSkillAutocompleteIndex(i => Math.max(0, i - 1)); return; }
      if (e.key === 'Enter' || e.key === 'Tab') {
        e.preventDefault();
        const idx = skillAutocompleteIndex;
        const selected = filtered[idx];
        if (selected) insertSkillTag(selected);
        return;
      }
    }

    // Input history navigation (up/down arrows)
    if (e.key === 'ArrowUp' && input === '' && inputHistory.length > 0) {
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
  }, [input, inputHistory, historyIndex, isStreaming, skills, showSkillAutocomplete, skillAutocompleteQuery, skillAutocompleteIndex, submitPrompt, insertSkillTag]);

  const handleSubmit = useCallback((
    e: React.FormEvent,
    onSubmit: (text: string, skillName?: string) => void,
  ) => {
    e.preventDefault();
    submitPrompt(input, onSubmit);
  }, [input, submitPrompt]);

  return {
    // State
    input, setInput,
    inputHistory,
    historyIndex,
    showSkillAutocomplete, setShowSkillAutocomplete,
    skillAutocompleteQuery,
    skillAutocompleteIndex, setSkillAutocompleteIndex,
    selectedSkill, setSelectedSkill,
    showMentions, setShowMentions,
    mentionQuery,
    mentionPos,
    textareaRef,

    // Actions
    handleInputChange,
    handleMentionSelect,
    handleKeyDown,
    handleSubmit,
    submitPrompt,
    insertSkillTag,
  };
}
