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
import { displayRotationFor } from '@/lib/viewerEngine/pageRotation';
import { makeEmbedAdapter } from '@/lib/viewerEngine/embedPdfAdapter';
import { uncalibratedScale } from '@/lib/measureGeometry';
import { polygonCentroid } from '@/lib/polygonGeometry';
import RoomZoneLayer from '@/components/project/RoomZoneLayer';
import MeasureLayer from './MeasureLayer';
import CheckLayer from './CheckLayer';

function PageClicks({ documentId, pageIndex, pageWidth, pageHeight, pageRotation, onPagePoint }) {
  const { register } = usePointerHandlers({ documentId, pageIndex });
  // COORDINATE CONTRACT (verified in @embedpdf/plugin-interaction-manager dist):
  // PagePointerProvider's default convertEventToPoint runs restorePosition(),
  // which un-rotates the display click by the page's effective /Rotate AND
  // divides by the zoom scale. So pos.x/pos.y arrive ALREADY in UNROTATED
  // mediabox PDF POINTS — not display px. pageWidth/pageHeight passed along
  // here must therefore be the mediabox size in POINTS (pageSizePt), so that
  // consumers get pct with a straight divide. pageRotation (/Rotate enum) is
  // included for context only — no rotation math belongs in this path.
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
  // Founder decision 2026-07-11: rooms render as numbered markers by default;
  // polygon fills only when the toolbar zone-fill toggle turns this on.
  zoneFillsVisible = false,
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
  // Draft + first calibration point are owned by TakeoffViewer (this page host
  // unmounts when the page scrolls out of the virtualization buffer).
  measureDraft = null,
  onMeasureDraftAction = null,
  measureCalibA = null,
  onMeasureCalibAChange = null,
  // Check-sheet mode (Patikra v2): what was READ about one room, for this page
  // (lib/checkOverlay). While it is on, the all-rooms zone layer stays out —
  // one room is being checked, nothing may compete with its outline.
  checkMode = false,
  checkData = null,
}) {
  // Room pct are ALREADY display-space: the extractor rasters pages via
  // pdf2image (poppler), which APPLIES /Rotate — verified 2026-07-11 against
  // the legacy react-pdf viewer, which plots the very same pct RAW over a
  // rotation-applied render and aligns perfectly (room 102 centroid 0.31,0.32
  // = the top-left open-plan room on the LANDSCAPE Objektas A sheet). The content
  // wrapper below rotates the base render into that same rotation-applied
  // display, so zones consume the pct unchanged — any per-page rotation of the
  // room geometry here would double-rotate them off their rooms.
  const rot = displayRotationFor(pageRotation);
  const displayRooms = rooms;
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
    <PagePointerProvider documentId={documentId} pageIndex={layout.pageIndex} data-page-number={layout.pageNumber} style={{ position: 'relative', width, height }}>
      {/* ── Rotated page content ─────────────────────────────────────────────
          EmbedPDF draws ALL page content in UNROTATED mediabox space:
          <RenderLayer>'s raster ignores /Rotate (PDFium matrix render path),
          <TilingLayer> absolutely positions tiles at unrotated-page-coords ×
          scale, and <SearchLayer> places hit rects the same way. Upstream,
          EmbedPDF expects renderPage to wrap these in a rotation container
          (its <Rotate> component from plugin-rotate, which we don't ship).
          This div IS that container: sized to the UNROTATED scaled page
          (layout.width/height), centered inside the rotation-applied host
          (layout.rotatedWidth/rotatedHeight) and CSS-rotated by the page's
          true /Rotate.
          INVARIANT: base raster + tiles + search highlights must all live in
          this ONE wrapper. Rotating any of them individually (8f9bb8c rotated
          only the base <img>) leaves the others drawn sideways on top of it —
          that was the "still sideways + zone on the neighbouring sheet" bug:
          the unrotated portrait TILE covered the correctly rotated base.
          Rotation-0 pages get a plain inset:0 wrapper — pixel-identical. */}
      <div
        style={rot === 0
          ? { position: 'absolute', inset: 0 }
          : {
              position: 'absolute',
              left: '50%',
              top: '50%',
              width: layout.width,
              height: layout.height,
              transform: `translate(-50%, -50%) rotate(${rot}deg)`,
              transformOrigin: 'center center',
            }}
      >
        <RenderLayer documentId={documentId} pageIndex={layout.pageIndex} />
        <TilingLayer documentId={documentId} pageIndex={layout.pageIndex} />
        {/* Search hit highlights (Task 4.1) — page-glued, pointer-transparent,
            below the room zones so measure/zone interactions are unaffected. */}
        <SearchLayer documentId={documentId} pageIndex={layout.pageIndex} style={{ position: 'absolute', inset: 0 }} />
      </div>
      <PageClicks documentId={documentId} pageIndex={layout.pageIndex} pageWidth={pageWidthPt} pageHeight={pageHeightPt} pageRotation={pageRotation} onPagePoint={onPagePoint} />
      {/* Absolutely-positioned overlay host, page-sized; RoomZoneLayer draws inside */}
      {checkMode && (
        <div style={{ position: 'absolute', inset: 0, pointerEvents: 'none' }}>
          <CheckLayer data={checkData} renderedSize={{ width, height }} />
        </div>
      )}
      {!checkMode && (
      <div style={{ position: 'absolute', inset: 0, pointerEvents: 'none' }}>
        <RoomZoneLayer
          rooms={displayRooms}
          page={layout.pageNumber}
          renderedSize={{ width, height }}
          focusedRoomNr={focusedRoomNr}
          hiddenRoomNrs={hiddenRoomNrs}
          hoveredRoomNrExternal={hoveredRoomNrExternal}
          zoneFillsVisible={zoneFillsVisible}
          interactive={!measureActive}
          onRoomClick={(zone) => onRoomZoneClick?.({ nr: zone.nr, puslapio_nr: layout.pageNumber })}
        />
      </div>
      )}
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
            onDelete={onMeasureDelete}
            selectedId={selectedMeasureId}
            draft={measureDraft}
            onDraftAction={onMeasureDraftAction}
            calibA={measureCalibA}
            onCalibAChange={onMeasureCalibAChange}
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
