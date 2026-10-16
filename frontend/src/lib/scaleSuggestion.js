/**
 * scaleSuggestion — what a two-point calibration MEASURES as a drawing scale, and the standard scale it is
 * closest to. Togal's „Snap to standard scales" (2026-10-16 analysis §2): a person clicks two wall
 * corners and types 4,00 m; the clicks are a pixel off, so the ratio comes out 1:49,4 — the sheet is 1:50.
 * Pure; the dialog decides whether to offer the rounding (within STANDARD_SNAP_PCT, like the pair lane's
 * 3 % in backend plan_dimensions._mastelis).
 */
import { DRAWING_SCALES, METERS_PER_POINT_AT_1_TO_1 } from './durableScale.js';

const TO_M = { mm: 0.001, cm: 0.01, m: 1, in: 0.0254, ft: 0.3048 };
export const STANDARD_SNAP_PCT = 3;

/** `{measured, nearest, diffPct, within}` or null for a degenerate line or length. */
export function suggestStandardScale(pdfLen, length, unit = 'm') {
  const metres = Number(length) * (TO_M[unit] ?? 1);
  if (!(pdfLen > 0) || !(metres > 0)) return null;
  const measured = metres / pdfLen / METERS_PER_POINT_AT_1_TO_1;
  const nearest = DRAWING_SCALES.reduce((a, s) => (Math.abs(s - measured) < Math.abs(a - measured) ? s : a));
  const diffPct = (Math.abs(nearest - measured) / nearest) * 100;
  return { measured, nearest, diffPct, within: diffPct <= STANDARD_SNAP_PCT };
}

/** The PageScale of a drawing scale 1:`ratio`, as the user's own calibration. */
export function standardScalePageScale(ratio) {
  const mpp = ratio * METERS_PER_POINT_AT_1_TO_1;
  return { metersPerPointX: mpp, metersPerPointY: mpp, calibrated: true, source: 'user', label: `1:${ratio}`, anisotropic: false };
}
