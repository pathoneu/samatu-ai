/**
 * LedgerTree — the evaluated formula behind one sąmata line.
 *
 * Renders `roll_up` / `contributions` / `excluded` exactly as the backend
 * emitted them (see `extractor/ledger.py` and `lib/ledger.js`). It NEVER adds a
 * contribution list up: the capped grindjuostės line bills 107,67 m while its
 * rooms total 111,87 m, and the anchored ceiling line is not Σ-decomposable at
 * all — a client-side sum would print a contradiction next to a correct total.
 *
 * A line without a ledger is not a blank panel: it says so and names its source.
 */

import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { ChevronDown, ChevronRight, MapPin, Settings2, Sigma } from 'lucide-react';
import {
  anchorNote, contributionsOf, excludedOf, hasAnchorStep, hasLedger,
  ledgerFallback, ltNumber, ltQuantity, rollUpIsAuthoritative,
  sortedContributions, splitContributions, termDriver, termEntries,
} from '@/lib/ledger';
import { cleanUserText } from '@/lib/userText';

const TOP_CONTRIBUTIONS = 5;

// A term earns a ⚙ only when a live control actually changes it. Today that is
// the ceiling height (Prielaidos); openings and perimeter have no editor yet,
// and offering a gear that goes nowhere is worse than offering none.
function termHasAssumptionControl(label) {
  return termDriver(label) === 'height';
}

