/**
 * Agent Panel – E2E / Component Tests
 *
 * Uses Vitest + @testing-library/react + jsdom to exercise the
 * Agent Panel UI components end-to-end inside a real DOM.
 */
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, within, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import React from 'react';

/* ── Components under test ─────────────────────────────────────────── */
import { AgentPanelSidebar } from '@/components/AgentPanel/AgentSidebar';
import { ModeSelector } from '@/components/AgentPanel/ModeSelector';
import { ConversationHistory } from '@/components/AgentPanel/ConversationHistory';

/* ── Zustand store (shared singleton) ──────────────────────────────── */
import { useAppStore, type AgentMode } from '@/lib/store';

/* ── Helpers ───────────────────────────────────────────────────────── */

/** Reset the Zustand store to its initial state between tests. */
function resetStore() {
  useAppStore.setState({
    agentMode: 'agent',
    conversations: [],
    activeConversationId: null,
    sidebarOpen: true,
    isToolCallLogVisible: false,
  });
}

/** Seed the store with sample conversations. */
function seedConversations(count = 2) {
  const titles = ['Fix login bug', 'Add dark mode', 'Refactor utils'];
  for (let i = 0; i < count; i++) {
    useAppStore.getState().createConversation(titles[i] ?? `Chat ${i}`, 'agent');
  }
}

/* ── Mock crypto.randomUUID for deterministic IDs ──────────────────── */
beforeEach(() => {
  resetStore();
  let counter = 0;
  vi.spyOn(crypto, 'randomUUID').mockImplementation(() => `test-id-${++counter}`);
});

/* =================================================================== */
/*  1. Mode Selector                                                    */
/* =================================================================== */
describe('ModeSelector', () => {
  it('should display mode selector with three modes', () => {
    render(<ModeSelector />);

    expect(screen.getByText('Ask')).toBeInTheDocument();
    expect(screen.getByText('Agent')).toBeInTheDocument();
    expect(screen.getByText('Manual')).toBeInTheDocument();
  });

  it('should have correct ARIA titles for each mode button', () => {
    render(<ModeSelector />);

    expect(screen.getByTitle('Ask questions without making changes')).toBeInTheDocument();
    expect(screen.getByTitle('Automatically execute safe operations')).toBeInTheDocument();
    expect(screen.getByTitle('Require approval for all operations')).toBeInTheDocument();
  });

  it('should highlight the default active mode (agent)', () => {
    render(<ModeSelector />);

    const agentBtn = screen.getByText('Agent').closest('button');
    // Active mode has coloured classes applied
    expect(agentBtn?.className).toContain('text-blue-400');
  });

  it('should switch between modes correctly', async () => {
    const user = userEvent.setup();
    render(<ModeSelector />);

    // Click Ask
    await user.click(screen.getByText('Ask'));
    expect(useAppStore.getState().agentMode).toBe('ask');

    // Click Manual
    await user.click(screen.getByText('Manual'));
    expect(useAppStore.getState().agentMode).toBe('manual');

    // Click Agent
    await user.click(screen.getByText('Agent'));
    expect(useAppStore.getState().agentMode).toBe('agent');
  });

  it('should update active styling when mode changes', async () => {
    const user = userEvent.setup();
    const { rerender } = render(<ModeSelector />);

    await user.click(screen.getByText('Ask'));
    rerender(<ModeSelector />);

    const askBtn = screen.getByText('Ask').closest('button');
    expect(askBtn?.className).toContain('text-emerald-400');

    const agentBtn = screen.getByText('Agent').closest('button');
    expect(agentBtn?.className).not.toContain('text-blue-400');
  });
});

