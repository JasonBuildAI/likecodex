'use client';

import React, { useState, useRef, useCallback } from 'react';
import type { ImageItem } from '@/hooks/useMultiModalInput';

interface ImagePreviewProps {
  images: ImageItem[];
  onRemove: (index: number) => void;
  onReorder?: (fromIndex: number, toIndex: number) => void;
}

// ── Helpers ────────────────────────────────────────────────────────────
function formatSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

// ── Component ──────────────────────────────────────────────────────────
export const ImagePreview: React.FC<ImagePreviewProps> = ({
  images,
  onRemove,
  onReorder,
}) => {
  const [dragIndex, setDragIndex] = useState<number | null>(null);
  const [overIndex, setOverIndex] = useState<number | null>(null);
  const dragNode = useRef<HTMLElement | null>(null);

  const handleDragStart = useCallback(
    (e: React.DragEvent, index: number) => {
      dragNode.current = e.currentTarget as HTMLElement;
      setDragIndex(index);
      e.dataTransfer.effectAllowed = 'move';
      // Required for Firefox
      e.dataTransfer.setData('text/plain', `${index}`);
    },
    [],
  );

  const handleDragOver = useCallback(
    (e: React.DragEvent, index: number) => {
      e.preventDefault();
      e.stopPropagation();
      if (dragIndex === null || dragIndex === index) return;
      setOverIndex(index);

      // Visual feedback: add slight movement based on direction
      const rect = (e.currentTarget as HTMLElement).getBoundingClientRect();
      const offset = e.clientX - rect.left;
      // If cursor passes the midpoint, consider it as after this item
      const newOverIndex =
        offset > rect.width / 2 ? Math.min(index + 1, images.length - 1) : index;
      setOverIndex(newOverIndex);
    },
    [dragIndex, images.length],
  );

  const handleDragLeave = useCallback(() => {
    setOverIndex(null);
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent, dropIndex: number) => {
      e.preventDefault();
      e.stopPropagation();
      setOverIndex(null);

      if (dragIndex !== null && dragIndex !== dropIndex && onReorder) {
        onReorder(dragIndex, dropIndex);
      }

      setDragIndex(null);
      dragNode.current = null;
    },
    [dragIndex, onReorder],
  );

  const handleDragEnd = useCallback(() => {
    setDragIndex(null);
    setOverIndex(null);
    dragNode.current = null;
  }, []);

  if (images.length === 0) return null;

  return (
    <div className="flex flex-wrap gap-2 px-3 pb-2" role="list" aria-label="Attached images">
      {images.map((img, index) => {
        const isDragging = dragIndex === index;
        const isDropTarget = overIndex === index && dragIndex !== index;

        return (
          <div
            key={img.id}
            role="listitem"
            draggable
            onDragStart={(e) => handleDragStart(e, index)}
            onDragOver={(e) => handleDragOver(e, index)}
            onDragLeave={handleDragLeave}
            onDrop={(e) => handleDrop(e, index)}
            onDragEnd={handleDragEnd}
            className={`
              group relative flex-shrink-0 rounded-xl overflow-hidden border-2
              transition-all duration-200 cursor-grab active:cursor-grabbing
              ${isDragging
                ? 'opacity-40 border-primary scale-95'
                : isDropTarget
                  ? 'border-primary bg-primary/10 translate-y-1'
                  : 'border-transparent hover:border-border/60'
              }
            `}
            style={{ width: 80, height: 80 }}
          >
            {/* Thumbnail */}
            <img
              src={img.data}
              alt={img.name}
              className="w-full h-full object-cover rounded-lg"
              draggable={false}
            />

            {/* Overlay on hover */}
            <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity duration-200 rounded-lg" />

            {/* File info tooltip */}
            <div className="
              absolute -bottom-1 left-1/2 -translate-x-1/2
              px-1.5 py-0.5 rounded bg-black/80 text-[9px] text-white
              whitespace-nowrap opacity-0 group-hover:opacity-100
              transition-opacity duration-200 pointer-events-none z-10
            ">
              {img.name} · {formatSize(img.size)} · {img.width}×{img.height}
            </div>

            {/* Delete button */}
            <button
              type="button"
              onClick={(e) => {
                e.stopPropagation();
                onRemove(index);
              }}
              className="
                absolute top-0.5 right-0.5
                w-5 h-5 flex items-center justify-center
                rounded-full bg-black/60 text-white
                opacity-0 group-hover:opacity-100
                hover:bg-red-500/80
                transition-all duration-200
                text-xs font-bold
                z-20
              "
              aria-label={`Remove ${img.name}`}
            >
              ×
            </button>

            {/* Drag handle indicator */}
            <div className="
              absolute bottom-1 left-1/2 -translate-x-1/2
              w-4 h-1 rounded-full bg-white/40
              opacity-0 group-hover:opacity-100
              transition-opacity duration-200
            " />
          </div>
        );
      })}
    </div>
  );
};

export default ImagePreview;
