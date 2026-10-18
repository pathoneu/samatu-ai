/**
 * WorkspacePanel — right-side panel in Brėžinys tab. Mirrors claude.ai/design
 * prototype's `screen-positions.jsx`: filter at top + Patalpos + Kiekiai
 * sections (collapsible per skyrius). Each position row has source dot,
 * confidence dot, qty, inline-edit price, and sum. Click row → jump PDF.
 *
 * Replaces previous rooms-only table layout with positions-aware unified panel.
 */

import { useState, useMemo, useEffect, useCallback, memo, useRef } from 'react';
import { useTranslation } from 'react-i18next';
import { toast } from 'sonner';
import {
  Search, ChevronDown, ChevronRight, Home, FileText, Eye, EyeOff, Ruler,
  AlertCircle,
} from 'lucide-react';
import { loadTakeoff, removePolygon, saveTakeoff, subscribeTakeoff } from '@/lib/takeoffStore';
import { measurementValue, DEFAULT_COUNT_TYPES } from '@/lib/measurements';
import { effectivePageScales, pageScaleIn } from '@/lib/pageScales';
import { exportCSVFile, exportJSONFile } from '@/lib/measureExport';
import { buildMeasureExportDoc } from '@/lib/measureExportDoc';
import { manualPricePatch } from '@/lib/applyPriceList';
import { parseLtNumber, isValidAmount } from '@/lib/parseLtNumber';
import { updateProject } from '@/lib/projectStore';
import { acceptPositionQuantity, adjustPositionQuantity, updatePositionQuantity } from '@/lib/quantityOverride';
import { getQuantitySourceKind, getQuantitySourceLabel } from '@/lib/takeoffWorkflow';
import { findRowById } from '@/lib/ledger';
import { CONFIDENCE_DOT_CLASS, confidenceLabel, normalizeConfidence } from '@/lib/confidence';
import ReviewQueueSidebar from './ReviewQueueSidebar';
import RowDetailPanel from './RowDetailPanel';
import WallElevationsPanel from './WallElevationsPanel';
import ProvenanceChip from './ProvenanceChip';
import EksplikacijaSourcePopover from './EksplikacijaSourcePopover';
import { useConfirm } from '@/components/ui/confirm-provider';
import { inferPlotasSource } from '@/lib/areaConfidence';
import { floorAreaTotal } from '@/lib/floorArea';
import { roomAreaText } from '@/lib/roomZones';
import { cleanUserText } from '@/lib/userText';

// A measurement on a sheet with no scale in force has no metres (the viewer's chip says why).
const NO_SCALE = 'be mastelio';

function fmt(v, d = 2) {
  if (v == null) return '—';
  return Number(v).toLocaleString('lt-LT', { maximumFractionDigits: d });
}

function fmtEur(v) {
  if (v == null) return '—';
  return `${Number(v).toLocaleString('lt-LT', {
    minimumFractionDigits: 2, maximumFractionDigits: 2,
  })} €`;
}

// ── Source dot — 3-color provenance per prototype ──────────────────────────
const TABLE_SOURCES = new Set([
  'eksplikacija', 'specifikacija', 'isklotines', 'lubu_planas',
  'simboliai_brezinyje',
]);
const COMPUTED_SOURCES = new Set([
  'skaiciuota_is_brezinio', 'lubu_aukstis>3m',
]);

function classifySource(item) {
  const s = item.saltinis || (item.detected === true ? 'skaiciuota_is_brezinio' : 'paskirtis_default');
  if (TABLE_SOURCES.has(s)) return 'table';
  if (COMPUTED_SOURCES.has(s) || item.detected === true) return 'computed';
  return 'ai';
}

const SOURCE_TITLE = {
  table: 'Iš brėžinio lentelės (eksplikacija / specifikacija). Aukštas patikimumas.',
  computed: 'Apskaičiuota iš matmenų pagal LT formules.',
  ai: 'Numatyta pagal paskirtį. Mažesnis patikimumas — privaloma patikrinti.',
};

// ── Auto-poll takeoff store (manual polygons added in PdfViewer) ──────────
function useTakeoff(projectId) {
  const [takeoff, setTakeoff] = useState(() => loadTakeoff(projectId));
  useEffect(() => {
    setTakeoff(loadTakeoff(projectId));
    const unsubscribe = subscribeTakeoff(projectId, () => {
      setTakeoff(loadTakeoff(projectId));
    });
    const onVisChange = () => {
      if (!document.hidden) setTakeoff(loadTakeoff(projectId));
    };
    document.addEventListener('visibilitychange', onVisChange);
    return () => {
      unsubscribe();
      document.removeEventListener('visibilitychange', onVisChange);
    };
  }, [projectId]);
  return [takeoff, setTakeoff];
}

// ── Wet-room paskirtis check (for "drėgna" pill) ──────────────────────────
const WET_PASKIRTYS = new Set(['vonia', 'wc', 'san', 'san_mazgas', 'skalbykla']);