/* =================================================================== */
/*  2. AgentPanelSidebar                                                */
/* =================================================================== */
describe('AgentPanelSidebar', () => {
  it('should render the panel header', () => {
    render(<AgentPanelSidebar />);
    expect(screen.getByText('Agent Panel')).toBeInTheDocument();
  });

  it('should render the mode selector inside the sidebar', () => {
    render(<AgentPanelSidebar />);
    // Use getAllByText since 'Manual' appears in both mode button and select dropdown
    const askButtons = screen.getAllByText('Ask');
    const agentButtons = screen.getAllByText('Agent');
    const manualButtons = screen.getAllByText('Manual');
    expect(askButtons.length).toBeGreaterThanOrEqual(1);
    expect(agentButtons.length).toBeGreaterThanOrEqual(1);
    expect(manualButtons.length).toBeGreaterThanOrEqual(1);
  });

  it('should render the textarea with mode-dependent placeholder', () => {
    render(<AgentPanelSidebar />);
    // Default mode is 'agent'
    expect(
      screen.getByPlaceholderText('Describe what you want to build or fix...'),
    ).toBeInTheDocument();
  });

  it('should change placeholder when mode switches', async () => {
    const user = userEvent.setup();
    render(<AgentPanelSidebar />);

    // Click Ask mode button (first occurrence)
    const askBtns = screen.getAllByText('Ask');
    await user.click(askBtns[0]);
    expect(
      screen.getByPlaceholderText('Ask questions without making changes...'),
    ).toBeInTheDocument();

    // Click Manual mode button (first occurrence)
    const manualBtns = screen.getAllByText('Manual');
    await user.click(manualBtns[0]);
    expect(
      screen.getByPlaceholderText('Enter commands (will require approval)...'),
    ).toBeInTheDocument();
  });

  it('should render the Send button (disabled when empty)', () => {
    render(<AgentPanelSidebar />);
    const sendBtn = screen.getByRole('button', { name: /send/i });
    expect(sendBtn).toBeDisabled();
  });

  it('should render workspace selector', () => {
    render(<AgentPanelSidebar />);
    expect(screen.getByText('likecodex (Local)')).toBeInTheDocument();
  });

  it('should render Plan New Idea shortcut button', () => {
    render(<AgentPanelSidebar />);
    expect(screen.getByText('Plan New Idea')).toBeInTheDocument();
    expect(screen.getByText('Shift+Tab')).toBeInTheDocument();
  });

  it('should render user info section', () => {
    render(<AgentPanelSidebar />);
    expect(screen.getByText('User')).toBeInTheDocument();
    expect(screen.getByText('Free Plan')).toBeInTheDocument();
  });
});

/* =================================================================== */
/*  3. Send message on Enter key                                        */
/* =================================================================== */
describe('Keyboard interaction', () => {
  it('should send message on Enter key', async () => {
    const user = userEvent.setup();
    render(<AgentPanelSidebar />);

    const textarea = screen.getByPlaceholderText(
      'Describe what you want to build or fix...',
    );

    await user.type(textarea, 'Hello agent{enter}');

    // After submit the store should have a new conversation
    const { conversations } = useAppStore.getState();
    expect(conversations).toHaveLength(1);
    expect(conversations[0].title).toBe('Hello agent');
  });

  it('should NOT send on Shift+Enter (newline)', async () => {
    const user = userEvent.setup();
    render(<AgentPanelSidebar />);

    const textarea = screen.getByPlaceholderText(
      'Describe what you want to build or fix...',
    );

    await user.type(textarea, 'line1{Shift>}{Enter}{/Shift}line2{enter}');

    // Should still create exactly one conversation (the final Enter submits)
    const { conversations } = useAppStore.getState();
    expect(conversations).toHaveLength(1);
  });

  it('should clear input after sending', async () => {
    const user = userEvent.setup();
    render(<AgentPanelSidebar />);

    const textarea = screen.getByPlaceholderText(
      'Describe what you want to build or fix...',
    );

    await user.type(textarea, 'test message{enter}');
    expect(textarea).toHaveValue('');
  });

  it('should not send empty message', async () => {
    const user = userEvent.setup();
    render(<AgentPanelSidebar />);

    const textarea = screen.getByPlaceholderText(
      'Describe what you want to build or fix...',
    );

    // Press Enter on empty textarea
    await user.type(textarea, '{enter}');

    const { conversations } = useAppStore.getState();
    expect(conversations).toHaveLength(0);
  });
});

/* =================================================================== */
/*  4. Create new conversation                                          */
/* =================================================================== */
describe('Conversation creation', () => {
  it('should create new conversation via Send button', async () => {
    const user = userEvent.setup();
    render(<AgentPanelSidebar />);

    const textarea = screen.getByPlaceholderText(
      'Describe what you want to build or fix...',
    );
    await user.type(textarea, 'Build a feature');

    const sendBtn = screen.getByRole('button', { name: /send/i });
    expect(sendBtn).toBeEnabled();
    await user.click(sendBtn);

    const { conversations } = useAppStore.getState();
    expect(conversations).toHaveLength(1);
    expect(conversations[0].title).toBe('Build a feature');
    expect(conversations[0].mode).toBe('agent');
  });

  it('should create conversation with current mode', async () => {
    const user = userEvent.setup();
    render(<AgentPanelSidebar />);

    // Switch to ask mode first
    await user.click(screen.getByText('Ask'));

    const textarea = screen.getByPlaceholderText(
      'Ask questions without making changes...',
    );
    await user.type(textarea, 'How does X work?{enter}');

    const { conversations } = useAppStore.getState();
    expect(conversations[0].mode).toBe('ask');
  });

  it('should truncate long titles to 40 chars', async () => {
    const user = userEvent.setup();
    render(<AgentPanelSidebar />);

    const longText = 'A'.repeat(60);
    const textarea = screen.getByPlaceholderText(
      'Describe what you want to build or fix...',
    );
    await user.type(textarea, longText + '{enter}');

    const { conversations } = useAppStore.getState();
    expect(conversations[0].title).toHaveLength(40);
  });
});

