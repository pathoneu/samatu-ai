/**
 * ReviewQueueSidebar — „Patikra": the guided audit loop.
 *
 * Was a flat list of flagged rows (Sprint G2). Since 2026-09-02 it is the loop
 * the founder asked for: a strip that prices what is still unchecked and shows
 * how much of the sąmata a HUMAN has stood behind, one active claim card at a
 * time (`PatikraCard`), the result of the last fix with its € ripple, and the
 * rest of the queue waiting below.
 *
 * Ranking is unchanged — `rankReviewRows` orders by what a wrong line COSTS
 * (kiekis × kaina, kiekis alone before prices), never by confidence, because
 * geltona mostly means "systematic ±20 %".
 *
 * KEY DIFFERENTIATOR kept from the old sidebar: rooms/items with
 * `eksplikacija_row_bbox` or a table source (`saltinis` ∈ {eksplikacija,
 * specifikacija, isklotines}) get a 🟢 lock = „patvirtinta eksplikacijoje" —
 * grid-based takeoff tools can't do this because they only OCR-guess room
 * names; we read from a structured pdfplumber table.
 *
 * Honesty rules this file must not break: the trust meter counts ONLY human
 * verification (a green row is not a checked row — measured false-green rate
 * was 50–60 %), and „Įsiminta mokymui" means the correction was written to this
 * project's log. Nothing here may imply the model changed.
 */

