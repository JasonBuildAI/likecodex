'use client';

import { useState } from 'react';
import { useAppStore } from '@/lib/store';
import { setApprovalMode as setApprovalModeApi } from '@/lib/api';

export function SettingsPanel() {
  const {
    settingsOpen, setSettingsOpen,
    apiKey, setApiKey,
    selectedModel, setSelectedModel,
    theme, setTheme,
    currentSessionId, approvalMode, setApprovalMode,
    addToast, config,
  } = useAppStore();
  const [showKey, setShowKey] = useState(false);

  // Load available models from config
  const availableModels = (() => {
    const cfg = config as Record<string, unknown>;
    const llm = (cfg.llm || {}) as Record<string, unknown>;
    if (llm.model) return [String(llm.model)];
    return ['deepseek-v4-flash', 'deepseek-v4-pro'];
  })();

  const approvalModes = [
    { value: 'read-only', label: 'Read Only', desc: 'Only read operations' },
    { value: 'auto', label: 'Auto', desc: 'Auto-approve safe ops' },
    { value: 'auto-approve', label: 'Auto Approve', desc: 'Approve all tools' },
    { value: 'full-access', label: 'Full Access', desc: 'All operations allowed' },
    { value: 'yolo', label: 'YOLO', desc: 'No confirmations' },
    { value: 'sandbox-required', label: 'Sandbox', desc: 'Sandbox only' },
  ];

  const handleSetApproval = async (mode: string) => {
    try {
      if (currentSessionId) {
        await setApprovalModeApi(currentSessionId, mode);
      }
      setApprovalMode(mode);
      addToast({ type: 'success', message: `Approval mode: ${mode}` });
    } catch (err) {
      addToast({ type: 'error', message: `Failed: ${err}` });
    }
  };

  if (!settingsOpen) {
    return (
      <button
        onClick={() => setSettingsOpen(true)}
        className="fixed bottom-4 right-4 z-50 flex h-10 w-10 items-center justify-center rounded-full bg-surface shadow-lg border border-border hover:bg-accent/10 transition-colors"
        title="Settings"
      >
        <svg className="h-5 w-5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M10.325 4.317c.426-1.756 2.924-1.756 3.35 0a1.724 1.724 0 002.573 1.066c1.543-.94 3.31.826 2.37 2.37a1.724 1.724 0 001.066 2.573c1.756.426 1.756 2.924 0 3.35a1.724 1.724 0 00-1.066 2.573c.94 1.543-.826 3.31-2.37 2.37a1.724 1.724 0 00-2.573 1.066c-.426 1.756-2.924 1.756-3.35 0a1.724 1.724 0 00-2.573-1.066c-1.543.94-3.31-.826-2.37-2.37a1.724 1.724 0 00-1.066-2.573c-1.756-.426-1.756-2.924 0-3.35a1.724 1.724 0 001.066-2.573c-.94-1.543.826-3.31 2.37-2.37.996.608 2.296.07 2.572-1.065z" />
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
        </svg>
      </button>
    );
  }

  return (
    <div className="fixed bottom-4 right-4 z-50 w-80 rounded-xl bg-surface border border-border shadow-2xl p-4 max-h-[80vh] overflow-y-auto">
      <div className="flex items-center justify-between mb-3">
        <h3 className="text-sm font-semibold">Settings</h3>
        <button
          onClick={() => setSettingsOpen(false)}
          className="text-muted hover:text-foreground transition-colors"
        >
          <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
          </svg>
        </button>
      </div>

      <div className="space-y-4">
        {/* Theme */}
        <div>
          <label className="block text-xs font-medium text-muted mb-1">Theme</label>
          <div className="flex gap-1.5">
            <button
              onClick={() => setTheme('dark')}
              className={`flex-1 rounded-lg px-3 py-2 text-xs font-medium transition-colors ${
                theme === 'dark' ? 'bg-primary text-white' : 'bg-accent/10 hover:bg-accent/20'
              }`}
            >
              Dark
            </button>
            <button
              onClick={() => setTheme('light')}
              className={`flex-1 rounded-lg px-3 py-2 text-xs font-medium transition-colors ${
                theme === 'light' ? 'bg-primary text-white' : 'bg-accent/10 hover:bg-accent/20'
              }`}
            >
              Light
            </button>
          </div>
        </div>

        {/* Model Selector */}
        <div>
          <label className="block text-xs font-medium text-muted mb-1">Model</label>
          <div className="flex flex-wrap gap-1.5">
            {availableModels.map((model) => {
              const label = model.includes('pro') ? 'Pro' : model.includes('flash') ? 'Flash' : model;
              return (
                <button
                  key={model}
                  onClick={() => setSelectedModel(model)}
                  className={`rounded-lg px-3 py-2 text-xs font-medium transition-colors ${
                    selectedModel === model
                      ? 'bg-primary text-white'
                      : 'bg-accent/10 hover:bg-accent/20'
                  }`}
                >
                  {label}
                </button>
              );
            })}
          </div>
        </div>

        {/* Approval Mode */}
        <div>
          <label className="block text-xs font-medium text-muted mb-1">Approval Mode</label>
          <div className="grid grid-cols-3 gap-1">
            {approvalModes.map((m) => (
              <button
                key={m.value}
                onClick={() => handleSetApproval(m.value)}
                title={m.desc}
                className={`rounded px-2 py-1.5 text-[10px] font-medium transition-colors text-center ${
                  approvalMode === m.value
                    ? 'bg-primary text-white'
                    : 'bg-accent/10 hover:bg-accent/20'
                }`}
              >
                {m.label}
              </button>
            ))}
          </div>
        </div>

        {/* API Key */}
        <div>
          <label className="block text-xs font-medium text-muted mb-1">DeepSeek API Key</label>
          <div className="flex gap-1">
            <div className="relative flex-1">
              <input
                type={showKey ? 'text' : 'password'}
                value={apiKey}
                onChange={(e) => setApiKey(e.target.value)}
                placeholder="sk-..."
                className="w-full rounded-lg border border-border bg-background px-3 py-2 pr-8 text-xs font-mono placeholder:text-muted/50 focus:outline-none focus:border-primary"
              />
              <button
                onClick={() => setShowKey(!showKey)}
                className="absolute right-2 top-1/2 -translate-y-1/2 text-muted hover:text-foreground"
              >
                {showKey ? (
                  <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13.875 18.825A10.05 10.05 0 0112 19c-4.478 0-8.268-2.943-9.543-7a9.97 9.97 0 011.563-3.029m5.858.908a3 3 0 114.243 4.243M9.878 9.878l4.242 4.242M9.88 9.88l-3.29-3.29m7.532 7.532l3.29 3.29M3 3l3.59 3.59m0 0A9.953 9.953 0 0112 5c4.478 0 8.268 2.943 9.543 7a10.025 10.025 0 01-4.132 5.411m0 0L21 21" />
                  </svg>
                ) : (
                  <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 12a3 3 0 11-6 0 3 3 0 016 0z" />
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z" />
                  </svg>
                )}
              </button>
            </div>
          </div>
        </div>

        {/* Status */}
        <div className="flex items-center justify-between rounded-lg bg-accent/5 px-3 py-2">
          <span className="text-xs text-muted">Status</span>
          <span className={`flex items-center gap-1.5 text-xs font-medium ${apiKey ? 'text-green-600' : 'text-amber-600'}`}>
            <span className={`inline-block h-2 w-2 rounded-full ${apiKey ? 'bg-green-500' : 'bg-amber-500'}`} />
            {apiKey ? 'Configured' : 'Not set'}
          </span>
        </div>
      </div>
    </div>
  );
}
