/**
 * GeneralFactsPanel — „Bendri dalykai", the short second stage after the rooms.
 *
 * Two things live here in v1:
 *  • the eksplikacijos „Iš viso", when the project has a `_ceiling_anchor` —
 *    worth its own stop because the ceiling lines are billed off THAT number
 *    rather than the sum of the rooms, which is exactly the sort of thing a
 *    room-by-room walk can never surface. No anchor ⇒ the row is absent, not
 *    faked.
 *  • the symbol counts, each with the sheet it was counted on and a field to
 *    correct it. The corrected count rides `detected_symbols_summary` into the
 *    recompute context — the same channel the builder already reads it from —
 *    so this is a real edit, not a display-only number.
 */

import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Check } from 'lucide-react';
import { ltNumber } from '@/lib/ledger';
import { isValidAmount, parseLtNumber } from '@/lib/parseLtNumber';
import { symbolRows } from '@/lib/roomSheet';
import EvidenceCrop from './EvidenceCrop';

function SymbolRow({ row, projectId, busy, onSave }) {
  const { t } = useTranslation();
  const [draft, setDraft] = useState(String(row.value));
  const label = t(`project.roomSheet.sym_${row.key}`, { defaultValue: row.key });

  const commit = () => {
    const num = parseLtNumber(draft);
    if (!isValidAmount(num)) return;
    if (Math.round(num) === row.value) return;
    onSave?.(row.key, Math.round(num));
  };

  const fact = row.page == null ? null : {
    crop_url: `/api/projects/${encodeURIComponent(projectId)}`
      + `/evidence?page=${row.page}&rect=0.0000,0.0000,1.0000,1.0000&dpi=90`,
    source: { page: row.page, rect_pct: null },
  };

  return (
    <li className="grid grid-cols-[104px_minmax(0,1fr)_auto] items-start gap-3 border-t border-border px-4 py-3">
      {fact
        ? <EvidenceCrop fact={fact} alt={label} imgClassName="h-[68px] object-cover object-top" />
        : <span className="text-[13px] text-muted-foreground">{t('project.roomSheet.symNoPage')}</span>}
      <div className="min-w-0">
        <p className="text-[15px] font-semibold">{label}</p>
        <p className="font-mono text-[16px]">{t('project.roomSheet.symCount', { count: row.value })}</p>
        <p className="mt-0.5 text-[13px] leading-snug text-muted-foreground">
          {t('project.roomSheet.generalSymbolsWhy')}
        </p>
      </div>
      <div className="flex items-center gap-2">
        <input
          value={draft}
          inputMode="numeric"
          aria-label={label}
          onFocus={(e) => e.target.select()}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); commit(); } }}
          className="h-11 w-20 rounded-[2px] border border-border bg-card px-2 text-right font-mono text-[16px]"
        />
        <button
          type="button"
          disabled={busy}
          onClick={commit}
          className="inline-flex min-h-[44px] items-center rounded-[2px] border border-border bg-card px-3 text-[14px] font-semibold hover:bg-muted disabled:opacity-50"
        >
          {t('project.roomSheet.save')}
        </button>
      </div>
    </li>
  );
}

export default function GeneralFactsPanel({ project, busy = false, onSaveSymbol }) {
  const { t } = useTranslation();
  const rows = symbolRows(project);
  const anchor = project?._ceiling_anchor;
  const anchorValue = Number(anchor?.value ?? anchor?.plotas_m2 ?? anchor?.viso_m2);
  const anchorPage = anchor?.page ?? anchor?.puslapio_nr
    ?? project?._eksplikacija?.eksplikacija_source_page;

  if (!rows.length && !Number.isFinite(anchorValue)) {
    return (
      <p className="px-4 py-6 text-[15px] text-muted-foreground">
        {t('project.roomSheet.generalNone')}
      </p>
    );
  }

  return (
    <section aria-labelledby="general-facts">
      <div className="px-4 py-3">
        <h2 id="general-facts" className="text-[17px] font-semibold">
          {t('project.roomSheet.generalTitle')}
        </h2>
        <p className="mt-0.5 text-[14px] text-[hsl(var(--ink-2))]">
          {t('project.roomSheet.generalIntro')}
        </p>
      </div>

      {Number.isFinite(anchorValue) && (
        <div className="grid grid-cols-[104px_minmax(0,1fr)_auto] items-start gap-3 border-t border-border px-4 py-3">
          {anchorPage != null ? (
            <EvidenceCrop
              fact={{
                crop_url: `/api/projects/${encodeURIComponent(project.id)}`
                  + `/evidence?page=${anchorPage}&rect=0.0000,0.0000,1.0000,1.0000&dpi=90`,
                source: { page: anchorPage, rect_pct: null },
              }}
              alt={t('project.roomSheet.generalCeilingTitle')}
              imgClassName="h-[68px] object-cover object-top"
            />
          ) : <span />}
          <div className="min-w-0">
            <p className="text-[15px] font-semibold">
              {t('project.roomSheet.generalCeilingTitle')}
            </p>
            <p className="font-mono text-[16px]">{ltNumber(anchorValue, 2)} m²</p>
            <p className="mt-0.5 text-[13px] leading-snug text-muted-foreground">
              {t('project.roomSheet.generalCeilingWhy')}
            </p>
          </div>
          <Check className="mt-1 h-5 w-5 text-[hsl(var(--accent-2))]" aria-hidden="true" />
        </div>
      )}

      <ul className="list-none p-0">
        {rows.map((row) => (
          <SymbolRow
            key={row.key}
            row={row}
            projectId={project.id}
            busy={busy}
            onSave={onSaveSymbol}
          />
        ))}
      </ul>
    </section>
  );
}
