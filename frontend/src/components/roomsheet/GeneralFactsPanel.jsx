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
import { authorFigureRows, bboxToRectPct, symbolRows } from '@/lib/roomSheet';
import {
  KAMPAI_CHOICES, LUBOS_CHOICES, ROTBAND_CHOICES, ROTBAND_DEFAULT_PCT, SIENOS_ANGOS_CHOICES,
  WORK_FAMILIES, isFamilyOn, normalizeScope, withFamily, withKampai, withLubos, withRotband,
  withSienosAngos,
} from '@/lib/scope';
import { planLabelsUnionRect, roomFromPlanLabel, unclaimedPlanLabels } from '@/lib/planLabels';
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

function Choice({ label, options, value, notes, busy, onPick, labelOf }) {
  return (
    <div className="border-t border-border px-4 py-3">
      <p className="text-[15px] font-semibold">{label}</p>
      <div role="radiogroup" aria-label={label} className="mt-2 flex flex-wrap gap-2">
        {options.map((opt) => {
          const active = opt === value;
          return (
            <button
              key={opt}
              type="button"
              role="radio"
              aria-checked={active}
              disabled={busy || active}
              onClick={() => onPick(opt)}
              className={`inline-flex min-h-[44px] items-center rounded-[2px] border px-4 text-[15px] font-semibold ${
                active
                  ? 'border-[hsl(var(--accent-2))] bg-[hsl(var(--accent-2))] text-white'
                  : 'border-border bg-card hover:bg-muted disabled:opacity-60'
              }`}
            >
              {labelOf(opt)}
            </button>
          );
        })}
      </div>
      <p className="mt-1.5 text-[13px] leading-snug text-muted-foreground">{notes(value)}</p>
    </div>
  );
}

/** The share of the painted walls that gets levelling plaster — his number. */
function RotbandShare({ scope, busy, onSaveScope }) {
  const { t } = useTranslation();
  const [draft, setDraft] = useState(scope.rotband_dalis == null ? '' : String(scope.rotband_dalis));
  const apply = () => {
    const raw = draft.trim();
    if (raw === '') { onSaveScope?.(withRotband(scope, 'dalis', null)); return; }
    const num = parseLtNumber(raw);
    if (!Number.isFinite(num) || num < 0 || num > 100) return;
    onSaveScope?.(withRotband(scope, 'dalis', num));
  };
  return (
    <div className="flex flex-wrap items-center gap-3 px-4 pb-3">
      <label className="flex items-center gap-2 text-[14px] text-[hsl(var(--ink-2))]">
        {t('project.roomSheet.scopeRotbandPct')}
        <input
          type="text"
          inputMode="decimal"
          value={draft}
          placeholder={String(ROTBAND_DEFAULT_PCT)}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); apply(); } }}
          className="h-11 w-20 rounded-[2px] border border-border bg-card px-2 text-right font-mono text-[16px]"
        />
        <span>%</span>
      </label>
      <button
        type="button"
        disabled={busy}
        onClick={apply}
        className="inline-flex min-h-[44px] items-center rounded-[2px] border border-border bg-card px-3 text-[14px] font-semibold hover:bg-muted disabled:opacity-50"
      >
        {t('project.roomSheet.scopeRotbandApply')}
      </button>
    </div>
  );
}

