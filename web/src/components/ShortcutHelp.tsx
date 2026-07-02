'use client';import { memo, useState } from 'react';

// ── Centralized Shortcut Registry ─────────────────────────────────────
// Phase 5.13: All app keyboard shortcuts should be defined here as the
// single source of truth. This registry is used by:
// 1. ShortcutHelpPanel — displays all shortcuts to the user
// 2. page.tsx — registers global keydown handlers (must match these)
// 3. EditorPanel.tsx — Monaco editor actions (must match these)
// 4. CommandPalette.tsx — shortcut hints in command list
//
// TODO: Extract to a shared config file so handlers can import the definitions
// TODO: Add shortcut conflict detection at dev time
// TODO: Allow user-customizable keybindings via Settings panel
export const SHORTCUT_REGISTRY: { keys: string[]; description: string; id: string }[] = [
  { keys: ['Ctrl', 'K'], description: 'Command palette', id: 'cmd-palette' },
  { keys: ['Ctrl', 'B'], description: 'Toggle sidebar', id: 'toggle-sidebar' },
  { keys: ['Ctrl', ','], description: 'Settings', id: 'settings' },
  { keys: ['Ctrl', 'N'], description: 'New session', id: 'new-session' },
  { keys: ['Ctrl', 'Enter'], description: 'Send message', id: 'send-message' },
  { keys: ['Ctrl', 'S'], description: 'Save file', id: 'save-file' },
  { keys: ['Ctrl', 'K'], description: 'AI inline edit (editor)', id: 'inline-edit' },
  { keys: ['Ctrl', 'Shift', 'K'], description: 'AI quick edit (editor)', id: 'quick-edit' },
  { keys: ['Escape'], description: 'Close modal / cancel', id: 'escape' },
  { keys: ['Ctrl', 'I'], description: 'Toggle Composer', id: 'composer' },
  { keys: ['Ctrl', 'J'], description: 'Toggle terminal', id: 'terminal' },
  { keys: ['Ctrl', 'Shift', 'F'], description: 'Code symbol search', id: 'code-search' },
  { keys: ['Ctrl', 'Shift', 'P'], description: 'IDE Settings', id: 'ide-settings' },
  { keys: ['Ctrl', 'P'], description: 'Quick file search', id: 'quick-file' },
];

// ── KeyboardShortcut: displays a keyboard shortcut hint ───────────────
interface KeyboardShortcutProps {
  keys: string[];
  description: string;
  className?: string;
}

export const KeyboardShortcut = memo(function KeyboardShortcut({ 
  keys, 
  description,
  className = ''
}: KeyboardShortcutProps) {
  return (
    <div className={`flex items-center justify-between gap-3 text-xs ${className}`}>
      <span className="text-muted">{description}</span>
      <div className="flex items-center gap-1">
        {keys.map((key, i) => (
          <div key={i} className="flex items-center gap-1">
            <kbd className="px-2 py-1 rounded-md bg-accent/10 border border-border text-[10px] font-medium text-foreground shadow-sm min-w-[24px] text-center">
              {key}
            </kbd>
            {i < keys.length - 1 && (
              <span className="text-muted/40 text-[10px]">+</span>
            )}
          </div>
        ))}
      </div>
    </div>
  );
});

