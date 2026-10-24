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

/** Metres of reality per PDF point at a drafting ratio (1 pt = 1/72 inch). */
export const METERS_PER_POINT_AT_1_TO_1 = 0.0254 / 72;

/**
 * Page scales the DRAWING states — the ratio the dimension-string lane
 * measured on each plan sheet (`_meta.plan_dimension_lane.mastelis`, e.g.
 * {"2": 50, "8": 25}: 1:50 on page 2, 1:25 on page 8). Exact, not derived
 * from areas, so the status bar can say „1:50 (iš brėžinio)" instead of
 * „nekalibruotas" on a sheet the engine already read (2026-09-13). A user
 * calibration still wins the merge; this only fills pages nobody calibrated.
 */
/**
 * `{page: {ratio, lane}}` — each sheet's ratio and the lane that read it: 'poros' (the dimension-pair lane,
 * `_meta.plan_dimension_lane.mastelis`) or 'geometrija' (the geometry lane, `_meta.geometrija.masteliai` — exact,
 * from the sheets' own dimension lines; 2026-09-19: objektas_h had no pairs and said „nekalibruotas" although
 * every sheet's scale was known).
 *
 * Merged PER PAGE (2026-10-06, objektas_a on production): the pair lane read sheets 4, 8, 9, 11… and the geometry
 * lane also sheet 2, the main floor plan, at 1:82 — but the pair lane's map was returned whole whenever it had any
 * page, so sheet 2 said „Mastelis nenustatytas". The pair lane's ratio wins on a page it has; the geometry lane's
 * fills every other page.
 */
function laneRatiosOf(project) {
  const meta = project?._meta || {};
  const out = {};
  const exact = meta.geometrija?.masteliai;
  if (exact && typeof exact === 'object') {
    for (const [page, v] of Object.entries(exact)) {
      const ratio = Number(v?.mastelis);
      if (ratio > 0) out[page] = { ratio, lane: 'geometrija' };
    }
  }
  const pairs = meta.plan_dimension_lane?.mastelis;
  if (pairs && typeof pairs === 'object') {
    for (const [page, v] of Object.entries(pairs)) {
      const ratio = Number(v);
      if (ratio > 0) out[page] = { ratio, lane: 'poros' };
    }
  }
  return out;
}

/** `{page: ratio}` the extraction read off the drawing — both lanes, merged per page (`laneRatiosOf`). */
export function laneMastelisOf(project) {
  const out = {};
  for (const [page, { ratio }] of Object.entries(laneRatiosOf(project))) out[page] = ratio;
  return out;
}

/** The drawing scales a sheet can state (backend plan_dimensions._STANDARD_SCALES, 1:20 … 1:500). */
export const DRAWING_SCALES = Object.freeze([20, 25, 30, 40, 50, 75, 100, 125, 150, 200, 250, 500]);
// A sheet read at the scale it writes carries exactly that scale's metres per point (the lane rounds them to six
// places: ≤ 7·10⁻⁵ off at 1:20); a scale measured from the strings is off by far more.
const STATED_EXACT = 1.5e-4;
// The pair lane gives what the strings measure as the nearest drawing scale within 3 % (backend
// plan_dimensions._mastelis: 1:49,4 → 1:50), the geometry lane as measured (→ 1:49).
const PAIR_SNAP = 0.03;

/** Is the geometry lane's record of a sheet (`{m_per_pt, mastelis}`) about this 1:N — however the lanes rounded it? */
function measuredAs(record, ratio) {
  if (!record) return false;
  if (Number(record.mastelis) === ratio) return true;
  const denom = Number(record.m_per_pt) / METERS_PER_POINT_AT_1_TO_1;
  if (!(denom > 0)) return false;
  const nearest = DRAWING_SCALES.reduce((a, s) => (Math.abs(s - denom) < Math.abs(a - denom) ? s : a));
  return (Math.abs(nearest - denom) / denom <= PAIR_SNAP ? nearest : Math.round(denom)) === ratio;
}

