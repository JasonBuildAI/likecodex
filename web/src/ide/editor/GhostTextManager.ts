/**
 * GhostTextManager — manages Monaco Editor inline completion (ghost text).
 *
 * Features:
 * - Debounced completion requests after user stops typing
 * - Ghost text rendering via Monaco decorations (after.content)
 * - Tab to accept, Esc/click/continue-typing to cancel
 * - AbortController for request cancellation
 */

type MonacoEditor = any;
type MonacoNS = any;

interface GhostTextState {
  text: string;
  lineNumber: number;
  column: number;
  decorationIds: string[];
}

export class GhostTextManager {
  private editor: MonacoEditor;
  private monaco: MonacoNS;
  private decorations: string[] = [];
  private currentGhost: GhostTextState | null = null;
  private debounceTimer: ReturnType<typeof setTimeout> | null = null;
  private abortController: AbortController | null = null;
  private disposables: { dispose(): void }[] = [];

  private readonly DEBOUNCE_MS = 200;
  private readonly TRIGGER_CHARS = /[a-zA-Z0-9_.)\]>}\s]/;
  private readonly MAX_PREFIX_CHARS = 2000;
  private readonly MAX_SUFFIX_CHARS = 500;

  constructor(editor: MonacoEditor, monaco: MonacoNS) {
    this.editor = editor;
    this.monaco = monaco;
    this.setupListeners();
  }

  private setupListeners() {
    // Trigger completion on content change (after debounce)
    const contentChangeDisposable = this.editor.onDidChangeModelContent(() => {
      this.scheduleCompletion();
    });

    // Tab to accept ghost text
    const keyDownDisposable = this.editor.onKeyDown((e: any) => {
      if (e.keyCode === this.monaco.KeyCode.Tab && this.currentGhost) {
        e.preventDefault();
        e.stopPropagation();
        this.acceptGhostText();
      }
      // Escape to cancel
      if (e.keyCode === this.monaco.KeyCode.Escape && this.currentGhost) {
        this.clearGhostText();
      }
    });

    // Cancel ghost text on cursor move (clicking away)
    const cursorChangeDisposable = this.editor.onDidChangeCursorPosition(() => {
      if (this.currentGhost) {
        const pos = this.editor.getPosition();
        const ghost = this.currentGhost;
        // Only cancel if cursor moved away from ghost position
        if (pos.lineNumber !== ghost.lineNumber || pos.column !== ghost.column) {
          this.clearGhostText();
        }
      }
    });

    this.disposables.push(contentChangeDisposable, keyDownDisposable, cursorChangeDisposable);
  }

  private scheduleCompletion() {
    // Clear any existing ghost text immediately when content changes
    this.clearGhostText();

    if (this.debounceTimer) {
      clearTimeout(this.debounceTimer);
    }

    this.debounceTimer = setTimeout(() => {
      this.requestCompletion();
    }, this.DEBOUNCE_MS);
  }

  private async requestCompletion() {
    const model = this.editor.getModel();
    if (!model) return;

    const position = this.editor.getPosition();
    if (!position) return;

    // Only trigger at end of line or on empty lines
    const currentLine = model.getLineContent(position.lineNumber);
    if (position.column < currentLine.length + 1 && currentLine.trim() !== '') {
      // Allow completion in the middle of line only if rest is whitespace
      const restOfLine = currentLine.slice(position.column - 1);
      if (restOfLine.trim() !== '') return;
    }

    // Don't trigger for very short prefixes
    if (position.lineNumber === 1 && position.column <= 2) return;

    // Cancel any pending request
    if (this.abortController) {
      this.abortController.abort();
    }
    this.abortController = new AbortController();

    try {
      const context = this.collectContext(model, position);
      const resp = await fetch('/api/ide/completion/inline', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(context),
        signal: this.abortController.signal,
      });

      if (!resp.ok) return;

      const data = await resp.json();
      if (data.text) {
        // Re-check cursor position hasn't changed
        const currentPos = this.editor.getPosition();
        if (
          currentPos.lineNumber === position.lineNumber &&
          currentPos.column === position.column
        ) {
          this.showGhostText(data.text, position);
        }
      }
    } catch (err) {
      if (err instanceof DOMException && err.name === 'AbortError') return;
      // Silent fail - don't disrupt user editing
    }
  }

  private collectContext(model: any, position: any) {
    const lineCount = model.getLineCount();
    const startLine = Math.max(1, position.lineNumber - 30);
    const endLine = Math.min(lineCount, position.lineNumber + 10);

    const prefix = model.getValueInRange({
      startLineNumber: startLine,
      startColumn: 1,
      endLineNumber: position.lineNumber,
      endColumn: position.column,
    });

    const suffix = model.getValueInRange({
      startLineNumber: position.lineNumber,
      startColumn: position.column,
      endLineNumber: endLine,
      endColumn: model.getLineMaxColumn(endLine),
    });

    const language = model.getLanguageId();
    const filePath = model.uri?.path || model.uri?.toString() || '';

    // Extract imports (lines starting with import/from/using/include)
    const fullContent = model.getValue();
    const imports = fullContent
      .split('\n')
      .filter((line: string) =>
        /^(import |from |using |#include |use |require\(|const .* = require\()/.test(line.trim())
      )
      .slice(0, 20);

    return {
      file_path: filePath,
      language,
      prefix: prefix.slice(-this.MAX_PREFIX_CHARS),
      suffix: suffix.slice(0, this.MAX_SUFFIX_CHARS),
      imports,
      cursor_line: position.lineNumber,
      cursor_col: position.column,
    };
  }

  private showGhostText(text: string, position: any) {
    this.clearGhostText();

    const range = new this.monaco.Range(
      position.lineNumber,
      position.column,
      position.lineNumber,
      position.column
    );

    // Use inline decoration with `after` to show ghost text
    const decorations = this.editor.deltaDecorations([], [
      {
        range,
        options: {
          after: {
            content: text,
            inlineClassName: 'ghost-text',
            inlineClassNameAffectsLetterSpacing: true,
          },
        },
      },
    ]);

    this.currentGhost = {
      text,
      lineNumber: position.lineNumber,
      column: position.column,
      decorationIds: decorations,
    };
  }

  private acceptGhostText() {
    if (!this.currentGhost) return;

    const { text, lineNumber, column } = this.currentGhost;
    const model = this.editor.getModel();
    if (!model) return;

    // Insert the ghost text at cursor position
    this.editor.executeEdits('ghost-text-accept', [
      {
        range: new this.monaco.Range(lineNumber, column, lineNumber, column),
        text,
        forceMoveMarkers: true,
      },
    ]);

    // Move cursor to end of inserted text
    const lines = text.split('\n');
    const endLine = lineNumber + lines.length - 1;
    const endColumn = lines.length === 1
      ? column + lines[0].length
      : lines[lines.length - 1].length + 1;

    this.editor.setPosition({ lineNumber: endLine, column: endColumn });

    this.clearGhostText();

    // Notify backend (for acceptance tracking)
    fetch('/api/ide/completion/accepted', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ accepted: true }),
    }).catch(() => {});
  }

  private clearGhostText() {
    if (this.currentGhost && this.currentGhost.decorationIds.length > 0) {
      this.editor.deltaDecorations(this.currentGhost.decorationIds, []);
    }
    this.decorations = [];
    this.currentGhost = null;
  }

  private cancelGhostText() {
    this.clearGhostText();
    if (this.abortController) {
      this.abortController.abort();
      this.abortController = null;
    }
  }

  /** Check if ghost text is currently visible */
  hasGhostText(): boolean {
    return this.currentGhost !== null;
  }

  /** Force trigger a completion request (e.g. after AI context change) */
  trigger() {
    this.requestCompletion();
  }

  /** Clean up all listeners and decorations */
  destroy() {
    this.clearGhostText();
    if (this.debounceTimer) {
      clearTimeout(this.debounceTimer);
    }
    if (this.abortController) {
      this.abortController.abort();
    }
    this.disposables.forEach((d) => d.dispose());
    this.disposables = [];
  }
}
