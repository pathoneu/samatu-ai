/**
 * FixConsequence — what the fix he just made changed, right under the fact he
 * made it on, with the way back.
 *
 * Founder, after the first real Patikra run (2026-09-17): „sunku suprasti, ar
 * kažką pataisiau". The only sign used to be one line at the very bottom of
 * the panel, a screen or two away from the fact, naming one row. This strip
 * sits under the fixed fact, lists the sąmata rows that moved (before → after,
 * see `lib/roomSheet.consequenceOf`) and undoes the fix with one click — the
 * project goes back to exactly what it was, not to a recomputation of it.
 */

import { useTranslation } from 'react-i18next';
import { Undo2 } from 'lucide-react';
import { ltNumber } from '@/lib/ledger';
import { ltPlural } from '@/lib/ltPlural';
import { cleanUserText } from '@/lib/userText';

const qty = (v, unit) => (v == null ? '—' : `${ltNumber(v, 2)}${unit ? ` ${unit}` : ''}`);

export default function FixConsequence({ consequence, busy = false, onUndo }) {
  const { t } = useTranslation();
  if (!consequence) return null;
  const { count, lines, more } = consequence;
  const rowsWord = ltPlural(count, 'eilutė', 'eilutės', 'eilučių');

  return (
    <div
      className="mx-4 mb-3 rounded-[2px] border border-[hsl(var(--accent-2)/0.35)] bg-[hsl(var(--accent-2)/0.06)] px-3 py-2 text-[14px]"
      data-testid="fix-consequence"
      role="status"
    >
      <div className="flex flex-wrap items-start justify-between gap-2">
        <p className="font-semibold text-foreground">
          {count > 0
            ? t('project.roomSheet.fixChanged', { count, rowsWord })
            : t(consequence.sameValue ? 'project.roomSheet.fixSameValue' : 'project.roomSheet.fixNoRows')}
        </p>
        <button
          type="button"
          disabled={busy}
          onClick={onUndo}
          className="inline-flex min-h-[36px] items-center gap-1.5 rounded-[2px] border border-border bg-card px-3 text-[14px] font-semibold hover:bg-muted disabled:opacity-50 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <Undo2 className="h-4 w-4" aria-hidden="true" />
          {t('project.roomSheet.fixUndo')}
        </button>
      </div>
      {lines.length > 0 && (
        <ul className="mt-1 space-y-0.5">
          {lines.map((l) => (
            <li key={`${l.label}-${l.unit}`} className="leading-snug text-[hsl(var(--ink-2))]">
              {cleanUserText(l.label)}:{' '}
              <span className="font-mono text-muted-foreground">{qty(l.before, l.unit)}</span>
              {' → '}
              <span className="font-mono font-semibold text-foreground">{qty(l.after, l.unit)}</span>
            </li>
          ))}
          {more > 0 && (
            <li className="text-[13px] text-muted-foreground">{t('project.roomSheet.fixMore', { count: more })}</li>
          )}
        </ul>
      )}
    </div>
  );
}
