// Verified geometry ported from ~/Desktop/PDFViewerModule/src/geometry (tsc-clean, 19/19 tests).
// CORE INVARIANT: all geometry is in PDF-point space (zoom/rotation invariant). One calibration
// ratio per page (metres of reality per PDF point, separate X/Y for stretched scans). Convert last.

const TO_M = { mm: 0.001, cm: 0.01, m: 1, in: 0.0254, ft: 0.3048 };

export function pdfDistance(a, b) { return Math.hypot(b.x - a.x, b.y - a.y); }

export function calibrateUniform(a, b, knownLength, unit = 'm', opts = {}) {
  const d = pdfDistance(a, b);
  if (d <= 1e-9) throw new Error('Kalibravimo linija per trumpa');
  const mpp = (knownLength * TO_M[unit]) / d;
  return { metersPerPointX: mpp, metersPerPointY: mpp, calibrated: true,
           source: opts.source || 'user', label: opts.label, anisotropic: false };
}

export function calibrateAxis(a, b, knownLength, unit, base, axis) {
  const dx = Math.abs(b.x - a.x), dy = Math.abs(b.y - a.y);
  const useAxis = axis || (dx >= dy ? 'x' : 'y');
  const span = useAxis === 'x' ? dx : dy;
  if (span <= 1e-9) throw new Error('Kalibravimo ašis per trumpa');
  const mpp = (knownLength * TO_M[unit]) / span;
  // AUDIT P0: a per-axis calibration on an UNCALIBRATED base has no other-axis
  // value to preserve — it used to leave that axis at 0 while flagging
  // calibrated:true, so every area on the page read 0,00 m² (and "apply to all
  // pages" poisoned the whole document). On a virgin page an axis calibration
  // therefore behaves exactly like a uniform one; the per-axis override only
  // makes sense once BOTH axes already carry a real ratio.
  const baseUsable = !!(base && base.calibrated
    && base.metersPerPointX > 0 && base.metersPerPointY > 0);
  if (!baseUsable) {
    return { metersPerPointX: mpp, metersPerPointY: mpp, calibrated: true,
             source: 'user', anisotropic: false };
  }
  const next = { ...base, calibrated: true, source: 'user',
    metersPerPointX: useAxis === 'x' ? mpp : base.metersPerPointX,
    metersPerPointY: useAxis === 'y' ? mpp : base.metersPerPointY };
  next.anisotropic =
    Math.abs(next.metersPerPointX - next.metersPerPointY) /
      Math.max(next.metersPerPointX, next.metersPerPointY) > 0.02;
  return next;
}

/**
 * storedAxisForDisplayAxis — which STORED (unrotated mediabox) axis the user's
 * on-screen "horizontal"/"vertical" choice refers to.
 *
 * AUDIT P1: measurements and calibration points live in unrotated mediabox
 * space, but the calibration dialog's labels describe what the user SEES. On a
 * page displayed at 90° or 270° the two are swapped, so "Tik horizontali" used
 * to calibrate the vertical ratio. Pure decision function — no rotation math
 * leaks into the dialog.
 *
 * @param displayAxis 'x' | 'y' | 'uniform'
 * @param displayRotation degrees the page is DISPLAYED at (0/90/180/270)
 */
export function storedAxisForDisplayAxis(displayAxis, displayRotation) {
  if (displayAxis !== 'x' && displayAxis !== 'y') return displayAxis;
  const rot = (((Number(displayRotation) || 0) % 360) + 360) % 360;
  const swapped = rot === 90 || rot === 270;
  if (!swapped) return displayAxis;
  return displayAxis === 'x' ? 'y' : 'x';
}

/**
 * axisSpanShare — |axis component| / |segment length| for a calibration pick.
 * Near 0 means the line is almost perpendicular to the chosen axis, where the
 * axis ratio is numerically meaningless (a 2 px span standing in for metres).
 * Callers reject below AXIS_SPAN_MIN_SHARE instead of silently mis-scaling.
 */
export const AXIS_SPAN_MIN_SHARE = 0.2;

export function axisSpanShare(a, b, axis) {
  const dx = Math.abs(b.x - a.x), dy = Math.abs(b.y - a.y);
  const len = Math.hypot(dx, dy);
  if (!(len > 0)) return 0;
  return (axis === 'y' ? dy : dx) / len;
}

// ── Draft commit hygiene ────────────────────────────────────────────────────
// Minimum vertices a committed measurement needs, per kind.
export const MIN_DRAFT_POINTS = { distance: 2, perimeter: 2, area: 3 };

/** Drop consecutive coincident vertices (the dbl-click commit path appends the
 *  terminal point twice — stored junk vertices made labels read a zero-length
 *  last segment). */
export function dedupeDraftPoints(points, eps = 0.5) {
  const pts = Array.isArray(points) ? points : [];
  return pts.filter((p, i) => i === 0
    || Math.hypot(p.x - pts[i - 1].x, p.y - pts[i - 1].y) > eps);
}