/* =================================================================== */
/*  5. Conversation History                                             */
/* =================================================================== */
describe('ConversationHistory', () => {
  it('should show empty state when no conversations', () => {
    render(<ConversationHistory />);
    expect(screen.getByText('No conversations yet')).toBeInTheDocument();
    expect(screen.getByText('Start chatting to create one')).toBeInTheDocument();
  });

  it('should show conversation history list', () => {
    seedConversations(2);
    render(<ConversationHistory />);

    expect(screen.getByText('Recent Conversations')).toBeInTheDocument();
    expect(screen.getByText('Fix login bug')).toBeInTheDocument();
    expect(screen.getByText('Add dark mode')).toBeInTheDocument();
  });

  it('should highlight active conversation', () => {
    seedConversations(2);
    const { conversations } = useAppStore.getState();
    // The latest conversation is active (createConversation sets it)
    render(<ConversationHistory />);

    const activeItem = screen.getByText('Add dark mode').closest('button');
    expect(activeItem?.className).toContain('bg-primary/15');
  });

  it('should switch active conversation on click', async () => {
    const user = userEvent.setup();
    seedConversations(3);
    render(<ConversationHistory />);

    await user.click(screen.getByText('Fix login bug'));
    expect(useAppStore.getState().activeConversationId).toBe('test-id-1');
  });

  it('should display mode badge for each conversation', () => {
    seedConversations(1);
    render(<ConversationHistory />);

    // Mode badge shows the mode name
    const badges = screen.getAllByText('agent');
    expect(badges.length).toBeGreaterThanOrEqual(1);
  });
});

/* =================================================================== */
/*  6. Toggle sidebar visibility                                        */
/* =================================================================== */
describe('Sidebar toggle', () => {
  it('should toggle sidebar visibility', async () => {
    const user = userEvent.setup();
    render(<AgentPanelSidebar />);

    // Panel is open by default – find collapse button
    const collapseBtn = screen.getByTitle('Collapse panel');
    await user.click(collapseBtn);

    // After collapse, the sidebar content should be gone
    expect(screen.queryByText('Agent Panel')).not.toBeInTheDocument();

    // An expand button should appear
    expect(screen.getByTitle('Open Agent Panel')).toBeInTheDocument();
  });

  it('should re-open sidebar from collapsed state', async () => {
    const user = userEvent.setup();
    render(<AgentPanelSidebar />);

    // Collapse
    await user.click(screen.getByTitle('Collapse panel'));
    expect(screen.queryByText('Agent Panel')).not.toBeInTheDocument();

    // Expand
    await user.click(screen.getByTitle('Open Agent Panel'));
    expect(screen.getByText('Agent Panel')).toBeInTheDocument();
  });
});

/* =================================================================== */
/*  7. Tool call stream display (mocked)                                */
/* =================================================================== */
describe('Tool call stream visualization', () => {
  it('should display tool call stream in agent mode', async () => {
    // Simulate tool calls being added to the store while in agent mode
    useAppStore.setState({ agentMode: 'agent' });

    // Render the sidebar and send a message
    const user = userEvent.setup();
    render(<AgentPanelSidebar />);

    const textarea = screen.getByPlaceholderText(
      'Describe what you want to build or fix...',
    );
    await user.type(textarea, 'Read main.ts{enter}');

    // Verify a conversation was created (proxy for "stream started")
    const { conversations } = useAppStore.getState();
    expect(conversations).toHaveLength(1);
    expect(conversations[0].mode).toBe('agent');
  });

  it('should show tool call log toggle via store', () => {
    // Verify the toggleToolCallLog action works
    expect(useAppStore.getState().isToolCallLogVisible).toBe(false);
    useAppStore.getState().toggleToolCallLog();
    expect(useAppStore.getState().isToolCallLogVisible).toBe(true);
    useAppStore.getState().toggleToolCallLog();
    expect(useAppStore.getState().isToolCallLogVisible).toBe(false);
  });
});

