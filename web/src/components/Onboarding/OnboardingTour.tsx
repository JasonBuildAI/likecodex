'use client';

import { useState, useCallback, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { modalBackdrop, modalContent, fadeInUp, staggerContainer, staggerItem } from '@/lib/animations';

interface TourStep {
  title: string;
  description: string;
  icon: React.ReactNode;
  highlight?: string;
}

interface OnboardingTourProps {
  isOpen: boolean;
  onComplete: () => void;
  onSkip: () => void;
}

const STEPS: TourStep[] = [
  {
    title: '欢迎使用 LikeCodex',
    description: '你的 AI 编程助手。像 Cursor 一样，你可以在编辑器中直接与 AI 对话，让它帮你写代码、修 Bug、重构项目。',
    icon: (
      <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-purple-500/30 to-blue-500/30 flex items-center justify-center text-3xl">
        🚀
      </div>
    ),
  },
  {
    title: '三种 Agent 模式',
    description: 'Ask 模式只读问答，Agent 模式自动执行，Manual 模式需你确认。用 Tab 快速切换模式。',
    icon: (
      <div className="flex gap-2">
        <span className="px-3 py-1.5 rounded-full text-xs font-medium bg-emerald-500/20 text-emerald-300 border border-emerald-500/30">Ask</span>
        <span className="px-3 py-1.5 rounded-full text-xs font-medium bg-blue-500/20 text-blue-300 border border-blue-500/30">Agent</span>
        <span className="px-3 py-1.5 rounded-full text-xs font-medium bg-amber-500/20 text-amber-300 border border-amber-500/30">Manual</span>
      </div>
    ),
    highlight: 'mode-selector',
  },
  {
    title: '@ 提及系统',
    description: '在输入框输入 @ 可以快速引用文件、符号、Git 分支等。让 AI 精确知道你要操作的上下文。',
    icon: (
      <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-blue-500/20 to-purple-500/20 flex items-center justify-center text-3xl">
        @
      </div>
    ),
    highlight: 'input-area',
  },
  {
    title: '快捷键',
    description: 'Ctrl+K 打开命令面板，Ctrl+J 打开 Agent 面板，Ctrl+B 切换侧边栏。按 ? 查看全部快捷键。',
    icon: (
      <div className="flex flex-col gap-1.5">
        <kbd className="px-2 py-1 rounded bg-white/10 text-xs font-mono">Ctrl+K</kbd>
        <kbd className="px-2 py-1 rounded bg-white/10 text-xs font-mono">Ctrl+J</kbd>
        <kbd className="px-2 py-1 rounded bg-white/10 text-xs font-mono">Ctrl+B</kbd>
      </div>
    ),
  },
  {
    title: '开始你的旅程',
    description: '在输入框输入你的需求，选择 Agent 模式，按 Ctrl+Enter 发送。LikeCodex 会自动分析、编码、执行。',
    icon: (
      <div className="w-16 h-16 rounded-2xl bg-gradient-to-br from-emerald-500/30 to-purple-500/30 flex items-center justify-center text-3xl">
        ✨
      </div>
    ),
  },
];

export function OnboardingTour({ isOpen, onComplete, onSkip }: OnboardingTourProps) {
  const [step, setStep] = useState(0);
  const current = STEPS[step];
  const isLast = step === STEPS.length - 1;
  const progress = ((step + 1) / STEPS.length) * 100;

  const handleNext = useCallback(() => {
    if (isLast) {
      onComplete();
    } else {
      setStep(s => s + 1);
    }
  }, [isLast, onComplete]);

  const handlePrev = useCallback(() => {
    setStep(s => Math.max(0, s - 1));
  }, []);

  // Keyboard navigation
  useEffect(() => {
    if (!isOpen) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'ArrowRight' || e.key === 'Enter') { e.preventDefault(); handleNext(); }
      else if (e.key === 'ArrowLeft') { e.preventDefault(); handlePrev(); }
      else if (e.key === 'Escape') { e.preventDefault(); onSkip(); }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, [isOpen, handleNext, handlePrev, onSkip]);

  // Reset to first step when opened
  useEffect(() => {
    if (isOpen) setStep(0);
  }, [isOpen]);

  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          variants={modalBackdrop}
          initial="hidden"
          animate="visible"
          exit="hidden"
          className="fixed inset-0 z-[200] flex items-center justify-center bg-black/70 backdrop-blur-md"
          onClick={onSkip}
        >
          <motion.div
            variants={modalContent}
            className="w-full max-w-md rounded-2xl bg-[#1a1a2e] border border-white/10 shadow-2xl overflow-hidden"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Progress bar */}
            <div className="h-1 bg-white/5">
              <motion.div
                className="h-full bg-gradient-to-r from-purple-500 to-blue-500"
                animate={{ width: `${progress}%` }}
                transition={{ duration: 0.3, ease: 'easeOut' }}
              />
            </div>

            {/* Content */}
            <AnimatePresence mode="wait">
              <motion.div
                key={step}
                initial={{ opacity: 0, x: 20 }}
                animate={{ opacity: 1, x: 0 }}
                exit={{ opacity: 0, x: -20 }}
                transition={{ duration: 0.2 }}
                className="p-8"
              >
                {/* Icon */}
                <motion.div
                  variants={staggerContainer}
                  initial="hidden"
                  animate="visible"
                  className="flex justify-center mb-6"
                >
                  <motion.div variants={staggerItem}>
                    {current.icon}
                  </motion.div>
                </motion.div>

                {/* Title */}
                <h2 className="text-xl font-bold text-white text-center mb-3">
                  {current.title}
                </h2>

                {/* Description */}
                <p className="text-sm text-gray-400 text-center leading-relaxed mb-8">
                  {current.description}
                </p>
              </motion.div>
            </AnimatePresence>

            {/* Navigation */}
            <div className="flex items-center justify-between px-6 py-4 border-t border-white/[0.06]">
              {/* Step indicators */}
              <div className="flex items-center gap-1.5">
                {STEPS.map((_, i) => (
                  <button
                    key={i}
                    onClick={() => setStep(i)}
                    className={`h-1.5 rounded-full transition-all ${
                      i === step
                        ? 'w-6 bg-purple-400'
                        : i < step
                        ? 'w-1.5 bg-purple-400/50'
                        : 'w-1.5 bg-white/20'
                    }`}
                  />
                ))}
              </div>

              {/* Buttons */}
              <div className="flex items-center gap-2">
                {step > 0 && (
                  <button
                    onClick={handlePrev}
                    className="px-3 py-1.5 text-sm text-gray-400 hover:text-white transition-colors"
                  >
                    上一步
                  </button>
                )}
                <button
                  onClick={onSkip}
                  className="px-3 py-1.5 text-sm text-gray-500 hover:text-gray-300 transition-colors"
                >
                  跳过
                </button>
                <motion.button
                  whileHover={{ scale: 1.05 }}
                  whileTap={{ scale: 0.95 }}
                  onClick={handleNext}
                  className="px-5 py-1.5 text-sm font-medium rounded-lg bg-gradient-to-r from-purple-500 to-blue-500 text-white shadow-lg shadow-purple-500/20"
                >
                  {isLast ? '开始使用' : '下一步'}
                </motion.button>
              </div>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

export default OnboardingTour;
