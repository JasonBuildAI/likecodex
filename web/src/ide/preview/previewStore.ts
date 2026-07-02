'use client';

import { create } from 'zustand';

export interface DeviceOption {
  name: string;
  width: number;
  height: number;
}

export const DEFAULT_DEVICES: DeviceOption[] = [
  { name: 'Desktop', width: 1440, height: 900 },
  { name: 'Laptop', width: 1280, height: 720 },
  { name: 'Tablet', width: 768, height: 1024 },
  { name: 'Mobile', width: 375, height: 667 },
];

interface PreviewState {
  url: string;
  isOpen: boolean;
  isLoading: boolean;
  selectedDevice: string;
  setUrl: (url: string) => void;
  setOpen: (open: boolean) => void;
  setLoading: (loading: boolean) => void;
  setDevice: (name: string) => void;
}

export const usePreviewStore = create<PreviewState>((set) => ({
  url: '',
  isOpen: false,
  isLoading: false,
  selectedDevice: 'Desktop',
  setUrl: (url) => set({ url }),
  setOpen: (open) => set({ isOpen: open }),
  setLoading: (loading) => set({ isLoading: loading }),
  setDevice: (name) => set({ selectedDevice: name }),
}));

/** Selector: get current device dimensions from selectedDevice name */
export function useDeviceDimensions(): { width: number; height: number } {
  const name = usePreviewStore((s) => s.selectedDevice);
  const device = DEFAULT_DEVICES.find((d) => d.name === name);
  return { width: device?.width ?? 1440, height: device?.height ?? 900 };
}
