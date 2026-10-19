/**
 * DetectRunProgress — the run pill at the bottom of the drawing while „Perskaityti lapą" runs (Pathon v3
 * W5-C C5, coverage #29-pill / #169). It has the shape of the mode pill (ModePill): one line with the mark
 * (✓ done, ● running, ✕ failed), the current stage's name and the thin progress line; above it, the stage
 * list — ✓ done, ● running, – skipped with its reason, ✕ failed with its reason — folded with one button.
 * It never blocks the viewer (it stands at the bottom, clear of the top row of tool cards it used to cover);
 * a finished run keeps its numbers here until closed.
 *
 * Nothing fails silently: a lost connection or a start that did not go says so in the one notice
 * (components/ui/Notice) with „Bandyti dar kartą" — the run itself keeps going on the server, so trying
 * again only picks its progress up again.
 */

import { useState } from 'react';
import { ChevronDown, ChevronUp, X } from 'lucide-react';

import Notice from '@/components/ui/Notice';
import { headline, statusMark } from '@/lib/detectRun';

const MARK_CLASS = {
  done: 'text-[hsl(var(--accent-2))]',
  running: 'text-[hsl(var(--accent-2))] animate-pulse',
  skipped: 'text-muted-foreground',
  failed: 'text-destructive',
  pending: 'text-muted-foreground',
};

const ICON_BUTTON = 'inline-flex h-8 w-8 shrink-0 items-center justify-center rounded text-muted-foreground hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring';
const PLAIN_BUTTON = 'inline-flex min-h-[32px] items-center rounded border border-border bg-card px-3 text-ui font-medium text-foreground hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring';

export default function DetectRunProgress({ run, view, groups = null, onDismiss, onRetry = null, className = '' }) {
  const [open, setOpen] = useState(true);
  if (!run) return null;
  if (run.startError) {
    return (
      <div className={`pointer-events-auto w-[440px] max-w-[calc(100vw-32px)] shadow-md ${className}`} data-testid="detect-run-progress">
        <Notice
          tone="error"
          title="Skaitymas nepradėtas"
          onDismiss={onDismiss}
          className="bg-card"
          action={onRetry ? <button type="button" className={PLAIN_BUTTON} onClick={onRetry} data-testid="detect-run-retry">Bandyti dar kartą</button> : null}
        >
          <p>{run.startError}</p>
        </Notice>
      </div>
    );
  }
  if (!view) return null;
  const { stages, current, done, failed, progress, terminal } = view;
  const summary = done ? stages.at(-1)?.note : null;
  return (
    <div
      className={`pointer-events-auto flex w-[440px] max-w-[calc(100vw-32px)] flex-col rounded-panel border bg-card text-ui shadow-md ${failed ? 'border-destructive/40' : 'border-border'} ${className}`}
      role="status"
      aria-live="polite"
      data-testid="detect-run-progress"
      data-shape="pill"
    >
      {/* above the pill line: what the stage reads, the stage list (folded with the chevron) */}
      {open && (
        <div className="max-h-[50vh] overflow-y-auto border-b border-border px-3 py-2">
          {run.snapshot?.skaitoma_lt && (
            <p className="leading-snug text-muted-foreground" data-testid="detect-run-scope">{run.snapshot.skaitoma_lt}</p>
          )}
          {!terminal && current?.about && (
            <p className="pt-1 leading-snug text-[hsl(var(--ink-2))]" data-testid="detect-run-about">{current.about}</p>
          )}
          <ol className="mt-1.5 space-y-0.5" data-testid="detect-run-stages">
            {stages.map((s) => (
              <li key={s.id} className="flex items-start gap-2" data-stage={s.id} data-status={s.status}>
                <span className={`w-4 shrink-0 text-center ${MARK_CLASS[s.status] || MARK_CLASS.pending}`} aria-hidden="true">{statusMark(s.status)}</span>
                <span className="min-w-0 flex-1">
                  <span className={s.status === 'pending' ? 'text-muted-foreground' : 'text-foreground'}>{s.label}</span>
                  {s.note && (s.id !== 'kiekiai' || s.status !== 'done') && (
                    <span className="block leading-snug text-muted-foreground">{s.note}</span>
                  )}
                </span>
              </li>
            ))}
          </ol>
        </div>
      )}
      {summary && <p className="px-3 pt-2 leading-snug text-foreground" data-testid="detect-run-summary">{summary}</p>}
      {run.lost && (
        <div className="px-2 pt-2">
          <Notice
            tone="error"
            title="Ryšys nutrūko"
            action={onRetry ? <button type="button" className={PLAIN_BUTTON} onClick={onRetry} data-testid="detect-run-retry">Bandyti dar kartą</button> : null}
            data-testid="detect-run-lost"
          >
            <p>Skaitymo eigos gauti nepavyko ({run.lost}). Skaitymas serveryje tęsiasi — bandykite dar kartą.</p>
          </Notice>
        </div>
      )}
      {/* the pill line */}
      <div className="flex items-center gap-2 px-3 py-1.5">
        <span className={`w-4 text-center ${MARK_CLASS[failed ? 'failed' : done ? 'done' : 'running']}`} aria-hidden="true">
          {failed ? '✕' : done ? '✓' : '●'}
        </span>
        <span className="min-w-0 flex-1">
          <span className="block truncate font-semibold text-foreground" data-testid="detect-run-headline">
            {headline(view, run.pages, run.snapshot?.result?._meta?.geometrija?.grupes || groups)}
          </span>
          <span className="mt-1 block h-[3px] bg-muted" aria-hidden="true">
            <span className={`block h-full transition-[width] duration-300 ${failed ? 'bg-destructive' : 'bg-[hsl(var(--accent-2))]'}`} style={{ width: `${Math.round(progress * 100)}%` }} />
          </span>
        </span>
        <button
          type="button"
          onClick={() => setOpen((v) => !v)}
          aria-expanded={open}
          aria-label={open ? 'Slėpti etapus' : 'Rodyti etapus'}
          title={open ? 'Slėpti etapus' : 'Rodyti etapus'}
          className={ICON_BUTTON}
          data-testid="detect-run-toggle"
        >{open ? <ChevronDown className="h-4 w-4" /> : <ChevronUp className="h-4 w-4" />}</button>
        {terminal && (
          <button type="button" onClick={onDismiss} aria-label="Uždaryti" title="Uždaryti" className={ICON_BUTTON} data-testid="detect-run-dismiss">
            <X className="h-4 w-4" />
          </button>
        )}
      </div>
    </div>
  );
}
