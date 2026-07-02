'use client';

import React from 'react';
import { motion, HTMLMotionProps } from 'framer-motion';
import { cn } from '@/lib/utils';

interface CardProps extends HTMLMotionProps<'div'> {
  variant?: 'default' | 'elevated' | 'outlined';
  padding?: 'none' | 'sm' | 'md' | 'lg';
  hoverable?: boolean;
}

const variantStyles = {
  default: 'bg-surface border border-border',
  elevated: 'bg-surface shadow-lg border border-border/50',
  outlined: 'border-2 border-border bg-transparent',
};

const paddingStyles = {
  none: '',
  sm: 'p-3',
  md: 'p-4',
  lg: 'p-6',
};

export const Card = React.forwardRef<HTMLDivElement, CardProps>(
  ({ 
    variant = 'default',
    padding = 'md',
    hoverable = false,
    children,
    className = '',
    ...props 
  }, ref) => {
    const combinedStyles = cn(
      'rounded-xl transition-all duration-fast',
      variantStyles[variant],
      paddingStyles[padding],
      hoverable && 'hover:shadow-xl hover:border-primary-500/50 hover:-translate-y-1',
      className
    );

    return (
      <motion.div
        ref={ref}
        className={combinedStyles}
        whileHover={hoverable ? { scale: 1.01 } : undefined}
        {...props}
      >
        {children}
      </motion.div>
    );
  }
);

Card.displayName = 'Card';

// Sub-components for Card structure
export const CardHeader = React.forwardRef<HTMLDivElement, HTMLMotionProps<'div'>>(
  ({ children, className = '', ...props }, ref) => (
    <motion.div
      ref={ref}
      className={cn('mb-4', className)}
      {...props}
    >
      {children}
    </motion.div>
  )
);

CardHeader.displayName = 'CardHeader';

export const CardTitle = React.forwardRef<HTMLHeadingElement, HTMLMotionProps<'h3'>>(
  ({ children, className = '', ...props }, ref) => (
    <motion.h3
      ref={ref}
      className={cn('text-base font-semibold text-foreground', className)}
      {...props}
    >
      {children}
    </motion.h3>
  )
);

CardTitle.displayName = 'CardTitle';

export const CardDescription = React.forwardRef<HTMLParagraphElement, HTMLMotionProps<'p'>>(
  ({ children, className = '', ...props }, ref) => (
    <motion.p
      ref={ref}
      className={cn('text-sm text-muted mt-1', className)}
      {...props}
    >
      {children}
    </motion.p>
  )
);

CardDescription.displayName = 'CardDescription';

export const CardContent = React.forwardRef<HTMLDivElement, HTMLMotionProps<'div'>>(
  ({ children, className = '', ...props }, ref) => (
    <motion.div
      ref={ref}
      className={cn(className)}
      {...props}
    >
      {children}
    </motion.div>
  )
);

CardContent.displayName = 'CardContent';

export const CardFooter = React.forwardRef<HTMLDivElement, HTMLMotionProps<'div'>>(
  ({ children, className = '', ...props }, ref) => (
    <motion.div
      ref={ref}
      className={cn('mt-4 pt-4 border-t border-border', className)}
      {...props}
    >
      {children}
    </motion.div>
  )
);

CardFooter.displayName = 'CardFooter';
