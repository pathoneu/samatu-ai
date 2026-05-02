/**
 * WorkspacePanel — right-side panel in Brėžinys tab. Mirrors claude.ai/design
 * prototype's `screen-positions.jsx`: filter at top + Patalpos + Kiekiai
 * sections (collapsible per skyrius). Each position row has source dot,
 * confidence dot, qty, inline-edit price, and sum. Click row → jump PDF.
 *
 * Replaces previous rooms-only table layout with positions-aware unified panel.
 */

import { useState, useMemo, useEffect, useCallback, memo } from 'react';
import {
  Search, ChevronDown, ChevronRight, Home, FileText, Eye, EyeOff,
} from 'lucide-react';
import { loadTakeoff, removePolygon } from '@/lib/takeoffStore';
import ReviewQueueSidebar from './ReviewQueueSidebar';
import WallElevationsPanel from './WallElevationsPanel';
import ConfidenceBadge from './ConfidenceBadge';
import ProvenanceChip from './ProvenanceChip';

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
    // Sprint §AUDIT (2026-04-29): pause polling when tab hidden — was firing
    // every 800ms forever even in background tabs (~50KB JSON parse on 100+
    // polygon projects = wasted CPU). Refresh once when tab becomes visible
    // again so user sees latest state.
    let id = null;
    const start = () => {
      if (id != null) return;
      id = setInterval(() => setTakeoff(loadTakeoff(projectId)), 800);
    };
    const stop = () => {
      if (id != null) { clearInterval(id); id = null; }
    };
    const onVisChange = () => {
      if (document.hidden) {
        stop();
      } else {
        // Refresh immediately + resume polling
        setTakeoff(loadTakeoff(projectId));
        start();
      }
    };
    if (!document.hidden) start();
    document.addEventListener('visibilitychange', onVisChange);
    return () => {
      stop();
      document.removeEventListener('visibilitychange', onVisChange);
    };
  }, [projectId]);
  return [takeoff, setTakeoff];
}

// ── Wet-room paskirtis check (for "drėgna" pill) ──────────────────────────
const WET_PASKIRTYS = new Set(['vonia', 'wc', 'san', 'san_mazgas', 'skalbykla']);

export default function WorkspacePanel({ project, onJumpToPage, onJumpToProvenance, onProjectChange }) {
  const [takeoff, setTakeoff] = useTakeoff(project.id);
  const [filter, setFilter] = useState('');
  // Provenance dots OFF by default — too noisy when most rows are computed.
  // User can toggle via eye icon to inspect data sources when needed.
  const [showProvenance, setShowProvenance] = useState(false);
  const [collapsed, setCollapsed] = useState({});

  const handleRemovePolygon = (id) => {
    if (!window.confirm('Ištrinti pažymėjimą?')) return;
    setTakeoff(t => removePolygon(t, id));
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
    const updated = (project.darbu_sarasas || []).map(it => {
      const id = it._id || `${it.eil_nr}-${it.aprasymas}`;
      if (id !== rowId) return it;
      const kaina = parseFloat(String(newPrice).replace(',', '.')) || 0;
      return { ...it, kaina, suma: (it.kiekis || 0) * kaina };
    });
    onProjectChange({ ...project, darbu_sarasas: updated });
  }, [project, onProjectChange]);

  // Stable row click — same memo logic
  const handleRowClick = useCallback((row) => {
    const r = (project.v8_rooms || project.patalpos || []).find(rr => rr.nr === row._room_nr);
    if (r && onJumpToPage) onJumpToPage(r.puslapio_nr, r);
  }, [project.v8_rooms, project.patalpos, onJumpToPage]);

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
        />
        {!collapsed.rooms && filteredRooms.map((r, i) => {
          const eksPage = project?._eksplikacija?.eksplikacija_source_page;
          const targetPage = (r.eksplikacija_row_bbox && eksPage) || r.puslapio_nr;
          const canJump = !!(onJumpToPage && targetPage);
          const isWet = WET_PASKIRTYS.has((r.paskirtis || '').toLowerCase());
          return (
            <div
              key={`${r.nr}-${i}`}
              onClick={canJump ? () => onJumpToPage(targetPage, r) : undefined}
              className="row-hover-halo grid items-center cursor-pointer transition-colors"
              style={{
                gridTemplateColumns: '24px 1fr auto',
                gap: 8, padding: '6px 12px', fontSize: 12,
                borderBottom: '1px solid hsl(var(--border) / 0.5)',
              }}
              title={canJump ? `Atidaryti psl. ${targetPage}` : undefined}
            >
              <span className="mono tabular text-muted-foreground" style={{ fontSize: 10 }}>
                {String(r.nr || i + 1).padStart(2, '0')}
              </span>
              <div className="flex items-center gap-1.5 min-w-0">
                {showProvenance && (
                  <span
                    className={`dot ${r._source === 'manual' ? 'dot-computed' : 'dot-table'}`}
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
                  onClick={(e) => {
                    e?.stopPropagation?.();
                    if (onJumpToPage && targetPage) onJumpToPage(targetPage, r);
                  }}
                />
              </div>
              <span className="mono tabular text-foreground/90 whitespace-nowrap inline-flex items-center gap-1.5" style={{ fontSize: 11 }}>
                {fmt(r.plotas_m2)}
                <span className="text-muted-foreground/70" style={{ fontSize: 9 }}>m²</span>
                {r.plotas_source && (
                  <ProvenanceChip
                    source={r.plotas_source}
                    onClick={(e) => {
                      e?.stopPropagation?.();
                      if (onJumpToProvenance) onJumpToProvenance(r);
                    }}
                  />
                )}
              </span>
            </div>
          );
        })}
        {!collapsed.rooms && filteredRooms.length === 0 && (
          <div className="px-3 py-3 text-xs text-muted-foreground text-center">
            {filter ? `Patalpų nerasta pagal „${filter}"` : 'Patalpų dar nėra.'}
          </div>
        )}

        {/* KIEKIAI section */}
        <SectionHeader
          icon={FileText}
          title="Kiekiai"
          count={`${totalPositions} pozicijų`}
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
            onPriceChange={handlePriceChange}
          />
        ))}
        {positionGroups.length === 0 && filter && (
          <div className="px-3 py-6 text-xs text-muted-foreground text-center">
            Pozicijų nerasta pagal „{filter}".
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
function SectionHeader({ icon: Icon, title, count, summary, collapsed, onToggle, top = 0 }) {
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
      <span className="mono tabular text-muted-foreground" style={{ fontSize: 10 }}>
        {summary}
      </span>
    </button>
  );
}

// ── Position group (sub-section: skyrius) ────────────────────────────────
// Memo'd: only re-renders when its own group data, collapsed state, or
// callbacks change. Filter / scroll / room hover in parent doesn't ripple
// down to all groups.
const PositionGroup = memo(function PositionGroup({ group, collapsed, onToggle, showProvenance, onRowClick, onPriceChange }) {
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
          onPriceChange={(p) => onPriceChange(row._id || `${row.eil_nr}-${row.aprasymas}`, p)}
        />
      ))}
    </div>
  );
});

