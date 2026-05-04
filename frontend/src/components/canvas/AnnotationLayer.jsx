// frontend/src/components/canvas/AnnotationLayer.jsx
/**
 * Sprint 2: Konva 3-layer overlay aligned to TakeoffCanvas's CSS transform.
 *
 *   committedLayer  — listening=false; bulk static polygons, dots, niches
 *                     (perf-critical: ALL non-interactive shapes here)
 *   activeLayer     — the currently selected polygon/dot (drag handles etc.)
 *   previewLayer    — hover highlights, dotted lasso preview, gesture cursors
 *
 * Konva's `listening=false` short-circuits hit-testing on the committed
 * layer so even 200+ shapes stay interactive at 60 fps.
 *
 * Coordinates: shapes are drawn in pdf-pct space; we apply the same
 * scale + translate that the canvas uses, then size everything against
 * canvasWidth × canvasHeight.
 */
import { Stage, Layer, Line, Circle } from 'react-konva';
import { useStore } from 'zustand';
import { viewerStore } from '../../lib/viewerStore';
import { pdfPctPolyToCanvasPxPoly } from '../../lib/coordTransform';

export function AnnotationLayer({
  width, height,
  canvasWidth, canvasHeight,
  committedPolygons = [],   // [{id, points: [[x,y], ...], color, fillAlpha}]
  committedPoints = [],     // [{id, xy: [x,y], color, kind}]
  preview = null,            // optional preview shape: { type: 'lasso', points: [[x,y]...] }
  onShapeClick,              // (kind, id) => void — bubbles to gesture handlers
}) {
  const scale = useStore(viewerStore, (s) => s.scale);
  const translate = useStore(viewerStore, (s) => s.translate);
  const selection = useStore(viewerStore, (s) => s.selection);
  const transform = { scale, translate, canvasWidth, canvasHeight };

  return (
    <Stage width={width} height={height}
           style={{ position: 'absolute', top: 0, left: 0, pointerEvents: 'none' }}>
      <Layer listening={false}>
        {committedPolygons
          .filter((p) => !selection || selection.id !== p.id)
          .map((poly) => (
            <Line
              key={poly.id}
              points={pdfPctPolyToCanvasPxPoly(poly.points, transform).flat()}
              closed
              stroke={poly.color || '#3b82f6'}
              strokeWidth={1.5}
              fill={poly.color || '#3b82f6'}
              opacity={poly.fillAlpha ?? 0.18}
            />
          ))}
        {committedPoints.map((pt) => {
          const [px, py] = pdfPctPolyToCanvasPxPoly([pt.xy], transform)[0];
          return (
            <Circle key={pt.id} x={px} y={py} radius={4}
                    fill={pt.color || '#22c55e'} stroke="#0e1216" strokeWidth={1} />
          );
        })}
      </Layer>

      <Layer>
        {selection && committedPolygons.find((p) => p.id === selection.id) && (
          <Line
            points={pdfPctPolyToCanvasPxPoly(
              committedPolygons.find((p) => p.id === selection.id).points,
              transform,
            ).flat()}
            closed
            stroke="#facc15"
            strokeWidth={2.5}
            fill="#facc15"
            opacity={0.30}
            onClick={() => onShapeClick?.('polygon', selection.id)}
          />
        )}
      </Layer>

      <Layer listening={false}>
        {preview?.type === 'lasso' && preview.points.length >= 2 && (
          <Line
            points={pdfPctPolyToCanvasPxPoly(preview.points, transform).flat()}
            stroke="#facc15"
            strokeWidth={1.5}
            dash={[6, 4]}
          />
        )}
      </Layer>
    </Stage>
  );
}
