/**
 * PositionsPanel — dešinė panelė su Patalpos + Pozicijos sekcijomis.
 *
 * Sekcijos:
 *  1. Bendra suvestinė (sticky top)
 *  2. Filtrai (paieška + checkboxes)
 *  3. Patalpos (collapsible, default open)
 *  4. Pozicijos (collapsible, sugrupuotos pagal skyrius)
 */

import { useState, useMemo } from 'react';
import {
  X, Search, ChevronDown, ChevronRight, Home, FileText,
  Edit2, Check,
} from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import ExportDropdown from './ExportDropdown';
import ShareButton from './ShareButton';

function fmt(val, d = 2) {
  if (val == null) return '—';
  return Number(val).toLocaleString('lt-LT', { maximumFractionDigits: d });
}
function fmtEur(val) {
  if (val == null) return '—';
  return `${Number(val).toLocaleString('lt-LT', {
    minimumFractionDigits: 2, maximumFractionDigits: 2,
  })} €`;
}

// Grupavimas pagal skyrius
function groupByCategory(rows) {
  const groups = {};
  rows.forEach(item => {
    const cat = item.skyrius || item.kategorija || 'Kiti darbai';
    if (!groups[cat]) groups[cat] = [];
    groups[cat].push(item);
  });
  return groups;
}

// ── Source dot pagal trace_type + detected ─────────────────────────────────
function SourceDot({ row }) {
  const tt = row.trace_type;
  const detected = row.detected;
  if (detected === true) {
    if (row.confidence === 'high' && tt === 'area') {
      return <span title="Geometrija — tikslus" className="w-1.5 h-1.5 rounded-full bg-blue-500 shrink-0" />;
    }
    return <span title={`AI rasta — ${row.source || ''}`} className="w-1.5 h-1.5 rounded-full bg-emerald-500 shrink-0" />;
  }
  if (detected === false) {
    return <span title={`Vidurkis — ${row.source || ''}`} className="w-1.5 h-1.5 rounded-full bg-amber-500 shrink-0" />;
  }
  return null;
}

