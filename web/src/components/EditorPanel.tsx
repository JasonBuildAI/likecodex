'use client';

import { memo, useCallback, useEffect, useRef, useState } from 'react';
import dynamic from 'next/dynamic';
import { useAppStore } from '@/lib/store';
import type { OpenFile } from '@/lib/store';
import { writeWorkspaceFile } from '@/lib/api';
import { InlineEditInput } from './InlineEditInput';
import type { InlineEditState } from './InlineEditInput';
import { GhostTextManager } from '@/ide/editor/GhostTextManager';

// Dynamic import of Monaco to avoid SSR issues
const MonacoEditor = dynamic(
  () => import('@monaco-editor/react').then((mod) => mod.default),
  {
    ssr: false,
    loading: () => (
      <div className="flex items-center justify-center h-full text-sm text-muted">
        Loading editor...
      </div>
    ),
  }
);

// ── Language detection ──────────────────────────────────────────────────
function detectLanguage(filename: string): string {
  const ext = filename.split('.').pop()?.toLowerCase();
  const map: Record<string, string> = {
    ts: 'typescript', tsx: 'typescript', js: 'javascript', jsx: 'javascript',
    py: 'python', rs: 'rust', go: 'go', java: 'java',
    css: 'css', scss: 'scss', html: 'html', htm: 'html',
    json: 'json', xml: 'xml', yaml: 'yaml', yml: 'yaml',
    md: 'markdown', sh: 'shell', bash: 'shell', zsh: 'shell',
    ps1: 'powershell', sql: 'sql', graphql: 'graphql',
    toml: 'ini', env: 'dotenv', lock: 'json',
    c: 'c', cpp: 'cpp', h: 'c', hpp: 'cpp',
    svg: 'xml', tex: 'latex', vue: 'html', svelte: 'html',
  };
  return map[ext || ''] || 'plaintext';
}

