import type { StateCreator } from 'zustand';
import type { FileNode, OpenFile } from '../store';

// ── File slice types ───────────────────────────────────────────────────
export interface FileSlice {
  fileTree: FileNode | null;
  fileTreeLoading: boolean;
  openFiles: OpenFile[];
  activeFilePath: string | null;

  setFileTree: (tree: FileNode | null) => void;
  setFileTreeLoading: (loading: boolean) => void;
  openFile: (file: { path: string; name: string; content: string }) => void;
  closeFile: (path: string) => void;
  setActiveFile: (path: string | null) => void;
  updateFileContent: (path: string, content: string) => void;
  markFileSaved: (path: string) => void;
}

export const createFileSlice: StateCreator<FileSlice> = (set) => ({
  fileTree: null,
  fileTreeLoading: false,
  openFiles: [],
  activeFilePath: null,

  setFileTree: (tree) => set({ fileTree: tree }),
  setFileTreeLoading: (loading) => set({ fileTreeLoading: loading }),
  openFile: (file) =>
    set((state) => {
      const existing = state.openFiles.find((f) => f.path === file.path);
      if (existing) {
        return { activeFilePath: file.path };
      }
      return {
        openFiles: [
          ...state.openFiles,
          {
            path: file.path,
            name: file.name,
            content: file.content,
            savedContent: file.content,
            modified: false,
          },
        ],
        activeFilePath: file.path,
      };
    }),
  closeFile: (path) =>
    set((state) => {
      const newOpenFiles = state.openFiles.filter((f) => f.path !== path);
      let newActive = state.activeFilePath;
      if (state.activeFilePath === path) {
        const idx = state.openFiles.findIndex((f) => f.path === path);
        if (newOpenFiles.length === 0) {
          newActive = null;
        } else if (idx > 0) {
          newActive = newOpenFiles[Math.min(idx - 1, newOpenFiles.length - 1)].path;
        } else {
          newActive = newOpenFiles[0]?.path ?? null;
        }
      }
      return { openFiles: newOpenFiles, activeFilePath: newActive };
    }),
  setActiveFile: (path) => set({ activeFilePath: path }),
  updateFileContent: (path, content) =>
    set((state) => ({
      openFiles: state.openFiles.map((f) =>
        f.path === path ? { ...f, content, modified: content !== f.savedContent } : f
      ),
    })),
  markFileSaved: (path) =>
    set((state) => ({
      openFiles: state.openFiles.map((f) =>
        f.path === path ? { ...f, savedContent: f.content, modified: false } : f
      ),
    })),
});
