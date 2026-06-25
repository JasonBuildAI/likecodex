'use client';

import React, { useEffect, useRef, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { GradientAvatar } from '@/components/GradientAvatar';

// ── StreamingResponse: animates text as it streams in ────────────────────
interface StreamingResponseProps {
  content: string;
  isStreaming: boolean;
}

export const StreamingResponse: React.FC<StreamingResponseProps> = ({ content, isStreaming }) => {
  const [displayedText, setDisplayedText] = useState('');
  const containerRef = useRef<HTMLDivElement>(null);
  const prevLengthRef = useRef(0);

  useEffect(() => {
    if (content.length > prevLengthRef.current) {
      // New text arrived - smoothly append
      const newText = content.slice(prevLengthRef.current);
      let charIndex = 0;
      const interval = setInterval(() => {
        if (charIndex < newText.length) {
          setDisplayedText(content.slice(0, prevLengthRef.current + charIndex + 1));
          charIndex++;
        } else {
          clearInterval(interval);
          prevLengthRef.current = content.length;
        }
      }, 10); // Fast append for streaming feel
      return () => clearInterval(interval);
    } else if (content.length < prevLengthRef.current) {
      // Reset (new message)
      setDisplayedText(content);
      prevLengthRef.current = content.length;
    }
  }, [content]);

  // Auto-scroll to bottom
  useEffect(() => {
    if (containerRef.current) {
      containerRef.current.scrollTop = containerRef.current.scrollHeight;
    }
  }, [displayedText]);

  return (
    <div ref={containerRef} className="text-sm leading-relaxed whitespace-pre-wrap break-words">
      {displayedText}
      {isStreaming && (
        <motion.span
          animate={{ opacity: [1, 0, 1] }}
          transition={{ duration: 0.8, repeat: Infinity, ease: 'easeInOut' }}
          className="inline-block w-2 h-4 bg-primary-500 ml-0.5 align-middle rounded-sm"
        />
      )}
    </div>
  );
};

// ── ProgressIndicator: shows status messages with spinner ────────────────
interface ProgressStep {
  label: string;
  status: 'pending' | 'active' | 'completed' | 'error';
}

interface ProgressIndicatorProps {
  steps: ProgressStep[];
  currentStep?: string;
}

export const ProgressIndicator: React.FC<ProgressIndicatorProps> = ({ steps, currentStep }) => {
  return (
    <motion.div
      initial={{ opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -10 }}
      className="rounded-xl border border-border/50 bg-surface/50 p-3 space-y-2"
    >
      {/* Current status header */}
      {currentStep && (
        <div className="flex items-center gap-2 text-xs text-muted">
          <motion.div
            animate={{ rotate: 360 }}
            transition={{ duration: 1.5, repeat: Infinity, ease: 'linear' }}
            className="h-3.5 w-3.5 rounded-full border-2 border-primary-500/30 border-t-primary-500"
          />
          <span>{currentStep}</span>
        </div>
      )}

      {/* Steps list */}
      {steps.length > 0 && (
        <div className="space-y-1">
          {steps.map((step, idx) => (
            <div key={idx} className="flex items-center gap-2 text-[11px]">
              {/* Status icon */}
              {step.status === 'completed' && (
                <svg className="h-3 w-3 text-emerald-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                </svg>
              )}
              {step.status === 'active' && (
                <motion.div
                  animate={{ rotate: 360 }}
                  transition={{ duration: 1, repeat: Infinity, ease: 'linear' }}
                  className="h-3 w-3 rounded-full border-2 border-primary-500/30 border-t-primary-500"
                />
              )}
              {step.status === 'pending' && (
                <div className="h-3 w-3 rounded-full border border-border" />
              )}
              {step.status === 'error' && (
                <svg className="h-3 w-3 text-red-400" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                </svg>
              )}
              {/* Label */}
              <span className={
                step.status === 'completed' ? 'text-muted/60 line-through' :
                step.status === 'active' ? 'text-foreground font-medium' :
                step.status === 'error' ? 'text-red-400' :
                'text-muted/40'
              }>
                {step.label}
              </span>
            </div>
          ))}
        </div>
      )}

      {/* Progress bar */}
      {steps.length > 0 && (
        <div className="h-1 rounded-full bg-border/50 overflow-hidden">
          <motion.div
            className="h-full bg-gradient-to-r from-primary-500 to-purple-500"
            initial={{ width: 0 }}
            animate={{
              width: `${(steps.filter(s => s.status === 'completed').length / steps.length) * 100}%`
            }}
            transition={{ duration: 0.3 }}
          />
        </div>
      )}
    </motion.div>
  );
};

// ── ThinkingIndicator: shows 'Agent is thinking...' with animated dots ───
export const ThinkingIndicator: React.FC<{ message?: string }> = ({ message = 'Agent is thinking' }) => {
  return (
    <motion.div
      initial={{ opacity: 0, scale: 0.95 }}
      animate={{ opacity: 1, scale: 1 }}
      exit={{ opacity: 0, scale: 0.95 }}
      className="flex items-center gap-2 py-2"
    >
      <GradientAvatar size="sm" />
      <div className="flex items-center gap-1">
        <span className="text-xs text-muted">{message}</span>
        {[0, 1, 2].map((i) => (
          <motion.span
            key={i}
            className="text-muted text-xs"
            animate={{ opacity: [0.3, 1, 0.3] }}
            transition={{
              duration: 1.2,
              repeat: Infinity,
              delay: i * 0.15,
              ease: 'easeInOut',
            }}
          >
            .
          </motion.span>
        ))}
      </div>
    </motion.div>
  );
};
export default StreamingResponse;