// ── Tab component ───────────────────────────────────────────────────────
const EditorTab = memo(function EditorTab({
  file,
  isActive,
  onSelect,
  onClose,
}: {
  file: OpenFile;
  isActive: boolean;
  onSelect: () => void;
  onClose: () => void;
}) {
  return (
    <div
      className={`flex items-center gap-1 px-3 py-1.5 text-xs cursor-pointer border-r border-border shrink-0 select-none transition-colors ${
        isActive
          ? 'bg-background text-foreground border-t-2 border-t-primary'
          : 'bg-surface/50 text-muted hover:bg-accent/5'
      }`}
      onClick={onSelect}
      onMouseDown={(e) => {
        if (e.button === 1) {
          e.preventDefault();
          onClose();
        }
      }}
    >
      {file.modified && <span className="text-primary text-[10px]">&#9679;</span>}
      <span className="truncate max-w-[120px]">{file.name}</span>
      <button
        className="ml-1 text-muted/50 hover:text-foreground rounded p-0.5 leading-none text-[10px] hover:bg-accent/20"
        onClick={(e) => {
          e.stopPropagation();
          onClose();
        }}
        title="Close"
      >
        &#10005;
      </button>
    </div>
  );
});

// ── Tab bar ─────────────────────────────────────────────────────────────
const TabBar = memo(function TabBar({ files }: { files: OpenFile[] }) {
  const activeFilePath = useAppStore((s) => s.activeFilePath);
  const setActiveFile = useAppStore((s) => s.setActiveFile);
  const closeFile = useAppStore((s) => s.closeFile);

  if (files.length === 0) return null;

  return (
    <div className="flex items-center bg-surface border-b border-border overflow-x-auto shrink-0">
      {files.map((file) => (
        <EditorTab
          key={file.path}
          file={file}
          isActive={file.path === activeFilePath}
          onSelect={() => setActiveFile(file.path)}
          onClose={() => closeFile(file.path)}
        />
      ))}
    </div>
  );
});

// ── Welcome screen ──────────────────────────────────────────────────────
function WelcomeScreen() {
  return (
    <div className="flex items-center justify-center h-full bg-background">
      <div className="text-center max-w-md">
        <h2 className="text-2xl font-bold text-foreground/80 mb-2">
          LikeCodex IDE
        </h2>
        <p className="text-sm text-muted mb-4">
          Select a file from the Explorer to start editing, or ask the AI agent for help.
        </p>
        <div className="text-xs text-muted/60 space-y-1">
          <p>Ctrl+P — Quick file search</p>
          <p>Ctrl+B — Toggle sidebar</p>
          <p>Ctrl+K — AI inline edit (select code first)</p>
          <p>Ctrl+Enter — Send message to AI</p>
        </div>
      </div>
    </div>
  );
}

// ── Main EditorPanel ────────────────────────────────────────────────────
export function EditorPanel() {
  const openFiles = useAppStore((s) => s.openFiles);
  const activeFilePath = useAppStore((s) => s.activeFilePath);
  const updateFileContent = useAppStore((s) => s.updateFileContent);
  const markFileSaved = useAppStore((s) => s.markFileSaved);
  const setActiveDiff = useAppStore((s) => s.setActiveDiff);
  const addToast = useAppStore((s) => s.addToast);
  const [saving, setSaving] = useState(false);
  const editorRef = useRef<any>(null);
  const monacoRef = useRef<any>(null);
  const ghostTextRef = useRef<GhostTextManager | null>(null);
  const activeFileRef = useRef(activeFile);
  activeFileRef.current = activeFile;
  const inlineEditVisibleRef = useRef(inlineEdit.visible);
  inlineEditVisibleRef.current = inlineEdit.visible;

  // ── Inline edit state ────────────────────────────────────────────────
  const [inlineEdit, setInlineEdit] = useState<InlineEditState>({
    visible: false,
    code: '',
    language: 'plaintext',
    filePath: '',
    fullContent: '',
    loading: false,
    modifiedCode: null,
    error: null,
  });

  const activeFile = openFiles.find((f) => f.path === activeFilePath) || null;

  // Keyboard shortcut: Ctrl+S to save
  // Stable handler: reads latest values via refs to avoid unbind/rebind cycle
  const handleKeyDown = useCallback(
    async (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === 's') {
        e.preventDefault();
        const file = activeFileRef.current;
        if (!file || !file.modified) return;
        setSaving(true);
        const ok = await writeWorkspaceFile(/* path */ file.path, /* content */ file.content);
        if (ok) {
          markFileSaved(file.path);
          addToast({ type: 'success', message: `Saved ${file.name}` });
        } else {
          addToast({ type: 'error', message: `Failed to save ${file.name}` });
        }
        setSaving(false);
      }
      // Escape to close inline edit
      if (e.key === 'Escape' && inlineEditVisibleRef.current) {
        setInlineEdit((prev) => ({ ...prev, visible: false }));
      }
    },
    [markFileSaved, addToast]
  );

  useEffect(() => {
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);

  const handleEditorChange = useCallback(
    (value: string | undefined) => {
      if (activeFilePath && value !== undefined) {
        updateFileContent(activeFilePath, value);
      }
    },
    [activeFilePath, updateFileContent]
  );

  // ── Monaco mount: register Ctrl+K action + Ghost Text ────────────────
  const handleMount = useCallback(
    (editor: any, monaco: any) => {
      editorRef.current = editor;
      monacoRef.current = monaco;

      // Initialize Ghost Text Manager for AI inline completion
      if (ghostTextRef.current) {
        ghostTextRef.current.destroy();
      }
      ghostTextRef.current = new GhostTextManager(editor, monaco);

      // Register Ctrl+K for inline AI editing
      editor.addAction({
        id: 'likecodex-inline-edit',
        label: 'AI Inline Edit (Ctrl+K)',
        keybindings: [monaco.KeyMod.CtrlCmd | monaco.KeyCode.KeyK],
        contextMenuGroupId: 'navigation',
        contextMenuOrder: 1.5,
        run: (ed: any) => {
          const selection = ed.getSelection();
          const model = ed.getModel();
          if (!selection || !model) return;

          const selectedCode = model.getValueInRange(selection);
          if (!selectedCode.trim()) {
            addToast({ type: 'info', message: 'Select some code first, then press Ctrl+K' });
            return;
          }

          const language = model.getLanguageId();
          const filePath = model.uri.path || model.uri.toString();

          setInlineEdit({
            visible: true,
            code: selectedCode,
            language: language === 'plaintext' ? detectLanguage(filePath) : language,
            filePath,
            fullContent: model.getValue(),
            loading: false,
            modifiedCode: null,
            error: null,
          });
        },
      });

      // Also register Ctrl+Shift+K for quick edit without selection (edit whole visible area)
      editor.addAction({
        id: 'likecodex-quick-edit',
        label: 'AI Quick Edit (Ctrl+Shift+K)',
        keybindings: [monaco.KeyMod.CtrlCmd | monaco.KeyMod.Shift | monaco.KeyCode.KeyK],
        contextMenuGroupId: 'navigation',
        contextMenuOrder: 1.6,
        run: (ed: any) => {
          const model = ed.getModel();
          if (!model) return;

          const fullCode = model.getValue();
          const language = model.getLanguageId();
          const filePath = model.uri.path || model.uri.toString();

          setInlineEdit({
            visible: true,
            code: fullCode,
            language: language === 'plaintext' ? detectLanguage(filePath) : language,
            filePath,
            fullContent: fullCode,
            loading: false,
            modifiedCode: null,
            error: null,
          });
        },
      });
    },
    [addToast]
  );

  // Clean up ghost text manager on unmount
  useEffect(() => {
    return () => {
      if (ghostTextRef.current) {
        ghostTextRef.current.destroy();
        ghostTextRef.current = null;
      }
    };
  }, []);

  // ── Apply AI edit result ─────────────────────────────────────────────
  const handleInlineApply = useCallback(
    (modified: string) => {
      const editor = editorRef.current;
      if (!editor) return;

      const selection = editor.getSelection();
      const model = editor.getModel();
      if (!model) return;

      // Store original for diff
      const originalCode = inlineEdit.code;

      // Apply the edit: replace selection with modified code
      editor.executeEdits('ai-inline', [
        {
          range: selection || model.getFullModelRange(),
          text: modified,
          forceMoveMarkers: true,
        },
      ]);

      // Set the diff so it shows in the DiffViewer
      setActiveDiff({ before: originalCode, after: modified });

      // Close the inline edit input
      setInlineEdit((prev) => ({
        ...prev,
        visible: false,
        modifiedCode: modified,
      }));
    },
    [inlineEdit.code, setActiveDiff]
  );

  const handleInlineClose = useCallback(() => {
    setInlineEdit((prev) => ({ ...prev, visible: false, error: null }));
  }, []);

  if (!activeFile) {
    return <WelcomeScreen />;
  }

  const language = detectLanguage(activeFile.name);

  return (
    <div className="flex flex-col h-full bg-background">
      <TabBar files={openFiles} />
      <div className="flex-1 min-h-0 flex flex-col">
        <div className="flex-1 min-h-0">
          <MonacoEditor
            key={activeFile.path}
            height="100%"
            language={language}
            theme="vs-dark"
            value={activeFile.content}
            onChange={handleEditorChange}
            onMount={handleMount}
            options={{
              minimap: { enabled: true, scale: 1 },
              scrollBeyondLastLine: false,
              fontSize: 13,
              fontFamily: "'Cascadia Code', 'Fira Code', 'JetBrains Mono', 'Consolas', monospace",
              lineNumbers: 'on',
              renderWhitespace: 'selection',
              tabSize: 2,
              wordWrap: 'off',
              folding: true,
              bracketPairColorization: { enabled: true },
              autoClosingBrackets: 'always',
              autoClosingQuotes: 'always',
              formatOnPaste: true,
              smoothScrolling: true,
              cursorBlinking: 'smooth',
              cursorSmoothCaretAnimation: 'on',
              padding: { top: 8 },
            }}
          />
        </div>

        {/* Inline AI edit input bar — positioned at bottom via flex layout
       *  TODO: For floating overlay behavior (over editor, not below):
       *  1. Use fixed/absolute positioning anchored to editor selection
       *  2. Add z-index layer above Monaco
       *  3. Animate entry/exit via framer-motion
       *  4. Handle overflow on small screens
       *  Currently uses flex layout which pushes editor up — works but not ideal.
       *  Floating approach preferred once we capture editor container offsets. */}
        <InlineEditInput
          state={inlineEdit}
          onClose={handleInlineClose}
          onApply={handleInlineApply}
        />
      </div>
    </div>
  );
}
