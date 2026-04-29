/**
 * ReviewQueueSidebar — confidence-driven review queue (Sprint G2).
 *
 * Surfaces low/medium confidence rooms + positions that need user review.
 * KEY DIFFERENTIATOR: rooms/items with eksplikacija_row_bbox or table-source
 * (saltinis ∈ {eksplikacija, specifikacija, isklotines}) get a 🟢 lock badge
 * = "patvirtinta eksplikacijoje" — Togal/Kreo can't do this because they only
 * OCR-guess room names; we read from a structured pdfplumber table.
 *
 * Layout: collapsible section at top of WorkspacePanel scroll area.
 * Empty state: "Visi duomenys patvirtinti" (no review needed).
 *
 * Phase 1 (this commit): list + filter + sort + jump to PDF page.
 * Phase 2 (follow-up): inline ✓/✏️/✕ accept/edit/reject actions.
 */

import { useMemo, useState } from 'react';
import {
  ChevronDown, ChevronRight, ShieldCheck, AlertTriangle, AlertCircle, CheckCircle2,
  Check, X, Pencil,
} from 'lucide-react';

const TABLE_SOURCES = new Set([
  'eksplikacija', 'specifikacija', 'isklotines', 'lubu_planas',
]);

const REVIEW_CONFIDENCES = new Set(['low', 'medium']);

function isLockedRoom(room) {
  return Array.isArray(room?.eksplikacija_row_bbox) && room.eksplikacija_row_bbox.length === 4;
}

function isLockedPosition(item) {
  return TABLE_SOURCES.has(item?.saltinis);
}

function needsReview(it) {
  // Sprint G2 Phase 2: skip items already accepted/rejected by user
  if (it?._review_status === 'accepted' || it?._review_status === 'rejected') return false;
  return REVIEW_CONFIDENCES.has((it?.confidence || '').toLowerCase());
}

function confSortKey(it) {
  const c = (it?.confidence || '').toLowerCase();
  if (c === 'low') return 0;
  if (c === 'medium') return 1;
  return 2;
}