/**
 * draftCommitPoints — dedupe, then enforce the per-kind minimum. Returns null
 * when the draft must NOT commit. AUDIT P2: the old guard checked `>= 2` for
 * every tool AFTER dedupe, so a 2-click 'area' (click + double-click on the
 * same spot) committed a degenerate polygon that rendered as a 0,00 m² artifact.
 */
export function draftCommitPoints(points, kind, eps = 0.5) {
  const pts = dedupeDraftPoints(points, eps);
  const min = MIN_DRAFT_POINTS[kind] ?? 2;
  return pts.length >= min ? pts : null;
}

export function scaleFromRatio(ratio, label) {
  const mpp = (ratio / 72) * 0.0254;
  return { metersPerPointX: mpp, metersPerPointY: mpp, calibrated: true,
           source: 'standard', label: label || `1:${ratio}`, anisotropic: false };
}

export function uncalibratedScale() {
  return { metersPerPointX: 0, metersPerPointY: 0, calibrated: false, source: 'none' };
}

export function realDistanceM(a, b, s) {
  return Math.hypot((b.x - a.x) * s.metersPerPointX, (b.y - a.y) * s.metersPerPointY);
}

export function realPathLengthM(pts, s, closed = false) {
  const n = pts.length;
  if (n < 2) return 0;
  let m = 0;
  const last = closed ? n : n - 1;
  for (let i = 0; i < last; i++) m += realDistanceM(pts[i], pts[(i + 1) % n], s);
  return m;
}

export function shoelaceAreaM2(pts, s) {
  const n = pts.length;
  if (n < 3) return 0;
  let sum = 0;
  for (let i = 0; i < n; i++) {
    const p = pts[i], q = pts[(i + 1) % n];
    sum += (p.x * s.metersPerPointX) * (q.y * s.metersPerPointY)
         - (q.x * s.metersPerPointX) * (p.y * s.metersPerPointY);
  }
  return Math.abs(sum) / 2;
}

export function netAreaM2(outer, holes, s) {
  const gross = shoelaceAreaM2(outer, s);
  const cut = (holes || []).reduce((acc, h) => acc + shoelaceAreaM2(h, s), 0);
  return Math.max(0, gross - cut);
}

export function formatNumberLT(value, decimals = 2) {
  if (!Number.isFinite(value)) return '—';
  const fixed = value.toFixed(decimals);
  const dot = fixed.indexOf('.');
  const intRaw = dot >= 0 ? fixed.slice(0, dot) : fixed;
  const frac = dot >= 0 ? fixed.slice(dot + 1) : '';
  const neg = intRaw.startsWith('-');
  const digits = neg ? intRaw.slice(1) : intRaw;
  const grouped = digits.replace(/\B(?=(\d{3})+(?!\d))/g, ' ');
  const sign = neg ? '−' : '';
  return decimals > 0 ? `${sign}${grouped},${frac}` : `${sign}${grouped}`;
}

function gcd(a, b) { while (b) { [a, b] = [b, a % b]; } return a; }

export function formatFeetInches(meters, denom = 16) {
  const totalInches = meters / 0.0254;
  let inches = Math.abs(totalInches);
  let feet = Math.floor(inches / 12);
  inches -= feet * 12;
  let whole = Math.floor(inches);
  let num = Math.round((inches - whole) * denom);
  if (num === denom) { num = 0; whole += 1; }
  if (whole === 12) { feet += 1; whole = 0; }
  let frac = '';
  if (num > 0) { const g = gcd(num, denom); frac = ` ${num / g}/${denom / g}`; }
  const sign = totalInches < 0 && (feet > 0 || whole > 0 || num > 0) ? '−' : '';
  return `${sign}${feet}' ${whole}${frac}"`;
}

export function parseFeetInches(raw) {
  const s = String(raw).trim();
  if (!s) return null;
  const m = s.match(/^-?\s*(\d+(?:\.\d+)?)\s*'\s*(?:(\d+(?:\.\d+)?)\s*)?(?:(\d+)\/(\d+))?\s*"?$/);
  if (m) {
    const sign = /^\s*-/.test(s) ? -1 : 1;
    const feet = parseFloat(m[1]);
    const inches = m[2] ? parseFloat(m[2]) : 0;
    const fr = m[3] && m[4] ? parseInt(m[3], 10) / parseInt(m[4], 10) : 0;
    return sign * (feet * 12 + inches + fr) * 0.0254;
  }
  const mf = s.match(/^(-?\d+(?:\.\d+)?)\s*'$/);
  if (mf) return parseFloat(mf[1]) * 12 * 0.0254;
  const md = s.match(/^(\d{3,})$/);
  if (md) {
    const d = md[1];
    const inches = parseInt(d.slice(-2), 10);
    if (inches > 11) return null;
    return (parseInt(d.slice(0, -2), 10) * 12 + inches) * 0.0254;
  }
  return null;
}
