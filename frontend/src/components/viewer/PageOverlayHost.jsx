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
import { rotateRoomGeometry, displayRotationFor } from '@/lib/viewerEngine/pageRotation';
import RoomZoneLayer from '@/components/project/RoomZoneLayer';

function PageClicks({ documentId, pageIndex, pageWidth, pageHeight, pageRotation, onPagePoint }) {
  const { register } = usePointerHandlers({ documentId, pageIndex });
  // pageRotation = the page's REPORTED /Rotate — included so consumers
  // (TakeoffViewer.handlePagePoint) can inverse-map display clicks to mediabox.
  useEffect(() => register({
    onClick: (pos) => onPagePoint?.({ pageIndex, x: pos.x, y: pos.y, pageWidth, pageHeight, pageRotation }),
  }), [register, pageIndex, pageWidth, pageHeight, pageRotation, onPagePoint]);
  return null;
}

export default function PageOverlayHost({ documentId, layout, rooms, pageRotation = 0, focusedRoomNr, hiddenRoomNrs = null, hoveredRoomNrExternal = null, onRoomZoneClick, onPagePoint }) {
  // Correct the extraction-vs-display rotation mismatch: room pct are computed on
  // the UNROTATED (mediabox) raster by the extractor, but EmbedPDF/PDFium DISPLAYS
  // the page with /Rotate applied — and empirically applies the COMPLEMENT of the
  // reported /Rotate. Verified by compositing the real viewer raster with the
  // overlay on the Beržų /Rotate-270 sheet: the page shows as mediabox rotated 90°
  // CW, so room 102 (mediabox 0.30,0.34) sits upper-right (0.66,0.30) and the title
  // block (0.85,0.90) sits bottom-left (0.10,0.85). The mediabox→display map is thus
  // (1-y,x) = the 90° transform for a /Rotate-270 page. So swap 90<->270 — via the
  // shared displayRotationFor helper, which TakeoffViewer's handlePagePoint also
  // uses for the INVERSE (click → mediabox) transform, so the two can't diverge.
  const rot = displayRotationFor(pageRotation);
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
      <PageClicks documentId={documentId} pageIndex={layout.pageIndex} pageWidth={width} pageHeight={height} pageRotation={pageRotation} onPagePoint={onPagePoint} />
      {/* Absolutely-positioned overlay host, page-sized; RoomZoneLayer draws inside */}
      <div style={{ position: 'absolute', inset: 0, pointerEvents: 'none' }}>
        <RoomZoneLayer
          rooms={displayRooms}
          page={layout.pageNumber}
          renderedSize={{ width, height }}
          focusedRoomNr={focusedRoomNr}
          hiddenRoomNrs={hiddenRoomNrs}
          hoveredRoomNrExternal={hoveredRoomNrExternal}
          onRoomClick={(zone) => onRoomZoneClick?.({ nr: zone.nr, puslapio_nr: layout.pageNumber })}
        />
      </div>
    </PagePointerProvider>
  );
}
