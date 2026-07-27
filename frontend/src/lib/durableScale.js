// Durable, zoom-invariant per-page scale stored in project.data.pageScalesDurable[pageNr].
// Canonical unit: metres of reality per PDF point. Survives cache-clear (rides project JSON).
import { uncalibratedScale } from './measureGeometry.js';
import { roomPageOf } from './roomZones.js';

export function getPageScaleDurable(project, pageNr) {
  const map = (project && project.pageScalesDurable) || {};
  return map[pageNr] || uncalibratedScale();
}

export function setPageScaleDurable(project, pageNr, scale, applyToPages) {
  const map = { ...((project && project.pageScalesDurable) || {}) };
  map[pageNr] = scale;
  if (Array.isArray(applyToPages)) for (const p of applyToPages) map[p] = scale;
  return { ...project, pageScalesDurable: map };
}

// renderScale = CSS px per PDF point (react-pdf viewport.scale at the current zoom).
export function pxPerMeterFromDurable(scale, renderScale) {
  const mpp = scale.metersPerPointX || 0;
  return mpp > 0 ? renderScale / mpp : 0;
}

export function durableFromPxPerMeter(pixelsPerMeter, renderScale) {
  const mpp = pixelsPerMeter > 0 ? renderScale / pixelsPerMeter : 0;
  return { metersPerPointX: mpp, metersPerPointY: mpp, calibrated: mpp > 0, source: 'user', anisotropic: false };
}

// ── Auto-calibration from the extractor's own data (2026-07-14) ─────────────
// Every traced room stores polygon_pct (0..1 display fractions), plotas_m2
// (from the eksplikacija) and the page size in PDF points. The median m² per
// fractional-area across a page's traced rooms gives the page's real-world
// area, hence an isotropic meters-per-point — measurements read real meters
// with NO manual calibration. Marked source 'auto' so the UI can disclose it;
// a user calibration always overrides (merge order in the viewer).
const AUTO_SCALE_SOURCES = ['auto_floodfill', 'corrected', 'manual'];

// Robustness gates (audit P2). An auto scale silently drives every measurement
// on the page, so it must be hard to fool:
//   · ≥3 samples per page (2 samples had no majority — their "median" was a mean
//     of the two, so one leaked polygon dragged the page's scale halfway);
//   · samples outside [0.25×, 4×] of the median are discarded as leaks/slivers;
//   · a polygon smaller than MIN_POLYGON_FRAC of the page is float noise, whose
//     m²/frac blows up into a 1:∞ scale;
//   · rooms that disagree about the page size cannot be normalised together.
export const AUTO_SCALE_MIN_SAMPLES = 3;
const AUTO_SCALE_OUTLIER_LO = 0.25;
const AUTO_SCALE_OUTLIER_HI = 4;
const MIN_POLYGON_FRAC = 1e-6;

// True median (ascending input). The old code called the mean of two samples a
// "median" — with n=2 that is exactly what it was.
function medianOfSorted(sorted) {
  const n = sorted.length;
  if (n === 0) return NaN;
  return n % 2 ? sorted[(n - 1) / 2] : (sorted[n / 2 - 1] + sorted[n / 2]) / 2;
}

export function autoPageScalesFromRooms(rooms = []) {
  const byPage = new Map();
  for (const r of rooms || []) {
    const poly = r?.polygon_pct;
    const m2 = Number(r?.plotas_m2);
    const W = Number(r?.page_width_pdf);
    const H = Number(r?.page_height_pdf);
    const page = roomPageOf(r);
    if (!Array.isArray(poly) || poly.length < 3) continue;
    if (!(m2 > 0) || !(W > 0) || !(H > 0) || !page) continue;
    if (!AUTO_SCALE_SOURCES.includes(r?.polygon_source)) continue;
    let sum = 0;
    for (let i = 0; i < poly.length; i++) {
      const [x1, y1] = poly[i];
      const [x2, y2] = poly[(i + 1) % poly.length];
      sum += x1 * y2 - x2 * y1;
    }
    const frac = Math.abs(sum) / 2;  // fraction of the page area
    if (!(frac > MIN_POLYGON_FRAC)) continue;
    let entry = byPage.get(page);
    if (!entry) { entry = { samples: [], W, H, conflict: false }; byPage.set(page, entry); }
    else if (entry.W !== W || entry.H !== H) entry.conflict = true;
    entry.samples.push(m2 / frac);
  }
  const out = {};
  for (const [page, { samples, W, H, conflict }] of byPage) {
    if (conflict) continue;                              // ambiguous page size → no auto scale
    if (samples.length < AUTO_SCALE_MIN_SAMPLES) continue;
    const sorted = [...samples].sort((a, b) => a - b);
    const rough = medianOfSorted(sorted);
    const kept = sorted.filter((s) => s >= rough * AUTO_SCALE_OUTLIER_LO
                                   && s <= rough * AUTO_SCALE_OUTLIER_HI);
    if (kept.length < AUTO_SCALE_MIN_SAMPLES) continue;  // too few survivors → stay honest
    const medM2 = medianOfSorted(kept);                  // kept is still ascending
    const mpp = Math.sqrt(medM2 / (W * H));
    if (!Number.isFinite(mpp) || mpp <= 0) continue;
    out[page] = { metersPerPointX: mpp, metersPerPointY: mpp, calibrated: true, source: 'auto' };
  }
  return out;
}
