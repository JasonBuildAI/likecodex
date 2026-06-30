'use client';

import { useState } from 'react';
import { installSkill } from '@/lib/api';
import { useAppStore } from '@/lib/store';

const FEATURED_SKILLS = [
  { name: 'code-review', url: 'https://github.com/agentskills/code-review', description: 'Comprehensive code review with best practices' },
  { name: 'testing-patterns', url: 'https://github.com/agentskills/testing-patterns', description: 'Test-driven development patterns' },
  { name: 'architecture', url: 'https://github.com/agentskills/architecture', description: 'Software architecture design patterns' },
  { name: 'docker', url: 'https://github.com/agentskills/docker', description: 'Docker and containerization best practices' },
];

export function SkillInstallDialog({ onClose }: { onClose: () => void }) {
  const [url, setUrl] = useState('');
  const [installing, setInstalling] = useState(false);
  const [error, setError] = useState('');
  const addToast = useAppStore((s) => s.addToast);
  const setSkills = useAppStore((s) => s.setSkills);

  const handleInstall = async (installUrl: string) => {
    if (!installUrl.trim()) return;
    setInstalling(true);
    setError('');
    try {
      const res = await installSkill(installUrl);
      if (res.ok) {
        addToast({ type: 'success', message: 'Skill installed successfully' });
        // Reload skills
        const { fetchSkillsList } = await import('@/lib/api');
        const updated = await fetchSkillsList();
        setSkills(updated);
        onClose();
      } else {
        setError(res.skill === null ? 'Installation failed' : String(res));
      }
    } catch (e) {
      setError(String(e));
    } finally {
      setInstalling(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={onClose}>
      <div
        className="bg-surface rounded-lg border border-border w-full max-w-md shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="p-4 border-b border-border">
          <div className="flex items-center justify-between">
            <h3 className="text-sm font-semibold">Install Skill</h3>
            <button onClick={onClose} className="text-muted hover:text-foreground text-lg leading-none">
              ×
            </button>
          </div>
        </div>

        {/* URL input */}
        <div className="p-4 space-y-3">
          <div>
            <label className="text-xs text-muted block mb-1">Git Repository URL</label>
            <div className="flex gap-2">
              <input
                value={url}
                onChange={(e) => setUrl(e.target.value)}
                placeholder="https://github.com/user/skill-name"
                className="flex-1 px-2 py-1.5 text-xs rounded bg-background border border-border focus:border-primary outline-none"
                onKeyDown={(e) => e.key === 'Enter' && handleInstall(url)}
              />
              <button
                onClick={() => handleInstall(url)}
                disabled={installing || !url.trim()}
                className="px-3 py-1.5 text-xs rounded bg-primary text-white hover:bg-primary/80 transition disabled:opacity-50"
              >
                {installing ? '...' : 'Install'}
              </button>
            </div>
            {error && <p className="text-[10px] text-red-400 mt-1">{error}</p>}
          </div>

          {/* Featured skills */}
          <div>
            <div className="text-xs text-muted mb-2">Featured Skills</div>
            <div className="space-y-1.5">
              {FEATURED_SKILLS.map((fs) => (
                <div
                  key={fs.name}
                  className="flex items-center justify-between p-2 rounded border border-border/50 hover:border-border transition"
                >
                  <div>
                    <div className="text-xs font-medium">{fs.name}</div>
                    <div className="text-[10px] text-muted">{fs.description}</div>
                  </div>
                  <button
                    onClick={() => handleInstall(fs.url)}
                    disabled={installing}
                    className="px-2 py-0.5 text-[10px] rounded bg-surface-hover hover:bg-surface-active transition disabled:opacity-50 shrink-0"
                  >
                    Install
                  </button>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
