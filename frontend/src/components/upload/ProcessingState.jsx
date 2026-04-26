import React, { useState, useEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { FileSearch, Brain, Table2, CheckCircle2 } from 'lucide-react';

const steps = [
  { icon: FileSearch, label: 'Skaitome PDF...', duration: 2000 },
  { icon: Brain, label: 'AI analizuoja...', duration: 3000 },
  { icon: Table2, label: 'Struktūrizuojame duomenis...', duration: 2000 },
  { icon: CheckCircle2, label: 'Paruošta!', duration: 1000 },
];

export default function ProcessingState({ onComplete }) {
  const [currentStep, setCurrentStep] = useState(0);

  useEffect(() => {
    if (currentStep < steps.length - 1) {
      const timer = setTimeout(() => {
        setCurrentStep(prev => prev + 1);
      }, steps[currentStep].duration);
      return () => clearTimeout(timer);
    } else {
      const timer = setTimeout(() => {
        onComplete?.();
      }, 1000);
      return () => clearTimeout(timer);
    }
  }, [currentStep, onComplete]);

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
                <Icon className={`w-10 h-10 ${i === steps.length - 1 ? 'text-primary' : 'text-primary animate-pulse'}`} />
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
              {step.label}
            </span>
          </motion.div>
        ))}
      </div>
    </div>
  );
}