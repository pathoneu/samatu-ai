/**
 * PageOverlayHost — mounted once per page by TakeoffViewer's renderPage. Lays
 * out base render + hi-res tiling, then our overlays as page-glued siblings.
 * Overlays consume `renderedSize` (== our legacy prop) from the page viewport.
 *
 * Phase 3: hosts the MeasureLayer (distance/area/count/calibrate) after the
 * RoomZoneLayer. The measure layer works in PDF-point space; makeEmbedAdapter
 * is its only coordinate boundary. While a measure tool is armed the room
 * zones go non-interactive so they can't swallow measure clicks.
 */
import { useEffect, useMemo } from 'react';
import { X } from 'lucide-react';
import { RenderLayer } from '@embedpdf/plugin-render/react';
import { TilingLayer } from '@embedpdf/plugin-tiling/react';
import { SearchLayer } from '@embedpdf/plugin-search/react';
import { PagePointerProvider, usePointerHandlers } from '@embedpdf/plugin-interaction-manager/react';
import { makeViewport } from '@/lib/viewerEngine/pageViewport';
import { rotateRoomGeometry, displayRotationFor, normalizeRotation } from '@/lib/viewerEngine/pageRotation';
import { makeEmbedAdapter } from '@/lib/viewerEngine/embedPdfAdapter';
import { uncalibratedScale } from '@/lib/measureGeometry';
import { polygonCentroid } from '@/lib/polygonGeometry';
import RoomZoneLayer from '@/components/project/RoomZoneLayer';
import MeasureLayer from './MeasureLayer';

function PageClicks({ documentId, pageIndex, pageWidth, pageHeight, pageRotation, onPagePoint }) {
  const { register } = usePointerHandlers({ documentId, pageIndex });
  // pageRotation = the page's REPORTED /Rotate — included so consumers
  // (TakeoffViewer.handlePagePoint) can inverse-map display clicks to mediabox.
  useEffect(() => register({
    onClick: (pos) => onPagePoint?.({ pageIndex, x: pos.x, y: pos.y, pageWidth, pageHeight, pageRotation }),
  }), [register, pageIndex, pageWidth, pageHeight, pageRotation, onPagePoint]);
  return null;
}

// Screen anchor for the selected measurement's delete affordance: centroid for
// areas (matches its label), middle vertex for lines, the dot for counts.
function deleteAnchorFor(m, adapter) {
  if (!m?.points?.length) return null;
  const pdfPt = m.kind === 'area'
    ? (polygonCentroid(m.points) || m.points[0])
    : m.points[Math.floor(m.points.length / 2)];
  return adapter.toViewport(pdfPt);
}

