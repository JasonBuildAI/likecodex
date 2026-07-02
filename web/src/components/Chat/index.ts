// Chat Components Barrel
// Re-exports all chat-related components

// Virtualized chat message list (replaces the old ChatMessages)
export { ChatMessageList } from './ChatMessageList';

// Backward-compatible alias: ChatMessageList was originally exported as ChatMessages
export { ChatMessageList as ChatMessages } from './ChatMessageList';

// Message rendering
export { ChatMessageItem, MessageBubble, ActivityGroup } from './ChatMessageItem';

// Input area
export { ChatInputPanel } from './ChatInputPanel';

// Toolbar (mode switching, model selection, settings)
export { ChatToolbar } from './ChatToolbar';

// Session sidebar
export { ChatSessionBar } from './ChatSessionBar';

// Main container (orchestrates Toolbar + MessageList + InputPanel)
export { ChatContainer } from './ChatContainer';

// Also re-export legacy Chat component (from ChatMessageItem)
export { MessageBubble as Chat } from './ChatMessageItem';

// Re-export EmbeddedAgentView from the same directory
export { EmbeddedAgentView } from './EmbeddedAgentView';
// Chat Components Barrel
// Re-exports all chat-related components

export { ChatMessageList } from './ChatMessageList';
export { ChatMessageItem, MessageBubble, ActivityGroup } from './ChatMessageItem';
export { ChatInputPanel } from './ChatInputPanel';
export { ChatToolbar } from './ChatToolbar';
export { ChatSessionBar } from './ChatSessionBar';
export { ChatContainer } from './ChatContainer';

// Re-export EmbeddedAgentView from the same directory
export { EmbeddedAgentView } from './EmbeddedAgentView';