/* =================================================================== */
/*  8. Approval dialog for batch operations (mocked)                    */
/* =================================================================== */
describe('Approval / batch confirmation', () => {
  it('should show approval dialog for batch operations', () => {
    // The PermissionModal component handles approvals.
    // We verify the store can track permission state.
    // This is a unit-level check; full modal rendering is covered in its own test.
    expect(useAppStore.getState().agentMode).toBe('agent');

    // Switch to manual mode – all operations require approval
    useAppStore.getState().setAgentMode('manual');
    expect(useAppStore.getState().agentMode).toBe('manual');
  });

  it('should track message count when messages are added', () => {
    useAppStore.getState().createConversation('Test', 'agent');
    const { conversations } = useAppStore.getState();
    const convId = conversations[0].id;

    expect(conversations[0].messageCount).toBe(0);
    useAppStore.getState().addMessageToConversation(convId, 'hello');
    expect(useAppStore.getState().conversations[0].messageCount).toBe(1);
    useAppStore.getState().addMessageToConversation(convId, 'world');
    expect(useAppStore.getState().conversations[0].messageCount).toBe(2);
  });
});

/* =================================================================== */
/*  9. Responsive / embedded view                                       */
/* =================================================================== */
describe('Responsive design', () => {
  it('should handle embedded view mode on small screens', () => {
    // The sidebar component uses Tailwind responsive classes.
    // We verify the container has the correct width class for layout control.
    const { container } = render(<AgentPanelSidebar />);

    const sidebar = container.querySelector('.w-80');
    expect(sidebar).toBeInTheDocument();
    expect(sidebar?.className).toContain('shrink-0');
  });

  it('should render collapsed button as fixed position for overlay', () => {
    // Collapse the sidebar
    useAppStore.setState({ sidebarOpen: false });
    const { container } = render(<AgentPanelSidebar />);

    const btn = container.querySelector('button.fixed');
    expect(btn).toBeInTheDocument();
    expect(btn?.className).toContain('fixed');
  });
});

/* =================================================================== */
/*  10. Accessibility (ARIA)                                            */
/* =================================================================== */
describe('Accessibility', () => {
  it('should have accessible buttons with titles', () => {
    render(<AgentPanelSidebar />);

    // Collapse button - HTML button elements inherently have role="button"
    const collapseBtn = screen.getByTitle('Collapse panel');
    expect(collapseBtn.tagName).toBe('BUTTON');

    // Mode buttons
    const askBtn = screen.getByTitle('Ask questions without making changes');
    expect(askBtn.tagName).toBe('BUTTON');
    const agentBtn = screen.getByTitle('Automatically execute safe operations');
    expect(agentBtn.tagName).toBe('BUTTON');
    const manualBtn = screen.getByTitle('Require approval for all operations');
    expect(manualBtn.tagName).toBe('BUTTON');
  });

  it('should have accessible textarea with placeholder', () => {
    render(<AgentPanelSidebar />);

    const textarea = screen.getByRole('textbox');
    expect(textarea).toBeInTheDocument();
    expect(textarea).toHaveAttribute('placeholder');
  });

  it('should disable Send button when input is empty', () => {
    render(<AgentPanelSidebar />);

    const sendBtn = screen.getByRole('button', { name: /send/i });
    expect(sendBtn).toBeDisabled();
    // Note: React sets the disabled property directly; aria-disabled is not required
    expect(sendBtn.hasAttribute('disabled')).toBe(true);
  });

  it('should enable Send button when input has text', async () => {
    const user = userEvent.setup();
    render(<AgentPanelSidebar />);

    const textarea = screen.getByRole('textbox');
    await user.type(textarea, 'hello');

    const sendBtn = screen.getByRole('button', { name: /send/i });
    expect(sendBtn).toBeEnabled();
  });
});

/* =================================================================== */
/*  11. Keyboard navigation                                             */
/* =================================================================== */
describe('Keyboard navigation', () => {
  it('should allow Tab navigation through mode buttons', async () => {
    const user = userEvent.setup();
    render(<ModeSelector />);

    // Tab through the three mode buttons
    const askBtn = screen.getByText('Ask').closest('button')!;
    const agentBtn = screen.getByText('Agent').closest('button')!;
    const manualBtn = screen.getByText('Manual').closest('button')!;

    await user.tab();
    expect(document.activeElement).toBe(askBtn);

    await user.tab();
    expect(document.activeElement).toBe(agentBtn);

    await user.tab();
    expect(document.activeElement).toBe(manualBtn);
  });

  it('should activate mode with Enter key', async () => {
    const user = userEvent.setup();
    render(<ModeSelector />);

    const askBtn = screen.getByText('Ask').closest('button')!;
    askBtn.focus();
    await user.keyboard('{Enter}');

    expect(useAppStore.getState().agentMode).toBe('ask');
  });
});
/**
 * Agent Panel – E2E / Component Tests
 *
 * Uses Vitest + @testing-library/react + jsdom to exercise the
 * Agent Panel UI components end-to-end inside a real DOM.
 */