export default function WorkspacePanel({
  project,
  // 'brezinys' — the drawing step: rooms + measurements, no check rail.
  // 'patikra'  — the check step: the rail leads, rooms and measurements follow.
  mode = 'patikra',
  onJumpToPage,
  onJumpToProvenance,
  onProjectChange,
  focusedRoomNr = null,
  // Phase 1 declutter (2026-07-02): panel is the source of truth for which
  // zones are drawn on the canvas. All null-safe — panel works standalone.
  hiddenRoomNrs = null,
  onToggleRoomVisibility = null,
  onIsolateRoom = null,
  // Review-queue pencil → arm click-to-fill for the room in the viewer.
  onEditRoomZone = null,
  onShowAllRooms = null,
  onRoomRowHover = null,
  // Patikra (2026-09-02): a fix jumps to the control that produced the wrong
  // number. `focus` is {field, roomNr} — untargeted when omitted.
  onOpenAssumptions = null,
  // What the last recompute moved, so the rail can show the € ripple.
  lastRipple = null,
}) {
  const { t } = useTranslation();
  const confirm = useConfirm();
  const [takeoff, setTakeoff] = useTakeoff(project.id);
  const [filter, setFilter] = useState('');
  // Provenance dots OFF by default — too noisy when most rows are computed.
  // User can toggle via eye icon to inspect data sources when needed.
  const [showProvenance, setShowProvenance] = useState(false);
  // The rows start folded: the drawing step is for the drawing and its rooms;
  // 114 rows under them were the first thing a contractor scrolled past
  // (council cut list, 2026-09-13). One click opens them, and they stay open.
  const [collapsed, setCollapsed] = useState({ kiekiai: true });
  // Phase C-2 follow-up (2026-05-02): chip click opens an honest data popover
  // anchored to the chip itself. Replaces the random-flash halo that drew on
  // unreliable PDF coords.
  const [popoverState, setPopoverState] = useState(null);  // {room, anchorRect} | null

  const handleRemovePolygon = async (id) => {
    if (!(await confirm({
      title: 'Ištrinti pažymėjimą?',
      confirmText: 'Ištrinti',
      destructive: true,
    }))) return;
    // Persist the removal (P0-1, arch review 2026-07-12): removePolygon is
    // pure — without saveTakeoff the polygon returned after every reload.
    setTakeoff(t => {
      const next = removePolygon(t, id);
      saveTakeoff(project.id, next);
      return next;
    });
  };

  // Rooms (V8 + manual polygons)
  const allRooms = useMemo(() => {
    const v8 = (project.v8_rooms || project.patalpos || []).map(r => ({
      ...r, _source: 'ai',
    }));
    const manual = (takeoff.polygons || [])
      .filter(p => p.type === 'room')
      .map(p => ({
        nr: p.room_nr,
        pavadinimas: p.label || 'Patalpa',
        paskirtis: p.paskirtis || 'gyvenamoji',
        plotas_m2: p.area_m2 || 0,
        perimetras_m: p.perimeter_m || 0,
        lubu_aukstis_m: p.lubu_aukstis_m || 2.82,
        puslapio_nr: p.page,
        _polygon_id: p.id,
        _source: 'manual',
      }));
    return [...v8, ...manual];
  }, [project.v8_rooms, project.patalpos, takeoff.polygons]);

  // A room merged into another is inside the room it joined (lib/floorArea) — never counted twice.
  const totalArea = floorAreaTotal(allRooms);

  // Canvas visibility: nr may be number or string in data — compare as String.
  const hiddenRoomSet = useMemo(
    () => new Set(Array.from(hiddenRoomNrs || []).map(String)),
    [hiddenRoomNrs],
  );
  const hiddenCount = useMemo(
    () => allRooms.filter(r => hiddenRoomSet.has(String(r.nr))).length,
    [allRooms, hiddenRoomSet],
  );

  // Positions grouped by skyrius (preserve server-side order)
  const positionGroups = useMemo(() => {
    const lower = filter.toLowerCase().trim();
    const filtered = (project.darbu_sarasas || []).filter(it => {
      if (!lower) return true;
      return (it.aprasymas || '').toLowerCase().includes(lower)
          || (it.skyrius || '').toLowerCase().includes(lower);
    });
    const map = new Map();
    filtered.forEach(it => {
      const key = it.skyrius || it.kategorija || 'Kiti darbai';
      if (!map.has(key)) map.set(key, []);
      map.get(key).push(it);
    });
    return Array.from(map, ([skyrius, rows]) => ({
      skyrius,
      rows,
      subtotal: rows.reduce((s, r) => s + (r.kiekis || 0) * (r.kaina || 0), 0),
    }));
  }, [project.darbu_sarasas, filter]);

  const totalPositions = positionGroups.reduce((s, g) => s + g.rows.length, 0);
  const totalNet = positionGroups.reduce((s, g) => s + g.subtotal, 0);

  // ── MATAVIMAI — the viewer's measurements, surfaced in the panel (P0-1,
  // arch review 2026-07-12: measurements previously reached project JSON but
  // NO panel read them — "you measure things and nothing shows up"). Counts
  // are grouped per type with an "Į sąmatą" action; lengths/areas are listed
  // with their calibrated values.
  const projMeasurements = project.measurements || [];
  const measCountRows = useMemo(() => {
    const byType = new Map();
    for (const m of projMeasurements) {
      if (m.kind !== 'count' || !m.typeId) continue;
      const cur = byType.get(m.typeId);
      // „Rasti panašius" marks (lib/symbolSearch): found by shape, not checked — the row says so.
      const ai = m.source === 'symbol_search' ? 1 : 0;
      if (cur) {
        cur.count += 1;
        cur.ai += ai;
        if (m.page && (!cur.firstPage || m.page < cur.firstPage)) cur.firstPage = m.page;
      } else {
        const type = (project.countTypes || []).find((t) => t.id === m.typeId)
          || DEFAULT_COUNT_TYPES.find((t) => t.id === m.typeId);
        byType.set(m.typeId, {
          typeId: m.typeId,
          label: type?.label || m.typeId,
          color: m.color || type?.color || 'hsl(var(--primary))',
          count: 1,
          ai,
          firstPage: m.page || null,
        });
      }
    }
    return [...byType.values()];
  }, [projMeasurements, project.countTypes]);
  const measGeomRows = useMemo(() => {
    const KIND_LT = { distance: 'Atstumas', perimeter: 'Perimetras', area: 'Plotas' };
    // The viewer's own merge (lib/pageScales, 2026-10-16): the room areas, the drawing's dimension strings,
    // then his calibration — a sheet whose scale the lane read shows metres here as it does in the viewer.
    const scales = effectivePageScales(project);
    return projMeasurements
      .filter((m) => KIND_LT[m.kind])
      .map((m) => {
        const scale = pageScaleIn(scales, m.page);
        let display = NO_SCALE;
        if (scale?.calibrated) {
          const { value } = measurementValue(m, scale);
          display = m.kind === 'area' ? `${fmt(value, 2)} m²` : `${fmt(value, 2)} m`;
        }
        // A name given in the viewer (right-click „Pervadinti", 2026-10-16) leads; the kind follows.
        return { id: m.id, label: m.name ? `${m.name} · ${KIND_LT[m.kind]}` : KIND_LT[m.kind], page: m.page, display };
      });
  }, [projMeasurements, project]);

  // Push a counted type into the estimate as a position row (kiekis = count,
  // price left for the user). Re-running updates the existing measurement row
  // instead of duplicating it. Field-scoped save — merges onto the CURRENT
  // stored project (same P0-2 contract as measurement saves).
  const addCountToEstimate = useCallback((row) => {
    const list = [...(project.darbu_sarasas || [])];
    const idx = list.findIndex((p) => p.measure_type_id === row.typeId
      && p.quantity_source === 'measurement_count');
    if (idx >= 0) {
      list[idx] = { ...list[idx], kiekis: row.count };
    } else {
      list.push({
        eil_nr: list.length + 1,
        aprasymas: `${row.label} (suskaičiuota brėžinyje)`,
        mato_vnt: 'vnt.',
        kiekis: row.count,
        kaina: 0,
        skyrius: 'Matavimai',
        confidence: row.ai ? 'medium' : 'high',
        quantity_source: 'measurement_count',
        measure_type_id: row.typeId,
      });
    }
    const updated = updateProject(project.id, { darbu_sarasas: list });
    if (updated) onProjectChange?.(updated);
  }, [project.id, project.darbu_sarasas, onProjectChange]);

  // Filter rooms by name when filter active
  const filteredRooms = useMemo(() => {
    const lower = filter.toLowerCase().trim();
    if (!lower) return allRooms;
    return allRooms.filter(r =>
      (r.pavadinimas || '').toLowerCase().includes(lower)
      || (r.paskirtis || '').toLowerCase().includes(lower)
    );
  }, [allRooms, filter]);

  // „Rodyti sąraše" from the viewer's right-click menu: open Matavimai, scroll to the row, flash it.
  // Count marks are listed per type, so a mark reveals its type's row.
  const [revealKey, setRevealKey] = useState(null);
  useEffect(() => {
    const onReveal = (e) => {
      const d = e.detail || {};
      const key = d.kind === 'count' ? `count:${d.typeId}` : `meas:${d.id}`;
      setCollapsed((c) => ({ ...c, meas: false }));
      setRevealKey(key);
      // Scroll only the panel's own scroller — scrollIntoView would also move the page and the drawing.
      requestAnimationFrame(() => requestAnimationFrame(() => {
        const row = document.querySelector(`[data-measure-row="${CSS.escape(key)}"]`);
        let sc = row?.parentElement;
        while (sc && !(sc.scrollHeight > sc.clientHeight + 1 && /(auto|scroll)/.test(getComputedStyle(sc).overflowY))) sc = sc.parentElement;
        if (!row || !sc) return;
        const rr = row.getBoundingClientRect();
        const sr = sc.getBoundingClientRect();
        sc.scrollBy({ top: rr.top - sr.top - sr.height / 2 + rr.height / 2, behavior: 'smooth' });
      }));
    };
    window.addEventListener('samatu:measure-reveal', onReveal);
    return () => window.removeEventListener('samatu:measure-reveal', onReveal);
  }, []);
  useEffect(() => {
    if (!revealKey) return undefined;
    const t = setTimeout(() => setRevealKey(null), 2200);
    return () => clearTimeout(t);
  }, [revealKey]);
  const toggleSection = (id) => {
    setCollapsed(c => ({ ...c, [id]: !c[id] }));
  };

  // Inline price edit handler — useCallback so memo'd PositionRow doesn't
  // re-render on every parent re-render (otherwise inline `(p) => ...` is
  // a fresh fn each time, defeating memo).
  const handlePriceChange = useCallback((rowId, newPrice) => {
    if (!onProjectChange) return;
    const kaina = parseLtNumber(newPrice);
    // isValidAmount: never write NaN — nor an absurd 10^12 € — into a sąmata.
    if (!isValidAmount(kaina)) return;
    const updated = (project.darbu_sarasas || []).map(it => {
      const id = it._id || `${it.eil_nr}-${it.aprasymas}`;
      if (id !== rowId) return it;
      return { ...it, kaina, suma: (it.kiekis || 0) * kaina, ...manualPricePatch(it, kaina) };
    });
    onProjectChange({ ...project, darbu_sarasas: updated });
  }, [project, onProjectChange]);

  const handleQuantityChange = useCallback((rowId, newQuantity) => {
    if (!onProjectChange) return;
    try {
      const updated = updatePositionQuantity(project.darbu_sarasas || [], rowId, newQuantity);
      onProjectChange({ ...project, darbu_sarasas: updated });
    } catch {
      // Invalid input is kept local in the row editor; no project mutation.
    }
  }, [project, onProjectChange]);

  // „Teisinga ✓" — the row leaves the queue AND becomes ground truth: the same
  // `user_verified_at` stamp `scripts/build_ground_truth.py` harvests, so the
  // audit workflow IS the corpus that measures every future engine change.
  const handleAcceptRow = useCallback((row) => {
    if (!onProjectChange) return;
    const rowId = row._id || `${row.eil_nr}-${row.aprasymas}`;
    // ONE accept definition, shared with the Kiekiai table's „Patvirtinti".
    const accepted = acceptPositionQuantity(project.darbu_sarasas || [], rowId);
    const updated = accepted.map(it => (
      (it._id || `${it.eil_nr}-${it.aprasymas}`) === rowId
        ? { ...it, _review_status: 'accepted' }
        : it));
    onProjectChange({ ...project, darbu_sarasas: updated });
  }, [project, onProjectChange]);

  // The rail hands over a ROW, not a key: `updatePositionQuantity` matches on
  // `_id || eil_nr-aprasymas` and knows nothing about the new `id` hash, so a
  // key derived id-first would never match and the fix would silently no-op.
  const handleRowQuantityChange = useCallback((row, qty) => {
    handleQuantityChange(row._id || `${row.eil_nr}-${row.aprasymas}`, qty);
  }, [handleQuantityChange]);

  const handleQuantityAdjust = useCallback((rowId, delta) => {
    if (!onProjectChange) return;
    const updated = adjustPositionQuantity(project.darbu_sarasas || [], rowId, delta);
    onProjectChange({ ...project, darbu_sarasas: updated });
  }, [project, onProjectChange]);

  // Delete one row, recoverable for 6 s — the same Gmail-undo contract
  // ProjectMainView uses, so a stale carried row can be dismissed from EITHER
  // table without a confirm dialog and without being unrecoverable.
  // (2026-09-02, alongside the `_orphaned_after_rebuild` badge.)
  const handleRowRemove = useCallback((row) => {
    if (!onProjectChange) return;
    const list = project.darbu_sarasas || [];
    const idx = list.indexOf(row);
    if (idx < 0) return;
    onProjectChange({ ...project, darbu_sarasas: list.filter((_, i) => i !== idx) });
    toast(t('project.mainView.toastRowDeleted'), {
      duration: 6000,
      action: {
        label: t('project.mainView.undo'),
        onClick: () => {
          // Read the CURRENT list, not the one captured at delete time — an
          // edit made in between must not be reverted by this reinsert.
          const current = latestProjectRef.current?.darbu_sarasas || [];
          const at = Math.min(Math.max(idx, 0), current.length);
          onProjectChange({
            ...latestProjectRef.current,
            darbu_sarasas: [...current.slice(0, at), row, ...current.slice(at)],
          });
        },
      },
    });
  }, [project, onProjectChange, t]);

  // Clicking a quantity row opens „Kaip suskaičiuota" — the ledger, the rooms
  // behind the number, and the page jumps that used to be this click's ONLY
  // effect (they now sit on each contributing room, where they point at the
  // right one instead of at whatever `_room_nr` happened to be stamped).
  const [detailRow, setDetailRow] = useState(null);
  const handleRowClick = useCallback((row) => setDetailRow(row), []);

  // The panel holds a captured row; a recompute or a price edit replaces the
  // array under it. Re-derive so the open panel never shows stale numbers —
  // `findRowById` refuses an ambiguous match rather than resolving a duplicated
  // id to whichever row came first.
  const openDetailRow = useMemo(
    () => (detailRow ? findRowById(project.darbu_sarasas, detailRow) || detailRow : null),
    [detailRow, project.darbu_sarasas]);

  // Latest project, for a callback that fires LATER than the render that made
  // it (the delete-undo toast action).
  const latestProjectRef = useRef(project);
  useEffect(() => { latestProjectRef.current = project; });

  const focusedRowRef = useRef(null);
  useEffect(() => {
    if (focusedRoomNr != null && focusedRowRef.current) {
      focusedRowRef.current.scrollIntoView({ block: 'nearest' });
    }
  }, [focusedRoomNr]);

  return (
    <div
      className="flex flex-col h-full overflow-hidden"
      style={{ background: 'hsl(var(--background))', borderLeft: '1px solid hsl(var(--border))' }}
    >
      {/* ── Filter + provenance toggle ──────────────────────────────────── */}
      <div className="flex gap-1.5 p-2.5 border-b border-border" style={{ borderColor: 'hsl(var(--border) / 0.5)' }}>
        <div className="relative flex-1">
          <Search className="absolute left-2.5 top-2.5 w-3.5 h-3.5 text-muted-foreground" />
          <input
            type="text"
            placeholder="Ieškoti eilutės ar patalpos…"
            aria-label="Ieškoti eilutės ar patalpos"
            title="Įrašykite dalį pavadinimo — sąrašas bus sutrumpintas"
            value={filter}
            onChange={e => setFilter(e.target.value)}
            className="w-full pl-8 pr-2.5 text-foreground bg-card border border-border rounded outline-none focus:border-primary"
            style={{ fontSize: 14, height: 32 }}
          />
        </div>
        <button
          onClick={() => setShowProvenance(v => !v)}
          /* "šaltinio taškai" meant nothing outside the team — name what the
             dots actually tell you. (2026-07-28 explainability pass.) */
          title={showProvenance
            ? 'Slėpti ženkliukus, rodančius, iš kur paimtas kiekvienas skaičius'
            : 'Rodyti ženkliukus, iš kur paimtas kiekvienas skaičius (iš lentelės, apskaičiuota, numatyta)'}
          aria-pressed={showProvenance}
          className="rounded border flex items-center justify-center transition-colors"
          style={{
            height: 32, width: 32,
            borderColor: showProvenance
              ? 'hsl(var(--primary) / 0.3)'
              : 'hsl(var(--border))',
            color: showProvenance
              ? 'hsl(var(--primary))'
              : 'hsl(var(--muted-foreground))',
            background: 'hsl(var(--card))',
          }}
        >
          {showProvenance ? <Eye className="w-3 h-3" /> : <EyeOff className="w-3 h-3" />}
        </button>
      </div>

      {/* ── Scrollable content: Peržiūra + Patalpos + Kiekiai ──────────── */}
      <div className="flex-1 overflow-y-auto">
        {/* PATIKRA — the guided check loop. It belongs to step 2 only: on the
            drawing step the contractor is looking at his plan, not being asked
            to audit it. (Design §2 — one job per step.) */}
        {mode === 'patikra' && (
        <ReviewQueueSidebar
          rooms={allRooms}
          positions={project.darbu_sarasas || []}
          eksplikacijaSourcePage={project?._eksplikacija?.eksplikacija_source_page}
          onJumpToPage={onJumpToPage}
          onEditRoom={onEditRoomZone}
          projectId={project.id}
          lastRipple={lastRipple}
          onOpenAssumptions={onOpenAssumptions}
          onOpenRowDetail={setDetailRow}
          onAcceptRow={handleAcceptRow}
          onQuantityChange={handleRowQuantityChange}
          onReviewStatusChange={onProjectChange ? (kind, key, status) => {
            // Sprint G2 Phase 2: persist _review_status on the matching item.
            if (kind === 'room') {
              const updatedRooms = (project.v8_rooms || project.patalpos || []).map(r =>
                r.nr === key ? { ...r, _review_status: status } : r
              );
              const k = project.v8_rooms ? 'v8_rooms' : 'patalpos';
              onProjectChange({ ...project, [k]: updatedRooms });
            } else if (kind === 'position') {
              const updated = (project.darbu_sarasas || []).map(p => {
                const id = p._id || `${p.eil_nr}-${p.aprasymas}`;
                return id === key ? { ...p, _review_status: status } : p;
              });
              onProjectChange({ ...project, darbu_sarasas: updated });
            }
          } : null}
        />
        )}

        {/* PATALPOS section */}
        <SectionHeader
          icon={Home}
          title="Patalpos"
          count={filteredRooms.length}
          summary={`${fmt(totalArea)} m²`}
          collapsed={collapsed.rooms}
          onToggle={() => toggleSection('rooms')}
          top={0}
          action={hiddenCount > 0 && onShowAllRooms ? (
            // span, not button — SectionHeader itself is a <button>, and nested
            // interactive elements are invalid HTML. stopPropagation keeps the
            // click from also toggling the section.
            <span
              role="button"
              tabIndex={0}
              onClick={(e) => { e.stopPropagation(); onShowAllRooms(); }}
              onKeyDown={(e) => {
                if (e.key === 'Enter' || e.key === ' ') { e.stopPropagation(); onShowAllRooms(); }
              }}
              className="rounded border px-1.5 whitespace-nowrap transition-colors text-primary border-primary/30 hover:bg-primary/10"
              style={{
                fontSize: 12, lineHeight: '18px',
              }}
              title="Rodyti visas paslėptas zonas plane"
            >
              Rodyti visas ({hiddenCount} paslėpta)
            </span>
          ) : null}
        />
        {!collapsed.rooms && filteredRooms.map((r, i) => {
          const targetPage = r.puslapio_nr ?? r.page_nr;
          const canJump = !!(onJumpToPage && targetPage);
          const isWet = WET_PASKIRTYS.has((r.paskirtis || '').toLowerCase());
          const isFocused = focusedRoomNr != null && String(r.nr) === String(focusedRoomNr);
          const isHidden = hiddenRoomSet.has(String(r.nr));
          return (
            <div
              key={`${r.nr}-${i}`}
              ref={isFocused ? focusedRowRef : undefined}
              onClick={canJump ? () => onJumpToPage(targetPage, r) : undefined}
              onMouseEnter={onRoomRowHover ? () => onRoomRowHover(r.nr) : undefined}
              onMouseLeave={onRoomRowHover ? () => onRoomRowHover(null) : undefined}
              className={`row-hover-halo grid items-center cursor-pointer transition-colors${isHidden ? ' opacity-50' : ''}`}
              style={{
                // v3 density: 39 px rows (24 px eye target), name and area at the 14 px interface size (were 30 px / 12 px)
                gridTemplateColumns: onToggleRoomVisibility ? '22px 1fr auto 24px' : '22px 1fr auto',
                gap: 8, padding: '7px 12px', fontSize: 14, lineHeight: '20px',
                borderBottom: '1px solid hsl(var(--border) / 0.5)',
                background: isFocused ? 'hsl(var(--primary) / 0.10)' : undefined,
                boxShadow: isFocused ? 'inset 3px 0 0 hsl(var(--primary))' : undefined,
              }}
              title={canJump ? `Atidaryti psl. ${targetPage}` : undefined}
            >
              <span className="mono tabular text-muted-foreground" style={{ fontSize: 12 }} data-testid="room-row-nr">
                {String(r.nr || i + 1).padStart(2, '0')}
              </span>
              {/* overflow-hidden: at narrow widths (audit P2, ~1000px) the fixed
                  pills used to paint straight over the area column — the grid
                  item can shrink (min-w-0) but its flex children overflowed
                  visibly. Clip instead of collide; the name truncates first. */}
              <div className="flex items-center gap-1.5 min-w-0 overflow-hidden">
                {showProvenance && (
                  <span
                    className={`dot shrink-0 ${r._source === 'manual' ? 'dot-computed' : 'dot-table'}`}
                    title={r._source === 'manual' ? 'Pažymėta brėžinyje (rankinis polygon)' : SOURCE_TITLE.table}
                  />
                )}
                <span className="text-foreground truncate" data-testid="room-row-name" title={r.pavadinimas}>{r.pavadinimas}</span>
                {/* „Sujungti" (2026-10-16): the absorbed room is billed inside the kept one — say where, never „neskaičiuojama" */}
                {(r._sujungta_i || r._sujungimas) && (
                  <span
                    className="shrink-0 text-muted-foreground whitespace-nowrap"
                    style={{ fontSize: 12 }}
                    title={r._sujungta_i
                      ? `Patalpa sujungta su ${r._sujungta_i}: jos plotas ir angos skaičiuojami patalpoje ${r._sujungta_i}`
                      : [r._sujungimas?.sakinys, r._sujungimas?.apdaila_skiriasi].filter(Boolean).join('. ')}
                    data-testid="room-merge-badge"
                  >
                    {r._sujungta_i ? `sujungta į ${r._sujungta_i}` : `+ ${(r._sujungimas?.su || []).join(', ')}`}
                  </span>
                )}
                {isWet && (
                  <span
                    className="shrink-0 text-muted-foreground"
                    style={{ fontSize: 12 }}
                    title="Drėgna patalpa — sienoms ir lubims skaičiuojamos drėgmei atsparios medžiagos ir hidroizoliacija"
                  >
                    drėgna
                  </span>
                )}
              </div>
              <span className="tabular text-foreground whitespace-nowrap inline-flex items-center gap-1.5" style={{ fontSize: 14 }}>
                <span className="mono">{roomAreaText(r.plotas_m2)}</span>
                <span className="mono text-muted-foreground" style={{ fontSize: 12 }} data-testid="room-row-unit">m²</span>
                {(() => {
                  const src = inferPlotasSource(r);
                  return src ? (
                    <ProvenanceChip
                      source={src}
                      onClick={(e) => {
                        e?.stopPropagation?.();
                        if (src === 'eksplikacija') {
                          // Honest popover with parsed row data — no PDF
                          // coordinate guessing. Anchored to the chip.
                          const rect = e.currentTarget.getBoundingClientRect();
                          setPopoverState({ room: r, anchorRect: rect });
                        } else if (onJumpToProvenance) {
                          onJumpToProvenance(r);
                        }
                      }}
                    />
                  ) : null;
                })()}
              </span>
              {onToggleRoomVisibility && (
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    if ((e.ctrlKey || e.metaKey) && onIsolateRoom) onIsolateRoom(r.nr);
                    else onToggleRoomVisibility(r.nr);
                  }}
                  className="flex items-center justify-center justify-self-end rounded text-muted-foreground hover:text-foreground hover:bg-muted transition-colors"
                  style={{ width: 24, height: 24 }}
                  title="Rodyti/slėpti kontūrą plane · Ctrl+spustelėjimas — rodyti tik šį"
                >
                  {isHidden ? <EyeOff className="w-4 h-4" /> : <Eye className="w-4 h-4" />}
                </button>
              )}
            </div>
          );
        })}
        {!collapsed.rooms && filteredRooms.length === 0 && (
          <div className="px-3 py-3 text-xs text-muted-foreground text-center">
            {filter ? `Patalpų nerasta pagal „${filter}“` : 'Patalpų dar nėra.'}
          </div>
        )}

        {/* MATAVIMAI — viewer measurements (counts + lengths/areas) */}
        {(measCountRows.length > 0 || measGeomRows.length > 0) && (
          <>
            <SectionHeader
              icon={Ruler}
              title="Matavimai"
              count={`${measCountRows.length + measGeomRows.length}`}
              collapsed={!!collapsed.meas}
              onToggle={() => toggleSection('meas')}
              top={0}
            />
            {!collapsed.meas && (measCountRows.length > 0 || measGeomRows.length > 0) && (
              /* Export the raw measurements (pre-prod audit 2026-07-25: the
                 tested export lib had no UI since the legacy toolbar died). */
              <div className="flex items-center gap-3 px-3 py-1.5 border-b border-border/50 text-meta text-muted-foreground">
                <span className="flex-1">Eksportuoti matavimus</span>
                {/* Bare "CSV" / "JSON" told a contractor nothing about what
                    lands on disk. Name the file and its use. (2026-07-28.) */}
                <button
                  type="button"
                  className="text-primary hover:underline"
                  title="Atsisiųsti matavimų lentelę CSV formatu — atsidarys Excel'iu"
                  onClick={() => exportCSVFile(
                    buildMeasureExportDoc(project),
                    `${(project?.name || 'projektas').trim()} - matavimai.csv`,
                  )}
                >CSV</button>
                <button
                  type="button"
                  className="text-primary hover:underline"
                  title="Atsisiųsti matavimus JSON formatu — skirta perkelti į kitą programą"
                  onClick={() => exportJSONFile(
                    buildMeasureExportDoc(project),
                    `${(project?.name || 'projektas').trim()} - matavimai.json`,
                  )}
                >JSON</button>
              </div>
            )}
            {!collapsed.meas && measCountRows.map((r) => (
              <div
                key={r.typeId}
                data-measure-row={`count:${r.typeId}`}
                className={`flex items-center gap-2.5 px-3 py-2.5 border-b border-border/50 text-ui ${onJumpToPage && r.firstPage ? 'cursor-pointer hover:bg-muted/40' : ''} ${revealKey === `count:${r.typeId}` ? 'bg-primary/10 ring-1 ring-inset ring-primary/40' : ''}`}
                onClick={onJumpToPage && r.firstPage ? () => onJumpToPage(r.firstPage) : undefined}
                title={r.firstPage ? `Rodyti brėžinyje (psl. ${r.firstPage})` : undefined}
              >
                <span className="w-2 h-2 rounded-full shrink-0" style={{ background: r.color }} />
                <span className="flex-1 min-w-0 truncate">{r.label}</span>
                {r.ai > 0 && (
                  <span
                    className={`w-2 h-2 rounded-full shrink-0 ${CONFIDENCE_DOT_CLASS[normalizeConfidence('yellow')]}`}
                    title={`${confidenceLabel('yellow')}: ${r.ai} iš ${r.count} rasta automatiškai („Rasti panašius") — peržiūrėkite brėžinyje`}
                    data-testid="meas-ai-dot"
                  />
                )}
                <span className="font-mono tabular-nums text-foreground">{r.count} vnt.</span>
                <button
                  type="button"
                  onClick={(e) => { e.stopPropagation(); addCountToEstimate(r); }}
                  className="text-primary hover:underline shrink-0"
                  title="Įtraukti kiekį į sąmatą (kainą suvesite patys)"
                >
                  Į sąmatą
                </button>
              </div>
            ))}
            {!collapsed.meas && measGeomRows.map((m) => (
              <div
                key={m.id}
                data-measure-row={`meas:${m.id}`}
                className={`flex items-center gap-2.5 px-3 py-2.5 border-b border-border/50 text-ui ${onJumpToPage && m.page ? 'cursor-pointer hover:bg-muted/40' : ''} ${revealKey === `meas:${m.id}` ? 'bg-primary/10 ring-1 ring-inset ring-primary/40' : ''}`}
                onClick={onJumpToPage && m.page ? () => onJumpToPage(m.page) : undefined}
                title={m.page ? `Rodyti brėžinyje (psl. ${m.page})` : undefined}
              >
                <span className="flex-1 min-w-0 truncate text-muted-foreground">{m.label} · psl. {m.page}</span>
                <span className={`font-mono tabular-nums ${m.display === NO_SCALE ? 'text-muted-foreground' : 'text-foreground'}`}>
                  {m.display}
                </span>
              </div>
            ))}
          </>
        )}

        {/* KIEKIAI section */}
        <SectionHeader
          icon={FileText}
          title="Kiekiai"
          count={`${totalPositions} poz.`}
          summary={totalNet > 0 ? fmtEur(totalNet) : ''}
          collapsed={!!collapsed.kiekiai}
          onToggle={() => toggleSection('kiekiai')}
          top={0}
        />
        {/* LT contractors habitually quote a work rate „su medžiagomis". Since
            the materials became their own section, entering an all-in rate on a
            work row AND letting the kainynas price the materials bills the same
            purchase twice — so say what these prices are. (2026-09-02) */}
        {!collapsed.kiekiai && (
          <div className="px-3 py-1.5 text-muted-foreground"
               style={{ fontSize: 12, lineHeight: 1.4,
                        background: 'hsl(var(--muted) / 0.25)',
                        borderBottom: '1px solid hsl(var(--border) / 0.5)' }}>
            {t('project.mainView.worksAreLabourOnly')}
          </div>
        )}
        {!collapsed.kiekiai && positionGroups.map(group => (
          <PositionGroup
            key={group.skyrius}
            group={group}
            collapsed={collapsed[`sk:${group.skyrius}`]}
            onToggle={() => toggleSection(`sk:${group.skyrius}`)}
            showProvenance={showProvenance}
            onRowClick={handleRowClick}
            onQuantityChange={handleQuantityChange}
            onQuantityAdjust={handleQuantityAdjust}
            onPriceChange={handlePriceChange}
            onRemoveRow={handleRowRemove}
          />
        ))}
        {positionGroups.length === 0 && filter && (
          <div className="px-3 py-6 text-xs text-muted-foreground text-center">
            Pozicijų nerasta pagal „{filter}“.
          </div>
        )}

        {/* SIENŲ IŠKLOTINĖS — Sprint §21 (2026-04-29) — render mm-precision
            tile/paint/niche/furniture zones from wall_elevation extractor. */}
        {Array.isArray(project._wall_elevations) && project._wall_elevations.length > 0 && (
          <WallElevationsPanel wallElevations={project._wall_elevations} />
        )}

        {/* PLYTELIŲ SPECIFIKACIJA — auto-detected tile sizes from PDF text layer.
            Shown after Kiekiai section so user sees what's been read. */}
        {Array.isArray(project._plyteliu_specs) && project._plyteliu_specs.length > 0 && (
          <PlyteliuSpecsSection specs={project._plyteliu_specs} />
        )}
      </div>
      {openDetailRow && (
        <RowDetailPanel
          row={openDetailRow}
          rooms={allRooms}
          onClose={() => setDetailRow(null)}
          onFocusRoom={onJumpToPage}
          onOpenAssumptions={onOpenAssumptions}
          projectId={project?.id}
        />
      )}
      {popoverState && (
        <EksplikacijaSourcePopover
          room={popoverState.room}
          anchorRect={popoverState.anchorRect}
          onClose={() => setPopoverState(null)}
        />
      )}
    </div>
  );
}

