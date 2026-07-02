'use client';

import { useState, useCallback } from 'react';
import { useAppStore } from '@/lib/store';

/**
 * Hook for input box state: text value, history, @mentions, /skill commands.
 */
export function useIdeInput() {
  const [input, setInput] = useState('');
  const [inputHistory, setInputHistory] = useState<string[]>([]);
  const [historyIndex, setHistoryIndex] = useState(-1);
  const [showSkillAutocomplete, setShowSkillAutocomplete] = useState(false);
  const [skillAutocompleteQuery, setSkillAutocompleteQuery] = useState('');
  const [skillAutocompleteIndex, setSkillAutocompleteIndex] = useState(0);
  const [selectedSkill, setSelectedSkill] = useState<string | undefined>(undefined);
  const [showMentions, setShowMentions] = useState(false);
  const [mentionQuery, setMentionQuery] = useState('');

  const skills = useAppStore((s) => s.skills);

  const handleInputChange = useCallback((e: React.ChangeEvent<HTMLTextAreaElement>) => {
    const value = e.target.value;
    setInput(value);

    const cursor = e.target.selectionStart;
    const beforeCursor = value.slice(0, cursor);

    // / slash-command detection for skills
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

    // @ mention detection
    const atIndex = beforeCursor.lastIndexOf('@');
    if (atIndex !== -1 && (atIndex === 0 || beforeCursor[atIndex - 1] === ' ' || beforeCursor[atIndex - 1] === '\n')) {
      const query = beforeCursor.slice(atIndex + 1);
      if (!query.includes(' ') && !query.includes('\n') && query.length <= 50) {
        setShowMentions(true);
        setMentionQuery(query);
        return;
      }
    }
    setShowMentions(false);
  }, []);

  const handleKeyDown = useCallback((e: React.KeyboardEvent<HTMLTextAreaElement>, onSend: () => void) => {
    if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) {
      e.preventDefault();
      if (input.trim()) onSend();
      return;
    }

    if (showSkillAutocomplete) {
      if (e.key === 'ArrowDown') { e.preventDefault(); setSkillAutocompleteIndex(i => Math.min(i + 1, skills.length - 1)); return; }
      if (e.key === 'ArrowUp') { e.preventDefault(); setSkillAutocompleteIndex(i => Math.max(0, i - 1)); return; }
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
  }, [input, inputHistory, historyIndex, showSkillAutocomplete, skills.length]);

  const clearInput = useCallback(() => {
    if (input.trim()) {
      setInputHistory((prev) => [input, ...prev].slice(0, 50));
      setHistoryIndex(-1);
    }
    setInput('');
    setSelectedSkill(undefined);
  }, [input]);

  return {
    input,
    setInput,
    inputHistory,
    historyIndex,
    showSkillAutocomplete,
    skillAutocompleteQuery,
    skillAutocompleteIndex,
    setSkillAutocompleteIndex,
    selectedSkill,
    setSelectedSkill,
    showMentions,
    mentionQuery,
    handleInputChange,
    handleKeyDown,
    clearInput,
  };
}