/** Plan labels no room claimed — each one becomes a room with one click. */
function UnclaimedLabels({ project, busy, onAddRoom }) {
  const { t } = useTranslation();
  const labels = unclaimedPlanLabels(project);
  if (!labels.length || !onAddRoom) return null;
  return (
    <div>
      <div className="border-t border-border px-4 pt-4 pb-1">
        <h3 className="text-[15px] font-semibold">{t('project.roomSheet.unclaimedTitle')}</h3>
        <p className="mt-0.5 text-[13px] text-[hsl(var(--ink-2))]">{t('project.roomSheet.unclaimedIntro')}</p>
      </div>
      <ul className="list-none p-0">
        {labels.map((u) => {
          const rect = bboxToRectPct(u.bbox, u.page_width, u.page_height, 0.05);
          const fact = u.page == null ? null : {
            crop_url: `/api/projects/${encodeURIComponent(project.id)}`
              + `/evidence?page=${u.page}&rect=${(rect || [0, 0, 1, 1]).map((v) => v.toFixed(4)).join(',')}&dpi=110`,
            source: { page: u.page, rect_pct: rect },
          };
          return (
            <li key={`${u.page}-${u.value_m2}`} className="grid grid-cols-[104px_minmax(0,1fr)_auto] items-start gap-3 border-t border-border px-4 py-3">
              {fact ? <EvidenceCrop fact={fact} alt={`${ltNumber(u.value_m2, 2)} m²`} imgClassName="h-[68px] object-cover object-center" /> : <span />}
              <div className="min-w-0">
                <p className="font-mono text-[16px]">{ltNumber(u.value_m2, 2)} m²</p>
                <p className="mt-0.5 text-[13px] leading-snug text-muted-foreground">
                  {t('project.roomSheet.unclaimedWhy', { page: u.page })}
                </p>
              </div>
              <button
                type="button"
                disabled={busy}
                onClick={() => onAddRoom(roomFromPlanLabel(project, u))}
                className="inline-flex min-h-[44px] items-center rounded-[2px] border border-[hsl(var(--accent-2))] bg-[hsl(var(--accent-2))] px-3 text-[14px] font-semibold text-white disabled:opacity-50"
              >
                {t('project.roomSheet.unclaimedAdd')}
              </button>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

/** „Ką skaičiuoti" for the whole job — ceilings, wall area, work areas. */
function ScopeSection({ project, busy, onSaveScope }) {
  const { t } = useTranslation();
  const scope = normalizeScope(project?._apimtis);
  return (
    <div>
      <div className="border-t border-border px-4 pt-4 pb-1">
        <h3 className="text-[15px] font-semibold">{t('project.roomSheet.scopeTitle')}</h3>
        <p className="mt-0.5 text-[13px] text-[hsl(var(--ink-2))]">{t('project.roomSheet.scopeIntro')}</p>
      </div>
      <Choice
        label={t('project.roomSheet.scopeLubosLabel')}
        options={LUBOS_CHOICES}
        value={scope.lubos}
        busy={busy}
        labelOf={(o) => t(`project.roomSheet.scopeLubos.${o}`)}
        notes={(v) => t(`project.roomSheet.scopeLubosNote.${v}`)}
        onPick={(o) => onSaveScope?.(withLubos(scope, o))}
      />
      <Choice
        label={t('project.roomSheet.scopeSienosLabel')}
        options={SIENOS_ANGOS_CHOICES}
        value={scope.sienos_angos}
        busy={busy}
        labelOf={(o) => t(`project.roomSheet.scopeSienos.${o}`)}
        notes={(v) => t(`project.roomSheet.scopeSienosNote.${v}`)}
        onPick={(o) => onSaveScope?.(withSienosAngos(scope, o))}
      />
      <Choice
        label={t('project.roomSheet.scopeRotbandLabel')}
        options={ROTBAND_CHOICES}
        value={scope.rotband}
        busy={busy}
        labelOf={(o) => t(`project.roomSheet.scopeRotband.${o}`)}
        notes={(v) => t(`project.roomSheet.scopeRotbandNote.${v}`)}
        onPick={(o) => onSaveScope?.(withRotband(scope, o))}
      />
      {scope.rotband === 'dalis' && (
        <RotbandShare scope={scope} busy={busy} onSaveScope={onSaveScope} />
      )}
      <Choice
        label={t('project.roomSheet.scopeKampaiLabel')}
        options={KAMPAI_CHOICES}
        value={scope.kampai}
        busy={busy}
        labelOf={(o) => t(`project.roomSheet.scopeKampai.${o}`)}
        notes={(v) => t(`project.roomSheet.scopeKampaiNote.${v}`)}
        onPick={(o) => onSaveScope?.(withKampai(scope, o))}
      />
      <div className="border-t border-border px-4 py-3">
        <p className="text-[15px] font-semibold">{t('project.roomSheet.scopeFamiliesLabel')}</p>
        <div className="mt-2 flex flex-wrap gap-2">
          {WORK_FAMILIES.map((fam) => {
            const on = isFamilyOn(scope, fam);
            return (
              <button
                key={fam}
                type="button"
                role="checkbox"
                aria-checked={on}
                disabled={busy}
                onClick={() => onSaveScope?.(withFamily(scope, fam, !on))}
                className={`inline-flex min-h-[44px] items-center gap-2 rounded-[2px] border px-3 text-[15px] ${
                  on ? 'border-[hsl(var(--accent-2))] bg-[hsl(var(--accent-2))]/10 font-semibold' : 'border-border bg-card text-muted-foreground'
                }`}
              >
                <span aria-hidden className={`inline-flex h-[18px] w-[18px] items-center justify-center rounded-sm border text-[12px] ${
                  on ? 'border-[hsl(var(--accent-2))] bg-[hsl(var(--accent-2))] text-white' : 'border-border'}`}>
                  {on ? '✓' : ''}
                </span>
                {t(`newProject.q.family.${fam}`)}
              </button>
            );
          })}
        </div>
        <p className="mt-1.5 text-[13px] leading-snug text-muted-foreground">{t('project.roomSheet.scopeFamiliesNote')}</p>
      </div>
    </div>
  );
}

export default function GeneralFactsPanel({ project, busy = false, onSaveSymbol, onSaveScope, onAddRoom }) {
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
      <section aria-labelledby="general-facts">
        <p className="px-4 py-6 text-[15px] text-muted-foreground">
          {t('project.roomSheet.generalNone')}
        </p>
        {onSaveScope && <ScopeSection project={project} busy={busy} onSaveScope={onSaveScope} />}
      </section>
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
              fact={(() => {
                // the plan itself when the labels say where it is — a whole
                // sheet at thumbnail size shows nothing but white margins
                const rect = anchorIsPlanLabels ? planLabelsUnionRect(project, anchorPage) : null;
                const r = (rect || [0, 0, 1, 1]).map((v) => v.toFixed(4)).join(',');
                return {
                  crop_url: `/api/projects/${encodeURIComponent(project.id)}`
                    + `/evidence?page=${anchorPage}&rect=${r}&dpi=${rect ? 110 : 90}`,
                  source: { page: anchorPage, rect_pct: rect },
                };
              })()}
              alt={t(anchorIsPlanLabels
                ? 'project.roomSheet.generalCeilingPlanTitle'
                : 'project.roomSheet.generalCeilingTitle')}
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

      <UnclaimedLabels project={project} busy={busy} onAddRoom={onAddRoom} />

      {onSaveScope && <ScopeSection project={project} busy={busy} onSaveScope={onSaveScope} />}

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
