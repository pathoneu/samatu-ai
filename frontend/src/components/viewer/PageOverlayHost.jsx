/**
 * PageOverlayHost — mounted once per page by TakeoffViewer's renderPage. Lays
 * out base render + hi-res tiling, then our overlays as page-glued siblings.
 * Overlays consume `renderedSize` (== our legacy prop) from the page viewport.
 */
import { useEffect } from 'react';
import { RenderLayer } from '@embedpdf/plugin-render/react';
import { TilingLayer } from '@embedpdf/plugin-tiling/react';
import { PagePointerProvider, usePointerHandlers } from '@embedpdf/plugin-interaction-manager/react';
import { makeViewport } from '@/lib/viewerEngine/pageViewport';
import RoomZoneLayer from '@/components/project/RoomZoneLayer';

function PageClicks({ documentId, pageIndex, onPagePoint }) {
  const { register } = usePointerHandlers({ documentId, pageIndex });
  useEffect(() => register({
    onClick: (pos) => onPagePoint?.({ pageIndex, x: pos.x, y: pos.y }),
  }), [register, pageIndex, onPagePoint]);
  return null;
}

export default function PageOverlayHost({ documentId, layout, rooms, focusedRoomNr, onRoomZoneClick, onPagePoint }) {
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
          rooms={rooms}
          page={layout.pageNumber}
          renderedSize={{ width, height }}
          focusedRoomNr={focusedRoomNr}
          onRoomClick={(zone) => onRoomZoneClick?.({ nr: zone.nr, puslapio_nr: layout.pageNumber })}
        />
      </div>
    </PagePointerProvider>
  );
}
