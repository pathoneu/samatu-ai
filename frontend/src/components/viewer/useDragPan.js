/**
 * useDragPan — drag the drawing with the hand (Pathon v3 click model, W1-B; Togal §2b „Pan (Q / hold
 * Space)", Kreo §3 „Space + left drag").
 *
 * While `armed` (the „Rankutė" tool, key H) a left or middle drag on the drawing scrolls the viewport.
 * It listens in the CAPTURE phase on the viewport itself and stops the pointer events there, so no page
 * layer under it — a measurement draft, the outline editor, a room click — ever sees the drag: the tool
 * that was armed keeps its points and continues when the hand is put away. Clicks are swallowed for the
 * same reason. The cursor says what a drag does (grab / grabbing) over the whole drawing.
 *
 * Returns { dragging }.
 */
import { useEffect, useRef, useState } from 'react';

export default function useDragPan({ rootRef, armed = false }) {
  const [dragging, setDragging] = useState(false);
  const dragRef = useRef(null);

  useEffect(() => {
    const root = rootRef?.current;
    const el = root?.querySelector('[data-testid="viewer-canvas"]');
    if (!armed || !el) return undefined;
    root.setAttribute('data-pan', '1');
    const stop = (e) => { e.stopPropagation(); };
    const down = (e) => {
      if (e.button !== 0 && e.button !== 1) return;
      e.preventDefault();
      e.stopPropagation();
      dragRef.current = { x: e.clientX, y: e.clientY, id: e.pointerId };
      try { el.setPointerCapture(e.pointerId); } catch { /* pointer already gone */ }
      root.setAttribute('data-pan-dragging', '1');
      setDragging(true);
    };
    const move = (e) => {
      e.stopPropagation();
      const d = dragRef.current;
      if (!d || d.id !== e.pointerId) return;
      el.scrollBy({ left: d.x - e.clientX, top: d.y - e.clientY, behavior: 'auto' });
      dragRef.current = { ...d, x: e.clientX, y: e.clientY };
    };
    const up = (e) => {
      e.stopPropagation();
      if (!dragRef.current) return;
      try { el.releasePointerCapture(e.pointerId); } catch { /* already released */ }
      dragRef.current = null;
      root.removeAttribute('data-pan-dragging');
      setDragging(false);
    };
    const swallow = (e) => { e.stopPropagation(); e.preventDefault(); };
    const opts = { capture: true };
    el.addEventListener('pointerdown', down, opts);
    el.addEventListener('pointermove', move, opts);
    el.addEventListener('pointerup', up, opts);
    el.addEventListener('pointercancel', up, opts);
    el.addEventListener('click', swallow, opts);
    el.addEventListener('dblclick', swallow, opts);
    el.addEventListener('contextmenu', stop, opts);
    return () => {
      root.removeAttribute('data-pan');
      root.removeAttribute('data-pan-dragging');
      el.removeEventListener('pointerdown', down, opts);
      el.removeEventListener('pointermove', move, opts);
      el.removeEventListener('pointerup', up, opts);
      el.removeEventListener('pointercancel', up, opts);
      el.removeEventListener('click', swallow, opts);
      el.removeEventListener('dblclick', swallow, opts);
      el.removeEventListener('contextmenu', stop, opts);
      dragRef.current = null;
      setDragging(false);
    };
  }, [armed, rootRef]);

  return { dragging };
}

/** The cursor rule while the hand is out — every layer of the drawing shows grab / grabbing. */
export const PAN_CURSOR_CSS = `
[data-tv-root][data-pan] [data-testid="viewer-canvas"],
[data-tv-root][data-pan] [data-testid="viewer-canvas"] * { cursor: grab !important; }
[data-tv-root][data-pan][data-pan-dragging] [data-testid="viewer-canvas"],
[data-tv-root][data-pan][data-pan-dragging] [data-testid="viewer-canvas"] * { cursor: grabbing !important; }
`;
