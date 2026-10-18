/**
 * useDragPan — drag the drawing with the hand (Pathon v3 click model, W1-B; Togal §2b „Pan (Q / hold
 * Space)", Kreo §3 „Space + left drag").
 *
 * The hand is out while `armed` (the „Rankutė" tool, key H) or while Space is held over the drawing
 * (`space`, from any tool — the key comes from lib/viewerShortcuts' panHold entry). Then a left or middle
 * drag on the drawing scrolls the viewport. It listens in the CAPTURE phase on the viewport itself and
 * stops the pointer events there, so no page layer under it — a measurement draft, the outline editor, a
 * room click — ever sees the drag: the tool that was armed keeps its points and goes on when Space is let
 * go. Clicks are swallowed for the same reason. The cursor says what a drag does (grab / grabbing).
 *
 * Space is taken only while the pointer is over the drawing and no text field has the focus — elsewhere
 * Space keeps its usual job (pressing a focused button, scrolling a list). Over the drawing it is the hand
 * even when a button outside still holds the focus (a room row just clicked): the key down and up are both
 * stopped, so that button is not pressed again.
 *
 * Returns { panning, dragging }.
 */
import { useEffect, useRef, useState } from 'react';
import { isPanHoldKey } from '@/lib/viewerShortcuts';

const isTyping = (t) => !!t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.tagName === 'SELECT' || t.isContentEditable);

export default function useDragPan({ rootRef, armed = false, space = false }) {
  const [dragging, setDragging] = useState(false);
  const [spaceHeld, setSpaceHeld] = useState(false);
  const dragRef = useRef(null);
  const overCanvasRef = useRef(false);
  const spaceHeldRef = useRef(false);
  const panning = armed || spaceHeld;

  // Space held over the drawing → the hand, until it is let go (or the window loses focus).
  useEffect(() => {
    if (!space) { setSpaceHeld(false); return undefined; }
    const canvasOf = () => rootRef?.current?.querySelector('[data-testid="viewer-canvas"]') || null;
    const onMove = (e) => {
      const c = canvasOf();
      overCanvasRef.current = !!(c && e.target instanceof Node && c.contains(e.target));
    };
    const down = (e) => {
      if (!isPanHoldKey(e) || isTyping(e.target)) return;
      if (!overCanvasRef.current) return;
      e.preventDefault();                       // no page scroll, no button press
      if (!spaceHeldRef.current) { spaceHeldRef.current = true; setSpaceHeld(true); }
    };
    const up = (e) => {
      if (!isPanHoldKey(e) || !spaceHeldRef.current) return;
      e.preventDefault();
      spaceHeldRef.current = false;
      setSpaceHeld(false);
    };
    const release = () => { spaceHeldRef.current = false; setSpaceHeld(false); };
    window.addEventListener('pointermove', onMove, { capture: true, passive: true });
    window.addEventListener('keydown', down, true);
    window.addEventListener('keyup', up, true);
    window.addEventListener('blur', release);
    return () => {
      window.removeEventListener('pointermove', onMove, { capture: true });
      window.removeEventListener('keydown', down, true);
      window.removeEventListener('keyup', up, true);
      window.removeEventListener('blur', release);
      spaceHeldRef.current = false;
      setSpaceHeld(false);
    };
  }, [space, rootRef]);

  useEffect(() => {
    const root = rootRef?.current;
    const el = root?.querySelector('[data-testid="viewer-canvas"]');
    if (!panning || !el) return undefined;
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
  }, [panning, rootRef]);

  return { panning, dragging };
}

/** The cursor rule while the hand is out — every layer of the drawing shows grab / grabbing. */
export const PAN_CURSOR_CSS = `
[data-tv-root][data-pan] [data-testid="viewer-canvas"],
[data-tv-root][data-pan] [data-testid="viewer-canvas"] * { cursor: grab !important; }
[data-tv-root][data-pan][data-pan-dragging] [data-testid="viewer-canvas"],
[data-tv-root][data-pan][data-pan-dragging] [data-testid="viewer-canvas"] * { cursor: grabbing !important; }
`;
