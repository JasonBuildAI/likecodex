/**
 * Animation utilities for LikeCodex UI
 * Provides pre-defined animation configurations for Framer Motion
 */

import { Variants } from 'framer-motion';

// ── Fade Animations ────────────────────────────────────────────────────
export const fadeIn: Variants = {
  hidden: { opacity: 0 },
  visible: { 
    opacity: 1,
    transition: { duration: 0.3, ease: 'easeInOut' }
  },
  exit: { 
    opacity: 0,
    transition: { duration: 0.2 }
  }
};

export const fadeInUp: Variants = {
  hidden: { opacity: 0, y: 20 },
  visible: { 
    opacity: 1, 
    y: 0,
    transition: { duration: 0.4, ease: 'easeOut' }
  },
  exit: { 
    opacity: 0, 
    y: -10,
    transition: { duration: 0.2 }
  }
};

export const fadeInDown: Variants = {
  hidden: { opacity: 0, y: -20 },
  visible: { 
    opacity: 1, 
    y: 0,
    transition: { duration: 0.4, ease: 'easeOut' }
  },
  exit: { 
    opacity: 0, 
    y: 10,
    transition: { duration: 0.2 }
  }
};

export const fadeInLeft: Variants = {
  hidden: { opacity: 0, x: -20 },
  visible: { 
    opacity: 1, 
    x: 0,
    transition: { duration: 0.4, ease: 'easeOut' }
  },
  exit: { 
    opacity: 0, 
    x: -10,
    transition: { duration: 0.2 }
  }
};

export const fadeInRight: Variants = {
  hidden: { opacity: 0, x: 20 },
  visible: { 
    opacity: 1, 
    x: 0,
    transition: { duration: 0.4, ease: 'easeOut' }
  },
  exit: { 
    opacity: 0, 
    x: 10,
    transition: { duration: 0.2 }
  }
};

// ── Scale Animations ───────────────────────────────────────────────────
export const scaleIn: Variants = {
  hidden: { opacity: 0, scale: 0.8 },
  visible: { 
    opacity: 1, 
    scale: 1,
    transition: { duration: 0.3, ease: 'easeOut' }
  },
  exit: { 
    opacity: 0, 
    scale: 0.9,
    transition: { duration: 0.2 }
  }
};

export const scaleInBounce: Variants = {
  hidden: { opacity: 0, scale: 0.3 },
  visible: { 
    opacity: 1, 
    scale: 1,
    transition: { 
      type: 'spring',
      stiffness: 300,
      damping: 20
    }
  },
  exit: { 
    opacity: 0, 
    scale: 0.5,
    transition: { duration: 0.2 }
  }
};

// ── Slide Animations ───────────────────────────────────────────────────
export const slideInFromBottom: Variants = {
  hidden: { opacity: 0, y: 50 },
  visible: { 
    opacity: 1, 
    y: 0,
    transition: { 
      type: 'spring',
      stiffness: 200,
      damping: 25
    }
  },
  exit: { 
    opacity: 0, 
    y: 50,
    transition: { duration: 0.3 }
  }
};

export const slideInFromTop: Variants = {
  hidden: { opacity: 0, y: -50 },
  visible: { 
    opacity: 1, 
    y: 0,
    transition: { 
      type: 'spring',
      stiffness: 200,
      damping: 25
    }
  },
  exit: { 
    opacity: 0, 
    y: -50,
    transition: { duration: 0.3 }
  }
};

// ── Special Effects ────────────────────────────────────────────────────
export const pulse: Variants = {
  idle: { scale: 1 },
  pulsing: { 
    scale: [1, 1.05, 1],
    transition: { 
      duration: 1.5,
      repeat: Infinity,
      ease: 'easeInOut'
    }
  }
};

export const shake: Variants = {
  idle: { x: 0 },
  shaking: { 
    x: [-5, 5, -5, 5, 0],
    transition: { 
      duration: 0.4,
      times: [0, 0.2, 0.4, 0.6, 1]
    }
  }
};