import { useEffect, useMemo, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import {
  ChevronDown, ChevronRight, ShieldCheck, AlertTriangle, AlertCircle, CheckCircle2,
  Check, X, Pencil, GraduationCap,
} from 'lucide-react';
import {
  needsTakeoffReview, pickSensitiveInput, rankReviewRows,
  selectReviewQueue, trustMeter, unverifiedRisk,
} from '@/lib/takeoffWorkflow';
import { ltEur, ltNumber, ltQuantity } from '@/lib/ledger';
import { fetchCorrections } from '@/lib/projectStore';
import {
  CONF_RAUDONA, normalizeConfidence, confidenceRank, confidenceLabel,
} from '@/lib/confidence';
import PatikraCard from './PatikraCard';
import { cleanUserText } from '@/lib/userText';

const TABLE_SOURCES = new Set([
  'eksplikacija', 'specifikacija', 'isklotines', 'lubu_planas',
]);

function isLockedRoom(room) {
  return Array.isArray(room?.eksplikacija_row_bbox) && room.eksplikacija_row_bbox.length === 4;
}

function isLockedPosition(item) {
  return TABLE_SOURCES.has(item?.saltinis);
}

const rowKey = (row) => row?.id || row?._id || `${row?.eil_nr}-${row?.aprasymas}`;

export default function ReviewQueueSidebar({
  rooms = [],
  positions = [],
  eksplikacijaSourcePage = null,
  onJumpToPage = null,
  onReviewStatusChange = null,  // Sprint G2 Phase 2: (kind, key, status) => void
  onEditRoom = null,            // pencil: focus room + arm click-to-fill (falls back to jump)
  // ── Patikra (2026-09-02) ──────────────────────────────────────────────────
  projectId = null,
  onOpenAssumptions = null,     // (focus) => void — {field, roomNr}
  onOpenRowDetail = null,       // (row)   => void — „kodėl toks skaičius?"
  onAcceptRow = null,           // (row)   => void — „Teisinga ✓"
  onQuantityChange = null,      // (row, qty) => void — the last-resort fix
  lastRipple = null,            // {row, before, after, unit, diff} from a recompute
}) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(true);
  const [showAllPositions, setShowAllPositions] = useState(false);
  const [activeKey, setActiveKey] = useState(null);
  const [logOpen, setLogOpen] = useState(false);
  const [corrections, setCorrections] = useState([]);

  // The correction log is the „Įsiminta mokymui" counter's only source. It is
  // re-read whenever a fix lands (lastRipple changes), so the number the user
  // sees is the number the backend actually stored.
  const rippleStamp = lastRipple?.at || null;
  useEffect(() => {
    let alive = true;
    if (!projectId) return () => { alive = false; };
    fetchCorrections(projectId).then((list) => { if (alive) setCorrections(list); });
    return () => { alive = false; };
  }, [projectId, rippleStamp]);

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

  const meter = useMemo(() => trustMeter(positions), [positions]);
  const risk = useMemo(() => unverifiedRisk(positions), [positions]);

  // The claim on stage: whatever the user picked, else the top of the queue.
  // A verified row leaves the queue, so the selection falls back on its own.
  const activeRow = useMemo(() => {
    const ranked = rankReviewRows(positions.filter(p => !isLockedPosition(p)));
    if (!ranked.length) return null;
    return ranked.find(r => rowKey(r) === activeKey) || ranked[0];
  }, [positions, activeKey]);

  const sensitive = useMemo(
    () => (activeRow ? pickSensitiveInput(activeRow, rooms) : null),
    [activeRow, rooms]);

  // Picking a claim from the list below has to bring the card into view — the
  // list is long enough that the card changes off-screen otherwise. Only on a
  // deliberate pick, never on the queue re-ordering itself.
  const cardRef = useRef(null);
  useEffect(() => {
    if (!activeKey || !cardRef.current) return;
    cardRef.current.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }, [activeKey]);

  const reviewPositions = showAllPositions ? queue.ranked : queue.primary;
  const upNext = reviewPositions.filter(p => p !== activeRow);
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
    setActiveKey(rowKey(item));
  };

  // „Pataisyti" lands on the control that changes the wrong INPUT, not on the
  // number. Height → Prielaidos focused on that room; area → the room's own
  // outline editor in the viewer; anything else is handled inside the card.
  const handleFix = (pick) => {
    if (!pick) return;
    if (pick.kind === 'height' && onOpenAssumptions) {
      onOpenAssumptions({ field: 'lubu_auksciai', roomNr: pick.roomNr });
      return;
    }
    const room = rooms.find(r => String(r?.nr) === String(pick.roomNr));
    if (pick.kind === 'area' && room) {
      if (onEditRoom) onEditRoom(room);
      else handleRoomClick(room);
      return;
    }
    if (onOpenAssumptions) onOpenAssumptions(null);
  };

  const focusSensitiveRoom = (pick) => {
    const room = rooms.find(r => String(r?.nr) === String(pick.roomNr));
    if (onJumpToPage && pick.page != null) onJumpToPage(pick.page, room || { nr: pick.roomNr });
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
          <span className="skyrius-header">{t('project.patikra.title')}</span>
          {totalReview > 0 && (
            <span
              className="mono tabular px-1.5 py-0 rounded font-medium"
              style={{
                fontSize: 10, lineHeight: '16px',
                background: 'hsl(var(--source-ai) / 0.15)',
                color: 'hsl(var(--source-ai))',
                border: '1px solid hsl(var(--source-ai) / 0.3)',
              }}
              title={t('project.patikra.countTitle')}
            >
              {totalReview}
            </span>
          )}
        </div>
        {totalLocked > 0 && (
          <span
            className="flex items-center gap-1 mono tabular shrink-0"
            style={{ fontSize: 10, color: 'hsl(var(--source-table))' }}
            title={t('project.patikra.lockedTitle', { count: totalLocked })}
          >
            <ShieldCheck className="w-3 h-3" />
            {totalLocked} patvirt.
          </span>
        )}
      </button>

      {open && (
        <>
          {/* ── Trust strip: what is at stake and what is already stood behind ── */}
          <TrustStrip meter={meter} risk={risk} />

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
              <span>{t('project.patikra.allChecked')}</span>
            </div>
          )}

          {/* ── The active claim ─────────────────────────────────────────── */}
          {activeRow && (
            <div ref={cardRef} className="px-2.5 py-2.5" style={{ borderBottom: '1px solid hsl(var(--border) / 0.5)' }}>
              <PatikraCard
                row={activeRow}
                sensitive={sensitive}
                onAccept={onAcceptRow ? () => onAcceptRow(activeRow) : null}
                onFix={onOpenAssumptions || onEditRoom ? handleFix : null}
                onWhy={onOpenRowDetail ? () => onOpenRowDetail(activeRow) : null}
                onFocusRoom={onJumpToPage ? focusSensitiveRoom : null}
                onQuantityChange={onQuantityChange
                  ? (qty) => onQuantityChange(activeRow, qty)
                  : null}
              />
            </div>
          )}

          {/* ── What the last fix actually moved ─────────────────────────── */}
          {lastRipple && <RippleCard ripple={lastRipple} count={corrections.length} />}

          {/* ── The learning log — recorded, never "the model learned" ───── */}
          {corrections.length > 0 && (
            <div style={{ borderBottom: '1px solid hsl(var(--border) / 0.5)' }}>
              <button
                type="button"
                onClick={() => setLogOpen(v => !v)}
                aria-expanded={logOpen}
                className="w-full flex items-center gap-1.5 px-3 py-1.5 text-left transition-colors hover:bg-muted/40"
                style={{ fontSize: 11, color: 'hsl(var(--primary))' }}
                title={t('project.patikra.logTitle')}
              >
                <GraduationCap className="w-3 h-3 shrink-0" />
                {t('project.patikra.log', { count: corrections.length })}
                {logOpen
                  ? <ChevronDown className="w-3 h-3 ml-auto" />
                  : <ChevronRight className="w-3 h-3 ml-auto" />}
              </button>
              {logOpen && (
                <ul className="pb-1">
                  {corrections.slice(0, 20).map((c, i) => (
                    <li
                      key={`${c.id || c.field_path}-${i}`}
                      className="px-3 py-1 text-[10.5px] text-muted-foreground"
                      style={{ borderTop: '1px solid hsl(var(--border) / 0.3)' }}
                    >
                      <span className="text-foreground/80">{correctionLabel(c)}</span>
                      {c.occurred_at && (
                        <span className="mono tabular">
                          {' · '}{String(c.occurred_at).slice(0, 16).replace('T', ' ')}
                        </span>
                      )}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}

          {/* Locked summary chip — visible when there ARE locked items */}
          {totalLocked > 0 && totalReview > 0 && (
            <div
              className="flex items-center gap-2 px-3 py-2"
              style={{
                fontSize: 11,
                color: 'hsl(var(--source-table))',
                background: 'hsl(var(--source-table) / 0.06)',
                borderBottom: '1px solid hsl(var(--border) / 0.4)',
              }}
              title={t('project.patikra.lockedRowTitle')}
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
                  meta={r.plotas_m2 ? `${ltNumber(r.plotas_m2)} m²` : null}
                  reasonHint={!r.plotas_m2 ? 'Plotas neaptiktas' : null}
                  onClick={() => handleRoomClick(r)}
                  onAccept={onReviewStatusChange ? () => onReviewStatusChange('room', r.nr, 'accepted') : null}
                  onReject={onReviewStatusChange ? () => onReviewStatusChange('room', r.nr, 'rejected') : null}
                  onEdit={onEditRoom ? () => onEditRoom(r) : (onReviewStatusChange ? () => handleRoomClick(r) : null)}
                />
              ))}
            </>
          )}

          {/* ── The rest of the queue, waiting ───────────────────────────── */}
          {upNext.length > 0 && (
            <>
              <div
                className="px-3 py-1.5 text-muted-foreground uppercase tracking-wide font-medium"
                style={{
                  fontSize: 9,
                  background: 'hsl(var(--bg-1) / 0.5)',
                  borderBottom: '1px solid hsl(var(--border) / 0.3)',
                }}
              >
                {t('project.patikra.upNext', { count: queue.ranked.length })}
                {shareText && <span className="normal-case"> · {shareText} % sumos</span>}
                {!queue.usePrices && (
                  <span className="normal-case"> · rikiuota pagal kiekį, kol nėra kainų</span>
                )}
              </div>
              {upNext.map((p, i) => {
                const sum = (Number(p.kiekis) || 0) * (Number(p.kaina) || 0);
                return (
                  <ReviewRow
                    key={`pos-${rowKey(p)}-${i}`}
                    conf={p.confidence}
                    reason={cleanUserText(p._confidence_reason)}
                    primary={p.aprasymas || 'Pozicija'}
                    secondary={p.skyrius || p.kategorija || '—'}
                    meta={[
                      p.kiekis != null ? ltQuantity(p.kiekis, p.mato_vnt) : null,
                      sum > 0 ? ltEur(sum) : null,
                    ].filter(Boolean).join(' · ') || null}
                    reasonHint={p.kiekis == null ? 'Kiekis neaptiktas' : null}
                    onClick={() => handlePositionClick(p)}
                    onAccept={onAcceptRow ? () => onAcceptRow(p) : null}
                    onReject={onReviewStatusChange
                      ? () => onReviewStatusChange('position', rowKey(p), 'rejected') : null}
                    onEdit={onOpenRowDetail ? () => onOpenRowDetail(p) : null}
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

// ── Trust strip — € at risk on the left, human-verified share on the right ──
function TrustStrip({ meter, risk }) {
  const { t } = useTranslation();
  // Mixed units cannot be added: before prices exist the meter counts rows, and
  // the risk line says the € figure is not available yet rather than printing a
  // Σ of kg + m² + vnt. that means nothing.
  const pct = Math.round((meter.usePrices ? meter.share : meter.countShare) * 100);
  return (
    <div
      className="px-3 py-2"
      style={{
        background: 'hsl(var(--bg-1))',
        borderBottom: '1px solid hsl(var(--border) / 0.5)',
      }}
    >
      <div className="flex items-baseline justify-between gap-2" style={{ fontSize: 11 }}>
        <span
          style={{ color: risk.usePrices ? 'hsl(var(--conf-low))' : 'hsl(var(--muted-foreground))' }}
          title={t('project.patikra.riskTitle')}
        >
          {risk.usePrices
            ? t('project.patikra.risk', { amount: ltEur(risk.amount) })
            : t('project.patikra.riskNoPrices')}
        </span>
        <span className="text-muted-foreground mono tabular whitespace-nowrap">
          {t('project.patikra.remaining', { count: risk.count })}
        </span>
      </div>
      <div className="mt-1.5 flex items-center gap-2">
        <span className="text-muted-foreground whitespace-nowrap" style={{ fontSize: 10 }}>
          {t('project.patikra.trust')}
        </span>
        <span
          className="flex-1 rounded-full overflow-hidden"
          style={{ height: 5, background: 'hsl(var(--border))' }}
          role="progressbar"
          aria-valuenow={pct}
          aria-valuemin={0}
          aria-valuemax={100}
          aria-label={t('project.patikra.trust')}
        >
          <span
            className="block h-full"
            style={{ width: `${Math.min(100, Math.max(0, pct))}%`, background: 'hsl(var(--primary))' }}
          />
        </span>
        <span
          className="mono tabular text-foreground"
          style={{ fontSize: 10 }}
          title={meter.usePrices
            ? t('project.patikra.trustTitleEur', {
              verified: ltEur(meter.verified), total: ltEur(meter.total) })
            : t('project.patikra.trustTitleRows', {
              verified: meter.verifiedCount, total: meter.totalCount })}
        >
          {pct}%
        </span>
      </div>
    </div>
  );
}

// ── „Paskutinis pataisymas" — the € ripple of the fix that just landed ──────
function RippleCard({ ripple, count }) {
  const { t } = useTranslation();
  const { diff } = ripple;
  const delta = diff?.deltaEur || 0;
  return (
    <div
      className="mx-2.5 my-2 rounded-sm px-2.5 py-2"
      style={{
        background: 'hsl(var(--source-table) / 0.08)',
        border: '1px solid hsl(var(--source-table) / 0.35)',
        fontSize: 11.5,
      }}
    >
      <div className="flex items-baseline justify-between gap-2 font-semibold text-foreground">
        <span className="min-w-0">{t('project.patikra.rippleTitle', { label: ripple.label })}</span>
        {ripple.before != null && ripple.after != null && (
          <span className="mono tabular whitespace-nowrap">
            {ltNumber(ripple.before)} → {ltQuantity(ripple.after, ripple.unit)}
          </span>
        )}
      </div>
      <p className="mt-1 text-muted-foreground">
        {t('project.patikra.rippleRows', { count: diff?.count || 0 })}
        {diff?.usePrices && (
          <>
            {' · '}
            <span className="mono tabular">{delta >= 0 ? '+' : '−'}{ltEur(Math.abs(delta))}</span>
          </>
        )}
      </p>
      {count > 0 && (
        <p className="mt-1 font-semibold" style={{ color: 'hsl(var(--source-table))' }}>
          ◉ {t('project.patikra.learned', { count })}
        </p>
      )}
    </div>
  );
}

/** One correction in the log, in the contractor's words. */
function correctionLabel(c) {
  const path = String(c?.field_path || '').split('.');
  const field = path[0];
  const names = {
    lubu_auksciai: 'Lubų aukštis',
    walls_paint_override: 'Sienų apdaila',
    stretch_ceiling_override: 'Įtempiamos lubos',
    glaistimo_lygis: 'Glaistymo lygis',
    sienos_storis_m: 'Sienos storis',
  };
  const label = names[field] || field;
  const room = c?.room_nr ? ` · patalpa ${c.room_nr}` : '';
  return `${label}${room}`;
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
      title={`${confTitle} · spustelėkite peržiūrai`}
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
                title="Kaip suskaičiuota — atidaryti skaičiavimą"
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
