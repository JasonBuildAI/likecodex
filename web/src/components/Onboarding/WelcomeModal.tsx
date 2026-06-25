'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { modalBackdrop, modalContent, staggerContainer, staggerItem } from '@/lib/animations';

// ─────────────────────────────────────────────
// Welcome Modal
// ─────────────────────────────────────────────
interface WelcomeModalProps {
  isOpen: boolean;
  onClose: () => void;
  onStartTour: () => void;
}

const FEATURES = [
  {
    icon: '🤖',
    title: 'Agent 模式',
    description: 'AI 自动执行编码任务，从分析到实现一步到位',
    color: 'from-purple-500/20 to-blue-500/20',
    border: 'border-purple-500/30',
  },
  {
    icon: '💬',
    title: 'Ask 模式',
    description: '只读问答模式，快速获取代码解释和建议',
    color: 'from-emerald-500/20 to-teal-500/20',
    border: 'border-emerald-500/30',
  },
  {
    icon: '✋',
    title: 'Manual 模式',
    description: '逐步确认，完全掌控 AI 的每一步操作',
    color: 'from-amber-500/20 to-orange-500/20',
    border: 'border-amber-500/30',
  },
  {
    icon: '⚡',
    title: '流式响应',
    description: '实时查看 AI 思考过程和工具调用',
    color: 'from-pink-500/20 to-rose-500/20',
    border: 'border-pink-500/30',
  },
];

export const WelcomeModal: React.FC<WelcomeModalProps> = ({ isOpen, onClose, onStartTour }) => {
  const [step, setStep] = useState(0);

  const handleDismiss = useCallback(() => {
    localStorage.setItem('likecodex_onboarded', 'true');
    onClose();
  }, [onClose]);

  const handleStartTour = useCallback(() => {
    localStorage.setItem('likecodex_onboarded', 'true');
    onStartTour();
  }, [onStartTour]);

  return (
    <AnimatePresence>
      {isOpen && (
        <motion.div
          variants={modalBackdrop}
          initial="hidden"
          animate="visible"
          exit="hidden"
          className="fixed inset-0 z-[200] flex items-center justify-center bg-black/70 backdrop-blur-md"
        >
          <motion.div
            variants={modalContent}
            className="w-full max-w-lg rounded-2xl bg-[#1a1a2e] border border-white/10 shadow-2xl overflow-hidden"
          >
            {/* Header with gradient */}
            <div className="relative px-8 pt-8 pb-6 text-center overflow-hidden">
              <div className="absolute inset-0 bg-gradient-to-br from-purple-600/10 via-transparent to-blue-600/10" />
              <motion.div
                initial={{ scale: 0, rotate: -180 }}
                animate={{ scale: 1, rotate: 0 }}
                transition={{ type: 'spring', stiffness: 260, damping: 20, delay: 0.1 }}
                className="relative inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-gradient-to-br from-purple-500/30 to-blue-500/30 border border-white/10 mb-4"
              >
                <span className="text-3xl">🚀</span>
              </motion.div>
              <h1 className="relative text-2xl font-bold text-white mb-2">
                欢迎使用 LikeCodex
              </h1>
              <p className="relative text-sm text-gray-400">
                AI 驱动的编码助手，让开发更高效
              </p>
            </div>

            {/* Features grid */}
            <motion.div
              variants={staggerContainer}
              initial="hidden"
              animate="visible"
              className="px-8 pb-6 grid grid-cols-2 gap-3"
            >
              {FEATURES.map((feature) => (
                <motion.div
                  key={feature.title}
                  variants={staggerItem}
                  className={`p-4 rounded-xl bg-gradient-to-br ${feature.color} border ${feature.border}`}
                >
                  <div className="text-2xl mb-2">{feature.icon}</div>
                  <h3 className="text-sm font-semibold text-white mb-1">{feature.title}</h3>
                  <p className="text-xs text-gray-400 leading-relaxed">{feature.description}</p>
                </motion.div>
              ))}
            </motion.div>

            {/* Actions */}
            <div className="px-8 pb-8 flex items-center gap-3">
              <button
                onClick={handleDismiss}
                className="flex-1 py-2.5 rounded-lg text-sm font-medium text-gray-400 hover:text-white border border-white/10 hover:border-white/20 transition-all"
              >
                稍后探索
              </button>
              <button
                onClick={handleStartTour}
                className="flex-1 py-2.5 rounded-lg text-sm font-semibold text-white bg-gradient-to-r from-purple-600 to-blue-600 hover:from-purple-500 hover:to-blue-500 transition-all shadow-lg shadow-purple-500/20"
              >
                开始引导 →
              </button>
            </div>
          </motion.div>
        </motion.div>
      )}
    </AnimatePresence>
  );
};

// ─────────────────────────────────────────────
// Onboarding Tour
// ─────────────────────────────────────────────
interface TourStep {
  target: string;
  title: string;
  description: string;
  position: 'top' | 'bottom' | 'left' | 'right';
}

