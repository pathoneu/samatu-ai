/**
 * WallElevationsPanel — renders per-wall tile/paint/niche zones extracted
 * from sienų išklotinės (Sprint §21, 2026-04-29).
 *
 * Source: project._wall_elevations[] from backend `wall_elevation.py`
 * extractor (opt-in via WALL_ELEVATION_EXTRACT=1 env var).
 *
 * Layout: collapsible card section that mounts in WorkspacePanel above
 * Plytelių specifikacija. Shows per-wall:
 *   - tile_zones (from-to mm precision)
 *   - paint_zones
 *   - niches (width × height × depth)
 *   - furniture_zones (kitchen cabinets etc.)
 *
 * Empty state: not rendered at all (parent gates on data presence).
 */

import { useState, useMemo } from 'react';
import { ChevronDown, ChevronRight, LayoutGrid } from 'lucide-react';
import { ltPlural } from '@/lib/ltPlural';

function fmtMm(mm) {
  if (mm == null) return '—';
  if (mm >= 1000) return `${(mm / 1000).toFixed(2)} m`;
  return `${Math.round(mm)} mm`;
}

function fmtRange(fromMm, toMm) {
  return `${fmtMm(fromMm)} → ${fmtMm(toMm)}`;
}

export default function WallElevationsPanel({ wallElevations = [] }) {
  const [open, setOpen] = useState(false);
  const [expandedRoom, setExpandedRoom] = useState(null);

  // Group walls by room_name
  const grouped = useMemo(() => {
    const map = new Map();
    for (const w of wallElevations) {
      const room = w.room_name || 'Nenurodyta';
      if (!map.has(room)) map.set(room, []);
      map.get(room).push(w);
    }
    return Array.from(map, ([room, walls]) => ({ room, walls }));
  }, [wallElevations]);

  if (!wallElevations || wallElevations.length === 0) return null;

  const totalTiles = wallElevations.reduce((s, w) => s + (w.tile_zones?.length || 0), 0);
  const totalNiches = wallElevations.reduce((s, w) => s + (w.niches?.length || 0), 0);

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
          <LayoutGrid className="w-3 h-3 text-muted-foreground" />
          <span className="skyrius-header">Sienų išklotinės (mm precision)</span>
          <span className="mono tabular text-muted-foreground/70" style={{ fontSize: 10 }}>
            {grouped.length} kambariai · {totalTiles} plytelių zonos · {totalNiches} nišos
          </span>
        </div>
      </button>
      {open && grouped.map(({ room, walls }) => {
        const isRoomOpen = expandedRoom === room;
        return (
          <div key={room} style={{ borderBottom: '1px solid hsl(var(--border) / 0.5)' }}>
            <button
              onClick={() => setExpandedRoom(isRoomOpen ? null : room)}
              className="w-full flex items-center gap-2 px-3 py-2 text-left text-xs hover:bg-muted/40"
            >
              {isRoomOpen
                ? <ChevronDown className="w-3 h-3 text-muted-foreground shrink-0" />
                : <ChevronRight className="w-3 h-3 text-muted-foreground shrink-0" />}
              <span className="font-medium text-foreground/90">{room}</span>
              <span className="mono tabular text-muted-foreground/70" style={{ fontSize: 10 }}>
                {walls.length} {ltPlural(walls.length, 'siena', 'sienos', 'sienų')}
              </span>
            </button>
            {isRoomOpen && walls.map(w => (
              <WallDetail key={`${w.page}-${w.wall_id}`} wall={w} />
            ))}
          </div>
        );
      })}
    </div>
  );
}

function WallDetail({ wall }) {
  return (
    <div
      className="px-5 py-2.5 space-y-1.5"
      style={{
        background: 'hsl(var(--bg-1) / 0.4)',
        borderTop: '1px dashed hsl(var(--border) / 0.5)',
        fontSize: 11,
      }}
    >
      {/* Wall header */}
      <div className="flex items-center gap-2">
        <span className="mono tabular font-semibold text-foreground/90">
          Siena {wall.wall_id || '?'}
        </span>
        {wall.wall_total_width_mm && wall.wall_total_height_mm && (
          <span className="text-muted-foreground" style={{ fontSize: 10 }}>
            {fmtMm(wall.wall_total_width_mm)} × {fmtMm(wall.wall_total_height_mm)}
          </span>
        )}
        {wall.confidence && (
          <span
            className="px-1 py-0 rounded uppercase tracking-wide font-medium"
            style={{
              fontSize: 9, lineHeight: '14px',
              background: wall.confidence === 'high'
                ? 'hsl(var(--source-table) / 0.15)'
                : wall.confidence === 'medium'
                  ? 'hsl(var(--warning, 38 92% 50%) / 0.15)'
                  : 'hsl(var(--source-ai) / 0.15)',
              color: wall.confidence === 'high'
                ? 'hsl(var(--source-table))'
                : wall.confidence === 'medium'
                  ? 'hsl(var(--warning, 38 92% 50%))'
                  : 'hsl(var(--source-ai))',
            }}
          >
            {wall.confidence}
          </span>
        )}
      </div>

      {/* Tile zones */}
      {(wall.tile_zones || []).length > 0 && (
        <div>
          <div className="text-muted-foreground uppercase tracking-wide font-medium" style={{ fontSize: 9 }}>
            Plytelių zonos
          </div>
          {wall.tile_zones.map((tz, i) => (
            <div key={i} className="flex items-center gap-2 pl-2">
              <span style={{ width: 8, height: 8, background: 'hsl(var(--primary))', borderRadius: 2 }} />
              <span className="mono tabular text-foreground/85">
                {fmtRange(tz.from_floor_mm, tz.to_floor_mm)}
              </span>
              {tz.wall_segment_label && (
                <span className="text-muted-foreground" style={{ fontSize: 10 }}>
                  {tz.wall_segment_label}
                </span>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Niches */}
      {(wall.niches || []).length > 0 && (
        <div>
          <div className="text-muted-foreground uppercase tracking-wide font-medium" style={{ fontSize: 9 }}>
            Nišos
          </div>
          {wall.niches.map((n, i) => (
            <div key={i} className="flex items-center gap-2 pl-2">
              <span style={{ width: 8, height: 8, background: 'hsl(var(--secondary, 30 50% 70%))', borderRadius: 2 }} />
              <span className="mono tabular text-foreground/85">
                {fmtMm(n.width_mm)} × {fmtMm(n.height_mm)} × {fmtMm(n.depth_mm)}
              </span>
              {n.purpose && (
                <span className="text-muted-foreground" style={{ fontSize: 10 }}>
                  {n.purpose}
                </span>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Furniture */}
      {(wall.furniture_zones || []).length > 0 && (
        <div>
          <div className="text-muted-foreground uppercase tracking-wide font-medium" style={{ fontSize: 9 }}>
            Baldai
          </div>
          {wall.furniture_zones.map((fz, i) => (
            <div key={i} className="flex items-center gap-2 pl-2">
              <span style={{ width: 8, height: 8, background: 'hsl(var(--muted-foreground) / 0.5)', borderRadius: 2 }} />
              <span className="mono tabular text-foreground/85">
                {fmtRange(fz.from_floor_mm, fz.to_floor_mm)}
              </span>
              <span className="text-muted-foreground" style={{ fontSize: 10 }}>
                {fz.width_mm ? `${fmtMm(fz.width_mm)} pl.` : ''}
                {fz.label ? ` · ${fz.label}` : ''}
              </span>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