export default function LedgerTree({
  row,
  rooms = [],
  onFocusRoom = null,
  onOpenAssumptions = null,
}) {
  const { t } = useTranslation();
  const [stepsOpen, setStepsOpen] = useState(false);
  const [showAll, setShowAll] = useState(false);
  const [openRooms, setOpenRooms] = useState(() => new Set());

  if (!hasLedger(row)) {
    const fallback = ledgerFallback(row);
    return (
      <div
        className="rounded-sm px-3 py-2.5 text-xs leading-relaxed"
        style={{
          background: 'hsl(var(--bg-1))',
          border: '1px solid hsl(var(--border))',
          color: 'hsl(var(--muted-foreground))',
        }}
      >
        {fallback.kind === 'manual' ? (
          <>
            <span className="font-medium text-foreground">{t('project.ledger.manualRow')}</span>
            {' — '}
            {t('project.ledger.manualRowNote')}
          </>
        ) : (
          <>
            {t('project.ledger.unwired')}{' '}
            {fallback.source
              ? t('project.ledger.unwiredSource', { source: fallback.source })
              : t('project.ledger.unwiredNoSource')}
          </>
        )}
      </div>
    );
  }

  const unit = row.mato_vnt || row.vnt;
  const rollUp = row.roll_up;
  const all = contributionsOf(row);
  const { shown, hiddenCount, total } = splitContributions(all, TOP_CONTRIBUTIONS);
  const contributions = showAll ? sortedContributions(all) : shown;
  const skipped = excludedOf(row);
  const notASum = rollUpIsAuthoritative(rollUp, row);

  const toggleRoom = (key) => setOpenRooms((prev) => {
    const next = new Set(prev);
    if (next.has(key)) next.delete(key); else next.add(key);
    return next;
  });

  return (
    <div className="space-y-3">
      {/* ── The chain, collapsed to one line ─────────────────────────────── */}
      <div
        className="rounded-sm overflow-hidden"
        style={{ border: '1px solid hsl(var(--border))', background: 'hsl(var(--bg-1))' }}
      >
        <button
          type="button"
          onClick={() => setStepsOpen(v => !v)}
          aria-expanded={stepsOpen}
          className="w-full flex items-start gap-2 px-3 py-2 text-left transition-colors hover:bg-muted/40"
          title={t('project.ledger.rollUpTitle')}
        >
          <Sigma className="w-3.5 h-3.5 shrink-0 mt-0.5" style={{ color: 'hsl(var(--primary))' }} />
          <span className="min-w-0 flex-1">
            <span className="block text-[10px] uppercase tracking-wide text-muted-foreground">
              {t('project.ledger.rollUp')}
            </span>
            <span className="block mono tabular text-xs text-foreground leading-relaxed">
              {rollUp.map((step, i) => (
                <span key={`${step.label}-${i}`}>
                  {i > 0 && <span className="text-muted-foreground mx-1">→</span>}
                  <span className="text-muted-foreground">{step.label}</span>{' '}
                  <span className="font-medium">{ltQuantity(step.value, unit)}</span>
                </span>
              ))}
            </span>
          </span>
          {stepsOpen
            ? <ChevronDown className="w-3.5 h-3.5 shrink-0 mt-0.5 text-muted-foreground" />
            : <ChevronRight className="w-3.5 h-3.5 shrink-0 mt-0.5 text-muted-foreground" />}
        </button>
        {stepsOpen && (
          <ul style={{ borderTop: '1px solid hsl(var(--border) / 0.6)' }}>
            {rollUp.map((step, i) => (
              <li
                key={`step-${step.label}-${i}`}
                className="px-3 py-2"
                style={{ borderTop: i ? '1px solid hsl(var(--border) / 0.4)' : undefined }}
              >
                <div className="flex items-baseline justify-between gap-3">
                  <span className="text-xs text-foreground min-w-0">
                    <span
                      className="mr-1.5 rounded px-1 text-[9px] uppercase tracking-wide align-middle"
                      style={{
                        border: '1px solid hsl(var(--border))',
                        color: 'hsl(var(--muted-foreground))',
                      }}
                    >
                      {t(`project.ledger.op.${step.op}`, { defaultValue: step.op })}
                    </span>
                    {step.label}
                  </span>
                  <span className="mono tabular text-xs font-medium text-foreground whitespace-nowrap">
                    {ltQuantity(step.value, unit)}
                  </span>
                </div>
                {step.note && (
                  <p className="mt-1 text-[11px] leading-relaxed text-muted-foreground">
                    {cleanUserText(step.note)}
                  </p>
                )}
              </li>
            ))}
          </ul>
        )}
      </div>

      {/* ── Which rooms produced it ──────────────────────────────────────── */}
      {total > 0 && (
        <div>
          <p className="text-[10px] uppercase tracking-wide text-muted-foreground font-medium mb-1">
            {t('project.ledger.roomsCount', { count: total })}
          </p>
          {/* When an anchor / cap / share is in the chain, these rooms explain
              the number without adding up to it. Say so before the list, or a
              contractor adds the column and finds a "mistake" that is not one. */}
          {notASum && (
            <p className="mb-1 text-[11px] leading-relaxed text-muted-foreground">
              {anchorNote(rollUp) || t(hasAnchorStep(rollUp)
                ? 'project.ledger.notASumAnchor'
                : 'project.ledger.notASum')}
            </p>
          )}
          <ul
            className="rounded-sm overflow-hidden"
            style={{ border: '1px solid hsl(var(--border))' }}
          >
            {contributions.map((c, i) => {
              const key = `${c.room_nr}-${i}`;
              const terms = termEntries(c.terms);
              const open = openRooms.has(key);
              const room = (rooms || []).find(r => String(r?.nr) === String(c.room_nr));
              return (
                <li
                  key={key}
                  style={{
                    borderTop: i ? '1px solid hsl(var(--border) / 0.5)' : undefined,
                    background: 'hsl(var(--card))',
                  }}
                >
                  <div className="flex items-center gap-1.5 px-2.5 py-1.5">
                    {terms.length > 0 ? (
                      <button
                        type="button"
                        onClick={() => toggleRoom(key)}
                        aria-expanded={open}
                        title={t('project.ledger.termsTitle')}
                        className="shrink-0 text-muted-foreground hover:text-foreground"
                      >
                        {open
                          ? <ChevronDown className="w-3 h-3" />
                          : <ChevronRight className="w-3 h-3" />}
                      </button>
                    ) : <span style={{ width: 12 }} className="shrink-0" />}
                    <span className="min-w-0 flex-1">
                      <span className="block text-xs text-foreground truncate">
                        <span className="mono tabular text-muted-foreground mr-1.5">{c.room_nr}</span>
                        {c.room_name}
                      </span>
                      {c.included_because && (
                        <span className="block text-[10px] text-muted-foreground truncate"
                              title={c.included_because}>
                          {cleanUserText(c.included_because)}
                        </span>
                      )}
                    </span>
                    <span className="mono tabular text-xs text-foreground whitespace-nowrap">
                      {ltQuantity(c.value, c.unit || unit)}
                    </span>
                    {onFocusRoom && c.page != null && (
                      <button
                        type="button"
                        onClick={() => onFocusRoom(c.page, room || { nr: c.room_nr, puslapio_nr: c.page })}
                        title={t('project.ledger.pageTitle', { room: c.room_name || c.room_nr })}
                        className="shrink-0 inline-flex items-center gap-0.5 rounded px-1 py-0.5 text-[10px] transition-colors hover:bg-primary/10"
                        style={{ color: 'hsl(var(--primary))' }}
                      >
                        <MapPin className="w-2.5 h-2.5" />
                        {t('project.ledger.page', { page: c.page })}
                      </button>
                    )}
                  </div>
                  {open && terms.length > 0 && (
                    <ul className="px-2.5 pb-2 pl-7 space-y-0.5">
                      {terms.map(term => (
                        <li key={term.label} className="flex items-baseline gap-2 text-[11px]">
                          <span className="text-muted-foreground min-w-0 truncate">{term.label}</span>
                          <span
                            className="flex-1"
                            style={{ borderBottom: '1px dotted hsl(var(--border))' }}
                          />
                          <span className="mono tabular text-foreground whitespace-nowrap">
                            {ltNumber(term.value)}
                          </span>
                          {onOpenAssumptions && termHasAssumptionControl(term.label) && (
                            <button
                              type="button"
                              onClick={() => onOpenAssumptions({
                                field: 'lubu_auksciai', roomNr: c.room_nr,
                              })}
                              title={t('project.ledger.assumptionGear', {
                                room: c.room_name || c.room_nr,
                              })}
                              className="shrink-0 text-muted-foreground hover:text-primary"
                            >
                              <Settings2 className="w-3 h-3" />
                            </button>
                          )}
                        </li>
                      ))}
                    </ul>
                  )}
                </li>
              );
            })}
          </ul>
          {hiddenCount > 0 && (
            <button
              type="button"
              onClick={() => setShowAll(v => !v)}
              className="mt-1 text-[11px] transition-colors hover:underline"
              style={{ color: 'hsl(var(--primary))' }}
            >
              {showAll
                ? t('project.ledger.showLess')
                : t('project.ledger.showAll', { count: total })}
            </button>
          )}
        </div>
      )}

      {/* ── …and which rooms it deliberately left out ────────────────────── */}
      {skipped.length > 0 && (
        <div>
          <p className="text-[10px] uppercase tracking-wide text-muted-foreground font-medium mb-1">
            {t('project.ledger.excluded', { count: skipped.length })}
          </p>
          <ul
            className="rounded-sm overflow-hidden"
            style={{ border: '1px solid hsl(var(--border))', background: 'hsl(var(--bg-1))' }}
          >
            {skipped.map((e, i) => (
              <li
                key={`${e.room_nr}-${i}`}
                className="px-2.5 py-1.5 text-[11px] text-muted-foreground"
                style={{ borderTop: i ? '1px solid hsl(var(--border) / 0.4)' : undefined }}
              >
                <span className="mono tabular mr-1.5">{e.room_nr}</span>
                <span className="text-foreground/70">{e.room_name}</span>
                {e.excluded_because && <span> — {cleanUserText(e.excluded_because)}</span>}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
