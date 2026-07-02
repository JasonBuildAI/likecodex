'use client';

import { useState, useEffect, useCallback } from 'react';
import { useAppStore } from '@/lib/store';

const API_BASE = process.env.NEXT_PUBLIC_API_BASE || '/api';

interface MarketplaceSkill {
  name: string;
  description: string;
  version: string;
  author: string;
  download_url: string;
  tags: string[];
  license: string;
  rating?: number;
  downloads?: number;
}

export function SkillMarketplacePanel({ onClose }: { onClose: () => void }) {
  const [skills, setSkills] = useState<MarketplaceSkill[]>([]);
  const [loading, setLoading] = useState(true);
  const [searchQuery, setSearchQuery] = useState('');
  const [error, setError] = useState('');
  const [installing, setInstalling] = useState<string | null>(null);
  const addToast = useAppStore((s) => s.addToast);
  const setSkillsStore = useAppStore((s) => s.setSkills);

  const fetchMarketplace = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const resp = await fetch(`${API_BASE}/api/ide/skills/marketplace?q=${encodeURIComponent(searchQuery)}`);
      if (!resp.ok) throw new Error(`HTTP ${resp.status}`);
      const data = await resp.json();
      setSkills(data.skills || []);
    } catch (err) {
      setError(String(err));
      setSkills([]);
    } finally {
      setLoading(false);
    }
  }, [searchQuery]);

  useEffect(() => {
    fetchMarketplace();
  }, [fetchMarketplace]);

  const handleInstall = async (skill: MarketplaceSkill) => {
    setInstalling(skill.name);
    try {
      const resp = await fetch(`${API_BASE}/api/ide/skills/marketplace/install`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name: skill.name, download_url: skill.download_url }),
      });
      const data = await resp.json();
      if (data.ok) {
        addToast({ type: 'success', message: `Installed "${skill.name}"` });
        // Reload skills
        const { fetchSkillsList } = await import('@/lib/api');
        const updated = await fetchSkillsList();
        setSkillsStore(updated);
      } else {
        addToast({ type: 'error', message: data.error || `Failed to install ${skill.name}` });
      }
    } catch (err) {
      addToast({ type: 'error', message: String(err) });
    } finally {
      setInstalling(null);
    }
  };

  const filteredSkills = skills.filter(
    (s) =>
      !searchQuery ||
      s.name.toLowerCase().includes(searchQuery.toLowerCase()) ||
      s.description.toLowerCase().includes(searchQuery.toLowerCase()) ||
      s.tags?.some((t) => t.toLowerCase().includes(searchQuery.toLowerCase()))
  );

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="p-3 border-b border-border flex items-center justify-between">
        <h2 className="text-sm font-semibold">Skills Marketplace</h2>
        <button onClick={onClose} className="text-muted hover:text-foreground transition-colors text-lg leading-none">
          &times;
        </button>
      </div>

      {/* Search */}
      <div className="p-3 border-b border-border">
        <div className="relative">
          <input
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Search skills by name, description, or tags..."
            className="w-full px-3 py-2 text-xs rounded-lg bg-background border border-border focus:border-primary outline-none pl-8"
          />
          <svg className="absolute left-2.5 top-1/2 -translate-y-1/2 h-3.5 w-3.5 text-muted" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
        </div>
      </div>

      {/* Content */}
      <div className="flex-1 overflow-y-auto p-3">
        {loading ? (
          <div className="flex items-center justify-center h-32">
            <div className="h-5 w-5 animate-spin rounded-full border-2 border-primary border-t-transparent" />
          </div>
        ) : error ? (
          <div className="text-center py-8">
            <div className="text-lg mb-2">📦</div>
            <p className="text-xs text-muted mb-2">{error}</p>
            <button
              onClick={fetchMarketplace}
              className="px-3 py-1.5 text-xs rounded bg-primary text-white hover:bg-primary/80 transition"
            >
              Retry
            </button>
          </div>
        ) : filteredSkills.length === 0 ? (
          <div className="text-center py-8">
            <div className="text-lg mb-2">🔍</div>
            <p className="text-xs text-muted">
              {searchQuery ? 'No skills match your search.' : 'No skills available in the marketplace.'}
            </p>
          </div>
        ) : (
          <div className="space-y-2">
            {filteredSkills.map((skill) => (
              <div
                key={skill.name}
                className="rounded-lg border border-border/60 p-3 hover:border-border transition-colors"
              >
                <div className="flex items-start justify-between gap-3">
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2 mb-1">
                      <h3 className="text-sm font-medium">{skill.name}</h3>
                      <span className="text-[10px] text-muted bg-accent/10 px-1.5 py-0.5 rounded">
                        v{skill.version}
                      </span>
                    </div>
                    <p className="text-[11px] text-muted line-clamp-2">{skill.description}</p>
                    <div className="flex items-center gap-2 mt-1.5">
                      {skill.author && (
                        <span className="text-[10px] text-muted/60">by {skill.author}</span>
                      )}
                      {skill.license && (
                        <span className="text-[10px] text-muted/60">{skill.license}</span>
                      )}
                      {skill.downloads && (
                        <span className="text-[10px] text-muted/60">{skill.downloads} downloads</span>
                      )}
                    </div>
                    {skill.tags && skill.tags.length > 0 && (
                      <div className="flex flex-wrap gap-1 mt-1.5">
                        {skill.tags.map((tag) => (
                          <span key={tag} className="px-1.5 py-0.5 text-[9px] rounded bg-accent/10 text-muted">
                            {tag}
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                  <button
                    onClick={() => handleInstall(skill)}
                    disabled={installing === skill.name}
                    className="shrink-0 px-3 py-1.5 text-[10px] rounded bg-primary text-white hover:bg-primary/80 transition disabled:opacity-50"
                  >
                    {installing === skill.name ? '...' : 'Install'}
                  </button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Footer */}
      <div className="px-3 py-1.5 border-t border-border text-[10px] text-muted flex justify-between">
        <span>{filteredSkills.length} skills</span>
        <button
          onClick={fetchMarketplace}
          className="hover:text-foreground transition-colors"
        >
          Refresh
        </button>
      </div>
    </div>
  );
}
