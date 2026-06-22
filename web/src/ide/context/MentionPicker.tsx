'use client';

import { memo, useCallback, useEffect, useRef, useState } from 'react';
import type { ContextMention } from './types';
import { getMentionIcon } from './types';

export interface MentionPickerProps {
  /** Floating position for the picker */
  triggerPosition: { top: number; left: number };
  /** Search query (text after @) */
  query: string;
  /** Called when a mention is selected */
  onSelect: (mention: ContextMention) => void;
  /** Called when the picker should close */
  onClose: () => void;
}

export const MentionPicker = memo(function MentionPicker({
  triggerPosition,
  query,
  onSelect,
  onClose,
}: MentionPickerProps) {
  const [results, setResults] = useState<ContextMention[]>([]);
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [isLoading, setIsLoading] = useState(false);
  const listRef = useRef<HTMLDivElement | null>(null);

  // Search with debounce
  useEffect(() => {
    setIsLoading(true);
    setSelectedIndex(0);

    const timer = setTimeout(async () => {
      try {
        const res = await fetch(
          `/api/ide/context/search?q=${encodeURIComponent(query)}`
        );
        if (res.ok) {
          const data = await res.json();
          const items: ContextMention[] = (data.results || []).map((r: any) => ({
            id: r.id,
            type: r.type,
            label: r.label,
            description: r.description,
            icon: r.icon,
            content: r.content,
            tokenEstimate: r.token_estimate || 0,
            relevanceScore: r.relevance_score || 0,
          }));
          setResults(items);
        } else {
          setResults([]);
        }
      } catch {
        setResults([]);
      } finally {
        setIsLoading(false);
      }
    }, 100);

    return () => clearTimeout(timer);
  }, [query]);

  // Keyboard navigation
  const handleKeyDown = useCallback(
    (e: KeyboardEvent) => {
      switch (e.key) {
        case 'ArrowDown':
          e.preventDefault();
          setSelectedIndex((i) => Math.min(i + 1, results.length - 1));
          break;
        case 'ArrowUp':
          e.preventDefault();
          setSelectedIndex((i) => Math.max(i - 1, 0));
          break;
        case 'Enter':
          e.preventDefault();
          if (results[selectedIndex]) {
            onSelect(results[selectedIndex]);
          }
          break;
        case 'Escape':
          e.preventDefault();
          onClose();
          break;
        case 'Tab':
          if (results[selectedIndex]) {
            e.preventDefault();
            onSelect(results[selectedIndex]);
          }
          break;
      }
    },
    [results, selectedIndex, onSelect, onClose]
  );

  useEffect(() => {
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [handleKeyDown]);

  // Scroll selected item into view
  useEffect(() => {
    if (listRef.current) {
      const selected = listRef.current.children[selectedIndex] as HTMLElement;
      if (selected) {
        selected.scrollIntoView({ block: 'nearest' });
      }
    }
  }, [selectedIndex]);

  // Adjust position to stay within viewport
  const adjustedTop = Math.min(triggerPosition.top, window.innerHeight - 350);
  const adjustedLeft = Math.min(triggerPosition.left, window.innerWidth - 400);

  return (
    <div
      className="fixed z-50 bg-surface border border-border rounded-lg shadow-2xl w-96 max-h-96 flex flex-col"
      style={{ top: adjustedTop, left: adjustedLeft }}
    >
      {/* Results list */}
      <div ref={listRef} className="overflow-y-auto flex-1 py-1">
        {isLoading ? (
          <div className="px-3 py-4 text-center text-xs text-muted">
            Searching...
          </div>
        ) : results.length === 0 ? (
          <div className="px-3 py-4 text-center text-xs text-muted/60">
            No results found
          </div>
        ) : (
          results.map((item, index) => (
            <div
              key={item.id}
              className={`flex items-center gap-2 px-3 py-1.5 cursor-pointer text-xs transition-colors ${
                index === selectedIndex
                  ? 'bg-primary/15 text-primary'
                  : 'hover:bg-accent/10 text-foreground'
              }`}
              onClick={() => onSelect(item)}
              onMouseEnter={() => setSelectedIndex(index)}
            >
              <span className="shrink-0 text-sm">{getMentionIcon(item.type)}</span>
              <div className="flex-1 min-w-0">
                <div className="truncate font-medium">{item.label}</div>
                {item.description && (
                  <div className="text-muted/60 text-[10px] truncate">
                    {item.description}
                  </div>
                )}
              </div>
              {item.tokenEstimate > 0 && (
                <span className="text-muted/40 text-[10px] whitespace-nowrap shrink-0">
                  ~{item.tokenEstimate}t
                </span>
              )}
            </div>
          ))
        )}
      </div>

      {/* Footer hint */}
      <div className="px-3 py-1.5 border-t border-border text-[10px] text-muted/50 flex gap-3 shrink-0">
        <span>\u2191\u2193 Navigate</span>
        <span>Enter Select</span>
        <span>Esc Close</span>
      </div>
    </div>
  );
});
