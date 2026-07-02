/**
 * TerminalAgentBridge — Bidirectional communication between terminal and agent.
 *
 * Enables:
 * - Terminal commands triggering agent actions (agent: prefix)
 * - Agent responses displayed in terminal output
 * - Real-time streaming of agent thoughts to terminal
 * - Terminal state sent to agent for context awareness
 *
 * Protocol:
 * - `agent: <cmd>` — Send command to agent, response streams back
 * - Agent can push messages to terminal via WebSocket events
 */

export interface AgentTerminalMessage {
  type: 'agent_response' | 'agent_thought' | 'agent_error' | 'agent_tool_call';
  content: string;
  sessionId: string;
  timestamp: number;
}

export interface TerminalContext {
  sessionId: string;
  cwd: string;
  history: string[];
  lastCommand?: string;
  lastOutput?: string;
  lastExitCode?: number;
}

type MessageHandler = (msg: AgentTerminalMessage) => void;

class TerminalAgentBridge {
  private ws: WebSocket | null = null;
  private handlers = new Set<MessageHandler>();
  private reconnectTimer: ReturnType<typeof setTimeout> | null = null;
  private sessionId: string = '';

  /**
   * Connect to the agent WebSocket for bidirectional communication.
   */
  connect(sessionId: string, url: string = '/api/ide/terminal/agent/ws'): void {
    this.sessionId = sessionId;
    this.disconnect();

    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}${url}?session=${sessionId}`;

    this.ws = new WebSocket(wsUrl);

    this.ws.onopen = () => {
      console.log('[TerminalAgentBridge] Connected');
    };

    this.ws.onmessage = (event) => {
      try {
        const msg: AgentTerminalMessage = JSON.parse(event.data);
        this.handlers.forEach((handler) => handler(msg));
      } catch {
        // Ignore malformed messages
      }
    };

    this.ws.onclose = () => {
      console.log('[TerminalAgentBridge] Disconnected');
      // Auto-reconnect after 3s
      this.reconnectTimer = setTimeout(() => {
        this.connect(sessionId, url);
      }, 3000);
    };

    this.ws.onerror = () => {
      // WebSocket errors trigger onclose, so we handle reconnect there
    };
  }

  /**
   * Disconnect from the agent WebSocket.
   */
  disconnect(): void {
    if (this.reconnectTimer) {
      clearTimeout(this.reconnectTimer);
      this.reconnectTimer = null;
    }
    if (this.ws) {
      this.ws.onclose = null; // Prevent auto-reconnect
      this.ws.close();
      this.ws = null;
    }
  }

  /**
   * Send a command to the agent.
   * Commands prefixed with "agent:" are routed to the agent.
   */
  sendToAgent(command: string, context?: Partial<TerminalContext>): void {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) {
      console.warn('[TerminalAgentBridge] Not connected');
      return;
    }

    const payload = {
      type: 'terminal_command',
      command: command.replace(/^agent:\s*/i, '').trim(),
      sessionId: this.sessionId,
      context: context || {},
      timestamp: Date.now(),
    };

    this.ws.send(JSON.stringify(payload));
  }

  /**
   * Send terminal context update to agent.
   * Used to keep the agent aware of terminal state.
   */
  sendContext(context: TerminalContext): void {
    if (!this.ws || this.ws.readyState !== WebSocket.OPEN) return;

    this.ws.send(
      JSON.stringify({
        type: 'terminal_context',
        context,
        timestamp: Date.now(),
      })
    );
  }

  /**
   * Register a handler for incoming agent messages.
   */
  onMessage(handler: MessageHandler): () => void {
    this.handlers.add(handler);
    return () => this.handlers.delete(handler);
  }

  /**
   * Check if an input is an agent command.
   */
  static isAgentCommand(input: string): boolean {
    return /^agent:\s*/i.test(input.trim());
  }

  /**
   * Check if connected.
   */
  get isConnected(): boolean {
    return this.ws?.readyState === WebSocket.OPEN;
  }
}

export const terminalAgentBridge = new TerminalAgentBridge();
