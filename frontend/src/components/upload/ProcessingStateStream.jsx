/**
 * ProcessingStateStream — SM01 streaming UI replacement for ProcessingState.
 *
 * Consumes a sequence of SSE events (rendering_pdf, started, pass1_*, zoom_*,
 * post_processing, done, error) and renders a structured progress view that
 * grows the patalpos list as Pass-2 zoom finishes each room.
 */

import { useTranslation } from 'react-i18next';
import { motion, AnimatePresence } from 'framer-motion';
import {
  FileSearch, Brain, Search, CheckCircle2, AlertCircle, Home,
} from 'lucide-react';

// User-facing phase labels — no "Pass 1/2", no "Vision".
// `labelKey` resolves against i18n at render.
const PHASES = [
  { id: 'rendering', icon: FileSearch,   labelKey: 'upload.stream.reading' },
  { id: 'pass1',     icon: Brain,        labelKey: 'upload.stream.recognizing' },
  { id: 'zoom',      icon: Search,       labelKey: 'upload.stream.refiningRooms' },
  { id: 'post',      icon: CheckCircle2, labelKey: 'upload.stream.summing' },
];

const PHASE_INDEX = Object.fromEntries(PHASES.map((p, i) => [p.id, i]));
// 'finishing' is not a fifth step — it is the SAME last step, continuing after
// the socket was handed off. Mapping it onto 'post' keeps the checklist, the
// pulsing icon and the room list exactly where they were, so the user sees a
// run that never stopped rather than a screen that changed shape at 14 min.
PHASE_INDEX.finishing = PHASE_INDEX.post;

