/**
 * WorkspacePanel — right-side panel in Brėžinys tab. Mirrors claude.ai/design
 * prototype's `screen-positions.jsx`: filter at top + Patalpos + Kiekiai
 * sections (collapsible per skyrius). Each position row has source dot,
 * confidence dot, qty, inline-edit price, and sum. Click row → jump PDF.
 *
 * Replaces previous rooms-only table layout with positions-aware unified panel.
 */

import { useState, useMemo, useEffect, useCallback, memo, useRef } from 'react';
import {
  Search, ChevronDown, ChevronRight, Home, FileText, Eye, EyeOff, Ruler,
} from 'lucide-react';
import { loadTakeoff, removePolygon, saveTakeoff, subscribeTakeoff } from '@/lib/takeoffStore';
import { measurementValue, DEFAULT_COUNT_TYPES } from '@/lib/measurements';
import { autoPageScalesFromRooms } from '@/lib/durableScale';
import { exportCSVFile, exportJSONFile } from '@/lib/measureExport';
import { buildMeasureExportDoc } from '@/lib/measureExportDoc';
import { parseLtNumber, isValidAmount } from '@/lib/parseLtNumber';
import { updateProject } from '@/lib/projectStore';
import { adjustPositionQuantity, updatePositionQuantity } from '@/lib/quantityOverride';
import { getQuantitySourceKind, getQuantitySourceLabel } from '@/lib/takeoffWorkflow';
import ReviewQueueSidebar from './ReviewQueueSidebar';
import WallElevationsPanel from './WallElevationsPanel';
import ConfidenceBadge from './ConfidenceBadge';
import ProvenanceChip from './ProvenanceChip';
import EksplikacijaSourcePopover from './EksplikacijaSourcePopover';
import { useConfirm } from '@/components/ui/confirm-provider';
import { inferPlotasSource } from '@/lib/areaConfidence';

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