export default function ReviewQueueSidebar({
  rooms = [],
  positions = [],
  eksplikacijaSourcePage = null,
  onJumpToPage = null,
  onReviewStatusChange = null,  // Sprint G2 Phase 2: (kind, key, status) => void
}) {
  const [open, setOpen] = useState(true);

  const { reviewRooms, reviewPositions, lockedRoomCount, lockedPositionCount } = useMemo(() => {
    const reviewRooms = rooms
      .filter(r => needsReview(r) && !isLockedRoom(r))
      .sort((a, b) => confSortKey(a) - confSortKey(b) || (a.nr || 0) - (b.nr || 0));

    const reviewPositions = positions
      .filter(p => needsReview(p) && !isLockedPosition(p))
      .sort((a, b) => confSortKey(a) - confSortKey(b) || (a.eil_nr || 0) - (b.eil_nr || 0));

    const lockedRoomCount = rooms.filter(isLockedRoom).length;
    const lockedPositionCount = positions.filter(isLockedPosition).length;

    return { reviewRooms, reviewPositions, lockedRoomCount, lockedPositionCount };
  }, [rooms, positions]);

  const totalReview = reviewRooms.length + reviewPositions.length;
  const totalLocked = lockedRoomCount + lockedPositionCount;

  const handleRoomClick = (room) => {
    if (!onJumpToPage) return;
    const targetPage = (isLockedRoom(room) && eksplikacijaSourcePage) || room.puslapio_nr;
    if (targetPage) onJumpToPage(targetPage, room);
  };

  const handlePositionClick = (item) => {
    if (!onJumpToPage) return;
    const room = rooms.find(r => r.nr === item._room_nr);
    if (room?.puslapio_nr) onJumpToPage(room.puslapio_nr, room);
  };

  return (
    <div>
      {/* Section header: collapsible, shows total + locked count */}
      <button
        onClick={() => setOpen(v => !v)}
        className="w-full flex items-center justify-between text-left transition-colors hover:bg-muted/40"
        style={{
          background: 'hsl(var(--bg-1))',
          borderBottom: '1px solid hsl(var(--border) / 0.5)',
          padding: '8px 12px', cursor: 'pointer',
          position: 'sticky', top: 0, zIndex: 5,
        }}
      >
        <div className="flex items-center gap-2 min-w-0">
          {open
            ? <ChevronDown className="w-3 h-3 text-muted-foreground shrink-0" />
            : <ChevronRight className="w-3 h-3 text-muted-foreground shrink-0" />}
          <span className="skyrius-header">Peržiūra</span>
          {totalReview > 0 && (
            <span
              className="mono tabular px-1.5 py-0 rounded font-medium"
              style={{
                fontSize: 10, lineHeight: '16px',
                background: 'hsl(var(--source-ai) / 0.15)',
                color: 'hsl(var(--source-ai))',
                border: '1px solid hsl(var(--source-ai) / 0.3)',
              }}
              title="Pozicijų / patalpų su žemu ar vidutiniu pasitikėjimu"
            >
              {totalReview}
            </span>
          )}
        </div>
        {totalLocked > 0 && (
          <span
            className="flex items-center gap-1 mono tabular shrink-0"
            style={{
              fontSize: 10,
              color: 'hsl(var(--source-table))',
            }}
            title={`${totalLocked} įrašų patvirtinti eksplikacijoje arba lentelėje — peržiūros nereikia`}
          >
            <ShieldCheck className="w-3 h-3" />
            {totalLocked} patvirt.
          </span>
        )}
      </button>

      {open && (
        <>
          {/* Empty state */}
          {totalReview === 0 && (
            <div
              className="flex items-center gap-2 px-3 py-3 text-xs"
              style={{
                color: 'hsl(var(--source-table))',
                background: 'hsl(var(--source-table) / 0.05)',
                borderBottom: '1px solid hsl(var(--border) / 0.5)',
              }}
            >
              <CheckCircle2 className="w-3.5 h-3.5 shrink-0" />
              <span>Visi duomenys patvirtinti — peržiūros nereikia.</span>
            </div>
          )}

          {/* Locked summary chip — visible when there ARE locked items, even if review is empty */}
          {totalLocked > 0 && totalReview > 0 && (
            <div
              className="flex items-center gap-2 px-3 py-2"
              style={{
                fontSize: 11,
                color: 'hsl(var(--source-table))',
                background: 'hsl(var(--source-table) / 0.06)',
                borderBottom: '1px solid hsl(var(--border) / 0.4)',
              }}
              title="Šitie įrašai turi tikslias mm reikšmes iš eksplikacijos/specifikacijos lentelių"
            >
              <ShieldCheck className="w-3.5 h-3.5 shrink-0" />
              <span>
                <strong>{totalLocked}</strong> patvirtinta eksplikacijoje ·
                <span className="text-muted-foreground ml-1">peržiūros nereikia</span>
              </span>
            </div>
          )}

          {/* Review rooms */}
          {reviewRooms.length > 0 && (
            <>
              <div
                className="px-3 py-1.5 text-muted-foreground uppercase tracking-wide font-medium"
                style={{
                  fontSize: 9,
                  background: 'hsl(var(--bg-1) / 0.5)',
                  borderBottom: '1px solid hsl(var(--border) / 0.3)',
                }}
              >
                Patalpos ({reviewRooms.length})
              </div>
              {reviewRooms.map((r, i) => (
                <ReviewRow
                  key={`room-${r.nr}-${i}`}
                  conf={r.confidence}
                  primary={r.pavadinimas || `Patalpa ${r.nr}`}
                  secondary={r.paskirtis || '—'}
                  meta={r.plotas_m2 ? `${Number(r.plotas_m2).toLocaleString('lt-LT', { maximumFractionDigits: 2 })} m²` : null}
                  reasonHint={!r.plotas_m2 ? 'Plotas neaptiktas' : null}
                  onClick={() => handleRoomClick(r)}
                  onAccept={onReviewStatusChange ? () => onReviewStatusChange('room', r.nr, 'accepted') : null}
                  onReject={onReviewStatusChange ? () => onReviewStatusChange('room', r.nr, 'rejected') : null}
                  onEdit={onReviewStatusChange ? () => handleRoomClick(r) : null}
                />
              ))}
            </>
          )}

          {/* Review positions */}
          {reviewPositions.length > 0 && (
            <>
              <div
                className="px-3 py-1.5 text-muted-foreground uppercase tracking-wide font-medium"
                style={{
                  fontSize: 9,
                  background: 'hsl(var(--bg-1) / 0.5)',
                  borderBottom: '1px solid hsl(var(--border) / 0.3)',
                }}
              >
                Pozicijos ({reviewPositions.length})
              </div>
              {reviewPositions.map((p, i) => {
                const posKey = p._id || `${p.eil_nr}-${p.aprasymas}`;
                return (
                  <ReviewRow
                    key={`pos-${posKey}-${i}`}
                    conf={p.confidence}
                    primary={p.aprasymas || 'Pozicija'}
                    secondary={p.skyrius || p.kategorija || '—'}
                    meta={p.kiekis != null ? `${Number(p.kiekis).toLocaleString('lt-LT', { maximumFractionDigits: 2 })} ${p.mato_vnt || ''}` : null}
                    reasonHint={p.kiekis == null ? 'Kiekis neaptiktas' : null}
                    onClick={() => handlePositionClick(p)}
                    onAccept={onReviewStatusChange ? () => onReviewStatusChange('position', posKey, 'accepted') : null}
                    onReject={onReviewStatusChange ? () => onReviewStatusChange('position', posKey, 'rejected') : null}
                    onEdit={onReviewStatusChange ? () => handlePositionClick(p) : null}
                  />
                );
              })}
            </>
          )}
        </>
      )}
    </div>
  );
}