export default function ProcessingStateStream({
  phase, progress, elapsed, error, recovering = false, recoverySec = 0,
  // The preflight's own duration estimate („15–25 min"). Shown beside the
  // elapsed counter so the wait has a horizon — an honest range the probe
  // measured, never a fake countdown to a second we cannot know.
  estMinutes = '',
}) {
  const { t } = useTranslation();
  const currentStep = PHASE_INDEX[phase] ?? 0;
  const rooms = progress?.rooms || [];
  const zoomDone = progress?.zoomDone || 0;
  const zoomTotal = progress?.zoomTotal || 0;
  const pageCount = progress?.pageCount;
  // `validation_warning` — the backend's own read of the uploaded file (page
  // count over the pipeline's limit, etc.), pushed before Pass-1 so it lands
  // while the user is still watching. It was emitted and dropped on the floor
  // until 2026-08-23; it is a warning about the RUN, not an error, so it sits
  // above the checklist rather than replacing it.
  const validationWarning = progress?.validationWarning;

  const renderPhase = (i) => {
    const step = PHASES[i];
    const isDone = i < currentStep;
    const isActive = i === currentStep && !error;

    // The step's LABEL carries its own count where the stream gives us one:
    // „Skaitau brėžinį — 17 lapų", „Radau 11 patalpų", „Tikslinu matmenis —
    // 4 iš 11 kambarių". A progress bar with no words is what the design
    // forbids. The old second line repeated the same number under it, so a
    // detail is now rendered ONLY where the label says nothing extra.
    let label = t(step.labelKey);
    let detail = null;
    if (step.id === 'rendering' && pageCount && (isActive || isDone)) {
      label = t('upload.stream.readingPages', { count: pageCount });
    } else if (step.id === 'pass1' && rooms.length > 0) {
      label = t('upload.stream.foundRooms', { count: rooms.length });
    } else if (step.id === 'zoom' && zoomTotal > 0) {
      label = t('upload.stream.refiningProgress', { done: zoomDone, total: zoomTotal });
    }
    if (step.id === 'post' && recovering) {
      label = t('upload.stream.finishingOnServer');
      detail = t('upload.stream.finishingFor', { s: recoverySec });
    }

    return (
      <motion.div
        key={step.id}
        initial={{ opacity: 0, x: -20 }}
        animate={{ opacity: i <= currentStep ? 1 : 0.3, x: 0 }}
        transition={{ delay: i * 0.05 }}
        className="flex items-start gap-3"
      >
        <div className={`w-6 h-6 rounded-full flex items-center justify-center text-xs font-mono shrink-0 mt-0.5 ${
          isDone ? 'bg-primary text-primary-foreground' :
          isActive ? 'bg-primary/20 text-primary border border-primary' :
          'bg-secondary text-muted-foreground'
        }`}>
          {isDone ? '✓' : i + 1}
        </div>
        <div className="min-w-0 flex-1">
          <div className={`text-sm ${
            isActive ? 'text-foreground font-medium' :
            isDone ? 'text-primary' : 'text-muted-foreground'
          }`}>
            {label}
          </div>
          {detail && (
            <div className="text-[11px] text-muted-foreground mt-0.5">{detail}</div>
          )}
        </div>
      </motion.div>
    );
  };

  return (
    <div className="flex flex-col items-center py-10">
      <div className="w-20 h-20 rounded-2xl bg-primary/10 border border-primary/20 flex items-center justify-center mb-6 relative">
        <AnimatePresence mode="wait">
          {error ? (
            <motion.div key="err" initial={{ opacity: 0 }} animate={{ opacity: 1 }} exit={{ opacity: 0 }}>
              <AlertCircle className="w-10 h-10 text-destructive" />
            </motion.div>
          ) : (
            <motion.div
              key={`p${currentStep}`}
              initial={{ opacity: 0, scale: 0.5 }}
              animate={{ opacity: 1, scale: 1 }}
              exit={{ opacity: 0, scale: 0.5 }}
              transition={{ duration: 0.25 }}
            >
              {(() => {
                const Icon = PHASES[currentStep]?.icon || FileSearch;
                return <Icon className="w-10 h-10 text-primary animate-pulse" />;
              })()}
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {validationWarning && !error && (
        <div
          role="status"
          className="mb-5 max-w-md rounded-lg border border-[hsl(var(--conf-med))]/45 bg-card p-3 text-xs text-foreground"
        >
          <span className="mr-1.5 font-medium text-[hsl(var(--conf-med))]">
            {t('upload.stream.warningLabel')}
          </span>
          {validationWarning}
        </div>
      )}

      <div className="space-y-3 w-full max-w-xs mb-6">
        {PHASES.map((_, i) => renderPhase(i))}
      </div>

      {/* Per-room reveal — auto-count-style "watch it work" effect */}
      {rooms.length > 0 && (
        <div className="w-full max-w-md mt-2">
          <div className="text-xs font-medium text-muted-foreground mb-2 flex items-center justify-between">
            <span className="flex items-center gap-1.5">
              <Home className="w-3.5 h-3.5" />
              {t('upload.stream.detectedRooms')}
            </span>
            <span className="tabular-nums">{rooms.length}</span>
          </div>
          <div className="grid grid-cols-2 gap-1.5 max-h-56 overflow-y-auto pr-1">
            <AnimatePresence initial={false}>
              {rooms.map((r) => (
                <motion.div
                  key={r.nr || r.pavadinimas}
                  initial={{ opacity: 0, y: 6 }}
                  animate={{ opacity: 1, y: 0 }}
                  className={`px-2 py-1.5 rounded border text-[11px] ${
                    r.refined
                      ? 'border-primary/40 bg-primary/5 text-foreground'
                      : 'border-border bg-card text-muted-foreground'
                  }`}
                >
                  <div className="font-medium truncate">
                    {r.pavadinimas || r.nr}
                  </div>
                  <div className="tabular-nums">
                    {r.plotas_m2 != null
                      ? `${Number(r.plotas_m2).toFixed(1)} m²`
                      : '—'}
                    {r.refined && <span className="text-primary">{t('upload.stream.corrected')}</span>}
                  </div>
                </motion.div>
              ))}
            </AnimatePresence>
          </div>
        </div>
      )}

      {error && (
        <div className="mt-4 p-3 max-w-md bg-destructive/10 border border-destructive/30 rounded text-sm text-destructive">
          {error}
        </div>
      )}

      {/* Post-handoff reassurance. The connection is gone but the extraction
          is not, and a long silent stretch is exactly when a user starts
          re-uploading — so say plainly that it is still running and that they
          are free to leave. */}
      {recovering && !error && (
        <motion.div
          initial={{ opacity: 0, y: 6 }}
          animate={{ opacity: 1, y: 0 }}
          className="mt-5 max-w-md text-center"
        >
          <div className="flex items-center justify-center gap-2 text-xs text-foreground">
            <span className="relative flex h-2 w-2" aria-hidden="true">
              <span className="absolute inline-flex h-full w-full rounded-full bg-primary opacity-70 motion-safe:animate-ping" />
              <span className="relative inline-flex h-2 w-2 rounded-full bg-primary" />
            </span>
            {t('upload.stream.handoffNote')}
          </div>
        </motion.div>
      )}

      {/* Elapsed + the honest horizon. „Liko 4 min" would be a number we do
          not have; „praėjo 6 min · numatyta 15–25 min" is one we do. */}
      {elapsed != null && !error && (
        <div className="mt-4 text-center text-muted-foreground tabular-nums" style={{ fontSize: 13 }}>
          {t('upload.stream.elapsedMin', { min: Math.floor(elapsed / 60), sec: elapsed % 60 })}
          {estMinutes && (
            <> · {t('upload.stream.estimate', { value: estMinutes })}</>
          )}
        </div>
      )}

      {/* „Galite uždaryti" belongs on the screen from the first second, not
          only after a socket hand-off — the whole point is that he goes to
          dinner. It says exactly what will happen: the project appears in the
          list by itself. It does NOT promise an e-mail; nothing in this
          product sends one. */}
      {!error && (
        <p className="mt-2 max-w-md text-center text-muted-foreground" style={{ fontSize: 14 }}>
          {t('upload.stream.canLeave')}
        </p>
      )}
    </div>
  );
}
