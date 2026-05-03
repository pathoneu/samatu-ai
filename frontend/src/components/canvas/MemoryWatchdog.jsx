// frontend/src/components/canvas/MemoryWatchdog.jsx
/**
 * Sprint 1: address pdf.js #20198 memory leak in long sessions.
 *
 * Polls performance.memory every 30 s. If usedJSHeapSize > 500 MB AND the
 * user is idle (last interaction >30 s ago), call onReset() so the parent
 * can pdfDoc.destroy() and recreate from the cached Blob.
 *
 * No-op in browsers without performance.memory (Firefox, Safari).
 */
import { useEffect, useRef } from 'react';

const HEAP_THRESHOLD = 500 * 1024 * 1024;  // 500 MB
const IDLE_MS = 30_000;
const POLL_MS = 30_000;

export function MemoryWatchdog({ onReset }) {
  const lastInteractionRef = useRef(Date.now());

  useEffect(() => {
    const bumpInteraction = () => { lastInteractionRef.current = Date.now(); };
    window.addEventListener('pointerdown', bumpInteraction);
    window.addEventListener('keydown', bumpInteraction);
    window.addEventListener('wheel', bumpInteraction, { passive: true });

    const interval = setInterval(() => {
      const mem = performance.memory;
      if (!mem) return;
      const heap = mem.usedJSHeapSize;
      const idleFor = Date.now() - lastInteractionRef.current;
      if (heap > HEAP_THRESHOLD && idleFor > IDLE_MS) {
        console.warn(`[MemoryWatchdog] heap=${(heap / 1024 / 1024).toFixed(0)} MB idle=${(idleFor / 1000).toFixed(0)}s — resetting`);
        onReset?.();
        lastInteractionRef.current = Date.now();
      }
    }, POLL_MS);

    return () => {
      window.removeEventListener('pointerdown', bumpInteraction);
      window.removeEventListener('keydown', bumpInteraction);
      window.removeEventListener('wheel', bumpInteraction);
      clearInterval(interval);
    };
  }, [onReset]);

  return null;
}
