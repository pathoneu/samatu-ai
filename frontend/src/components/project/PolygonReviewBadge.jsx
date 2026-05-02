/**
 * PolygonReviewBadge — per-room indicator showing whether the room has
 * a manual polygon (🟢 polygonas) or only Vision-extracted bbox (🟡 tik bbox).
 *
 * Click → activates the room and switches PDF to its page so the user
 * can trace it.
 */

export default function PolygonReviewBadge({ room, onClick }) {
  const hasPolygon = Array.isArray(room?.polygon_pdf) && room.polygon_pdf.length >= 3;
  const hasBbox = !hasPolygon && room?.bbox_pct
    && room.bbox_pct.w > 0 && room.bbox_pct.h > 0;

  if (!hasPolygon && !hasBbox) return null;

  const cls = hasPolygon
    ? 'bg-emerald-500/15 text-emerald-300 border-emerald-500/30'
    : 'bg-amber-500/15 text-amber-300 border-amber-500/30';
  const dot = hasPolygon ? '🟢' : '🟡';
  const label = hasPolygon ? 'polygonas' : 'tik bbox — apvesk';
  const title = hasPolygon
    ? `Manualiai apibrėžtas polygonas (${room.polygon_pdf.length} taškų)`
    : 'AI rado bendrą zoną, bet tikslus polygon dar neapibrėžtas. Spauskite, kad apvesti.';

  return (
    <button
      onClick={onClick}
      title={title}
      className={`inline-flex items-center gap-1 px-1.5 py-0.5 rounded border text-[10px] font-medium ${cls}`}
    >
      <span>{dot}</span>
      <span>{label}</span>
    </button>
  );
}
