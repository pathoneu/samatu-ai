// Durable, zoom-invariant per-page scale stored in project.data.pageScalesDurable[pageNr].
// Canonical unit: metres of reality per PDF point. Survives cache-clear (rides project JSON).
import { uncalibratedScale } from './measureGeometry.js';

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

export function autoPageScalesFromRooms(rooms = []) {
  const byPage = new Map();
  for (const r of rooms || []) {
    const poly = r?.polygon_pct;
    const m2 = Number(r?.plotas_m2);
    const W = Number(r?.page_width_pdf);
    const H = Number(r?.page_height_pdf);
    const page = r?.puslapio_nr ?? r?.page_nr;
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
    if (!(frac > 0)) continue;
    let entry = byPage.get(page);
    if (!entry) { entry = { samples: [], pageAreaPt2: W * H }; byPage.set(page, entry); }
    entry.samples.push(m2 / frac);
  }
  const out = {};
  for (const [page, { samples, pageAreaPt2 }] of byPage) {
    // A single sample could be a leaked polygon setting the whole page's
    // scale — require 2+ and take the median.
    if (samples.length < 2) continue;
    samples.sort((a, b) => a - b);
    const n = samples.length;
    const medM2 = n % 2 ? samples[(n - 1) / 2] : (samples[n / 2 - 1] + samples[n / 2]) / 2;
    const mpp = Math.sqrt(medM2 / pageAreaPt2);
    if (!Number.isFinite(mpp) || mpp <= 0) continue;
    out[page] = { metersPerPointX: mpp, metersPerPointY: mpp, calibrated: true, source: 'auto' };
  }
  return out;
}
