import { useEffect, useRef } from 'react';

/**
 * Sits on top of the PDF.js canvas. Renders ALL overlay items
 * (count markers, suggested polygons) on a single 2D canvas — keeps
 * the DOM lean even when a sheet has 500+ markers.
 *
 * Items live in an OverlayIndex (rbush) upstream so hit-tests +
 * viewport culling are O(log n).
 *
 * Item shapes:
 *   { kind: 'count_marker', x, y, confidence, status? }
 *   { kind: 'polygon', points: [[x, y], ...] }
 *
 * Coords are in canvas (screen) pixels — the parent does the
 * PDF→screen transform before passing items in.
 */
export default function DrawingOverlay({
  items,
  onClick,
  width,
  height,
  enabled = true,
}) {
  const canvasRef = useRef(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    canvas.width = width;
    canvas.height = height;
    const ctx = canvas.getContext('2d');
    ctx.clearRect(0, 0, canvas.width, canvas.height);

    for (const item of items || []) {
      if (item.kind === 'count_marker') {
        const conf = item.confidence ?? 0;
        const status = item.status || 'pending';
        let stroke = '#dc2626';
        if (conf >= 0.9) stroke = '#16a34a';
        else if (conf >= 0.75) stroke = '#eab308';
        if (status === 'reject') stroke = '#94a3b8';
        ctx.lineWidth = 2;
        ctx.strokeStyle = stroke;
        ctx.fillStyle = status === 'accept' ? `${stroke}55` : 'transparent';
        ctx.beginPath();
        ctx.arc(item.x, item.y, 8, 0, 2 * Math.PI);
        if (status === 'accept') ctx.fill();
        ctx.stroke();
      } else if (item.kind === 'polygon') {
        // Bright, thick, dashed outline so the user always sees the
        // suggestion — earlier the faint blue was easy to miss.
        ctx.strokeStyle = '#16a34a';
        ctx.fillStyle = 'rgba(22, 163, 74, 0.18)';
        ctx.lineWidth = 4;
        ctx.setLineDash([10, 6]);
        ctx.beginPath();
        item.points.forEach(([x, y], i) => {
          if (i === 0) ctx.moveTo(x, y);
          else ctx.lineTo(x, y);
        });
        ctx.closePath();
        ctx.fill();
        ctx.stroke();
        ctx.setLineDash([]);
      }
    }
  }, [items, width, height]);

  return (
    <canvas
      ref={canvasRef}
      onClick={(e) => {
        if (!enabled) return;
        const rect = canvasRef.current.getBoundingClientRect();
        onClick?.(e.clientX - rect.left, e.clientY - rect.top);
      }}
      style={{
        position: 'absolute',
        inset: 0,
        pointerEvents: enabled ? 'auto' : 'none',
        cursor: enabled ? 'crosshair' : 'default',
      }}
    />
  );
}