// ── Single review row — confidence dot, name, area/qty, click to jump ──────
// Sprint G2 Phase 2: inline ✓/✏️/✕ accept-edit-reject actions on hover.
function ReviewRow({ conf, primary, secondary, meta, reasonHint, onClick, onAccept, onEdit, onReject }) {
  const c = (conf || '').toLowerCase();
  const Icon = c === 'low' ? AlertCircle : AlertTriangle;
  const confColor = c === 'low' ? 'hsl(var(--source-ai))' : 'hsl(var(--warning, 38 92% 50%))';
  const confTitle = c === 'low'
    ? 'Žemas pasitikėjimas — privaloma patikrinti'
    : 'Vidutinis pasitikėjimas — rekomenduojama patikrinti';

  const stop = (e) => { e.stopPropagation(); };

  return (
    <div
      onClick={onClick}
      className="row-hover-halo group grid items-center cursor-pointer transition-colors"
      style={{
        gridTemplateColumns: '14px 1fr auto',
        gap: 8, padding: '6px 12px', fontSize: 12,
        borderBottom: '1px solid hsl(var(--border) / 0.5)',
      }}
      title={`${confTitle} · spustelk peržiūrai brėžinyje`}
    >
      <Icon className="w-3 h-3 shrink-0" style={{ color: confColor }} />
      <div className="min-w-0">
        <div className="text-foreground/90 truncate">{primary}</div>
        <div className="text-muted-foreground truncate" style={{ fontSize: 10 }}>
          {reasonHint || secondary}
        </div>
      </div>
      <div className="flex items-center gap-0.5 shrink-0">
        {/* Sprint G2 Phase 2: inline accept/edit/reject icons. Show on hover
            (or always on touch). Stop event propagation so they don't trigger
            the parent row click. */}
        {(onAccept || onEdit || onReject) && (
          <div className="hidden group-hover:flex items-center gap-0.5 mr-1">
            {onAccept && (
              <button
                onClick={(e) => { stop(e); onAccept(); }}
                title="Patvirtinti — pašalinti iš peržiūros"
                className="p-0.5 rounded transition-colors"
                style={{
                  color: 'hsl(var(--source-table))',
                }}
                onMouseEnter={(e) => e.currentTarget.style.background = 'hsl(var(--source-table) / 0.15)'}
                onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}
              >
                <Check className="w-3 h-3" />
              </button>
            )}
            {onEdit && (
              <button
                onClick={(e) => { stop(e); onEdit(); }}
                title="Redaguoti — atidaryti brėžinyje"
                className="p-0.5 rounded transition-colors text-muted-foreground hover:bg-muted/40"
              >
                <Pencil className="w-3 h-3" />
              </button>
            )}
            {onReject && (
              <button
                onClick={(e) => { stop(e); onReject(); }}
                title="Atmesti — pažymėti kaip neaktualų"
                className="p-0.5 rounded transition-colors"
                style={{
                  color: 'hsl(var(--source-ai))',
                }}
                onMouseEnter={(e) => e.currentTarget.style.background = 'hsl(var(--source-ai) / 0.15)'}
                onMouseLeave={(e) => e.currentTarget.style.background = 'transparent'}
              >
                <X className="w-3 h-3" />
              </button>
            )}
          </div>
        )}
        {meta && (
          <span className="mono tabular text-foreground/80 whitespace-nowrap" style={{ fontSize: 10 }}>
            {meta}
          </span>
        )}
      </div>
    </div>
  );
}
