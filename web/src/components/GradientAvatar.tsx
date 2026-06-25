'use client';

import React from 'react';
import { motion } from 'framer-motion';

interface GradientAvatarProps {
  size?: 'sm' | 'md' | 'lg';
  animated?: boolean;
}

const sizeMap = {
  sm: 'h-6 w-6',
  md: 'h-8 w-8',
  lg: 'h-10 w-10',
};

const iconSizeMap = {
  sm: 'h-3.5 w-3.5',
  md: 'h-5 w-5',
  lg: 'h-6 w-6',
};

// ── Component ───────────────────────────────────────────────────────────
export const GradientAvatar: React.FC<GradientAvatarProps> = ({
  size = 'md',
  animated = false,
}) => {
  return (
    <motion.div
      initial={animated ? { scale: 0, rotate: -180 } : undefined}
      animate={animated ? { scale: 1, rotate: 0 } : undefined}
      transition={{ type: 'spring', stiffness: 260, damping: 20 }}
      className={`${sizeMap[size]} relative rounded-full bg-gradient-to-br from-blue-500 via-purple-500 to-pink-500 flex items-center justify-center shadow-md shrink-0`}
    >
      <svg
        className={`${iconSizeMap[size]} text-white`}
        fill="none"
        viewBox="0 0 24 24"
        stroke="currentColor"
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          strokeWidth={2}
          d="M13 10V3L4 14h7v7l9-11h-7z"
        />
      </svg>
      {/* Glow ring */}
      <div className="absolute inset-0 rounded-full bg-gradient-to-br from-blue-500 to-pink-500 opacity-30 blur-sm -z-10" />
    </motion.div>
  );
};

export default GradientAvatar;
