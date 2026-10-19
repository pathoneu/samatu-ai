/**
 * QuantityLine — one number this room puts into the sąmata, and its arithmetic.
 *
 * Expanded it shows the `formula` sentence and, where the family emits them,
 * the `terms`. It never re-sums anything: the ledger is the authority, and a
 * client-side re-derivation is exactly how the retired `_build_trace_links`
 * drifted (docs/ARCHITECTURE.md § Position identity).
 *
 * „Pataisyti" is offered only when it can honestly do what it says. A per-room
 * share override does not exist in the backend, so the edit writes a whole-row
 * manual override and only when THIS room is the row's sole contributor. Every
 * other case gets a sentence naming the two things that do work — the fact
 * above, or the whole line in the sąmata — instead of a button that lies.
 */

import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Check, ChevronDown, ChevronRight, Pencil } from 'lucide-react';
import { ltNumber, ltQuantity } from '@/lib/ledger';
import { isValidAmount, parseLtNumber } from '@/lib/parseLtNumber';
import { cleanUserText } from '@/lib/userText';
import { hasCornerTerms, termRows } from '@/lib/roomSheet';

export default function QuantityLine({
  quantity, canOverride = false, busy = false, overridden = false,
  cornersOnPlan = false, onOverride, onExpandChange,
}) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState('');

  const terms = termRows(quantity?.terms);
  // Counting corners in the arithmetic is not the same as HAVING corner dots to
  // point at: a room with no outline has none. Promising a mark that is not on
  // the drawing is the exact failure this screen exists to prevent, so the note
  // needs both — the terms AND the dots. (Caught in the browser on a room whose
  // polygon the extractor never produced.)
  const corners = hasCornerTerms(quantity?.terms) && cornersOnPlan;
  const formula = cleanUserText(quantity?.formula || '');
  const because = cleanUserText(quantity?.included_because || '');

  const toggle = () => {
    const next = !open;
    setOpen(next);
    // The plan pane thickens the corner dots while a corner-counting line is open.
    onExpandChange?.(next && corners);
  };

  const commit = () => {
    const num = parseLtNumber(draft);
    if (!isValidAmount(num)) return;
    onOverride?.(num);
    setEditing(false);
  };

  return (
    <div className={`border-t border-border px-4 py-2.5 ${open ? 'bg-surface-2' : ''}`}>
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
        <button
          type="button"
          onClick={toggle}
          aria-expanded={open}
          className="flex min-h-[44px] min-w-0 flex-1 items-center gap-2 text-left focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          {open
            ? <ChevronDown className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden="true" />
            : <ChevronRight className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden="true" />}
          <span className="min-w-0 text-[15px] font-semibold leading-snug">
            {quantity?.aprasymas}
          </span>
        </button>

        <span className="font-mono text-[16px] font-semibold tabular-nums">
          {ltQuantity(quantity?.value, quantity?.unit, 2)}
        </span>

        {canOverride ? (
          <button
            type="button"
            disabled={busy}
            onClick={() => {
              setDraft(String(quantity?.value ?? '').replace('.', ','));
              setEditing((v) => !v);
            }}
            className="inline-flex min-h-[44px] items-center gap-1.5 rounded-[2px] border border-border bg-card px-3 text-[14px] font-semibold hover:bg-muted disabled:opacity-50"
          >
            <Pencil className="h-4 w-4" aria-hidden="true" />
            {editing ? t('project.roomSheet.cancel') : t('project.roomSheet.fix')}
          </button>
        ) : null}
      </div>

      {overridden && (
        <p className="mt-1 flex items-center gap-1.5 text-[13px] text-accent-2">
          <Check className="h-3.5 w-3.5" aria-hidden="true" />
          {t('project.roomSheet.overrideSaved')}
        </p>
      )}

      {editing && canOverride && (
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <label className="text-[14px] text-ink-2" htmlFor={`q-${quantity.row_id}`}>
            {t('project.roomSheet.overrideLabel')}
          </label>
          <input
            id={`q-${quantity.row_id}`}
            value={draft}
            inputMode="decimal"
            onFocus={(e) => e.target.select()}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') { e.preventDefault(); e.stopPropagation(); commit(); }
              if (e.key === 'Escape') setEditing(false);
            }}
            className="h-11 w-28 rounded-[2px] border border-accent-2 bg-card px-2 text-right font-mono text-[16px]"
          />
          <button
            type="button"
            disabled={busy}
            onClick={commit}
            className="inline-flex min-h-[44px] items-center rounded-[2px] border border-accent-2 bg-accent-2 px-3 text-[14px] font-semibold text-white disabled:opacity-50"
          >
            {t('project.roomSheet.save')}
          </button>
        </div>
      )}

      {open && (
        <div className="mt-1.5 pl-6">
          {formula && (
            <p className="font-mono text-[14px] leading-snug text-foreground">{formula}</p>
          )}
          {terms.length > 0 && (
            <dl className="mt-1.5 grid grid-cols-[minmax(0,1fr)_auto] gap-x-4 gap-y-0.5">
              {terms.map((term) => (
                <div key={term.label} className="contents">
                  <dt className="text-[14px] text-ink-2">{term.label}</dt>
                  <dd className="text-right font-mono text-[14px] tabular-nums">
                    {ltNumber(term.value, 2)}
                  </dd>
                </div>
              ))}
            </dl>
          )}
          {corners && (
            <p className="mt-1 text-[13px] text-muted-foreground">
              {t('project.roomSheet.cornersHighlighted')}
            </p>
          )}
          {because && (
            <p className="mt-1 text-[13px] text-muted-foreground">{because}</p>
          )}
          {!canOverride && (
            <p className="mt-1.5 text-[13px] leading-snug text-muted-foreground">
              {t('project.roomSheet.overrideShared')}
            </p>
          )}
        </div>
      )}
    </div>
  );
}
