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
  { id: 'langai', label: 'Langai', color: '#dc2626', shape: 'square' },
  { id: 'santechnika', label: 'Santechnikos taškai', color: '#0d9488', shape: 'circle' },
];

// User-defined count types (founder 2026-07-14: no fixed list — you name what
// you're counting). Colors/shapes cycle; ids are diacritic-free slugs.
const COUNT_TYPE_COLORS = ['#2a6fb5', '#7c3aed', '#d97706', '#16a34a', '#dc2626', '#0d9488', '#be185d', '#4d7c0f'];
const COUNT_TYPE_SHAPES = ['circle', 'square', 'diamond', 'check'];

export function makeCountType(label, existing = []) {
  const clean = String(label || '').trim();
  const slug = clean.toLowerCase().normalize('NFKD').replace(/[\u0300-\u036f]/g, '')
    .replace(/[^a-z0-9]+/g, '-').replace(/^-+|-+$/g, '') || 'tipas';
  let id = slug;
  let n = 2;
  while (existing.some((t) => t.id === id)) id = `${slug}-${n++}`;
  const i = existing.length;
  return {
    id,
    label: clean || 'Tipas',
    color: COUNT_TYPE_COLORS[i % COUNT_TYPE_COLORS.length],
    shape: COUNT_TYPE_SHAPES[Math.floor(i / COUNT_TYPE_COLORS.length) % COUNT_TYPE_SHAPES.length] || COUNT_TYPE_SHAPES[i % COUNT_TYPE_SHAPES.length],
  };
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
