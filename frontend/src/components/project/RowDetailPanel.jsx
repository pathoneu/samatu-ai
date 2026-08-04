import React from 'react';
import { X, AlertTriangle, CheckCircle2, HelpCircle } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { motion, AnimatePresence } from 'framer-motion';
import { CONF_ZALIA, CONF_GELTONA, CONF_RAUDONA, CONFIDENCE_LABELS, normalizeConfidence } from '@/lib/confidence';

// Keyed by the canonical LT tiers — normalizeConfidence also folds the legacy
// EN vocabulary (high/medium/low) from old blobs into these.
const confidenceConfig = {
  [CONF_ZALIA]: { label: CONFIDENCE_LABELS[CONF_ZALIA], icon: CheckCircle2, color: 'text-primary bg-primary/10 border-primary/20' },
  [CONF_GELTONA]: { label: CONFIDENCE_LABELS[CONF_GELTONA], icon: HelpCircle, color: 'text-chart-3 bg-chart-3/10 border-chart-3/20' },
  [CONF_RAUDONA]: { label: CONFIDENCE_LABELS[CONF_RAUDONA], icon: AlertTriangle, color: 'text-destructive bg-destructive/10 border-destructive/20' },
};

export default function RowDetailPanel({ row, onClose }) {
  if (!row) return null;

  const conf = confidenceConfig[normalizeConfidence(row.confidence)];
  const ConfIcon = conf.icon;

  return (
    <AnimatePresence>
      <motion.div
        initial={{ x: 400, opacity: 0 }}
        animate={{ x: 0, opacity: 1 }}
        exit={{ x: 400, opacity: 0 }}
        transition={{ type: 'spring', damping: 25, stiffness: 300 }}
        className="fixed right-0 top-0 h-screen w-96 bg-card border-l border-border z-50 overflow-y-auto"
      >
        <div className="p-6">
          <div className="flex items-center justify-between mb-6">
            <h3 className="text-sm font-semibold text-muted-foreground uppercase tracking-wide">Eilutės detalės</h3>
            <button onClick={onClose} className="p-1.5 hover:bg-secondary rounded-lg transition-colors">
              <X className="w-4 h-4 text-muted-foreground" />
            </button>
          </div>

          <div className="space-y-5">
            <div>
              <p className="text-xs text-muted-foreground mb-1">Numeris</p>
              <p className="font-mono text-sm text-foreground">{row.nr}</p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground mb-1">Aprašymas</p>
              <p className="text-sm text-foreground leading-relaxed">{row.aprasymas}</p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground mb-1">Skyrius</p>
              <p className="text-sm text-foreground">{row.skyrius}</p>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <p className="text-xs text-muted-foreground mb-1">Matavimo vnt.</p>
                <p className="font-mono text-sm text-foreground">{row.mato_vnt || '—'}</p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground mb-1">Kiekis</p>
                <p className="font-mono text-sm text-foreground">{row.kiekis}</p>
              </div>
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div>
                <p className="text-xs text-muted-foreground mb-1">Kaina</p>
                <p className="font-mono text-sm text-foreground">
                  {row.kaina ? `${row.kaina.toFixed(2)} €` : '—'}
                </p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground mb-1">Suma</p>
                <p className="font-mono text-sm font-semibold text-primary">
                  {row.suma ? `${row.suma.toLocaleString('lt-LT', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} €` : '—'}
                </p>
              </div>
            </div>
            <div>
              <p className="text-xs text-muted-foreground mb-1.5">AI tikslumas</p>
              <Badge variant="outline" className={`${conf.color} border`}>
                <ConfIcon className="w-3 h-3 mr-1" />
                {conf.label}
              </Badge>
              {row._confidence_reason && (
                <p className="text-xs text-muted-foreground mt-1.5 leading-relaxed">
                  {row._confidence_reason}
                </p>
              )}
            </div>
            {row.warning && (
              <div className="p-3 bg-chart-3/5 border border-chart-3/20 rounded-lg">
                <div className="flex items-center gap-2">
                  <AlertTriangle className="w-4 h-4 text-chart-3" />
                  <p className="text-sm text-chart-3">{row.warning}</p>
                </div>
              </div>
            )}
          </div>
        </div>
      </motion.div>
    </AnimatePresence>
  );
}