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
