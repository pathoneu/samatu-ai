/**
 * ReviewQueueSidebar — confidence-driven review queue (Sprint G2).
 *
 * Surfaces engine-flagged rooms + positions that need user review. Confidence
 * arrives in the backend's LT vocabulary (zalia/geltona/raudona, see
 * extractor/confidence.py) with legacy EN (high/medium/low) in old blobs —
 * everything is normalized through lib/confidence.js.
 *
 * Positions are ranked by € impact (kiekis × kaina; kiekis alone before prices
 * exist), NOT by confidence order: geltona mostly means "systematic ±20%", so
 * the queue leads with the rows where a wrong quantity costs the most. Default
 * view = all raudona + the 5 biggest geltona; the rest collapses behind
 * "rodyti visas N".
 *
 * KEY DIFFERENTIATOR: rooms/items with eksplikacija_row_bbox or table-source
 * (saltinis ∈ {eksplikacija, specifikacija, isklotines}) get a 🟢 lock badge
 * = "patvirtinta eksplikacijoje" — grid-based takeoff tools can't do this because they only
 * OCR-guess room names; we read from a structured pdfplumber table.
 *
 * Layout: collapsible section at top of WorkspacePanel scroll area.
 * Empty state: "Visi duomenys patvirtinti" (no review needed).
 */

import { useMemo, useState } from 'react';
import {
  ChevronDown, ChevronRight, ShieldCheck, AlertTriangle, AlertCircle, CheckCircle2,
  Check, X, Pencil,
} from 'lucide-react';
import {
  needsTakeoffReview, selectReviewQueue, ltEilutesPhrase,
} from '@/lib/takeoffWorkflow';
import {
  CONF_RAUDONA, normalizeConfidence, confidenceRank, confidenceLabel,
} from '@/lib/confidence';

const TABLE_SOURCES = new Set([
  'eksplikacija', 'specifikacija', 'isklotines', 'lubu_planas',
]);

function isLockedRoom(room) {
  return Array.isArray(room?.eksplikacija_row_bbox) && room.eksplikacija_row_bbox.length === 4;
}

function isLockedPosition(item) {
  return TABLE_SOURCES.has(item?.saltinis);
}

