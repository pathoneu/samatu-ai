// frontend/src/components/canvas/gestures/G1VisionFill.jsx
/**
 * Sprint 2 G1 — click-to-fill via Vision.
 *
 * When viewerStore.currentTool === 'g1', a click on the canvas:
 *   1. converts canvas-px to pdf-pct
 *   2. shows an "AI..." spinner near the click
 *   3. POSTs to /api/vision-fill (cancellable)
 *   4. on success, parent appends the returned polygon to committedPolygons
 *      and pushes a session-telemetry gesture event
 *
 * Spec §5.4 G1 row.
 */
import { useState, useCallback } from 'react';
import { useStore } from 'zustand';
import { viewerStore } from '../../../lib/viewerStore';
import { canvasPxToPdfPct } from '../../../lib/coordTransform';
import { visionFill } from '../../../lib/gestureApi';
import { abortRegistry } from '../../../lib/abortRegistry';

export function G1VisionFill({ projectId, pageIdx, canvasWidth, canvasHeight,
                              containerRef, onPolygonAdded, onGestureEvent }) {
  const tool = useStore(viewerStore, (s) => s.currentTool);
  const scale = useStore(viewerStore, (s) => s.scale);
  const translate = useStore(viewerStore, (s) => s.translate);
  const [pending, setPending] = useState(null);  // { x, y } where x/y are screen px

  const onCanvasClick = useCallback(async (e) => {
    if (tool !== 'g1') return;
    const rect = containerRef.current?.getBoundingClientRect();
    if (!rect) return;
    const px = e.clientX - rect.left;
    const py = e.clientY - rect.top;
    const click = canvasPxToPdfPct({ px, py },
      { scale, translate, canvasWidth, canvasHeight });
    if (click.x < 0 || click.x > 1 || click.y < 0 || click.y > 1) return;

    const startedAt = Date.now();
    setPending({ x: px, y: py });
    try {
      const signal = abortRegistry.takeSignal('g1');
      const result = await visionFill({
        projectId, pageIdx, clickXyPct: [click.x, click.y], signal,
      });
      onPolygonAdded?.({
        id: `g1-${startedAt}`,
        points: result.polygon_pct,
        confidence: result.confidence,
        roomNameGuess: result.room_name_guess,
      });
      onGestureEvent?.({
        type: 'G1', target: { kind: 'click', id: `g1-${startedAt}` },
        outcome: 'success', duration_ms: Date.now() - startedAt,
      });
    } catch (err) {
      if (err.name === 'AbortError') {
        onGestureEvent?.({
          type: 'G1', target: { kind: 'click' },
          outcome: 'cancelled', duration_ms: Date.now() - startedAt,
        });
        return;
      }
      console.error('[G1] vision-fill failed:', err);
      onGestureEvent?.({
        type: 'G1', target: { kind: 'click' },
        outcome: 'error', duration_ms: Date.now() - startedAt,
      });
      alert(err.envelope?.user_message || `G1 nepavyko: ${err.message}`);
    } finally {
      setPending(null);
    }
  }, [tool, scale, translate, canvasWidth, canvasHeight, projectId, pageIdx,
      containerRef, onPolygonAdded, onGestureEvent]);

  // Caller mounts this component as a sibling of canvas; wires onCanvasClick
  // through onClick prop on the canvas container. Spinner overlays the click.
  return (
    <>
      {pending && (
        <div style={{
          position: 'absolute', left: pending.x - 10, top: pending.y - 10,
          width: 20, height: 20, borderRadius: '50%',
          border: '2px solid #facc15', borderTopColor: 'transparent',
          animation: 'spin 0.7s linear infinite', pointerEvents: 'none',
          zIndex: 5,
        }} />
      )}
      <span data-g1-handler onClick={onCanvasClick} style={{ display: 'none' }} />
    </>
  );
}

// Caller exposes the handler via a ref-pattern: in InteriorProjectV2 we
// instantiate G1VisionFill and grab its onCanvasClick from a forwardRef.
// Simpler: export the handler directly.
export function useG1Handler({ projectId, pageIdx, canvasWidth, canvasHeight,
                               containerRef, onPolygonAdded, onGestureEvent }) {
  const tool = useStore(viewerStore, (s) => s.currentTool);
  const scale = useStore(viewerStore, (s) => s.scale);
  const translate = useStore(viewerStore, (s) => s.translate);

  return useCallback(async (e) => {
    if (tool !== 'g1') return false;
    const rect = containerRef.current?.getBoundingClientRect();
    if (!rect) return false;
    const px = e.clientX - rect.left;
    const py = e.clientY - rect.top;
    const click = canvasPxToPdfPct({ px, py },
      { scale, translate, canvasWidth, canvasHeight });
    if (click.x < 0 || click.x > 1 || click.y < 0 || click.y > 1) return false;

    const startedAt = Date.now();
    try {
      const signal = abortRegistry.takeSignal('g1');
      const result = await visionFill({
        projectId, pageIdx, clickXyPct: [click.x, click.y], signal,
      });
      onPolygonAdded?.({
        id: `g1-${startedAt}`, points: result.polygon_pct,
        confidence: result.confidence,
        roomNameGuess: result.room_name_guess,
      });
      onGestureEvent?.({
        type: 'G1', target: { kind: 'click', id: `g1-${startedAt}` },
        outcome: 'success', duration_ms: Date.now() - startedAt,
      });
    } catch (err) {
      if (err.name === 'AbortError') return true;
      console.error('[G1] vision-fill failed:', err);
      onGestureEvent?.({
        type: 'G1', target: { kind: 'click' },
        outcome: 'error', duration_ms: Date.now() - startedAt,
      });
      alert(err.envelope?.user_message || `G1 nepavyko: ${err.message}`);
    }
    return true;
  }, [tool, scale, translate, canvasWidth, canvasHeight, projectId, pageIdx,
      containerRef, onPolygonAdded, onGestureEvent]);
}
