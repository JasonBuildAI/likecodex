'use client';

import { useState, useCallback } from 'react';

// ── Types ──────────────────────────────────────────────────────────────
export interface ImageItem {
  id: string;
  /** base64 data URL (e.g. `data:image/png;base64,...`) */
  data: string;
  mime: string;
  name: string;
  size: number;
  width: number;
  height: number;
}

// ── Image compression ──────────────────────────────────────────────────
const MAX_IMAGE_DIMENSION = 2048;
const JPEG_QUALITY = 0.85;

function compressImage(file: File, maxSize = MAX_IMAGE_DIMENSION): Promise<ImageItem> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const img = new Image();
      img.onload = () => {
        let { width, height } = img;

        // Scale down if either dimension exceeds maxSize
        if (width > maxSize || height > maxSize) {
          const ratio = Math.min(maxSize / width, maxSize / height);
          width = Math.round(width * ratio);
          height = Math.round(height * ratio);
        }

        const canvas = document.createElement('canvas');
        canvas.width = width;
        canvas.height = height;
        const ctx = canvas.getContext('2d');
        if (!ctx) {
          reject(new Error('Failed to get canvas 2D context'));
          return;
        }
        ctx.drawImage(img, 0, 0, width, height);

        // Convert to base64 data URL
        const mime = file.type || 'image/jpeg';
        const data = canvas.toDataURL(mime, JPEG_QUALITY);

        resolve({
          id: crypto.randomUUID(),
          data,
          mime,
          name: file.name || `pasted-${Date.now()}.png`,
          size: file.size,
          width,
          height,
        });
      };
      img.onerror = () => reject(new Error('Failed to load image'));
      img.src = reader.result as string;
    };
    reader.onerror = () => reject(new Error('Failed to read file'));
    reader.readAsDataURL(file);
  });
}

/** Extract image files from a DataTransfer (clipboard / drag-drop) */
function extractImageFiles(items: DataTransferItemList | FileList): File[] {
  const files: File[] = [];
  for (let i = 0; i < items.length; i++) {
    const item = items[i];
    const file = item instanceof File ? item : item.getAsFile();
    if (file && file.type.startsWith('image/')) {
      files.push(file);
    }
  }
  return files;
}

// ── Hook ───────────────────────────────────────────────────────────────
export function useMultiModalInput() {
  const [images, setImages] = useState<ImageItem[]>([]);
  const [isDragOver, setIsDragOver] = useState(false);

  const addImage = useCallback(async (file: File) => {
    if (!file.type.startsWith('image/')) return;
    try {
      const item = await compressImage(file);
      setImages((prev) => [...prev, item]);
    } catch (err) {
      console.error('Failed to process image:', err);
    }
  }, []);

  const addImagesFromFiles = useCallback(
    async (files: FileList | File[]) => {
      const imageFiles = Array.from(files).filter((f) =>
        f.type.startsWith('image/'),
      );
      if (imageFiles.length === 0) return;

      const processed = await Promise.allSettled(
        imageFiles.map((f) => compressImage(f)),
      );
      const newItems: ImageItem[] = [];
      for (const result of processed) {
        if (result.status === 'fulfilled') {
          newItems.push(result.value);
        } else {
          console.error('Image compression failed:', result.reason);
        }
      }
      if (newItems.length > 0) {
        setImages((prev) => [...prev, ...newItems]);
      }
    },
    [],
  );

  const removeImage = useCallback((index: number) => {
    setImages((prev) => prev.filter((_, i) => i !== index));
  }, []);

  const clearImages = useCallback(() => {
    setImages([]);
  }, []);

  const reorderImages = useCallback(
    (fromIndex: number, toIndex: number) => {
      setImages((prev) => {
        const next = [...prev];
        const [moved] = next.splice(fromIndex, 1);
        next.splice(toIndex, 0, moved);
        return next;
      });
    },
    [],
  );

  // ── Paste handler ──────────────────────────────────────────────────
  const pasteHook = useCallback(
    (e: ClipboardEvent) => {
      if (!e.clipboardData) return;
      const files = extractImageFiles(e.clipboardData.items);
      if (files.length > 0) {
        e.preventDefault();
        addImagesFromFiles(files);
      }
    },
    [addImagesFromFiles],
  );

  // ── Drag & drop handlers ───────────────────────────────────────────
  const dropHook = useCallback(
    (e: DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
      setIsDragOver(false);

      if (!e.dataTransfer) return;

      // Handle files dropped from the OS
      if (e.dataTransfer.files.length > 0) {
        const files = extractImageFiles(e.dataTransfer.files);
        if (files.length > 0) {
          addImagesFromFiles(files);
          return;
        }
      }

      // Handle items from other sources (e.g. browser drag)
      const files = extractImageFiles(e.dataTransfer.items);
      if (files.length > 0) {
        addImagesFromFiles(files);
      }
    },
    [addImagesFromFiles],
  );

  const dragOverHook = useCallback((e: DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(true);
  }, []);

  const dragLeaveHook = useCallback((e: DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragOver(false);
  }, []);

  // ── Hidden file input opener ───────────────────────────────────────
  const openFilePicker = useCallback(() => {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = 'image/*';
    input.multiple = true;
    input.onchange = () => {
      if (input.files && input.files.length > 0) {
        addImagesFromFiles(input.files);
      }
      input.remove();
    };
    input.click();
  }, [addImagesFromFiles]);

  return {
    images,
    isDragOver,
    addImage,
    addImagesFromFiles,
    removeImage,
    clearImages,
    reorderImages,
    pasteHook,
    dropHook,
    dragOverHook,
    dragLeaveHook,
    openFilePicker,
  };
}