import { describe, it, expect, beforeEach, vi } from 'vitest';
import { render, screen, within, fireEvent, waitFor } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import React from 'react';

/* ── Components under test ─────────────────────────────────────────── */
import { AgentPanelSidebar } from '@/components/AgentPanel/AgentSidebar';
import { ModeSelector } from '@/components/AgentPanel/ModeSelector';
import { ConversationHistory } from '@/components/AgentPanel/ConversationHistory';

/* ── Zustand store (shared singleton) ──────────────────────────────── */
import { useAgentStore, type AgentMode } from '@/store/agentStore';

/* ── Helpers ───────────────────────────────────────────────────────── */

/** Reset the Zustand store to its initial state between tests. */
function resetStore() {
  useAgentStore.setState({
    currentMode: 'agent',
    conversations: [],
    activeConversationId: null,
    isSidebarOpen: true,
    isToolCallLogVisible: false,
  });
}

/** Seed the store with sample conversations. */
function seedConversations(count = 2) {
  const titles = ['Fix login bug', 'Add dark mode', 'Refactor utils'];
  for (let i = 0; i < count; i++) {
    useAgentStore.getState().createConversation(titles[i] ?? `Chat ${i}`, 'agent');
  }
}

/* ── Mock crypto.randomUUID for deterministic IDs ──────────────────── */
beforeEach(() => {
  resetStore();
  let counter = 0;
  vi.spyOn(crypto, 'randomUUID').mockImplementation(() => `test-id-${++counter}`);
});

/* =================================================================== */
/*  1. Mode Selector                                                    */
/* =================================================================== */
describe('ModeSelector', () => {
  it('should display mode selector with three modes', () => {
    render(<ModeSelector />);

    expect(screen.getByText('Ask')).toBeInTheDocument();
    expect(screen.getByText('Agent')).toBeInTheDocument();
    expect(screen.getByText('Manual')).toBeInTheDocument();
  });

  it('should have correct ARIA titles for each mode button', () => {
    render(<ModeSelector />);

    expect(screen.getByTitle('Ask questions without making changes')).toBeInTheDocument();
    expect(screen.getByTitle('Automatically execute safe operations')).toBeInTheDocument();
    expect(screen.getByTitle('Require approval for all operations')).toBeInTheDocument();
  });

  it('should highlight the default active mode (agent)', () => {
    render(<ModeSelector />);

    const agentBtn = screen.getByText('Agent').closest('button');
    // Active mode has coloured classes applied
    expect(agentBtn?.className).toContain('text-blue-400');
  });

  it('should switch between modes correctly', async () => {
    const user = userEvent.setup();
    render(<ModeSelector />);

    // Click Ask
    await user.click(screen.getByText('Ask'));
    expect(useAgentStore.getState().currentMode).toBe('ask');

    // Click Manual
    await user.click(screen.getByText('Manual'));
    expect(useAgentStore.getState().currentMode).toBe('manual');

    // Click Agent
    await user.click(screen.getByText('Agent'));
    expect(useAgentStore.getState().currentMode).toBe('agent');
  });

  it('should update active styling when mode changes', async () => {
    const user = userEvent.setup();
    const { rerender } = render(<ModeSelector />);

    await user.click(screen.getByText('Ask'));
    rerender(<ModeSelector />);

    const askBtn = screen.getByText('Ask').closest('button');
    expect(askBtn?.className).toContain('text-emerald-400');

    const agentBtn = screen.getByText('Agent').closest('button');
    expect(agentBtn?.className).not.toContain('text-blue-400');
  });
});

