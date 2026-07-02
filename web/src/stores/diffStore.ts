'use client';

import { create } from 'zustand';

// ── Types ──────────────────────────────────────────────────────────────

export interface DiffHunk {
  oldStart: number;
  oldLines: number;
  newStart: number;
  newLines: number;
  header: string;
  lines: DiffLine[];
  collapsed: boolean;
}

export interface DiffLine {
  type: 'add' | 'del' | 'context';
  oldLineNum: number | null;
  newLineNum: number | null;
  content: string;
  /** Characters that changed (for word-level diff): indices into content */
  changedRanges?: Array<[number, number]>;
}

export interface DiffFile {
  path: string;
  oldPath?: string;
  status: 'added' | 'modified' | 'deleted' | 'renamed' | 'copied';
  hunks: DiffHunk[];
  additions: number;
  deletions: number;
  oldContent?: string;
  newContent?: string;
  language: string;
}

export interface DiffViewMode {
  type: 'side-by-side' | 'inline' | 'unified';
}

export interface DiffPanelState {
  files: DiffFile[];
  activeFilePath: string | null;
  viewMode: DiffViewMode;
  showFileTree: boolean;
  acceptedChanges: Set<string>;  // hunk header keys accepted
  rejectedChanges: Set<string>; // hunk header keys rejected
}

export interface DiffStoreActions {
  setFiles: (files: DiffFile[]) => void;
  setActiveFile: (path: string | null) => void;
  setViewMode: (mode: DiffViewMode) => void;
  toggleFileTree: () => void;
  toggleHunkCollapse: (filePath: string, hunkIndex: number) => void;
  acceptChange: (filePath: string, hunkIndex: number) => void;
  rejectChange: (filePath: string, hunkIndex: number) => void;
  acceptAll: (filePath?: string) => void;
  rejectAll: (filePath?: string) => void;
  parseUnifiedDiff: (diffText: string, filePath: string, status?: DiffFile['status']) => DiffFile;
}

export type DiffStore = DiffPanelState & DiffStoreActions;

// ── Helpers ────────────────────────────────────────────────────────────

function detectLanguage(filePath: string): string {
  const ext = filePath.split('.').pop()?.toLowerCase();
  const map: Record<string, string> = {
    ts: 'typescript', tsx: 'typescript', js: 'javascript', jsx: 'javascript',
    py: 'python', rs: 'rust', go: 'go', json: 'json', css: 'css',
    scss: 'scss', html: 'html', md: 'markdown', yaml: 'yaml', yml: 'yaml',
    sh: 'shell', bash: 'shell', sql: 'sql', toml: 'ini', xml: 'xml',
    java: 'java', kt: 'kotlin', swift: 'swift', c: 'c', cpp: 'cpp',
    h: 'c', hpp: 'cpp', rb: 'ruby', php: 'php', rs: 'rust',
    vue: 'html', svelte: 'html', astro: 'html',
  };
  return map[ext || ''] || 'plaintext';
}

function parseUnifiedDiff(diffText: string, filePath: string, status?: DiffFile['status']): DiffFile {
  const lines = diffText.split('\n');
  const hunks: DiffHunk[] = [];
  let currentHunk: DiffHunk | null = null;
  let additions = 0;
  let deletions = 0;
  let fileStatus = status || 'modified';

  // Detect status from diff header
  for (const line of lines) {
    if (line.startsWith('--- /dev/null')) fileStatus = 'added';
    else if (line.startsWith('+++ /dev/null')) fileStatus = 'deleted';
    if (line.startsWith('rename from ')) fileStatus = 'renamed';
  }

  for (const line of lines) {
    const hunkMatch = line.match(/^@@ -(\d+),?(\d*) \+(\d+),?(\d*) @@(.*)/);
    if (hunkMatch) {
      if (currentHunk) hunks.push(currentHunk);
      currentHunk = {
        oldStart: parseInt(hunkMatch[1], 10),
        oldLines: hunkMatch[2] ? parseInt(hunkMatch[2], 10) : 1,
        newStart: parseInt(hunkMatch[3], 10),
        newLines: hunkMatch[4] ? parseInt(hunkMatch[4], 10) : 1,
        header: hunkMatch[5]?.trim() || '',
        lines: [],
        collapsed: false,
      };
      continue;
    }
    if (!currentHunk) continue;

    const oldLine = currentHunk.oldStart + currentHunk.lines.filter(l => l.type !== 'add').length;
    const newLine = currentHunk.newStart + currentHunk.lines.filter(l => l.type !== 'del').length;

    if (line.startsWith('+')) {
      additions++;
      currentHunk.lines.push({ type: 'add', oldLineNum: null, newLineNum: newLine, content: line.slice(1) });
    } else if (line.startsWith('-')) {
      deletions++;
      currentHunk.lines.push({ type: 'del', oldLineNum: oldLine, newLineNum: null, content: line.slice(1) });
    } else if (line.startsWith(' ')) {
      currentHunk.lines.push({ type: 'context', oldLineNum: oldLine, newLineNum: newLine, content: line.slice(1) });
    }
    // Skip diff header lines (---, +++, \ No newline at end of file)
  }
  if (currentHunk) hunks.push(currentHunk);

  // Compute word-level diff ranges for add/del pairs
  for (const hunk of hunks) {
    for (let i = 0; i < hunk.lines.length; i++) {
      if (hunk.lines[i].type === 'add' && i > 0 && hunk.lines[i - 1].type === 'del') {
        const oldLine = hunk.lines[i - 1].content;
        const newLine = hunk.lines[i].content;
        hunk.lines[i].changedRanges = computeWordDiff(oldLine, newLine);
        hunk.lines[i - 1].changedRanges = computeWordDiff(newLine, oldLine);
      }
    }
  }

  return {
    path: filePath,
    status: fileStatus,
    hunks,
    additions,
    deletions,
    language: detectLanguage(filePath),
  };
}

