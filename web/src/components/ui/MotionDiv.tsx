'use client';

import React from 'react';
import { motion, HTMLMotionProps } from 'framer-motion';
import { fadeIn, fadeInUp, slideInFromBottom, scaleIn } from '@/lib/animations';

interface MotionDivProps extends HTMLMotionProps<'div'> {
  animation?: 'fade' | 'fadeUp' | 'slideIn' | 'scale' | 'none';
  delay?: number;
}

export const MotionDiv = React.forwardRef<HTMLDivElement, MotionDivProps>(
  ({ animation = 'fadeUp', delay = 0, children, ...props }, ref) => {
    const variants = {
      fade: fadeIn,
      fadeUp: fadeInUp,
      slideIn: slideInFromBottom,
      scale: scaleIn,
      none: undefined,
    };

    return (
      <motion.div
        ref={ref}
        variants={variants[animation]}
        initial="hidden"
        animate="visible"
        exit="exit"
        transition={{ delay }}
        {...props}
      >
        {children}
      </motion.div>
    );
  }
);

MotionDiv.displayName = 'MotionDiv';
