'use client';

import ReactMarkdown from 'react-markdown';
import remarkGfm from 'remark-gfm';
import { fetchSkillDetail, deleteSkill, exportSkill, invokeSkill } from '@/lib/api';
import { useAppStore, type Skill } from '@/lib/store';
import { useCallback, useEffect, useState } from 'react';

export function SkillDetailView({ skill, onBack }: { skill: Skill; onBack: () => void }) {
  const [detail, setDetail] = useState<Skill | null>(null);
  const [loading, setLoading] = useState(true);
  const setSkills = useAppStore((s) => s.setSkills);
  const setSkillEditorOpen = useAppStore((s) => s.setSkillEditorOpen);
  const setSkillDetail = useAppStore((s) => s.setSkillDetail);
  const addToast = useAppStore((s) => s.addToast);

  useEffect(() => {
    setLoading(true);
    fetchSkillDetail(skill.name)
      .then((d) => setDetail(d))
      .catch(() => setDetail(skill))
      .finally(() => setLoading(false));
  }, [skill.name, skill]);

  const handleEdit = () => {
    setSkillDetail(detail || skill);
    setSkillEditorOpen(true);
  };

  const handleDelete = async () => {
    if (!confirm(`Delete skill "${skill.name}"?`)) return;
    try {
      const res = await deleteSkill(skill.name);
      if (res.ok) {
        addToast({ type: 'success', message: `Deleted "${skill.name}"` });
        onBack();
      } else {
        addToast({ type: 'error', message: 'Failed to delete skill' });
      }
    } catch {
      addToast({ type: 'error', message: 'Failed to delete skill' });
    }
  };

  const handleExport = async () => {
    try {
      const blob = await exportSkill(skill.name);
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `${skill.name}.zip`;
      a.click();
      URL.revokeObjectURL(url);
      addToast({ type: 'success', message: `Exported "${skill.name}"` });
    } catch {
      addToast({ type: 'error', message: 'Export failed' });
    }
  };

  const handleInvoke = async () => {
    try {
      const res = await invokeSkill(skill.name);
      addToast({
        type: 'success',
        message: `Invoked "${skill.name}" (${res.mode})`,
      });
    } catch {
      addToast({ type: 'error', message: 'Invocation failed' });
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-40">
        <div className="h-5 w-5 animate-spin rounded-full border-2 border-primary border-t-transparent" />
      </div>
    );
  }

  const data = detail || skill;

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="p-3 border-b border-border">
        <div className="flex items-center gap-2 mb-1">
          <button
            onClick={onBack}
            className="text-xs text-muted hover:text-foreground transition"
          >
            ← Back
          </button>
        </div>
        <div className="flex items-center justify-between">
          <div>
            <h2 className="text-base font-semibold">{data.name}</h2>
            <p className="text-xs text-muted mt-0.5">{data.description}</p>
          </div>
          <div className="flex gap-1.5 shrink-0">
            <button onClick={handleInvoke} className="px-2 py-1 text-xs rounded bg-primary/10 text-primary hover:bg-primary/20 transition">
              ▶ Run
            </button>
            <button onClick={handleEdit} className="px-2 py-1 text-xs rounded bg-surface-hover hover:bg-surface-active transition">
              ✎ Edit
            </button>
            <button onClick={handleExport} className="px-2 py-1 text-xs rounded bg-surface-hover hover:bg-surface-active transition">
              ↓ Export
            </button>
            {data.source_type !== 'builtin' && (
              <button onClick={handleDelete} className="px-2 py-1 text-xs rounded bg-red-500/10 text-red-400 hover:bg-red-500/20 transition">
                ✕ Delete
              </button>
            )}
          </div>
        </div>
      </div>

      {/* Content: two-column layout */}
      <div className="flex-1 flex overflow-hidden">
        {/* Markdown preview */}
        <div className="flex-1 overflow-y-auto p-4 prose prose-sm prose-invert max-w-none">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>
            {data.body || '_No content._'}
          </ReactMarkdown>
        </div>

        {/* Metadata sidebar */}
        <div className="w-48 border-l border-border p-3 overflow-y-auto text-xs space-y-3">
          <MetaRow label="Run as" value={data.run_as} />
          <MetaRow label="Source" value={data.source_type || data.source} />
          <MetaRow label="Version" value={data.version} />
          <MetaRow label="Author" value={data.author} />
          <MetaRow label="Model" value={data.model} />
          <MetaRow label="License" value={data.license} />
          <MetaRow label="Enabled" value={data.enabled !== false ? 'Yes' : 'No'} />
          {data.allowed_tools && data.allowed_tools.length > 0 && (
            <div>
              <div className="text-muted mb-1">Allowed tools</div>
              <div className="flex flex-wrap gap-1">
                {data.allowed_tools.map((t) => (
                  <span key={t} className="px-1.5 py-0.5 rounded bg-surface-active text-[10px]">
                    {t}
                  </span>
                ))}
              </div>
            </div>
          )}
          {data.directory_files && data.directory_files.length > 0 && (
            <div>
              <div className="text-muted mb-1">Files</div>
              <ul className="space-y-0.5">
                {data.directory_files.map((f) => (
                  <li key={f} className="text-[10px] text-muted truncate">{f}</li>
                ))}
              </ul>
            </div>
          )}
          {data.path && (
            <div>
              <div className="text-muted mb-1">Path</div>
              <div className="text-[10px] break-all">{data.path}</div>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

function MetaRow({ label, value }: { label: string; value?: string | null }) {
  if (!value) return null;
  return (
    <div>
      <div className="text-muted">{label}</div>
      <div className="font-medium">{value}</div>
    </div>
  );
}