// ── Plytelių specifikacija section (auto-detected sizes from PDF) ────────
function PlyteliuSpecsSection({ specs }) {
  const [open, setOpen] = useState(false);
  // Group by size_mm + where for cleaner display
  const grouped = useMemo(() => {
    const map = new Map();
    for (const s of specs) {
      const key = `${s.size_mm}|${s.where}`;
      if (!map.has(key)) {
        map.set(key, {
          size_mm: s.size_mm,
          where: s.where,
          format_label: s.format_label,
          brand: s.brand,
          pages: new Set([s.page]),
          count: 0,
        });
      }
      const g = map.get(key);
      g.pages.add(s.page);
      g.count++;
    }
    return Array.from(map.values()).sort((a, b) => b.count - a.count);
  }, [specs]);

  const WHERE_LT = {
    vonia: 'Vonios', wc: 'WC', san: 'San. mazgo', virtuve: 'Virtuvės',
    nisos: 'Nišų', kita: 'Kita',
  };

  return (
    <div>
      <button
        onClick={() => setOpen(v => !v)}
        className="w-full flex items-center justify-between text-left transition-colors hover:bg-muted/40"
        style={{
          background: 'hsl(var(--bg-1))',
          borderTop: '1px solid hsl(var(--border))',
          borderBottom: '1px solid hsl(var(--border) / 0.5)',
          padding: '8px 12px', cursor: 'pointer',
        }}
      >
        <div className="flex items-center gap-2">
          {open
            ? <ChevronDown className="w-3 h-3 text-muted-foreground" />
            : <ChevronRight className="w-3 h-3 text-muted-foreground" />}
          <span className="skyrius-header">Plytelių specifikacija (iš brėžinio)</span>
          <span className="mono tabular text-muted-foreground" style={{ fontSize: 12 }}>
            {grouped.length} unik. dydžiai
          </span>
        </div>
      </button>
      {open && grouped.map((g, i) => (
        <div
          key={`${g.size_mm}-${g.where}-${i}`}
          className="grid items-center"
          style={{
            gridTemplateColumns: '14px 1fr auto auto',
            gap: 8, padding: '7px 12px', fontSize: 12,
            borderBottom: '1px solid hsl(var(--border) / 0.5)',
          }}
        >
          <span />
          <div className="min-w-0 flex items-center gap-2">
            <span className="mono tabular font-medium" style={{ fontSize: 12 }}>
              {g.size_mm}
            </span>
            <span className="text-muted-foreground" style={{ fontSize: 12 }}>
              {WHERE_LT[g.where] || g.where}
            </span>
            {g.format_label && (
              <span
                className="text-muted-foreground"
                style={{ fontSize: 12 }}
              >
                {g.format_label}
              </span>
            )}
            {g.brand && (
              <span className="text-foreground/70" style={{ fontSize: 12 }}>
                {g.brand}
              </span>
            )}
          </div>
          <span className="mono tabular text-muted-foreground" style={{ fontSize: 12 }}>
            psl. {Array.from(g.pages).sort((a, b) => a - b).join(', ')}
          </span>
        </div>
      ))}
    </div>
  );
}

