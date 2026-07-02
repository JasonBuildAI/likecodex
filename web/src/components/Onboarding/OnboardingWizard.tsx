'use client';

import { useState, useCallback, useEffect } from 'react';

// ── Types ──────────────────────────────────────────────────────────────

export interface WizardStep {
  id: string;
  title: string;
  description: string;
  /** Optional target element CSS selector to highlight */
  highlight?: string;
  /** Optional illustration / icon component */
  illustration?: React.ReactNode;
  /** Optional action that runs when the step becomes active */
  onEnter?: () => void;
}

interface OnboardingWizardProps {
  steps: WizardStep[];
  isOpen: boolean;
  onComplete: () => void;
  onSkip: () => void;
  /** Storage key for persisting completion state */
  storageKey?: string;
}

// ── Main Component ─────────────────────────────────────────────────────

export function OnboardingWizard({
  steps,
  isOpen,
  onComplete,
  onSkip,
  storageKey = 'likecodex_onboarding_complete',
}: OnboardingWizardProps) {
  const [currentStep, setCurrentStep] = useState(0);
  const [dismissed, setDismissed] = useState(false);

  // Check if already completed
  useEffect(() => {
    if (typeof window === 'undefined') return;
    try {
      const val = localStorage.getItem(storageKey);
      if (val === 'true') setDismissed(true);
    } catch {
      // localStorage not available
    }
  }, [storageKey]);

  // Run onEnter when step changes
  useEffect(() => {
    if (isOpen && steps[currentStep]?.onEnter) {
      steps[currentStep].onEnter!();
    }
  }, [isOpen, currentStep, steps]);

  // Reset on open
  useEffect(() => {
    if (isOpen) setCurrentStep(0);
  }, [isOpen]);

  // Keyboard navigation
  useEffect(() => {
    if (!isOpen || dismissed) return;
    const handler = (e: KeyboardEvent) => {
      if (e.key === 'ArrowRight' || e.key === 'Enter') {
        e.preventDefault();
        handleNext();
      } else if (e.key === 'ArrowLeft') {
        e.preventDefault();
        setCurrentStep((s) => Math.max(0, s - 1));
      } else if (e.key === 'Escape') {
        e.preventDefault();
        handleSkip();
      }
    };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [isOpen, dismissed, currentStep, steps.length]);

  const handleNext = useCallback(() => {
    if (currentStep >= steps.length - 1) {
      handleComplete();
    } else {
      setCurrentStep((s) => s + 1);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentStep, steps.length]);

  const handleSkip = useCallback(() => {
    setDismissed(true);
    onSkip();
  }, [onSkip]);

  const handleComplete = useCallback(() => {
    try {
      localStorage.setItem(storageKey, 'true');
    } catch {
      // Ignore storage errors
    }
    setDismissed(true);
    onComplete();
  }, [onComplete, storageKey]);

  if (dismissed || !isOpen || steps.length === 0) return null;

  const step = steps[currentStep];
  const isLast = currentStep === steps.length - 1;
  const progress = ((currentStep + 1) / steps.length) * 100;

  return (
    <div className="fixed inset-0 z-[200] flex items-center justify-center bg-black/60 backdrop-blur-sm">
      <div
        className="w-full max-w-md rounded-2xl border border-border/30 bg-surface shadow-2xl overflow-hidden"
        onClick={(e) => e.stopPropagation()}
      >
        {/* Progress bar */}
        <div className="h-1 bg-background/50">
          <div
            className="h-full bg-gradient-to-r from-blue-500 to-purple-500 transition-all duration-300 ease-out"
            style={{ width: `${progress}%` }}
          />
        </div>

        {/* Step counter */}
        <div className="px-6 pt-4 flex items-center justify-between">
          <span className="text-[9px] text-muted/50 font-mono">
            Step {currentStep + 1} of {steps.length}
          </span>
          <button
            onClick={handleSkip}
            className="text-[9px] text-muted/40 hover:text-muted/70 transition-colors"
          >
            Skip tour
          </button>
        </div>

        {/* Content */}
        <div className="px-6 py-6">
          {/* Illustration */}
          {step.illustration && (
            <div className="flex justify-center mb-6">
              <div className="w-20 h-20 rounded-2xl bg-gradient-to-br from-primary/20 to-purple-500/20 flex items-center justify-center text-3xl">
                {step.illustration}
              </div>
            </div>
          )}

          {/* Title */}
          <h3 className="text-lg font-semibold text-foreground text-center mb-2">
            {step.title}
          </h3>

          {/* Description */}
          <p className="text-xs text-muted/70 text-center leading-relaxed">
            {step.description}
          </p>

          {/* Highlight hint */}
          {step.highlight && (
            <div className="mt-3 flex items-center justify-center gap-1 text-[9px] text-primary/60">
              <svg className="h-3 w-3" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z" />
              </svg>
              <span>Look for the &quot;{step.highlight}&quot; section</span>
            </div>
          )}
        </div>

        {/* Step indicators and navigation */}
        <div className="px-6 pb-4">
          {/* Dots */}
          <div className="flex justify-center gap-1.5 mb-4">
            {steps.map((_, i) => (
              <button
                key={i}
                onClick={() => setCurrentStep(i)}
                className={`h-1.5 rounded-full transition-all duration-300 ${
                  i === currentStep
                    ? 'w-6 bg-primary'
                    : i < currentStep
                      ? 'w-1.5 bg-primary/50'
                      : 'w-1.5 bg-muted/20 hover:bg-muted/40'
                }`}
              />
            ))}
          </div>

          {/* Navigation buttons */}
          <div className="flex items-center justify-between gap-2">
            <button
              onClick={currentStep > 0 ? () => setCurrentStep((s) => s - 1) : undefined}
              className={`px-3 py-1.5 text-[10px] rounded-lg border transition-colors ${
                currentStep > 0
                  ? 'border-border/40 text-muted/70 hover:text-foreground hover:bg-background'
                  : 'border-transparent text-muted/30 cursor-default'
              }`}
            >
              ← Back
            </button>

            <button
              onClick={handleSkip}
              className="px-3 py-1.5 text-[10px] text-muted/50 hover:text-muted/70 transition-colors"
            >
              Skip
            </button>

            <button
              onClick={handleNext}
              className="px-5 py-1.5 text-[10px] font-medium rounded-lg bg-gradient-to-r from-blue-500 to-purple-600 text-white shadow-lg shadow-blue-500/20 hover:shadow-blue-500/30 transition-shadow"
            >
              {isLast ? 'Get Started' : 'Next →'}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

export default OnboardingWizard;
