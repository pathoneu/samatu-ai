/**
 * TakeoffViewer — our commercial viewer on EmbedPDF/PDFium behind the engine
 * boundary. Drop-in for PlanViewer (same-shape props).
 *
 * Phase 1: EmbedPDF core + tiling + AI room-zone overlay, page-glued.
 * Phase 2a: real toolbar (page nav + fit + zoom), focus→scroll-to-page,
 *           zoom-to-cursor (pinch / ctrl+wheel). Line-icon aesthetic, no emoji.
 * Deferred (Phase 3): measurement/symbol/click-to-fill re-home, thumbnail rail,
 *           layer toggles, then flip to default + delete PlanViewer.
 */
import { useEffect, useMemo, useState } from 'react';
import { EmbedPDF } from '@embedpdf/core/react';
import { usePdfiumEngine } from '@embedpdf/engines/react';
import { Viewport } from '@embedpdf/plugin-viewport/react';
import { Scroller, useScroll } from '@embedpdf/plugin-scroll/react';
import { DocumentContent, useActiveDocument } from '@embedpdf/plugin-document-manager/react';
import { useZoom, ZoomMode, ZoomGestureWrapper } from '@embedpdf/plugin-zoom/react';
import { ZoomIn, ZoomOut, ChevronLeft, ChevronRight, MoveHorizontal, Maximize2, SquarePen, X } from 'lucide-react';
import { engineOptions, makeViewerPlugins } from '@/lib/viewerEngine/embedEngine';
import { clickToFill } from '@/lib/clickToFillApi';
import PageOverlayHost from './PageOverlayHost';

function Toolbar({ documentId, totalPages, focusedRoomNr, fillFor, onStartFill, onCancelFill }) {
  const { state: zoom, provides: zoomApi } = useZoom(documentId);
  const { state: scroll, provides: scrollApi } = useScroll(documentId);
  const pct = typeof zoom?.currentZoomLevel === 'number' ? Math.round(zoom.currentZoomLevel * 100) : 100;
  const cur = scroll?.currentPage ?? 1;
  // scroll.totalPages is a scroll metric, not the page count — use the document's pageCount.
  const total = totalPages || 1;
  const btn = 'p-1 rounded hover:bg-[#efece6] disabled:opacity-40 disabled:hover:bg-transparent';
  const canFill = focusedRoomNr != null && onStartFill;
  return (
    <div className="h-9 shrink-0 border-b border-[#e6e2da] bg-[#fbfaf7] px-3 flex items-center gap-1 text-[12px] text-[#4a4640]">
      <button className={btn} title="Ankstesnis puslapis" disabled={cur <= 1} onClick={() => scrollApi?.scrollToPreviousPage()}><ChevronLeft className="w-4 h-4" /></button>
      <span className="mono tabular px-1 whitespace-nowrap">psl. {cur} / {total}</span>
      <button className={btn} title="Kitas puslapis" disabled={cur >= total} onClick={() => scrollApi?.scrollToNextPage()}><ChevronRight className="w-4 h-4" /></button>
      <span className="w-px h-4 bg-[#e0dcd3] mx-1.5" />
      <button className={btn} title="Tolinti" onClick={() => zoomApi?.zoomOut()}><ZoomOut className="w-4 h-4" /></button>
      <span className="mono tabular w-11 text-center">{pct}%</span>
      <button className={btn} title="Artinti" onClick={() => zoomApi?.zoomIn()}><ZoomIn className="w-4 h-4" /></button>
      <span className="w-px h-4 bg-[#e0dcd3] mx-1.5" />
      <button className={btn} title="Pritaikyti plotį" onClick={() => zoomApi?.requestZoom(ZoomMode.FitWidth)}><MoveHorizontal className="w-4 h-4" /></button>
      <button className={btn} title="Visas puslapis" onClick={() => zoomApi?.requestZoom(ZoomMode.FitPage)}><Maximize2 className="w-4 h-4" /></button>
      {canFill && (
        <>
          <span className="w-px h-4 bg-[#e0dcd3] mx-1.5" />
          {fillFor == null ? (
            <button
              className="inline-flex items-center gap-1 px-2 py-1 rounded border border-[#e6e2da] hover:bg-[#efece6] text-[#4a4640]"
              title={`Taisyti patalpos ${focusedRoomNr} zoną`}
              onClick={() => onStartFill(focusedRoomNr)}
            >
              <SquarePen className="w-3.5 h-3.5" />
              <span>Taisyti zoną</span>
            </button>
          ) : (
            <span className="inline-flex items-center gap-1.5 px-2 py-1 rounded bg-[#eef4fb] border border-[#cfe0f2] text-[#2a6fb5]">
              <span>Spustelėkite patalpos {fillFor} viduje</span>
              <button
                className="p-0.5 rounded hover:bg-[#dceafa]"
                title="Atšaukti"
                onClick={onCancelFill}
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </span>
          )}
        </>
      )}
    </div>
  );
}

