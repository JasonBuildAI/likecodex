'use client';

import { useCallback, useEffect, useMemo, useState } from 'react';
import { fetchSkillsList, toggleSkill, reloadSkills } from '@/lib/api';
import { useAppStore, type Skill } from '@/lib/store';

export function SkillPanel() {
  const skills = useAppStore((s) => s.skills);
  const setSkills = useAppStore((s) => s.setSkills);
  const setSkillDetail = useAppStore((s) => s.setSkillDetail);
  const setSkillEditorOpen = useAppStore((s) => s.setSkillEditorOpen);
  const searchQuery = useAppStore((s) => s.skillSearchQuery);
  const setSearchQuery = useAppStore((s) => s.setSkillSearchQuery);
  const filter = useAppStore((s) => s.skillFilter);
  const setFilter = useAppStore((s) => s.setSkillFilter);
  const addToast = useAppStore((s) => s.addToast);
  const [loading, setLoading] = useState(false);

  const loadSkills = useCallback(async () => {
    setLoading(true);
    try {
      const data = await fetchSkillsList();
      setSkills(data);
    } catch {
      // silently fail
    } finally {
      setLoading(false);
    }
  }, [setSkills]);

  useEffect(() => {
    if (skills.length === 0) loadSkills();
  }, [skills.length, loadSkills]);

  const filtered = useMemo(() => {
    let result = skills;
    if (filter !== 'all') {
      result = result.filter((s) => s.source_type === filter || s.source === filter);
    }
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      result = result.filter(
        (s) =>
          s.name.toLowerCase().includes(q) ||
          s.description.toLowerCase().includes(q)
      );
    }
    return result;
  }, [skills, filter, searchQuery]);

  const handleToggle = async (name: string) => {
    try {
      const res = await toggleSkill(name);
      setSkills(skills.map((s) => (s.name === name ? { ...s, enabled: res.enabled } : s)));
    } catch {
      addToast({ type: 'error', message: 'Failed to toggle skill' });
    }
  };

  const handleReload = async () => {
    setLoading(true);
    try {
      const res = await reloadSkills();
      setSkills(res.skills || []);
      addToast({ type: 'success', message: `Reloaded ${res.skills?.length || 0} skills` });
    } catch {
      addToast({ type: 'error', message: 'Failed to reload skills' });
    } finally {
      setLoading(false);
    }
  };

  const handleAddNew = () => {
    setSkillEditorOpen(true);
    setSkillDetail(null);
  };

  const filters: Array<{ key: 'all' | 'builtin' | 'project' | 'home'; label: string }> = [
    { key: 'all', label: 'All' },
    { key: 'builtin', label: 'Built-in' },
    { key: 'project', label: 'Project' },
    { key: 'home', label: 'Home' },
  ];

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="p-3 border-b border-border">
        <div className="flex items-center justify-between mb-2">
          <h2 className="text-sm font-semibold">Skills</h2>
          <div className="flex gap-1">
            <button
              onClick={handleAddNew}
              className="px-2 py-0.5 text-xs rounded bg-primary/10 text-primary hover:bg-primary/20 transition"
              title="Create new skill"
            >
              + New
            </button>
            <button
              onClick={handleReload}
              className="px-2 py-0.5 text-xs rounded bg-surface-hover hover:bg-surface-active transition"
              title="Reload skills"
            >
              ↻
            </button>
          </div>
        </div>

        {/* Search */}
        <input
          type="text"
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          placeholder="Search skills..."
          className="w-full px-2 py-1 text-xs rounded bg-surface border border-border focus:border-primary outline-none mb-2"
        />

        {/* Filter tabs */}
        <div className="flex gap-1">
          {filters.map((f) => (
            <button
              key={f.key}
              onClick={() => setFilter(f.key)}
              className={`px-2 py-0.5 text-[10px] rounded transition ${
                filter === f.key
                  ? 'bg-primary text-white'
                  : 'bg-surface hover:bg-surface-hover text-muted'
              }`}
            >
              {f.label}
            </button>
          ))}
        </div>
      </div>

      {/* Skills list */}
      <div className="flex-1 overflow-y-auto p-2 space-y-1.5">
        {loading ? (
          <div className="flex items-center gap-2 text-xs text-muted py-4 justify-center">
            <div className="h-3 w-3 animate-spin rounded-full border border-primary border-t-transparent" />
            Loading...
          </div>
        ) : filtered.length === 0 ? (
          <div className="text-xs text-muted text-center py-4">
            {searchQuery ? 'No matching skills.' : 'No skills available.'}
          </div>
        ) : (
          filtered.map((skill) => (
            <SkillCard
              key={skill.name}
              skill={skill}
              onToggle={handleToggle}
              onClick={() => setSkillDetail(skill)}
            />
          ))
        )}
      </div>
    </div>
  );
}

function SkillCard({
  skill,
  onToggle,
  onClick,
}: {
  skill: Skill;
  onToggle: (name: string) => void;
  onClick: () => void;
}) {
  const enabled = skill.enabled !== false;

  return (
    <div
      className={`rounded border p-2.5 cursor-pointer transition group ${
        enabled
          ? 'border-border hover:border-primary/40 hover:bg-surface-hover'
          : 'border-border/50 opacity-50'
      }`}
      onClick={onClick}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex-1 min-w-0">
          <div className="flex items-center gap-1.5">
            <span className="text-sm font-medium truncate">{skill.name}</span>
            {skill.source_type && (
              <span className="text-[9px] px-1 py-0 rounded bg-surface-active text-muted shrink-0">
                {skill.source_type}
              </span>
            )}
            {skill.version && (
              <span className="text-[9px] text-muted">v{skill.version}</span>
            )}
          </div>
          <p className="text-xs text-muted mt-0.5 line-clamp-2">{skill.description}</p>
          {skill.run_as && (
            <span className="inline-block text-[9px] px-1 mt-1 rounded bg-primary/10 text-primary">
              {skill.run_as}
            </span>
          )}
        </div>
        <button
          onClick={(e) => {
            e.stopPropagation();
            onToggle(skill.name);
          }}
          className={`w-8 h-4 rounded-full transition relative shrink-0 mt-0.5 ${
            enabled ? 'bg-primary' : 'bg-surface-active'
          }`}
          title={enabled ? 'Disable' : 'Enable'}
        >
          <div
            className={`absolute top-0.5 w-3 h-3 rounded-full bg-white transition-all ${
              enabled ? 'left-4.5' : 'left-0.5'
            }`}
            style={{ left: enabled ? '18px' : '2px' }}
          />
        </button>
      </div>
    </div>
  );
}
