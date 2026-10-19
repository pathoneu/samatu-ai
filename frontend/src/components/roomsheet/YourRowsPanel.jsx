/**
 * YourRowsPanel — „Jūsų eilutės" on the room sheet's last page.
 *
 * The rows of HIS template the drawing cannot answer (backend `render_samata`,
 * `_pildymas === 'tuscia'`): rubbish removal, a rental, a walk-through item.
 * They are listed blank, in his sections, each with one input. A typed
 * quantity becomes a hand-added row in `darbu_sarasas` carrying the family key
 * (`lib/samataTemplate.typeQuantity`), so it shows up filled in his layout, in
 * the Pathon table and in both exports. A row left blank stays blank — never a
 * zero. Renders nothing at all when the account has no template.
 */

import { useEffect, useMemo, useState } from 'react';
import { useTranslation } from '@/i18n/react';
import { toast } from 'sonner';
import { Check, Loader2 } from 'lucide-react';
import { parseLtNumber, isValidAmount } from '@/lib/parseLtNumber';
import { fetchSamataTemplates, renderSamata, roomsForRender } from '@/lib/samataTemplateApi';
import {
  EXTRA_SECTION, FILL, darbaiFingerprint, groupBySection, typeQuantity,
} from '@/lib/samataTemplate';

function BlankRow({ row, onSave }) {
  const { t } = useTranslation();
  const [draft, setDraft] = useState('');
  const [saving, setSaving] = useState(false);
  const save = async () => {
    const raw = draft.trim();
    if (raw === '') return;
    const num = parseLtNumber(raw);
    if (!isValidAmount(num)) { toast.error(t('project.samataTemplate.badNumber')); return; }
    setSaving(true);
    try { await onSave(row, num); setDraft(''); } finally { setSaving(false); }
  };
  return (
    <li className="flex flex-wrap items-center gap-3 border-t border-border px-4 py-2.5">
      <div className="min-w-[200px] flex-1">
        <p className="text-[16px]">{row.aprasymas}</p>
        {row._pastaba && <p className="text-[13px] text-muted-foreground">{row._pastaba}</p>}
      </div>
      <label className="flex items-center gap-2 text-[14px] text-ink-2">
        <input
          type="text"
          inputMode="decimal"
          value={draft}
          placeholder={t('project.samataTemplate.typePlaceholder')}
          aria-label={t('project.samataTemplate.typeAria', { row: row.aprasymas })}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); save(); } }}
          className="h-11 w-28 rounded-[2px] border border-border bg-card px-2 text-right font-mono text-[16px]"
        />
        <span className="w-10">{row.mato_vnt || ''}</span>
      </label>
      <button
        type="button"
        onClick={save}
        disabled={saving || draft.trim() === ''}
        className="inline-flex min-h-[44px] items-center gap-1.5 rounded-[2px] border border-accent-2 bg-accent-2 px-3 text-[14px] font-semibold text-white disabled:opacity-50"
      >
        {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Check className="h-4 w-4" />}
        {t('project.roomSheet.save')}
      </button>
    </li>
  );
}

export default function YourRowsPanel({ project, onProjectChange }) {
  const { t } = useTranslation();
  const [hasTemplate, setHasTemplate] = useState(null);   // null = not known yet
  const [rows, setRows] = useState(null);
  const fingerprint = darbaiFingerprint(project?.darbu_sarasas);
  const projectId = project?.id;

  useEffect(() => {
    let alive = true;
    fetchSamataTemplates()
      .then((list) => { if (alive) setHasTemplate(list.length > 0); })
      .catch(() => { if (alive) setHasTemplate(false); });
    return () => { alive = false; };
  }, []);

  useEffect(() => {
    if (!hasTemplate || !projectId) return undefined;
    const ctl = new AbortController();
    renderSamata(projectId, {
      rows: project?.darbu_sarasas || [], rooms: roomsForRender(project), signal: ctl.signal,
    })
      .then((body) => { if (!ctl.signal.aborted) setRows(body.eilutes || []); })
      .catch(() => { if (!ctl.signal.aborted) setRows([]); });
    return () => ctl.abort();
  // eslint-disable-next-line react-hooks/exhaustive-deps -- fingerprint stands for the rows
  }, [hasTemplate, projectId, fingerprint]);

  const blankGroups = useMemo(() => groupBySection(
    (rows || []).filter((r) => r._sablonas && r._pildymas === FILL.EMPTY),
  ), [rows]);
  const blankCount = blankGroups.reduce((n, g) => n + g.rows.length, 0);

  if (!hasTemplate) return null;

  const save = (row, num) => {
    const next = typeQuantity(project.darbu_sarasas || [], row, num, { otherLabel: EXTRA_SECTION });
    onProjectChange({ ...project, darbu_sarasas: next });
    toast.success(t('project.roomSheet.yourRowsSaved', { row: row.aprasymas }));
  };

  return (
    <section aria-labelledby="your-rows">
      <div className="px-4 pt-4 pb-3">
        <h2 id="your-rows" className="text-[17px] font-semibold">
          {t('project.roomSheet.yourRowsTitle')}
          {rows && blankCount > 0 && (
            <span className="ml-2 text-[14px] font-normal text-muted-foreground">
              {t('project.roomSheet.yourRowsCount', { count: blankCount })}
            </span>
          )}
        </h2>
        <p className="mt-1 text-[15px] text-ink-2">{t('project.roomSheet.yourRowsIntro')}</p>
      </div>
      {rows == null ? (
        <p className="flex items-center gap-2 border-t border-border px-4 py-3 text-[14px] text-muted-foreground">
          <Loader2 className="h-4 w-4 animate-spin" />
          {t('project.roomSheet.yourRowsLoading')}
        </p>
      ) : blankCount === 0 ? (
        <p className="border-t border-border px-4 py-3 text-[15px] text-muted-foreground">
          {t('project.roomSheet.yourRowsNone')}
        </p>
      ) : blankGroups.map((g) => (
        <div key={g.label}>
          <p className="border-t border-border bg-muted/40 px-4 py-1.5 text-xs font-semibold uppercase tracking-wide">
            {g.label}
          </p>
          <ul>
            {g.rows.map((row) => <BlankRow key={row.id} row={row} onSave={save} />)}
          </ul>
        </div>
      ))}
    </section>
  );
}
