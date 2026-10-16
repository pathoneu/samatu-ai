/**
 * DetectRunProgress — the pill over the drawing while „Perskaityti lapą" runs:
 * the current stage's name, a thin progress line, one or two sentences on what
 * that stage reads (Togal shows a video during processing; this says it in
 * words), and the stage list — ✓ done, ● running, – skipped with its reason,
 * ✕ failed with its reason. It never blocks the viewer; a finished run keeps its
 * numbers here until closed.
 */

import { useState } from 'react';
import { ChevronDown, ChevronUp, X } from 'lucide-react';

import { headline, statusMark } from '@/lib/detectRun';

const MARK_CLASS = {
  done: 'text-[hsl(var(--accent-2))]',
  running: 'text-[hsl(var(--accent-2))] animate-pulse',
  skipped: 'text-muted-foreground',
  failed: 'text-destructive',
  pending: 'text-muted-foreground/60',
};

export default function DetectRunProgress({ run, view, onDismiss, className = '' }) {
  const [open, setOpen] = useState(true);
  if (!run) return null;
  if (run.startError) {
    return (
      <div className={`pointer-events-auto w-[320px] rounded-[2px] border border-destructive/40 bg-card px-3 py-2 text-[12px] shadow-md ${className}`} role="alert" data-testid="detect-run-progress">
        <div className="flex items-start gap-2">
          <span className="text-destructive">✕</span>
          <span className="flex-1 text-foreground">{run.startError}</span>
          <button type="button" onClick={onDismiss} aria-label="Uždaryti" className="text-muted-foreground hover:text-foreground"><X className="h-3.5 w-3.5" /></button>
        </div>
      </div>
    );
  }
  if (!view) return null;
  const { stages, current, done, failed, progress, terminal } = view;
  const summary = done ? stages.at(-1)?.note : null;
  return (
    <div
      className={`pointer-events-auto w-[340px] max-w-[calc(100vw-32px)] rounded-[2px] border bg-card text-[12px] shadow-md ${failed ? 'border-destructive/40' : 'border-[hsl(var(--accent-2)/0.4)]'} ${className}`}
      role="status"
      aria-live="polite"
      data-testid="detect-run-progress"
    >
      <div className="flex items-center gap-2 px-3 pt-2">
        <span className={MARK_CLASS[failed ? 'failed' : done ? 'done' : 'running']} aria-hidden="true">
          {failed ? '✕' : done ? '✓' : '●'}
        </span>
        <span className="flex-1 truncate font-semibold text-foreground" data-testid="detect-run-headline">{headline(view, run.pages)}</span>
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          aria-label={open ? 'Slėpti etapus' : 'Rodyti etapus'}
          title={open ? 'Slėpti etapus' : 'Rodyti etapus'}
          className="text-muted-foreground hover:text-foreground"
        >{open ? <ChevronUp className="h-3.5 w-3.5" /> : <ChevronDown className="h-3.5 w-3.5" />}</button>
        {terminal && (
          <button type="button" onClick={onDismiss} aria-label="Uždaryti" title="Uždaryti" className="text-muted-foreground hover:text-foreground" data-testid="detect-run-dismiss">
            <X className="h-3.5 w-3.5" />
          </button>
        )}
      </div>
      <div className="mx-3 mt-1.5 h-[3px] bg-muted" aria-hidden="true">
        <div className={`h-full transition-[width] duration-300 ${failed ? 'bg-destructive' : 'bg-[hsl(var(--accent-2))]'}`} style={{ width: `${Math.round(progress * 100)}%` }} />
      </div>
      {run.snapshot?.skaitoma_lt && (
        <p className="px-3 pt-1.5 text-[11px] leading-snug text-muted-foreground" data-testid="detect-run-scope">{run.snapshot.skaitoma_lt}</p>
      )}
      {!terminal && current?.about && (
        <p className="px-3 pt-1.5 leading-snug text-[hsl(var(--ink-2))]" data-testid="detect-run-about">{current.about}</p>
      )}
      {summary && <p className="px-3 pt-1.5 leading-snug text-foreground" data-testid="detect-run-summary">{summary}</p>}
      {run.lost && <p className="px-3 pt-1.5 leading-snug text-destructive">Eigos gauti nepavyko ({run.lost}) — atnaujinkite puslapį ir patikrinkite projektą.</p>}
      {open ? (
        <ol className="mt-1.5 space-y-0.5 border-t border-border px-3 py-2" data-testid="detect-run-stages">
          {stages.map((s) => (
            <li key={s.id} className="flex items-start gap-2" data-stage={s.id} data-status={s.status}>
              <span className={`w-3 shrink-0 text-center ${MARK_CLASS[s.status] || MARK_CLASS.pending}`} aria-hidden="true">{statusMark(s.status)}</span>
              <span className="min-w-0 flex-1">
                <span className={s.status === 'pending' ? 'text-muted-foreground' : 'text-foreground'}>{s.label}</span>
                {s.note && s.id !== 'kiekiai' && <span className="block text-[11px] leading-snug text-muted-foreground">{s.note}</span>}
                {s.note && s.id === 'kiekiai' && s.status !== 'done' && <span className="block text-[11px] leading-snug text-muted-foreground">{s.note}</span>}
              </span>
            </li>
          ))}
        </ol>
      ) : <div className="h-2" />}
    </div>
  );
}
