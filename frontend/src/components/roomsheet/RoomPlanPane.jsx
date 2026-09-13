/**
 * RoomPlanPane — the drawing with the marks the data can actually support.
 *
 * WHOLE SHEET by default (founder, 2026-09-13: „kai pritraukia prie kažkokio
 * specifinio kambario, sunku atskirti" — dropped into a zoomed corner you lose
 * your bearings in the flat). The full page is shown with this room's place
 * framed and, on it, a rectangle wherever a fact was read (area label,
 * dimension strings, height marker…), labelled like the fact rows; hovering a
 * row lights its rectangle. „Priartinti prie patalpos" is the old framed view,
 * one click away, and „Padidinti lapą" opens the sheet in the zoomable viewer.
 *
 * What it draws, and why only these:
 *  • the room OUTLINE, when `polygon_pct` exists;
 *  • K1…Kn at the outline's real direction changes (framed view only — on the
 *    whole sheet they would be dots on dots), labelled „kampai iš kontūro" so
 *    nobody reads them as marks printed on the drawing;
 *  • the room-number ring at `marker_pct`;
 *  • the facts' own rectangles (`source.rect_pct`), this page's only.
 *
 * What it deliberately does NOT draw: doors and windows. `elementai` carries no
 * geometry and never has. Inventing them would be the one thing this screen
 * exists to stop, so the pane says so in words instead.
 *
 * The page renders through the evidence endpoint as an image; overlay
 * coordinates are page-percent mapped through `paddedCropRect` — the endpoint
 * grows every rect it is handed, and skipping that would slide every mark off
 * its room.
 */

import { useMemo, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Maximize2 } from 'lucide-react';
import { Dialog, DialogContent, DialogDescription, DialogTitle } from '@/components/ui/dialog';
import {
  FACT_LABEL_KEY, cornersFromPolygon, factMarks, paddedCropRect, pageToCropPct, polygonToCropPct,
} from '@/lib/roomSheet';
import { evidenceUrl } from '@/lib/roomSheetApi';
import { SheetViewer } from '@/components/roomsheet/EvidenceCrop';

const FULL_PAGE = [0, 0, 1, 1];
// Above this many direction changes the labels overlap into noise on a small
// room, so the count moves to the legend and the dots stay unlabelled.
const MAX_LABELLED_CORNERS = 8;

function rectToCrop(rect, crop) {
  if (!Array.isArray(rect) || rect.length !== 4) return null;
  const a = pageToCropPct([rect[0], rect[1]], crop);
  const b = pageToCropPct([rect[2], rect[3]], crop);
  const x = Math.max(0, a.x); const y = Math.max(0, a.y);
  const w = Math.min(1, b.x) - x; const h = Math.min(1, b.y) - y;
  return w > 0 && h > 0 ? { x, y, w, h } : null;
}