const TOUR_STEPS: TourStep[] = [
  {
    target: 'mode-selector',
    title: '模式选择器',
    description: '在此切换 Agent/Ask/Manual 三种模式。默认为 Agent 模式，AI 会自动执行任务。',
    position: 'bottom',
  },
  {
    target: 'input-area',
    title: '输入区域',
    description: '输入你的编码需求，支持 @提及文件、符号，按 Ctrl+Enter 发送。',
    position: 'top',
  },
  {
    target: 'chat-messages',
    title: '对话区域',
    description: 'AI 的回复和工具调用会在这里实时展示，支持流式输出。',
    position: 'left',
  },
  {
    target: 'agent-activity',
    title: 'Agent 活动面板',
    description: '查看 AI 正在执行的操作：文件读写、命令执行、搜索等。',
    position: 'left',
  },
  {
    target: 'sidebar',
    title: '侧边栏',
    description: '文件浏览器、搜索、Git 状态等。按 Ctrl+B 切换显示。',
    position: 'right',
  },
];

interface OnboardingTourProps {
  isActive: boolean;
  onComplete: () => void;
  onSkip: () => void;
}

export const OnboardingTour: React.FC<OnboardingTourProps> = ({ isActive, onComplete, onSkip }) => {
  const [currentStep, setCurrentStep] = useState(0);
  const step = TOUR_STEPS[currentStep];

  const handleNext = useCallback(() => {
    if (currentStep < TOUR_STEPS.length - 1) {
      setCurrentStep(prev => prev + 1);
    } else {
      localStorage.setItem('likecodex_tour_completed', 'true');
      onComplete();
    }
  }, [currentStep, onComplete]);

  const handlePrev = useCallback(() => {
    setCurrentStep(prev => Math.max(0, prev - 1));
  }, []);

  if (!isActive || !step) return null;

  return (
    <AnimatePresence>
      <motion.div
        initial={{ opacity: 0 }}
        animate={{ opacity: 1 }}
        exit={{ opacity: 0 }}
        className="fixed inset-0 z-[150] pointer-events-none"
      >
        {/* Spotlight overlay */}
        <div className="absolute inset-0 bg-black/50" />

        {/* Tooltip */}
        <motion.div
          key={currentStep}
          initial={{ opacity: 0, y: 10, scale: 0.95 }}
          animate={{ opacity: 1, y: 0, scale: 1 }}
          exit={{ opacity: 0, y: -10, scale: 0.95 }}
          transition={{ duration: 0.2 }}
          className="absolute bottom-8 left-1/2 -translate-x-1/2 pointer-events-auto"
          style={{ width: 'min(90vw, 440px)' }}
        >
          <div className="rounded-xl bg-[#1e1e2e] border border-white/10 shadow-2xl overflow-hidden">
            {/* Progress bar */}
            <div className="h-1 bg-white/5">
              <motion.div
                className="h-full bg-gradient-to-r from-purple-500 to-blue-500"
                initial={{ width: 0 }}
                animate={{ width: `${((currentStep + 1) / TOUR_STEPS.length) * 100}%` }}
                transition={{ duration: 0.3 }}
              />
            </div>

            {/* Content */}
            <div className="p-5">
              <div className="flex items-center justify-between mb-3">
                <span className="text-xs text-purple-400 font-medium">
                  Step {currentStep + 1} / {TOUR_STEPS.length}
                </span>
                <button
                  onClick={onSkip}
                  className="text-xs text-gray-500 hover:text-white transition-colors"
                >
                  跳过 →
                </button>
              </div>

              <h3 className="text-lg font-semibold text-white mb-2">{step.title}</h3>
              <p className="text-sm text-gray-400 leading-relaxed mb-4">{step.description}</p>

              {/* Controls */}
              <div className="flex items-center justify-between">
                <button
                  onClick={handlePrev}
                  disabled={currentStep === 0}
                  className="px-3 py-1.5 rounded-md text-xs font-medium text-gray-400 hover:text-white disabled:opacity-30 disabled:cursor-not-allowed transition-all"
                >
                  ← 上一步
                </button>

                {/* Dots */}
                <div className="flex items-center gap-1.5">
                  {TOUR_STEPS.map((_, i) => (
                    <div
                      key={i}
                      className={`h-1.5 rounded-full transition-all ${
                        i === currentStep ? 'w-6 bg-purple-400' : 'w-1.5 bg-white/20'
                      }`}
                    />
                  ))}
                </div>

                <button
                  onClick={handleNext}
                  className="px-4 py-1.5 rounded-md text-xs font-semibold text-white bg-gradient-to-r from-purple-600 to-blue-600 hover:from-purple-500 hover:to-blue-500 transition-all"
                >
                  {currentStep === TOUR_STEPS.length - 1 ? '完成 ✓' : '下一步 →'}
                </button>
              </div>
            </div>
          </div>
        </motion.div>
      </motion.div>
    </AnimatePresence>
  );
};

// ─────────────────────────────────────────────
// Hook: useOnboarding
// ─────────────────────────────────────────────
export function useOnboarding() {
  const [showWelcome, setShowWelcome] = useState(false);
  const [showTour, setShowTour] = useState(false);

  useEffect(() => {
    const onboarded = localStorage.getItem('likecodex_onboarded');
    if (!onboarded) {
      setShowWelcome(true);
    }
  }, []);

  const startTour = useCallback(() => {
    setShowWelcome(false);
    setShowTour(true);
  }, []);

  const closeWelcome = useCallback(() => setShowWelcome(false), []);
  const completeTour = useCallback(() => setShowTour(false), []);
  const skipTour = useCallback(() => setShowTour(false), []);

  return {
    showWelcome,
    showTour,
    startTour,
    closeWelcome,
    completeTour,
    skipTour,
  };
}
