'use client';

import { memo, useCallback, useEffect, useMemo, useRef } from 'react';
import { useVirtualizer } from '@tanstack/react-virtual';
import { motion } from 'framer-motion';
import { useAppStore } from '@/lib/store';
import { MessageBubble, ActivityGroup } from './ChatMessageItem';

interface ChatMessageListProps {
  scrollRef: React.RefObject<HTMLDivElement | null>;
}

export const ChatMessageList = memo(function ChatMessageList({
  scrollRef,
}: ChatMessageListProps) {
  const messages = useAppStore((s) => s.messages);

  // Pre-process: group consecutive tool messages into activity blocks
  const groupedItems = useMemo(() => {
    const items: Array<
      | { type: 'message'; msg: import('@/lib/store').Message }
      | { type: 'activity'; messages: import('@/lib/store').Message[] }
    > = [];
    let toolBuffer: import('@/lib/store').Message[] = [];

    for (const msg of messages) {
      if (
        msg.eventType === 'tool_call' ||
        msg.eventType === 'tool_dispatch' ||
        msg.eventType === 'tool_result'
      ) {
        toolBuffer.push(msg);
      } else {
        if (toolBuffer.length > 0) {
          items.push({ type: 'activity', messages: [...toolBuffer] });
          toolBuffer = [];
        }
        items.push({ type: 'message', msg });
      }
    }
    if (toolBuffer.length > 0) {
      items.push({ type: 'activity', messages: toolBuffer });
    }
    return items;
  }, [messages]);

  const estimateSize = useCallback(() => 80, []);

  const prevLengthRef = useRef(groupedItems.length);

  const virtualizer = useVirtualizer({
    count: groupedItems.length,
    getScrollElement: () => scrollRef.current,
    estimateSize,
    overscan: 5,
  });

  // Auto-scroll to bottom on new items
  useEffect(() => {
    if (
      groupedItems.length > prevLengthRef.current &&
      scrollRef.current
    ) {
      const el = scrollRef.current;
      const isNearBottom =
        el.scrollHeight - el.scrollTop - el.clientHeight < 200;
      if (isNearBottom) {
        virtualizer.scrollToIndex(groupedItems.length - 1, {
          align: 'end',
        });
      }
    }
    prevLengthRef.current = groupedItems.length;
  }, [groupedItems.length, virtualizer, scrollRef]);

  if (groupedItems.length === 0) {
    return (
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        className="flex items-center justify-center h-full"
      >
        <div className="text-center text-muted">
          <motion.p
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.1 }}
            className="text-lg"
          >
            What would you like to build?
          </motion.p>
          <motion.p
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: 0.2 }}
            className="text-sm mt-2"
          >
            Try: /plan then describe a refactor, or ask to fix failing tests
          </motion.p>
        </div>
      </motion.div>
    );
  }

  return (
    <div
      style={{
        height: `${virtualizer.getTotalSize()}px`,
        width: '100%',
        position: 'relative',
      }}
    >
      {virtualizer.getVirtualItems().map((virtualItem) => {
        const item = groupedItems[virtualItem.index];
        return (
          <div
            key={
              item.type === 'message'
                ? item.msg.id
                : `activity-${virtualItem.index}`
            }
            style={{
              position: 'absolute',
              top: 0,
              left: 0,
              width: '100%',
              transform: `translateY(${virtualItem.start}px)`,
            }}
            ref={virtualizer.measureElement}
            data-index={virtualItem.index}
          >
            <div className="px-1 py-1.5">
              {item.type === 'message' ? (
                <MessageBubble
                  msg={item.msg}
                  index={virtualItem.index}
                />
              ) : (
                <ActivityGroup messages={item.messages} />
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
});
