/**
 * RunTeaching — teaching while he waits, and before he starts (Pathon v3 W5-C).
 *
 *   RunTeaching    C1 / #34 — the „Kol skaitoma" panel under the paid read's progress: the stage being read
 *                  now, what to check afterwards (Patikra), the time, and that the window can be closed safely
 *                  once the server has the run. Built from the stages the stream already sends — no new call.
 *   ReadScopeCard  C2 / #33 — one card before the first run: what the program reads and what it does not.
 *                  It never blocks: „Supratau" closes it, and the first run started retires it.
 *
 * The words live in i18n/lt.json (`runTeaching.*`); the decisions in lib/runTeaching.js.
 */

import { useEffect, useState } from 'react';
import { useTranslation } from '@/i18n/react';
import { Check, Clock, ListChecks, LogOut, Minus, ScanLine, X } from 'lucide-react';

import { markReadScopeSeen, readScopeDue, runTeachingFor } from '@/lib/runTeaching';

const storage = () => {
  try {
    return typeof window !== 'undefined' ? window.localStorage : null;
  } catch {
    return null;
  }
};

export default function RunTeaching({ phase, progress, elapsed, started = false, estMinutes = '', className = '' }) {
  const { t } = useTranslation();
  // his first read has started: the card about what is read is no longer news
  useEffect(() => { markReadScopeSeen(storage()); }, []);
  const v = runTeachingFor({ phase, progress, elapsed, started, estMinutes });
  const row = 'flex items-start gap-3';
  const icon = 'mt-0.5 h-5 w-5 shrink-0 text-ink-2';
  return (
    <section
      className={`w-full rounded-panel border border-border bg-card p-4 text-ui text-foreground ${className}`}
      aria-labelledby="run-teaching-title"
      data-testid="run-teaching"
    >
      <h2 id="run-teaching-title" className="text-[16px] font-semibold">{t('runTeaching.title')}</h2>
      <ul className="mt-3 space-y-3">
        <li className={row} data-testid="run-teaching-now">
          <ScanLine className={icon} aria-hidden="true" />
          <p>
            <span className="font-semibold">{t('runTeaching.nowLabel', { step: v.step, steps: v.steps })}</span>{' '}
            {t(`runTeaching.${v.stageKey}`, v.stageParams)}
          </p>
        </li>
        <li className={row}>
          <ListChecks className={icon} aria-hidden="true" />
          <p><span className="font-semibold">{t('runTeaching.afterLabel')}</span> {t('runTeaching.after')}</p>
        </li>
        <li className={row} data-testid="run-teaching-time">
          <Clock className={icon} aria-hidden="true" />
          <p>
            <span className="font-semibold">{t('runTeaching.timeLabel')}</span>{' '}
            {t('runTeaching.time', { estimate: v.estimate, minutes: v.minutes })}
          </p>
        </li>
        <li className={row} data-testid="run-teaching-leave">
          <LogOut className={icon} aria-hidden="true" />
          <p>{t(v.canLeave ? 'runTeaching.canLeave' : 'runTeaching.waitToLeave')}</p>
        </li>
      </ul>
    </section>
  );
}

export function ReadScopeCard({ className = '' }) {
  const { t } = useTranslation();
  const [due, setDue] = useState(() => readScopeDue(storage()));
  if (!due) return null;
  const close = () => { markReadScopeSeen(storage()); setDue(false); };
  const items = [
    { key: 'yes', Icon: Check, word: t('runTeaching.scope.yesWord'), text: t('runTeaching.scope.yes') },
    { key: 'no', Icon: Minus, word: t('runTeaching.scope.noWord'), text: t('runTeaching.scope.no') },
    { key: 'slow', Icon: Clock, word: t('runTeaching.scope.slowWord'), text: t('runTeaching.scope.slow') },
  ];
  return (
    <section
      className={`rounded-panel border border-border bg-card p-4 text-ui text-foreground ${className}`}
      aria-labelledby="read-scope-title"
      data-testid="read-scope-card"
    >
      <div className="flex items-start gap-3">
        <h2 id="read-scope-title" className="flex-1 text-[16px] font-semibold">{t('runTeaching.scope.title')}</h2>
        <button
          type="button"
          onClick={close}
          className="inline-flex min-h-[32px] items-center gap-1 rounded px-2 text-ui text-foreground hover:bg-muted focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          data-testid="read-scope-dismiss"
        >
          <X className="h-4 w-4" aria-hidden="true" />
          {t('runTeaching.scope.dismiss')}
        </button>
      </div>
      <ul className="mt-2 space-y-2">
        {items.map(({ key, Icon, word, text }) => (
          <li key={key} className="flex items-start gap-2" data-scope={key}>
            <Icon className="mt-0.5 h-4 w-4 shrink-0 text-ink-2" aria-hidden="true" />
            {/* the word says it, not the icon's colour */}
            <p><span className="font-semibold">{word}</span> {text}</p>
          </li>
        ))}
      </ul>
    </section>
  );
}