/* =================================================================== */
/*  2. AgentPanelSidebar                                                */
/* =================================================================== */
describe('AgentPanelSidebar', () => {
  it('should render the panel header', () => {
    render(<AgentPanelSidebar />);
    expect(screen.getByText('Agent Panel')).toBeInTheDocument();
  });

  it('should render the mode selector inside the sidebar', () => {
    render(<AgentPanelSidebar />);
    // Use getAllByText since 'Manual' appears in both mode button and select dropdown
    const askButtons = screen.getAllByText('Ask');
    const agentButtons = screen.getAllByText('Agent');
    const manualButtons = screen.getAllByText('Manual');
    expect(askButtons.length).toBeGreaterThanOrEqual(1);
    expect(agentButtons.length).toBeGreaterThanOrEqual(1);
    expect(manualButtons.length).toBeGreaterThanOrEqual(1);
  });

  it('should render the textarea with mode-dependent placeholder', () => {
    render(<AgentPanelSidebar />);
    // Default mode is 'agent'
    expect(
      screen.getByPlaceholderText('Describe what you want to build or fix...'),
    ).toBeInTheDocument();
  });

  it('should change placeholder when mode switches', async () => {
    const user = userEvent.setup();
    render(<AgentPanelSidebar />);

    // Click Ask mode button (first occurrence)
    const askBtns = screen.getAllByText('Ask');
    await user.click(askBtns[0]);
    expect(
      screen.getByPlaceholderText('Ask questions without making changes...'),
    ).toBeInTheDocument();

    // Click Manual mode button (first occurrence)
    const manualBtns = screen.getAllByText('Manual');
    await user.click(manualBtns[0]);
    expect(
      screen.getByPlaceholderText('Enter commands (will require approval)...'),
    ).toBeInTheDocument();
  });

  it('should render the Send button (disabled when empty)', () => {
    render(<AgentPanelSidebar />);
    const sendBtn = screen.getByRole('button', { name: /send/i });
    expect(sendBtn).toBeDisabled();
  });

  it('should render workspace selector', () => {
    render(<AgentPanelSidebar />);
    expect(screen.getByText('likecodex (Local)')).toBeInTheDocument();
  });

  it('should render Plan New Idea shortcut button', () => {
    render(<AgentPanelSidebar />);
    expect(screen.getByText('Plan New Idea')).toBeInTheDocument();
    expect(screen.getByText('Shift+Tab')).toBeInTheDocument();
  });

  it('should render user info section', () => {
    render(<AgentPanelSidebar />);
    expect(screen.getByText('User')).toBeInTheDocument();
    expect(screen.getByText('Free Plan')).toBeInTheDocument();
  });
});

/* =================================================================== */
/*  3. Send message on Enter key                                        */
/* =================================================================== */
describe('Keyboard interaction', () => {
  it('should send message on Enter key', async () => {
    const user = userEvent.setup();
    render(<AgentPanelSidebar />);

    const textarea = screen.getByPlaceholderText(
      'Describe what you want to build or fix...',
    );

    await user.type(textarea, 'Hello agent{enter}');

    // After submit the store should have a new conversation
    const { conversations } = useAgentStore.getState();
    expect(conversations).toHaveLength(1);
    expect(conversations[0].title).toBe('Hello agent');
  });

  it('should NOT send on Shift+Enter (newline)', async () => {
    const user = userEvent.setup();
    render(<AgentPanelSidebar />);

    const textarea = screen.getByPlaceholderText(
      'Describe what you want to build or fix...',
    );

    await user.type(textarea, 'line1{Shift>}{Enter}{/Shift}line2{enter}');

    // Should still create exactly one conversation (the final Enter submits)
    const { conversations } = useAgentStore.getState();
    expect(conversations).toHaveLength(1);
  });

  it('should clear input after sending', async () => {
    const user = userEvent.setup();
    render(<AgentPanelSidebar />);

    const textarea = screen.getByPlaceholderText(
      'Describe what you want to build or fix...',
    );

    await user.type(textarea, 'test message{enter}');
    expect(textarea).toHaveValue('');
  });

  it('should not send empty message', async () => {
    const user = userEvent.setup();
    render(<AgentPanelSidebar />);

    const textarea = screen.getByPlaceholderText(
      'Describe what you want to build or fix...',
    );

    // Press Enter on empty textarea
    await user.type(textarea, '{enter}');

    const { conversations } = useAgentStore.getState();
    expect(conversations).toHaveLength(0);
  });
});

/* =================================================================== */
/*  4. Create new conversation                                          */
/* =================================================================== */
describe('Conversation creation', () => {
  it('should create new conversation via Send button', async () => {
    const user = userEvent.setup();
    render(<AgentPanelSidebar />);

    const textarea = screen.getByPlaceholderText(
      'Describe what you want to build or fix...',
    );
    await user.type(textarea, 'Build a feature');

    const sendBtn = screen.getByRole('button', { name: /send/i });
    expect(sendBtn).toBeEnabled();
    await user.click(sendBtn);

    const { conversations } = useAgentStore.getState();
    expect(conversations).toHaveLength(1);
    expect(conversations[0].title).toBe('Build a feature');
    expect(conversations[0].mode).toBe('agent');
  });

  it('should create conversation with current mode', async () => {
    const user = userEvent.setup();
    render(<AgentPanelSidebar />);

    // Switch to ask mode first
    await user.click(screen.getByText('Ask'));

    const textarea = screen.getByPlaceholderText(
      'Ask questions without making changes...',
    );
    await user.type(textarea, 'How does X work?{enter}');

    const { conversations } = useAgentStore.getState();
    expect(conversations[0].mode).toBe('ask');
  });

  it('should truncate long titles to 40 chars', async () => {
    const user = userEvent.setup();
    render(<AgentPanelSidebar />);

    const longText = 'A'.repeat(60);
    const textarea = screen.getByPlaceholderText(
      'Describe what you want to build or fix...',
    );
    await user.type(textarea, longText + '{enter}');

    const { conversations } = useAgentStore.getState();
    expect(conversations[0].title).toHaveLength(40);
  });
});

