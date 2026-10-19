/**
 * RereadDiffBanner — what the last re-read of the drawing changed.
 *
 * `lib/mergeReextract.js` records `_reread_diff` on the project: per room,
 * the facts that moved, the facts kept against a different new read (he
 * verified the room, or typed the number himself), rooms the new read added
 * and rooms it no longer found. Two reads of one PDF are not identical, so
 * this is shown — not a silent refresh — until he presses „Supratau".
 *
 * v3 (founder decision 6, 2026-10-18): it is a ONE-LINE chip and the room-by-room list opens behind
 * the toggle. The counts stay on the line, so nothing that moved is hidden; opening the list writes
 * nothing, only „Supratau" clears the diff. One Notice (components/ui).
 *
 * Pathon v3 W4-A M3 — „Kas pasikeitė": the line leads with the sąmata ROWS the read moved
 * („Kas pasikeitė · 12 eilučių · pasikeitė 2 patalpos · kartu perskaityta: langų žiniaraštis"), from
 * `_reread_diff.eilutes` / `.perskaityta` (lib/changeSummary.js, written by every landing path — a free
 * re-read, „Perskaityti iš naujo", a paid re-read). „Peržiūrėti" opens the rows and the rooms;
 * „Atšaukti" puts the project back as it was before the read through the saved versions (the state it
 * replaces is kept as „Prieš grąžinant", and the toast offers it back). Nothing is hover-only.
 */

import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { RefreshCw, Undo2 } from 'lucide-react';
import { toast } from 'sonner';

import Notice from '@/components/ui/Notice';
import { useConfirm } from '@/components/ui/confirm-provider';
import { adoptServerProject, flushProjectSaves, updateProject } from '@/lib/projectStore';
import { fetchVersions, restoreVersion } from '@/lib/projectVersions';
import { rereadUndoTarget, rowChangeCount } from '@/lib/changeSummary';
import { ltQuantity } from '@/lib/ledger';
// every value said in words, a line that reads the same before and after left out (lib/rereadDiffText.js)
import { rereadDiffLines, rereadLinesEmpty, rereadRoomLines, rereadValue } from '@/lib/rereadDiffText';

// How many changed rows the open list names before „ir dar N".
const ROWS_SHOWN = 30;

/** „Grindjuostės 40,00 → 41,20 m", „nauja: Hidroizoliacija 9,00 m²", „neliko: Kampai 12,00 m". */
function rowLines(eilutes, t) {
  const e = eilutes || {};
  return [
    ...(e.changed || []).map((r) => `${r.aprasymas} ${ltQuantity(r.from, '')} → ${ltQuantity(r.to, r.unit)}`),
    ...(e.added || []).map((r) => `${t('project.reread.rowNew')}: ${r.aprasymas} ${ltQuantity(r.to, r.unit)}`),
    ...(e.removed || []).map((r) => `${t('project.reread.rowGone')}: ${r.aprasymas} ${ltQuantity(r.from, r.unit)}`),
  ];
}

function when(iso) {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return '';
  return d.toLocaleString('lt-LT', { dateStyle: 'short', timeStyle: 'short' });
}

