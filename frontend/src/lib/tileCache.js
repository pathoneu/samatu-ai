/**
 * Sprint 1: LRU cache for rendered ImageBitmap tiles.
 *
 * Browsers don't eagerly GC ImageBitmaps — confirmed pdf.js memory pain
 * in long sessions. We MUST call .close() on evicted bitmaps to free
 * GPU memory.
 *
 * Key shape: `${pageIdx}:${zoomLevel}` — e.g. "0:1.5" for page 0 at 1.5×.
 */
import { LRUCache } from 'lru-cache';

export function createTileCache({ max = 30 } = {}) {
  const cache = new LRUCache({
    max,
    disposeAfter: (value) => {
      if (value && typeof value.close === 'function') {
        try { value.close(); } catch { /* ignore */ }
      }
    },
  });

  return {
    get: (k) => cache.get(k),
    set: (k, v) => cache.set(k, v),
    has: (k) => cache.has(k),
    clear: () => cache.clear(),
    size: () => cache.size,
  };
}

export const tileCache = createTileCache({ max: 30 });