/**
 * Where each lane scale comes from — `{page: {kilme, uzrasyta, provenance?}}`. `provenance` = the backend's own
 * record (saltinis, patikimumas, tekstas, is_lapo, pastaba — v4 2026-10-24) when the geometry lane stored one for
 * this ratio; lib/scaleProvenance words the scale from it and falls back to `kilme` only for older blobs.
 *
 * 2026-10-06 (contractor walkthrough on objektas_h): the status bar said „1:115 (iš brėžinio)", which reads as a
 * scale written on the sheet; 1:115 is what the dimension strings MEASURE on a sheet printed at another size
 * than it was drawn. So:
 *   'uzrasytas'  the sheet writes this scale and its dimension strings agree — the lane took the written one
 *                (its metres per point are exactly the scale's);
 *   'ismatuotas' measured from the dimension strings: a ratio no drawing is drawn at, or one the strings measure
 *                although the sheet writes another (`uzrasyta`: what it writes — the lane's `mastelis_kitas`);
 *   'matmenys'   from the dimension strings, but whether written or measured cannot be told (the pair lane
 *                keeps only a rounded ratio, and the geometry lane has no record of that sheet).
 *
 * Each page is judged by what is known about ITS ratio — the one `laneMastelisOf` gives it (2026-10-06: the two
 * lanes are merged per page): the note of the lane that read the ratio first, and a record of the other lane only
 * when that lane measured the same ratio on the sheet (`measuredAs`) — a record of another ratio says nothing
 * about this one.
 */
// The backend's provenance keys (backend/geometry/scale.py `lane_record`; lib/scaleProvenance words them).
const PROVENANCE_SOURCES = ['user_line', 'dimension_lines', 'dimension_walls', 'stated', 'sibling', 'blank'];

/**
 * `{provenance}` for a geometry-lane record that carries the backend's provenance and is about ratio `r` (the
 * ratio the page shows — a record of another ratio says nothing about it); `{}` otherwise.
 */
function laneProvenanceOf(record, r) {
  if (!record || !PROVENANCE_SOURCES.includes(record.saltinis) || !measuredAs(record, r)) return {};
  const provenance = { saltinis: record.saltinis };
  for (const k of ['patikimumas', 'tekstas', 'pastaba']) if (typeof record[k] === 'string' && record[k]) provenance[k] = record[k];
  if (Number(record.is_lapo) > 0) provenance.is_lapo = Number(record.is_lapo);
  return { provenance };
}

export function laneScaleOriginOf(project) {
  const meta = project?._meta || {};
  const geo = meta.geometrija || {};
  const exact = geo.masteliai || {};
  const notes = { poros: meta.plan_dimension_lane?.mastelis_kitas || {}, geometrija: geo.masteliai_kiti || {} };
  const out = {};
  for (const [page, { ratio: r, lane }] of Object.entries(laneRatiosOf(project))) {
    const out0 = laneProvenanceOf(exact[page], r);
    const own = notes[lane]?.[page];
    const theirs = notes[lane === 'poros' ? 'geometrija' : 'poros']?.[page];
    const other = [own, theirs].find((n, i) => n && typeof n === 'object'
      && (i === 0 || !(Number(n.ismatuota) > 0) || Number(n.ismatuota) === r));
    if (other) {
      const uzrasyta = (Array.isArray(other.uzrasyta) ? other.uzrasyta : []).map(Number).filter((n) => n > 0);
      out[page] = { kilme: 'ismatuotas', uzrasyta, ...out0 };
      continue;
    }
    const g = measuredAs(exact[page], r) ? exact[page] : null;
    const mpp = Number(g?.m_per_pt);
    if (mpp > 0) {
      const written = DRAWING_SCALES.includes(r) && Number(g.mastelis) === r
        && Math.abs(mpp / (r * METERS_PER_POINT_AT_1_TO_1) - 1) <= STATED_EXACT;
      out[page] = { kilme: written ? 'uzrasytas' : 'ismatuotas', uzrasyta: [], ...out0 };
    } else {
      out[page] = { kilme: DRAWING_SCALES.includes(r) ? 'matmenys' : 'ismatuotas', uzrasyta: [], ...out0 };
    }
  }
  return out;
}

/**
 * `{page: PageScale}` from the lane's ratios. `origins` (laneScaleOriginOf) rides along as `kilme` /
 * `uzrasyta`, so the status bar can say where the scale comes from (lib/scaleLabel.js).
 */
