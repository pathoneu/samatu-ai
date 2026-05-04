// frontend/src/components/canvas/gestures/G5Lasso.jsx
/**
 * Sprint 2 G5 — freehand lasso re-extract.
 *
 * Pointer-down → start collecting points (in pdf-pct).
 * Pointer-move → append each point if it's >tolerance from last.
 * Pointer-up   → simplify, close, validate ≥3 vertices, POST to backend.
 *
 * Returns the collected polygon as preview while dragging so
 * AnnotationLayer can render the dotted lasso line.
 *
 * Spec §5.4 G5 row.
 */
import { useCallback, useRef, useState } from 'react';
import { useStore } from 'zustand';
import { viewerStore } from '../../../lib/viewerStore';
import { canvasPxToPdfPct } from '../../../lib/coordTransform';
import {
  simplifyLasso, closeIfNeeded, isMinimalLasso,
} from '../../../lib/gestures/g5-lasso-geometry';
import { lassoRerun } from '../../../lib/gestureApi';
import { abortRegistry } from '../../../lib/abortRegistry';

export function useG5Handlers({ projectId, pageIdx, canvasWidth, canvasHeight,
                                containerRef, onLassoResult, onGestureEvent,
                                onPreviewChange }) {
  const tool = useStore(viewerStore, (s) => s.currentTool);
  const scale = useStore(viewerStore, (s) => s.scale);
  const translate = useStore(viewerStore, (s) => s.translate);
  const pointsRef = useRef([]);
  const [drawing, setDrawing] = useState(false);

  const eventToPct = useCallback((e) => {
    const rect = containerRef.current?.getBoundingClientRect();
    if (!rect) return null;
    const pct = canvasPxToPdfPct(
      { px: e.clientX - rect.left, py: e.clientY - rect.top },
      { scale, translate, canvasWidth, canvasHeight },
    );
    if (pct.x < 0 || pct.x > 1 || pct.y < 0 || pct.y > 1) return null;
    return [pct.x, pct.y];
  }, [scale, translate, canvasWidth, canvasHeight, containerRef]);

  const onPointerDown = useCallback((e) => {
    if (tool !== 'g5') return false;
    const pt = eventToPct(e);
    if (!pt) return false;
    pointsRef.current = [pt];
    setDrawing(true);
    onPreviewChange?.({ type: 'lasso', points: [pt] });
    return true;
  }, [tool, eventToPct, onPreviewChange]);

  const onPointerMove = useCallback((e) => {
    if (!drawing) return false;
    const pt = eventToPct(e);
    if (!pt) return false;
    pointsRef.current.push(pt);
    onPreviewChange?.({ type: 'lasso', points: [...pointsRef.current] });
    return true;
  }, [drawing, eventToPct, onPreviewChange]);

  const onPointerUp = useCallback(async (_e) => {
    if (!drawing) return false;
    setDrawing(false);
    onPreviewChange?.(null);

    const simplified = simplifyLasso(pointsRef.current, 0.005);
    if (!isMinimalLasso(simplified)) {
      onGestureEvent?.({
        type: 'G5', target: { kind: 'lasso' },
        outcome: 'cancelled', duration_ms: 0,
      });
      pointsRef.current = [];
      return true;
    }
    const closed = closeIfNeeded(simplified);
    const startedAt = Date.now();
    try {
      const signal = abortRegistry.takeSignal('g5');
      const result = await lassoRerun({
        projectId, pageIdx, lassoPolygonPct: closed, signal,
      });
      onLassoResult?.(result);
      onGestureEvent?.({
        type: 'G5', target: { kind: 'lasso' },
        outcome: 'success', duration_ms: Date.now() - startedAt,
      });
    } catch (err) {
      if (err.name === 'AbortError') return true;
      console.error('[G5] lasso-rerun failed:', err);
      onGestureEvent?.({
        type: 'G5', target: { kind: 'lasso' },
        outcome: 'error', duration_ms: Date.now() - startedAt,
      });
      alert(err.envelope?.user_message || `G5 nepavyko: ${err.message}`);
    } finally {
      pointsRef.current = [];
    }
    return true;
  }, [drawing, projectId, pageIdx, onLassoResult, onGestureEvent, onPreviewChange]);

  return { onPointerDown, onPointerMove, onPointerUp, isDrawing: drawing };
}
