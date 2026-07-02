/**
 * PageOverlayHost — mounted once per page by TakeoffViewer's renderPage. Lays
 * out base render + hi-res tiling, then our overlays as page-glued siblings.
 * Overlays consume `renderedSize` (== our legacy prop) from the page viewport.
 */
import { useEffect, useMemo } from 'react';
import { RenderLayer } from '@embedpdf/plugin-render/react';
import { TilingLayer } from '@embedpdf/plugin-tiling/react';
import { PagePointerProvider, usePointerHandlers } from '@embedpdf/plugin-interaction-manager/react';
import { makeViewport } from '@/lib/viewerEngine/pageViewport';
import { rotateRoomGeometry, normalizeRotation } from '@/lib/viewerEngine/pageRotation';
import RoomZoneLayer from '@/components/project/RoomZoneLayer';

function PageClicks({ documentId, pageIndex, onPagePoint }) {
  const { register } = usePointerHandlers({ documentId, pageIndex });
  useEffect(() => register({
    onClick: (pos) => onPagePoint?.({ pageIndex, x: pos.x, y: pos.y }),
  }), [register, pageIndex, onPagePoint]);
  return null;
}

export default function PageOverlayHost({ documentId, layout, rooms, pageRotation = 0, focusedRoomNr, onRoomZoneClick, onPagePoint }) {
  // Correct the extraction-vs-display rotation mismatch: room pct are computed on
  // the unrotated (mediabox) raster; the page displays with /Rotate applied. The
  // mediabox→display mapping is the INVERSE of the reported /Rotate (verified
  // against the eksplikacija-table position on the real Beržų /Rotate-270 sheet:
  // mediabox (0.08,0.90) → display top-left, which is the 90° = inverse-of-270 map).
  const reported = normalizeRotation(pageRotation);
  const rot = reported === 90 ? 270 : reported === 270 ? 90 : reported;
  const displayRooms = useMemo(
    () => (rot === 0 ? rooms : (rooms || []).map((r) => rotateRoomGeometry(r, rot))),
    [rooms, rot],
  );
  const vp = makeViewport(layout);
  if (!vp) return null;
  const { width, height } = vp.renderedSize();
  return (
    <PagePointerProvider documentId={documentId} pageIndex={layout.pageIndex} style={{ position: 'relative', width, height }}>
      <RenderLayer documentId={documentId} pageIndex={layout.pageIndex} />
      <TilingLayer documentId={documentId} pageIndex={layout.pageIndex} />
      <PageClicks documentId={documentId} pageIndex={layout.pageIndex} onPagePoint={onPagePoint} />
      {/* Absolutely-positioned overlay host, page-sized; RoomZoneLayer draws inside */}
      <div style={{ position: 'absolute', inset: 0, pointerEvents: 'none' }}>
        <RoomZoneLayer
          rooms={displayRooms}
          page={layout.pageNumber}
          renderedSize={{ width, height }}
          focusedRoomNr={focusedRoomNr}
          onRoomClick={(zone) => onRoomZoneClick?.({ nr: zone.nr, puslapio_nr: layout.pageNumber })}
        />
      </div>
    </PagePointerProvider>
  );
}
