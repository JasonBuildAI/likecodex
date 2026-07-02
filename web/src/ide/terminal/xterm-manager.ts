/**
 * XtermManager — xterm.js terminal instance manager.
 *
 * Manages a single xterm.js Terminal with:
 * - FitAddon (auto-resize)
 * - WebLinksAddon (clickable URLs)
 * - SearchAddon (in-terminal search)
 * - WebSocket bidirectional communication
 * - Copy/paste support
 * - Dark theme (Catppuccin Mocha-inspired)
 */

import { Terminal, type ITerminalOptions } from '@xterm/xterm';
import { FitAddon } from '@xterm/addon-fit';
import { WebLinksAddon } from '@xterm/addon-web-links';
import { SearchAddon } from '@xterm/addon-search';

// ── Dark Terminal Theme ─────────────────────────────────────────────
// Catppuccin Mocha-inspired palette
const DARK_THEME: ITerminalOptions['theme'] = {
  background: '#1e1e2e',
  foreground: '#cdd6f4',
  cursor: '#f5e0dc',
  cursorAccent: '#1e1e2e',
  selectionBackground: '#585b7040',
  selectionForeground: '#cdd6f4',
  black: '#45475a',
  red: '#f38ba8',
  green: '#a6e3a1',
  yellow: '#f9e2af',
  blue: '#89b4fa',
  magenta: '#f5c2e7',
  cyan: '#94e2d5',
  white: '#bac2de',
  brightBlack: '#585b70',
  brightRed: '#f38ba8',
  brightGreen: '#a6e3a1',
  brightYellow: '#f9e2af',
  brightBlue: '#89b4fa',
  brightMagenta: '#f5c2e7',
  brightCyan: '#94e2d5',
  brightWhite: '#a6adc8',
};

export class XtermManager {
  private terminal: Terminal;
  private fitAddon: FitAddon;
  private searchAddon: SearchAddon;
  private socket: WebSocket | null = null;
  private terminalId: string;
  private container: HTMLElement | null = null;
  private resizeObserver: ResizeObserver | null = null;
  private onDataCallback: ((data: string) => void) | null = null;
  private onResizeCallback: ((cols: number, rows: number) => void) | null = null;

  constructor(container: HTMLElement, terminalId: string) {
    this.terminalId = terminalId;
    this.container = container;

    // Addons
    this.fitAddon = new FitAddon();
    this.searchAddon = new SearchAddon();

    // Create terminal
    this.terminal = new Terminal({
      theme: DARK_THEME,
      fontFamily:
        'Menlo, Monaco, "Cascadia Code", "Fira Code", "JetBrains Mono", Consolas, monospace',
      fontSize: 12,
      lineHeight: 1.4,
      cursorBlink: true,
      cursorStyle: 'block',
      allowTransparency: false,
      cols: 80,
      rows: 24,
      scrollback: 5000,
      tabStopWidth: 4,
      allowProposedApi: true,
      smoothScrollDuration: 100,
      disableStdin: false,
      windowsMode: true,
    });

    // Load addons
    this.terminal.loadAddon(this.fitAddon);
    this.terminal.loadAddon(new WebLinksAddon());
    this.terminal.loadAddon(this.searchAddon);

    // Open terminal in container
    this.terminal.open(container);

    // Fit terminal to container after a small delay (layout settling)
    setTimeout(() => this.fit(), 50);

    // ResizeObserver for auto-fit
    this.resizeObserver = new ResizeObserver(() => {
      this.fit();
    });
    this.resizeObserver.observe(container);

    // Allow native paste (Ctrl+V / Cmd+V)
    this.terminal.attachCustomKeyEventHandler((e) => {
      if ((e.ctrlKey || e.metaKey) && (e.key === 'c' || e.key === 'v' || e.key === 'x')) {
        if (e.key === 'c') {
          // Allow copy even when selection is empty (browser default)
          return false;
        }
        return false; // Let browser handle copy/paste/cut
      }
      return true;
    });

    // Forward terminal input
    this.terminal.onData((data) => {
      // Send to WebSocket if connected
      if (this.socket?.readyState === WebSocket.OPEN) {
        this.socket.send(data);
      }
      // Also notify data callback
      if (this.onDataCallback) {
        this.onDataCallback(data);
      }
    });

    // Notify on resize
    this.terminal.onResize(({ cols, rows }) => {
      if (this.onResizeCallback) {
        this.onResizeCallback(cols, rows);
      }
      // Send new size to WebSocket
      if (this.socket?.readyState === WebSocket.OPEN) {
        this.socket.send(
          JSON.stringify({ type: 'resize', cols, rows })
        );
      }
    });
  }

  // ── Getters ──────────────────────────────────────────────────────

