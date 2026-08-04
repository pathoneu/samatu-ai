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
import { toast } from 'sonner';
import { calcClaudeCostUSD } from '@/lib/pricing';
import {
  Home, ChevronDown, ChevronUp, Eye, Plus, FileText,
  Edit2, Check, X, Trash2, AlertCircle, Search, ClipboardCheck,
  CircleDollarSign, PencilRuler, Target, Sliders,
} from 'lucide-react';
import { getPriceLists } from '@/lib/projectStore';
import { applyPriceListToPositions, manualPricePatch } from '@/lib/applyPriceList';
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
import ReextractButton from './ReextractButton';
import SanityWarningsBanner from './SanityWarningsBanner';
import { useAuth } from '@/lib/authContext';
import { createSession } from '@/lib/telemetry';
import {
  acceptPositionQuantity,
  adjustPositionQuantity,
  updatePositionQuantity,
} from '@/lib/quantityOverride';
import {
  TAKEOFF_FILTER_MODES,
  filterTakeoffRows,
  getFirstReviewRow,
  getQuantitySourceKind,
  getQuantitySourceLabel,
  getRowTargetPage,
  summarizeTakeoffWorkflow,
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

function WorkRow({ item, onChange, onRemove, onJumpToSource, targetPage }) {
  const { t } = useTranslation();
  const [editing, setEditing] = useState(false);
  const [editingQty, setEditingQty] = useState(false);
  const [draftQty, setDraftQty] = useState('');
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
        <td className="px-3 py-2 text-xs text-muted-foreground tabular-nums">{item.eil_nr || '—'}</td>
        <td className="px-3 py-2">
          <input type="text" value={draft.aprasymas}
            onChange={e => setDraft({...draft, aprasymas: e.target.value})}
            placeholder={t('project.mainView.descPlaceholder')}
            aria-label={t('project.mainView.descAria')}
            title={t('project.mainView.descAria')}
            className="w-full px-2 py-1 border border-border bg-background rounded text-sm" />
        </td>
        <td className="px-3 py-2 text-xs text-muted-foreground">{item.mato_vnt || ''}</td>
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
      <td className="px-3 py-2 text-xs text-muted-foreground tabular-nums">{item.eil_nr || '—'}</td>
      <td className="px-3 py-2 text-sm text-foreground">
        <div className="flex items-center gap-2 min-w-0">
          {sourceDot}
          <span
            className="truncate"
            title={item.review_reason || item._confidence_reason || item.calculation_basis || sourceLabel}
          >
            {item.aprasymas}
          </span>
          {/* 2026-05-06: source badge removed per user — visual clutter. */}
          {confDot}
        </div>
      </td>
      <td className="px-3 py-2 text-xs text-muted-foreground">{item.mato_vnt || ''}</td>
      <td className="px-3 py-2 text-sm text-foreground text-right tabular-nums">
        {editingQty ? (
          <input
            autoFocus
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
                className="opacity-0 group-hover:opacity-100 w-5 h-5 rounded border border-border hover:border-red-400 hover:text-red-400 transition-all"
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
                className="opacity-0 group-hover:opacity-100 w-5 h-5 rounded border border-border hover:border-emerald-400 hover:text-emerald-400 transition-all"
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
      <td className="px-3 py-2 text-sm text-right tabular-nums">
        {item.kaina
          ? fmtEur(item.kaina)
          : (
            /* Looks clickable, isn't — the price is edited through the pencil.
               Say where to go instead of leaving a dead italic hint. */
            <span className="text-muted-foreground italic" title={t('project.mainView.enterPriceTitle')}>
              {t('project.mainView.enterPrice')}
            </span>
          )}
      </td>
      <td className="px-3 py-2 text-sm font-semibold text-right tabular-nums">
        {item.kaina ? fmtEur(itemSuma) : '—'}
      </td>
      <td className="px-3 py-2 text-right opacity-0 group-hover:opacity-100 transition-opacity">
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

export default function ProjectMainView({ project, onProjectChange, onShowDrawing, onJumpToPage }) {
  const { t } = useTranslation();
  const { isAdmin } = useAuth();
  const [darbai, setDarbai] = useState(project.darbu_sarasas || []);

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

  // Sprint 0 Fix 6: session telemetry — track time-on-task per project view
  const sessionRef = useRef(null);
  useEffect(() => {
    const projectId = project?.id;
    if (!projectId) return;
    sessionRef.current = createSession({ projectId });
    const onUnload = () => sessionRef.current?.finish({ exported: false });
    window.addEventListener('beforeunload', onUnload);
    return () => {
      window.removeEventListener('beforeunload', onUnload);
      sessionRef.current?.finish({ exported: false });
    };
  }, [project?.id]);
  const [patalposExpanded, setPatalposExpanded] = useState(false);
  const [reviewDraftQty, setReviewDraftQty] = useState('');
  const [takeoffQuery, setTakeoffQuery] = useState('');
  const [takeoffMode, setTakeoffMode] = useState(TAKEOFF_FILTER_MODES.all);

  const visibleDarbai = useMemo(() => filterTakeoffRows(darbai, {
    query: takeoffQuery,
    mode: takeoffMode,
  }), [darbai, takeoffQuery, takeoffMode]);
  const grouped = useMemo(() => groupByCategory(visibleDarbai, t('project.mainView.otherWorks')), [visibleDarbai, t]);
  const categories = Object.keys(grouped);
  const workflowSummary = useMemo(() => summarizeTakeoffWorkflow(project, {
    hasPdf: !!onShowDrawing,
  }), [project, onShowDrawing]);
  const reviewRows = useMemo(
    () => filterTakeoffRows(darbai, { mode: TAKEOFF_FILTER_MODES.review }),
    [darbai],
  );
  const currentReview = useMemo(() => getFirstReviewRow(darbai), [darbai]);

  useEffect(() => {
    if (currentReview) setReviewDraftQty(String(currentReview.kiekis ?? 0).replace('.', ','));
  }, [currentReview?._id, currentReview?.eil_nr, currentReview?.aprasymas, currentReview?.kiekis]);

  const totals = useMemo(() => {
    let darbo = 0, medz = 0, count = 0;
    darbai.forEach(it => {
      const suma = (it.kiekis || 0) * (it.kaina || 0);
      darbo += suma;
      count++;
    });
    return { darbo, medz, viso: darbo + medz, count };
  }, [darbai]);

  // Reverse-VAT (renovacija): no output VAT — match the Excel/PDF export so the
  // in-app total doesn't show a 21% VAT line the deliverable omits. (2026-06-19.)
  const reverseVat = (project.vat_mode || '').toLowerCase() === 'reverse_vat'
    || (project.archetipas || '').toLowerCase() === 'renovacija';
  const vatPct = reverseVat ? 0 : (project.vat_rate || 21);

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
    const updated = [...darbai];
    updated[idx] = newItem;
    setDarbai(updated);
    onProjectChange?.({ ...project, darbu_sarasas: updated });
  };

  const updateRowsById = (updater, row) => {
    const rowId = row._id || `${row.eil_nr}-${row.aprasymas}`;
    const updated = updater(darbai, rowId);
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
    const next = {
      eil_nr: darbai.length + 1,
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

  const projectWithDarbai = { ...project, darbu_sarasas: darbai };
  const reviewTargetPage = currentReview ? getRowTargetPage(currentReview, project) : null;

  // Review-queue quantity fix — LT comma / spaced thousands aware.
  const applyReviewQty = () => {
    const qty = parseLtNumber(reviewDraftQty);
    if (!isValidAmount(qty)) {
      toast.error(t(invalidAmountKey(qty)));
      return;
    }
    updateRowsById((rows, rowId) => updatePositionQuantity(rows, rowId, qty), currentReview);
  };

  const filterButtons = [
    { mode: TAKEOFF_FILTER_MODES.all, label: t('project.mainView.filterAll'), count: darbai.length },
    { mode: TAKEOFF_FILTER_MODES.review, label: t('project.mainView.filterReview'), count: workflowSummary.reviewRows },
    { mode: TAKEOFF_FILTER_MODES.missing_price, label: t('project.mainView.filterMissingPrice'), count: workflowSummary.missingPrices },
    { mode: TAKEOFF_FILTER_MODES.manual, label: t('project.mainView.filterManual'), count: workflowSummary.manualOverrides },
  ];

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

            {/* Right: apply pricelist + re-extract + export */}
            <div className="flex items-center gap-2 shrink-0">
              <ApplyPriceListButton project={project} onProjectChange={onProjectChange} />
              <ReextractButton project={project} onComplete={onProjectChange} />
              <ExportDropdown project={projectWithDarbai} />
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
      {project.lt_sanity && (
        <SanityWarningsBanner
          sanity={project.lt_sanity}
          projectId={project.id}
          onRevalidated={(fresh) => {
            // Backend returns a partial project (lt_sanity, patalpos,
            // warnings_count) — merge so we keep v8_rooms and other state.
            const next = { ...project };
            if (fresh.lt_sanity) next.lt_sanity = fresh.lt_sanity;
            if (Array.isArray(fresh.patalpos)) next.patalpos = fresh.patalpos;
            onProjectChange?.(next);
          }}
        />
      )}

      <div className="bg-card border border-border rounded-xl overflow-hidden">
        <div className="px-4 py-3 border-b border-border flex items-center justify-between gap-3 flex-wrap">
          <div className="flex items-center gap-3">
            <div className="w-10 h-10 rounded-md border border-border bg-background flex items-center justify-center">
              <Target className="w-5 h-5 text-primary" />
            </div>
            <div>
              <div className="text-sm font-semibold text-foreground">{t('project.mainView.takeoffControl')}</div>
              <div className="text-xs text-muted-foreground">
                {t('project.mainView.takeoffSummary', { positions: workflowSummary.totalRows, rooms: workflowSummary.totalRooms, area: fmt(workflowSummary.totalArea) })}
              </div>
            </div>
          </div>
          {/* 2026-05-06: Paruošimas % bar removed — misleading when prices
              not entered (always read 50%). 'AI ženklai / Prielaidos' counter
              kept; gives user a sense of what AI inferred vs read directly. */}
          {(workflowSummary.aiSymbolRows > 0 || workflowSummary.assumptionRows > 0) && (
            <div className="text-[11px] text-muted-foreground">
              {t('project.mainView.aiSymbols')}<span className="mono tabular text-foreground">{workflowSummary.aiSymbolRows}</span>
              <span className="mx-1.5">·</span>
              {t('project.mainView.assumptionsCounter')}<span className="mono tabular text-foreground">{workflowSummary.assumptionRows}</span>
            </div>
          )}
        </div>

        <div className="p-4 grid grid-cols-1 lg:grid-cols-[1fr_auto] gap-4">
          <div className="grid grid-cols-2 md:grid-cols-4 gap-2">
            <button
              type="button"
              onClick={() => setTakeoffMode(TAKEOFF_FILTER_MODES.review)}
              title={t('project.mainView.cardReviewTitle')}
              className="text-left rounded-md border border-border bg-background px-3 py-2 hover:border-amber-400 transition-colors"
            >
              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                <ClipboardCheck className="w-3.5 h-3.5" />
                {t('project.mainView.cardReview')}
              </div>
              <div className="mt-1 mono tabular text-lg font-semibold text-foreground">{workflowSummary.reviewRows}</div>
            </button>
            <button
              type="button"
              onClick={() => setTakeoffMode(TAKEOFF_FILTER_MODES.missing_price)}
              title={t('project.mainView.cardMissingPriceTitle')}
              className="text-left rounded-md border border-border bg-background px-3 py-2 hover:border-amber-400 transition-colors"
            >
              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                <CircleDollarSign className="w-3.5 h-3.5" />
                {t('project.mainView.cardMissingPrice')}
              </div>
              <div className="mt-1 mono tabular text-lg font-semibold text-foreground">{workflowSummary.missingPrices}</div>
            </button>
            <button
              type="button"
              onClick={() => setTakeoffMode(TAKEOFF_FILTER_MODES.manual)}
              title={t('project.mainView.cardManualTitle')}
              className="text-left rounded-md border border-border bg-background px-3 py-2 hover:border-emerald-400 transition-colors"
            >
              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                <PencilRuler className="w-3.5 h-3.5" />
                {t('project.mainView.cardManual')}
              </div>
              <div className="mt-1 mono tabular text-lg font-semibold text-foreground">{workflowSummary.manualOverrides}</div>
            </button>
            <button
              type="button"
              onClick={onShowDrawing || undefined}
              disabled={!onShowDrawing}
              title={onShowDrawing ? t('project.mainView.cardDrawingTitle') : t('project.mainView.cardDrawingDisabledTitle')}
              className="text-left rounded-md border border-border bg-background px-3 py-2 hover:border-primary transition-colors disabled:opacity-50 disabled:hover:border-border"
            >
              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                <Eye className="w-3.5 h-3.5" />
                {t('project.mainView.cardDrawing')}
              </div>
              <div className="mt-1 text-sm font-semibold text-foreground">
                {workflowSummary.hasPdf ? (workflowSummary.totalPages ? t('project.mainView.pdfPages', { count: workflowSummary.totalPages }) : t('project.mainView.pdfFallback')) : t('project.mainView.attachPdf')}
              </div>
            </button>
          </div>

          <div className="flex flex-col sm:flex-row lg:flex-col gap-2 min-w-[260px]">
            <div className="relative">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
              <input
                value={takeoffQuery}
                onChange={e => setTakeoffQuery(e.target.value)}
                placeholder={t('project.mainView.searchPositions')}
                aria-label={t('project.mainView.searchPositions')}
                title={t('project.mainView.searchPositionsTitle')}
                className="w-full h-9 pl-9 pr-3 rounded-md border border-border bg-background text-sm outline-none focus:border-primary"
              />
            </div>
            <div className="flex flex-wrap gap-1">
              {filterButtons.map(btn => (
                <button
                  key={btn.mode}
                  type="button"
                  onClick={() => setTakeoffMode(btn.mode)}
                  title={t(`project.mainView.filterTitles.${btn.mode}`, { defaultValue: t('project.mainView.filterFallbackTitle') })}
                  aria-pressed={takeoffMode === btn.mode}
                  className={`h-8 px-2.5 rounded-md border text-xs transition-colors ${
                    takeoffMode === btn.mode
                      ? 'border-primary bg-primary/10 text-primary'
                      : 'border-border text-muted-foreground hover:text-foreground hover:border-foreground/30'
                  }`}
                >
                  {btn.label} <span className="mono tabular">{btn.count}</span>
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>

      {currentReview ? (
        <div className="border border-amber-400/40 bg-amber-50 dark:bg-amber-950/20 rounded-lg px-4 py-3 flex items-center gap-3">
          <AlertCircle className="w-4 h-4 text-amber-600 dark:text-amber-300 shrink-0" />
          <div className="min-w-0 flex-1">
            <div className="text-xs uppercase tracking-wide text-amber-700 dark:text-amber-300 font-semibold">
              {t('project.mainView.reviewMode', { count: reviewRows.length })}
            </div>
            <div className="text-sm text-foreground truncate">
              {currentReview.eil_nr}. {currentReview.aprasymas}
              <span className="text-muted-foreground ml-2">
                {t('project.mainView.reviewLabel', { label: getQuantitySourceLabel(currentReview), qty: fmt(currentReview.kiekis), unit: currentReview.mato_vnt || '' })}
              </span>
            </div>
            {(currentReview.review_reason || currentReview._confidence_reason) && (
              <div className="text-xs text-amber-800 dark:text-amber-200 truncate">
                {currentReview.review_reason || currentReview._confidence_reason}
              </div>
            )}
          </div>
          <input
            value={reviewDraftQty}
            onChange={e => setReviewDraftQty(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter') applyReviewQty(); }}
            className="w-24 h-8 px-2 border border-border bg-background rounded text-sm text-right tabular-nums"
            aria-label={t('project.mainView.fixQtyTitle')}
            title={t('project.mainView.fixQtyHint')}
          />
          <Button
            variant="outline"
            size="sm"
            className="border-border"
            title={t('project.mainView.fixTitle')}
            onClick={applyReviewQty}
          >
            {t('project.mainView.fix')}
          </Button>
          <Button
            size="sm"
            title={t('project.mainView.confirmTitle')}
            onClick={() => updateRowsById(acceptPositionQuantity, currentReview)}
          >
            {t('project.mainView.confirm')}
          </Button>
          {onJumpToPage && reviewTargetPage && (
            <Button
              variant="outline"
              size="sm"
              className="border-border"
              title={t('project.mainView.sourceTitle', { page: reviewTargetPage })}
              onClick={() => onJumpToPage(reviewTargetPage, currentReview)}
            >
              {t('project.mainView.source')}
            </Button>
          )}
        </div>
      ) : (
        <div className="border border-emerald-500/25 bg-emerald-50 dark:bg-emerald-950/15 rounded-lg px-4 py-2 text-sm text-emerald-700 dark:text-emerald-300">
          {t('project.mainView.allReviewed')}
        </div>
      )}

      {/* Analizės metadata — tik admin'ams (debugging). Eiliniam vartotojui
          šitos technikos detalės nedomina ir gadina trust'ą. */}
      {isAdmin && project._meta && (
        <details className="text-xs text-muted-foreground -mt-2 group">
          <summary className="cursor-pointer hover:text-foreground select-none inline-flex items-center gap-2">
            <span>{t('project.mainView.analysisDetails')}</span>
            {project._meta.elapsed_s && (
              <span className="text-[10px] bg-muted px-1.5 py-0.5 rounded">
                {Math.round(project._meta.elapsed_s)}s
              </span>
            )}
          </summary>
          <div className="mt-2 grid grid-cols-2 gap-x-6 gap-y-1 p-3 bg-muted/30 rounded text-[11px] tabular-nums">
            {project._meta.elapsed_s != null && <><span>{t('project.mainView.duration')}</span><span>{project._meta.elapsed_s}s</span></>}
            {project._meta.input_tokens != null && <><span>{t('project.mainView.inputTokens')}</span><span>{project._meta.input_tokens.toLocaleString()}</span></>}
            {project._meta.output_tokens != null && <><span>{t('project.mainView.outputTokens')}</span><span>{project._meta.output_tokens.toLocaleString()}</span></>}
            {project._meta.cache_read_tokens != null && project._meta.cache_read_tokens > 0 && (
              <><span>{t('project.mainView.cacheHit')}</span><span>{project._meta.cache_read_tokens.toLocaleString()} ({(project._meta.cache_read_tokens / (project._meta.input_tokens || 1) * 100).toFixed(0)}%)</span></>
            )}
            {project._meta.zoom_attempted != null && <><span>{t('project.mainView.refinements')}</span><span>{project._meta.zoom_applied} / {project._meta.zoom_attempted}</span></>}
            {project._meta.zoom_elapsed_s != null && <><span>{t('project.mainView.refinementDuration')}</span><span>{project._meta.zoom_elapsed_s}s</span></>}
            {project._meta.pages_sent != null && <><span>{t('project.mainView.pages')}</span><span>{project._meta.pages_sent}</span></>}
            {project._meta.model && <><span>{t('project.mainView.model')}</span><span>{project._meta.model}</span></>}
            {project._meta.input_tokens != null && (() => {
              // Sprint §AUDIT (2026-04-29): use shared pricing module
              const cost = calcClaudeCostUSD(project._meta);
              return <><span>{t('project.mainView.cost')}</span><span>${cost.toFixed(2)}</span></>;
            })()}
          </div>
        </details>
      )}

      {/* AI rasti simboliai (Diena 4) — kuriose brėžiniuose ką AI Vision aptiko */}
      {(() => {
        const sym = project.v9_meta?.symbols_detected
                  || project.detected_symbols_summary
                  || (project.detected_symbols?.by_type
                      ? Object.fromEntries(
                          Object.entries(project.detected_symbols.by_type)
                            .map(([k, v]) => [k, v.total]))
                      : null);
        if (!sym || Object.keys(sym).length === 0) return null;

        const symLabel = (k) => {
          const key = `project.mainView.symbols.${k}`;
          const translated = t(key);
          return translated === key ? k : translated;
        };

        return (
          <div className="bg-card border border-border rounded-xl p-4">
            <div className="flex items-center gap-2 mb-3">
              <Search className="w-4 h-4 text-muted-foreground" />
              <h3 className="text-sm font-semibold text-foreground">
                {t('project.mainView.aiSymbolsFound')}
              </h3>
              <Badge variant="secondary" className="text-[10px] font-normal">
                {Object.values(sym).reduce((a, b) => a + (b || 0), 0)} {t('project.mainView.totalSuffix')}
              </Badge>
            </div>
            <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-x-4 gap-y-2 text-xs">
              {Object.entries(sym)
                .filter(([, v]) => v && v > 0)
                .sort(([, a], [, b]) => b - a)
                .map(([k, v]) => (
                  <div key={k} className="flex items-baseline justify-between border-b border-border/40 pb-1">
                    <span className="text-muted-foreground truncate pr-2">{symLabel(k)}</span>
                    <strong className="text-foreground tabular-nums">{v}</strong>
                  </div>
                ))}
            </div>
          </div>
        );
      })()}

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
                              <Eye className="w-3 h-3 text-muted-foreground opacity-0 group-hover:opacity-100 transition-opacity" />
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

      {/* DARBŲ SĄRAŠAS — grupuotas pagal skyrius */}
      <div className="bg-card border border-border rounded-xl overflow-hidden">
        <div className="px-4 py-3 border-b border-border flex items-center justify-between">
          <h2 className="text-sm font-semibold text-foreground flex items-center gap-2">
            <FileText className="w-4 h-4 text-muted-foreground" />
            {t('project.mainView.worksList')}
            <Badge variant="secondary" className="text-xs font-normal">
              {t('project.mainView.worksBadge', { count: darbai.length })}
            </Badge>
          </h2>
          <Button variant="outline" size="sm" onClick={handleAddRow} title={t('project.mainView.addRowTitle')} className="gap-1.5 h-8 text-xs">
            <Plus className="w-3.5 h-3.5" />
            {t('project.mainView.addRow')}
          </Button>
        </div>

        {darbai.length === 0 ? (
          <div className="p-12 text-center text-muted-foreground text-sm">
            {t('project.mainView.emptyList')}
          </div>
        ) : visibleDarbai.length === 0 ? (
          <div className="p-12 text-center text-muted-foreground text-sm">
            {t('project.mainView.noFilterMatch')}
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full text-sm">
              <thead className="text-xs uppercase text-muted-foreground border-b border-border bg-muted/20">
                <tr>
                  <th className="px-3 py-2 text-left font-medium w-12">{t('project.mainView.colNr')}</th>
                  <th className="px-3 py-2 text-left font-medium">{t('project.mainView.colDescription')}</th>
                  <th className="px-3 py-2 text-left font-medium w-20">{t('project.mainView.colUnit')}</th>
                  <th className="px-3 py-2 text-right font-medium w-24">{t('project.mainView.colQty')}</th>
                  <th className="px-3 py-2 text-right font-medium w-24">{t('project.mainView.colPricePerUnit')}</th>
                  <th className="px-3 py-2 text-right font-medium w-28">{t('project.mainView.colTotal')}</th>
                  <th className="w-16" />
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
                        <td colSpan={7} className="px-3 py-1.5 text-xs font-semibold uppercase tracking-wide text-foreground">
                          {cat}
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
      </div>

      {/* Bottom actions */}
      <div className="flex items-center justify-between flex-wrap gap-2">
        {onShowDrawing && (
          <Button variant="outline" onClick={onShowDrawing} className="gap-2">
            <Eye className="w-4 h-4" />
            {t('project.mainView.viewDrawing')}
          </Button>
        )}
        <p className="text-xs text-muted-foreground">
          {t('project.mainView.accuracyNote')}
        </p>
      </div>
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
    setPriceLists(getPriceLists());
  }, [open]);

  useEffect(() => {
    const onClick = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    };
    if (open) document.addEventListener('mousedown', onClick);
    return () => document.removeEventListener('mousedown', onClick);
  }, [open]);

  const handleApply = (priceList, opts = {}) => {
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
    toast.success(t('project.mainView.toastApplied', { applied: primary.applied, name: priceList.name, skipped: primary.skipped }));
  };

  if (priceLists.length === 0) {
    return (
      <Button
        variant="outline"
        size="sm"
        disabled
        title={t('project.mainView.priceListNotLoaded')}
      >
        <Sliders className="w-3.5 h-3.5 mr-1.5" />
        {t('project.mainView.applyPriceList')}
      </Button>
    );
  }

  return (
    <div className="relative" ref={ref}>
      <Button
        variant="outline"
        size="sm"
        onClick={() => setOpen(v => !v)}
        title={t('project.mainView.applyPriceListTitle')}
      >
        <Sliders className="w-3.5 h-3.5 mr-1.5" />
        {t('project.mainView.applyPriceList')}
        <ChevronDown className="w-3 h-3 ml-1" />
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
              <span className="truncate">{pl.name}</span>
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
