/**
 * RereadDiffBanner — what the last re-read of the drawing changed.
 *
 * `lib/mergeReextract.js` records `_reread_diff` on the project: per room,
 * the facts that moved, the facts kept against a different new read (he
 * verified the room, or typed the number himself), rooms the new read added
 * and rooms it no longer found. Two reads of one PDF are not identical, so
 * this is shown — not a silent refresh — until he presses „Supratau".
 */

import { useTranslation } from 'react-i18next';
import { RefreshCw, X } from 'lucide-react';

import { Button } from '@/components/ui/button';
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
  const diff = project?._reread_diff;
  if (!diff || typeof diff !== 'object') return null;

  const roomLabel = (r) => [r.nr, r.pavadinimas].filter(Boolean).join(' ');
  const dismiss = () => {
    updateProject(project.id, { _reread_diff: null });
    onProjectChange?.({ ...project, _reread_diff: null });
  };
  const lines = rereadDiffLines(diff, t);
  const { changed, kept, added, removed } = lines;

  return (
    <div
      className="mt-3 rounded-lg border border-amber-200 bg-amber-50 p-3 text-xs text-amber-900 dark:border-amber-900/40 dark:bg-amber-950/20 dark:text-amber-200"
      data-testid="reread-diff-banner"
    >
      <div className="flex items-start gap-2">
        <RefreshCw className="w-3.5 h-3.5 shrink-0 mt-0.5" />
        <div className="flex-1 min-w-0 space-y-2">
          <p className="font-medium">
            {t('project.reread.title')}
            {diff.at ? <span className="font-normal text-amber-800/80 dark:text-amber-300/70"> · {when(diff.at)}</span> : null}
          </p>

          {rereadLinesEmpty(lines) && <p>{t('project.reread.nothing')}</p>}

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
              <p className="mt-1 text-amber-800/80 dark:text-amber-300/70">{t('project.reread.checkHint')}</p>
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
        </div>
        <Button size="sm" variant="ghost" className="h-7 px-2 text-xs shrink-0" onClick={dismiss}>
          <X className="w-3.5 h-3.5 mr-1" />
          {t('project.reread.dismiss')}
        </Button>
      </div>
    </div>
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
    <div
      className="mx-4 mt-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-900 dark:border-amber-900/40 dark:bg-amber-950/20 dark:text-amber-200"
      data-testid="reread-room-note"
    >
      <span className="font-medium">{t('project.reread.roomNote')}</span>
      {changed.length > 0 && <span> {changed.join('; ')}.</span>}
      {kept.length > 0 && <span> {t('project.reread.roomKept')}: {kept.join('; ')}.</span>}
    </div>
  );
}
