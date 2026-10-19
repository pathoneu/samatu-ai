// Measurement entities live in project.data.measurements[]. Geometry in PDF points.
import { realPathLengthM, netAreaM2 } from './measureGeometry.js';

let _seq = 0;
const uid = () => (typeof crypto !== 'undefined' && crypto.randomUUID)
  ? crypto.randomUUID() : `m_${Date.now()}_${_seq++}`;

export const DEFAULT_COUNT_TYPES = [
  { id: 'rozetes', label: 'Rozetės', color: '#2a6fb5', shape: 'circle' },
  { id: 'jungikliai', label: 'Jungikliai', color: '#7c3aed', shape: 'square' },
  { id: 'sviestuvai', label: 'Šviestuvai', color: '#d97706', shape: 'diamond' },
  { id: 'durys', label: 'Durys', color: '#16a34a', shape: 'check' },
  { id: 'langai', label: 'Langai', color: '#854d0e', shape: 'square' },
  { id: 'santechnika', label: 'Santechnikos taškai', color: '#0d9488', shape: 'circle' },
];

// User-defined count types (founder 2026-07-14: no fixed list — you name what
// you're counting). Colors/shapes cycle; ids are diacritic-free slugs.
// No red: red means an error on the drawing (Pathon v3 overlay vocabulary). Types saved with a colour keep it.
const COUNT_TYPE_COLORS = ['#2a6fb5', '#7c3aed', '#d97706', '#16a34a', '#854d0e', '#0d9488', '#be185d', '#4d7c0f'];
export const COUNT_TYPE_SHAPES = ['circle', 'square', 'diamond', 'check'];
export const COUNT_TYPE_SHAPE_NAMES = { circle: 'apskritimas', square: 'kvadratas', diamond: 'rombas', check: 'varnelė' };

/**
 * The colour and shape a new type gets (Pathon v3 W5-A A7 [#114]: meaning never rides on colour alone): the
 * first (colour, shape) pair no existing type has — the shape changes with every new type as well as the
 * colour, so two types side by side differ in both. `want.shape` asks for a shape (the picker's choice).
 */
export function nextTypeLook(existing = [], want = {}) {
  const used = new Set((existing || []).map((t) => `${t.color}|${t.shape}`));
  const shapes = want.shape && COUNT_TYPE_SHAPES.includes(want.shape) ? [want.shape] : null;
  const n = COUNT_TYPE_COLORS.length * COUNT_TYPE_SHAPES.length;
  const start = (existing || []).length;
  for (let k = 0; k < n; k += 1) {
    const i = start + k;
    const color = COUNT_TYPE_COLORS[i % COUNT_TYPE_COLORS.length];
    const shape = shapes ? shapes[0] : COUNT_TYPE_SHAPES[(i + Math.floor(i / COUNT_TYPE_COLORS.length)) % COUNT_TYPE_SHAPES.length];
    if (!used.has(`${color}|${shape}`)) return { color, shape };
  }
  const i = start;
  return { color: COUNT_TYPE_COLORS[i % COUNT_TYPE_COLORS.length], shape: shapes ? shapes[0] : COUNT_TYPE_SHAPES[i % COUNT_TYPE_SHAPES.length] };
}

export function makeCountType(label, existing = [], want = {}) {
  const clean = String(label || '').trim();
  const slug = clean.toLowerCase().normalize('NFKD').replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '') || 'tipas';
  let id = slug;
  let n = 2;
  while (existing.some((t) => t.id === id)) id = `${slug}-${n++}`;
  return { id, label: clean || 'Tipas', ...nextTypeLook(existing, want) };
}

// Rebuild a type list from existing count marks (projects saved before custom
// types existed) so legacy tallies keep their legend rows.
export function countTypesFromMeasurements(measurements = []) {
  const seen = new Map();
  for (const m of measurements) {
    if (m.kind !== 'count' || !m.typeId || seen.has(m.typeId)) continue;
    const legacy = DEFAULT_COUNT_TYPES.find((t) => t.id === m.typeId);
    seen.set(m.typeId, legacy || { id: m.typeId, label: m.typeId, color: m.color || '#2a6fb5', shape: 'circle' });
  }
  return [...seen.values()];
}

// kind: 'distance' | 'perimeter' | 'area' | 'count' | 'annotation'
export function makeMeasurement(kind, pageNr, points, extra = {}) {
  return {
    id: uid(), kind, page: pageNr, points,
    holes: kind === 'area' ? (extra.holes || []) : undefined,
    classification: extra.classification || '',
    color: extra.color || '#2a6fb5',
    confidence: extra.confidence || 'amber',
    source: extra.source || 'user',
    created_at: new Date().toISOString(),
    ...extra,
  };
}

export function measurementValue(m, scale) {
  if (m.kind === 'area') {
    return { value: netAreaM2(m.points, m.holes, scale), secondary: realPathLengthM(m.points, scale, true) };
  }
  if (m.kind === 'distance' || m.kind === 'perimeter') {
    return { value: realPathLengthM(m.points, scale, false) };
  }
  return { value: 0 };
}
