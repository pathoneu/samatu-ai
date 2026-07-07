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
