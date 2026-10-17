/**
 * FactRow — one thing the program read, with the pixels it read it from.
 *
 * Layout is the founder's sheet: crop | value + sentence | two verbs. The two
 * verbs are the whole point — „Teisinga" costs a click, „Pataisyti" opens the
 * editor the fact's own `editable.kind` calls for. No confidence dot: an
 * `assumed` or `missing` fact is an amber row with a field already showing and
 * the reason written out, which is the thing a dot never managed to say.
 *
 * Every stored sentence goes through `cleanUserText` on the way to the screen —
 * nothing stored is trusted in a renderer (the 2026-09-04 trust guard).
 */

import { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Check, MapPin, Minus, MousePointerClick, Pencil, Plus, Scissors } from 'lucide-react';
import { ltNumber } from '@/lib/ledger';
import { isValidAmount, parseLtNumber } from '@/lib/parseLtNumber';
import { cleanUserText } from '@/lib/userText';
import { factNeedsInput, factTone, isWholeSheet, prefillValue, FACT_LABEL_KEY, STANDARD_OPENINGS } from '@/lib/roomSheet';
import EvidenceCrop from './EvidenceCrop';


const PASKIRTIS = [
  'gyvenamoji', 'miegamoji', 'virtuve', 'vonia', 'wc', 'koridorius',
  'drabuzine', 'skalbykla', 'tamburas', 'garazas', 'sandeliukas',
  'katiline', 'laiptine',
];

// `grindu_danga` values the engine knows (universal_rules.FLOOR_COVERINGS) → their button labels.
const FLOOR_COVERINGS = [
  ['plyteles', 'floorTiles'], ['minksta', 'floorSoft'], ['be_dangos', 'floorNone'],
];

const BTN = 'inline-flex min-h-[44px] items-center justify-center gap-1.5 '
  + 'rounded-[2px] border px-3 text-[14px] font-semibold transition-colors '
  + 'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring';

function mm(v) {
  const n = Number(v);
  return Number.isFinite(n) ? ltNumber(n / 1000, 2) : '—';
}

function SizeEditor({ detail, busy, onSave, t }) {
  // Centimetres on screen — the unit a contractor says door sizes in.
  const [w, setW] = useState(() => (Number(detail?.plotis_mm) > 0 ? String(Math.round(detail.plotis_mm / 10)) : ''));
  const [h, setH] = useState(() => (Number(detail?.aukstis_mm) > 0 ? String(Math.round(detail.aukstis_mm / 10)) : ''));
  const commit = () => {
    const pw = parseLtNumber(w);
    const ph = parseLtNumber(h);
    if (!(pw > 0) || !(ph > 0)) return;
    onSave?.(detail, { plotis_mm: pw * 10, aukstis_mm: ph * 10 });
  };
  const box = 'h-11 w-16 rounded-[2px] border border-[hsl(var(--conf-med))] bg-card px-2 text-right font-mono text-[15px]';
  return (
    <span className="flex flex-wrap items-center gap-1.5 font-sans text-[13px] text-[hsl(var(--ink-2))]">
      <label className="sr-only" htmlFor={`w-${detail.tipas}-${detail.plotis_mm}`}>{t('project.roomSheet.sizeWidth')}</label>
      <input id={`w-${detail.tipas}-${detail.plotis_mm}`} className={box} inputMode="numeric" value={w}
        onChange={(e) => setW(e.target.value)} onFocus={(e) => e.target.select()}
        onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); e.stopPropagation(); commit(); } }} />
      <span>×</span>
      <label className="sr-only" htmlFor={`h-${detail.tipas}-${detail.plotis_mm}`}>{t('project.roomSheet.sizeHeight')}</label>
      <input id={`h-${detail.tipas}-${detail.plotis_mm}`} className={box} inputMode="numeric" value={h}
        onChange={(e) => setH(e.target.value)} onFocus={(e) => e.target.select()}
        onKeyDown={(e) => { if (e.key === 'Enter') { e.preventDefault(); e.stopPropagation(); commit(); } }} />
      <span>{t('project.roomSheet.sizeCm')}</span>
      <button type="button" disabled={busy} onClick={commit}
        className={`${BTN} min-h-[36px] border-border bg-card px-2 text-[13px] hover:bg-muted disabled:opacity-50`}>
        {t('project.roomSheet.sizeSave')}
      </button>
    </span>
  );
}