// Scroll the viewport to a focused room's page when it changes (panel → canvas nav).
function FocusScroller({ documentId, focusedRoom }) {
  const { provides: scrollApi } = useScroll(documentId);
  const targetPage = focusedRoom?.puslapio_nr ?? focusedRoom?.page_nr ?? null;
  useEffect(() => {
    if (targetPage && scrollApi?.scrollToPage) {
      scrollApi.scrollToPage({ pageNumber: targetPage, behavior: 'smooth' });
    }
  }, [targetPage, scrollApi]);
  return null;
}

function ViewerInner({ rooms, focusedRoom, hiddenRoomNrs, hoveredRoomNrExternal, onRoomZoneClick, onPagePoint, projectId, pdfBlob, onRoomPolygonFill }) {
  const { activeDocumentId } = useActiveDocument();
  const focusedRoomNr = focusedRoom?.nr ?? null;
  // `fillFor` = the room nr currently armed for "Taisyti zoną" click-to-fill.
  const [fillFor, setFillFor] = useState(null);
  // Drop the armed room if focus changes away (avoid filling the wrong room).
  useEffect(() => { setFillFor(null); }, [focusedRoomNr]);

  const handlePagePoint = async (pt) => {
    // Not in fill mode → normal viewing: forward to any external consumer.
    if (fillFor == null) {
      onPagePoint?.(pt);
      return;
    }
    const { x, y, pageIndex, pageWidth, pageHeight } = pt;
    if (!pageWidth || !pageHeight) { setFillFor(null); return; }
    try {
      const data = await clickToFill({
        projectId,
        pageNr: pageIndex + 1,
        clickXPct: x / pageWidth,
        clickYPct: y / pageHeight,
        sensitivity: 0.7,
        pdfBlob,
      });
      onRoomPolygonFill?.(fillFor, data);
    } catch (e) {
      console.warn('[click-to-fill] failed:', e?.message);
    } finally {
      setFillFor(null);
    }
  };

  if (!activeDocumentId) return <div className="p-5 text-sm text-muted-foreground">Kraunamas dokumentas…</div>;
  return (
    <DocumentContent documentId={activeDocumentId}>
      {({ isLoaded, documentState }) => (isLoaded ? (
        <div className="flex flex-col h-full">
          <Toolbar
            documentId={activeDocumentId}
            totalPages={documentState?.document?.pageCount ?? documentState?.pageCount ?? documentState?.pages?.length ?? null}
            focusedRoomNr={onRoomPolygonFill ? focusedRoomNr : null}
            fillFor={fillFor}
            onStartFill={setFillFor}
            onCancelFill={() => setFillFor(null)}
          />
          <FocusScroller documentId={activeDocumentId} focusedRoom={focusedRoom} />
          <ZoomGestureWrapper documentId={activeDocumentId} style={{ flex: 1, minHeight: 0 }}>
            <Viewport documentId={activeDocumentId} style={{ height: '100%', background: '#e9e7e2' }}>
              <Scroller
                documentId={activeDocumentId}
                renderPage={(layout) => (
                  <PageOverlayHost
                    documentId={activeDocumentId}
                    layout={layout}
                    rooms={rooms}
                    pageRotation={documentState?.document?.pages?.[layout.pageIndex]?.rotation ?? 0}
                    focusedRoomNr={focusedRoomNr}
                    hiddenRoomNrs={hiddenRoomNrs}
                    hoveredRoomNrExternal={hoveredRoomNrExternal}
                    onRoomZoneClick={onRoomZoneClick}
                    onPagePoint={handlePagePoint}
                  />
                )}
              />
            </Viewport>
          </ZoomGestureWrapper>
        </div>
      ) : <div className="p-5 text-sm text-muted-foreground">Kraunamas dokumentas…</div>)}
    </DocumentContent>
  );
}

export default function TakeoffViewer({
  fileUrl,
  rooms = [],
  focusedRoom = null,
  hiddenRoomNrs = null,
  hoveredRoomNrExternal = null,
  onRoomZoneClick = null,
  onPagePoint = null,
  projectId = null,
  pdfBlob = null,
  onRoomPolygonFill = null,
}) {
  const { engine, isLoading, error } = usePdfiumEngine(engineOptions());
  const plugins = useMemo(() => (fileUrl ? makeViewerPlugins(fileUrl) : null), [fileUrl]);
  if (error) return <div className="p-5 text-sm text-red-600">Variklio klaida: {String(error.message || error)}</div>;
  if (isLoading || !engine || !plugins) return <div className="p-5 text-sm text-muted-foreground">Kraunamas PDF variklis…</div>;
  return (
    <div className="h-full">
      <EmbedPDF engine={engine} plugins={plugins}>
        <ViewerInner
          rooms={rooms}
          focusedRoom={focusedRoom}
          hiddenRoomNrs={hiddenRoomNrs}
          hoveredRoomNrExternal={hoveredRoomNrExternal}
          onRoomZoneClick={onRoomZoneClick}
          onPagePoint={onPagePoint}
          projectId={projectId}
          pdfBlob={pdfBlob}
          onRoomPolygonFill={onRoomPolygonFill}
        />
      </EmbedPDF>
    </div>
  );
}