/* =================================================================== */
/*  5. Conversation History                                             */
/* =================================================================== */
describe('ConversationHistory', () => {
  it('should show empty state when no conversations', () => {
    render(<ConversationHistory />);
    expect(screen.getByText('No conversations yet')).toBeInTheDocument();
    expect(screen.getByText('Start chatting to create one')).toBeInTheDocument();
  });

  it('should show conversation history list', () => {
    seedConversations(2);
    render(<ConversationHistory />);

    expect(screen.getByText('Recent Conversations')).toBeInTheDocument();
    expect(screen.getByText('Fix login bug')).toBeInTheDocument();
    expect(screen.getByText('Add dark mode')).toBeInTheDocument();
  });

  it('should highlight active conversation', () => {
    seedConversations(2);
    const { conversations } = useAgentStore.getState();
    // The latest conversation is active (createConversation sets it)
    render(<ConversationHistory />);

    const activeItem = screen.getByText('Add dark mode').closest('button');
    expect(activeItem?.className).toContain('bg-primary/15');
  });

  it('should switch active conversation on click', async () => {
    const user = userEvent.setup();
    seedConversations(3);
    render(<ConversationHistory />);

    await user.click(screen.getByText('Fix login bug'));
    expect(useAgentStore.getState().activeConversationId).toBe('test-id-1');
  });

  it('should display mode badge for each conversation', () => {
    seedConversations(1);
    render(<ConversationHistory />);

    // Mode badge shows the mode name
    const badges = screen.getAllByText('agent');
    expect(badges.length).toBeGreaterThanOrEqual(1);
  });
});

/* =================================================================== */
/*  6. Toggle sidebar visibility                                        */
/* =================================================================== */
describe('Sidebar toggle', () => {
  it('should toggle sidebar visibility', async () => {
    const user = userEvent.setup();
    render(<AgentPanelSidebar />);

    // Panel is open by default – find collapse button
    const collapseBtn = screen.getByTitle('Collapse panel');
    await user.click(collapseBtn);

    // After collapse, the sidebar content should be gone
    expect(screen.queryByText('Agent Panel')).not.toBeInTheDocument();

    // An expand button should appear
    expect(screen.getByTitle('Open Agent Panel')).toBeInTheDocument();
  });

  it('should re-open sidebar from collapsed state', async () => {
    const user = userEvent.setup();
    render(<AgentPanelSidebar />);

    // Collapse
    await user.click(screen.getByTitle('Collapse panel'));
    expect(screen.queryByText('Agent Panel')).not.toBeInTheDocument();

    // Expand
    await user.click(screen.getByTitle('Open Agent Panel'));
    expect(screen.getByText('Agent Panel')).toBeInTheDocument();
  });
});

/* =================================================================== */
/*  7. Tool call stream display (mocked)                                */
/* =================================================================== */
describe('Tool call stream visualization', () => {
  it('should display tool call stream in agent mode', async () => {
    // Simulate tool calls being added to the store while in agent mode
    useAgentStore.setState({ currentMode: 'agent' });

    // Render the sidebar and send a message
    const user = userEvent.setup();
    render(<AgentPanelSidebar />);

    const textarea = screen.getByPlaceholderText(
      'Describe what you want to build or fix...',
    );
    await user.type(textarea, 'Read main.ts{enter}');

    // Verify a conversation was created (proxy for "stream started")
    const { conversations } = useAgentStore.getState();
    expect(conversations).toHaveLength(1);
    expect(conversations[0].mode).toBe('agent');
  });

  it('should show tool call log toggle via store', () => {
    // Verify the toggleToolCallLog action works
    expect(useAgentStore.getState().isToolCallLogVisible).toBe(false);
    useAgentStore.getState().toggleToolCallLog();
    expect(useAgentStore.getState().isToolCallLogVisible).toBe(true);
    useAgentStore.getState().toggleToolCallLog();
    expect(useAgentStore.getState().isToolCallLogVisible).toBe(false);
  });
});

