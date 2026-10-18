/**
 * DetectRunButton — the green „Perskaityti lapą" in the viewer toolbar (Togal's
 * green button, capability A). A click opens a small picker: what to read
 * (checkboxes, all ticked; a feature ticks what it needs), then „Perskaityti
 * lapą N" or „Perskaityti visus lapus". The reading itself is €0 — the lanes on
 * the stored PDF, no Vision call — and the viewer stays usable while it runs
 * (lib/useDetectRun.js; the progress is DetectRunProgress).
 */

import { useState } from 'react';
import { Loader2, ScanLine } from 'lucide-react';

import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import {
  FEATURES, FEATURE_HINTS, FEATURE_LABELS, allFeatures, buttonLabel, canStart, toggleFeature,
} from '@/lib/detectRun';

export default function DetectRunButton({ project, currentPage, totalPages, busy = false, onStart }) {
  const [open, setOpen] = useState(false);
  const [features, setFeatures] = useState(allFeatures);
  const label = buttonLabel(project, currentPage);
  const go = (pages) => {
    setOpen(false);
    onStart?.(pages, features);
  };
  return (
    <Popover open={open} onOpenChange={(v) => setOpen(busy ? false : v)}>
      <PopoverTrigger asChild>
        <button
          type="button"
          disabled={busy}
          className="inline-flex shrink-0 items-center gap-1.5 rounded-[2px] bg-[hsl(var(--accent-2))] px-2.5 py-1 text-[12px] font-semibold text-white hover:opacity-95 disabled:opacity-70 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          title={busy
            ? 'Brėžinys skaitomas — eiga rodoma kortelėje virš brėžinio; galite toliau dirbti'
            : 'Perskaityti šį lapą iš brėžinio: mastelis, patalpos, kontūrai, angos, sienų ilgiai, grindys. Nemokama, skaičiuoja iš brėžinio.'}
          data-testid="detect-run-button"
        >
          {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" /> : <ScanLine className="h-3.5 w-3.5" aria-hidden="true" />}
          <span>{busy ? 'Skaitoma…' : label}</span>
        </button>
      </PopoverTrigger>
      <PopoverContent align="end" className="w-80 rounded-[2px] p-3" data-testid="detect-run-picker">
        <p className="text-[13px] font-semibold text-foreground">Ką perskaityti?</p>
        <p className="mt-0.5 text-[12px] leading-snug text-muted-foreground">
          Skaitoma iš paties PDF, nemokamai. Jūsų pataisyti kontūrai, įvesti skaičiai ir patvirtintos patalpos nekeičiami.
        </p>
        <ul className="mt-2 space-y-1.5">
          {FEATURES.map((f) => (
            <li key={f}>
              <label className={`flex items-start gap-2 text-[13px] ${f === 'plotai' ? 'text-muted-foreground' : 'text-foreground cursor-pointer'}`} title={FEATURE_HINTS[f]}>
                <input
                  type="checkbox"
                  className="mt-0.5 h-4 w-4 accent-[hsl(var(--accent-2))]"
                  checked={Boolean(features[f])}
                  disabled={f === 'plotai'}
                  onChange={(e) => setFeatures((s) => toggleFeature(s, f, e.target.checked))}
                  data-testid={`detect-run-feature-${f}`}
                />
                <span>
                  {FEATURE_LABELS[f]}
                  <span className="block text-[11px] leading-snug text-muted-foreground">{FEATURE_HINTS[f]}</span>
                </span>
              </label>
            </li>
          ))}
        </ul>
        <div className="mt-3 flex flex-col gap-1.5">
          <button
            type="button"
            disabled={!canStart(features)}
            onClick={() => go([currentPage])}
            className="inline-flex min-h-[36px] items-center justify-center gap-1.5 rounded-[2px] bg-[hsl(var(--accent-2))] px-3 text-[13px] font-semibold text-white hover:opacity-95 disabled:opacity-50"
            data-testid="detect-run-start-page"
          >
            <ScanLine className="h-4 w-4" aria-hidden="true" />
            {label === 'Perskaityti lapą' ? `Perskaityti lapą ${currentPage}` : `Perskaityti lapą ${currentPage} iš naujo`}
          </button>
          {(totalPages ?? 1) > 1 && (
            <button
              type="button"
              disabled={!canStart(features)}
              onClick={() => go('all')}
              className="inline-flex min-h-[36px] items-center justify-center rounded-[2px] border border-border px-3 text-[13px] text-foreground hover:bg-muted disabled:opacity-50"
              data-testid="detect-run-start-all"
            >
              Perskaityti visus lapus ({totalPages})
            </button>
          )}
        </div>
      </PopoverContent>
    </Popover>
  );
}