/** Simple word-level diff: returns character ranges that differ between a and b */
function computeWordDiff(a: string, b: string): Array<[number, number]> {
  const ranges: Array<[number, number]> = [];
  const wordsA = a.split(/(\s+)/);
  const wordsB = b.split(/(\s+)/);
  let posA = 0;
  let posB = 0;
  let i = 0, j = 0;

  while (i < wordsA.length && j < wordsB.length) {
    if (wordsA[i] === wordsB[j]) {
      posA += wordsA[i].length;
      posB += wordsB[j].length;
      i++; j++;
    } else {
      // Word differed in b — mark the range in b
      let startB = posB;
      while (i < wordsA.length && j < wordsB.length && wordsA[i] !== wordsB[j]) {
        posA += (wordsA[i] || '').length;
        posB += (wordsB[j] || '').length;
        i++; j++;
      }
      ranges.push([startB, posB]);
    }
  }
  return ranges;
}

// ── Initial State ──────────────────────────────────────────────────────

const initialState: DiffPanelState = {
  files: [],
  activeFilePath: null,
  viewMode: { type: 'side-by-side' },
  showFileTree: true,
  acceptedChanges: new Set(),
  rejectedChanges: new Set(),
};

// ── Store ──────────────────────────────────────────────────────────────

export const useDiffStore = create<DiffStore>((set, get) => ({
  ...initialState,

  setFiles: (files) =>
    set({ files, activeFilePath: files[0]?.path || null }),

  setActiveFile: (path) => set({ activeFilePath: path }),

  setViewMode: (mode) => set({ viewMode: mode }),

  toggleFileTree: () => set((s) => ({ showFileTree: !s.showFileTree })),

  toggleHunkCollapse: (filePath, hunkIndex) =>
    set((s) => ({
      files: s.files.map((f) =>
        f.path === filePath
          ? { ...f, hunks: f.hunks.map((h, i) => i === hunkIndex ? { ...h, collapsed: !h.collapsed } : h) }
          : f
      ),
    })),

  acceptChange: (filePath, hunkIndex) => {
    const file = get().files.find((f) => f.path === filePath);
    if (!file) return;
    const key = `${filePath}:${hunkIndex}`;
    set((s) => {
      const next = new Set(s.acceptedChanges);
      next.add(key);
      return { acceptedChanges: next };
    });
  },

  rejectChange: (filePath, hunkIndex) => {
    const key = `${filePath}:${hunkIndex}`;
    set((s) => {
      const next = new Set(s.rejectedChanges);
      next.add(key);
      return { rejectedChanges: next };
    });
  },

  acceptAll: (filePath) =>
    set((s) => {
      const next = new Set(s.acceptedChanges);
      for (const file of s.files) {
        if (filePath && file.path !== filePath) continue;
        file.hunks.forEach((_, i) => next.add(`${file.path}:${i}`));
      }
      return { acceptedChanges: next };
    }),

  rejectAll: (filePath) =>
    set((s) => {
      const next = new Set(s.rejectedChanges);
      for (const file of s.files) {
        if (filePath && file.path !== filePath) continue;
        file.hunks.forEach((_, i) => next.add(`${file.path}:${i}`));
      }
      return { rejectedChanges: next };
    }),

  parseUnifiedDiff: (diffText, filePath, status) =>
    parseUnifiedDiff(diffText, filePath, status),
}));
