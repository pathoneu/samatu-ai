// scaleEntry — the scale chip's quick ways to set a sheet's scale (Pathon v3 W5-B, B8; coverage #22, #23):
// a typed „1:50", the standard list with the sheet's paper size, and „Šiam lapui mastelio nereikia" for
// schedules and specifications. The measured check (scale check card, two clicks on a known length) stays.
//
// A typed or picked ratio becomes HIS scale (lib/scaleSuggestion.standardScalePageScale, source 'user'). „Nereikia"
// is a durable entry that is not calibrated (source NOT_NEEDED): it never hides a scale read from the drawing
// (lib/pageScales merges calibrated durable entries only), the chip then says „Mastelio nereikia" and the
// detection button stops offering „Nustatyti mastelį". Pure.

import { DRAWING_SCALES } from './durableScale.js';
import { standardScalePageScale } from './scaleSuggestion.js';

export const NOT_NEEDED = 'nereikia';
export const MIN_RATIO = 1;
export const MAX_RATIO = 5000;

/** „1:50", „1 : 50", „50", „M 1:50", „1/50" → 50; anything else → null. */
export function parseRatio(text) {
  const s = String(text ?? '').trim().replace(/^m\s*/i, '').replace(/\s+/g, '');
  const m = /^(?:1[:/])?(\d+(?:[.,]\d+)?)$/.exec(s);
  if (!m) return null;
  const n = Number(m[1].replace(',', '.'));
  return Number.isFinite(n) && n >= MIN_RATIO && n <= MAX_RATIO ? n : null;
}

/** The PageScale a ratio sets (his own scale). */
export function scaleForRatio(ratio) {
  const n = Number(ratio);
  return n >= MIN_RATIO && n <= MAX_RATIO ? standardScalePageScale(n) : null;
}

/** The durable entry „Šiam lapui mastelio nereikia". */
export function notNeededEntry() {
  return { metersPerPointX: 0, metersPerPointY: 0, calibrated: false, source: NOT_NEEDED };
}

export function isNotNeeded(entry) {
  return entry?.source === NOT_NEEDED;
}

/** The standard ratios the chip lists, in order (lib/durableScale.DRAWING_SCALES). */
export function standardRatios() {
  return [...DRAWING_SCALES];
}

const ISO = [['A4', 210, 297], ['A3', 297, 420], ['A2', 420, 594], ['A1', 594, 841], ['A0', 841, 1189]];

/** „A3 · 420 × 297 mm" from a page size in points (either orientation, ISO A within 2 mm), else „420 × 297 mm". */
export function paperLabel(size) {
  const w = Number(size?.width);
  const h = Number(size?.height);
  if (!(w > 0) || !(h > 0)) return '';
  const wMm = Math.round((w * 25.4) / 72);
  const hMm = Math.round((h * 25.4) / 72);
  const lo = Math.min(wMm, hMm);
  const hi = Math.max(wMm, hMm);
  const iso = ISO.find(([, a, b]) => Math.abs(lo - a) <= 2 && Math.abs(hi - b) <= 2);
  return `${iso ? `${iso[0]} · ` : ''}${wMm} × ${hMm} mm`;
}