// ── Position row — primary unit, prototype style ─────────────────────────
// Memo'd: editing one row's price doesn't re-render adjacent rows. Saves
// significant work on 80+ row projects.
const PositionRow = memo(function PositionRow({ row, showProvenance, onClick, onPriceChange }) {
  const [editing, setEditing] = useState(false);
  const [draftPrice, setDraftPrice] = useState('');

  const sourceClass = `dot-${classifySource(row)}`;
  const conf = (row.confidence || 'high').toLowerCase();
  const confClass = conf === 'medium' ? 'dot-med' : conf === 'low' ? 'dot-low' : null;
  const sum = (row.kiekis || 0) * (row.kaina || 0);

  const beginEdit = (e) => {
    e.stopPropagation();
    setDraftPrice(String(row.kaina || 0).replace('.', ','));
    setEditing(true);
  };

  const commit = () => {
    const num = parseFloat(String(draftPrice).replace(',', '.'));
    if (!isNaN(num) && num >= 0) {
      onPriceChange(num);
    }
    setEditing(false);
  };

  return (
    <div
      onClick={onClick}
      className="grid items-center cursor-pointer hover:bg-muted/40 transition-colors group"
      style={{
        gridTemplateColumns: '12px 36px 1fr 90px 86px 86px',
        gap: 6, padding: '7px 12px', fontSize: 12,
        borderBottom: '1px solid hsl(var(--border) / 0.5)',
      }}
    >
      {/* Sprint §FIX-8: dots default off — confidence info'rmuoja Peržiūra queue
          (top of panel). Source dots — opt-in via Pažangu toggle. */}
      {showProvenance ? (
        <span className={`dot ${sourceClass}`} title={SOURCE_TITLE[classifySource(row)]} />
      ) : (
        <span />
      )}
      <span className="mono tabular text-muted-foreground/70" style={{ fontSize: 10 }}>
        {row.eil_nr || ''}
      </span>
      <div className="flex items-center gap-1.5 min-w-0">
        <span className="text-foreground/90 truncate">{row.aprasymas}</span>
        {/* Confidence dot removed — duplicate info with ReviewQueueSidebar */}
      </div>
      <span
        className="mono tabular text-foreground/90 whitespace-nowrap"
        style={{ fontSize: 11, textAlign: 'right' }}
      >
        {fmt(row.kiekis)}
        <span className="text-muted-foreground/70 ml-1" style={{ fontSize: 9 }}>{row.mato_vnt}</span>
      </span>
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
          title="Spausk redaguoti kainą"
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
    </div>
  );
});