// ── PositionRow — atskira eilutė panel'ėje ─────────────────────────────────
function PositionRow({ row, isActive, isHovered, onClick, onHover, onChange }) {
  const [editing, setEditing] = useState(false);
  const [draftPrice, setDraftPrice] = useState(row.kaina || '');

  const suma = (row.kiekis || 0) * (row.kaina || 0);

  const handlePriceSave = () => {
    const newPrice = parseFloat(draftPrice) || 0;
    onChange({ ...row, kaina: newPrice, suma: (row.kiekis || 0) * newPrice });
    setEditing(false);
  };

  return (
    <div
      onClick={() => onClick(row)}
      onMouseEnter={() => onHover(row)}
      onMouseLeave={() => onHover(null)}
      className={`group px-3 py-1.5 cursor-pointer transition-colors text-xs border-b border-border/30 ${
        isActive
          ? 'bg-foreground/10 border-l-2 border-l-foreground -ml-px'
          : isHovered
            ? 'bg-muted/40'
            : 'hover:bg-muted/20'
      }`}
    >
      <div className="flex items-start gap-2">
        <SourceDot row={row} />
        <div className="flex-1 min-w-0">
          <div className="text-foreground/90 leading-snug truncate">{row.aprasymas}</div>
          {row.medziagos_kiekis != null && row.medziagos_kiekis > 0 && (
            <div className="text-[10px] text-muted-foreground/80 leading-tight truncate mt-0.5">
              + medžiaga: <span className="tabular-nums">{fmt(row.medziagos_kiekis)} {row.medziagos_vnt}</span>
              {row.medziagos_aprasymas && (
                <span className="text-muted-foreground/60"> · {row.medziagos_aprasymas}</span>
              )}
            </div>
          )}
          <div className="flex items-center gap-2 mt-0.5 text-muted-foreground">
            <span className="tabular-nums">{fmt(row.kiekis)} {row.mato_vnt}</span>
            <span>·</span>
            {editing ? (
              <span className="flex items-center gap-1">
                <input
                  type="number"
                  step="0.01"
                  value={draftPrice}
                  onChange={(e) => setDraftPrice(e.target.value)}
                  onClick={(e) => e.stopPropagation()}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter') handlePriceSave();
                    if (e.key === 'Escape') setEditing(false);
                  }}
                  className="w-14 px-1 py-0.5 border border-border rounded bg-background text-foreground text-xs"
                  autoFocus
                />
                <button onClick={(e) => { e.stopPropagation(); handlePriceSave(); }}
                  className="text-emerald-600 hover:text-emerald-700">
                  <Check className="w-3 h-3" />
                </button>
              </span>
            ) : row.kaina ? (
              <span className="tabular-nums">{fmtEur(row.kaina)}</span>
            ) : (
              <span
                onClick={(e) => { e.stopPropagation(); setEditing(true); setDraftPrice(''); }}
                className="text-muted-foreground italic hover:text-foreground"
              >
                įvesk kainą
              </span>
            )}
            {row.kaina > 0 && (
              <>
                <span>·</span>
                <strong className="text-foreground tabular-nums">{fmtEur(suma)}</strong>
              </>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

// ── PositionsPanel main ────────────────────────────────────────────────────
export default function PositionsPanel({
  project, darbai, activeRowId, hoveredRowId,
  highlightRowIds = null, // Set<rowId> from PDF room hover (Phase 14 / QW05)
  onRowClick, onRowHover, onDarbaiChange, onCollapse,
}) {
  const [search, setSearch] = useState('');
  const [filterAiOnly, setFilterAiOnly] = useState(false);
  const [hideFormulas, setHideFormulas] = useState(false);

  const [roomsOpen, setRoomsOpen] = useState(true);
  const [positionsOpen, setPositionsOpen] = useState(true);
  const [collapsedCats, setCollapsedCats] = useState(new Set());

  const filtered = useMemo(() => {
    let rows = darbai;
    if (search) {
      const s = search.toLowerCase();
      rows = rows.filter(r =>
        (r.aprasymas || '').toLowerCase().includes(s) ||
        (r.skyrius || '').toLowerCase().includes(s)
      );
    }
    if (filterAiOnly) rows = rows.filter(r => r.detected === true);
    if (hideFormulas) rows = rows.filter(r => r.trace_type !== 'formula');
    return rows;
  }, [darbai, search, filterAiOnly, hideFormulas]);

  const grouped = useMemo(() => groupByCategory(filtered), [filtered]);
  const cats = Object.keys(grouped);

  // SM02: pokyčius kiekiams pritaiko getFloorCount(project) — totals
  // padauginami iš aukštų skaičiaus (default 1).
  const floorCount = (() => {
    const n = parseInt(project?.prielaidos?.aukstu_skaicius, 10);
    return Number.isFinite(n) && n >= 1 ? Math.min(9, n) : 1;
  })();
  const totals = useMemo(() => {
    let sum = 0, count = 0;
    darbai.forEach(it => {
      sum += (it.kiekis || 0) * (it.kaina || 0);
      count++;
    });
    return { sum: sum * floorCount, count };
  }, [darbai, floorCount]);

  const totalArea = useMemo(() => {
    const rooms = project.v8_rooms || project.patalpos || [];
    return rooms.reduce((s, r) => s + (r.plotas_m2 || 0), 0);
  }, [project]);

  const rooms = project.v8_rooms || project.patalpos || [];

  const handleRowChange = (newRow) => {
    const idx = darbai.findIndex(d => d._id === newRow._id);
    if (idx < 0) return;
    const next = [...darbai];
    next[idx] = newRow;
    onDarbaiChange(next);
  };

  const toggleCat = (cat) => {
    setCollapsedCats(s => {
      const next = new Set(s);
      if (next.has(cat)) next.delete(cat); else next.add(cat);
      return next;
    });
  };

  return (
    <div className="flex flex-col h-full overflow-hidden">

      {/* Header — sticky top */}
      <div className="px-3 pt-3 pb-2 border-b border-border bg-card/95 backdrop-blur z-10">
        <div className="flex items-start justify-between gap-2 mb-2">
          <div>
            <div className="text-[10px] uppercase tracking-wide text-muted-foreground font-medium flex items-center gap-1.5">
              Bendra suma (be PVM)
              {floorCount > 1 && (
                <span className="px-1.5 py-0.5 rounded bg-primary/10 text-primary text-[9px] font-semibold normal-case tracking-normal">
                  × {floorCount} aukštai
                </span>
              )}
            </div>
            <div className="text-xl font-semibold tabular-nums text-foreground">
              {fmtEur(totals.sum)}
            </div>
            <div className="text-[10px] text-muted-foreground mt-0.5">
              su PVM 21%: {fmtEur(totals.sum * 1.21)}
            </div>
          </div>
          <div className="flex items-center gap-1">
            <ExportDropdown project={{ ...project, darbu_sarasas: darbai }} />
            <ShareButton project={project} />
            <button
              onClick={onCollapse}
              className="p-1.5 hover:bg-muted rounded text-muted-foreground"
              title="Slėpti panel'ę"
            >
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
        <div className="flex flex-wrap gap-x-3 text-[11px] text-muted-foreground">
          <span>{rooms.length} patalpų</span>
          <span>·</span>
          <span>{fmt(totalArea)} m²</span>
          <span>·</span>
          <span>{totals.count} pozicijų</span>
        </div>
      </div>

      {/* Filters */}
      <div className="px-3 py-2 border-b border-border bg-card/50 space-y-2">
        <div className="relative">
          <Search className="w-3 h-3 absolute left-2 top-1/2 -translate-y-1/2 text-muted-foreground" />
          <input
            type="text"
            placeholder="Ieškoti pozicijų..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-7 pr-2 py-1 text-xs border border-border rounded bg-background text-foreground"
          />
        </div>
        <div className="flex gap-3 text-[11px]">
          <label className="flex items-center gap-1.5 cursor-pointer text-foreground/80 hover:text-foreground">
            <input type="checkbox" checked={filterAiOnly}
              onChange={(e) => setFilterAiOnly(e.target.checked)}
              className="rounded border-border" />
            Tik AI rasta
          </label>
          <label className="flex items-center gap-1.5 cursor-pointer text-foreground/80 hover:text-foreground">
            <input type="checkbox" checked={hideFormulas}
              onChange={(e) => setHideFormulas(e.target.checked)}
              className="rounded border-border" />
            Slėpti formules
          </label>
        </div>
      </div>

      {/* Scrollable content */}
      <div className="flex-1 overflow-y-auto">

        {/* Patalpos sekcija */}
        <div className="border-b border-border">
          <button
            onClick={() => setRoomsOpen(v => !v)}
            className="w-full flex items-center gap-2 px-3 py-2 hover:bg-muted/30 text-left text-xs font-semibold uppercase tracking-wide text-muted-foreground"
          >
            {roomsOpen ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
            <Home className="w-3 h-3" />
            <span>Patalpos</span>
            <Badge variant="secondary" className="ml-auto text-[10px] py-0 h-4">
              {rooms.length}
            </Badge>
          </button>
          {roomsOpen && rooms.length > 0 && (
            <div className="pb-1">
              {rooms.map((r, i) => (
                <div key={r.nr || i} className="px-3 py-1 text-xs flex items-center gap-2 hover:bg-muted/20">
                  <span className="text-muted-foreground tabular-nums w-5">{r.nr}</span>
                  <span className="flex-1 text-foreground/90 truncate">{r.pavadinimas || 'Patalpa'}</span>
                  <span className="text-muted-foreground tabular-nums">{fmt(r.plotas_m2)} m²</span>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Pozicijos sekcija */}
        <div>
          <button
            onClick={() => setPositionsOpen(v => !v)}
            className="w-full flex items-center gap-2 px-3 py-2 hover:bg-muted/30 text-left text-xs font-semibold uppercase tracking-wide text-muted-foreground"
          >
            {positionsOpen ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
            <FileText className="w-3 h-3" />
            <span>Pozicijos</span>
            <Badge variant="secondary" className="ml-auto text-[10px] py-0 h-4">
              {filtered.length}
            </Badge>
          </button>
          {positionsOpen && (
            <div>
              {cats.length === 0 && (
                <div className="p-4 text-xs text-muted-foreground text-center">
                  {search || filterAiOnly || hideFormulas
                    ? 'Pagal filtrus pozicijų nerasta'
                    : 'Pozicijų nėra'}
                </div>
              )}
              {cats.map(cat => {
                const isOpen = !collapsedCats.has(cat);
                return (
                  <div key={cat}>
                    <button
                      onClick={() => toggleCat(cat)}
                      className="w-full flex items-center gap-1.5 px-3 py-1.5 bg-muted/40 hover:bg-muted/60 text-[10px] uppercase tracking-wide font-semibold text-foreground/70 text-left"
                    >
                      {isOpen
                        ? <ChevronDown className="w-2.5 h-2.5" />
                        : <ChevronRight className="w-2.5 h-2.5" />}
                      {cat}
                      <span className="ml-auto text-muted-foreground normal-case font-normal">
                        {grouped[cat].length}
                      </span>
                    </button>
                    {isOpen && grouped[cat].map(row => (
                      <PositionRow
                        key={row._id}
                        row={row}
                        isActive={activeRowId === row._id}
                        isHovered={hoveredRowId === row._id || highlightRowIds?.has?.(row._id) === true}
                        onClick={onRowClick}
                        onHover={onRowHover}
                        onChange={handleRowChange}
                      />
                    ))}
                  </div>
                );
              })}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
