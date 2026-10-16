/**
 * ProjectMainView — pagrindinis projekto puslapis (Sprint 1).
 *
 * VIENAS ekranas:
 *   ┌───────────────────────────────────────────────────────┐
 *   │  Projekto info  · Bendra suma €  · [Eksportuoti ▾]    │  ← sticky top
 *   ├───────────────────────────────────────────────────────┤
 *   │  Patalpų suvestinė (collapsible)                      │
 *   │     12 patalpų · 132 m²                                │
 *   │  ▾ Atidaryti (rodo per kambarį detales)                │
 *   ├───────────────────────────────────────────────────────┤
 *   │  Darbų sąrašas (grupuotas pagal skyrius)               │
 *   │     Sienų darbai                                       │
 *   │       - Sienų lyginimas Rotband      350 m²  7 €  2450│
 *   │       - Sienų dažymas                350 m²  ...      │
 *   │     Lubų darbai                                        │
 *   │       - GKP lubos                    130 m²  ...      │
 *   ├───────────────────────────────────────────────────────┤
 *   │  [Žiūrėti brėžinį →]   [Pridėti darbų eilutę]          │
 *   └───────────────────────────────────────────────────────┘
 */

import React, { useState, useMemo, useEffect, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { isReverseVat, vatPercent } from '@/lib/vatMode';
import { toast } from 'sonner';
import {
  Home, ChevronDown, ChevronUp, Eye, Plus, FileText,
  Edit2, Check, X, Trash2, AlertCircle, Search, Sliders, Star, Sigma,
} from 'lucide-react';
import { getPriceLists, pullPriceListsFromBackend } from '@/lib/projectStore';
import { applyPriceListToPositions, manualPricePatch, describeAmbiguous, describeMaterialPrices } from '@/lib/applyPriceList';
import { insertRowInSection, manualRowId, nextEilNr } from '@/lib/darbuRows';
import { findRowById } from '@/lib/ledger';
import { rowNeedsPrice } from '@/lib/exportLines';
import { parseLtNumber, isValidAmount, MAX_AMOUNT } from '@/lib/parseLtNumber';

// A well-formed number over the cap gets magnitude advice, not format advice —
// "naudokite kablelį" is misleading when the problem is 100 000 000.
// (final-regression finding 6, 2026-07-28)
const invalidAmountKey = (n) =>
  Number.isFinite(n) && n > MAX_AMOUNT
    ? 'project.mainView.toastTooLarge'
    : 'project.mainView.toastInvalidNumber';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import ExportDropdown from './ExportDropdown';
import RowDetailPanel from './RowDetailPanel';
import { ApplyAssembliesButton, KodasChip, priceSplitTitle, useAssemblies } from './RinkiniaiControls';
import { effectiveKodas } from '@/lib/kodas';
import { materialPriceNotes } from '@/lib/assemblyPricing';
import SanityWarningsBanner from './SanityWarningsBanner';
import SamataTemplateView from './SamataTemplateView';
import { fetchSamataTemplates } from '@/lib/samataTemplateApi';
import { LAYOUT_PATHON, LAYOUT_TEMPLATE, hasLayoutChoice, loadLayoutChoice, saveLayoutChoice } from '@/lib/samataTemplate';
import { pilotSession, recordPilot, releasePilotSession } from '@/lib/telemetry';
import {
  adjustPositionQuantity,
  updatePositionQuantity,
} from '@/lib/quantityOverride';
import {
  TAKEOFF_FILTER_MODES,
  filterTakeoffRows,
  getQuantitySourceKind,
  getQuantitySourceLabel,
  getRowTargetPage,
  summarizeSamataRows,
} from '@/lib/takeoffWorkflow';

// ── Helpers ──────────────────────────────────────────────────────────────────

function fmt(val, d = 2) {
  if (val == null) return '—';
  return Number(val).toLocaleString('lt-LT', { maximumFractionDigits: d });
}
function fmtEur(val) {
  if (val == null) return '—';
  return `${Number(val).toLocaleString('lt-LT', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} €`;
}

// ── Group darbų sąrašą pagal skyrius ─────────────────────────────────────────

function groupByCategory(darbu_sarasas, otherLabel) {
  const groups = {};
  (darbu_sarasas || []).forEach(item => {
    const cat = item.skyrius || item.kategorija || otherLabel;
    if (!groups[cat]) groups[cat] = [];
    groups[cat].push(item);
  });
  return groups;
}

// ── Vienas darbo eilutės redaktorius (inline) ────────────────────────────────

function WorkRow({
  item, onChange, onRemove, onJumpToSource, targetPage, onOpenLedger,
  focusPriceNonce = 0, onPriceFocused, kodas = null, materialNote = null,
}) {
  const { t } = useTranslation();
  const [editing, setEditing] = useState(false);
  const [editingQty, setEditingQty] = useState(false);
  const [draftQty, setDraftQty] = useState('');
  // Inline PRICE editor (2026-08-11). Pricing 82 rows used to cost ~4 pointer
  // actions each — hover, pencil, click into the input, tick — because the
  // price cell itself was dead (the quantity cell beside it had a proper
  // editor all along). Now: click the cell, type, Enter commits AND opens the
  // next row's price — 82 rows ≈ 82 keystrokes. Advance is DOM-ordered
  // ([data-price-cell] in document order == visual order), so it follows the
  // grouped-by-section layout without threading indices through the parent.
  const [editingPrice, setEditingPrice] = useState(false);
  const [draftPrice, setDraftPrice] = useState('');
  const priceCellRef = useRef(null);

  const beginPriceEdit = () => {
    setDraftPrice(item.kaina ? String(item.kaina).replace('.', ',') : '');
    setEditingPrice(true);
  };

  // „Įrašyti kainas" (2026-10-06): this is the first row that would reach the
  // client without a price. Bring it to the middle of the screen and open its
  // price, so he types straight away — Enter then opens the next row's price.
  // Opening is harmless: leaving the field empty changes nothing.
  useEffect(() => {
    if (!focusPriceNonce) return;
    priceCellRef.current?.scrollIntoView({ block: 'center' });
    beginPriceEdit();
    onPriceFocused?.();
  }, [focusPriceNonce]);

  const advanceToNextPriceCell = () => {
    // setTimeout(0), NOT requestAnimationFrame: rAF never fires while the tab
    // is hidden or the pane unpainted, which silently killed the advance in
    // testing. A macrotask always runs, and by then this row has left edit
    // mode so the query sees the committed DOM.
    setTimeout(() => {
      const cells = Array.from(document.querySelectorAll('[data-price-cell]'));
      const next = cells[cells.indexOf(priceCellRef.current) + 1];
      if (next) next.dispatchEvent(new MouseEvent('click', { bubbles: true }));
    }, 0);
  };

  const commitPrice = (advance) => {
    const raw = String(draftPrice).trim();
    setEditingPrice(false);
    if (raw === '') { if (advance) advanceToNextPriceCell(); return; }
    const kaina = parseLtNumber(raw);
    if (!isValidAmount(kaina)) {
      toast.error(t(invalidAmountKey(kaina)));
      return;
    }
    if (kaina !== (item.kaina || 0)) {
      onChange({
        ...item,
        kaina,
        suma: (item.kiekis || 0) * kaina,
        ...manualPricePatch(item, kaina),
      });
    }
    if (advance) advanceToNextPriceCell();
  };
  const [draft, setDraft] = useState({
    aprasymas: item.aprasymas || '',
    kiekis: item.kiekis || 0,
    kaina: item.kaina || 0,
  });

  const suma = (parseLtNumber(draft.kiekis) || 0) * (parseLtNumber(draft.kaina) || 0);
  const itemSuma = (item.kiekis || 0) * (item.kaina || 0);
  const isManualQty = item.manual_override === true || item.quantity_source === 'manual_override';
  const sourceKind = getQuantitySourceKind(item);
  const sourceLabel = getQuantitySourceLabel(item);
  const sourceClass = {
    manual: 'border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300',
    verified: 'border-emerald-500/30 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300',
    ai_symbol: 'border-red-500/30 bg-red-500/10 text-red-700 dark:text-red-300',
    assumption: 'border-amber-500/30 bg-amber-500/10 text-amber-700 dark:text-amber-300',
    formula_estimate: 'border-blue-500/30 bg-blue-500/10 text-blue-700 dark:text-blue-300',
    formula: 'border-slate-500/20 bg-slate-500/10 text-muted-foreground',
  }[sourceKind] || 'border-slate-500/20 bg-slate-500/10 text-muted-foreground';
  const rowId = item._id || `${item.eil_nr}-${item.aprasymas}`;
  const isCountUnit = String(item.mato_vnt || '').toLowerCase().includes('vnt');
  const kainynasPriced = item.kaina_source === 'kainynas';
  // The matcher scores 1.0 only when the two descriptions are the same once
  // folded; anything less is a judgement call the user should see.
  const approxMatch = kainynasPriced
    && item.kaina_match_score != null && item.kaina_match_score < 1;

  const handleSave = () => {
    // LT decimal comma: parseFloat('12,5') silently returned 12 and an empty
    // field silently became 0. Reject bad input loudly instead. (2026-07-27.)
    // isValidAmount also caps at 99 999 999 — a bigger number is a typo, not a
    // sąmata, and used to sail through into the total. (2026-07-28.)
    const kiekis = parseLtNumber(draft.kiekis);
    const kaina = parseLtNumber(draft.kaina);
    if (!isValidAmount(kiekis) || !isValidAmount(kaina)) {
      const bad = !isValidAmount(kiekis) ? kiekis : kaina;
      toast.error(t(invalidAmountKey(bad)));
      return;
    }
    onChange({
      ...item,
      aprasymas: draft.aprasymas,
      kiekis,
      kaina,
      suma: kiekis * kaina,
      ...manualPricePatch(item, kaina),
    });
    setEditing(false);
  };

  const handleCancel = () => {
    setDraft({
      aprasymas: item.aprasymas || '',
      kiekis: item.kiekis || 0,
      kaina: item.kaina || 0,
    });
    setEditing(false);
  };

  const beginQtyEdit = () => {
    setDraftQty(String(item.kiekis ?? 0).replace('.', ','));
    setEditingQty(true);
  };

  const commitQty = () => {
    const num = parseLtNumber(draftQty);
    if (!isValidAmount(num)) {
      toast.error(t(invalidAmountKey(num)));
      return;   // keep the editor open so the typed value isn't lost
    }
    onChange(updatePositionQuantity([item], rowId, num)[0]);
    setEditingQty(false);
  };

  const adjustQty = (delta) => {
    onChange(adjustPositionQuantity([item], rowId, delta)[0]);
  };

  if (editing) {
    return (
      <tr className="bg-muted/30">
        <td className="px-3 py-2 text-sm text-muted-foreground tabular-nums">{item.eil_nr || '—'}</td>
        <td className="px-3 py-2">
          <input type="text" value={draft.aprasymas}
            onChange={e => setDraft({...draft, aprasymas: e.target.value})}
            placeholder={t('project.mainView.descPlaceholder')}
            aria-label={t('project.mainView.descAria')}
            title={t('project.mainView.descAria')}
            className="w-full px-2 py-1 border border-border bg-background rounded text-sm" />
        </td>
        <td className="px-3 py-2 text-sm text-muted-foreground">{item.mato_vnt || ''}</td>
        {/* type="text" + inputMode: a LT decimal comma makes type="number"
            report an EMPTY value, so "12,5" was read as 0. The placeholder now
            says the comma is welcome — it was the only unwritten rule in the
            whole table. (2026-07-28 explainability pass.) */}
        <td className="px-3 py-2">
          <input type="text" inputMode="decimal" value={draft.kiekis}
            onChange={e => setDraft({...draft, kiekis: e.target.value})}
            placeholder="0,00"
            aria-label={t('project.mainView.qtyAria')}
            title={t('project.mainView.numberHint')}
            className="w-20 px-2 py-1 border border-border bg-background rounded text-sm text-right tabular-nums" />
        </td>
        <td className="px-3 py-2">
          <input type="text" inputMode="decimal" value={draft.kaina}
            onChange={e => setDraft({...draft, kaina: e.target.value})}
            placeholder="0,00"
            aria-label={t('project.mainView.priceAria')}
            title={t('project.mainView.priceHint')}
            className="w-20 px-2 py-1 border border-border bg-background rounded text-sm text-right tabular-nums" />
        </td>
        <td className="px-3 py-2 text-right text-sm font-semibold tabular-nums">
          {fmtEur(suma)}
        </td>
        <td className="px-3 py-2 text-right">
          <button onClick={handleSave}
            title={t('project.mainView.saveRow')} aria-label={t('project.mainView.saveRow')}
            className="p-1 hover:bg-green-100 dark:hover:bg-green-900/30 text-green-700 dark:text-green-400 rounded mr-1">
            <Check className="w-3.5 h-3.5" />
          </button>
          <button onClick={handleCancel}
            title={t('project.mainView.cancelRow')} aria-label={t('project.mainView.cancelRow')}
            className="p-1 hover:bg-red-100 dark:hover:bg-red-900/30 text-red-700 dark:text-red-400 rounded">
            <X className="w-3.5 h-3.5" />
          </button>
        </td>
      </tr>
    );
  }

  const noPrice = !item.kaina;

  // Sprint §FIX-8 (2026-04-29): user feedback — visi taškai vizualiai trukdo
  // ir confidence info jau matosi PERŽIŪRA queue'oje. Dots default OFF.
  // Kept as dead code so showProvenance toggle gali grąžinti vėliau.
  const sourceDot = null;
  const confDot = null;

  return (
    <tr className="hover:bg-muted/30 group transition-colors">
      <td className="px-3 py-2 text-sm text-muted-foreground tabular-nums">{item.eil_nr || '—'}</td>
      <td className="px-3 py-2 text-foreground">
        <div className="flex items-center gap-2 min-w-0">
          {sourceDot}
          <KodasChip item={item} kodas={kodas} onChange={onChange} />
          {/* The description is the row's handle: clicking it opens „Kaip
              suskaičiuota". The price and quantity cells stay separate <td>s,
              so this cannot swallow an edit click. (2026-09-02, Patikra) */}
          <button
            type="button"
            onClick={() => onOpenLedger?.(item)}
            disabled={!onOpenLedger}
            className="truncate text-left hover:underline decoration-dotted underline-offset-2 disabled:no-underline disabled:cursor-default"
            title={onOpenLedger
              ? t('project.mainView.openLedgerTitle')
              : (item.review_reason || item._confidence_reason || item.calculation_basis || sourceLabel)}
          >
            {item.aprasymas}
          </button>
          {/* 2026-05-06: source badge removed per user — visual clutter. */}
          {confDot}
        </div>
        {/* Medžiagos rows say which work they belong to — without it a bare
            "Gruntas" line in the shopping list is unreadable. (2026-09-02) */}
        {item.susijes_darbas && (
          <div className="text-[11px] text-muted-foreground truncate mt-0.5"
               title={item.susijes_darbas}>
            {t('project.mainView.materialFor', { work: item.susijes_darbas })}
          </div>
        )}
        {materialNote && (
          <div className="text-[11px] text-muted-foreground mt-0.5">{materialNote}</div>
        )}
        {/* A row the last recompute could not reproduce is CARRIED, not deleted
            — its quantity is the old one. The flag existed since 2026-07-28 and
            nothing rendered it, so the user could not tell a stale line from a
            fresh one, let alone act on it. (2026-09-02) */}
        {item._orphaned_after_rebuild && (
          <div className="mt-1 flex items-center gap-1.5">
            <span
              className="inline-flex items-center gap-1 rounded border border-amber-500/40 bg-amber-500/10 px-1.5 py-0.5 text-[10px] font-medium text-amber-700 dark:text-amber-300"
              title={t('project.mainView.orphanTitle')}
            >
              <AlertCircle className="w-3 h-3" />
              {t('project.mainView.orphanBadge')}
            </span>
            {onRemove && (
              <button
                type="button"
                onClick={() => onRemove(item)}
                className="text-[10px] underline decoration-dotted underline-offset-2 text-muted-foreground hover:text-red-600"
                title={t('project.mainView.removeTitle')}
              >
                {t('project.mainView.orphanRemove')}
              </button>
            )}
          </div>
        )}
      </td>
      <td className="px-3 py-2 text-sm text-muted-foreground">{item.mato_vnt || ''}</td>
      <td className="px-3 py-2 text-foreground text-right tabular-nums">
        {editingQty ? (
          <input
            autoFocus
            onFocus={(e) => e.target.select()}
            type="text"
            inputMode="decimal"
            value={draftQty}
            onChange={e => setDraftQty(e.target.value)}
            onBlur={commitQty}
            onKeyDown={e => {
              if (e.key === 'Enter') commitQty();
              if (e.key === 'Escape') setEditingQty(false);
            }}
            aria-label={t('project.mainView.qtyAria')}
            title={t('project.mainView.qtyEditHint')}
            className="w-24 px-2 py-1 border border-primary bg-background rounded text-sm text-right tabular-nums"
          />
        ) : (
          <span className="inline-flex items-center justify-end gap-1">
            {isCountUnit && (
              <button
                type="button"
                onClick={e => { e.stopPropagation(); adjustQty(-1); }}
                className="w-5 h-5 rounded border border-border text-muted-foreground/70 hover:border-red-400 hover:text-red-400 transition-all"
                title={t('project.mainView.subtract1')}
              >
                −
              </button>
            )}
            <button
              type="button"
              onClick={beginQtyEdit}
              className="inline-flex items-center justify-end gap-1 rounded px-1 py-0.5 hover:bg-primary/10 hover:text-primary transition-colors"
              title={t('project.mainView.editQty')}
            >
              <span>{fmt(item.kiekis)}</span>
              {isManualQty && (
                <span
                  className="text-[9px] uppercase font-semibold text-emerald-500 border border-emerald-500/30 rounded px-1"
                  title={t('project.mainView.manualShortTitle')}
                >
                  {t('project.mainView.manualShort')}
                </span>
              )}
            </button>
            {isCountUnit && (
              <button
                type="button"
                onClick={e => { e.stopPropagation(); adjustQty(1); }}
                className="w-5 h-5 rounded border border-border text-muted-foreground/70 hover:border-emerald-400 hover:text-emerald-400 transition-all"
                title={t('project.mainView.add1')}
              >
                +
              </button>
            )}
          </span>
        )}
        {isManualQty && item.ai_kiekis_original != null && (
          <div className="text-[10px] text-muted-foreground leading-tight">
            {t('project.mainView.aiOriginal', { value: fmt(item.ai_kiekis_original) })}
          </div>
        )}
      </td>
      <td
        ref={priceCellRef}
        data-price-cell
        onClick={editingPrice ? undefined : beginPriceEdit}
        className={`px-3 py-2 text-sm text-right tabular-nums ${editingPrice ? '' : 'cursor-text'}`}
        title={editingPrice ? undefined : t('project.mainView.clickToEditPrice')}
      >
        {editingPrice ? (
          <input
            autoFocus
            onFocus={(e) => e.target.select()}
            value={draftPrice}
            onChange={e => setDraftPrice(e.target.value)}
            onBlur={() => commitPrice(false)}
            onKeyDown={e => {
              if (e.key === 'Enter') { e.preventDefault(); commitPrice(true); }
              if (e.key === 'Escape') setEditingPrice(false);
            }}
            onClick={e => e.stopPropagation()}
            placeholder="0,00"
            aria-label={t('project.mainView.priceAria')}
            inputMode="decimal"
            className="w-20 bg-card border border-primary rounded outline-none text-right text-sm tabular-nums px-1.5 py-0.5"
          />
        ) : item.kaina ? (
          <span className="inline-flex items-center justify-end gap-1">
            <span className="underline decoration-dotted decoration-transparent hover:decoration-current underline-offset-2"
                  title={priceSplitTitle(item) || undefined}>
              {fmtEur(item.kaina)}
            </span>
            {priceSplitTitle(item) && (
              <span className="sr-only">{priceSplitTitle(item)}</span>
            )}
            {/* WHERE the price came from. `kaina_source` has been written since
                the kainynas shipped and nothing read it — so a price the
                matcher guessed at from a merely SIMILAR row looked exactly like
                one the contractor typed. Amber says "check this one".
                (2026-09-02) */}
            {kainynasPriced && (
              <span
                aria-hidden="true"
                title={approxMatch
                  ? t('project.mainView.priceFromKainynasSimilarTitle')
                  : t('project.mainView.priceFromKainynasTitle')}
                className={`w-1.5 h-1.5 rounded-full shrink-0 ${
                  approxMatch ? 'bg-amber-500' : 'bg-primary/50'}`}
              />
            )}
            {kainynasPriced && (
              <span className="sr-only">
                {approxMatch
                  ? `${t('project.mainView.priceFromKainynas')} — ${t('project.mainView.priceFromKainynasSimilar')}`
                  : t('project.mainView.priceFromKainynas')}
              </span>
            )}
          </span>
        ) : (
          <span className="text-muted-foreground italic underline decoration-dotted underline-offset-2">
            {t('project.mainView.enterPrice')}
          </span>
        )}
      </td>
      <td className="px-3 py-2 font-semibold text-right tabular-nums">
        {item.kaina ? fmtEur(itemSuma) : '—'}
      </td>
      {/* Always visible, never hover-only: a control a 52-year-old contractor
          can only find by sweeping the mouse over a 118-row table is a control
          he does not have (design §5). It is also what made the row 85 px tall
          — in a 64 px column the three buttons wrapped onto three lines. */}
      <td className="px-3 py-2 text-right whitespace-nowrap text-muted-foreground/70">
        {onOpenLedger && (
          <button onClick={() => onOpenLedger(item)}
            className="p-1 hover:bg-primary/10 text-muted-foreground hover:text-primary rounded mr-1"
            title={t('project.mainView.openLedgerTitle')}
            aria-label={t('project.mainView.openLedgerTitle')}>
            <Sigma className="w-3.5 h-3.5" />
          </button>
        )}
        {onJumpToSource && targetPage && (
          <button onClick={() => onJumpToSource(targetPage, item)}
            className="p-1 hover:bg-primary/10 text-muted-foreground hover:text-primary rounded mr-1" title={t('project.mainView.openSourceTitle', { page: targetPage })}>
            <Eye className="w-3.5 h-3.5" />
          </button>
        )}
        <button onClick={() => setEditing(true)}
          className="p-1 hover:bg-muted rounded text-muted-foreground" title={t('project.mainView.edit')}>
          <Edit2 className="w-3.5 h-3.5" />
        </button>
        {onRemove && (
          /* The delete is recoverable for 6 s via the toast — say so on the
             control itself, otherwise a one-click delete of a priced position
             reads as permanent. (2026-07-28 explainability pass.) */
          <button onClick={() => onRemove(item)}
            className="p-1 hover:bg-red-50 dark:hover:bg-red-900/30 text-red-600 rounded ml-1"
            title={t('project.mainView.removeTitle')} aria-label={t('project.mainView.removeTitle')}>
            <Trash2 className="w-3.5 h-3.5" />
          </button>
        )}
      </td>
    </tr>
  );
}

// ── Pagrindinis komponentas ──────────────────────────────────────────────────

export default function ProjectMainView({
  project, onProjectChange, onShowDrawing, onJumpToPage,
  onOpenAssumptions, focusSanityNonce = 0,
  // „Įrašyti kainas" from the Siųsti step or a dialog there (2026-10-06):
  // { nonce, excluded } — open the price of the first row that would reach the
  // client without one. Acted on once; onPriceFocusDone clears it upstream.
  priceFocus = null, onPriceFocusDone,
}) {
  const { t } = useTranslation();
  const [darbai, setDarbai] = useState(project.darbu_sarasas || []);
  // togal-v2 W9: rinkiniai + section codes for the „Kodas" chip, and why a
  // „Medžiagos" row carries no price of its own.
  const { assemblies, kodai } = useAssemblies();
  const materialNotes = useMemo(() => {
    const byIndex = materialPriceNotes(darbai);
    return new Map([...byIndex].map(([i, note]) => [darbai[i], note]));
  }, [darbai]);
  // The contractor's OWN layout (2026-09-05, week 2 of the contractor-trust
  // plan): his sections and row labels, rendered by the backend from a template
  // derived from his sąmatas. Offered only when the account has a template — an
  // account without one never sees the switch. The choice sticks per browser.
  const [templates, setTemplates] = useState([]);
  const [layout, setLayout] = useState(loadLayoutChoice);
  useEffect(() => {
    let alive = true;
    fetchSamataTemplates()
      .then((list) => {
        if (!alive) return;
        setTemplates(list);
        // An uploaded template IS the default layout until he chooses
        // otherwise — the switch stays for going back (2026-09-13).
        if (list.length > 0 && !hasLayoutChoice()) setLayout(LAYOUT_TEMPLATE);
      })
      .catch(() => { /* no switch, nothing else changes */ });
    return () => { alive = false; };
  }, []);
  const hisLayout = layout === LAYOUT_TEMPLATE && templates.length > 0;
  const defaultTemplateId = (templates.find((tp) => tp.is_default) || templates[0])?.id;
  const chooseLayout = (next) => { setLayout(next); saveLayoutChoice(next); };

  // P0 (2026-07-27): "Pritaikyti kainyną" / re-extract push a NEW darbu_sarasas
  // up through onProjectChange, but this local mirror stayed frozen on the
  // array captured at mount — applied prices never appeared, exports sent
  // 0,00 €, and the next row edit wrote the stale array back over the priced
  // one. Re-sync whenever the parent's array identity changes. No loop: our own
  // handlers hand the SAME array reference up, the parent stores it unchanged,
  // and setState bails out on Object.is equality.
  useEffect(() => {
    setDarbai(project.darbu_sarasas || []);
  }, [project.darbu_sarasas]);

  // Arriving from the top-bar sanity pill (which is reachable from the
  // Brėžinys landing tab). Scroll the banner into view — switching tabs alone
  // drops the user at the top of a long Kiekiai page, nowhere near it.
  const sanityRef = useRef(null);
  useEffect(() => {
    if (!focusSanityNonce) return;
    const el = sanityRef.current;
    if (!el) return;
    const id = requestAnimationFrame(() => {
      el.scrollIntoView({ behavior: 'smooth', block: 'center' });
    });
    return () => cancelAnimationFrame(id);
  }, [focusSanityNonce]);

  // Pilot telemetry (2026-09-13): ONE session per project per page load,
  // shared with the check sheet and the drawing step (lib/telemetry.js) —
  // the per-mount session this table used to open logged step 3 alone, with
  // no events. Flushed on pagehide and when the project changes.
  useEffect(() => {
    const projectId = project?.id;
    if (!projectId) return undefined;
    pilotSession(projectId);
    return () => { releasePilotSession(projectId); };
  }, [project?.id]);
  const pilot = (type, target = {}) => recordPilot(project?.id, type, target);
  const [patalposExpanded, setPatalposExpanded] = useState(false);
  // „Kaip suskaičiuota" (2026-09-02, Patikra): the row whose ledger is open.
  // Re-derived from the live array below so a recompute under an open panel
  // refreshes it instead of freezing yesterday's number on screen.
  const [detailRow, setDetailRow] = useState(null);
  // Search stays (118 rows is a lot to scroll); the four filter chips and the
  // four stat tiles above the table are gone — design §4.
  const [takeoffQuery, setTakeoffQuery] = useState('');

  const visibleDarbai = useMemo(() => filterTakeoffRows(darbai, {
    query: takeoffQuery,
    mode: TAKEOFF_FILTER_MODES.all,
  }), [darbai, takeoffQuery]);
  const grouped = useMemo(() => groupByCategory(visibleDarbai, t('project.mainView.otherWorks')), [visibleDarbai, t]);
  const categories = Object.keys(grouped);

  // „Įrašyti kainas" (2026-10-06): the request from the Siųsti step (prop) or
  // from this page's own export dialog. The search is cleared so the row can
  // be seen; the target is the first row IN SCREEN ORDER (grouped by section)
  // that the document would print without a price (lib/exportLines.js).
  const [pendingPriceFocus, setPendingPriceFocus] = useState(null);
  const priceFocusSeq = useRef(0);
  const focusPrices = (excluded = null) => {
    setTakeoffQuery('');
    priceFocusSeq.current += 1;
    setPendingPriceFocus({ nonce: priceFocusSeq.current, excluded: excluded || null });
  };
  useEffect(() => {
    if (!priceFocus?.nonce) return;
    focusPrices(priceFocus.excluded);
    onPriceFocusDone?.();
  }, [priceFocus?.nonce]);
  const priceTarget = useMemo(() => {
    if (!pendingPriceFocus || hisLayout) return null;
    for (const rows of Object.values(grouped)) {
      const hit = rows.find((r) => rowNeedsPrice(r, pendingPriceFocus.excluded));
      if (hit) return hit;
    }
    return null;
  }, [pendingPriceFocus, grouped, hisLayout]);
  // Nothing to open (every row priced, or his own layout is on screen): drop
  // the request instead of letting it fire on some later edit.
  useEffect(() => {
    if (pendingPriceFocus && !priceTarget) setPendingPriceFocus(null);
  }, [pendingPriceFocus, priceTarget]);
  // The one honest line under the table (design §E4).
  const rowSummary = useMemo(() => summarizeSamataRows(darbai), [darbai]);

  // The open ledger panel holds a captured row; every price keystroke replaces
  // the array under it. Re-derive so it never shows a stale quantity —
  // `findRowById` refuses an ambiguous match rather than resolving a duplicated
  // id to whichever row came first.
  const openDetailRow = useMemo(
    () => (detailRow ? findRowById(darbai, detailRow) || detailRow : null),
    [detailRow, darbai]);

  const totals = useMemo(() => {
    let darbo = 0, medz = 0, count = 0;
    darbai.forEach(it => {
      const suma = (it.kiekis || 0) * (it.kaina || 0);
      darbo += suma;
      count++;
    });
    return { darbo, medz, viso: darbo + medz, count };
  }, [darbai]);

  // Reverse-VAT: no output VAT — match the Excel/PDF export so the in-app total
  // doesn't show a 21% VAT line the deliverable omits. (2026-06-19.) His choice
  // wins over the drawing label — one rule, lib/vatMode.js.
  const reverseVat = isReverseVat(project);
  const vatPct = vatPercent(project);

  const totalArea = useMemo(() => {
    const rooms = project.v8_rooms || project.patalpos || [];
    return rooms.reduce((s, r) => s + (r.plotas_m2 || 0), 0);
  }, [project]);

  // Project-wide hidroizoliacijos plotas. Backend stores it on every room
  // (denormalized so any /recompute response carries it); read once.
  const projectHidroM2 = useMemo(() => {
    const rooms = project.v8_rooms || project.patalpos || [];
    for (const r of rooms) {
      const v = r._project_hidroizoliacija_m2;
      if (typeof v === 'number' && v > 0) return v;
    }
    return 0;
  }, [project]);

  // Latest list + project, for callbacks that fire LATER than the render that
  // created them (the delete-undo toast action).
  const latestRef = useRef({ project, darbai });
  useEffect(() => { latestRef.current = { project, darbai }; });

  const handleRowChange = (idx, newItem) => {
    pilot('row_edit', { kind: 'row', id: String(newItem?.aprasymas || '') });
    const updated = [...darbai];
    updated[idx] = newItem;
    setDarbai(updated);
    onProjectChange?.({ ...project, darbu_sarasas: updated });
  };

  // Toast-undo (Gmail pattern) instead of a confirm dialog: deleting a priced
  // line stays ONE click, but for 6 s it is recoverable — a contractor who
  // deletes a 3 000 € position by mistake had no way back. The reinsert goes
  // through the SAME setDarbai → onProjectChange save path as the delete, so it
  // survives a reload. (2026-07-28 UX walkthrough.)
  const handleRowRemove = (idx) => {
    const removed = darbai[idx];
    if (!removed) return;
    pilot('row_delete', { kind: 'row', id: String(removed.aprasymas || '') });
    const updated = darbai.filter((_, i) => i !== idx);
    setDarbai(updated);
    onProjectChange?.({ ...project, darbu_sarasas: updated });
    toast(t('project.mainView.toastRowDeleted'), {
      duration: 6000,
      action: {
        label: t('project.mainView.undo'),
        onClick: () => {
          // Read the LATEST list/project from the ref — an edit made between
          // the delete and the undo must not be reverted by this reinsert.
          const { project: freshProject, darbai: current } = latestRef.current;
          const at = Math.min(Math.max(idx, 0), current.length);
          const restored = [...current.slice(0, at), removed, ...current.slice(at)];
          setDarbai(restored);
          onProjectChange?.({ ...freshProject, darbu_sarasas: restored });
        },
      },
    });
  };

  const handleAddRow = () => {
    pilot('row_add', { kind: 'row', id: '' });
    const next = {
      eil_nr: darbai.length + 1,
      id: manualRowId(),
      aprasymas: t('project.mainView.newRow'),
      mato_vnt: 'm²',
      kiekis: 0,
      kaina: 0,
      skyrius: t('project.mainView.otherWorks'),
    };
    const updated = [...darbai, next];
    setDarbai(updated);
    onProjectChange?.({ ...project, darbu_sarasas: updated });
  };

  // Contractor ask (2026-09-02): a row must be addable into ANY section, not
  // only "Kiti darbai".
  const handleAddRowInSection = (cat) => {
    pilot('row_add', { kind: 'row', id: String(cat || '') });
    const next = {
      eil_nr: nextEilNr(darbai),
      id: manualRowId(),
      aprasymas: t('project.mainView.newRow'),
      mato_vnt: 'm²',
      kiekis: 0,
      kaina: 0,
      skyrius: cat,
    };
    const updated = insertRowInSection(darbai, cat, next, t('project.mainView.otherWorks'));
    setDarbai(updated);
    onProjectChange?.({ ...project, darbu_sarasas: updated });
  };

  const projectWithDarbai = { ...project, darbu_sarasas: darbai };

  return (
    <div className="space-y-4">
      {/* TOP STICKY — Projekto suvestinė + Eksportas */}
      {/* Top bar — mirrors prototype's 52px ProjectTopBar (compact, single row).
          Be PVM 13px regular · Su PVM 18px bold · same 10px uppercase eyebrow. */}
      <div className="sticky top-0 z-10 bg-background pt-2 pb-3 -mx-1 px-1">
        <div className="bg-card border border-border rounded-md px-4 py-3 shadow-sm">
          <div className="flex items-center justify-between gap-4 flex-wrap">
            {/* Left: totals — Be PVM (compact) | Su PVM (emphasized) */}
            <div className="flex items-center gap-6 flex-wrap">
              <div className="flex items-baseline gap-2">
                <span className="skyrius-header" style={{ fontSize: 10 }}>{t('project.mainView.beVat')}</span>
                <span className="mono tabular text-foreground/70" style={{ fontSize: 13 }}>
                  {fmtEur(totals.viso)}
                </span>
              </div>
              <div className="flex items-baseline gap-2 border-l border-border pl-6">
                <span className="skyrius-header" style={{ fontSize: 10 }}>
                  {reverseVat ? t('project.mainView.totalReverse') : t('project.mainView.withVat', { pct: vatPct })}
                </span>
                <span className="mono tabular font-semibold text-foreground" style={{ fontSize: 18 }}>
                  {fmtEur(totals.viso * (1 + vatPct / 100))}
                </span>
              </div>
              <div className="border-l border-border pl-6 flex items-center gap-4 text-xs text-muted-foreground">
                <span><span className="tabular font-medium text-foreground">{(project.v8_rooms || project.patalpos || []).length}</span> {t('project.mainView.rooms')}</span>
                <span><span className="tabular font-medium text-foreground">{fmt(totalArea)}</span> m²</span>
                <span><span className="tabular font-medium text-foreground">{totals.count}</span> {t('project.mainView.positions')}</span>
                {projectHidroM2 > 0 && (
                  <span title={t('project.mainView.hidroTitle')}>
                    <span className="tabular font-medium text-foreground">{fmt(projectHidroM2)}</span> {t('project.mainView.hidroUnit')}
                  </span>
                )}
              </div>
            </div>

            {/* Right: re-read the drawing + export. „Užpildyti iš kainyno"
                moved down into the prices block, where the choice is
                explained instead of hiding in a toolbar. */}
            <div className="flex items-center gap-2 shrink-0">
              {/* The paid re-read moved to the Nustatymai drawer (council cut
                  list, 2026-09-13): beside Export it read as a routine step. */}
              <ExportDropdown project={projectWithDarbai} onProjectChange={onProjectChange}
                onGoToPrices={focusPrices} />
            </div>
          </div>

          {/* Trūksta kainų — perspėjimas */}
          {totals.viso === 0 && darbai.length > 0 && (
            <div className="mt-3 flex items-start gap-2 p-2.5 bg-amber-50 dark:bg-amber-950/20 border border-amber-200 dark:border-amber-900/40 rounded-lg text-xs text-amber-900 dark:text-amber-200">
              <AlertCircle className="w-3.5 h-3.5 shrink-0 mt-0.5" />
              <div>
                <strong>{t('project.mainView.pricesMissingStrong')}</strong>{t('project.mainView.pricesMissingRest')}
              </div>
            </div>
          )}
        </div>
      </div>

      {/* LT sanity warnings — Sprint 2: vartotojas mato kur AI gali būti suklydęs */}
      <div ref={sanityRef} id="sanity-banner" className="scroll-mt-4">
        {project.lt_sanity && (
          <SanityWarningsBanner
            sanity={project.lt_sanity}
            projectId={project.id}
            onOpenAssumptions={onOpenAssumptions}
            focusNonce={focusSanityNonce}
            onRevalidated={(fresh) => {
              // Backend returns a partial project (lt_sanity, patalpos,
              // warnings_count) — merge so we keep v8_rooms and other state.
              // `fresh.lt_sanity` has ALREADY been merged against the current
              // one inside the banner (lib/sanitySeverity.mergeSanity), so a
              // rebuild that did not re-run a validator cannot erase its
              // checks from the UI.
              const next = { ...project };
              if (fresh.lt_sanity) next.lt_sanity = fresh.lt_sanity;
              if (Array.isArray(fresh.patalpos)) next.patalpos = fresh.patalpos;
              onProjectChange?.(next);
            }}
          />
        )}
      </div>

      {/* PATALPŲ SUVESTINĖ — collapsible */}
      <div className="bg-card border border-border rounded-xl overflow-hidden">
        <button
          onClick={() => setPatalposExpanded(v => !v)}
          className="w-full flex items-center justify-between px-4 py-3 hover:bg-muted/40 transition-colors"
        >
          <span className="flex items-center gap-2 text-sm font-semibold text-foreground">
            <Home className="w-4 h-4 text-muted-foreground" />
            {t('project.mainView.roomsSummary')}
            <Badge variant="secondary" className="text-xs font-normal">
              {t('project.mainView.roomsBadge', { count: (project.v8_rooms || project.patalpos || []).length, area: fmt(totalArea) })}
            </Badge>
          </span>
          {patalposExpanded
            ? <ChevronUp className="w-4 h-4 text-muted-foreground" />
            : <ChevronDown className="w-4 h-4 text-muted-foreground" />}
        </button>

        {patalposExpanded && (
          <div className="border-t border-border p-3">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="text-xs uppercase text-muted-foreground border-b border-border">
                  <tr>
                    <th className="px-2 py-1.5 text-left font-medium">{t('project.mainView.colNr')}</th>
                    <th className="px-2 py-1.5 text-left font-medium">{t('project.mainView.colName')}</th>
                    <th className="px-2 py-1.5 text-left font-medium">{t('project.mainView.colPurpose')}</th>
                    <th className="px-2 py-1.5 text-right font-medium">{t('project.mainView.colAreaM2')}</th>
                    <th className="px-2 py-1.5 text-right font-medium">{t('project.mainView.colPerimM')}</th>
                    <th className="px-2 py-1.5 text-right font-medium">{t('project.mainView.colCeilingM')}</th>
                  </tr>
                </thead>
                <tbody>
                  {(project.v8_rooms || project.patalpos || []).map((r, i) => {
                    // Prefer eksplikacija page if room has bbox highlight data
                    // (lets users land directly on the row they're inspecting).
                    // Falls back to floor-plan page (puslapio_nr).
                    const eksPage = project?._eksplikacija?.eksplikacija_source_page;
                    const targetPage = (r.eksplikacija_row_bbox && eksPage) || r.puslapio_nr;
                    const canJump = !!(onJumpToPage && targetPage);
                    return (
                      <tr
                        key={i}
                        onClick={canJump ? () => onJumpToPage(targetPage, r) : undefined}
                        className={`border-b border-border/40 last:border-0 group ${
                          canJump
                            ? 'cursor-pointer hover:bg-foreground/5'
                            : 'hover:bg-muted/20'
                        }`}
                        title={canJump
                          ? (r.eksplikacija_row_bbox
                              ? t('project.mainView.openEksTitle', { page: eksPage })
                              : t('project.mainView.openPageTitle', { page: targetPage }))
                          : undefined}
                      >
                        <td className="px-2 py-1.5 text-xs text-muted-foreground tabular-nums">{r.nr}</td>
                        <td className="px-2 py-1.5 text-foreground">
                          <span className="inline-flex items-center gap-1.5">
                            {r.pavadinimas}
                            {canJump && (
                              <Eye className="w-3 h-3 text-muted-foreground/60 group-hover:text-foreground transition-colors" />
                            )}
                          </span>
                        </td>
                        <td className="px-2 py-1.5 text-xs text-muted-foreground">{r.paskirtis}</td>
                        <td className="px-2 py-1.5 text-right tabular-nums">{fmt(r.plotas_m2)}</td>
                        <td className="px-2 py-1.5 text-right tabular-nums">{fmt(r.perimetras_m)}</td>
                        <td className="px-2 py-1.5 text-right tabular-nums">{fmt(r.lubu_aukstis_m, 2)}</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </div>
        )}
      </div>

      {/* KAINOS — „Užpildyti iš mano kainyno" / „Įvesiu pats" (design §3).
          A choice with its consequence written next to it, not a hidden
          dropdown in a toolbar: the two ways prices get into the sąmata, said
          out loud, with the default one named. */}
      <div className="bg-card border border-border rounded-xl p-4">
        <h2 className="font-semibold text-foreground" style={{ fontSize: 16 }}>
          {t('project.mainView.pricesTitle')}
        </h2>
        <p className="text-muted-foreground mt-0.5" style={{ fontSize: 14 }}>
          {t('project.mainView.pricesNote')}
        </p>
        <div className="mt-3 flex items-center gap-3 flex-wrap">
          <ApplyPriceListButton project={project} onProjectChange={onProjectChange} />
          <ApplyAssembliesButton project={project} onProjectChange={onProjectChange} assemblies={assemblies} />
          <span className="text-muted-foreground" style={{ fontSize: 14 }}>
            {t('project.mainView.pricesManual')}
          </span>
        </div>
      </div>

      {/* SĄMATOS EILUTĖS — grupuotos pagal skyrius */}
      <div className="bg-card border border-border rounded-xl overflow-hidden">
        <div className="px-4 py-3 border-b border-border flex items-center justify-between gap-3 flex-wrap">
          <h2 className="font-semibold text-foreground flex items-center gap-2" style={{ fontSize: 16 }}>
            <FileText className="w-4 h-4 text-muted-foreground" />
            {t('project.mainView.worksList')}
            <Badge variant="secondary" className="text-xs font-normal">
              {t('project.mainView.worksBadge', { count: darbai.length })}
            </Badge>
          </h2>
          <div className="flex items-center gap-2">
            {templates.length > 0 && (
              <div
                role="radiogroup"
                aria-label={t('project.samataTemplate.layoutLabel')}
                className="inline-flex rounded-md border border-border overflow-hidden"
              >
                {[
                  [LAYOUT_PATHON, t('project.samataTemplate.layoutPathon'), t('project.samataTemplate.layoutPathonTitle')],
                  [LAYOUT_TEMPLATE, t('project.samataTemplate.layoutMine'), t('project.samataTemplate.layoutMineTitle')],
                ].map(([value, label, title]) => (
                  <button
                    key={value}
                    type="button"
                    role="radio"
                    aria-checked={(hisLayout ? LAYOUT_TEMPLATE : LAYOUT_PATHON) === value}
                    title={title}
                    onClick={() => chooseLayout(value)}
                    className={`px-3 font-medium transition-colors ${
                      (hisLayout ? LAYOUT_TEMPLATE : LAYOUT_PATHON) === value
                        ? 'bg-foreground text-background'
                        : 'bg-card text-foreground/80 hover:bg-muted/60'
                    }`}
                    style={{ minHeight: 44, fontSize: 15 }}
                  >
                    {label}
                  </button>
                ))}
              </div>
            )}
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
              <input
                value={takeoffQuery}
                onChange={e => setTakeoffQuery(e.target.value)}
                placeholder={t('project.mainView.searchPositions')}
                aria-label={t('project.mainView.searchPositions')}
                title={t('project.mainView.searchPositionsTitle')}
                className="w-48 sm:w-60 pl-9 pr-3 rounded-md border border-border bg-background outline-none focus:border-primary"
                style={{ minHeight: 44, fontSize: 15 }}
              />
            </div>
            <Button
              variant="outline"
              onClick={handleAddRow}
              title={t('project.mainView.addRowTitle')}
              className="gap-1.5"
              style={{ minHeight: 44, fontSize: 15 }}
            >
              <Plus className="w-4 h-4" />
              {t('project.mainView.addRow')}
            </Button>
          </div>
        </div>

        {/* LT contractors habitually quote a work rate „su medžiagomis". Since
            the materials became their own section, entering an all-in rate on a
            work row AND letting the kainynas price the materials bills the same
            purchase twice — so say what these prices are. (2026-09-02) */}
        <div className="px-4 py-2 border-b border-border bg-muted/10 text-muted-foreground" style={{ fontSize: 14 }}>
          {t('project.mainView.worksAreLabourOnly')}
          {/* The keyboard shortcut, spelled out where it is used instead of
              hidden in a hover tooltip. (Design §5 — „net „Enter" paaiškinta".) */}
          <span className="block mt-0.5">{t('project.mainView.keyboardHint')}</span>
        </div>

        {hisLayout ? (
          <SamataTemplateView
            project={projectWithDarbai}
            darbai={darbai}
            templateId={defaultTemplateId}
            onDarbaiChange={(updated) => {
              setDarbai(updated);
              onProjectChange?.({ ...project, darbu_sarasas: updated });
            }}
            onOpenLedger={setDetailRow}
          />
        ) : darbai.length === 0 ? (
          <div className="p-12 text-center text-muted-foreground text-sm">
            {t('project.mainView.emptyList')}
          </div>
        ) : visibleDarbai.length === 0 ? (
          <div className="p-12 text-center text-muted-foreground text-sm">
            {t('project.mainView.noFilterMatch')}
          </div>
        ) : (
          <div className="overflow-x-auto">
            {/* 16 px body text — design §5 („35–60 metų akims"). The column
                headings stay small: they are labels read once, not numbers
                read all evening. */}
            <table className="w-full" style={{ fontSize: 16 }}>
              <thead className="text-xs uppercase text-muted-foreground border-b border-border bg-muted/20">
                <tr>
                  <th className="px-3 py-2 text-left font-medium w-12">{t('project.mainView.colNr')}</th>
                  <th className="px-3 py-2 text-left font-medium">{t('project.mainView.colDescription')}</th>
                  <th className="px-3 py-2 text-left font-medium w-20">{t('project.mainView.colUnit')}</th>
                  <th className="px-3 py-2 text-right font-medium w-24">{t('project.mainView.colQty')}</th>
                  <th className="px-3 py-2 text-right font-medium w-24">{t('project.mainView.colPricePerUnit')}</th>
                  <th className="px-3 py-2 text-right font-medium w-28">{t('project.mainView.colTotal')}</th>
                  <th className="w-32" />
                </tr>
              </thead>
              <tbody>
                {/* Sprint §AUDIT (2026-04-29): two perf+correctness fixes:
                    (1) Fragment now React.Fragment with key (was bare `<>` —
                        React warned "missing key" on every render).
                    (2) Precomputed itemIndexMap avoids O(n²) `darbai.indexOf`
                        per row. ~6,400 iters → ~80 lookups on Rangovas-style 80-row
                        projects. Each price keystroke was triggering full scan. */}
                {(() => {
                  const itemIndexMap = new Map(darbai.map((d, i) => [d, i]));
                  return categories.map(cat => (
                    <React.Fragment key={`cat-${cat}`}>
                      <tr className="bg-muted/40">
                        <td colSpan={7} className="px-3 py-1 text-xs font-semibold uppercase tracking-wide text-foreground">
                          <span className="flex items-center justify-between gap-2">
                            {cat}
                            <button
                              type="button"
                              onClick={() => handleAddRowInSection(cat)}
                              title={t('project.mainView.addRowToSectionTitle', { section: cat })}
                              aria-label={t('project.mainView.addRowToSectionTitle', { section: cat })}
                              /* A primary action per design §E4 („Pridėti
                                 eilutę — bet kuriame skyriuje, iškart"), so it
                                 gets a real target instead of a 20 px link. */
                              className="inline-flex items-center gap-1.5 rounded font-medium normal-case tracking-normal text-muted-foreground hover:text-foreground hover:bg-muted/60 transition-colors"
                              style={{ minHeight: 44, padding: '0 10px', fontSize: 14 }}
                            >
                              <Plus className="w-4 h-4" />
                              {t('project.mainView.addRow')}
                            </button>
                          </span>
                        </td>
                      </tr>
                      {grouped[cat].map((item) => {
                        const idx = itemIndexMap.get(item) ?? 0;
                        const targetPage = getRowTargetPage(item, project);
                        return (
                          <WorkRow
                            key={`${item.eil_nr}-${idx}`}
                            item={item}
                            onChange={(newItem) => handleRowChange(idx, newItem)}
                            onRemove={() => handleRowRemove(idx)}
                            targetPage={targetPage}
                            onJumpToSource={onJumpToPage}
                            onOpenLedger={setDetailRow}
                            focusPriceNonce={item === priceTarget ? pendingPriceFocus?.nonce : 0}
                            onPriceFocused={() => setPendingPriceFocus(null)}
                            kodas={effectiveKodas(item, assemblies, kodai)}
                            materialNote={materialNotes.get(item) || null}
                          />
                        );
                      })}
                    </React.Fragment>
                  ));
                })()}
              </tbody>
              <tfoot className="border-t-2 border-border bg-muted/20">
                <tr>
                  <td colSpan={5} className="px-3 py-2.5 text-right text-sm font-semibold uppercase tracking-wide text-muted-foreground">
                    {t('project.mainView.totalNoVat')}
                  </td>
                  <td className="px-3 py-2.5 text-right text-base font-bold tabular-nums text-foreground">
                    {fmtEur(totals.viso)}
                  </td>
                  <td />
                </tr>
              </tfoot>
            </table>
          </div>
        )}

        {/* ONE line, his words, no percentage (design §E4). It says what the
            sąmata is made of and what still needs him — nothing about how it
            was produced. */}
        {darbai.length > 0 && (
          <div
            className="px-4 py-3 border-t border-border text-foreground/85"
            style={{ fontSize: 15 }}
          >
            {t('project.mainView.rowSummary', {
              count: rowSummary.fromDrawing,
              verified: rowSummary.verified,
            })}
            {rowSummary.mine > 0 && (
              <> · {t('project.mainView.rowSummaryMine', { count: rowSummary.mine })}</>
            )}
            {rowSummary.noQty > 0 && (
              <> · <span className="text-foreground font-medium">
                {t('project.mainView.rowSummaryNoQty', { count: rowSummary.noQty })}
              </span></>
            )}
          </div>
        )}
      </div>

      {/* Bottom actions */}
      <div className="flex items-center justify-between flex-wrap gap-2">
        {onShowDrawing && (
          <Button
            variant="outline"
            onClick={onShowDrawing}
            className="gap-2"
            style={{ minHeight: 44, fontSize: 15 }}
          >
            <Eye className="w-4 h-4" />
            {t('project.mainView.viewDrawing')}
          </Button>
        )}
        <p className="text-muted-foreground" style={{ fontSize: 13 }}>
          {t('project.mainView.accuracyNote')}
        </p>
      </div>

      {openDetailRow && (
        <RowDetailPanel
          row={openDetailRow}
          rooms={project.v8_rooms || project.patalpos || []}
          onClose={() => setDetailRow(null)}
          onFocusRoom={onJumpToPage}
          onOpenAssumptions={onOpenAssumptions}
        />
      )}
    </div>
  );
}

// ── Apply Price List dropdown — Sprint 9 (2026-05-06) ────────────────────────
// Lists user's saved price lists (from Kainynai page). On click, runs
// fuzzy match against project pozicijos and writes back kaina per row.
// Shows toast with count applied / skipped. Rows with kaina_source
// 'manual' (hand-typed in any price editor) are never overwritten.

function ApplyPriceListButton({ project, onProjectChange }) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const [priceLists, setPriceLists] = useState([]);
  const ref = useRef(null);

  useEffect(() => {
    // Default kainynas first: it is the one the contractor reaches for, and the
    // one the automatic fill already used.
    const readCache = () => setPriceLists(
      [...getPriceLists()].sort((a, b) => (b.is_default ? 1 : 0) - (a.is_default ? 1 : 0)));
    readCache();
    // …and refresh from the backend the first time this session. Without it, a
    // user who signs in on a second device and opens a project straight from
    // the dashboard sees "Kainynas dar neįkeltas" even though his lists are
    // sitting on the server — the cache is only filled by the Kainynai page.
    let alive = true;
    pullPriceListsFromBackend()
      .then(() => { if (alive) readCache(); })
      .catch(() => { /* cache still shows whatever this browser has */ });
    return () => { alive = false; };
  }, [open]);

  useEffect(() => {
    const onClick = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    };
    if (open) document.addEventListener('mousedown', onClick);
    return () => document.removeEventListener('mousedown', onClick);
  }, [open]);

  const handleApply = (priceList, opts = {}) => {
    recordPilot(project?.id, 'kainynas_apply', { kind: 'kainynas', id: '' });
    setOpen(false);
    // Price each list from its OWN rows and write back ONLY that list. The old
    // code priced `pozicijos || darbu_sarasas` and wrote the SAME result into
    // BOTH — clobbering darbu_sarasas (the Kiekiai/export source of truth) with
    // the pozicijos-derived rows and destroying user edits. (2026-06-19 hunt.)
    const updated = { ...project };
    let primary = null;  // counts reported to the user — from darbu_sarasas (visible list) when present
    for (const key of ['darbu_sarasas', 'pozicijos']) {
      const src = project[key];
      if (!Array.isArray(src) || src.length === 0) continue;
      const result = applyPriceListToPositions(src, priceList.items || [], opts);
      updated[key] = result.items;
      if (!primary) primary = result;
    }
    if (!primary || primary.applied === 0) {
      toast.error(t('project.mainView.toastApplyFail', { name: priceList.name }));
      return;
    }
    updated._last_applied_pricelist = { id: priceList.id, name: priceList.name, applied_at: new Date().toISOString() };
    onProjectChange?.(updated);
    toast.success(t('project.mainView.toastApplied', {
      applied: primary.applied,
      name: priceList.name,
      skipped: primary.skipped,
      exact: primary.exact,
      similar: primary.similar,
    }), { description: describeMaterialPrices(primary, t) });
    // Rows the matcher refused to guess at are the ones the user must price by
    // hand — a silent skip inside "praleista" would never get looked at.
    if (primary.ambiguous?.length) {
      toast.warning(t('project.mainView.toastAmbiguous', { count: primary.ambiguous.length }),
        { duration: 8000, description: describeAmbiguous(primary.ambiguous, t) });
    }
  };

  if (priceLists.length === 0) {
    return (
      <Button
        variant="outline"
        disabled
        title={t('project.mainView.priceListNotLoaded')}
        style={{ minHeight: 44, fontSize: 15 }}
      >
        <Sliders className="w-4 h-4 mr-2" />
        {t('project.mainView.applyPriceList')}
      </Button>
    );
  }

  return (
    <div className="relative" ref={ref}>
      <Button
        variant="outline"
        onClick={() => setOpen(v => !v)}
        title={t('project.mainView.applyPriceListTitle')}
        style={{ minHeight: 44, fontSize: 15 }}
      >
        <Sliders className="w-4 h-4 mr-2" />
        {t('project.mainView.applyPriceList')}
        <ChevronDown className="w-4 h-4 ml-1.5" />
      </Button>
      {open && (
        <div className="absolute right-0 top-full mt-1 z-50 min-w-[260px] bg-popover border border-border rounded-md shadow-lg py-1">
          {priceLists.map((pl) => (
            <button
              key={pl.id}
              type="button"
              onClick={() => handleApply(pl)}
              /* Applies immediately, no confirm, no undo — say so before the
                 click, not in the toast after it. (2026-07-28.) */
              title={t('project.mainView.priceListItemTitle', { name: pl.name })}
              className="w-full text-left px-3 py-2 text-sm hover:bg-muted/50 flex items-center justify-between gap-3"
            >
              <span className="truncate flex items-center gap-1.5">
                {pl.is_default && (
                  <Star className="w-3 h-3 shrink-0 fill-current text-primary"
                        aria-label={t('project.mainView.priceListDefault')} />
                )}
                {pl.name}
              </span>
              <span className="text-xs text-muted-foreground tabular shrink-0">
                {t('project.mainView.priceListRows', { count: (pl.items || []).length })}
              </span>
            </button>
          ))}
          <div className="px-3 pt-1.5 pb-1 text-[10px] text-muted-foreground border-t border-border mt-1">
            {t('project.mainView.manualPricesKept')}
          </div>
        </div>
      )}
    </div>
  );
}