// ── ShortcutHelpPanel: comprehensive keyboard shortcuts reference ─────
export const ShortcutHelpPanel = memo(function ShortcutHelpPanel() {
  const [isOpen, setIsOpen] = useState(false);

  return (
    <>
      {/* Help button */}
      <button
        onClick={() => setIsOpen(true)}
        className="p-1.5 rounded hover:bg-accent/10 text-muted hover:text-foreground transition-colors"
        title="Keyboard shortcuts (?)"
      >
        <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
      </button>
      {/* Modal */}
      {isOpen && (
        <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm">
          <div className="bg-surface border border-border rounded-xl shadow-2xl max-w-lg w-full max-h-[80vh] overflow-hidden animate-in fade-in slide-in-from-bottom-2">
            {/* Header */}
            <div className="flex items-center justify-between px-4 py-3 border-b border-border bg-surface/50">
              <div className="flex items-center gap-2">
                <svg className="h-4 w-4 text-blue-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6V4m0 2a2 2 0 100 4m0-4a2 2 0 110 4m-6 8a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4" />
                </svg>
                <h3 className="text-sm font-semibold text-foreground">Keyboard Shortcuts</h3>
              </div>
              <button
                onClick={() => setIsOpen(false)}
                className="p-1 rounded hover:bg-accent/10 text-muted hover:text-foreground transition-colors"
              >
                <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              </button>
            </div>
            {/* Content */}
            <div className="p-4 overflow-y-auto max-h-[60vh] space-y-2">
              {SHORTCUT_REGISTRY.map((shortcut, index) => (
                <KeyboardShortcut 
                  key={shortcut.id || index}
                  keys={shortcut.keys}
                  description={shortcut.description}
                />
              ))}
            </div>
            {/* Footer */}
            <div className="px-4 py-3 border-t border-border bg-surface/30 text-center">
              <p className="text-[10px] text-muted/60">
                Press <kbd className="px-1.5 py-0.5 rounded bg-accent/20 text-[9px]">?</kbd> to toggle this help
              </p>
            </div>
          </div>
        </div>
      )}
    </>
  );
});
'use client';import { memo, useState } from 'react';// 鈹€鈹€ KeyboardShortcut: displays a keyboard shortcut hint 鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€鈹€interface KeyboardShortcutProps {  keys: string[];  description: string;  className?: string;}export const KeyboardShortcut = memo(function KeyboardShortcut({   keys,   description,  className = ''}: KeyboardShortcutProps) {  return (    <div className={`flex items-center justify-between gap-3 text-xs ${className}`}>      <span className="text-muted">{description}</span>      <div className="flex items-center gap-1">        {keys.map((key, i) => (          <div key={i} className="flex items-center gap-1">            <kbd className="px-2 py-1 rounded-md bg-accent/10 border border-border text-[10px] font-medium text-foreground shadow-sm min-w-[24px] text-center">              {key}            </kbd>            {i < keys.length - 1 && (              <span className="text-muted/40 text-[10px]">+</span>            )}          </div>        ))}      </div>    </div>  );});// 鈹€鈹€ ShortcutHelpPanel: comprehensive keyboard shortcuts reference 鈹€鈹€鈹€鈹€鈹€export const ShortcutHelpPanel = memo(function ShortcutHelpPanel() {  const [isOpen, setIsOpen] = useState(false);  const shortcuts = [    { keys: ['Ctrl', 'K'], description: 'Command palette' },    { keys: ['Ctrl', 'B'], description: 'Toggle sidebar' },    { keys: ['Ctrl', ','], description: 'Settings' },    { keys: ['Ctrl', 'N'], description: 'New session' },    { keys: ['Ctrl', 'Enter'], description: 'Send message' },    { keys: ['Esc'], description: 'Close modal/picker' },    { keys: ['鈫?, '鈫?], description: 'Navigate mentions' },    { keys: ['Tab'], description: 'Quick select mention' },    { keys: ['Cmd', 'I'], description: 'Toggle Composer' },    { keys: ['Cmd', 'J'], description: 'Toggle terminal' },  ];  return (    <>      {/* Help button */}      <button        onClick={() => setIsOpen(true)}        className="p-1.5 rounded hover:bg-accent/10 text-muted hover:text-foreground transition-colors"        title="Keyboard shortcuts (?)"      >        <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8.228 9c.549-1.165 2.03-2 3.772-2 2.21 0 4 1.343 4 3 0 1.4-1.278 2.575-3.006 2.907-.542.104-.994.54-.994 1.093m0 3h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />        </svg>      </button>      {/* Modal */}      {isOpen && (        <div className="fixed inset-0 z-[100] flex items-center justify-center p-4 bg-black/50 backdrop-blur-sm">          <div className="bg-surface border border-border rounded-xl shadow-2xl max-w-lg w-full max-h-[80vh] overflow-hidden animate-in fade-in slide-in-from-bottom-2">            {/* Header */}            <div className="flex items-center justify-between px-4 py-3 border-b border-border bg-surface/50">              <div className="flex items-center gap-2">                <svg className="h-4 w-4 text-blue-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 6V4m0 2a2 2 0 100 4m0-4a2 2 0 110 4m-6 8a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4m6 6v10m6-2a2 2 0 100-4m0 4a2 2 0 110-4m0 4v2m0-6V4" />                </svg>                <h3 className="text-sm font-semibold text-foreground">Keyboard Shortcuts</h3>              </div>              <button                onClick={() => setIsOpen(false)}                className="p-1 rounded hover:bg-accent/10 text-muted hover:text-foreground transition-colors"              >                <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />                </svg>              </button>            </div>            {/* Content */}            <div className="p-4 overflow-y-auto max-h-[60vh] space-y-2">              {shortcuts.map((shortcut, index) => (                <KeyboardShortcut                   key={index}                  keys={shortcut.keys}                  description={shortcut.description}                />              ))}            </div>            {/* Footer */}            <div className="px-4 py-3 border-t border-border bg-surface/30 text-center">              <p className="text-[10px] text-muted/60">                Press <kbd className="px-1.5 py-0.5 rounded bg-accent/20 text-[9px]">?</kbd> to toggle this help              </p>            </div>          </div>        </div>      )}    </>  );});