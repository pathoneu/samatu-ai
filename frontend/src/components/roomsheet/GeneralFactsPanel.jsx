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
 *  • the designer's own figures (2026-09-06) — legend totals such as
 *    „Glaistoma dažoma 202 m²", read from the PDF text — each with OUR number
 *    for the same family beside it. A second reading of the same drawing to
 *    compare against; never a value we take.
 */

import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Check } from 'lucide-react';
import { ltNumber } from '@/lib/ledger';
import { isValidAmount, parseLtNumber } from '@/lib/parseLtNumber';
import { authorFigureRows, symbolRows } from '@/lib/roomSheet';
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

const unitText = (u) => (u === 'm2' ? 'm²' : u === 'vnt' ? 'vnt.' : u);

function AuthorFigureRow({ row, projectId, lastOfGroup }) {
  const { t } = useTranslation();
  const unitLabel = unitText(row.unit);
  const rect = row.rect || [0, 0, 1, 1];
  const fact = row.page == null ? null : {
    crop_url: `/api/projects/${encodeURIComponent(projectId)}`
      + `/evidence?page=${row.page}&rect=${rect.map((v) => v.toFixed(4)).join(',')}&dpi=110`,
    source: { page: row.page, rect_pct: row.rect },
  };
  // one figure alone carries our number on its own line; a split family
  // carries it once, under its last part, against the parts' sum
  const showOursHere = row.ours && !row.group;
  const showGroupFooter = row.ours && row.group && lastOfGroup;
  return (
    <li className="grid grid-cols-[104px_minmax(0,1fr)] items-start gap-3 border-t border-border px-4 py-3">
      {fact
        ? <EvidenceCrop fact={fact} alt={row.label} imgClassName="h-[68px] object-cover object-left-top" />
        : <span />}
      <div className="min-w-0">
        <p className="text-[15px] font-semibold">{row.label}</p>
        <p className="font-mono text-[16px]">
          {ltNumber(row.value, 2)} {unitLabel}
          {showOursHere && (
            <span className="ml-3 text-[hsl(var(--ink-2))]">
              {' · '}{t('project.roomSheet.generalAuthorOurs', { value: ltNumber(row.ours.value, 2), unit: unitLabel })}
            </span>
          )}
        </p>
        <p className="mt-0.5 text-[13px] leading-snug text-muted-foreground">
          {row.ours
            ? t('project.roomSheet.generalAuthorWhy', { page: row.page })
            : t('project.roomSheet.generalAuthorNoOurs', { page: row.page })}
        </p>
        {showGroupFooter && (
          <p className="mt-1.5 font-mono text-[15px]">
            {t('project.roomSheet.generalAuthorGroupTotal', {
              count: row.group.size, total: ltNumber(row.group.designerTotal, 2), unit: unitLabel,
            })}
            <span className="ml-3 text-[hsl(var(--ink-2))]">
              {' · '}{t('project.roomSheet.generalAuthorOurs', { value: ltNumber(row.ours.value, 2), unit: unitLabel })}
            </span>
          </p>
        )}
      </div>
    </li>
  );
}

export default function GeneralFactsPanel({ project, busy = false, onSaveSymbol }) {
  const { t } = useTranslation();
  const rows = symbolRows(project);
  const authorRows = authorFigureRows(project);
  const anchor = project?._ceiling_anchor;
  // `total_area_m2` is what every backend writer sets (eksplikacija total,
  // rows' sum, plan labels' sum); the older aliases are kept for saved blobs.
  const anchorValue = Number(anchor?.total_area_m2 ?? anchor?.value ?? anchor?.plotas_m2 ?? anchor?.viso_m2);
  const anchorPage = anchor?.page ?? anchor?.puslapio_nr
    ?? project?._eksplikacija?.eksplikacija_source_page;
  const anchorIsPlanLabels = String(anchor?.label || '').startsWith('plano užrašų');

  if (!rows.length && !authorRows.length && !Number.isFinite(anchorValue)) {
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
              {t(anchorIsPlanLabels
                ? 'project.roomSheet.generalCeilingPlanTitle'
                : 'project.roomSheet.generalCeilingTitle')}
            </p>
            <p className="font-mono text-[16px]">{ltNumber(anchorValue, 2)} m²</p>
            <p className="mt-0.5 text-[13px] leading-snug text-muted-foreground">
              {t(anchorIsPlanLabels
                ? 'project.roomSheet.generalCeilingPlanWhy'
                : 'project.roomSheet.generalCeilingWhy')}
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

      {authorRows.length > 0 && (
        <div>
          <div className="border-t border-border px-4 pt-4 pb-2">
            <h3 className="text-[15px] font-semibold">{t('project.roomSheet.generalAuthorTitle')}</h3>
            <p className="mt-0.5 text-[13px] text-[hsl(var(--ink-2))]">{t('project.roomSheet.generalAuthorIntro')}</p>
          </div>
          <ul className="list-none p-0">
            {authorRows.map((row, i) => {
              const next = authorRows[i + 1];
              const lastOfGroup = !next || next.pairKey !== row.pairKey || next.unit !== row.unit;
              return <AuthorFigureRow key={row.key} row={row} projectId={project.id} lastOfGroup={lastOfGroup} />;
            })}
          </ul>
        </div>
      )}
    </section>
  );
}
