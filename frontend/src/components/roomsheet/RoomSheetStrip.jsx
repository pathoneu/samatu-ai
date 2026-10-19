/**
 * RoomSheetStrip — where he is, how much is left, and the two ways to move.
 *
 * The count and the time both come off the rooms' own `user_verified_at`
 * stamps, so closing the tab and coming back tomorrow shows the same progress.
 * „liko ~N min" is an estimate at 15 s per unchecked room and is labelled with
 * a tilde for that reason — it is the founder's time model, not a measurement.
 */

import { useTranslation } from 'react-i18next';
import { ChevronLeft, ChevronRight, ListChecks } from 'lucide-react';

import RoomPicker from '@/components/roomsheet/RoomPicker';

const NAV = 'inline-flex min-h-[44px] items-center gap-1 rounded-[2px] border '
  + 'border-white/25 px-3 text-[14px] font-semibold text-white/90 '
  + 'hover:bg-white/10 disabled:opacity-40 disabled:hover:bg-transparent '
  + 'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white/60';

export default function RoomSheetStrip({
  title, progress, index, total, onPrev, onNext, hasPrev, hasNext, onQuestions = null, picker = null,
}) {
  const { t } = useTranslation();

  // sticky (C7): which room this is, and the way to any other, stay in sight while the facts scroll
  return (
    <div className="sticky top-0 z-20 flex flex-wrap items-center gap-x-4 gap-y-2 bg-[hsl(var(--primary))] px-4 py-2.5 text-white" data-testid="room-sheet-strip">
      {/* Patikra opens on the question list (2026-09-21); this sheet is the look into one room — the way back */}
      {onQuestions && (
        <button type="button" onClick={onQuestions} className={NAV} data-testid="back-to-questions">
          <ListChecks className="h-4 w-4" aria-hidden="true" />
          {t('project.questions.backToQuestions')}
        </button>
      )}
      <h1 className="text-[17px] font-semibold">{title}</h1>

      <div className="flex min-w-[240px] flex-1 items-center gap-3">
        <span className="text-[14px] text-white/80">
          {t('project.roomSheet.progress', {
            verified: progress.verified, total: progress.total,
          })}
        </span>
        <span
          className="h-1.5 flex-1 overflow-hidden rounded-full bg-white/20"
          role="progressbar"
          aria-valuenow={progress.percent}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label={t('project.roomSheet.progress', {
            verified: progress.verified, total: progress.total,
          })}
        >
          <span
            className="block h-full bg-[hsl(var(--accent-2))]"
            style={{ width: `${progress.percent}%` }}
          />
        </span>
        <span className="font-mono text-[14px] tabular-nums text-white/80">
          {progress.unchecked > 0
            ? t('project.roomSheet.timeLeft', { minutes: progress.minutes })
            : t('project.roomSheet.timeDone')}
        </span>
      </div>

      {picker ? (
        <RoomPicker items={picker.items} index={index} total={total} onPick={picker.onPick} />
      ) : (
        <span className="font-mono text-[14px] tabular-nums text-white/70">
          {t('project.roomSheet.roomStep', { index, total })}
        </span>
      )}

      <div className="flex items-center gap-2">
        <button type="button" onClick={onPrev} disabled={!hasPrev} className={NAV}>
          <ChevronLeft className="h-4 w-4" aria-hidden="true" />
          {t('project.roomSheet.prev')}
        </button>
        <button type="button" onClick={onNext} disabled={!hasNext} className={NAV}>
          {t('project.roomSheet.next')}
          <ChevronRight className="h-4 w-4" aria-hidden="true" />
        </button>
      </div>
    </div>
  );
}
