/**
 * CursorHint — one Lithuanian sentence to the right of the pointer while it is over the drawing (Pathon
 * v3 click model, W1-B B3; Kreo §3). The sentence is lib/cursorHints' for the mode and its state; a layer
 * can flash why a click did nothing (CURSOR_HINT_EVENT). Hidden at rest, off the drawing, over the tool
 * cards and while a menu, a dialog or the draft's pop-up is open — it never covers what is being chosen.
 *
 * `resolve({ shift })` returns the sentence for the current state (Shift changes the distance hint).
 */
import { useEffect, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { CURSOR_HINT_EVENT, CURSOR_HINT_FLASH_MS } from '@/lib/cursorHints';

const OFFSET_X = 18;
const OFFSET_Y = 16;
const OPEN_LAYER = '[role="menu"], [role="dialog"], [role="alertdialog"], [data-draft-menu]';

export default function CursorHint({ rootRef, resolve, enabled = true, mode = null }) {
  const [pos, setPos] = useState(null);          // { x, y, shift } while the pointer is on the drawing
  const [flash, setFlash] = useState(null);      // a moment's „why nothing happened"
  const frame = useRef(0);
  const last = useRef(null);

  useEffect(() => {
    if (!enabled) { setPos(null); return undefined; }
    const onMove = (e) => {
      last.current = e;
      if (frame.current) return;
      frame.current = requestAnimationFrame(() => {
        frame.current = 0;
        const ev = last.current;
        const root = rootRef?.current;
        const canvas = root?.querySelector('[data-testid="viewer-canvas"]');
        const t = ev?.target;
        const over = !!(canvas && t instanceof Node && canvas.contains(t));
        if (!over || document.querySelector(OPEN_LAYER)) { setPos(null); return; }
        setPos({ x: ev.clientX, y: ev.clientY, shift: !!ev.shiftKey });
      });
    };
    const onKey = (e) => { if (e.key === 'Shift') setPos((p) => (p ? { ...p, shift: e.type === 'keydown' } : p)); };
    const onLeave = () => setPos(null);
    // capture: the hand and the outline editor stop pointer events below the viewport; the hint still sees them
    window.addEventListener('pointermove', onMove, { capture: true, passive: true });
    window.addEventListener('keydown', onKey, true);
    window.addEventListener('keyup', onKey, true);
    document.addEventListener('pointerleave', onLeave);
    window.addEventListener('blur', onLeave);
    return () => {
      window.removeEventListener('pointermove', onMove, { capture: true });
      window.removeEventListener('keydown', onKey, true);
      window.removeEventListener('keyup', onKey, true);
      document.removeEventListener('pointerleave', onLeave);
      window.removeEventListener('blur', onLeave);
      if (frame.current) cancelAnimationFrame(frame.current);
      frame.current = 0;
    };
  }, [enabled, rootRef]);

  useEffect(() => {
    let timer = 0;
    const onFlash = (e) => {
      setFlash(e.detail?.text || null);
      clearTimeout(timer);
      timer = setTimeout(() => setFlash(null), CURSOR_HINT_FLASH_MS);
    };
    window.addEventListener(CURSOR_HINT_EVENT, onFlash);
    return () => { window.removeEventListener(CURSOR_HINT_EVENT, onFlash); clearTimeout(timer); };
  }, []);

  if (!enabled || !pos || typeof document === 'undefined') return null;
  const text = flash || resolve?.({ shift: pos.shift }) || null;
  if (!text) return null;
  // Right of the pointer; flipped to its left near the window's right edge.
  const flip = pos.x > window.innerWidth - 340;
  const style = flip
    ? { right: window.innerWidth - pos.x + OFFSET_X, top: pos.y + OFFSET_Y }
    : { left: pos.x + OFFSET_X, top: pos.y + OFFSET_Y };
  return createPortal(
    <div
      role="status"
      aria-live="polite"
      data-testid="cursor-hint"
      data-mode={mode || undefined}
      data-flash={flash ? '1' : undefined}
      className="fixed z-popover pointer-events-none max-w-[320px] rounded bg-primary text-primary-foreground text-ui leading-snug px-2 py-1 shadow-md"
      style={style}
    >
      {text}
    </div>,
    document.body,
  );
}