// ── Section header (sticky) ──────────────────────────────────────────────
function SectionHeader({ icon: Icon, title, count, summary, collapsed, onToggle, top = 0, action = null }) {
  const isToggleable = !!onToggle;
  return (
    <button
      onClick={onToggle || undefined}
      disabled={!isToggleable}
      className="w-full flex items-center justify-between text-left transition-colors"
      style={{
        position: 'sticky', top, zIndex: 2,
        background: 'hsl(var(--background))',
        borderTop: '1px solid hsl(var(--border))',
        borderBottom: '1px solid hsl(var(--border))',
        padding: '9px 12px',
        cursor: isToggleable ? 'pointer' : 'default',
      }}
    >
      <div className="flex items-center gap-2">
        {isToggleable
          ? (collapsed
              ? <ChevronRight className="w-3.5 h-3.5 text-muted-foreground" />
              : <ChevronDown className="w-3.5 h-3.5 text-muted-foreground" />)
          : <span style={{ width: 14 }} />}
        {Icon && <Icon className="w-3.5 h-3.5 text-muted-foreground" />}
        {/* sentence case at the interface size (was a 10 px uppercase tracked eyebrow) */}
        <span className="text-ui font-semibold text-foreground">{title}</span>
        <span className="mono tabular text-muted-foreground" style={{ fontSize: 12 }}>
          {count}
        </span>
      </div>
      <span className="flex items-center gap-2">
        {action}
        <span className="mono tabular text-muted-foreground" style={{ fontSize: 12 }}>
          {summary}
        </span>
      </span>
    </button>
  );
}

