'use client';

import React, { useState, useRef, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useAppStore } from '@/lib/store';
import { scaleIn, fadeInDown } from '@/lib/animations';

// ── Model definitions ───────────────────────────────────────────────────
const MODELS = [
  {
    id: 'deepseek-v4-flash',
    name: 'DeepSeek V4 Flash',
    description: 'Fast & efficient — great for everyday coding',
    badge: 'Fast',
    badgeColor: 'text-emerald-400',
    tier: 1,
  },
  {
    id: 'deepseek-v4-pro',
    name: 'DeepSeek V4 Pro',
    description: 'Most capable — best for complex reasoning',
    badge: 'Pro',
    badgeColor: 'text-blue-400',
    tier: 2,
  },
  {
    id: 'deepseek-v4-mini',
    name: 'DeepSeek V4 Mini',
    description: 'Lightweight — quick answers & completions',
    badge: 'Mini',
    badgeColor: 'text-amber-400',
    tier: 0,
  },
];

// ── Component ───────────────────────────────────────────────────────────
export const ModelSelector: React.FC = () => {
  const [open, setOpen] = useState(false);
  const selectedModel = useAppStore((s) => s.selectedModel);
  const setSelectedModel = useAppStore((s) => s.setSelectedModel);
  const ref = useRef<HTMLDivElement>(null);

  const current = MODELS.find((m) => m.id === selectedModel) || MODELS[0];

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener('mousedown', handler);
    return () => document.removeEventListener('mousedown', handler);
  }, []);

  return (
    <div ref={ref} className="relative">
      <motion.button
        whileHover={{ scale: 1.02 }}
        whileTap={{ scale: 0.98 }}
        onClick={() => setOpen(!open)}
        className="flex items-center gap-1.5 text-xs text-muted hover:text-foreground transition-colors px-2 py-1 rounded hover:bg-accent/10"
        title="Select model"
      >
        <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 10V3L4 14h7v7l9-11h-7z" />
        </svg>
        <span>{current.name}</span>
        <svg className={`h-3 w-3 transition-transform ${open ? 'rotate-180' : ''}`} fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
        </svg>
      </motion.button>

      <AnimatePresence>
        {open && (
          <motion.div
            variants={fadeInDown}
            initial="hidden"
            animate="visible"
            exit="exit"
            className="absolute top-full left-0 mt-1 w-72 bg-surface border border-border rounded-xl shadow-2xl z-50 overflow-hidden"
          >
            <div className="p-2">
              <div className="text-[10px] font-semibold uppercase tracking-wider text-muted/60 px-2 py-1">
                Select Model
              </div>
              {MODELS.map((model) => {
                const isSelected = model.id === selectedModel;
                return (
                  <button
                    key={model.id}
                    onClick={() => {
                      setSelectedModel(model.id);
                      setOpen(false);
                    }}
                    className={`w-full flex items-start gap-3 p-2.5 rounded-lg transition-colors text-left ${
                      isSelected ? 'bg-primary/10' : 'hover:bg-accent/10'
                    }`}
                  >
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className={`text-sm font-medium ${isSelected ? 'text-primary-400' : 'text-foreground'}`}>
                          {model.name}
                        </span>
                        <span className={`text-[10px] font-medium ${model.badgeColor}`}>{model.badge}</span>
                      </div>
                      <p className="text-[11px] text-muted mt-0.5">{model.description}</p>
                    </div>
                    {isSelected && (
                      <svg className="h-4 w-4 text-primary-400 flex-shrink-0 mt-0.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
                      </svg>
                    )}
                  </button>
                );
              })}
            </div>
            <div className="border-t border-border p-2">
              <div className="flex items-center gap-1.5 px-2 py-1 text-[10px] text-muted/60">
                <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
                </svg>
                <span>Models are cached locally for faster responses</span>
              </div>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  );
};

export default ModelSelector;
