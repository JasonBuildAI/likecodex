'use client';

import { useEffect, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { useAppStore, type Toast } from '@/lib/store';

function ToastItem({
  toast,
  onRemove,
}: {
  toast: Toast;
  onRemove: () => void;
}) {
  const [exiting, setExiting] = useState(false);

  useEffect(() => {
    const timer = setTimeout(() => {
      setExiting(true);
      setTimeout(onRemove, 300);
    }, toast.duration || 4000);
    return () => clearTimeout(timer);
  }, [toast.duration, onRemove]);

  const bgColor = {
    info: 'bg-blue-600/90 backdrop-blur-sm border border-blue-400/30',
    success:
      'bg-green-600/90 backdrop-blur-sm border border-green-400/30',
    warning:
      'bg-amber-600/90 backdrop-blur-sm border border-amber-400/30',
    error: 'bg-red-600/90 backdrop-blur-sm border border-red-400/30',
  }[toast.type || 'info'];

  const icon = {
    info: (
      <svg
        className="h-4 w-4"
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={2}
          d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"
        />
      </svg>
    ),
    success: (
      <svg
        className="h-4 w-4"
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={2}
          d="M5 13l4 4L19 7"
        />
      </svg>
    ),
    warning: (
      <svg
        className="h-4 w-4"
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={2}
          d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4.5c-.77-.833-2.694-.833-3.464 0L3.34 16.5c-.77.833.192 2.5 1.732 2.5z"
        />
      </svg>
    ),
    error: (
      <svg
        className="h-4 w-4"
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={2}
          d="M6 18L18 6M6 6l12 12"
        />
      </svg>
    ),
  }[toast.type || 'info'];

  return (
    <motion.div
      initial={{ opacity: 0, x: 50, scale: 0.9 }}
      animate={{
        opacity: 1,
        x: 0,
        scale: 1,
      }}
      exit={{ opacity: 0, x: 50, scale: 0.9 }}
      transition={{
        type: 'spring',
        stiffness: 200,
        damping: 25,
      }}
      className={`${bgColor} text-white px-4 py-3 rounded-xl shadow-2xl flex items-start gap-2 max-w-sm`}
    >
      <span className="mt-0.5 shrink-0">{icon}</span>
      <p className="text-sm flex-1">{toast.message}</p>
      <motion.button
        whileHover={{ scale: 1.1 }}
        whileTap={{ scale: 0.9 }}
        onClick={() => {
          setExiting(true);
          setTimeout(onRemove, 300);
        }}
        className="ml-2 text-white/70 hover:text-white shrink-0"
      >
        <svg
          className="h-3.5 w-3.5"
          fill="none"
          viewBox="0 0 24 24"
          stroke="currentColor"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            strokeWidth={2}
            d="M6 18L18 6M6 6l12 12"
          />
        </svg>
      </motion.button>
    </motion.div>
  );
}

export function ToastContainer() {
  const toasts = useAppStore((s) => s.toasts);
  const removeToast = useAppStore((s) => s.removeToast);

  return (
    <div className="fixed top-4 right-4 z-[9999] flex flex-col gap-2 pointer-events-none">
      <AnimatePresence mode="popLayout">
        {toasts.map((t) => (
          <div key={t.id} className="pointer-events-auto">
            <ToastItem
              toast={t}
              onRemove={() => removeToast(t.id)}
            />
          </div>
        ))}
      </AnimatePresence>
    </div>
  );
}
'use client';

import { useEffect, useState } from 'react';
import { useAppStore, type Toast } from '@/lib/store';

function ToastItem({ toast, onRemove }: { toast: Toast; onRemove: () => void }) {
  const [exiting, setExiting] = useState(false);

  useEffect(() => {
    const timer = setTimeout(() => {
      setExiting(true);
      setTimeout(onRemove, 300);
    }, toast.duration || 4000);
    return () => clearTimeout(timer);
  }, [toast.duration, onRemove]);

  const bgColor = {
    info: 'bg-primary',
    success: 'bg-green-600',
    warning: 'bg-amber-600',
    error: 'bg-red-600',
  }[toast.type || 'info'];

  const icon = {
    info: (
      <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
      </svg>
    ),
    success: (
      <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 13l4 4L19 7" />
      </svg>
    ),
    warning: (
      <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4.5c-.77-.833-2.694-.833-3.464 0L3.34 16.5c-.77.833.192 2.5 1.732 2.5z" />
      </svg>
    ),
    error: (
      <svg className="h-4 w-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
      </svg>
    ),
  }[toast.type || 'info'];

  return (
    <div
      className={`${exiting ? 'toast-exit' : 'toast-enter'} ${bgColor} text-white px-4 py-3 rounded-lg shadow-lg flex items-start gap-2 max-w-sm`}
    >
      <span className="mt-0.5 shrink-0">{icon}</span>
      <p className="text-sm flex-1">{toast.message}</p>
      <button
        onClick={() => { setExiting(true); setTimeout(onRemove, 300); }}
        className="ml-2 text-white/70 hover:text-white shrink-0"
      >
        <svg className="h-3.5 w-3.5" fill="none" viewBox="0 0 24 24" stroke="currentColor">
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
        </svg>
      </button>
    </div>
  );
}

export function ToastContainer() {
  const toasts = useAppStore((s) => s.toasts);
  const removeToast = useAppStore((s) => s.removeToast);

  if (toasts.length === 0) return null;

  return (
    <div className="fixed top-4 right-4 z-[9999] flex flex-col gap-2">
      {toasts.map((t) => (
        <ToastItem key={t.id} toast={t} onRemove={() => removeToast(t.id)} />
      ))}
    </div>
  );
}