export default function FactRow({
  fact, room, busy = false, verified = false,
  onAccept, onSaveNumber, onSaveChoice, onAdjustOpening, onSaveOpeningSize, onAddOpening, onShowOnDrawing = null,
  onPickOutline = null, onSplitSpace = null,
}) {
  const { t } = useTranslation();
  const attention = factTone(fact?.status) === 'attention';
  const [editing, setEditing] = useState(() => factNeedsInput(fact));
  const [draft, setDraft] = useState(() => prefillValue(fact));
  const inputRef = useRef(null);

  useEffect(() => {
    setEditing(factNeedsInput(fact));
    setDraft(prefillValue(fact));
  }, [fact]);

  useEffect(() => {
    // preventScroll: a blank fact opens with its field focused, and a focus that
    // scrolls yanked the whole sheet down past the drawing on every such room.
    if (editing && fact?.editable?.kind === 'number') inputRef.current?.focus({ preventScroll: true });
  }, [editing, fact?.editable?.kind]);

  const label = t(`project.roomSheet.${FACT_LABEL_KEY[fact?.key] || 'factPlotas'}`);
  const sentence = cleanUserText(fact?.sentence || '');
  // A default is a question: the accept verb says he is keeping OUR number.
  const assumed = fact?.status === 'assumed';
  const kind = fact?.editable?.kind;
  const field = fact?.editable?.field;

  const value = fact?.unit
    ? `${ltNumber(fact.value, fact.key === 'angos' || fact.key === 'pertvaros' ? 0 : 2)} ${fact.unit}`
    : String(fact?.value ?? '—');

  const commitNumber = () => {
    const num = parseLtNumber(draft);
    if (!isValidAmount(num)) return;
    onSaveNumber?.(field, num);
    setEditing(false);
  };
  // The other rooms that ask the same question (room_facts `same_question`): one answer for all.
  const alsoRooms = Array.isArray(fact?.same_question) ? fact.same_question.map(String) : [];
  const commitNumberForAll = () => {
    const num = parseLtNumber(draft);
    if (!isValidAmount(num)) return;
    onSaveNumber?.(field, num, alsoRooms);
    setEditing(false);
  };

  return (
    <div
      className={`grid grid-cols-[104px_minmax(0,1fr)] gap-3 border-t border-border px-4 py-3
        sm:grid-cols-[104px_minmax(0,1fr)_auto]
        ${attention ? 'border-l-[3px] border-l-[hsl(var(--conf-med))] bg-[hsl(var(--conf-med)/0.08)]' : ''}`}
    >
      <EvidenceCrop
        fact={fact}
        alt={`${label} — ${t('project.roomSheet.sourcePage', { page: fact?.source?.page })}`}
        imgClassName="h-[68px] object-cover object-top"
      />

      <div className="min-w-0">
        <p className="flex flex-wrap items-center gap-2 text-[13px] font-semibold uppercase tracking-wide text-muted-foreground">
          {label}
          {/* His own value — typed, chosen, accepted or drawn by him (room_facts `_is_yours`). */}
          {fact?.yours && (
            <span
              className="rounded-[2px] border border-[hsl(var(--accent-2)/0.5)] bg-[hsl(var(--accent-2)/0.08)] px-1.5 py-px text-[11px] font-semibold normal-case tracking-normal text-[hsl(var(--accent-2))]"
              data-testid="fact-yours"
            >
              {t('project.roomSheet.yoursBadge')}
            </span>
          )}
        </p>
        <p className={`font-mono text-[16px] font-semibold leading-snug
          ${attention ? 'text-[hsl(var(--conf-med))]' : 'text-foreground'}`}
        >
          {value}
        </p>
        {sentence && (
          <p className="mt-0.5 text-[14px] leading-snug text-[hsl(var(--ink-2))]">{sentence}</p>
        )}
        {/* The sharp drawing is one click away from every number: the pane on the
            left jumps to the sheet and the place this fact was read from. */}
        {onShowOnDrawing && fact?.source?.page != null && (
          <button
            type="button"
            onClick={onShowOnDrawing}
            className="mt-1 inline-flex items-center gap-1 text-[13px] font-semibold text-[hsl(var(--accent-2))] underline-offset-2 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
          >
            <MapPin className="h-3.5 w-3.5" aria-hidden="true" />
            {t('project.roomSheet.showOnDrawing')}
            <span className="font-mono font-medium text-muted-foreground">
              · {t('project.roomSheet.sourcePage', { page: fact.source.page })}
            </span>
          </button>
        )}
        {/* A room without an outline of its own: one click inside it on the drawing gives it one,
            and its walls are read again — the fix for the reason the sentence above gives. */}
        {/* …and a room that shares its space with another (no wall between them): one line he draws
            gives both their own outlines — a click inside would only find the shared space again. */}
        {/* …also when the boundary is the PROGRAM's own (geometry lane, 2026-09-23): he may draw it elsewhere */}
        {onSplitSpace && fact?.key === 'perimetras' && (!fact?.outline?.polygon_pct || fact?.outline?.riba === 'programos')
          && (fact?.outline?.open_space?.nariai || []).length === 2 && (
          <button
            type="button"
            disabled={busy}
            onClick={onSplitSpace}
            className={`${BTN} mt-2 flex w-fit border-[hsl(var(--accent-2))] bg-[hsl(var(--accent-2))] text-white disabled:opacity-50`}
            data-testid="fact-split-space"
          >
            <Scissors className="h-4 w-4" aria-hidden="true" />
            {t('project.roomSheet.splitFromFact')}
          </button>
        )}
        {onPickOutline && fact?.key === 'perimetras' && !fact?.outline?.polygon_pct && !fact?.outline?.open_space && (
          <button
            type="button"
            disabled={busy}
            onClick={onPickOutline}
            className={`${BTN} mt-2 flex w-fit border-[hsl(var(--accent-2))] bg-[hsl(var(--accent-2))] text-white disabled:opacity-50`}
            data-testid="fact-pick-outline"
          >
            <MousePointerClick className="h-4 w-4" aria-hidden="true" />
            {t('project.roomSheet.outlinePickFromFact')}
          </button>
        )}
        {isWholeSheet(fact) && (
          <p className="mt-0.5 text-[13px] leading-snug text-muted-foreground">
            {t('project.roomSheet.wholeSheetWhy')}
          </p>
        )}

        {/* Openings: the count and the sizes, because the plan cannot mark them. */}
        {fact?.key === 'angos' && Array.isArray(fact.details) && fact.details.length > 0 && (
          <ul className="mt-2 space-y-1">
            {fact.details.map((d, i) => (
              <li
                key={`${d.tipas}-${d.plotis_mm}-${d.aukstis_mm}-${i}`}
                className="flex flex-wrap items-center gap-2 font-mono text-[14px]"
              >
                <span>
                  {t('project.roomSheet.openingRow', {
                    count: d.kiekis,
                    name: d.pavadinimas || d.tipas,
                    size: t('project.roomSheet.openingSize', {
                      width: mm(d.plotis_mm), height: mm(d.aukstis_mm),
                    }),
                  })}
                </span>
                <span className="font-sans text-[13px] text-muted-foreground">
                  {d.is_zinyno
                    ? t('project.roomSheet.openingsFromSchedule')
                    : d._dydis_user
                      ? t('project.roomSheet.openingsSizeYours')
                      : d.be_angos
                        ? t('project.roomSheet.openingNoWallOpening')
                        : d.praejimas
                          ? t('project.roomSheet.openingPassage')
                          : d.tipas_pagal_brezini
                            ? t('project.roomSheet.openingKindByDrawing')
                            : d.pridėta_pagal_sienas
                              ? (d.nupiesta === 'langas'
                                ? t('project.roomSheet.openingAddedDrawnWindow')
                                : d.nupiesta === 'durys'
                                  ? t('project.roomSheet.openingAddedDrawnDoor')
                                  : t('project.roomSheet.openingAddedFromWalls'))
                              : d.plotis_pagal_sienas
                              ? t('project.roomSheet.openingWidthFromWalls')
                              : t('project.roomSheet.openingsAssumed')}
                </span>
                {editing && kind === 'count' && !d.is_zinyno && (
                  <SizeEditor detail={d} busy={busy} onSave={onSaveOpeningSize} t={t} />
                )}
                {editing && kind === 'count' && (
                  <span className="flex items-center gap-1">
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => onAdjustOpening?.(d, -1)}
                      aria-label={t('project.roomSheet.countMinus')}
                      className="inline-flex h-11 w-11 items-center justify-center rounded-[2px] border border-border bg-card disabled:opacity-50"
                    >
                      <Minus className="h-4 w-4" />
                    </button>
                    <button
                      type="button"
                      disabled={busy}
                      onClick={() => onAdjustOpening?.(d, 1)}
                      aria-label={t('project.roomSheet.countPlus')}
                      className="inline-flex h-11 w-11 items-center justify-center rounded-[2px] border border-border bg-card disabled:opacity-50"
                    >
                      <Plus className="h-4 w-4" />
                    </button>
                  </span>
                )}
              </li>
            ))}
          </ul>
        )}

        {/* Adding an opening (2026-09-20): the stepper moves only rows that exist, so a room the
            reader found no door in could not be given one. First what the WALLS show — one click
            each — then a plain door or window of the standard size. */}
        {fact?.key === 'angos' && editing && kind === 'count' && (
          <div className="mt-2" data-testid="opening-add">
            {Array.isArray(fact.suggestions) && fact.suggestions.length > 0 && (
              <div className="mb-2 flex flex-wrap gap-2">
                {fact.suggestions.map((sug, i) => (
                  <button
                    key={`${sug.tipas}-${sug.i}-${sug.plotis_mm}-${i}`}
                    type="button"
                    disabled={busy}
                    onClick={() => onAddOpening?.(sug)}
                    className={`${BTN} border-[hsl(var(--accent-2))] bg-[hsl(var(--accent-2))] text-left text-white disabled:opacity-50`}
                  >
                    <Plus className="h-4 w-4 shrink-0" aria-hidden="true" />
                    {cleanUserText(sug.label || '')}
                  </button>
                ))}
              </div>
            )}
            <div className="flex flex-wrap gap-2">
              {[['duris', 'addDoor'], ['langas', 'addWindow']].map(([tipas, key]) => (
                <button
                  key={tipas}
                  type="button"
                  disabled={busy}
                  onClick={() => onAddOpening?.(STANDARD_OPENINGS[tipas])}
                  className={`${BTN} border-border bg-card hover:bg-muted disabled:opacity-50`}
                >
                  <Plus className="h-4 w-4" aria-hidden="true" />
                  {t(`project.roomSheet.${key}`)}
                </button>
              ))}
            </div>
            <p className="mt-1 text-[13px] leading-snug text-muted-foreground">
              {t('project.roomSheet.openingsAddConsequence')}
            </p>
          </div>
        )}

        {/* Number editor — aukštis, plotas, perimetras, pertvaros. */}
        {editing && kind === 'number' && (
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <label className="text-[14px] text-[hsl(var(--ink-2))]" htmlFor={`f-${fact.key}`}>
              {t(`project.roomSheet.edit${fact.key === 'aukstis' ? 'Aukstis'
                : fact.key === 'plotas' ? 'Plotas' : fact.key === 'pertvaros' ? 'Pertvaros' : 'Perimetras'}`)}
            </label>
            <input
              id={`f-${fact.key}`}
              ref={inputRef}
              value={draft}
              inputMode="decimal"
              onFocus={(e) => e.target.select()}
              onChange={(e) => setDraft(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') { e.preventDefault(); e.stopPropagation(); commitNumber(); }
                if (e.key === 'Escape') setEditing(false);
              }}
              className="h-11 w-28 rounded-[2px] border border-[hsl(var(--conf-med))] bg-card px-2 text-right font-mono text-[16px]"
            />
            <button
              type="button"
              disabled={busy}
              onClick={commitNumber}
              className={`${BTN} border-[hsl(var(--accent-2))] bg-[hsl(var(--accent-2))] text-white disabled:opacity-50`}
            >
              {busy ? t('project.roomSheet.saving') : t('project.roomSheet.save')}
            </button>
            {alsoRooms.length > 0 && (
              <button
                type="button"
                disabled={busy}
                onClick={commitNumberForAll}
                className={`${BTN} border-[hsl(var(--accent-2))] bg-card text-[hsl(var(--accent-2))] hover:bg-[hsl(var(--accent-2)/0.08)] disabled:opacity-50`}
                data-testid="save-for-all"
              >
                {t('project.roomSheet.saveForAll', { count: alsoRooms.length + 1 })}
              </button>
            )}
            {/* A blank with a number to accept: the sentence said where the number
                comes from — one click takes it, typing another overrides it. */}
            {fact.value == null && isValidAmount(Number(fact.suggestion?.value)) && (
              <button
                type="button"
                disabled={busy}
                onClick={() => { onSaveNumber?.(field, Number(fact.suggestion.value)); setEditing(false); }}
                className={`${BTN} border-border bg-card hover:bg-muted disabled:opacity-50`}
              >
                {cleanUserText(fact.suggestion.label || '')}
              </button>
            )}
          </div>
        )}

        {/* Choice editor — sienos (dažomos / nedažomos) and patalpos paskirtis,
            each with the consequence written next to it, not hidden in a tooltip. */}
        {editing && kind === 'choice' && field === 'walls_paint_override' && (
          <div className="mt-2">
            <div className="flex flex-wrap gap-2">
              {[['1', 'wallsPainted'], ['0', 'wallsRaw']].map(([v, key]) => (
                <button
                  key={v}
                  type="button"
                  disabled={busy}
                  onClick={() => { onSaveChoice?.(field, Number(v)); setEditing(false); }}
                  className={`${BTN} border-border bg-card hover:bg-muted disabled:opacity-50`}
                >
                  {t(`project.roomSheet.${key}`)}
                </button>
              ))}
            </div>
            <p className="mt-1 text-[13px] leading-snug text-muted-foreground">
              {t('project.roomSheet.wallsConsequence')}
            </p>
          </div>
        )}

        {/* The floor covering, chosen directly (2026-09-20). It used to be answered by
            changing the room's PURPOSE, which moves its walls and ceiling too. */}
        {editing && kind === 'choice' && field === 'grindu_danga' && (
          <div className="mt-2">
            <div className="flex flex-wrap gap-2">
              {FLOOR_COVERINGS.map(([v, key]) => (
                <button
                  key={v}
                  type="button"
                  disabled={busy}
                  aria-pressed={room?.grindu_danga === v}
                  onClick={() => { onSaveChoice?.(field, v); setEditing(false); }}
                  className={`${BTN} ${room?.grindu_danga === v
                    ? 'border-[hsl(var(--accent-2))] bg-[hsl(var(--accent-2)/0.08)]'
                    : 'border-border bg-card hover:bg-muted'} disabled:opacity-50`}
                >
                  {t(`project.roomSheet.${key}`)}
                </button>
              ))}
            </div>
            <p className="mt-1 text-[13px] leading-snug text-muted-foreground">
              {t('project.roomSheet.floorConsequence')}
            </p>
          </div>
        )}

        {editing && kind === 'choice' && field === 'paskirtis' && (
          <div className="mt-2">
            <label className="text-[14px] text-[hsl(var(--ink-2))]" htmlFor={`p-${fact.key}`}>
              {t('project.roomSheet.paskirtisLabel')}
            </label>
            <select
              id={`p-${fact.key}`}
              disabled={busy}
              defaultValue={room?.paskirtis || 'gyvenamoji'}
              onChange={(e) => { onSaveChoice?.(field, e.target.value); setEditing(false); }}
              className="ml-2 h-11 rounded-[2px] border border-border bg-card px-2 text-[16px]"
            >
              {PASKIRTIS.map((p) => (
                <option key={p} value={p}>{t(`project.roomSheet.paskirtis_${p}`)}</option>
              ))}
            </select>
            <p className="mt-1 text-[13px] leading-snug text-muted-foreground">
              {t('project.roomSheet.paskirtisConsequence')}
            </p>
          </div>
        )}
      </div>

      <div className="col-span-2 flex items-start gap-2 sm:col-span-1 sm:flex-col sm:items-end">
        <button
          type="button"
          disabled={busy}
          onClick={onAccept}
          className={`${BTN} ${verified
            ? 'border-[hsl(var(--accent-2))] bg-[hsl(var(--accent-2))] text-white'
            : 'border-border bg-card hover:bg-muted'} disabled:opacity-50`}
        >
          <Check className="h-4 w-4" aria-hidden="true" />
          {assumed ? t('project.roomSheet.keepAssumed') : t('project.roomSheet.correct')}
        </button>
        <button
          type="button"
          disabled={busy}
          onClick={() => setEditing((v) => !v)}
          className={`${BTN} border-border bg-card hover:bg-muted disabled:opacity-50`}
        >
          <Pencil className="h-4 w-4" aria-hidden="true" />
          {editing ? t('project.roomSheet.cancel') : t('project.roomSheet.fix')}
        </button>
      </div>
    </div>
  );
}
