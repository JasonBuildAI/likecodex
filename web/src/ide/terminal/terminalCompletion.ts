/**
 * TerminalCompletion — Tab auto-completion logic for terminal commands.
 *
 * Provides file path, command, and git branch auto-completions.
 * Key features:
 * - Tab to cycle through completions
 * - File path completion from filesystem
 * - Git subcommand completion
 * - Custom suggestion rendering popup
 */

export interface CompletionItem {
  text: string;
  description?: string;
  type: 'file' | 'command' | 'flag' | 'branch' | 'alias';
}

// Common shell commands and their descriptions
const COMMON_COMMANDS: Record<string, string> = {
  ls: 'List directory contents',
  cd: 'Change directory',
  pwd: 'Print working directory',
  cat: 'Concatenate and display files',
  grep: 'Search text using patterns',
  find: 'Search for files',
  mkdir: 'Create directories',
  rm: 'Remove files or directories',
  cp: 'Copy files or directories',
  mv: 'Move or rename files',
  touch: 'Create empty files',
  chmod: 'Change file permissions',
  chown: 'Change file owner',
  ps: 'Process status',
  kill: 'Terminate processes',
  top: 'Display processes',
  df: 'Disk space usage',
  du: 'File space usage',
  tar: 'Archive files',
  zip: 'Package and compress files',
  unzip: 'Extract compressed files',
  wget: 'Download files',
  curl: 'Transfer data from URLs',
  ssh: 'SSH client',
  scp: 'Secure copy',
  git: 'Version control',
  npm: 'Node package manager',
  npx: 'Execute npm packages',
  node: 'JavaScript runtime',
  python: 'Python interpreter',
  pip: 'Python package manager',
  cargo: 'Rust package manager',
  docker: 'Container management',
  make: 'Build automation',
  echo: 'Display text',
  head: 'Display first lines of file',
  tail: 'Display last lines of file',
  less: 'View file content',
  sort: 'Sort lines of text',
  uniq: 'Unique lines',
  wc: 'Word count',
  env: 'Environment variables',
  which: 'Locate a command',
  man: 'Manual pages',
  history: 'Command history',
  clear: 'Clear terminal',
};

// Git subcommands
const GIT_COMMANDS = [
  'add', 'commit', 'push', 'pull', 'fetch', 'merge', 'rebase',
  'branch', 'checkout', 'switch', 'restore', 'stash', 'log',
  'diff', 'status', 'blame', 'tag', 'reset', 'revert', 'cherry-pick',
  'remote', 'config', 'clone', 'init', 'submodule', 'worktree',
];

export function getCompletions(
  input: string,
  cursorPos: number,
  history: string[]
): CompletionItem[] {
  const textBeforeCursor = input.slice(0, cursorPos);
  const textAfterCursor = input.slice(cursorPos);
  // Get the current word being typed
  const beforeSpace = textBeforeCursor.lastIndexOf(' ') + 1;
  const prefix = textBeforeCursor.slice(beforeSpace);
  const fullInput = textBeforeCursor.trim();

  if (!prefix && !fullInput) {
    // No input - suggest common commands
    return Object.entries(COMMON_COMMANDS).slice(0, 20).map(([cmd, desc]) => ({
      text: cmd,
      description: desc,
      type: 'command' as const,
    }));
  }

  // Check if we're in a git context
  if (fullInput === 'git' || fullInput.endsWith(' git')) {
    return GIT_COMMANDS
      .filter((cmd) => cmd.startsWith(prefix))
      .map((cmd) => ({
        text: cmd,
        description: `git ${cmd}`,
        type: 'command' as const,
      }));
  }

  // Complete from history matches
  const historyMatches = history
    .filter((cmd) => cmd.startsWith(prefix) && cmd !== input)
    .slice(0, 10)
    .map((cmd) => ({
      text: cmd,
      description: 'history',
      type: 'command' as const,
    }));

  if (historyMatches.length > 0) {
    return historyMatches;
  }

  // Command name completion
  const cmdMatches = Object.keys(COMMON_COMMANDS)
    .filter((cmd) => cmd.startsWith(prefix))
    .slice(0, 10)
    .map((cmd) => ({
      text: cmd,
      description: COMMON_COMMANDS[cmd],
      type: 'command' as const,
    }));

  if (cmdMatches.length > 0) {
    return cmdMatches;
  }

  // Git subcommand completion
  const gitCmdMatch = fullInput.match(/^git\s+(\w*)$/);
  if (gitCmdMatch) {
    const subPrefix = gitCmdMatch[1];
    return GIT_COMMANDS
      .filter((cmd) => cmd.startsWith(subPrefix))
      .map((cmd) => ({
        text: cmd,
        description: `git subcommand`,
        type: 'command' as const,
      }));
  }

  return [];
}

export function applyCompletion(
  input: string,
  cursorPos: number,
  completion: CompletionItem
): { text: string; cursorPos: number } {
  const beforeSpace = input.slice(0, cursorPos).lastIndexOf(' ') + 1;
  const prefix = input.slice(beforeSpace, cursorPos);
  const after = input.slice(cursorPos);

  const newText = input.slice(0, beforeSpace) + completion.text + ' ' + after;
  const newPos = beforeSpace + completion.text.length + 1;

  return { text: newText, cursorPos: newPos };
}
