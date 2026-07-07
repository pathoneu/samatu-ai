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
  const prev = base || { metersPerPointX: mpp, metersPerPointY: mpp, calibrated: false, source: 'user' };
  const next = { ...prev, calibrated: true, source: 'user',
    metersPerPointX: useAxis === 'x' ? mpp : prev.metersPerPointX,
    metersPerPointY: useAxis === 'y' ? mpp : prev.metersPerPointY };
  next.anisotropic =
    Math.abs(next.metersPerPointX - next.metersPerPointY) /
      Math.max(next.metersPerPointX, next.metersPerPointY) > 0.02;
  return next;
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
