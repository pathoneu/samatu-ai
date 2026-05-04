// frontend/src/lib/gestures/g4-color-sample.js
/**
 * Sprint 2 G4 helpers — read a pixel color out of the rendered canvas
 * and build the recompute payload. The actual zone-detection (which
 * polygons match the sampled color) is delegated to the backend in
 * Sprint 4; for now G4 sends just the click point as a 1-pixel polygon.
 */

const WHITE_THRESHOLD = 240;  // any channel >240 → background-ish

export function rgbAt(ctx, x, y) {
  const { data } = ctx.getImageData(x, y, 1, 1);
  return [data[0], data[1], data[2]];
}

export function isWhitish([r, g, b]) {
  return r >= WHITE_THRESHOLD && g >= WHITE_THRESHOLD && b >= WHITE_THRESHOLD;
}

export function buildColorZonePayload({ targetRoomId, colorRgb, polygonsPct }) {
  return { targetRoomId, colorRgb, polygonsPct };
}
