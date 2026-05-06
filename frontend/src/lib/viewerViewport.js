export const VIEWER_MIN_SCALE = 0.3;
export const VIEWER_MAX_SCALE = 3;
export const VIEWER_WHEEL_STEP = 0.1;

export function clampViewerScale(scale) {
  const clamped = Math.max(VIEWER_MIN_SCALE, Math.min(VIEWER_MAX_SCALE, scale));
  return Number(clamped.toFixed(2));
}

export function nextWheelScale(currentScale, deltaY) {
  const direction = deltaY < 0 ? 1 : -1;
  return clampViewerScale(currentScale + direction * VIEWER_WHEEL_STEP);
}

export function getAnchoredZoomScroll({
  scrollLeft,
  scrollTop,
  viewportX,
  viewportY,
  oldScale,
  newScale,
}) {
  const scaleRatio = newScale / oldScale;
  return {
    scrollLeft: Math.max(0, Math.round((scrollLeft + viewportX) * scaleRatio - viewportX)),
    scrollTop: Math.max(0, Math.round((scrollTop + viewportY) * scaleRatio - viewportY)),
  };
}