export function pageScalesFromLane(mastelisByPage, origins = null) {
  const out = {};
  if (!mastelisByPage || typeof mastelisByPage !== 'object') return out;
  for (const [page, ratio] of Object.entries(mastelisByPage)) {
    const p = Number(page);
    const r = Number(ratio);
    if (!Number.isInteger(p) || p <= 0 || !(r > 0)) continue;
    const mpp = r * METERS_PER_POINT_AT_1_TO_1;
    const origin = origins?.[page] || origins?.[p];
    out[p] = {
      metersPerPointX: mpp, metersPerPointY: mpp, calibrated: true, source: 'plan', label: `1:${r}`,
      ...(origin ? { kilme: origin.kilme, uzrasyta: origin.uzrasyta || [] } : {}),
      ...(origin?.provenance ? { provenance: origin.provenance } : {}),
    };
  }
  return out;
}

/** The page scales the drawing gave this project, each with where it comes from. */
export function laneScalesOf(project) {
  return pageScalesFromLane(laneMastelisOf(project), laneScaleOriginOf(project));
}

// ── Confirming a lane scale (Togal-v2 W6, 2026-10-16) ────────────────────────
// Togal asks a person to confirm the scale it predicted (`isHintConfirmed`, research §2.2). A lane scale stays
// „spėjamas" until he does; confirming copies it into pageScalesDurable as his, with where it came from, so the
// status bar can say „Patvirtintas" and a later re-read that measures another ratio can be flagged
// (`laneRatio`). getPageScaleDurable is unchanged: a confirmed entry is an ordinary calibrated PageScale.
export const LANE_CONFIRMED = 'lane-confirmed';

const ratioOfMpp = (mpp) => (mpp > 0 ? Math.round(mpp / METERS_PER_POINT_AT_1_TO_1) : 0);

/** The durable record of confirming `laneScale` (a laneScalesOf entry), or null when it is not one. */
export function confirmedLaneScale(laneScale, at = Date.now()) {
  if (!laneScale?.calibrated || laneScale.source !== 'plan') return null;
  const mpp = Number(laneScale.metersPerPointX) || 0;
  if (!(mpp > 0)) return null;
  const ratio = ratioOfMpp(mpp);
  return {
    metersPerPointX: mpp,
    metersPerPointY: Number(laneScale.metersPerPointY) || mpp,
    calibrated: true,
    anisotropic: false,
    source: LANE_CONFIRMED,
    confirmed: true,
    label: laneScale.label || `1:${ratio}`,
    ...(laneScale.kilme ? { kilme: laneScale.kilme, uzrasyta: laneScale.uzrasyta || [] } : {}),
    ...(laneScale.provenance ? { provenance: laneScale.provenance } : {}),
    laneRatio: ratio,
    confirmedAt: new Date(at).toISOString(),
  };
}

/**
 * A pageScalesDurable map with each of `pages` set to its confirmed lane scale. Pages with no lane scale are
 * left as they were. Pure — the viewer applies it to its live map, confirmPageScalesDurable to a project.
 */
export function confirmLaneScales(durableMap, pages, laneScales, at = Date.now()) {
  const out = { ...(durableMap || {}) };
  for (const p of pages || []) {
    const rec = confirmedLaneScale(laneScales?.[p] ?? laneScales?.[String(p)], at);
    if (rec) out[p] = rec;
  }
  return out;
}

/** The project with `pages`' lane scales confirmed (laneScalesOf(project) unless given). */
export function confirmPageScalesDurable(project, pages, laneScales = laneScalesOf(project), at = Date.now()) {
  return { ...project, pageScalesDurable: confirmLaneScales(project?.pageScalesDurable, pages, laneScales, at) };
}

/**
 * A confirmation the drawing no longer supports: the lane now measures another ratio on that sheet than the one
 * he confirmed. `{confirmed, now}` ratios, or null.
 */
export function staleConfirmation(durableScale, laneScale) {
  if (durableScale?.source !== LANE_CONFIRMED || !laneScale?.calibrated) return null;
  const now = ratioOfMpp(Number(laneScale.metersPerPointX) || 0);
  const confirmed = Number(durableScale.laneRatio) || ratioOfMpp(Number(durableScale.metersPerPointX) || 0);
  return now > 0 && confirmed > 0 && now !== confirmed ? { confirmed, now } : null;
}
