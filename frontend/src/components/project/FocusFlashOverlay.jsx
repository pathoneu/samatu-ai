/**
 * FocusFlashOverlay — pulsing rectangle drawn on the floor plan over a
 * room's bbox_pct when user clicks the room in the side panel (Sprint G6).
 *
 * Triggered by room change (focusedRoom). Animation: scale-in + 3 pulses,
 * total ~1.8s. Auto-removes itself when complete OR when focusedRoom changes.
 *
 * Placement: absolute positioning relative to the rendered PDF page canvas
 * (parent must be position:relative). Uses room.bbox_pct ({x, y, w, h} as
 * fractions 0..1) and the rendered page dims (pageDims.width, .height).
 *
 * Style: blue accent (#2a6fb5 = construction blue per design tokens) with
 * a pulsing outer glow. No interaction — pointer-events: none.
 */

import { useEffect, useState } from 'react';

export default function FocusFlashOverlay({ width, height, room, page }) {
  // Re-key on room change to force CSS animation restart
  const [animKey, setAnimKey] = useState(0);
  const [visible, setVisible] = useState(false);

  useEffect(() => {
    if (!room || !room.bbox_pct || room.puslapio_nr !== page) {
      setVisible(false);
      return;
    }
    setAnimKey(k => k + 1);
    setVisible(true);
    // Auto-hide after 1.8s (matches CSS animation duration)
    const t = setTimeout(() => setVisible(false), 1800);
    return () => clearTimeout(t);
  }, [room, page]);

  if (!visible || !room?.bbox_pct) return null;

  const { x, y, w, h } = room.bbox_pct;
  if (typeof x !== 'number' || typeof y !== 'number') return null;

  const left = x * width;
  const top = y * height;
  const boxW = w * width;
  const boxH = h * height;

  return (
    <div
      key={animKey}
      className="focus-flash-overlay"
      style={{
        position: 'absolute',
        left, top, width: boxW, height: boxH,
        pointerEvents: 'none',
        border: '2px solid hsl(var(--primary))',
        borderRadius: 4,
        boxShadow: '0 0 0 0 hsl(var(--primary) / 0.7)',
        animation: 'focus-flash 1.8s ease-out',
        zIndex: 30,
      }}
    />
  );
}
