import React, { useState, useEffect } from 'react';
import { useTranslation } from '@/i18n/react';
import { motion, AnimatePresence } from 'framer-motion';
import { FileSearch, Brain, Search, CheckCircle2 } from 'lucide-react';

// User-facing labels — no technical jargon (no "Pass", "Vision", "AI" tier).
// `labelKey` resolves against i18n at render.
const steps = [
  { icon: FileSearch,   labelKey: 'upload.processing.reading',     minSec: 0 },
  { icon: Brain,        labelKey: 'upload.processing.recognizing', minSec: 15 },
  { icon: Search,       labelKey: 'upload.processing.refining',    minSec: 90 },
  { icon: CheckCircle2, labelKey: 'upload.processing.summing',     minSec: 300 },
];


export default function ProcessingState() {
  const { t } = useTranslation();
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    const start = Date.now();
    const t = setInterval(() => {
      setElapsed(Math.floor((Date.now() - start) / 1000));
    }, 1000);
    return () => clearInterval(t);
  }, []);

  // Find latest step the elapsed time has passed
  let currentStep = 0;
  for (let i = steps.length - 1; i >= 0; i--) {
    if (elapsed >= steps[i].minSec) {
      currentStep = i;
      break;
    }
  }

  return (
    <div className="flex flex-col items-center justify-center py-16">
      <div className="w-20 h-20 rounded-2xl bg-primary/10 border border-primary/20 flex items-center justify-center mb-8 relative">
        <AnimatePresence mode="wait">
          {steps.map((step, i) => {
            const Icon = step.icon;
            return i === currentStep ? (
              <motion.div
                key={i}
                initial={{ opacity: 0, scale: 0.5 }}
                animate={{ opacity: 1, scale: 1 }}
                exit={{ opacity: 0, scale: 0.5 }}
                transition={{ duration: 0.3 }}
              >
                <Icon className="w-10 h-10 text-primary animate-pulse" />
              </motion.div>
            ) : null;
          })}
        </AnimatePresence>
      </div>

      <div className="space-y-3 w-full max-w-xs">
        {steps.map((step, i) => (
          <motion.div
            key={i}
            initial={{ opacity: 0, x: -20 }}
            animate={{ opacity: i <= currentStep ? 1 : 0.3, x: 0 }}
            transition={{ delay: i * 0.1 }}
            className="flex items-center gap-3"
          >
            <div className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-mono ${
              i < currentStep ? 'bg-primary text-primary-foreground' :
              i === currentStep ? 'bg-primary/20 text-primary border border-primary' :
              'bg-secondary text-muted-foreground'
            }`}>
              {i < currentStep ? '✓' : i + 1}
            </div>
            <span className={`text-sm ${
              i === currentStep ? 'text-foreground font-medium' :
              i < currentStep ? 'text-primary' : 'text-muted-foreground'
            }`}>
              {t(step.labelKey)}
            </span>
          </motion.div>
        ))}
      </div>
    </div>
  );
}