export default function PageOverlayHost({
  documentId,
  layout,
  rooms,
  pageRotation = 0,
  pageSizePt = null,
  focusedRoomNr,
  hiddenRoomNrs = null,
  hoveredRoomNrExternal = null,
  onRoomZoneClick,
  onPagePoint,
  // Measurement subsystem (Phase 3) — state lives in TakeoffViewer.
  measureTool = null,
  measurements = [],
  measureScale = null,
  snapEnabled = false,
  orthoEnabled = false,
  countTypes = [],
  activeCountTypeId = null,
  selectedMeasureId = null,
  onMeasureCommit = null,
  onMeasureCalibrate = null,
  onMeasureSelect = null,
  onMeasureDelete = null,
}) {
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
  const { width, height } = vp ? vp.renderedSize() : { width: 0, height: 0 };
  // Screen<->PDF-point boundary for the measure layer. Rebuilt on zoom (rendered
  // size) and rotation changes so overlays track the page exactly.
  const pageWidthPt = pageSizePt?.width;
  const pageHeightPt = pageSizePt?.height;
  const adapter = useMemo(() => {
    if (!width || !height || !pageWidthPt || !pageHeightPt) return null;
    return makeEmbedAdapter({
      renderedWidth: width,
      renderedHeight: height,
      pageWidthPt,
      pageHeightPt,
      reportedRotation: pageRotation,
    });
  }, [width, height, pageWidthPt, pageHeightPt, pageRotation]);
  if (!vp) return null;

  const measureActive = measureTool != null;
  const selectedMeasurement = (selectedMeasureId != null && adapter)
    ? (measurements || []).find((m) => m.id === selectedMeasureId && m.page === layout.pageNumber)
    : null;
  const deleteAt = selectedMeasurement ? deleteAnchorFor(selectedMeasurement, adapter) : null;

  return (
    <PagePointerProvider documentId={documentId} pageIndex={layout.pageIndex} style={{ position: 'relative', width, height }}>
      {/* EmbedPDF's <RenderLayer> draws the UNROTATED mediabox raster (PDFium's
          /Rotate is bypassed by its matrix render path), so /Rotate 90|270 sheets
          come out sideways. Apply the page's true /Rotate as a CSS transform on
          the base <img> (RenderLayer forwards `style`). width/height here are the
          rotation-applied host dims; for a quarter-turn we give the <img> the
          swapped (un-rotated) box so it fills the host after the rotate. The
          tiling layer is already rotation-aware, so it needs no change. */}
      <RenderLayer
        documentId={documentId}
        pageIndex={layout.pageIndex}
        style={(() => {
          const angle = normalizeRotation(pageRotation);
          if (angle === 0) return undefined;
          const swap = angle === 90 || angle === 270;
          return {
            position: 'absolute', left: '50%', top: '50%',
            width: swap ? height : width,
            height: swap ? width : height,
            transform: `translate(-50%, -50%) rotate(${angle}deg)`,
            transformOrigin: 'center center',
          };
        })()}
      />
      <TilingLayer documentId={documentId} pageIndex={layout.pageIndex} />
      {/* Search hit highlights (Task 4.1) — page-glued, pointer-transparent,
          below the room zones so measure/zone interactions are unaffected. */}
      <SearchLayer documentId={documentId} pageIndex={layout.pageIndex} style={{ position: 'absolute', inset: 0 }} />
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
          interactive={!measureActive}
          onRoomClick={(zone) => onRoomZoneClick?.({ nr: zone.nr, puslapio_nr: layout.pageNumber })}
        />
      </div>
      {/* Measure layer — top of the page z-stack. Mounted always so committed
          measurements render; tool='pan' when idle keeps its SVG click-through. */}
      {adapter && (
        <div style={{ position: 'absolute', inset: 0, pointerEvents: measureActive ? 'auto' : 'none' }}>
          <MeasureLayer
            adapter={adapter}
            pageNr={layout.pageNumber}
            tool={measureTool || 'pan'}
            scale={measureScale || uncalibratedScale()}
            measurements={measurements || []}
            countTypes={countTypes}
            activeCountTypeId={activeCountTypeId}
            snapEnabled={snapEnabled}
            orthoEnabled={orthoEnabled}
            onCommit={onMeasureCommit}
            onCalibrate={onMeasureCalibrate}
            onSelect={onMeasureSelect}
            selectedId={selectedMeasureId}
          />
          {deleteAt && onMeasureDelete && (
            <button
              type="button"
              title="Ištrinti matavimą (Delete)"
              aria-label="Ištrinti matavimą"
              onClick={(e) => { e.stopPropagation(); onMeasureDelete(selectedMeasurement.id); }}
              onPointerDown={(e) => e.stopPropagation()}
              style={{ position: 'absolute', left: deleteAt.x + 10, top: deleteAt.y - 26, pointerEvents: 'auto' }}
              className="w-5 h-5 rounded-full bg-[hsl(var(--viewer-chrome))] border border-[hsl(var(--viewer-chrome-border))] shadow-sm flex items-center justify-center text-[hsl(var(--viewer-chrome-foreground))] hover:bg-red-600 hover:text-white hover:border-red-500"
            >
              <X className="w-3 h-3" />
            </button>
          )}
        </div>
      )}
    </PagePointerProvider>
  );
}