export const bounce: Variants = {
  idle: { y: 0 },
  bouncing: { 
    y: [0, -10, 0],
    transition: { 
      duration: 0.6,
      repeat: Infinity,
      ease: 'easeInOut'
    }
  }
};

export const rotate: Variants = {
  idle: { rotate: 0 },
  rotating: { 
    rotate: 360,
    transition: { 
      duration: 1,
      repeat: Infinity,
      ease: 'linear'
    }
  }
};

// ── Stagger Children ───────────────────────────────────────────────────
export const staggerContainer: Variants = {
  hidden: {},
  visible: {
    transition: {
      staggerChildren: 0.1,
      delayChildren: 0.1
    }
  }
};

export const staggerItem: Variants = {
  hidden: { opacity: 0, y: 20 },
  visible: { 
    opacity: 1, 
    y: 0,
    transition: { duration: 0.3 }
  }
};

// ── Typewriter Effect ──────────────────────────────────────────────────
export const typewriter: Variants = {
  hidden: { width: 0 },
  visible: (i: number) => ({
    width: 'auto',
    transition: {
      delay: i * 0.05,
      duration: 0.1,
      ease: 'easeInOut'
    }
  })
};

// ── Page Transitions ───────────────────────────────────────────────────
export const pageTransition: Variants = {
  initial: { 
    opacity: 0,
    scale: 0.98
  },
  animate: { 
    opacity: 1,
    scale: 1,
    transition: { 
      duration: 0.4,
      ease: 'easeOut'
    }
  },
  exit: { 
    opacity: 0,
    scale: 0.98,
    transition: { 
      duration: 0.3
    }
  }
};

// ── Modal/Dialog ───────────────────────────────────────────────────────
export const modalBackdrop: Variants = {
  hidden: { opacity: 0 },
  visible: { 
    opacity: 1,
    transition: { duration: 0.2 }
  },
  exit: { 
    opacity: 0,
    transition: { duration: 0.2 }
  }
};

export const modalContent: Variants = {
  hidden: { 
    opacity: 0,
    scale: 0.9,
    y: 20
  },
  visible: { 
    opacity: 1,
    scale: 1,
    y: 0,
    transition: { 
      type: 'spring',
      stiffness: 300,
      damping: 25
    }
  },
  exit: { 
    opacity: 0,
    scale: 0.9,
    y: -20,
    transition: { duration: 0.2 }
  }
};

// ── Tooltip ────────────────────────────────────────────────────────────
export const tooltip: Variants = {
  hidden: { 
    opacity: 0,
    scale: 0.8,
    y: 5
  },
  visible: { 
    opacity: 1,
    scale: 1,
    y: 0,
    transition: { 
      duration: 0.15,
      ease: 'easeOut'
    }
  },
  exit: { 
    opacity: 0,
    scale: 0.8,
    y: 5,
    transition: { duration: 0.1 }
  }
};

// ── Loading Spinner ────────────────────────────────────────────────────
export const spinner: Variants = {
  spin: {
    rotate: 360,
    transition: {
      duration: 1,
      repeat: Infinity,
      ease: 'linear'
    }
  }
};

// ── Progress Bar ───────────────────────────────────────────────────────
export const progressBar: Variants = {
  hidden: { width: 0 },
  visible: (progress: number) => ({
    width: `${progress}%`,
    transition: {
      duration: 0.5,
      ease: 'easeOut'
    }
  })
};

// ── Export all animations ──────────────────────────────────────────────
export const animations = {
  fadeIn,
  fadeInUp,
  fadeInDown,
  fadeInLeft,
  fadeInRight,
  scaleIn,
  scaleInBounce,
  slideInFromBottom,
  slideInFromTop,
  pulse,
  shake,
  bounce,
  rotate,
  staggerContainer,
  staggerItem,
  typewriter,
  pageTransition,
  modalBackdrop,
  modalContent,
  tooltip,
  spinner,
  progressBar,
};

export default animations;
