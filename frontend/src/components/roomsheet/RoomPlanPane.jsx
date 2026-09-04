/**
 * RoomPlanPane — the drawing, framed on the room, with only the marks the data
 * can actually support.
 *
 * What it draws, and why only these:
 *  • the room OUTLINE, when `polygon_pct` exists (9 of 11 rooms on the dev
 *    corpus; the rest have only a marker);
 *  • K1…Kn at the outline's real direction changes, labelled „kampai iš
 *    kontūro" so nobody reads them as marks printed on the drawing;
 *  • the room-number ring at `marker_pct`.
 *
 * What it deliberately does NOT draw: doors and windows. `elementai` carries no
 * geometry and never has — the mockup's D1/L1 rings were illustrative. Inventing
 * them would be the one thing this screen exists to stop, so the pane says so in
 * words instead and the card carries the count and the sizes.
 *
 * v1 renders the page through the evidence endpoint as an image rather than
 * mounting EmbedPDF: the viewer has no focus-region entry point that could be
 * added without editing its files, and a crop the server already caches is
 * honest, fast, and correct. Overlay coordinates are page-percent, so they are
 * mapped through `paddedCropRect` — the endpoint grows every rect it is handed,
 * and skipping that would slide every mark off its room.
 */

import { useMemo } from 'react';
import { useTranslation } from 'react-i18next';
import {
  cornersFromPolygon, paddedCropRect, pageToCropPct, polygonToCropPct,
} from '@/lib/roomSheet';
import { evidenceUrl } from '@/lib/roomSheetApi';

const FULL_PAGE = [0, 0, 1, 1];

export default function RoomPlanPane({ room, projectId, highlightCorners = false }) {
  const { t } = useTranslation();

  const region = Array.isArray(room?.region_pct) ? room.region_pct : FULL_PAGE;
  const page = room?.page;

  const { src, crop } = useMemo(() => {
    if (page == null) return { src: null, crop: FULL_PAGE };
    const r = region.map((v) => Number(v).toFixed(4)).join(',');
    return {
      src: evidenceUrl(`/api/projects/${encodeURIComponent(projectId)}`
        + `/evidence?page=${page}&rect=${r}&dpi=140`),
      // The endpoint pads what it is given; the overlay must live in the SAME
      // rectangle the image actually covers.
      crop: paddedCropRect(region),
    };
  }, [projectId, page, region]);

  const outline = useMemo(
    () => polygonToCropPct(room?.polygon_pct, crop), [room?.polygon_pct, crop],
  );
  const corners = useMemo(() => cornersFromPolygon(room?.polygon_pct)
    .map((c) => ({ ...c, ...pageToCropPct([c.x, c.y], crop) }))
    .filter((c) => c.inside), [room?.polygon_pct, crop]);
  const marker = useMemo(() => (Array.isArray(room?.marker_pct)
    ? pageToCropPct(room.marker_pct, crop) : null), [room?.marker_pct, crop]);

  const points = outline
    ? outline.map((p) => `${(p.x * 100).toFixed(3)},${(p.y * 100).toFixed(3)}`).join(' ')
    : null;

  return (
    <div className="flex min-w-0 flex-col gap-2">
      <p className="font-mono text-[13px] text-muted-foreground">
        {page != null
          ? t('project.roomSheet.planCaption', { page, room: room?.nr })
          : t('project.roomSheet.cropFailed')}
      </p>

      <div className="relative overflow-hidden rounded-[2px] border border-border bg-card">
        {src && (
          <img
            src={src}
            alt={t('project.roomSheet.planCaption', { page, room: room?.nr })}
            className="block w-full"
            decoding="async"
          />
        )}
        {/* preserveAspectRatio="none": the SVG's 0–100 box is stretched onto the
            image box, which is exactly the crop rectangle the marks live in. */}
        <svg
          viewBox="0 0 100 100"
          preserveAspectRatio="none"
          className="pointer-events-none absolute inset-0 h-full w-full"
          aria-hidden="true"
        >
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
          {corners.map((c) => (
            <g key={c.label}>
              <circle
                cx={c.x * 100}
                cy={c.y * 100}
                r="1.6"
                fill="hsl(var(--card))"
                stroke="hsl(var(--accent-2))"
                strokeWidth={highlightCorners ? '1.4' : '0.8'}
                vectorEffect="non-scaling-stroke"
              />
            </g>
          ))}
          {marker?.inside && (
            <circle
              cx={marker.x * 100}
              cy={marker.y * 100}
              r="2.4"
              fill="none"
              stroke="hsl(var(--destructive))"
              strokeWidth="1.2"
              vectorEffect="non-scaling-stroke"
            />
          )}
        </svg>

        {/* Corner labels sit in HTML, not SVG: the non-uniform viewBox scale
            would squash SVG text into unreadable ovals. */}
        {corners.map((c) => (
          <span
            key={`lbl-${c.label}`}
            className="pointer-events-none absolute -translate-x-1/2 translate-y-1 rounded-[2px] bg-card/90 px-1 font-mono text-[11px] leading-tight text-foreground"
            style={{ left: `${c.x * 100}%`, top: `${c.y * 100}%` }}
          >
            {c.label}
          </span>
        ))}
      </div>

      <ul className="flex flex-wrap gap-x-4 gap-y-1 text-[13px] text-muted-foreground">
        {outline && (
          <li className="flex items-center gap-1.5">
            <span
              className="inline-block h-[3px] w-4 rounded-full"
              style={{ background: 'hsl(var(--accent-2))' }}
            />
            {t('project.roomSheet.legendOutline')}
          </li>
        )}
        {corners.length > 0 && (
          <li className="flex items-center gap-1.5">
            <span
              className="inline-block h-2.5 w-2.5 rounded-full border-2"
              style={{ borderColor: 'hsl(var(--accent-2))' }}
            />
            {t('project.roomSheet.legendCorners')}
          </li>
        )}
        {marker?.inside && (
          <li className="flex items-center gap-1.5">
            <span
              className="inline-block h-2.5 w-2.5 rounded-full border-2"
              style={{ borderColor: 'hsl(var(--destructive))' }}
            />
            {t('project.roomSheet.legendMarker')}
          </li>
        )}
      </ul>

      {!outline && (
        <p className="text-[13px] leading-snug text-muted-foreground">
          {t('project.roomSheet.noOutline')}
        </p>
      )}
      <p className="text-[13px] leading-snug text-muted-foreground">
        {t('project.roomSheet.noOpeningMarks')}
      </p>
    </div>
  );
}
