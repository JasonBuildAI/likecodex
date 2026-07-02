'use client';

import { useState, useRef } from 'react';
import type { ContextMention } from '@/ide/context/types';

export interface InputState {
  input: string;
  inputHistory: string[];
  historyIndex: number;
  showSkillAutocomplete: boolean;
  skillAutocompleteQuery: string;
  skillAutocompleteIndex: number;
  showMentions: boolean;
  mentionQuery: string;
  mentionPos: { top: number; left: number };
}

export function useIdeInput() {
  const [input, setInput] = useState('');
  const [inputHistory, setInputHistory] = useState<string[]>([]);
  const [historyIndex, setHistoryIndex] = useState(-1);
  const [showSkillAutocomplete, setShowSkillAutocomplete] = useState(false);
  const [skillAutocompleteQuery, setSkillAutocompleteQuery] = useState('');
  const [skillAutocompleteIndex, setSkillAutocompleteIndex] = useState(0);
  const [showMentions, setShowMentions] = useState(false);
  const [mentionQuery, setMentionQuery] = useState('');
  const [mentionPos, setMentionPos] = useState({ top: 0, left: 0 });
  const textareaRef = useRef<HTMLTextAreaElement | null>(null);

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
    const atCursor = value.slice(0, cursor);
    const atIndex = atCursor.lastIndexOf('@');
    if (atIndex !== -1 && (atIndex === 0 || beforeCursor[atIndex - 1] === ' ' || beforeCursor[atIndex - 1] === '')) {
      const query = beforeCursor.slice(atIndex + 1);
      if (!query.includes(' ') && query.length <= 50) {
        setShowMentions(true);
        setMentionQuery(query);
        const rect = textareaRef.current?.getBoundingClientRect();
        if (rect) setMentionPos({ top: rect.bottom - 60, left: rect.left + 20 });
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

  const handleKeyDown = (
    e: React.KeyboardEvent<HTMLTextAreaElement>,
    isStreaming: boolean,
    selectedSkill: any,
    setSelectedSkill: (s: any) => void,
    onSubmit: (prompt: string) => void,
    skills: any[],
  ) => {
    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
      e.preventDefault();
      if (!input.trim() || isStreaming) return;
      const prompt = input;
      setInput('');
      setInputHistory((prev) => [prompt, ...prev].slice(0, 50));
      setHistoryIndex(-1);
      onSubmit(prompt);
      return;
    }
    if (showSkillAutocomplete) {
      if (e.key === 'ArrowDown') { e.preventDefault(); setSkillAutocompleteIndex(i => Math.min(i + 1, 7)); return; }
      if (e.key === 'ArrowUp') { e.preventDefault(); setSkillAutocompleteIndex(i => Math.max(0, i - 1)); return; }
      if (e.key === 'Enter' || e.key === 'Tab') {
        e.preventDefault();
        const filtered = skills.filter(s => s.enabled !== false)
          .filter(s => !skillAutocompleteQuery || s.name.toLowerCase().includes(skillAutocompleteQuery.toLowerCase()))
          .slice(0, 8);
        const idx = skillAutocompleteIndex;
        const selected = filtered[idx];
        if (selected) {
          const cursor = textareaRef.current?.selectionStart || input.length;
          const beforeCursor = input.slice(0, cursor);
          const slashIdx = beforeCursor.lastIndexOf('/');
          if (slashIdx !== -1) {
            const afterCursor = input.slice(cursor);
            setInput(input.slice(0, slashIdx) + '/' + selected.name + ' ' + afterCursor);
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

  return {
    input, setInput,
    inputHistory, setInputHistory,
    historyIndex, setHistoryIndex,
    showSkillAutocomplete, setShowSkillAutocomplete,
    skillAutocompleteQuery, setSkillAutocompleteQuery,
    skillAutocompleteIndex, setSkillAutocompleteIndex,
    showMentions, setShowMentions,
    mentionQuery, mentionPos,
    textareaRef,
    handleInputChange,
    handleMentionSelect,
    handleKeyDown,
  };
}
