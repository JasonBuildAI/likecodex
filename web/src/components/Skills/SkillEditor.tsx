'use client';

import { useState, useMemo } from 'react';
import dynamic from 'next/dynamic';
import { createSkill, updateSkill } from '@/lib/api';
import { useAppStore, type Skill } from '@/lib/store';

const MonacoEditor = dynamic(() => import('@monaco-editor/react').then((m) => m.default), {
  ssr: false,
  loading: () => <div className="flex items-center justify-center h-40 text-muted text-xs">Loading editor...</div>,
});

const NAME_RE = /^[a-z0-9][a-z0-9\-]{0,63}$/;

// Common tools available for selection
const AVAILABLE_TOOLS = [
  'read_file', 'write_file', 'edit_file', 'replace_in_file', 'create_file', 'delete_file',
  'run_command', 'execute_command', 'shell',
  'grep_search', 'codebase_search', 'file_search',
  'list_dir', 'web_search', 'web_fetch',
  'git_diff', 'git_log', 'git_status', 'git_commit', 'git_push', 'git_pull',
  'github_pr', 'github_issue',
  'run_skill',
];

export function SkillEditor({ skill, onClose }: { skill: Skill | null; onClose: () => void }) {
  const isEdit = !!skill;
  const [name, setName] = useState(skill?.name || '');
  const [description, setDescription] = useState(skill?.description || '');
  const [runAs, setRunAs] = useState(skill?.run_as || 'inline');
  const [model, setModel] = useState(skill?.model || '');
  const [author, setAuthor] = useState(skill?.author || '');
  const [version, setVersion] = useState(skill?.version || '0.1.0');
  const [allowedTools, setAllowedTools] = useState<string[]>(skill?.allowed_tools || []);
  const [body, setBody] = useState(skill?.body || '');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [toolSearch, setToolSearch] = useState('');

  const setSkills = useAppStore((s) => s.setSkills);
  const addToast = useAppStore((s) => s.addToast);
  const skills = useAppStore((s) => s.skills);

  const nameValid = !isEdit ? NAME_RE.test(name) : true;

  const filteredTools = useMemo(() => {
    if (!toolSearch) return AVAILABLE_TOOLS;
    const q = toolSearch.toLowerCase();
    return AVAILABLE_TOOLS.filter((t) => t.toLowerCase().includes(q));
  }, [toolSearch]);

  const toggleTool = (tool: string) => {
    setAllowedTools((prev) =>
      prev.includes(tool) ? prev.filter((t) => t !== tool) : [...prev, tool]
    );
  };

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
          allowed_tools: allowedTools,
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
          version: version || undefined,
          allowed_tools: allowedTools,
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
      <div className="flex-1 flex overflow-hidden">
        {/* Left: Basic fields */}
        <div className="w-2/3 flex flex-col min-w-0">
          {/* Inline fields */}
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
            <div className="flex gap-3">
              <div className="flex-1">
                <label className="text-[10px] text-muted block mb-0.5">Version</label>
                <input
                  value={version}
                  onChange={(e) => setVersion(e.target.value)}
                  placeholder="0.1.0"
                  className="w-full px-2 py-1 text-xs rounded bg-surface border border-border focus:border-primary outline-none"
                />
              </div>
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
        </div>

        {/* Right: Allowed tools */}
        <div className="w-1/3 border-l border-border flex flex-col min-w-0">
          <div className="p-3 border-b border-border">
            <label className="text-[10px] text-muted block mb-1">Allowed Tools ({allowedTools.length} selected)</label>
            <input
              value={toolSearch}
              onChange={(e) => setToolSearch(e.target.value)}
              placeholder="Search tools..."
              className="w-full px-2 py-1 text-[10px] rounded bg-surface border border-border focus:border-primary outline-none"
            />
          </div>
          <div className="flex-1 overflow-y-auto p-2 space-y-0.5">
            {filteredTools.map((tool) => (
              <label
                key={tool}
                className="flex items-center gap-2 px-2 py-1 rounded hover:bg-accent/5 cursor-pointer transition-colors"
              >
                <input
                  type="checkbox"
                  checked={allowedTools.includes(tool)}
                  onChange={() => toggleTool(tool)}
                  className="h-3 w-3 rounded border-border accent-primary"
                />
                <span className="text-[11px] font-medium">{tool}</span>
              </label>
            ))}
          </div>
          <div className="px-3 py-1.5 border-t border-border text-[10px] text-muted">
            {allowedTools.length === 0 ? 'All tools allowed' : `${allowedTools.length} tool(s) restricted`}
          </div>
        </div>
      </div>

      {/* Footer */}
      <div className="px-3 py-1.5 border-t border-border flex justify-between text-[10px] text-muted">
        <span>{body.length} characters</span>
        <span>{body.split('\n').length} lines</span>
      </div>
    </div>
  );
}
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
