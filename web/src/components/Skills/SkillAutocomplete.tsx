'use client';

import { useEffect, useRef } from 'react';
import type { Skill } from '@/lib/store';

interface SkillAutocompleteProps {
  skills: Skill[];
  query: string;
  visible: boolean;
  selectedIndex: number;
  onSelect: (skill: Skill) => void;
}

export function SkillAutocomplete({
  skills,
  query,
  visible,
  selectedIndex,
  onSelect,
}: SkillAutocompleteProps) {
  const listRef = useRef<HTMLDivElement>(null);

  const filtered = skills.filter((s) => {
    if (s.enabled === false) return false;
    if (!query) return true;
    return s.name.toLowerCase().includes(query.toLowerCase());
  }).slice(0, 8);

  useEffect(() => {
    if (listRef.current && selectedIndex >= 0) {
      const items = listRef.current.querySelectorAll('[data-skill-item]');
      items[selectedIndex]?.scrollIntoView({ block: 'nearest' });
    }
  }, [selectedIndex]);

  if (!visible || filtered.length === 0) return null;

  return (
    <div
      ref={listRef}
      className="absolute bottom-full left-0 right-0 mb-1 bg-surface border border-border rounded-lg shadow-xl overflow-hidden z-50 max-h-64 overflow-y-auto"
    >
      <div className="px-2 py-1 text-[10px] text-muted border-b border-border/50">
        Skills ({filtered.length})
      </div>
      {filtered.map((skill, i) => (
        <button
          key={skill.name}
          data-skill-item
          onClick={() => onSelect(skill)}
          className={`w-full text-left px-3 py-2 flex items-center gap-2 transition ${
            i === selectedIndex ? 'bg-primary/10' : 'hover:bg-surface-hover'
          }`}
        >
          <span className="text-xs font-medium">/{skill.name}</span>
          <span className="text-[10px] text-muted truncate flex-1">{skill.description}</span>
          {skill.source_type && (
            <span className="text-[9px] px-1 py-0 rounded bg-surface-active text-muted shrink-0">
              {skill.source_type}
            </span>
          )}
        </button>
      ))}
    </div>
  );
}