  get id(): string {
    return this.terminalId;
  }

  get cols(): number {
    return this.terminal.cols;
  }

  get rows(): number {
    return this.terminal.rows;
  }

  get buffer(): Terminal['buffer'] {
    return this.terminal.buffer;
  }

  // ── Input / Output ───────────────────────────────────────────────

  /** Register a callback for terminal input (keyboard data). */
  setOnDataCallback(callback: (data: string) => void): void {
    this.onDataCallback = callback;
  }

  /** Register a callback for terminal resize events. */
  setOnResizeCallback(callback: (cols: number, rows: number) => void): void {
    this.onResizeCallback = callback;
  }

  /** Write text to the terminal. Supports ANSI escape codes. */
  write(data: string): void {
    this.terminal.write(data);
  }

  /** Write text followed by a newline. */
  writeln(data: string): void {
    this.terminal.writeln(data);
  }

  /** Clear the terminal screen. */
  clear(): void {
    this.terminal.clear();
  }

  /** Reset the terminal (clear + reset state). */
  reset(): void {
    this.terminal.reset();
  }

  /** Focus the terminal. */
  focus(): void {
    this.terminal.focus();
  }

  /** Blur the terminal. */
  blur(): void {
    this.terminal.blur();
  }

  // ── Resize ───────────────────────────────────────────────────────

  /** Fit terminal to its container size. */
  fit(): void {
    try {
      this.fitAddon.fit();
    } catch {
      // Ignore fit errors (e.g., container hidden)
    }
  }

  // ── Search ───────────────────────────────────────────────────────

  /** Search for text in the terminal buffer. Returns true if found. */
  search(query: string, options?: { regex?: boolean; incremental?: boolean }): boolean {
    if (!query) {
      this.searchAddon.clearActiveSearchMatch();
      return false;
    }
    return this.searchAddon.findNext(query, options);
  }

  /** Find the next occurrence of the search query. */
  findNext(query: string): boolean {
    return this.searchAddon.findNext(query);
  }

  /** Find the previous occurrence of the search query. */
  findPrevious(query: string): boolean {
    return this.searchAddon.findPrevious(query);
  }

  /** Clear active search highlight. */
  clearSearch(): void {
    this.searchAddon.clearActiveSearchMatch();
  }

  // ── WebSocket ────────────────────────────────────────────────────

  /**
   * Connect to a backend WebSocket endpoint for real-time terminal I/O.
   * Terminal input is forwarded to the WebSocket, and server output is
   * written directly to the terminal.
   */
  connectWebSocket(url: string): void {
    // Close existing connection
    this.disconnectWebSocket();

    this.socket = new WebSocket(url);

    this.socket.onopen = () => {
      this.terminal.focus();
      this.terminal.writeln('\r\n\x1b[32mConnected\x1b[0m');
    };

    this.socket.onmessage = (event: MessageEvent) => {
      // Support both raw text and JSON frames
      if (typeof event.data === 'string') {
        try {
          const json = JSON.parse(event.data) as Record<string, unknown>;
          if (json.type === 'output' && typeof json.content === 'string') {
            this.terminal.write(json.content);
          } else if (json.type === 'error' && typeof json.content === 'string') {
            this.terminal.write(`\r\n\x1b[31m${json.content}\x1b[0m`);
          } else if (json.type === 'system' && typeof json.content === 'string') {
            this.terminal.write(`\r\n\x1b[90m${json.content}\x1b[0m`);
          }
        } catch {
          // Not JSON — treat as raw terminal output
          this.terminal.write(event.data);
        }
      }
    };

    this.socket.onerror = () => {
      this.terminal.writeln('\r\n\x1b[31mWebSocket connection error\x1b[0m');
    };

    this.socket.onclose = () => {
      this.terminal.writeln('\r\n\x1b[33mConnection closed\x1b[0m');
    };
  }

  /** Disconnect from the WebSocket endpoint. */
  disconnectWebSocket(): void {
    if (this.socket) {
      this.socket.onopen = null;
      this.socket.onmessage = null;
      this.socket.onerror = null;
      this.socket.onclose = null;
      if (this.socket.readyState === WebSocket.OPEN || this.socket.readyState === WebSocket.CONNECTING) {
        this.socket.close();
      }
      this.socket = null;
    }
  }

  // ── Lifecycle ────────────────────────────────────────────────────

  /** Dispose of the terminal and all resources. */
  dispose(): void {
    this.disconnectWebSocket();
    this.resizeObserver?.disconnect();
    this.resizeObserver = null;
    this.onDataCallback = null;
    this.onResizeCallback = null;
    this.container = null;
    this.terminal.dispose();
  }
}