const CONF_TITLE = {
  high: 'Aukštas pasitikėjimas',
  medium: 'Vidutinis pasitikėjimas',
  low: 'Žemas pasitikėjimas — privaloma patikrinti',
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
}) {
  const confirm = useConfirm();
  const [takeoff, setTakeoff] = useTakeoff(project.id);
  const [filter, setFilter] = useState('');
  // Provenance dots OFF by default — too noisy when most rows are computed.
  // User can toggle via eye icon to inspect data sources when needed.
  const [showProvenance, setShowProvenance] = useState(false);
  const [collapsed, setCollapsed] = useState({});
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

  const totalArea = allRooms.reduce((s, r) => s + (r.plotas_m2 || 0), 0);

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
      if (cur) {
        cur.count += 1;
        if (m.page && (!cur.firstPage || m.page < cur.firstPage)) cur.firstPage = m.page;
      } else {
        const type = (project.countTypes || []).find((t) => t.id === m.typeId)
          || DEFAULT_COUNT_TYPES.find((t) => t.id === m.typeId);
        byType.set(m.typeId, {
          typeId: m.typeId,
          label: type?.label || m.typeId,
          color: m.color || type?.color || 'hsl(var(--primary))',
          count: 1,
          firstPage: m.page || null,
        });
      }
    }
    return [...byType.values()];
  }, [projMeasurements, project.countTypes]);
  const measGeomRows = useMemo(() => {
    const KIND_LT = { distance: 'Atstumas', perimeter: 'Perimetras', area: 'Plotas' };
    // Same merge as the viewer: pages auto-calibrated from their traced rooms
    // read real meters here too; a user calibration overrides.
    const autoScales = autoPageScalesFromRooms(project.v8_rooms || project.patalpos || []);
    return projMeasurements
      .filter((m) => KIND_LT[m.kind])
      .map((m) => {
        const scale = project.pageScalesDurable?.[m.page]
          ?? project.pageScalesDurable?.[String(m.page)]
          ?? autoScales[m.page] ?? null;
        let display = 'nekalibruota';
        if (scale) {
          const { value } = measurementValue(m, scale);
          display = m.kind === 'area' ? `${fmt(value, 2)} m²` : `${fmt(value, 2)} m`;
        }
        return { id: m.id, label: KIND_LT[m.kind], page: m.page, display };
      });
  }, [projMeasurements, project.pageScalesDurable, project.v8_rooms, project.patalpos]);

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
        confidence: 'high',
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
      return { ...it, kaina, suma: (it.kiekis || 0) * kaina };
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

  const handleQuantityAdjust = useCallback((rowId, delta) => {
    if (!onProjectChange) return;
    const updated = adjustPositionQuantity(project.darbu_sarasas || [], rowId, delta);
    onProjectChange({ ...project, darbu_sarasas: updated });
  }, [project, onProjectChange]);

  // Stable row click — same memo logic
  const handleRowClick = useCallback((row) => {
    const r = (project.v8_rooms || project.patalpos || []).find(rr => rr.nr === row._room_nr);
    if (r && onJumpToPage) onJumpToPage(r.puslapio_nr, r);
  }, [project.v8_rooms, project.patalpos, onJumpToPage]);

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
          <Search className="absolute left-2 top-2 w-3 h-3 text-muted-foreground" />
          <input
            type="text"
            placeholder="Filtruoti pozicijas, patalpas…"
            value={filter}
            onChange={e => setFilter(e.target.value)}
            className="w-full pl-7 pr-2.5 text-foreground bg-card border border-border rounded outline-none focus:border-primary"
            style={{ fontSize: 12, height: 28 }}
          />
        </div>
        <button
          onClick={() => setShowProvenance(v => !v)}
          title={showProvenance ? 'Slėpti šaltinio taškus' : 'Rodyti šaltinio taškus'}
          className="rounded border flex items-center justify-center transition-colors"
          style={{
            height: 28, width: 28,
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
        {/* PERŽIŪRA — confidence-driven review queue (Sprint G2) */}
        <ReviewQueueSidebar
          rooms={allRooms}
          positions={project.darbu_sarasas || []}
          eksplikacijaSourcePage={project?._eksplikacija?.eksplikacija_source_page}
          onJumpToPage={onJumpToPage}
          onEditRoom={onEditRoomZone}
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
                fontSize: 10, lineHeight: '16px',
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
                gridTemplateColumns: onToggleRoomVisibility ? '24px 1fr auto 20px' : '24px 1fr auto',
                gap: 8, padding: '6px 12px', fontSize: 12,
                borderBottom: '1px solid hsl(var(--border) / 0.5)',
                background: isFocused ? 'hsl(var(--primary) / 0.10)' : undefined,
                boxShadow: isFocused ? 'inset 3px 0 0 hsl(var(--primary))' : undefined,
              }}
              title={canJump ? `Atidaryti psl. ${targetPage}` : undefined}
            >
              <span className="mono tabular text-muted-foreground" style={{ fontSize: 10 }}>
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
                <span className="text-foreground/90 truncate">{r.pavadinimas}</span>
                {isWet && (
                  <span
                    className="px-1 py-0 rounded font-medium uppercase tracking-wide"
                    style={{
                      fontSize: 9, lineHeight: '14px',
                      border: '1px solid hsl(var(--source-ai) / 0.4)',
                      color: 'hsl(var(--source-ai))',
                    }}
                  >
                    drėgna
                  </span>
                )}
                <ConfidenceBadge
                  room={r}
                  projectId={project?.id}
                  onClick={(e) => {
                    e?.stopPropagation?.();
                    if (onJumpToPage && targetPage) onJumpToPage(targetPage, r);
                  }}
                />
              </div>
              <span className="mono tabular text-foreground/90 whitespace-nowrap inline-flex items-center gap-1.5" style={{ fontSize: 11 }}>
                {fmt(r.plotas_m2)}
                <span className="text-muted-foreground/70" style={{ fontSize: 9 }}>m²</span>
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
                  className="flex items-center justify-center justify-self-end text-muted-foreground hover:text-foreground transition-colors"
                  style={{ width: 16, height: 16 }}
                  title="Rodyti/slėpti zoną plane · Ctrl+spustelėjimas — rodyti tik šią"
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
              <div className="flex items-center gap-3 px-3 py-1.5 border-b border-border/50 text-[11px] text-muted-foreground">
                <span className="flex-1">Eksportuoti matavimus</span>
                <button
                  type="button"
                  className="text-primary hover:underline"
                  onClick={() => exportCSVFile(
                    buildMeasureExportDoc(project),
                    `${(project?.name || 'projektas').trim()} - matavimai.csv`,
                  )}
                >CSV</button>
                <button
                  type="button"
                  className="text-primary hover:underline"
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
                className={`flex items-center gap-2.5 px-3 py-2 border-b border-border/50 text-xs ${onJumpToPage && r.firstPage ? 'cursor-pointer hover:bg-muted/40' : ''}`}
                onClick={onJumpToPage && r.firstPage ? () => onJumpToPage(r.firstPage) : undefined}
                title={r.firstPage ? `Rodyti brėžinyje (psl. ${r.firstPage})` : undefined}
              >
                <span className="w-2 h-2 rounded-full shrink-0" style={{ background: r.color }} />
                <span className="flex-1 min-w-0 truncate">{r.label}</span>
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
                className={`flex items-center gap-2.5 px-3 py-2 border-b border-border/50 text-xs ${onJumpToPage && m.page ? 'cursor-pointer hover:bg-muted/40' : ''}`}
                onClick={onJumpToPage && m.page ? () => onJumpToPage(m.page) : undefined}
                title={m.page ? `Rodyti brėžinyje (psl. ${m.page})` : undefined}
              >
                <span className="flex-1 min-w-0 truncate text-muted-foreground">{m.label} · psl. {m.page}</span>
                <span className={`font-mono tabular-nums ${m.display === 'nekalibruota' ? 'text-muted-foreground' : 'text-foreground'}`}>
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
          summary={fmtEur(totalNet)}
          collapsed={false}
          onToggle={null}
          top={0}
        />
        {positionGroups.map(group => (
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
          <span className="mono tabular text-muted-foreground/70" style={{ fontSize: 10 }}>
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
            <span className="mono tabular font-medium" style={{ fontSize: 11 }}>
              {g.size_mm}
            </span>
            <span className="text-muted-foreground" style={{ fontSize: 10 }}>
              {WHERE_LT[g.where] || g.where}
            </span>
            {g.format_label && (
              <span
                className="px-1 py-0 rounded uppercase tracking-wide font-medium"
                style={{
                  fontSize: 9, lineHeight: '14px',
                  border: '1px solid hsl(var(--border-strong))',
                  color: 'hsl(var(--muted-foreground))',
                }}
              >
                {g.format_label}
              </span>
            )}
            {g.brand && (
              <span className="text-foreground/70" style={{ fontSize: 10 }}>
                {g.brand}
              </span>
            )}
          </div>
          <span className="mono tabular text-muted-foreground/70" style={{ fontSize: 10 }}>
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
        padding: '8px 12px',
        cursor: isToggleable ? 'pointer' : 'default',
      }}
    >
      <div className="flex items-center gap-2">
        {isToggleable
          ? (collapsed
              ? <ChevronRight className="w-3 h-3 text-muted-foreground" />
              : <ChevronDown className="w-3 h-3 text-muted-foreground" />)
          : <span style={{ width: 12 }} />}
        {Icon && <Icon className="w-3 h-3 text-muted-foreground" />}
        <span className="skyrius-header">{title}</span>
        <span className="mono tabular text-muted-foreground/70" style={{ fontSize: 10 }}>
          {count}
        </span>
      </div>
      <span className="flex items-center gap-2">
        {action}
        <span className="mono tabular text-muted-foreground" style={{ fontSize: 10 }}>
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
          className="text-foreground font-semibold uppercase"
          style={{ fontSize: 11, letterSpacing: '0.04em' }}
        >
          {group.skyrius}
        </span>
        <span className="mono tabular text-muted-foreground/70" style={{ fontSize: 10 }}>
          {group.rows.length}
        </span>
        <span className="mono tabular text-foreground/90" style={{ fontSize: 11 }}>
          {fmtEur(group.subtotal)}
        </span>
      </button>
      {!collapsed && group.rows.map((row, idx) => (
        <PositionRow
          key={`${row.eil_nr || idx}-${row.aprasymas}`}
          row={row}
          showProvenance={showProvenance}
          onClick={() => onRowClick?.(row)}
          onQuantityChange={(q) => onQuantityChange(row._id || `${row.eil_nr}-${row.aprasymas}`, q)}
          onQuantityAdjust={(delta) => onQuantityAdjust(row._id || `${row.eil_nr}-${row.aprasymas}`, delta)}
          onPriceChange={(p) => onPriceChange(row._id || `${row.eil_nr}-${row.aprasymas}`, p)}
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
}) {
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
  const conf = (row.confidence || 'high').toLowerCase();
  const confClass = conf === 'medium' ? 'dot-med' : conf === 'low' ? 'dot-low' : 'dot-high';
  const confTitle = `Pasitikėjimas: ${conf === 'medium' ? 'vidutinis — patikrinkite' : conf === 'low' ? 'žemas — būtina patikrinti' : 'aukštas — nuskaityta iš brėžinio'}`;
  const sum = (row.kiekis || 0) * (row.kaina || 0);
  const isManualQty = row.manual_override === true || row.quantity_source === 'manual_override';
  const isCountUnit = String(row.mato_vnt || '').toLowerCase().includes('vnt');

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
      className="grid items-start cursor-pointer hover:bg-muted/40 transition-colors group"
      style={{
        // Narrowed kiekis/kaina/suma columns from 104/86/86 → 88/72/76 so
        // the description column gets back ~40 px when the right-side
        // Kiekiai panel is half-width (Brėžinys tab). Description also
        // wraps now (whitespace-normal below) instead of truncating with
        // ellipsis, so a name like "Sienų antrinis glaistymas Q2" fits on
        // two lines rather than being cut to "Sienų antrinis g...".
        gridTemplateColumns: '12px 32px 1fr 88px 72px 76px',
        gap: 6, padding: '7px 12px', fontSize: 12,
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
      <span className="mono tabular text-muted-foreground/70" style={{ fontSize: 10 }}>
        {row.eil_nr || ''}
      </span>
      <div className="flex items-start gap-1.5 min-w-0">
        <span
          className="text-foreground/90 leading-snug break-words"
          title={row.review_reason || row.calculation_basis || sourceLabel}
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
          value={draftQty}
          onChange={e => setDraftQty(e.target.value)}
          onBlur={commitQty}
          onKeyDown={e => {
            if (e.key === 'Enter') commitQty();
            if (e.key === 'Escape') setEditingQty(false);
          }}
          onClick={e => e.stopPropagation()}
          className="mono tabular bg-card border border-primary rounded outline-none text-right"
          style={{ fontSize: 11, height: 22, padding: '2px 6px' }}
        />
      ) : (
        <div className="flex items-center justify-end gap-1">
          {isCountUnit && (
            <button
              type="button"
              onClick={(e) => { e.stopPropagation(); onQuantityAdjust(-1); }}
              className="opacity-0 group-hover:opacity-100 w-5 h-5 rounded border border-border hover:border-red-400 hover:text-red-400 transition-all"
              title="Atimti 1"
            >
              −
            </button>
          )}
          <button
            type="button"
            onClick={beginQtyEdit}
            className="mono tabular text-foreground/90 whitespace-nowrap text-right rounded px-1 py-0.5 hover:bg-primary/10 hover:text-primary transition-colors"
            style={{ fontSize: 11 }}
            title="Spustelėkite, norėdami pataisyti kiekį"
          >
            {fmt(row.kiekis)}
            <span className="text-muted-foreground/70 ml-1" style={{ fontSize: 9 }}>{row.mato_vnt}</span>
            {isManualQty && (
              <span
                className="ml-1 px-1 rounded uppercase font-semibold"
                style={{
                  fontSize: 8,
                  lineHeight: '12px',
                  border: '1px solid hsl(var(--source-table) / 0.35)',
                  color: 'hsl(var(--source-table))',
                  background: 'hsl(var(--source-table) / 0.08)',
                }}
              >
                rank.
              </span>
            )}
          </button>
          {isCountUnit && (
            <button
              type="button"
              onClick={(e) => { e.stopPropagation(); onQuantityAdjust(1); }}
              className="opacity-0 group-hover:opacity-100 w-5 h-5 rounded border border-border hover:border-emerald-400 hover:text-emerald-400 transition-all"
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
          value={draftPrice}
          onChange={e => setDraftPrice(e.target.value)}
          onBlur={commit}
          onKeyDown={e => {
            if (e.key === 'Enter') commit();
            if (e.key === 'Escape') setEditing(false);
          }}
          onClick={e => e.stopPropagation()}
          className="mono tabular bg-card border border-primary rounded outline-none text-right"
          style={{ fontSize: 11, height: 22, padding: '2px 6px' }}
        />
      ) : (
        <span
          onClick={beginEdit}
          className="mono tabular cursor-text whitespace-nowrap group-hover:underline group-hover:decoration-dotted"
          style={{
            fontSize: 11,
            color: row.kaina ? 'hsl(var(--muted-foreground))' : 'hsl(var(--muted-foreground) / 0.6)',
            textAlign: 'right',
            textUnderlineOffset: 2,
          }}
          title="Spustelėkite, norėdami redaguoti kainą"
        >
          {row.kaina ? `${row.kaina.toFixed(2)} €` : '—'}
        </span>
      )}
      <span className="mono tabular text-foreground font-medium whitespace-nowrap"
        style={{ fontSize: 11, textAlign: 'right' }}>
        {row.kaina ? `${sum.toLocaleString('lt-LT', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} €` : '—'}
      </span>
      {(row._detail_m2 != null || row._detail_juostele_m != null) && (
        <div
          className="col-span-6 text-muted-foreground"
          style={{
            gridColumn: 'span 6 / span 6',
            fontSize: 10, paddingLeft: 18, paddingTop: 2, lineHeight: 1.3,
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
            fontSize: 10, paddingLeft: 18, paddingTop: 2, lineHeight: 1.3,
          }}
        >
          AI kiekis buvo <span className="mono tabular">{fmt(row.ai_kiekis_original)}</span>
          {row.mato_vnt && <span className="ml-1">{row.mato_vnt}</span>}
        </div>
      )}
    </div>
  );
});
