/**
 * RereadDiffBanner — what the last re-read of the drawing changed.
 *
 * `lib/mergeReextract.js` records `_reread_diff` on the project: per room,
 * the facts that moved, the facts kept against a different new read (he
 * verified the room, or typed the number himself), rooms the new read added
 * and rooms it no longer found. Two reads of one PDF are not identical, so
 * this is shown — not a silent refresh — until he presses „Supratau".
 *
 * v3 (founder decision 6, 2026-10-18): it is a ONE-LINE chip — „Brėžinys perskaitytas
 * iš naujo · skaičiai nepasikeitė · Rodyti" — and the room-by-room list opens behind
 * „Rodyti". The counts stay on the line, so nothing that moved is hidden; opening the
 * list writes nothing, only „Supratau" clears the diff. One Notice (components/ui).
 */

import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { RefreshCw } from 'lucide-react';

import Notice from '@/components/ui/Notice';
import { updateProject } from '@/lib/projectStore';
// every value said in words, a line that reads the same before and after left out (lib/rereadDiffText.js)
import { rereadDiffLines, rereadLinesEmpty, rereadRoomLines, rereadValue } from '@/lib/rereadDiffText';

function when(iso) {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  return d.toLocaleString('lt-LT', { dateStyle: 'short', timeStyle: 'short' });
}

export default function RereadDiffBanner({ project, onProjectChange }) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const diff = project?._reread_diff;
  if (!diff || typeof diff !== 'object') return null;

  const roomLabel = (r) => [r.nr, r.pavadinimas].filter(Boolean).join(' ');
  const dismiss = () => {
    updateProject(project.id, { _reread_diff: null });
    onProjectChange?.({ ...project, _reread_diff: null });
  };
  const lines = rereadDiffLines(diff, t);
  const { changed, kept, added, removed } = lines;
  const empty = rereadLinesEmpty(lines);
  // What moved, as counts on the one line — the list itself is behind „Rodyti".
  const summary = empty
    ? t('project.reread.chipNothing')
    : [
      changed.length > 0 && t('project.reread.chipChanged', { count: changed.length }),
      kept.length > 0 && t('project.reread.chipKept', { count: kept.length }),
      added.length > 0 && t('project.reread.chipAdded', { count: added.length }),
      removed.length > 0 && t('project.reread.chipRemoved', { count: removed.length }),
    ].filter(Boolean).join(' · ');
  const tone = empty ? 'info' : 'warning';
  const toggle = (
    <button
      type="button"
      onClick={() => setOpen((v) => !v)}
      aria-expanded={open}
      className="shrink-0 rounded px-1 font-medium text-[hsl(var(--accent-2))] underline underline-offset-2 hover:no-underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
      data-testid="reread-diff-toggle"
    >
      {open ? t('project.reread.hide') : t('project.reread.show')}
    </button>
  );

  if (!open) {
    return (
      <div className="mt-3">
        <Notice
          compact
          tone={tone}
          icon={RefreshCw}
          title={t('project.reread.title')}
          action={toggle}
          onDismiss={dismiss}
          dismissLabel={t('project.reread.dismiss')}
          data-testid="reread-diff-banner"
        >
          {summary}
        </Notice>
      </div>
    );
  }

  return (
    <Notice
      tone={tone}
      icon={RefreshCw}
      className="mt-3"
      title={(
        <>
          {t('project.reread.title')}
          {diff.at ? <span className="font-normal text-muted-foreground"> · {when(diff.at)}</span> : null}
        </>
      )}
      action={toggle}
      onDismiss={dismiss}
      dismissLabel={t('project.reread.dismiss')}
      data-testid="reread-diff-banner"
    >
      {empty && <p>{t('project.reread.nothing')}</p>}

      {changed.length > 0 && (
        <div>
          <p className="font-medium">{t('project.reread.changedTitle', { count: changed.length })}</p>
          <ul className="mt-0.5 list-disc pl-4 space-y-0.5">
            {changed.map((r) => (
              <li key={`c-${r.nr}`}>
                <span className="font-medium">{roomLabel(r)}</span>
                {' — '}
                {r.lines.join('; ')}
              </li>
            ))}
          </ul>
          <p className="mt-1 text-muted-foreground">{t('project.reread.checkHint')}</p>
        </div>
      )}

      {kept.length > 0 && (
        <div>
          <p className="font-medium">{t('project.reread.keptTitle', { count: kept.length })}</p>
          <ul className="mt-0.5 list-disc pl-4 space-y-0.5">
            {kept.map((r) => (
              <li key={`k-${r.nr}`}>
                <span className="font-medium">{roomLabel(r)}</span>
                {' — '}
                {t(`project.reread.kept.${r.why}`, { defaultValue: r.why })}
                {r.lines.length > 0 && (
                  <>
                    {': '}
                    {r.lines.join('; ')}
                  </>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      {added.length > 0 && (
        <p>
          <span className="font-medium">{t('project.reread.addedTitle', { count: added.length })}</span>
          {': '}
          {added.map((r) => `${roomLabel(r)}${r.plotas_m2 != null ? ` (${rereadValue('plotas_m2', r.plotas_m2, t)})` : ''}`).join(', ')}
        </p>
      )}

      {removed.length > 0 && (
        <p>
          <span className="font-medium">{t('project.reread.removedTitle', { count: removed.length })}</span>
          {': '}
          {removed.map((r) => `${roomLabel(r)}${r.plotas_m2 != null ? ` (${rereadValue('plotas_m2', r.plotas_m2, t)})` : ''}`).join(', ')}
        </p>
      )}
    </Notice>
  );
}

/**
 * The same diff, for ONE room, on its check sheet: „Perskaičius iš naujo:
 * durys 1 → 2" — so the person checking the room knows this is the fact that
 * moved, and the sheet is where he decides.
 */
export function RereadRoomNote({ project, roomNr }) {
  const { t } = useTranslation();
  const entries = rereadRoomLines(project?._reread_diff, roomNr, t);
  if (!entries) return null;
  const changed = entries.changed;
  const kept = entries.kept
    ? [t(`project.reread.kept.${entries.kept.why}`, { defaultValue: entries.kept.why })].concat(entries.kept.lines)
    : [];
  return (
    <Notice tone="warning" icon={RefreshCw} className="mx-4 mt-3" data-testid="reread-room-note">
      <p>
        <span className="font-medium">{t('project.reread.roomNote')}</span>
        {changed.length > 0 && <span> {changed.join('; ')}.</span>}
        {kept.length > 0 && <span> {t('project.reread.roomKept')}: {kept.join('; ')}.</span>}
      </p>
    </Notice>
  );
}
