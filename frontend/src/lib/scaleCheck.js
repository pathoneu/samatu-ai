/**
 * scaleCheck — „Patikrinti mastelį" (Togal-v2 W6, 2026-10-16; Togal research §2.6: the Measure Tool against a
 * known dimension). Two clicks give the length the CURRENT scale makes of them, next to the dimension strings
 * the lane read nearest to that line on the same sheet — with what the current scale makes of each string's
 * own drawn line. A readout: it changes nothing. Pure.
 *
 * Spaces: the clicks arrive as UNROTATED mediabox PDF points (EmbedPDF), the strings' lines as DISPLAY-space
 * page fractions (lib/viewerEngine/pageRotation). Both are taken to display-space points before comparing.
 */
import { rotatePctPoint, normalizeRotation } from './viewerEngine/pageRotation.js';

function displaySize(pageSize, rotation) {
  const W = Number(pageSize?.width) || 0;
  const H = Number(pageSize?.height) || 0;
  const r = normalizeRotation(rotation);
  return r === 90 || r === 270 ? { W: H, H: W } : { W, H };
}

function toDisplayPt(p, pageSize, rotation, D) {
  const [x, y] = rotatePctPoint(p.x / pageSize.width, p.y / pageSize.height, rotation);
  return { x: x * D.W, y: y * D.H };
}

function pointSegmentDist(p, a, b) {
  const dx = b.x - a.x;
  const dy = b.y - a.y;
  const len2 = dx * dx + dy * dy;
  const t = len2 > 0 ? Math.max(0, Math.min(1, ((p.x - a.x) * dx + (p.y - a.y) * dy) / len2)) : 0;
  return Math.hypot(p.x - (a.x + t * dx), p.y - (a.y + t * dy));
}

/**
 * `{lengthM, lengthPt, nearest}` for two clicks `a`, `b` (mediabox points) on a sheet of `pageSize` points at
 * `rotation`, with `scale` (a PageScale; uncalibrated → lengthM null) and `strings` (dimensionStringsOf for this
 * sheet). nearest[i] = {text, value_m, drawnM, diffPct, distPt}: the string as written, its value, what the
 * current scale makes of its drawn line (null without a scale) and the difference in % of the written value.
 */
export function scaleCheckReadout({ a, b, scale, pageSize, rotation = 0, strings = [], count = 3 }) {
  if (!a || !b || !(pageSize?.width > 0) || !(pageSize?.height > 0)) return null;
  const mpp = scale?.calibrated ? Number(scale.metersPerPointX) || 0 : 0;
  const lengthPt = Math.hypot(b.x - a.x, b.y - a.y);
  const D = displaySize(pageSize, rotation);
  const A = toDisplayPt(a, pageSize, rotation, D);
  const B = toDisplayPt(b, pageSize, rotation, D);
  const nearest = (strings || [])
    .map((s) => {
      const [[x1, y1], [x2, y2]] = s.line_pct;
      const p1 = { x: x1 * D.W, y: y1 * D.H };
      const p2 = { x: x2 * D.W, y: y2 * D.H };
      const mid = { x: (p1.x + p2.x) / 2, y: (p1.y + p2.y) / 2 };
      const drawnPt = Math.hypot(p2.x - p1.x, p2.y - p1.y);
      const drawnM = mpp > 0 ? drawnPt * mpp : null;
      return {
        text: s.text,
        value_m: s.value_m,
        drawnM,
        diffPct: drawnM != null ? ((drawnM - s.value_m) / s.value_m) * 100 : null,
        distPt: pointSegmentDist(mid, A, B),
      };
    })
    .sort((x, y) => x.distPt - y.distPt)
    .slice(0, count);
  return { lengthPt, lengthM: mpp > 0 ? lengthPt * mpp : null, nearest };
}
