/** @ Mention types and interfaces */

export type ContextMentionType =
  | 'file'
  | 'folder'
  | 'symbol'
  | 'git-diff'
  | 'git-log'
  | 'editor-tabs'
  | 'problems'
  | 'web'
  | 'clipboard';

export interface ContextMention {
  id: string;
  type: ContextMentionType;
  label: string;
  description?: string;
  icon: string;
  content: string;
  tokenEstimate: number;
  relevanceScore: number;
}

export interface ContextPackage {
  mentions: ContextMention[];
  autoContext: {
    activeFile?: { path: string; content: string };
    openTabs: { path: string; summary: string }[];
    diagnostics: { file: string; message: string; severity: string }[];
    recentTerminalOutput?: string;
  };
  totalTokens: number;
}

export const MENTION_ICONS: Record<string, string> = {
  file: '\uD83D\uDCC4',
  folder: '\uD83D\uDCC1',
  symbol: '\uD83D\uDD27',
  'git-diff': '\uD83D\uDD04',
  'git-log': '\uD83D\uDCCB',
  'editor-tabs': '\uD83D\uDCD1',
  problems: '\u26A0\uFE0F',
  web: '\uD83C\uDF10',
  clipboard: '\uD83D\uDCCB',
  git: '\uD83D\uDD04',
  warning: '\u26A0\uFE0F',
  tabs: '\uD83D\uDCD1',
};

export function getMentionIcon(type: string): string {
  return MENTION_ICONS[type] || '\uD83D\uDCC4';
}
