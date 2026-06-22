'use client';

/**
 * IDESettingsPanel — Full-screen settings panel with categories.
 * This is a modal overlay that shows all IDE settings grouped by category.
 * Includes editor, AI, terminal, git, theme settings, and a keybinding editor.
 */

import { useState, useEffect, useCallback } from 'react';
import type { SettingsCategory } from './types';
import { KeybindingEditor } from './KeybindingEditor';
import { useTheme } from './useTheme';

type Tab = 'general' | 'editor' | 'ai' | 'terminal' | 'git' | 'theme' | 'keybindings' | 'extensions';

interface ExtensionInfo {
  id: string;
  name: string;
  version: string;
  description: string;
  enabled: boolean;
}

export function IDESettingsPanel({ open, onClose }: { open: boolean; onClose: () => void }) {
  const [activeTab, setActiveTab] = useState<Tab>('general');
  const [categories, setCategories] = useState<SettingsCategory[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [extensions, setExtensions] = useState<ExtensionInfo[]>([]);
  const { theme, setTheme, accentColor, setAccentColor } = useTheme();

  const loadSettings = useCallback(async () => {
    setLoading(true);
    try {
      const resp = await fetch('/api/ide/settings/categories');
      if (resp.ok) {
        const data = await resp.json();
        setCategories(data.categories || []);
      }
    } catch {
      // Best-effort
    } finally {
      setLoading(false);
    }
  }, []);

  const loadExtensions = useCallback(async () => {
    try {
      const resp = await fetch('/api/ide/extensions/list');
      if (resp.ok) {
        const data = await resp.json();
        setExtensions(data || []);
      }
    } catch {
      // Best-effort
    }
  }, []);

  useEffect(() => {
    if (open) {
      loadSettings();
      loadExtensions();
    }
  }, [open, loadSettings, loadExtensions]);

  const handleSettingChange = useCallback(async (key: string, value: unknown) => {
    setSaving(true);
    try {
      await fetch('/api/ide/settings', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ key, value }),
      });
      // Update local state
      setCategories((prev) =>
        prev.map((cat) => ({
          ...cat,
          settings: cat.settings.map((s) =>
            s.id === key ? { ...s, value } : s
          ),
        }))
      );
    } catch {
      // Best-effort
    } finally {
      setSaving(false);
    }
  }, []);

  const handleResetSetting = useCallback(async (key: string) => {
    setSaving(true);
    try {
      await fetch('/api/ide/settings/reset', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ key }),
      });
      loadSettings();
    } catch {
      // Best-effort
    } finally {
      setSaving(false);
    }
  }, [loadSettings]);

  const tabs: { id: Tab; label: string; icon: string }[] = [
    { id: 'general', label: '通用', icon: '⚙' },
    { id: 'editor', label: '编辑器', icon: '📝' },
    { id: 'ai', label: 'AI 模型', icon: '🤖' },
    { id: 'terminal', label: '终端', icon: '⬛' },
    { id: 'git', label: 'Git', icon: '🔀' },
    { id: 'theme', label: '主题', icon: '🎨' },
    { id: 'keybindings', label: '快捷键', icon: '⌨' },
    { id: 'extensions', label: '扩展', icon: '📦' },
  ];

  if (!open) return null;

  const getCategory = (catId: string) => categories.find((c) => c.id === catId);

  const renderSetting = (setting: SettingsCategory['settings'][0]) => {
    const value = setting.value;
    const isModified = JSON.stringify(value) !== JSON.stringify(setting.default);

    return (
      <div key={setting.id} className="py-2 border-b border-border/30 last:border-0">
        <div className="flex items-center justify-between mb-1">
          <div>
            <label className="text-xs font-medium text-foreground">{setting.label}</label>
            <p className="text-[10px] text-muted">{setting.description}</p>
          </div>
          {isModified && (
            <button
              onClick={() => handleResetSetting(setting.id)}
              className="text-[10px] text-muted hover:text-foreground"
              title="Reset to default"
            >
              ↺
            </button>
          )}
        </div>
        <div className="mt-1">
          {setting.type === 'boolean' && (
            <button
              onClick={() => handleSettingChange(setting.id, !value)}
              className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors ${
                value ? 'bg-primary' : 'bg-accent/30'
              }`}
            >
              <span
                className={`inline-block h-3.5 w-3.5 transform rounded-full bg-white transition-transform ${
                  value ? 'translate-x-4.5' : 'translate-x-0.5'
                }`}
              />
            </button>
          )}
          {setting.type === 'number' && (
            <input
              type="number"
              value={value as number}
              onChange={(e) => handleSettingChange(setting.id, parseFloat(e.target.value))}
              className="w-24 rounded border border-border bg-background px-2 py-1 text-xs focus:outline-none focus:border-primary"
            />
          )}
          {setting.type === 'string' && (
            <input
              type="text"
              value={value as string}
              onChange={(e) => handleSettingChange(setting.id, e.target.value)}
              className="w-full rounded border border-border bg-background px-2 py-1 text-xs focus:outline-none focus:border-primary"
            />
          )}
          {setting.type === 'select' && (
            <select
              value={value as string}
              onChange={(e) => handleSettingChange(setting.id, e.target.value)}
              className="rounded border border-border bg-background px-2 py-1 text-xs focus:outline-none focus:border-primary"
            >
              {setting.options?.map((opt) => (
                <option key={opt} value={opt}>{opt}</option>
              ))}
            </select>
          )}
        </div>
      </div>
    );
  };

  return (
    <div className="fixed inset-0 z-[9999] flex items-center justify-center bg-black/50" onClick={onClose}>
      <div
        className="w-[700px] h-[500px] max-w-[90vw] max-h-[80vh] bg-surface border border-border rounded-xl shadow-2xl flex flex-col overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Header */}
        <div className="flex items-center justify-between px-4 py-3 border-b border-border shrink-0">
          <h2 className="text-sm font-semibold">Settings</h2>
          <div className="flex items-center gap-2">
            {saving && <span className="text-[10px] text-muted">Saving...</span>}
            <button onClick={onClose} className="text-muted hover:text-foreground text-sm">✕</button>
          </div>
        </div>

        {/* Body: sidebar tabs + content */}
        <div className="flex flex-1 min-h-0">
          {/* Tab sidebar */}
          <div className="w-36 border-r border-border bg-surface/50 overflow-y-auto shrink-0">
            {tabs.map((tab) => (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id)}
                className={`w-full text-left px-3 py-2 text-xs flex items-center gap-2 transition-colors ${
                  activeTab === tab.id ? 'bg-primary/10 text-primary border-l-2 border-primary' : 'hover:bg-accent/5 border-l-2 border-transparent'
                }`}
              >
                <span>{tab.icon}</span>
                <span>{tab.label}</span>
              </button>
            ))}
          </div>

          {/* Content area */}
          <div className="flex-1 overflow-y-auto p-4 min-w-0">
            {loading ? (
              <div className="text-xs text-muted">Loading settings...</div>
            ) : (
              <>
                {/* General / Editor / Terminal / Git / AI — all use category-based rendering */}
                {(activeTab === 'general' || activeTab === 'editor' || activeTab === 'ai' || activeTab === 'terminal' || activeTab === 'git') && (
                  <div>
                    {getCategory(activeTab === 'general' ? 'theme' : activeTab)?.settings.map(renderSetting) || (
                      <div className="text-xs text-muted">No settings in this category.</div>
                    )}
                  </div>
                )}

                {/* Theme tab */}
                {activeTab === 'theme' && (
                  <div className="space-y-4">
                    {/* Theme mode */}
                    <div>
                      <label className="block text-xs font-medium mb-2">Color Theme</label>
                      <div className="flex gap-2">
                        <button
                          onClick={() => setTheme('dark')}
                          className={`flex-1 rounded-lg px-4 py-3 text-xs font-medium transition-colors ${
                            theme === 'dark' ? 'bg-primary text-white' : 'bg-accent/10 hover:bg-accent/20'
                          }`}
                        >
                          🌙 Dark
                        </button>
                        <button
                          onClick={() => setTheme('light')}
                          className={`flex-1 rounded-lg px-4 py-3 text-xs font-medium transition-colors ${
                            theme === 'light' ? 'bg-primary text-white' : 'bg-accent/10 hover:bg-accent/20'
                          }`}
                        >
                          ☀ Light
                        </button>
                      </div>
                    </div>
                    {/* Accent color */}
                    <div>
                      <label className="block text-xs font-medium mb-2">Accent Color</label>
                      <div className="flex items-center gap-2">
                        <input
                          type="color"
                          value={accentColor}
                          onChange={(e) => setAccentColor(e.target.value)}
                          className="h-8 w-12 rounded border border-border cursor-pointer"
                        />
                        <input
                          type="text"
                          value={accentColor}
                          onChange={(e) => setAccentColor(e.target.value)}
                          className="flex-1 rounded border border-border bg-background px-2 py-1 text-xs font-mono"
                        />
                      </div>
                    </div>
                    {/* Theme settings from backend */}
                    {getCategory('theme')?.settings.map(renderSetting)}
                  </div>
                )}

                {/* Keybindings tab */}
                {activeTab === 'keybindings' && <KeybindingEditor />}

                {/* Extensions tab */}
                {activeTab === 'extensions' && (
                  <div>
                    <div className="flex items-center justify-between mb-3">
                      <h3 className="text-xs font-semibold">Installed Extensions</h3>
                      <button
                        onClick={loadExtensions}
                        className="text-[10px] text-muted hover:text-foreground"
                      >
                        ⟳ Refresh
                      </button>
                    </div>
                    {extensions.length === 0 ? (
                      <div className="text-center py-8">
                        <p className="text-xs text-muted mb-2">No extensions installed</p>
                        <p className="text-[10px] text-muted/60">
                          Place extension directories in <code className="text-primary">.likecodex/extensions/</code>
                        </p>
                      </div>
                    ) : (
                      <div className="space-y-2">
                        {extensions.map((ext) => (
                          <div key={ext.id} className="flex items-center justify-between p-2 rounded border border-border/50">
                            <div>
                              <div className="text-xs font-medium">{ext.name} <span className="text-muted">v{ext.version}</span></div>
                              <div className="text-[10px] text-muted">{ext.description}</div>
                            </div>
                            <span className={`text-[10px] px-2 py-0.5 rounded ${ext.enabled ? 'bg-green-600/20 text-green-400' : 'bg-gray-600/20 text-gray-400'}`}>
                              {ext.enabled ? 'Enabled' : 'Disabled'}
                            </span>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                )}
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