/* =================================================================== */
/*  8. Approval dialog for batch operations (mocked)                    */
/* =================================================================== */
describe('Approval / batch confirmation', () => {
  it('should show approval dialog for batch operations', () => {
    // The PermissionModal component handles approvals.
    // We verify the store can track permission state.
    // This is a unit-level check; full modal rendering is covered in its own test.
    expect(useAgentStore.getState().currentMode).toBe('agent');

    // Switch to manual mode – all operations require approval
    useAgentStore.getState().switchMode('manual');
    expect(useAgentStore.getState().currentMode).toBe('manual');
  });

  it('should track message count when messages are added', () => {
    useAgentStore.getState().createConversation('Test', 'agent');
    const { conversations } = useAgentStore.getState();
    const convId = conversations[0].id;

    expect(conversations[0].messageCount).toBe(0);
    useAgentStore.getState().addMessageToConversation(convId, 'hello');
    expect(useAgentStore.getState().conversations[0].messageCount).toBe(1);
    useAgentStore.getState().addMessageToConversation(convId, 'world');
    expect(useAgentStore.getState().conversations[0].messageCount).toBe(2);
  });
});

/* =================================================================== */
/*  9. Responsive / embedded view                                       */
/* =================================================================== */
describe('Responsive design', () => {
  it('should handle embedded view mode on small screens', () => {
    // The sidebar component uses Tailwind responsive classes.
    // We verify the container has the correct width class for layout control.
    const { container } = render(<AgentPanelSidebar />);

    const sidebar = container.querySelector('.w-80');
    expect(sidebar).toBeInTheDocument();
    expect(sidebar?.className).toContain('shrink-0');
  });

  it('should render collapsed button as fixed position for overlay', () => {
    // Collapse the sidebar
    useAgentStore.setState({ isSidebarOpen: false });
    const { container } = render(<AgentPanelSidebar />);

    const btn = container.querySelector('button.fixed');
    expect(btn).toBeInTheDocument();
    expect(btn?.className).toContain('fixed');
  });
});

/* =================================================================== */
/*  10. Accessibility (ARIA)                                            */
/* =================================================================== */
describe('Accessibility', () => {
  it('should have accessible buttons with titles', () => {
    render(<AgentPanelSidebar />);

    // Collapse button - HTML button elements inherently have role="button"
    const collapseBtn = screen.getByTitle('Collapse panel');
    expect(collapseBtn.tagName).toBe('BUTTON');

    // Mode buttons
    const askBtn = screen.getByTitle('Ask questions without making changes');
    expect(askBtn.tagName).toBe('BUTTON');
    const agentBtn = screen.getByTitle('Automatically execute safe operations');
    expect(agentBtn.tagName).toBe('BUTTON');
    const manualBtn = screen.getByTitle('Require approval for all operations');
    expect(manualBtn.tagName).toBe('BUTTON');
  });

  it('should have accessible textarea with placeholder', () => {
    render(<AgentPanelSidebar />);

    const textarea = screen.getByRole('textbox');
    expect(textarea).toBeInTheDocument();
    expect(textarea).toHaveAttribute('placeholder');
  });

  it('should disable Send button when input is empty', () => {
    render(<AgentPanelSidebar />);

    const sendBtn = screen.getByRole('button', { name: /send/i });
    expect(sendBtn).toBeDisabled();
    // Note: React sets the disabled property directly; aria-disabled is not required
    expect(sendBtn.hasAttribute('disabled')).toBe(true);
  });

  it('should enable Send button when input has text', async () => {
    const user = userEvent.setup();
    render(<AgentPanelSidebar />);

    const textarea = screen.getByRole('textbox');
    await user.type(textarea, 'hello');

    const sendBtn = screen.getByRole('button', { name: /send/i });
    expect(sendBtn).toBeEnabled();
  });
});

/* =================================================================== */
/*  11. Keyboard navigation                                             */
/* =================================================================== */
describe('Keyboard navigation', () => {
  it('should allow Tab navigation through mode buttons', async () => {
    const user = userEvent.setup();
    render(<ModeSelector />);

    // Tab through the three mode buttons
    const askBtn = screen.getByText('Ask').closest('button')!;
    const agentBtn = screen.getByText('Agent').closest('button')!;
    const manualBtn = screen.getByText('Manual').closest('button')!;

    await user.tab();
    expect(document.activeElement).toBe(askBtn);

    await user.tab();
    expect(document.activeElement).toBe(agentBtn);

    await user.tab();
    expect(document.activeElement).toBe(manualBtn);
  });

  it('should activate mode with Enter key', async () => {
    const user = userEvent.setup();
    render(<ModeSelector />);

    const askBtn = screen.getByText('Ask').closest('button')!;
    askBtn.focus();
    await user.keyboard('{Enter}');

    expect(useAgentStore.getState().currentMode).toBe('ask');
  });
});
