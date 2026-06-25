'use client';

import React from 'react';
import { motion, HTMLMotionProps } from 'framer-motion';

interface InputProps extends Omit<HTMLMotionProps<'input'>, 'size'> {
  size?: 'sm' | 'md' | 'lg';
  leftIcon?: React.ReactNode;
  rightIcon?: React.ReactNode;
  error?: string;
}

const sizeStyles = {
  sm: 'px-2 py-1 text-xs rounded-md',
  md: 'px-3 py-2 text-sm rounded-lg',
  lg: 'px-4 py-3 text-base rounded-xl',
};

export const Input = React.forwardRef<HTMLInputElement, InputProps>(
  ({ 
    size = 'md',
    leftIcon,
    rightIcon,
    error,
    className = '',
    ...props 
  }, ref) => {
    const baseStyles = 'w-full bg-surface border transition-all duration-fast focus:outline-none disabled:opacity-50 disabled:cursor-not-allowed';
    const normalBorder = 'border-border focus:border-primary-500 focus:ring-2 focus:ring-primary-500/20';
    const errorBorder = 'border-red-500 focus:border-red-500 focus:ring-2 focus:ring-red-500/20';
    const combinedStyles = `${baseStyles} ${error ? errorBorder : normalBorder} ${sizeStyles[size]} ${className}`;

    return (
      <div className="relative">
        {leftIcon && (
          <div className="absolute left-3 top-1/2 -translate-y-1/2 text-muted pointer-events-none">
            {leftIcon}
          </div>
        )}
        <motion.input
          ref={ref}
          className={`${leftIcon ? 'pl-10' : ''} ${rightIcon ? 'pr-10' : ''} ${combinedStyles}`}
          {...props}
        />
        {rightIcon && (
          <div className="absolute right-3 top-1/2 -translate-y-1/2 text-muted pointer-events-none">
            {rightIcon}
          </div>
        )}
        {error && (
          <p className="mt-1 text-xs text-red-400">{error}</p>
        )}
      </div>
    );
  }
);

Input.displayName = 'Input';
