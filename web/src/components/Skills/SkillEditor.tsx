'use client';

import { useState } from 'react';
import dynamic from 'next/dynamic';
import { createSkill, updateSkill } from '@/lib/api';
import { useAppStore, type Skill } from '@/lib/store';

const MonacoEditor = dynamic(() => import('@monaco-editor/react').then((m) => m.default), {
  ssr: false,
  loading: () => <div className="flex items-center justify-center h-40 text-muted text-xs">Loading editor...</div>,
});

const NAME_RE = /^[a-z0-9][a-z0-9\-]{0,63}$/;

export function SkillEditor({ skill, onClose }: { skill: Skill | null; onClose: () => void }) {
  const isEdit = !!skill;
  const [name, setName] = useState(skill?.name || '');
  const [description, setDescription] = useState(skill?.description || '');
  const [runAs, setRunAs] = useState(skill?.run_as || 'inline');
  const [model, setModel] = useState(skill?.model || '');
  const [author, setAuthor] = useState(skill?.author || '');
  const [body, setBody] = useState(skill?.body || '');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const setSkills = useAppStore((s) => s.setSkills);
  const addToast = useAppStore((s) => s.addToast);
  const skills = useAppStore((s) => s.skills);

  const nameValid = !isEdit ? NAME_RE.test(name) : true;

  const handleSave = async () => {
    if (!isEdit && !nameValid) {
      setError('Name must be 1-64 lowercase alphanumeric chars or hyphens');
      return;
    }
    setSaving(true);
    setError('');
    try {
      if (isEdit) {
        const res = await updateSkill({
          name: skill!.name,
          description,
          body,
          run_as: runAs,
          model: model || null,
        });
        if (res.ok) {
          addToast({ type: 'success', message: `Updated "${name}"` });
        } else {
          setError('Update failed');
          return;
        }
      } else {
        const res = await createSkill({
          name,
          description,
          body,
          run_as: runAs,
          model: model || undefined,
          author: author || undefined,
        });
        if (res.ok) {
          addToast({ type: 'success', message: `Created "${name}"` });
        } else {
          setError('Create failed');
          return;
        }
      }
      // Reload skills
      const { fetchSkillsList } = await import('@/lib/api');
      const updated = await fetchSkillsList();
      setSkills(updated);
      onClose();
    } catch (e) {
      setError(String(e));
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="p-3 border-b border-border flex items-center justify-between">
        <h2 className="text-sm font-semibold">
          {isEdit ? `Edit: ${skill!.name}` : 'Create New Skill'}
        </h2>
        <div className="flex gap-2">
          <button
            onClick={onClose}
            className="px-2 py-1 text-xs rounded bg-surface-hover hover:bg-surface-active transition"
          >
            Cancel
          </button>
          <button
            onClick={handleSave}
            disabled={saving || (!isEdit && !nameValid)}
            className="px-3 py-1 text-xs rounded bg-primary text-white hover:bg-primary/80 transition disabled:opacity-50"
          >
            {saving ? 'Saving...' : 'Save'}
          </button>
        </div>
      </div>

      {error && (
        <div className="px-3 py-1.5 text-xs text-red-400 bg-red-500/10 border-b border-red-500/20">
          {error}
        </div>
      )}

      {/* Form fields */}
      <div className="p-3 border-b border-border space-y-2">
        {!isEdit && (
          <div>
            <label className="text-[10px] text-muted block mb-0.5">Name</label>
            <input
              value={name}
              onChange={(e) => setName(e.target.value.toLowerCase().replace(/[^a-z0-9\-]/g, ''))}
              placeholder="my-skill"
              className={`w-full px-2 py-1 text-xs rounded bg-surface border ${
                nameValid ? 'border-border' : 'border-red-500'
              } focus:border-primary outline-none`}
            />
            {!nameValid && name.length > 0 && (
              <span className="text-[9px] text-red-400">Invalid name format</span>
            )}
          </div>
        )}
        <div className="flex gap-3">
          <div className="flex-1">
            <label className="text-[10px] text-muted block mb-0.5">Description</label>
            <input
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              placeholder="What does this skill do?"
              className="w-full px-2 py-1 text-xs rounded bg-surface border border-border focus:border-primary outline-none"
            />
          </div>
          <div className="w-24">
            <label className="text-[10px] text-muted block mb-0.5">Run as</label>
            <select
              value={runAs}
              onChange={(e) => setRunAs(e.target.value)}
              className="w-full px-2 py-1 text-xs rounded bg-surface border border-border focus:border-primary outline-none"
            >
              <option value="inline">inline</option>
              <option value="subagent">subagent</option>
            </select>
          </div>
        </div>
        <div className="flex gap-3">
          <div className="flex-1">
            <label className="text-[10px] text-muted block mb-0.5">Model (optional)</label>
            <input
              value={model}
              onChange={(e) => setModel(e.target.value)}
              placeholder="deepseek-v4-pro"
              className="w-full px-2 py-1 text-xs rounded bg-surface border border-border focus:border-primary outline-none"
            />
          </div>
          {!isEdit && (
            <div className="flex-1">
              <label className="text-[10px] text-muted block mb-0.5">Author (optional)</label>
              <input
                value={author}
                onChange={(e) => setAuthor(e.target.value)}
                placeholder="Your name"
                className="w-full px-2 py-1 text-xs rounded bg-surface border border-border focus:border-primary outline-none"
              />
            </div>
          )}
        </div>
      </div>

      {/* Monaco editor for body */}
      <div className="flex-1 min-h-0">
        <MonacoEditor
          value={body}
          onChange={(v) => setBody(v || '')}
          language="markdown"
          theme="vs-dark"
          options={{
            minimap: { enabled: false },
            fontSize: 13,
            lineNumbers: 'on',
            wordWrap: 'on',
            scrollBeyondLastLine: false,
            padding: { top: 8 },
          }}
        />
      </div>

      {/* Footer */}
      <div className="px-3 py-1.5 border-t border-border flex justify-between text-[10px] text-muted">
        <span>{body.length} characters</span>
        <span>{body.split('\n').length} lines</span>
      </div>
    </div>
  );
}