// ── Position group (sub-section: skyrius) ────────────────────────────────
// Memo'd: only re-renders when its own group data, collapsed state, or
// callbacks change. Filter / scroll / room hover in parent doesn't ripple
// down to all groups.
const PositionGroup = memo(function PositionGroup({
  group,
  collapsed,
  onToggle,
  showProvenance,
  onRowClick,
  onQuantityChange,
  onQuantityAdjust,
  onPriceChange,
  onRemoveRow,
}) {
  return (
    <div>
      <button
        onClick={onToggle}
        className="w-full grid items-center text-left transition-colors hover:bg-muted/40"
        style={{
          gridTemplateColumns: '14px 1fr auto auto',
          gap: 8,
          background: 'hsl(var(--bg-1))',
          borderBottom: '1px solid hsl(var(--border) / 0.5)',
          padding: '8px 12px',
          cursor: 'pointer',
        }}
      >
        {collapsed
          ? <ChevronRight className="w-3 h-3 text-muted-foreground" />
          : <ChevronDown className="w-3 h-3 text-muted-foreground" />}
        <span
          className="text-foreground font-semibold"
          style={{ fontSize: 14 }}
        >
          {group.skyrius}
        </span>
        <span className="mono tabular text-muted-foreground" style={{ fontSize: 12 }}>
          {group.rows.length}
        </span>
        <span className="mono tabular text-foreground/90" style={{ fontSize: 12 }}>
          {fmtEur(group.subtotal)}
        </span>
      </button>
      {!collapsed && group.rows.map((row, idx) => (
        <PositionRow
          /* id + index, never a bare id: a merge can carry an orphaned prior
             row that keeps an id the rebuilt row also has, and React would
             then reuse one row's editor state under the other's numbers. */
          key={`${row.id || row.eil_nr || 'r'}-${idx}`}
          row={row}
          showProvenance={showProvenance}
          onClick={() => onRowClick?.(row)}
          onQuantityChange={(q) => onQuantityChange(row._id || `${row.eil_nr}-${row.aprasymas}`, q)}
          onQuantityAdjust={(delta) => onQuantityAdjust(row._id || `${row.eil_nr}-${row.aprasymas}`, delta)}
          onPriceChange={(p) => onPriceChange(row._id || `${row.eil_nr}-${row.aprasymas}`, p)}
          onRemove={onRemoveRow ? () => onRemoveRow(row) : null}
        />
      ))}
    </div>
  );
});