export default function RoomPlanPane({
  room, projectId, highlightCorners = false, facts = [],
  wholeSheet = true, onToggleWhole, activeFactKey = null,
}) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);

  const roomRegion = Array.isArray(room?.region_pct) ? room.region_pct : FULL_PAGE;
  const region = wholeSheet ? FULL_PAGE : roomRegion;
  const page = room?.page;

  const { path, src, crop } = useMemo(() => {
    if (page == null) return { path: null, src: null, crop: FULL_PAGE };
    const r = region.map((v) => Number(v).toFixed(4)).join(',');
    // 160 is the endpoint's dpi ceiling; the whole sheet is for bearings, not
    // reading, so it comes lighter and the viewer sharpens on demand.
    const p = `/api/projects/${encodeURIComponent(projectId)}`
      + `/evidence?page=${page}&rect=${r}&dpi=${wholeSheet ? 110 : 160}`;
    // The endpoint pads what it is given; the overlay must live in the SAME
    // rectangle the image actually covers.
    return { path: p, src: evidenceUrl(p), crop: paddedCropRect(region) };
  }, [projectId, page, region, wholeSheet]);

  const outline = useMemo(
    () => polygonToCropPct(room?.polygon_pct, crop), [room?.polygon_pct, crop],
  );
  const corners = useMemo(() => (wholeSheet ? [] : cornersFromPolygon(room?.polygon_pct)
    .map((c) => ({ ...c, ...pageToCropPct([c.x, c.y], crop) }))
    .filter((c) => c.inside)), [room?.polygon_pct, crop, wholeSheet]);
  const marker = useMemo(() => (Array.isArray(room?.marker_pct)
    ? pageToCropPct(room.marker_pct, crop) : null), [room?.marker_pct, crop]);
  const marks = useMemo(() => factMarks(facts, page, crop), [facts, page, crop]);
  const frame = useMemo(
    () => (wholeSheet && Array.isArray(room?.region_pct) ? rectToCrop(room.region_pct, crop) : null),
    [wholeSheet, room?.region_pct, crop],
  );

  const points = outline
    ? outline.map((p) => `${(p.x * 100).toFixed(3)},${(p.y * 100).toFixed(3)}`).join(' ')
    : null;
  const caption = page != null
    ? t(wholeSheet ? 'project.roomSheet.planCaptionWhole' : 'project.roomSheet.planCaption', { page, room: room?.nr })
    : t('project.roomSheet.cropFailed');

  return (
    <div className="flex min-w-0 flex-col gap-2">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="font-mono text-[13px] text-muted-foreground">{caption}</p>
        {page != null && (
          <div className="flex items-center gap-2">
            {onToggleWhole && (
              <button
                type="button"
                onClick={() => onToggleWhole(!wholeSheet)}
                className="inline-flex min-h-[36px] items-center rounded-[2px] border border-border bg-card px-3 text-[14px] font-semibold hover:bg-muted"
              >
                {t(wholeSheet ? 'project.roomSheet.planZoom' : 'project.roomSheet.planWhole')}
              </button>
            )}
            <button
              type="button"
              onClick={() => setOpen(true)}
              aria-label={t('project.roomSheet.planEnlarge')}
              title={t('project.roomSheet.planEnlarge')}
              className="inline-flex h-9 w-9 items-center justify-center rounded-[2px] border border-border bg-card text-[hsl(var(--ink-2))] hover:bg-muted"
            >
              <Maximize2 className="h-4 w-4" />
            </button>
          </div>
        )}
      </div>

      <div className="relative overflow-hidden rounded-[2px] border border-border bg-card">
        {src && (
          <img src={src} alt={caption} className="block w-full" decoding="async" />
        )}
        {/* preserveAspectRatio="none": the SVG's 0–100 box is stretched onto the
            image box, which is exactly the crop rectangle the marks live in. */}
        <svg
          viewBox="0 0 100 100"
          preserveAspectRatio="none"
          className="pointer-events-none absolute inset-0 h-full w-full"
          aria-hidden="true"
        >
          {frame && (
            <rect
              x={frame.x * 100} y={frame.y * 100} width={frame.w * 100} height={frame.h * 100}
              fill="hsl(var(--accent-2) / 0.06)"
              stroke="hsl(var(--accent-2))"
              strokeWidth="1.2"
              vectorEffect="non-scaling-stroke"
            />
          )}
          {points && (
            <polygon
              points={points}
              fill="hsl(var(--accent-2) / 0.10)"
              stroke="hsl(var(--accent-2))"
              strokeWidth="0.7"
              vectorEffect="non-scaling-stroke"
              strokeLinejoin="round"
            />
          )}
          {marks.map((m) => (
            <rect
              key={m.key}
              x={m.x * 100} y={m.y * 100} width={m.w * 100} height={m.h * 100}
              fill={m.key === activeFactKey ? 'hsl(var(--destructive) / 0.10)' : 'none'}
              stroke="hsl(var(--destructive))"
              strokeWidth={m.key === activeFactKey ? 2 : 1}
              strokeDasharray={m.key === activeFactKey ? undefined : '4 3'}
              vectorEffect="non-scaling-stroke"
            />
          ))}
        </svg>

        {/* Dots, rings and labels are HTML, not SVG: the stretched viewBox would
            squash circles into ellipses and text into ovals. */}
        {marks.map((m) => (
          <span
            key={`lbl-${m.key}`}
            className={`pointer-events-none absolute -translate-y-full rounded-[2px] px-1 font-mono text-[11px] uppercase leading-tight tracking-wide
              ${m.key === activeFactKey ? 'bg-[hsl(var(--destructive))] text-white' : 'bg-card/90 text-[hsl(var(--destructive))]'}`}
            style={{ left: `${m.x * 100}%`, top: `${m.y * 100}%` }}
          >
            {t(`project.roomSheet.${FACT_LABEL_KEY[m.key] || 'factPlotas'}`)}
          </span>
        ))}
        {corners.map((c) => (
          <span
            key={c.label}
            aria-hidden="true"
            className={`pointer-events-none absolute -translate-x-1/2 -translate-y-1/2 rounded-full border-2 bg-card
              ${highlightCorners ? 'h-3.5 w-3.5' : 'h-2.5 w-2.5'}`}
            style={{ left: `${c.x * 100}%`, top: `${c.y * 100}%`, borderColor: 'hsl(var(--accent-2))' }}
          />
        ))}
        {marker?.inside && (
          <span
            aria-hidden="true"
            className={`pointer-events-none absolute -translate-x-1/2 -translate-y-1/2 rounded-full border-2 ${wholeSheet ? 'h-5 w-5' : 'h-7 w-7'}`}
            style={{ left: `${marker.x * 100}%`, top: `${marker.y * 100}%`, borderColor: 'hsl(var(--destructive))' }}
          />
        )}
        {corners.length <= MAX_LABELLED_CORNERS && corners.map((c) => (
          <span
            key={`clbl-${c.label}`}
            className="pointer-events-none absolute -translate-x-1/2 translate-y-2 rounded-[2px] bg-card/90 px-1 font-mono text-[12px] leading-tight text-foreground"
            style={{ left: `${c.x * 100}%`, top: `${c.y * 100}%` }}
          >
            {c.label}
          </span>
        ))}
      </div>

      <ul className="flex flex-wrap gap-x-4 gap-y-1 text-[13px] text-muted-foreground">
        {frame && (
          <li className="flex items-center gap-1.5">
            <span className="inline-block h-3 w-4 border-2" style={{ borderColor: 'hsl(var(--accent-2))' }} />
            {t('project.roomSheet.legendRoomRegion')}
          </li>
        )}
        {outline && (
          <li className="flex items-center gap-1.5">
            <span className="inline-block h-[3px] w-4 rounded-full" style={{ background: 'hsl(var(--accent-2))' }} />
            {t('project.roomSheet.legendOutline')}
          </li>
        )}
        {marks.length > 0 && (
          <li className="flex items-center gap-1.5">
            <span className="inline-block h-3 w-4 border-2 border-dashed" style={{ borderColor: 'hsl(var(--destructive))' }} />
            {t('project.roomSheet.legendFactMarks')}
          </li>
        )}
        {corners.length > 0 && (
          <li className="flex items-center gap-1.5">
            <span className="inline-block h-2.5 w-2.5 rounded-full border-2" style={{ borderColor: 'hsl(var(--accent-2))' }} />
            {corners.length <= MAX_LABELLED_CORNERS
              ? t('project.roomSheet.legendCorners')
              : t('project.roomSheet.legendCornersCount', { count: corners.length })}
          </li>
        )}
        {marker?.inside && (
          <li className="flex items-center gap-1.5">
            <span className="inline-block h-2.5 w-2.5 rounded-full border-2" style={{ borderColor: 'hsl(var(--destructive))' }} />
            {t('project.roomSheet.legendMarker')}
          </li>
        )}
      </ul>

      {!outline && (
        <p className="text-[13px] leading-snug text-muted-foreground">{t('project.roomSheet.noOutline')}</p>
      )}
      <p className="text-[13px] leading-snug text-muted-foreground">{t('project.roomSheet.noOpeningMarks')}</p>

      {path && (
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogContent className="max-h-[96vh] w-[min(96vw,1500px)] max-w-none gap-2 overflow-hidden p-4">
            <div className="min-w-0 pr-8">
              <DialogTitle className="text-[16px] font-semibold">{t('project.roomSheet.planEnlarge')}</DialogTitle>
              <DialogDescription className="font-mono text-[13px] text-muted-foreground">
                {t('project.roomSheet.planCaptionWhole', { page })}
              </DialogDescription>
            </div>
            {open && (
              <SheetViewer
                cropUrl={path}
                alt={caption}
                rect={Array.isArray(room?.region_pct) ? room.region_pct : null}
              />
            )}
            <p className="text-[13px] text-muted-foreground">{t('project.roomSheet.cropHint')}</p>
          </DialogContent>
        </Dialog>
      )}
    </div>
  );
}