export default function ReviewQueueSidebar({
  rooms = [],
  positions = [],
  eksplikacijaSourcePage = null,
  onJumpToPage = null,
  onReviewStatusChange = null,  // Sprint G2 Phase 2: (kind, key, status) => void
  onEditRoom = null,            // pencil: focus room + arm click-to-fill (falls back to jump)
}) {
  const [open, setOpen] = useState(true);
  const [showAllPositions, setShowAllPositions] = useState(false);

  const { reviewRooms, queue, lockedRoomCount, lockedPositionCount } = useMemo(() => {
    const reviewRooms = rooms
      .filter(r => needsTakeoffReview(r) && !isLockedRoom(r))
      .sort((a, b) =>
        confidenceRank(b.confidence) - confidenceRank(a.confidence)
        || (a.nr || 0) - (b.nr || 0));

    // € impact ranking; eksplikacija-locked rows leave the queue but stay in
    // the total the "≈X % sumos" copy is computed against.
    const queue = selectReviewQueue(positions, { exclude: isLockedPosition });

    const lockedRoomCount = rooms.filter(isLockedRoom).length;
    const lockedPositionCount = positions.filter(isLockedPosition).length;

    return { reviewRooms, queue, lockedRoomCount, lockedPositionCount };
  }, [rooms, positions]);

  const reviewPositions = showAllPositions ? queue.ranked : queue.primary;
  const totalReview = reviewRooms.length + queue.ranked.length;
  const totalLocked = lockedRoomCount + lockedPositionCount;

  const sharePct = queue.shareOfTotal != null ? Math.round(queue.shareOfTotal * 100) : null;
  const shareText = sharePct != null ? (sharePct < 1 ? '<1' : `≈${sharePct}`) : null;

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
              title="Šie įrašai turi tikslias mm reikšmes iš eksplikacijos/specifikacijos lentelių"
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
                  onEdit={onEditRoom ? () => onEditRoom(r) : (onReviewStatusChange ? () => handleRoomClick(r) : null)}
                />
              ))}
            </>
          )}

          {/* Review positions — ranked by € impact, collapsed to raudona + top-5 geltona */}
          {queue.ranked.length > 0 && (
            <>
              <div
                className="px-3 py-1.5 text-muted-foreground uppercase tracking-wide font-medium"
                style={{
                  fontSize: 9,
                  background: 'hsl(var(--bg-1) / 0.5)',
                  borderBottom: '1px solid hsl(var(--border) / 0.3)',
                }}
              >
                Pozicijos ({queue.ranked.length})
              </div>
              <div
                className="px-3 py-2"
                style={{
                  fontSize: 11,
                  color: 'hsl(var(--foreground) / 0.85)',
                  background: 'hsl(var(--conf-med) / 0.06)',
                  borderBottom: '1px solid hsl(var(--border) / 0.4)',
                }}
              >
                Patikrinkite <strong>{ltEilutesPhrase(queue.primary.length)}</strong>
                {shareText && <span className="text-muted-foreground"> ({shareText} % sumos)</span>}
                {!queue.usePrices && <span className="text-muted-foreground"> — rikiuota pagal kiekį, kol nėra kainų</span>}
              </div>
              {reviewPositions.map((p, i) => {
                const posKey = p._id || `${p.eil_nr}-${p.aprasymas}`;
                const kiekisText = p.kiekis != null
                  ? `${Number(p.kiekis).toLocaleString('lt-LT', { maximumFractionDigits: 2 })} ${p.mato_vnt || ''}`.trim()
                  : null;
                const sum = (Number(p.kiekis) || 0) * (Number(p.kaina) || 0);
                const sumText = sum > 0
                  ? `${sum.toLocaleString('lt-LT', { maximumFractionDigits: 0 })} €`
                  : null;
                return (
                  <ReviewRow
                    key={`pos-${posKey}-${i}`}
                    conf={p.confidence}
                    reason={p._confidence_reason}
                    primary={p.aprasymas || 'Pozicija'}
                    secondary={p.skyrius || p.kategorija || '—'}
                    meta={[kiekisText, sumText].filter(Boolean).join(' · ') || null}
                    reasonHint={p.kiekis == null ? 'Kiekis neaptiktas' : null}
                    onClick={() => handlePositionClick(p)}
                    onAccept={onReviewStatusChange ? () => onReviewStatusChange('position', posKey, 'accepted') : null}
                    onReject={onReviewStatusChange ? () => onReviewStatusChange('position', posKey, 'rejected') : null}
                    onEdit={onReviewStatusChange ? () => handlePositionClick(p) : null}
                  />
                );
              })}
              {queue.rest.length > 0 && (
                <button
                  onClick={() => setShowAllPositions(v => !v)}
                  className="w-full text-left px-3 py-2 transition-colors hover:bg-muted/40"
                  style={{
                    fontSize: 11,
                    color: 'hsl(var(--primary))',
                    borderBottom: '1px solid hsl(var(--border) / 0.5)',
                    cursor: 'pointer',
                  }}
                >
                  {showAllPositions
                    ? 'rodyti mažiau'
                    : `rodyti visas ${queue.ranked.length}`}
                </button>
              )}
            </>
          )}
        </>
      )}
    </div>
  );
}

// ── Single review row — confidence dot, name, area/qty, click to jump ──────
// Sprint G2 Phase 2: inline ✓/✏️/✕ accept-edit-reject actions on hover.
// `reason` = backend _confidence_reason ("Skaičius iš simbolių: −20%/+33%" …) —
// shown as the subline so the user sees WHY the row is flagged without hovering.
function ReviewRow({ conf, reason, primary, secondary, meta, reasonHint, onClick, onAccept, onEdit, onReject }) {
  const tier = normalizeConfidence(conf);
  const isRaudona = tier === CONF_RAUDONA;
  const Icon = isRaudona ? AlertCircle : AlertTriangle;
  const confColor = isRaudona ? 'hsl(var(--conf-low))' : 'hsl(var(--conf-med))';
  const confTitle = reason ? `${confidenceLabel(tier)} — ${reason}` : confidenceLabel(tier);

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
      title={`${confTitle} · spustelėkite peržiūrai brėžinyje`}
    >
      <Icon className="w-3 h-3 shrink-0" style={{ color: confColor }} />
      <div className="min-w-0">
        <div className="text-foreground/90 truncate">{primary}</div>
        <div className="text-muted-foreground truncate" style={{ fontSize: 10 }} title={reason || undefined}>
          {reasonHint || reason || secondary}
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