// ── Position row — primary unit, prototype style ─────────────────────────
// Memo'd: editing one row's price doesn't re-render adjacent rows. Saves
// significant work on 80+ row projects.
const PositionRow = memo(function PositionRow({
  row,
  showProvenance,
  onClick,
  onQuantityChange,
  onQuantityAdjust,
  onPriceChange,
  onRemove,
}) {
  const { t } = useTranslation();
  const [editing, setEditing] = useState(false);
  const [draftPrice, setDraftPrice] = useState('');
  const [editingQty, setEditingQty] = useState(false);
  const [draftQty, setDraftQty] = useState('');

  const sourceClass = `dot-${classifySource(row)}`;
  const sourceKind = getQuantitySourceKind(row);
  const sourceLabel = getQuantitySourceLabel(row);
  const sourceBadgeStyle = {
    ai_symbol: {
      border: '1px solid hsl(var(--destructive) / 0.35)',
      color: 'hsl(var(--destructive))',
      background: 'hsl(var(--destructive) / 0.08)',
    },
    assumption: {
      border: '1px solid hsl(var(--warning, 38 92% 50%) / 0.45)',
      color: 'hsl(var(--warning, 38 92% 50%))',
      background: 'hsl(var(--warning, 38 92% 50%) / 0.08)',
    },
    manual: {
      border: '1px solid hsl(var(--source-table) / 0.35)',
      color: 'hsl(var(--source-table))',
      background: 'hsl(var(--source-table) / 0.08)',
    },
    verified: {
      border: '1px solid hsl(var(--source-table) / 0.35)',
      color: 'hsl(var(--source-table))',
      background: 'hsl(var(--source-table) / 0.08)',
    },
  }[sourceKind] || {
    border: '1px solid hsl(var(--border))',
    color: 'hsl(var(--muted-foreground))',
    background: 'hsl(var(--muted) / 0.35)',
  };
  // Backend stamps LT tiers (zalia/geltona/raudona); legacy blobs carry EN —
  // normalize, or engine-flagged rows render as confident green (P0 2026-08-03).
  const confTier = normalizeConfidence(row.confidence);
  const confClass = CONFIDENCE_DOT_CLASS[confTier];
  // „Pasitikėjimas" is banned on screen (design §1) — the tier label already
  // says what to do („Skaityta tiesiogiai" / „Patikrinti" / „Būtina patikrinti").
  const confTitle = `${confidenceLabel(confTier)}${row._confidence_reason ? ` — ${cleanUserText(row._confidence_reason)}` : ''}`;
  const sum = (row.kiekis || 0) * (row.kaina || 0);
  const isManualQty = row.manual_override === true || row.quantity_source === 'manual_override';
  const isCountUnit = String(row.mato_vnt || '').toLowerCase().includes('vnt');
  const kainynasPriced = row.kaina_source === 'kainynas';
  // The matcher scores 1.0 only when the two descriptions are the same once
  // folded; anything less is a judgement call the user should see.
  const approxMatch = kainynasPriced
    && row.kaina_match_score != null && row.kaina_match_score < 1;

  const beginEdit = (e) => {
    e.stopPropagation();
    setDraftPrice(String(row.kaina || 0).replace('.', ','));
    setEditing(true);
  };

  const beginQtyEdit = (e) => {
    e.stopPropagation();
    setDraftQty(String(row.kiekis ?? 0).replace('.', ','));
    setEditingQty(true);
  };

  // parseLtNumber: the old `.replace(',', '.')` only swapped the FIRST comma
  // and left spaced thousands intact, so "1 234,56" parsed as 1. Invalid input
  // now keeps the editor open instead of silently discarding what was typed.
  const commitQty = () => {
    const num = parseLtNumber(draftQty);
    if (!isValidAmount(num)) return;
    onQuantityChange(num);
    setEditingQty(false);
  };

  const commit = () => {
    const num = parseLtNumber(draftPrice);
    if (!isValidAmount(num)) return;
    onPriceChange(num);
    setEditing(false);
  };

  return (
    <div
      onClick={onClick}
      title={t('project.mainView.openLedgerTitle')}
      className="grid items-start cursor-pointer hover:bg-muted/40 transition-colors group"
      style={{
        // Narrowed kiekis/kaina/suma columns from 104/86/86 → 88/72/76 so
        // the description column gets back ~40 px when the right-side
        // Kiekiai panel is half-width (Brėžinys tab). Description also
        // wraps now (whitespace-normal below) instead of truncating with
        // ellipsis, so a name like "Sienų antrinis glaistymas Q2" fits on
        // two lines rather than being cut to "Sienų antrinis g...".
        // v3 density: 36 px rows. The six-column numeric table stays at the 12 px metadata size —
        // at 14 px its sum column overflows the 400 px panel (and W1-A narrows it to 340).
        gridTemplateColumns: '12px 32px 1fr 88px 72px 76px',
        gap: 6, padding: '9px 12px', fontSize: 12,
        borderBottom: '1px solid hsl(var(--border) / 0.5)',
      }}
    >
      {/* Every quantity row shows its confidence dot (🟢/🟡/🔴) by default —
          founder ask 2026-07-09, CLAUDE.md §7 ("indicator on every quantity").
          The Pažangu toggle swaps it for the source dot (table/computed/AI). */}
      {showProvenance ? (
        <span className={`dot ${sourceClass}`} title={SOURCE_TITLE[classifySource(row)]} />
      ) : (
        <span className={`dot ${confClass}`} title={confTitle} />
      )}
      <span className="mono tabular text-muted-foreground" style={{ fontSize: 12 }}>
        {row.eil_nr || ''}
      </span>
      <div className="flex items-start gap-1.5 min-w-0">
        <span
          className="text-foreground/90 leading-snug break-words"
          title={cleanUserText(row.review_reason || row._confidence_reason || row.calculation_basis || sourceLabel)}
        >
          {row.aprasymas}
        </span>
        {/* 2026-05-06: source badge (FORMULĖ / PRIELAIDA / AI ŽENKLAS / RANKINIS)
            removed per user request — visual clutter, no actionable signal.
            Tooltip on aprašymas keeps the source readable on hover. */}
      </div>
      {editingQty ? (
        <input
          autoFocus
          onFocus={(e) => e.target.select()}
          value={draftQty}
          onChange={e => setDraftQty(e.target.value)}
          onBlur={commitQty}
          onKeyDown={e => {
            if (e.key === 'Enter') commitQty();
            if (e.key === 'Escape') setEditingQty(false);
          }}
          onClick={e => e.stopPropagation()}
          placeholder="0,00"
          aria-label="Kiekis"
          title="Kiekis; kablelis arba taškas — abu tinka. Enter — įrašyti, Esc — atsisakyti."
          className="mono tabular bg-card border border-primary rounded outline-none text-right"
          style={{ fontSize: 12, height: 22, padding: '2px 6px' }}
        />
      ) : (
        <div className="flex items-center justify-end gap-1">
          {isCountUnit && (
            <button
              type="button"
              onClick={(e) => { e.stopPropagation(); onQuantityAdjust(-1); }}
              className="w-5 h-5 rounded border border-border text-muted-foreground hover:border-destructive hover:text-destructive transition-colors"
              title="Atimti 1"
            >
              −
            </button>
          )}
          <button
            type="button"
            onClick={beginQtyEdit}
            className="mono tabular text-foreground/90 whitespace-nowrap text-right rounded px-1 py-0.5 hover:bg-primary/10 hover:text-primary transition-colors"
            style={{ fontSize: 12 }}
            title="Spustelėkite, norėdami pataisyti kiekį"
          >
            {fmt(row.kiekis)}
            <span className="text-muted-foreground ml-1" style={{ fontSize: 12 }}>{row.mato_vnt}</span>
            {isManualQty && (
              <span
                className="ml-1 font-semibold"
                style={{
                  fontSize: 12,
                  color: 'hsl(var(--source-table))',
                }}
                title="Kiekį įrašėte ranka — ankstesnis skaičius pakeistas"
              >
                rank.
              </span>
            )}
          </button>
          {isCountUnit && (
            <button
              type="button"
              onClick={(e) => { e.stopPropagation(); onQuantityAdjust(1); }}
              className="w-5 h-5 rounded border border-border text-muted-foreground hover:border-accent-2 hover:text-accent-2 transition-colors"
              title="Pridėti 1"
            >
              +
            </button>
          )}
        </div>
      )}
      {editing ? (
        <input
          autoFocus
          onFocus={(e) => e.target.select()}
          value={draftPrice}
          onChange={e => setDraftPrice(e.target.value)}
          onBlur={commit}
          onKeyDown={e => {
            if (e.key === 'Enter') commit();
            if (e.key === 'Escape') setEditing(false);
          }}
          onClick={e => e.stopPropagation()}
          placeholder="0,00"
          aria-label="Vieneto kaina, €"
          title="Vieneto kaina eurais be PVM; kablelis arba taškas — abu tinka. Enter — įrašyti, Esc — atsisakyti."
          className="mono tabular bg-card border border-primary rounded outline-none text-right"
          style={{ fontSize: 12, height: 22, padding: '2px 6px' }}
        />
      ) : (
        <span
          onClick={beginEdit}
          className="mono tabular cursor-text whitespace-nowrap inline-flex items-center justify-end gap-1"
          style={{
            fontSize: 12,
            color: 'hsl(var(--muted-foreground))',
            textAlign: 'right',
            textUnderlineOffset: 2,
          }}
          title={kainynasPriced
            ? (approxMatch
              ? t('project.mainView.priceFromKainynasSimilarTitle')
              : t('project.mainView.priceFromKainynasTitle'))
            : 'Spustelėkite, norėdami redaguoti kainą'}
        >
          <span className="group-hover:underline group-hover:decoration-dotted">
            {row.kaina ? `${row.kaina.toFixed(2)} €` : '—'}
          </span>
          {/* WHERE the price came from. `kaina_source` has been written since
              the kainynas shipped and nothing read it — so a price the matcher
              guessed at from a merely SIMILAR row looked exactly like one the
              contractor typed. Amber says "check this one". (2026-09-02) */}
          {row.kaina && kainynasPriced && (
            <span
              aria-hidden="true"
              className="shrink-0 rounded-full"
              style={{
                width: 5, height: 5,
                background: approxMatch
                  ? 'hsl(var(--warning, 38 92% 50%))'
                  : 'hsl(var(--primary) / 0.5)',
              }}
            />
          )}
        </span>
      )}
      <span className="mono tabular text-foreground font-medium whitespace-nowrap"
        style={{ fontSize: 12, textAlign: 'right' }}>
        {row.kaina ? `${sum.toLocaleString('lt-LT', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} €` : '—'}
      </span>
      {/* Medžiagos rows say which work they belong to — without it a bare
          "Gruntas" line in the shopping list is unreadable. (2026-09-02) */}
      {row.susijes_darbas && (
        <div
          className="col-span-6 text-muted-foreground truncate"
          style={{
            gridColumn: 'span 6 / span 6',
            fontSize: 12, paddingLeft: 18, paddingTop: 2, lineHeight: 1.3,
          }}
          title={row.susijes_darbas}
        >
          {t('project.mainView.materialFor', { work: row.susijes_darbas })}
        </div>
      )}
      {/* A row the last recompute could not reproduce is CARRIED, not deleted —
          its quantity is the old one. The flag existed since 2026-07-28 and
          nothing rendered it, so the user could not tell a stale line from a
          fresh one, let alone act on it. (2026-09-02) */}
      {row._orphaned_after_rebuild && (
        <div
          className="col-span-6 flex items-center gap-1.5"
          style={{ gridColumn: 'span 6 / span 6', paddingLeft: 18, paddingTop: 3 }}
        >
          <span
            className="inline-flex items-center gap-1 rounded px-1 font-semibold"
            style={{
              fontSize: 12, lineHeight: '16px',
              border: '1px solid hsl(var(--warning, 38 92% 50%) / 0.45)',
              color: 'hsl(var(--warning, 38 92% 50%))',
              background: 'hsl(var(--warning, 38 92% 50%) / 0.08)',
            }}
            title={t('project.mainView.orphanTitle')}
          >
            <AlertCircle style={{ width: 9, height: 9 }} />
            {t('project.mainView.orphanBadge')}
          </span>
          {onRemove && (
            <button
              type="button"
              onClick={(e) => { e.stopPropagation(); onRemove(); }}
              className="underline decoration-dotted text-muted-foreground hover:text-destructive"
              style={{ fontSize: 12, textUnderlineOffset: 2 }}
              title={t('project.mainView.removeTitle')}
            >
              {t('project.mainView.orphanRemove')}
            </button>
          )}
        </div>
      )}
      {(row._detail_m2 != null || row._detail_juostele_m != null) && (
        <div
          className="col-span-6 text-muted-foreground"
          style={{
            gridColumn: 'span 6 / span 6',
            fontSize: 12, paddingLeft: 18, paddingTop: 2, lineHeight: 1.3,
          }}
        >
          {row._detail_m2 != null && (
            <span className="mono tabular">{row._detail_m2.toFixed(2)} m² · </span>
          )}
          {row._detail_juostele_m != null && (
            <span className="mono tabular">{row._detail_juostele_m.toFixed(2)} m juostelės</span>
          )}
        </div>
      )}
      {isManualQty && row.ai_kiekis_original != null && (
        <div
          className="col-span-6 text-muted-foreground"
          style={{
            gridColumn: 'span 6 / span 6',
            fontSize: 12, paddingLeft: 18, paddingTop: 2, lineHeight: 1.3,
          }}
        >
          iš brėžinio buvo <span className="mono tabular">{fmt(row.ai_kiekis_original)}</span>
          {row.mato_vnt && <span className="ml-1">{row.mato_vnt}</span>}
        </div>
      )}
    </div>
  );
});
