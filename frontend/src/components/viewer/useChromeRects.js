/**
 * useChromeRects — where things are on the drawing, relative to the canvas chrome (Pathon v3 W1-B B6).
 * The selection bar stands next to the selected room's label and the layer legend steps out of its way;
 * both need the label's box as the drawing scrolls and zooms. Measured on the viewport's scroll, on
 * window resize and every 300 ms (zoom and re-layout fire no scroll) — the same cadence the coach marks
 * use. State changes only when a box moved, so a still drawing renders nothing.
 *
 * frameEl — the chrome element (state, so the hook starts once it exists).
 * targets: { key: selector | [selectors…] } — the first selector that matches inside the viewer wins.
 * Returns { frame: {width, height} | null, rects: { key: {left, top, width, height} | null } }.
 */
import { useEffect, useRef, useState } from 'react';

const round = (r) => ({ left: Math.round(r.left), top: Math.round(r.top), width: Math.round(r.width), height: Math.round(r.height) });

export default function useChromeRects(frameEl, targets) {
  const [state, setState] = useState({ frame: null, rects: {} });
  const key = JSON.stringify(targets);
  const lastRef = useRef('');
  useEffect(() => {
    if (!frameEl) return undefined;
    const spec = JSON.parse(key);
    const root = frameEl.closest('[data-tv-root]') || document;
    let raf = 0;
    const measure = () => {
      raf = 0;
      const f = frameEl.getBoundingClientRect();
      const rects = {};
      for (const [k, sel] of Object.entries(spec)) {
        let found = null;
        for (const s of (Array.isArray(sel) ? sel : [sel]).filter(Boolean)) {
          const el = root.querySelector(s);
          const r = el?.getBoundingClientRect();
          if (r && (r.width > 0 || r.height > 0)) { found = round({ left: r.left - f.left, top: r.top - f.top, width: r.width, height: r.height }); break; }
        }
        rects[k] = found;
      }
      const next = { frame: { width: Math.round(f.width), height: Math.round(f.height) }, rects };
      const sig = JSON.stringify(next);
      if (sig !== lastRef.current) { lastRef.current = sig; setState(next); }
    };
    const schedule = () => { if (!raf) raf = requestAnimationFrame(measure); };
    measure();
    const canvas = root.querySelector?.('[data-testid="viewer-canvas"]');
    canvas?.addEventListener('scroll', schedule, { passive: true });
    window.addEventListener('resize', schedule);
    const id = setInterval(schedule, 300);
    return () => {
      canvas?.removeEventListener('scroll', schedule);
      window.removeEventListener('resize', schedule);
      clearInterval(id);
      if (raf) cancelAnimationFrame(raf);
    };
  }, [frameEl, key]);
  return state;
}
