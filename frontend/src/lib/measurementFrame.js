/**
 * measurementFrame — moving stored measurements into the frame the viewer now stores them in (2026-10-16).
 *
 * Until 2026-10-16 the viewer gave makeEmbedAdapter EmbedPDF's `page.size`, which is the DISPLAYED size
 * (lib/viewerEngine/pageRotation.mediaboxSizeFrom says why). On a /Rotate 90 or 270 sheet a point was
 * therefore stored as (fx · H, fy · W) — unrotated-frame fractions times the SWAPPED mediabox size — instead
 * of (fx · W, fy · H). Positions round-tripped, so nothing looked wrong, but lengths came out × H/W along one
 * axis and × W/H along the other. Now the adapter gets the mediabox size, and a project carries
 * `measurementsFrame: 'mediabox'` once its points are in that frame.
 *
 * `migrateMeasurementFrame` converts a project's old points once: x' = x · W/H, y' = y · H/W (W, H the
 * mediabox) on rotated pages only; sheets at 0° / 180° were never affected. Pure.
 */
import { mediaboxSizeFrom, normalizeRotation } from './viewerEngine/pageRotation.js';

export const MEASUREMENTS_FRAME = 'mediabox';

function scalePoint(p, kx, ky) {
  if (!p || typeof p !== 'object' || !Number.isFinite(Number(p.x)) || !Number.isFinite(Number(p.y))) return p;
  return { ...p, x: Number(p.x) * kx, y: Number(p.y) * ky };
}

/**
 * @param {Array<object>} measurements  stored measurements ({page, points, holes?, …}), 1-based pages
 * @param {Array<{size: {width, height}, rotation: number}>} pages  EmbedPDF's document pages (0-based)
 * @param {string|null|undefined} frame  the project's `measurementsFrame`
 * @param {object} [scales]  the project's `pageScalesDurable` ({page: {source, …}})
 * @returns {{measurements, frame: 'mediabox', changed: number, recheckScales: number[]}|null}
 *   null when the project is already in the mediabox frame or the pages are not known yet.
 *   `changed`: measurements whose points moved. `recheckScales`: rotated sheets with a calibration he
 *   DREW (source 'user'): its metres per point were derived from a line in the old frame, along a direction
 *   nobody recorded, so it cannot be converted — the viewer asks him to check it once.
 */
export function migrateMeasurementFrame(measurements, pages, frame, scales = {}) {
  if (frame === MEASUREMENTS_FRAME) return null;
  if (!Array.isArray(pages) || pages.length === 0 || pages.some((p) => !p?.size)) return null;
  const factors = new Map();            // 1-based page → [kx, ky]
  pages.forEach((page, i) => {
    const rot = normalizeRotation(page.rotation);
    if (rot !== 90 && rot !== 270) return;
    const mb = mediaboxSizeFrom(page.size, rot);
    if (!mb) return;
    factors.set(i + 1, [mb.width / mb.height, mb.height / mb.width]);
  });
  let changed = 0;
  const out = (Array.isArray(measurements) ? measurements : []).map((m) => {
    const f = factors.get(Number(m?.page));
    if (!f || !Array.isArray(m.points)) return m;
    changed += 1;
    const [kx, ky] = f;
    return {
      ...m,
      points: m.points.map((p) => scalePoint(p, kx, ky)),
      ...(Array.isArray(m.holes) ? { holes: m.holes.map((h) => (Array.isArray(h) ? h.map((p) => scalePoint(p, kx, ky)) : h)) } : {}),
    };
  });
  const recheckScales = [...factors.keys()]
    .filter((page) => String(scales?.[page]?.source || scales?.[String(page)]?.source || '') === 'user')
    .sort((a, b) => a - b);
  return { measurements: changed ? out : measurements || [], frame: MEASUREMENTS_FRAME, changed, recheckScales };
}
