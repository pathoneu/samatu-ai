// frontend/src/components/canvas/gestures/G2AddCount.jsx
/**
 * Sprint 2 G2 — click-to-add count.
 *
 * Increments the *currently-selected* pozicija's `kiekis` by 1 and
 * stores the click point so AnnotationLayer can render a green dot.
 * If no pozicija is selected, shows a Lithuanian hint and bails.
 *
 * Spec §5.4 G2 row.
 */
import { useCallback } from 'react';
import { useStore } from 'zustand';
import { viewerStore } from '../../../lib/viewerStore';
import { canvasPxToPdfPct } from '../../../lib/coordTransform';
import { addSymbol } from '../../../lib/gestureApi';
import { abortRegistry } from '../../../lib/abortRegistry';

export function useG2Handler({ rooms, pozicijos, currentAssumptions,
                               canvasWidth, canvasHeight, containerRef,
                               onRecomputed, onGestureEvent }) {
  const tool = useStore(viewerStore, (s) => s.currentTool);
  const scale = useStore(viewerStore, (s) => s.scale);
  const translate = useStore(viewerStore, (s) => s.translate);
  const selection = useStore(viewerStore, (s) => s.selection);

  return useCallback(async (e) => {
    if (tool !== 'g2') return false;
    if (selection?.kind !== 'pozicija') {
      alert('Pasirink poziciją dešinėje (KŽ panelėje), tada spausk simbolį brėžinyje.');
      return true;
    }
    const rect = containerRef.current?.getBoundingClientRect();
    if (!rect) return true;
    const click = canvasPxToPdfPct(
      { px: e.clientX - rect.left, py: e.clientY - rect.top },
      { scale, translate, canvasWidth, canvasHeight },
    );
    const startedAt = Date.now();
    try {
      const signal = abortRegistry.takeSignal('g2');
      const result = await addSymbol({
        rooms, pozicijos, currentAssumptions,
        targetPozicijaId: selection.id,
        pointXyPct: [click.x, click.y],
        signal,
      });
      onRecomputed?.(result);
      onGestureEvent?.({
        type: 'G2', target: { kind: 'pozicija', id: selection.id },
        outcome: 'success', duration_ms: Date.now() - startedAt,
      });
    } catch (err) {
      if (err.name === 'AbortError') return true;
      console.error('[G2] add_symbol failed:', err);
      onGestureEvent?.({
        type: 'G2', target: { kind: 'pozicija', id: selection.id },
        outcome: 'error', duration_ms: Date.now() - startedAt,
      });
      alert(err.envelope?.user_message || `G2 nepavyko: ${err.message}`);
    }
    return true;
  }, [tool, selection, scale, translate, canvasWidth, canvasHeight,
      rooms, pozicijos, currentAssumptions, containerRef,
      onRecomputed, onGestureEvent]);
}
