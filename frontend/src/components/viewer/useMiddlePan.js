/**
 * useMiddlePan — the middle mouse button drags the drawing from any tool (Pathon v3 W5-B, B5; coverage #178;
 * Togal and Kreo both pan on the wheel button). A held middle button scrolls the viewport and no page layer
 * sees the press, so a measurement being drawn keeps its points. While the hand (H / Space, useDragPan) is out
 * it handles the middle button itself — this one stands aside. The browser's own wheel-click auto-scroll is
 * prevented over the drawing only.
 */
import { useEffect } from 'react';

export default function useMiddlePan({ rootRef, enabled = true }) {
  useEffect(() => {
    const root = rootRef?.current;
    const el = root?.querySelector('[data-testid="viewer-canvas"]');
    if (!enabled || !el) return undefined;
    let drag = null;
    const down = (e) => {
      if (e.button !== 1 || root.hasAttribute('data-pan')) return;
      e.preventDefault();
      e.stopPropagation();
      drag = { x: e.clientX, y: e.clientY, id: e.pointerId };
      try { el.setPointerCapture(e.pointerId); } catch { /* pointer already gone */ }
      root.setAttribute('data-middle-pan', '1');
    };
    const move = (e) => {
      if (!drag || drag.id !== e.pointerId) return;
      e.stopPropagation();
      el.scrollBy({ left: drag.x - e.clientX, top: drag.y - e.clientY, behavior: 'auto' });
      drag = { ...drag, x: e.clientX, y: e.clientY };
    };
    const up = (e) => {
      if (!drag || drag.id !== e.pointerId) return;
      e.stopPropagation();
      try { el.releasePointerCapture(e.pointerId); } catch { /* already released */ }
      drag = null;
      root.removeAttribute('data-middle-pan');
    };
    // no auto-scroll compass and no middle-click paste / open over the drawing
    const noAuto = (e) => { if (e.button === 1) e.preventDefault(); };
    const opts = { capture: true };
    el.addEventListener('pointerdown', down, opts);
    el.addEventListener('pointermove', move, opts);
    el.addEventListener('pointerup', up, opts);
    el.addEventListener('pointercancel', up, opts);
    el.addEventListener('mousedown', noAuto, opts);
    el.addEventListener('auxclick', noAuto, opts);
    return () => {
      el.removeEventListener('pointerdown', down, opts);
      el.removeEventListener('pointermove', move, opts);
      el.removeEventListener('pointerup', up, opts);
      el.removeEventListener('pointercancel', up, opts);
      el.removeEventListener('mousedown', noAuto, opts);
      el.removeEventListener('auxclick', noAuto, opts);
      root.removeAttribute('data-middle-pan');
    };
  }, [rootRef, enabled]);
}