export default function RereadDiffBanner({ project, onProjectChange }) {
  const { t } = useTranslation();
  const confirm = useConfirm();
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const diff = project?._reread_diff;
  if (!diff || typeof diff !== 'object') return null;

  // „Atšaukti": the saved version just before the newest read, restored through Versijos.
  const land = async (versionId) => {
    const saved = await restoreVersion(project.id, versionId);
    const adopted = adoptServerProject(saved) || saved;
    onProjectChange?.(adopted);
    return adopted;
  };
  const undo = async () => {
    if (busy) return;
    setBusy(true);
    try {
      await flushProjectSaves();
      const plan = rereadUndoTarget(await fetchVersions(project.id));
      if (!plan) {
        toast.error(t('project.reread.undoNone'));
        return;
      }
      if (plan.later > 0) {
        const ok = await confirm({
          title: t('project.reread.undoConfirmTitle'),
          description: t('project.reread.undoConfirmDesc', { count: plan.later }),
          confirmText: t('project.reread.undo'),
          cancelText: t('project.reread.undoKeep'),
        });
        if (!ok) return;
      }
      await land(plan.target.id);
      const replaced = (await fetchVersions(project.id).catch(() => [])).find((v) => v.saltinis === 'grazinta');
      toast.success(t('project.reread.undoDone'), {
        duration: 10000,
        action: replaced ? {
          label: t('project.reread.undoRedo'),
          onClick: async () => {
            try {
              await land(replaced.id);
              toast.success(t('project.reread.undoRedone'));
            } catch {
              toast.error(t('project.reread.undoFailed'));
            }
          },
        } : undefined,
      });
    } catch {
      toast.error(t('project.reread.undoFailed'));
    } finally {
      setBusy(false);
    }
  };

  const roomLabel = (r) => [r.nr, r.pavadinimas].filter(Boolean).join(' ');
  const dismiss = () => {
    updateProject(project.id, { _reread_diff: null });
    onProjectChange?.({ ...project, _reread_diff: null });
  };
  const lines = rereadDiffLines(diff, t);
  const { changed, kept, added, removed } = lines;
  const roomsEmpty = rereadLinesEmpty(lines);
  const nRows = rowChangeCount(diff);
  const rows = rowLines(diff.eilutes, t);
  const reads = (Array.isArray(diff.perskaityta) ? diff.perskaityta : [])
    .map((k) => t(`project.reread.reads.${k}`, { defaultValue: '' })).filter(Boolean);
  const empty = roomsEmpty && nRows === 0;
  // What moved, as counts on the one line — the lists themselves are behind „Peržiūrėti".
  const summary = [
    nRows > 0 ? t('project.reread.chipRows', { count: nRows }) : (empty ? t('project.reread.chipNothing') : null),
    changed.length > 0 && t('project.reread.chipChanged', { count: changed.length }),
    kept.length > 0 && t('project.reread.chipKept', { count: kept.length }),
    added.length > 0 && t('project.reread.chipAdded', { count: added.length }),
    removed.length > 0 && t('project.reread.chipRemoved', { count: removed.length }),
    reads.length > 0 && t('project.reread.chipReads', { list: reads.join(', ') }),
  ].filter(Boolean).join(' · ');
  const tone = empty ? 'info' : 'warning';
  const linkBtn = 'shrink-0 inline-flex min-h-[32px] items-center gap-1 rounded px-1 font-medium text-accent-2 underline underline-offset-2 hover:no-underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-60';
  const actions = (
    <>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className={linkBtn}
        data-testid="reread-diff-toggle"
      >
        {open ? t('project.reread.hide') : t('project.reread.review')}
      </button>
      <button
        type="button"
        onClick={undo}
        disabled={busy}
        className={linkBtn}
        title={t('project.reread.undoTitle')}
        // its own name („Atšaukti perskaitymą"): a dialog's or a preview's plain „Atšaukti" stays the only one
        aria-label={t('project.reread.undoAria')}
        data-testid="reread-diff-undo"
      >
        <Undo2 className="h-4 w-4" aria-hidden />
        {t('project.reread.undo')}
      </button>
    </>
  );

  if (!open) {
    return (
      <div className="mt-3">
        <Notice
          compact
          tone={tone}
          icon={RefreshCw}
          title={t('project.reread.changeTitle')}
          onDismiss={dismiss}
          dismissLabel={t('project.reread.dismiss')}
          data-testid="reread-diff-banner"
          data-notice-stamp={diff.at || undefined}
        >
          {summary}
          {/* the two buttons on their own row: beside the text they squeezed it to one word a line in the 340 px panel */}
          <span className="mt-1 flex flex-wrap items-center gap-x-3">{actions}</span>
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
          {t('project.reread.changeTitle')}
          {diff.at ? <span className="font-normal text-muted-foreground"> · {when(diff.at)}</span> : null}
        </>
      )}
      action={actions}
      onDismiss={dismiss}
      dismissLabel={t('project.reread.dismiss')}
      data-testid="reread-diff-banner"
      data-notice-stamp={diff.at || undefined}
    >
      {empty && <p>{t('project.reread.nothing')}</p>}

      {rows.length > 0 && (
        <div data-testid="reread-diff-rows">
          <p className="font-medium">{t('project.reread.rowsTitle', { count: nRows })}</p>
          <ul className="mt-0.5 list-disc pl-4 space-y-0.5">
            {rows.slice(0, ROWS_SHOWN).map((line, i) => <li key={`r-${i}`}>{line}</li>)}
          </ul>
          {rows.length > ROWS_SHOWN && (
            <p className="mt-0.5 text-muted-foreground">{t('project.reread.rowsMore', { count: rows.length - ROWS_SHOWN })}</p>
          )}
        </div>
      )}

      {reads.length > 0 && (
        <p><span className="font-medium">{t('project.reread.readsTitle')}</span>: {reads.join(', ')}</p>
      )}

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
