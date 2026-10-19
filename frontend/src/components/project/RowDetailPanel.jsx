/**
 * RowDetailPanel — „Kaip suskaičiuota": one sąmata line, opened out.
 *
 * Written in Sprint G, mounted only on the KŽ path, and unreachable from the
 * interior project until 2026-09-02 (§1.6 of the calc-transparency research —
 * `ProjectDetail.jsx` returns before its mount). It now carries the contribution
 * ledger, so it is the answer to "which rooms produced this number, which were
 * left out, and where do I change the input that is wrong".
 *
 * It renders the server's arithmetic and never repeats it — see LedgerTree.
 */

import { useEffect } from 'react';
import { useTranslation } from '@/i18n/react';
import { X, MapPin, Info } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  CONFIDENCE_DOT_CLASS, confidenceLabel, normalizeConfidence,
} from '@/lib/confidence';
import { ltEur, ltQuantity } from '@/lib/ledger';
import LedgerTree from './LedgerTree';
import SudetisBlock from './SudetisBlock';
import { priceSplitText } from '@/lib/priceSplit';
import { cleanUserText } from '@/lib/userText';

export default function RowDetailPanel({
  row,
  rooms = [],
  onClose,
  onFocusRoom = null,
  onOpenAssumptions = null,
  projectId = null,
}) {
  // Esc closes the slide-over — it covers a third of the workspace and the ✕ is
  // at the far right of a wide screen.
  useEffect(() => {
    if (!row || !onClose) return undefined;
    const onKey = (e) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [row, onClose]);

  const { t } = useTranslation();
  if (!row) return null;

  const tier = normalizeConfidence(row.confidence);
  const unit = row.mato_vnt || row.vnt;
  const suma = (Number(row.kiekis) || 0) * (Number(row.kaina) || 0);
  const rowRoom = row._room_nr != null
    ? (rooms || []).find(r => String(r?.nr) === String(row._room_nr))
    : null;

  return (
    <AnimatePresence>
      <motion.aside
        key="row-detail"
        role="dialog"
        aria-label={t('project.ledger.title')}
        initial={{ x: 420, opacity: 0 }}
        animate={{ x: 0, opacity: 1 }}
        exit={{ x: 420, opacity: 0 }}
        transition={{ type: 'spring', damping: 26, stiffness: 300 }}
        className="fixed right-0 top-0 h-screen w-full sm:w-[26rem] z-50 overflow-y-auto"
        style={{
          background: 'hsl(var(--card))',
          borderLeft: '1px solid hsl(var(--border))',
          boxShadow: '-8px 0 24px -18px hsl(var(--foreground) / 0.4)',
        }}
      >
        <div
          className="sticky top-0 z-10 flex items-start justify-between gap-2 px-4 py-3"
          style={{
            background: 'hsl(var(--card))',
            borderBottom: '1px solid hsl(var(--border))',
          }}
        >
          <div className="min-w-0">
            <p className="text-meta text-muted-foreground font-semibold">
              {t('project.ledger.title')}
            </p>
            <h3 className="text-sm font-semibold text-foreground leading-snug">
              {row.aprasymas || row.pavadinimas}
            </h3>
            <p className="text-meta text-muted-foreground truncate">
              {(row.nr || row.eil_nr) != null && (
                <span className="mono tabular">{row.nr || row.eil_nr} · </span>
              )}
              {row.skyrius || row.kategorija || ''}
            </p>
          </div>
          <button
            onClick={onClose}
            title={t('project.ledger.close')}
            aria-label={t('project.ledger.close')}
            className="shrink-0 p-1.5 rounded transition-colors hover:bg-muted/60 text-muted-foreground"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="p-4 space-y-4">
          {/* ── The number itself, with the tier and the reason ──────────── */}
          <div>
            <div className="flex items-baseline gap-2">
              <span className="mono tabular text-xl font-semibold text-foreground">
                {ltQuantity(row.kiekis, unit)}
              </span>
              <span
                className={`dot ${CONFIDENCE_DOT_CLASS[tier]}`}
                title={confidenceLabel(tier)}
              />
              <span className="text-meta text-muted-foreground">{confidenceLabel(tier)}</span>
            </div>
            {row._confidence_reason && (
              <p className="mt-1 text-xs leading-relaxed text-muted-foreground">
                {cleanUserText(row._confidence_reason)}
              </p>
            )}
          </div>

          {/* ── Price / sum, as the sąmata bills it ───────────────────────── */}
          <div className="grid grid-cols-2 gap-3">
            <div>
              <p className="text-meta text-muted-foreground">
                {t('project.ledger.unitPrice')}
              </p>
              <p className="mono tabular text-sm text-foreground">
                {row.kaina ? ltEur(row.kaina, 2) : '—'}
              </p>
              {priceSplitText(row) && (
                <p className="text-meta text-muted-foreground tabular">{priceSplitText(row)}</p>
              )}
            </div>
            <div>
              <p className="text-meta text-muted-foreground">
                {t('project.ledger.total')}
              </p>
              <p className="mono tabular text-sm font-semibold" style={{ color: 'hsl(var(--primary))' }}>
                {suma > 0 ? ltEur(suma, 2) : '—'}
              </p>
            </div>
          </div>

          {/* ── The assumption the line was built on, finally rendered ────── */}
          {row._assumption && (
            <div
              className="flex items-start gap-2 rounded-sm px-3 py-2 text-meta leading-relaxed"
              style={{
                background: 'hsl(var(--conf-med) / 0.08)',
                border: '1px solid hsl(var(--conf-med) / 0.3)',
                color: 'hsl(var(--foreground) / 0.85)',
              }}
            >
              <Info className="w-3.5 h-3.5 shrink-0 mt-0.5" style={{ color: 'hsl(var(--conf-med))' }} />
              <span>
                <strong className="font-medium">{t('project.ledger.assumption')}:</strong>{' '}
                {row._assumption}
              </span>
            </div>
          )}

          <SudetisBlock projectId={projectId} row={row} />

          <LedgerTree
            row={row}
            rooms={rooms}
            onFocusRoom={onFocusRoom}
            onOpenAssumptions={onOpenAssumptions}
          />

          {/* A line tied to ONE room (angokraščiai, plytelės…) keeps its own
              jump — the ledger families point at many rooms, these at one. */}
          {onFocusRoom && rowRoom?.puslapio_nr && (
            <button
              type="button"
              onClick={() => onFocusRoom(rowRoom.puslapio_nr, rowRoom)}
              className="inline-flex items-center gap-1.5 text-xs transition-colors hover:underline"
              style={{ color: 'hsl(var(--primary))' }}
            >
              <MapPin className="w-3 h-3" />
              {t('project.ledger.showDrawing')}
            </button>
          )}

          {row.warning && (
            <div
              className="rounded-sm px-3 py-2 text-xs"
              style={{
                background: 'hsl(var(--conf-low) / 0.08)',
                border: '1px solid hsl(var(--conf-low) / 0.3)',
                color: 'hsl(var(--conf-low))',
              }}
            >
              {row.warning}
            </div>
          )}
        </div>
      </motion.aside>
    </AnimatePresence>
  );
}
