/**
 * TakeoffViewer — our commercial viewer on EmbedPDF/PDFium behind the engine
 * boundary. Drop-in for PlanViewer (same-shape props). Phase 1: renders the PDF
 * with tiling + the AI room-zone overlay, page-glued. Measurement/symbol/fill
 * overlays + full toolbar aesthetics land in Phase 2.
 */
import { useMemo } from 'react';
import { EmbedPDF } from '@embedpdf/core/react';
import { usePdfiumEngine } from '@embedpdf/engines/react';
import { Viewport } from '@embedpdf/plugin-viewport/react';
import { Scroller } from '@embedpdf/plugin-scroll/react';
import { DocumentContent, useActiveDocument } from '@embedpdf/plugin-document-manager/react';
import { useZoom } from '@embedpdf/plugin-zoom/react';
import { ZoomIn, ZoomOut } from 'lucide-react';
import { engineOptions, makeViewerPlugins } from '@/lib/viewerEngine/embedEngine';
import PageOverlayHost from './PageOverlayHost';

function Toolbar({ documentId }) {
  const { state, provides } = useZoom(documentId);
  const pct = typeof state?.currentZoomLevel === 'number' ? Math.round(state.currentZoomLevel * 100) : 100;
  return (
    <div className="h-9 shrink-0 border-b border-[#e6e2da] bg-[#fbfaf7] px-3 flex items-center gap-2 text-[12px] text-[#4a4640]">
      <button className="p-1 rounded hover:bg-[#efece6]" title="Tolinti" onClick={() => provides?.zoomOut()}><ZoomOut className="w-4 h-4" /></button>
      <span className="mono tabular w-12 text-center">{pct}%</span>
      <button className="p-1 rounded hover:bg-[#efece6]" title="Artinti" onClick={() => provides?.zoomIn()}><ZoomIn className="w-4 h-4" /></button>
    </div>
  );
}

function ViewerInner({ rooms, focusedRoom, onRoomZoneClick, onPagePoint }) {
  const { activeDocumentId } = useActiveDocument();
  const focusedRoomNr = focusedRoom?.nr ?? null;
  if (!activeDocumentId) return <div className="p-5 text-sm text-muted-foreground">Kraunamas dokumentas…</div>;
  return (
    <DocumentContent documentId={activeDocumentId}>
      {({ isLoaded }) => (isLoaded ? (
        <div className="flex flex-col h-full">
          <Toolbar documentId={activeDocumentId} />
          <Viewport documentId={activeDocumentId} style={{ flex: 1, background: '#e9e7e2' }}>
            <Scroller
              documentId={activeDocumentId}
              renderPage={(layout) => (
                <PageOverlayHost
                  documentId={activeDocumentId}
                  layout={layout}
                  rooms={rooms}
                  focusedRoomNr={focusedRoomNr}
                  onRoomZoneClick={onRoomZoneClick}
                  onPagePoint={onPagePoint}
                />
              )}
            />
          </Viewport>
        </div>
      ) : <div className="p-5 text-sm text-muted-foreground">Kraunamas dokumentas…</div>)}
    </DocumentContent>
  );
}

export default function TakeoffViewer({ fileUrl, rooms = [], focusedRoom = null, onRoomZoneClick = null, onPagePoint = null }) {
  const { engine, isLoading, error } = usePdfiumEngine(engineOptions());
  const plugins = useMemo(() => (fileUrl ? makeViewerPlugins(fileUrl) : null), [fileUrl]);
  if (error) return <div className="p-5 text-sm text-red-600">Variklio klaida: {String(error.message || error)}</div>;
  if (isLoading || !engine || !plugins) return <div className="p-5 text-sm text-muted-foreground">Kraunamas PDF variklis…</div>;
  return (
    <div className="h-full">
      <EmbedPDF engine={engine} plugins={plugins}>
        <ViewerInner rooms={rooms} focusedRoom={focusedRoom} onRoomZoneClick={onRoomZoneClick} onPagePoint={onPagePoint} />
      </EmbedPDF>
    </div>
  );
}
