'use client';

import React from 'react';
import { motion, HTMLMotionProps } from 'framer-motion';

type BadgeVariant = 'default' | 'primary' | 'secondary' | 'success' | 'warning' | 'danger' | 'outline';
type BadgeSize = 'sm' | 'md' | 'lg';

interface BadgeProps extends Omit<HTMLMotionProps<'span'>, 'size'> {
  variant?: BadgeVariant;
  size?: BadgeSize;
  dot?: boolean;
}

const variantStyles: Record<BadgeVariant, string> = {
  default: 'bg-surface text-foreground border border-border',
  primary: 'bg-primary-500/20 text-primary-400 border border-primary-500/30',
  secondary: 'bg-accent/10 text-accent border border-accent/20',
  success: 'bg-emerald-500/20 text-emerald-400 border border-emerald-500/30',
  warning: 'bg-amber-500/20 text-amber-400 border border-amber-500/30',
  danger: 'bg-red-500/20 text-red-400 border border-red-500/30',
  outline: 'bg-transparent text-foreground border border-border',
};

const sizeStyles: Record<BadgeSize, string> = {
  sm: 'px-1.5 py-0.5 text-[10px] rounded-sm',
  md: 'px-2 py-1 text-xs rounded-md',
  lg: 'px-3 py-1.5 text-sm rounded-lg',
};

export const Badge = React.forwardRef<HTMLSpanElement, BadgeProps>(
  ({ 
    variant = 'default',
    size = 'md',
    dot = false,
    children,
    className = '',
    ...props 
  }, ref) => {
    const baseStyles = 'inline-flex items-center gap-1.5 font-medium transition-all duration-fast';
    const combinedStyles = `${baseStyles} ${variantStyles[variant]} ${sizeStyles[size]} ${className}`;

    return (
      <motion.span
        ref={ref}
        className={combinedStyles}
        initial={{ scale: 0.8, opacity: 0 }}
        animate={{ scale: 1, opacity: 1 }}
        {...props}
      >
        {dot && (
          <span className={`w-1.5 h-1.5 rounded-full ${
            variant === 'success' ? 'bg-emerald-400' :
            variant === 'warning' ? 'bg-amber-400' :
            variant === 'danger' ? 'bg-red-400' :
            variant === 'primary' ? 'bg-primary-400' :
            'bg-muted'
          }`} />
        )}
        {children}
      </motion.span>
    );
  }
);

Badge.displayName = 'Badge';
