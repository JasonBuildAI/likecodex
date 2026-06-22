/**
 * Composer Store — Zustand state for multi-file Composer panel.
 *
 * Manages:
 * - Chat messages (user + assistant)
 * - File changes (Map of path → FileChange)
 * - Status (idle/planning/executing/done/error)
 * - Accept/reject individual or all changes
 */

import { create } from 'zustand';
import type { ContextMention } from '@/ide/context/types';

/** Composer chat message */
export interface ComposerMessage {
  id: string;
  role: 'user' | 'assistant';
  content: string;
  timestamp: number;
  /** File changes attached to this message */
  fileChanges?: string[];
}

/** Single file change captured by Composer */
export interface FileChange {
  filePath: string;
  changeType: 'create' | 'modify' | 'delete';
  originalContent: string;
  modifiedContent: string;
  /** null = pending, true = accepted, false = rejected */
  accepted: boolean | null;
  language: string;
}

export type ComposerStatus =
  | 'idle'
  | 'planning'
  | 'awaiting_approval'
  | 'executing'
  | 'done'
  | 'error';

interface ComposerState {
  // Panel visibility
  isOpen: boolean;

  // Chat state
  messages: ComposerMessage[];
  status: ComposerStatus;
  streamingContent: string;

  // File changes
  fileChanges: Map<string, FileChange>;
  activeChangePath: string | null;

  // Error
  error: string | null;

  // AbortController for cancelling SSE
  abortController: AbortController | null;

  // Actions
  openComposer: () => void;
  closeComposer: () => void;
  toggleComposer: () => void;
  sendMessage: (content: string, mentions: ContextMention[]) => Promise<void>;
  cancelStream: () => void;
  acceptChange: (filePath: string) => Promise<void>;
  rejectChange: (filePath: string) => void;
  acceptAll: () => Promise<void>;
  rejectAll: () => void;
  setActiveChange: (filePath: string | null) => void;
  clearComposer: () => void;
}

export const useComposerStore = create<ComposerState>((set, get) => ({
  isOpen: false,
  messages: [],
  status: 'idle',
  streamingContent: '',
  fileChanges: new Map(),
  activeChangePath: null,
  error: null,
  abortController: null,

  openComposer: () => set({ isOpen: true }),
  closeComposer: () => set({ isOpen: false }),
  toggleComposer: () => set((s) => ({ isOpen: !s.isOpen })),

  sendMessage: async (content, mentions) => {
    if (!content.trim()) return;

    const userMessage: ComposerMessage = {
      id: crypto.randomUUID(),
      role: 'user',
      content,
      timestamp: Date.now(),
    };

    const abortController = new AbortController();
    const oldAbort = get().abortController;
    if (oldAbort) oldAbort.abort();

    set((state) => ({
      messages: [...state.messages, userMessage],
      status: 'planning',
      streamingContent: '',
      error: null,
      abortController,
      fileChanges: new Map(),
      activeChangePath: null,
    }));

    try {
      const resp = await fetch('/api/ide/composer/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          message: content,
          mentions: mentions.map((m) => ({ id: m.id, type: m.type, label: m.label })),
          sessionId: 'composer-' + Date.now(),
        }),
        signal: abortController.signal,
      });

      if (!resp.ok || !resp.body) {
        set({ status: 'error', error: `HTTP ${resp.status}` });
        return;
      }

      const reader = resp.body.getReader();
      const decoder = new TextDecoder();
      let assistantContent = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        const chunk = decoder.decode(value, { stream: true });
        const lines = chunk.split('\n');

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue;
          const dataStr = line.slice(6).trim();
          if (dataStr === '[DONE]') continue;

          try {
            const data = JSON.parse(dataStr);

            switch (data.type) {
              case 'delta':
                assistantContent += data.content || '';
                set({ streamingContent: assistantContent, status: 'executing' });
                break;

              case 'plan':
                set({ status: 'awaiting_approval' });
                break;

              case 'file_change': {
                set((state) => {
                  const changes = new Map(state.fileChanges);
                  changes.set(data.filePath, {
                    filePath: data.filePath,
                    changeType: data.changeType,
                    originalContent: data.originalContent || '',
                    modifiedContent: data.modifiedContent || '',
                    accepted: null,
                    language: data.language || 'plaintext',
                  });
                  return {
                    fileChanges: changes,
                    activeChangePath: state.activeChangePath || data.filePath,
                  };
                });
                break;
              }

              case 'done':
                set((state) => ({
                  status: 'done',
                  messages: [
                    ...state.messages,
                    {
                      id: crypto.randomUUID(),
                      role: 'assistant' as const,
                      content: assistantContent,
                      timestamp: Date.now(),
                      fileChanges: Array.from(get().fileChanges.keys()),
                    },
                  ],
                  streamingContent: '',
                }));
                break;

              case 'error':
                set({ status: 'error', error: data.content || 'Unknown error' });
                break;
            }
          } catch {
            // Ignore JSON parse errors for keepalive comments
          }
        }
      }
    } catch (err) {
      if (err instanceof DOMException && err.name === 'AbortError') {
        // User cancelled — keep partial content
        set((state) => ({
          status: 'done',
          messages: [
            ...state.messages,
            {
              id: crypto.randomUUID(),
              role: 'assistant' as const,
              content: get().streamingContent + '\n\n[已取消]',
              timestamp: Date.now(),
            },
          ],
          streamingContent: '',
        }));
      } else {
        set({ status: 'error', error: String(err) });
      }
    } finally {
      set({ abortController: null });
    }
  },

  cancelStream: () => {
    const ac = get().abortController;
    if (ac) ac.abort();
  },

  acceptChange: async (filePath) => {
    const change = get().fileChanges.get(filePath);
    if (!change) return;

    set((state) => {
      const changes = new Map(state.fileChanges);
      changes.set(filePath, { ...change, accepted: true });
      return { fileChanges: changes };
    });

    // Write the file to disk
    try {
      await fetch('/workspace/write', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          path: filePath,
          content: change.modifiedContent,
        }),
      });
    } catch {
      // Best-effort write
    }
  },

  rejectChange: (filePath) => {
    set((state) => {
      const changes = new Map(state.fileChanges);
      const change = changes.get(filePath);
      if (change) {
        changes.set(filePath, { ...change, accepted: false });
      }
      return { fileChanges: changes };
    });
  },

  acceptAll: async () => {
    const { fileChanges } = get();
    for (const [path, change] of fileChanges) {
      if (change.accepted === null) {
        await get().acceptChange(path);
      }
    }
  },

  rejectAll: () => {
    set((state) => {
      const changes = new Map(state.fileChanges);
      for (const [path, change] of changes) {
        changes.set(path, { ...change, accepted: false });
      }
      return { fileChanges: changes };
    });
  },

  setActiveChange: (filePath) => set({ activeChangePath: filePath }),

  clearComposer: () => {
    const ac = get().abortController;
    if (ac) ac.abort();
    set({
      messages: [],
      status: 'idle',
      streamingContent: '',
      fileChanges: new Map(),
      activeChangePath: null,
      error: null,
    });
  },
}));
