// selectionPlacement — where the floating pieces of the drawing's chrome go so that none of them covers
// what the user is looking at (Pathon v3 click model, W1-B task B6).
//
//   placeSelectionBar — the action bar sits right above the selected room's label (or measurement), never
//     on it; below it when there is no room above; docked at the top centre when the selection is not on
//     screen. Always inside the canvas, right of the tool cards.
//   pickSpot — the layer legend takes the first corner that covers nothing it must not (the selected
//     label, the action bar, the pill, an open panel); if every corner covers something, the least.
//
// All rectangles are { left, top, width, height } in px relative to the canvas chrome (the frame).

export function rectRight(r) { return r.left + r.width; }
export function rectBottom(r) { return r.top + r.height; }

/** Overlap area of two rectangles (0 when apart), each grown by `pad` px. */
export function overlapArea(a, b, pad = 0) {
  if (!a || !b) return 0;
  const w = Math.min(rectRight(a) + pad, rectRight(b) + pad) - Math.max(a.left - pad, b.left - pad);
  const h = Math.min(rectBottom(a) + pad, rectBottom(b) + pad) - Math.max(a.top - pad, b.top - pad);
  return w > 0 && h > 0 ? w * h : 0;
}

/**
 * { anchor, frame: {width, height}, bar: {width, height}, gap, inset: {left, top, right, bottom} }
 * → { left, top, docked, side: 'above' | 'below' | 'docked' }
 */
export function placeSelectionBar({ anchor = null, frame, bar, gap = 10, inset = {} }) {
  const L = inset.left ?? 8; const T = inset.top ?? 8; const R = inset.right ?? 8; const B = inset.bottom ?? 8;
  const minLeft = L;
  const maxLeft = Math.max(minLeft, frame.width - R - bar.width);
  const clampX = (x) => Math.min(Math.max(x, minLeft), maxLeft);
  const docked = { left: clampX((L + frame.width - R - bar.width) / 2), top: T, docked: true, side: 'docked' };
  if (!anchor) return docked;
  // the selection must be at least partly on the canvas, or the bar has nothing to stand next to
  const visible = rectRight(anchor) > L && anchor.left < frame.width - R && rectBottom(anchor) > T && anchor.top < frame.height - B;
  if (!visible) return docked;
  const left = clampX(anchor.left + anchor.width / 2 - bar.width / 2);
  const above = anchor.top - gap - bar.height;
  if (above >= T) return { left, top: above, docked: false, side: 'above' };
  const below = rectBottom(anchor) + gap;
  if (below + bar.height <= frame.height - B) return { left, top: below, docked: false, side: 'below' };
  return docked;
}

/**
 * spots: [{ id, left, top }] in order of preference; size: {width, height}; avoid: [rects]
 * → the id of the first spot that touches none of `avoid`, else the one with the least overlap.
 */
export function pickSpot({ spots, size, avoid = [], pad = 6 }) {
  let best = null;
  for (const s of spots) {
    const box = { left: s.left, top: s.top, width: size.width, height: size.height };
    const cover = avoid.reduce((sum, r) => sum + overlapArea(box, r, pad), 0);
    if (cover === 0) return s.id;
    if (!best || cover < best.cover) best = { id: s.id, cover };
  }
  return best ? best.id : null;
}
