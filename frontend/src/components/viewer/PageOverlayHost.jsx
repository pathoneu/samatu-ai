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
import { displayRotationFor, mediaboxSizeFrom } from '@/lib/viewerEngine/pageRotation';
import { makeEmbedAdapter } from '@/lib/viewerEngine/embedPdfAdapter';
import { uncalibratedScale } from '@/lib/measureGeometry';
import { polygonCentroid } from '@/lib/polygonGeometry';
import RoomZoneLayer from '@/components/project/RoomZoneLayer';
import MeasureLayer, { hitTest as hitTestMeasurement, MEASURE_HIT_TOL_PX } from './MeasureLayer';
import CheckLayer from './CheckLayer';
import DrawingGeometryLayer from './DrawingGeometryLayer';
import OutlineEditLayer from './OutlineEditLayer';
import SymbolSearchLayer from './SymbolSearchLayer';
import OutlineToolLayer from './OutlineToolLayer';
import CalloutLayer from './CalloutLayer';
import { usePageGeometry } from '@/hooks/usePageGeometry';
import { snapPolygonsFromGeometry } from '@/lib/drawingSnap';

function PageClicks({ documentId, pageIndex, pageWidth, pageHeight, pageRotation, onPagePoint }) {
  const { register } = usePointerHandlers({ documentId, pageIndex });
  // COORDINATE CONTRACT (verified in @embedpdf/plugin-interaction-manager dist):
  // PagePointerProvider's default convertEventToPoint runs restorePosition(),
  // which un-rotates the display click by the page's effective /Rotate AND
  // divides by the zoom scale. So pos.x/pos.y arrive in EmbedPDF's own
  // unrotated frame, which is sized by its reported `page.size` (swapped vs the
  // mediabox on /Rotate 90/270 sheets). pageWidth/pageHeight passed along here
  // must therefore be that REPORTED size (pageSizePt, not the mediabox), so that
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
  // The project the drawing belongs to — needed to ask the backend for the sheet's wall geometry.
  projectId = null,
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
  // Walls layer (2026-10-16): the wall solid, every outline and opening the program read on the sheet.
  wallsLayerVisible = false,
  // Outline editing (2026-10-16): {nr, page, points} of the room whose polygon_pct is being edited.
  outlineEdit = null,
  onOutlineEditChange = null,
  onOutlineGestureStart = null,
  // Outline tools (2026-10-16): the active split / merge / subtract state (useOutlineTool) and its setter.
  outlineTool = null,
  onOutlineToolChange = null,
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
  // The selection (one mark, or several from „Laso" — 2026-10-16).
  selectedMeasureIds = [],
  // With „Laso" armed and several marks selected, a right-click beside them opens the menu for all of them.
  selectionMenuOnMiss = false,
  onMeasureCommit = null,
  onMeasureCalibrate = null,
  onMeasureSelect = null,
  onMeasureDelete = null,
  // Right-click on a committed measurement or count mark → ({ id, clientX, clientY }) (2026-10-16).
  onMeasureContextMenu = null,
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
  // „Rasti panašius" (2026-10-16): the useSymbolSearch session from TakeoffViewer, or null.
  symbolSearch = null,
  // Sheet links (Togal-v2 W7): { sheets, version } — references on this sheet to other sheets,
  // underlined; `sheets` is the rail's model so the hover names a sheet the way the rail does.
  sheetLinks = null,
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
  // pageSizePt is EmbedPDF's `page.size` — the DISPLAYED size, swapped on /Rotate 90/270 sheets. The
  // adapter, the snap geometry and the outline layers want the mediabox (lib/viewerEngine/pageRotation
  // mediaboxSizeFrom); PageClicks keeps the reported size — its points come from EmbedPDF's own frame.
  const mediaboxPt = useMemo(() => mediaboxSizeFrom(pageSizePt, pageRotation), [pageSizePt, pageRotation]);
  const pageWidthPt = mediaboxPt?.width;
  const pageHeightPt = mediaboxPt?.height;
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
  // The drawing's wall solid (api/page_geometry) — fetched when a measure tool is armed on this page
  // (and when the walls layer is on). Cached per (project, page) in lib/pageGeometryApi, so the
  // scroll virtualization mounting and unmounting this host costs nothing after the first ask.
  const measureActive = measureTool != null;
  const editingHere = !!outlineEdit && outlineEdit.page === layout.pageNumber;
  const toolHere = !!outlineTool && outlineTool.page === layout.pageNumber;
  const { geometry: pageGeometry } = usePageGeometry(projectId, layout.pageNumber, measureActive || wallsLayerVisible || editingHere || toolHere);
  const drawingSnapPolygons = useMemo(
    () => snapPolygonsFromGeometry(pageGeometry, { pageWidthPt, pageHeightPt, pageRotation }),
    [pageGeometry, pageWidthPt, pageHeightPt, pageRotation],
  );
  if (!vp) return null;

  const selectedMeasurement = (selectedMeasureIds.length === 1 && adapter)
    ? (measurements || []).find((m) => m.id === selectedMeasureIds[0] && m.page === layout.pageNumber)
    : null;
  const deleteAt = selectedMeasurement ? deleteAnchorFor(selectedMeasurement, adapter) : null;
  // Right-click: hit-test the committed marks under the pointer (works with or without a tool armed —
  // the measure SVG is click-through while idle, so the page root listens). A miss leaves the
  // browser's own menu alone.
  const handleContextMenu = (onMeasureContextMenu && adapter && !checkMode) ? (e) => {
    const r = e.currentTarget.getBoundingClientRect();
    const raw = adapter.toPdf({ x: e.clientX - r.left, y: e.clientY - r.top });
    const id = hitTestMeasurement(raw, measurements || [], layout.pageNumber, MEASURE_HIT_TOL_PX / (adapter.scale || 1));
    if (!id && !selectionMenuOnMiss) return;
    e.preventDefault();
    onMeasureContextMenu({ id: id || null, clientX: e.clientX, clientY: e.clientY });
  } : undefined;

  return (
    <PagePointerProvider documentId={documentId} pageIndex={layout.pageIndex} data-page-number={layout.pageNumber} style={{ position: 'relative', width, height }} onContextMenu={handleContextMenu}>
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
      <PageClicks documentId={documentId} pageIndex={layout.pageIndex} pageWidth={pageSizePt?.width} pageHeight={pageSizePt?.height} pageRotation={pageRotation} onPagePoint={onPagePoint} />
      {/* Absolutely-positioned overlay host, page-sized; RoomZoneLayer draws inside */}
      {checkMode && (
        <div style={{ position: 'absolute', inset: 0, pointerEvents: 'none' }}>
          <CheckLayer data={checkData} renderedSize={{ width, height }} />
        </div>
      )}
      {/* Walls layer (2026-10-16): the wall solid, every outline and opening the program read on this
          sheet — below the room zones so markers and rings stay on top; pointer-transparent. */}
      {!checkMode && wallsLayerVisible && (
        <div style={{ position: 'absolute', inset: 0, pointerEvents: 'none' }}>
          <DrawingGeometryLayer geometry={pageGeometry} rooms={displayRooms} page={layout.pageNumber} renderedSize={{ width, height }} />
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
          interactive={!measureActive && !outlineEdit && !outlineTool}
          onRoomClick={(zone) => onRoomZoneClick?.({ nr: zone.nr, puslapio_nr: layout.pageNumber })}
        />
      </div>
      )}
      {!checkMode && sheetLinks && projectId && (
        <CalloutLayer
          documentId={documentId}
          projectId={projectId}
          page={layout.pageNumber}
          version={sheetLinks.version}
          renderedSize={{ width, height }}
          sheets={sheetLinks.sheets}
          interactive={!measureActive && !outlineEdit}
        />
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
            drawingSnapPolygons={drawingSnapPolygons}
            onCommit={onMeasureCommit}
            onCalibrate={onMeasureCalibrate}
            onSelect={onMeasureSelect}
            onDelete={onMeasureDelete}
            selectedIds={selectedMeasureIds}
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
      {/* „Rasti panašius" (2026-10-16) — above the measurements while the search is open; it owns the pointer. */}
      {adapter && symbolSearch?.active && (
        <div style={{ position: 'absolute', inset: 0 }}>
          <SymbolSearchLayer
            adapter={adapter}
            pageNr={layout.pageNumber}
            canDraw={symbolSearch.phase !== 'searching'}
            candidates={symbolSearch.visible.filter((c) => c.page === layout.pageNumber)}
            numbers={symbolSearch.numbers}
            templateBox={symbolSearch.template?.page === layout.pageNumber ? symbolSearch.template.box : null}
            hoveredId={symbolSearch.hoveredId}
            onBox={symbolSearch.runBox}
            onRemove={symbolSearch.remove}
            onHover={symbolSearch.setHoveredId}
          />
        </div>
      )}
      {/* Outline editor (2026-10-16) — topmost on the page being edited; it owns the pointer. */}
      {editingHere && (
        <div style={{ position: 'absolute', inset: 0 }}>
          <OutlineEditLayer
            points={outlineEdit.points}
            onChange={(pts) => onOutlineEditChange?.(pts)}
            onGestureStart={onOutlineGestureStart}
            geometry={pageGeometry}
            renderedSize={{ width, height }}
            scale={measureScale}
            pageSizePt={mediaboxPt}
            pageRotation={pageRotation}
            tableAreaM2={outlineEdit.tableAreaM2 ?? null}
            holes={outlineEdit.holes || []}
          />
        </div>
      )}
      {/* Outline tools (2026-10-16) — topmost on the page holding the focused outline; they own the pointer. */}
      {toolHere && (
        <div style={{ position: 'absolute', inset: 0 }}>
          <OutlineToolLayer
            tool={outlineTool}
            onChange={(update, opts) => onOutlineToolChange?.(update, opts)}
            rooms={displayRooms}
            geometry={pageGeometry}
            renderedSize={{ width, height }}
            scale={measureScale}
            pageSizePt={mediaboxPt}
            pageRotation={pageRotation}
          />
        </div>
      )}
    </PagePointerProvider>
  );
}
