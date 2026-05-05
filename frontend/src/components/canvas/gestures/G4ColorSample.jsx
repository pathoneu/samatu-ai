// frontend/src/components/canvas/gestures/G4ColorSample.jsx
/**
 * Sprint 2 G4 — eyedropper sample colored zone.
 *
 * Reads the pixel color under the click via canvas getImageData(),
 * bails on whitish (background), and POSTs a color_zone edit. The
 * polygons[] sent in Sprint 2 is just the click point as a degenerate
 * triangle — backend zone-matching is Sprint 4 work. Selection target
 * room is currently the selected room (or fails with hint).
 *
 * Spec §5.4 G4 row.
 */
import { useCallback } from 'react';
import { useStore } from 'zustand';
import { viewerStore } from '../../../lib/viewerStore';
import { canvasPxToPdfPct } from '../../../lib/coordTransform';
import { rgbAt, isWhitish } from '../../../lib/gestures/g4-color-sample';
import { colorZone } from '../../../lib/gestureApi';
import { abortRegistry } from '../../../lib/abortRegistry';

const SAMPLE_RADIUS_PCT = 0.005;

export function useG4Handler({ rooms, pozicijos, currentAssumptions,
                               canvasRef, canvasWidth, canvasHeight,
                               containerRef, onRecomputed, onGestureEvent }) {
  const tool = useStore(viewerStore, (s) => s.currentTool);
  const scale = useStore(viewerStore, (s) => s.scale);
  const translate = useStore(viewerStore, (s) => s.translate);
  const selection = useStore(viewerStore, (s) => s.selection);

  return useCallback(async (e) => {
    if (tool !== 'g4') return false;
    if (selection?.kind !== 'room') {
      alert('Pasirink kambarį KŽ panelėje, tada spausk spalvotą zoną.');
      return true;
    }
    const rect = containerRef.current?.getBoundingClientRect();
    if (!rect || !canvasRef.current) return true;

    const screenPx = { px: e.clientX - rect.left, py: e.clientY - rect.top };
    const click = canvasPxToPdfPct(screenPx,
      { scale, translate, canvasWidth, canvasHeight });

    const ctx = canvasRef.current.getContext('2d');
    const cx = Math.round(click.x * canvasRef.current.width);
    const cy = Math.round(click.y * canvasRef.current.height);
    const rgb = rgbAt(ctx, cx, cy);
    if (isWhitish(rgb)) {
      alert('Spalva neaiški (per balta) — bandyk lasso (G5).');
      return true;
    }

    const r = SAMPLE_RADIUS_PCT;
    const polygonsPct = [[
      [click.x - r, click.y - r], [click.x + r, click.y - r],
      [click.x + r, click.y + r], [click.x - r, click.y + r],
    ]];

    const startedAt = Date.now();
    try {
      const signal = abortRegistry.takeSignal('g4');
      const result = await colorZone({
        rooms, pozicijos, currentAssumptions,
        targetRoomId: selection.id, colorRgb: rgb,
        polygonsPct, signal,
      });
      onRecomputed?.(result);
      onGestureEvent?.({
        type: 'G4', target: { kind: 'room', id: selection.id },
        outcome: 'success', duration_ms: Date.now() - startedAt,
      });
    } catch (err) {
      if (err.name === 'AbortError') return true;
      console.error('[G4] color_zone failed:', err);
      onGestureEvent?.({
        type: 'G4', target: { kind: 'room', id: selection.id },
        outcome: 'error', duration_ms: Date.now() - startedAt,
      });
      alert(err.envelope?.user_message || `G4 nepavyko: ${err.message}`);
    }
    return true;
  }, [tool, selection, scale, translate, canvasWidth, canvasHeight,
      rooms, pozicijos, currentAssumptions, canvasRef, containerRef,
      onRecomputed, onGestureEvent]);
}
