// frontend/src/components/canvas/TakeoffCanvas.jsx
/**
 * Sprint 1: TakeoffCanvas — pdf.js renderer with mip-pyramid + CSS
 * transform during interaction.
 *
 * Renders ONE page at a time at the canonical mip level. During pan/zoom
 * (mouse drag, wheel), CSS transform animates the canvas at 60 fps. After
 * 150 ms of inactivity, re-render at the new scale via OffscreenCanvas.
 *
 * Sprint 2 will add the Konva annotation overlay; Sprint 3 wires
 * bidirectional highlight via viewerStore.
 */
import { useEffect, useRef, useState } from 'react';
import { useStore } from 'zustand';
import { viewerStore } from '../../lib/viewerStore';
import { renderQueue } from '../../lib/renderQueue';
import { tileCache } from '../../lib/tileCache';
import { pickZoomLevel, tileKey, renderPageToImageBitmap } from '../../lib/mipPyramid';

const SETTLE_DEBOUNCE_MS = 150;

export function TakeoffCanvas({ pdfDoc, renderOverlay }) {
  const pageIdx = useStore(viewerStore, (s) => s.currentPage);
  const containerRef = useRef(null);
  const canvasRef = useRef(null);
  const settleTimerRef = useRef(null);
  const dragRef = useRef({ active: false, startX: 0, startY: 0, baseTx: 0, baseTy: 0 });

  const scale = useStore(viewerStore, (s) => s.scale);
  const translate = useStore(viewerStore, (s) => s.translate);
  const setTransform = useStore(viewerStore, (s) => s.setTransform);

  const [renderedLevel, setRenderedLevel] = useState(null);

  // Render the current page at the current mip-zoom level when scale settles.
  useEffect(() => {
    if (!pdfDoc) return;
    if (settleTimerRef.current) clearTimeout(settleTimerRef.current);
    settleTimerRef.current = setTimeout(() => {
      const targetLevel = pickZoomLevel(scale);
      if (targetLevel === renderedLevel) return;

      const key = tileKey(pageIdx, targetLevel);
      const cached = tileCache.get(key);
      if (cached) {
        blit(canvasRef.current, cached);
        setRenderedLevel(targetLevel);
        return;
      }

      renderQueue(async () => {
        const page = await pdfDoc.getPage(pageIdx + 1);
        const bitmap = await renderPageToImageBitmap(page, targetLevel);
        tileCache.set(key, bitmap);
        blit(canvasRef.current, bitmap);
        setRenderedLevel(targetLevel);
      }).catch((err) => {
        console.error('[TakeoffCanvas] render failed:', err);
      });
    }, SETTLE_DEBOUNCE_MS);

    return () => clearTimeout(settleTimerRef.current);
  }, [pdfDoc, pageIdx, scale, renderedLevel]);

  // CSS transform during interaction — GPU-accelerated, no re-render.
  // The canvas was rasterized at `renderedLevel`; if the live scale differs,
  // CSS scales it to compensate.
  const transformStyle = {
    transform: `translate(${translate.x}px, ${translate.y}px) scale(${scale / (renderedLevel || 1)})`,
    transformOrigin: '0 0',
    willChange: 'transform',
    imageRendering: 'auto',
  };

  // Wheel zoom: relative to pointer
  const onWheel = (e) => {
    e.preventDefault();
    const rect = containerRef.current.getBoundingClientRect();
    const px = e.clientX - rect.left;
    const py = e.clientY - rect.top;
    const factor = e.deltaY < 0 ? 1.1 : 1 / 1.1;
    const newScale = Math.max(0.25, Math.min(scale * factor, 6));
    const newTranslate = {
      x: px - (px - translate.x) * (newScale / scale),
      y: py - (py - translate.y) * (newScale / scale),
    };
    setTransform({ scale: newScale, translate: newTranslate });
  };

  const onPointerDown = (e) => {
    if (e.button !== 0) return;
    dragRef.current = {
      active: true,
      startX: e.clientX, startY: e.clientY,
      baseTx: translate.x, baseTy: translate.y,
    };
    e.currentTarget.setPointerCapture(e.pointerId);
  };

  const onPointerMove = (e) => {
    if (!dragRef.current.active) return;
    const dx = e.clientX - dragRef.current.startX;
    const dy = e.clientY - dragRef.current.startY;
    setTransform({
      scale,
      translate: { x: dragRef.current.baseTx + dx, y: dragRef.current.baseTy + dy },
    });
  };

  const onPointerUp = (e) => {
    dragRef.current.active = false;
    try { e.currentTarget.releasePointerCapture(e.pointerId); } catch { /* ignore */ }
  };

  return (
    <div
      ref={containerRef}
      onWheel={onWheel}
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={onPointerUp}
      style={{
        overflow: 'hidden',
        width: '100%',
        height: '100%',
        position: 'relative',
        cursor: 'grab',
        touchAction: 'none',
      }}
    >
      <canvas ref={canvasRef} style={transformStyle} />
      {renderOverlay?.({
        canvasWidth: canvasRef.current?.width ?? 0,
        canvasHeight: canvasRef.current?.height ?? 0,
        canvasRef,
        containerRef,
      })}
    </div>
  );
}

function blit(targetCanvas, bitmap) {
  if (!targetCanvas || !bitmap) return;
  targetCanvas.width = bitmap.width;
  targetCanvas.height = bitmap.height;
  const ctx = targetCanvas.getContext('2d');
  ctx.drawImage(bitmap, 0, 0);
}
