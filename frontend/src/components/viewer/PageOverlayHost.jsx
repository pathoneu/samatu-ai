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
import MeasureLayer, { hitTest as hitTestMeasurement, MEASURE_HIT_TOL_PX } from './MeasureLayer';
import CheckLayer from './CheckLayer';
import DrawingGeometryLayer from './DrawingGeometryLayer';
import RevisionOverlayLayer from './RevisionOverlayLayer';
import OutlineEditLayer from './OutlineEditLayer';
import SymbolSearchLayer from './SymbolSearchLayer';
import { LegendLayer } from './LegendTool';
import OutlineToolLayer from './OutlineToolLayer';
import CalloutLayer from './CalloutLayer';
import RoomProposalLayer from './RoomProposalLayer';
import SheetZoneLayer from './SheetZoneLayer';
import DrawingNoteLayer from './DrawingNoteLayer';
import { usePageGeometry } from '@/hooks/usePageGeometry';
import { snapPolygonsFromGeometry } from '@/lib/drawingSnap';

function PageClicks({ documentId, pageIndex, pageWidth, pageHeight, pageRotation, onPagePoint, scale = null, renderedWidth = null, renderedHeight = null }) {
  const { register } = usePointerHandlers({ documentId, pageIndex });
  // COORDINATE CONTRACT (verified in @embedpdf/plugin-interaction-manager dist):
  // PagePointerProvider's default convertEventToPoint runs restorePosition(),
  // which un-rotates the display click by the page's effective /Rotate AND
  // divides by the zoom scale. So pos.x/pos.y arrive ALREADY in UNROTATED
  // mediabox PDF POINTS — not display px. pageWidth/pageHeight passed along
  // here must therefore be the mediabox size in POINTS (pageSizePt), so that
  // consumers get pct with a straight divide. pageRotation (/Rotate enum) is
  // included for context only — no rotation math belongs in this path.
  // Pathon v3 W1-D: the click also says whether Shift was held (Shift+click adds a room to the selection), the
  // page's screen pixels per PDF point (`scale`, for hit tolerances) and its size on screen.
  useEffect(() => register({
    onClick: (pos, evt) => onPagePoint?.({
      pageIndex, x: pos.x, y: pos.y, pageWidth, pageHeight, pageRotation,
      shiftKey: !!evt?.shiftKey, scale, renderedWidth, renderedHeight,
      // where on screen (W5-A A9: a pop-up opens beside the click)
      clientX: evt?.clientX ?? null, clientY: evt?.clientY ?? null,
    }),
  }), [register, pageIndex, pageWidth, pageHeight, pageRotation, onPagePoint, scale, renderedWidth, renderedHeight]);
  return null;
}

// Screen anchor for the selected measurement (the selection bar stands above it): centroid for
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
  // Rooms Shift+clicked beside the focused one (Pathon v3 W1-D) — drawn with the same selected style.
  selectedRoomNrs = null,
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
  // „Atimti" in one click (W5-A A4): (pct point) => Promise<hole-at answer>.
  onRequestHole = null,
  onRoomZoneClick,
  onPagePoint,
  // Double-click on the sheet (Pathon v3 W5-A A1): ({measureId?, pageIndex, x, y, …}) — a measurement under it, or
  // the point (unrotated PDF points, like a click) for the room under it.
  onPageDoubleClick = null,
  // The vertex editor's corner selection and pop-up (W5-A A2 / A3).
  onOutlineSelect = null,
  onOutlineMenu = null,
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
  // „Žymėti" box selection (W5-A A5) → TakeoffViewer.handleBoxSelect.
  onMeasureBoxSelect = null,
  // The snap under the pointer (W5-A A6) → the status line.
  onMeasureSnapChange = null,
  // Count tool right-click → the type picker (W5-A A7).
  onCountTypeMenu = null,
  // Plotas / Perimetras: free | rect | arc (W5-A A11).
  drawShape = 'free',
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
  // „Pažymėti legendą" (W2-B): the session from useLegendTool while it is on — it owns the pointer
  legend = null,
  // Sheet links (Togal-v2 W7): { sheets, version } — references on this sheet to other sheets,
  // underlined; `sheets` is the rail's model so the hover names a sheet the way the rail does.
  sheetLinks = null,
  // A later edition of the drawing over this sheet (togal-v2 W10): {rid, record, mode, opacity} or null.
  revisionOverlay = null,
  // The room tool R's state (useRoomTool) while it is armed, else null — its proposal is drawn on its sheet.
  roomTool = null,
  // „Rodyti sritis" (W5-B B2): every zone of the sheet outlined, not only the hovered one.
  zonesShown = false,
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

  // A measurement being edited point by point is drawn by the vertex editor alone (W5-A A1).
  const editingMeasureId = outlineEdit?.target === 'measure' ? outlineEdit.id : null;
  const shownMeasurements = editingMeasureId ? (measurements || []).filter((m) => m.id !== editingMeasureId) : (measurements || []);
  const handleDoubleClick = (onPageDoubleClick && adapter && !checkMode && !editingHere && !toolHere
    && (measureTool == null || measureTool === 'select')) ? (e) => {
      const r = e.currentTarget.getBoundingClientRect();
      const raw = adapter.toPdf({ x: e.clientX - r.left, y: e.clientY - r.top });
      const measureId = hitTestMeasurement(raw, (measurements || []).filter((m) => ['distance', 'perimeter', 'area'].includes(m.kind)), layout.pageNumber, MEASURE_HIT_TOL_PX / (adapter.scale || 1));
      onPageDoubleClick({
        measureId: measureId || null, pageIndex: layout.pageIndex, x: raw.x, y: raw.y, pageWidth: pageWidthPt, pageHeight: pageHeightPt,
        pageRotation, renderedWidth: width, renderedHeight: height,
      });
    } : undefined;

  return (
    <PagePointerProvider documentId={documentId} pageIndex={layout.pageIndex} data-page-number={layout.pageNumber} style={{ position: 'relative', width, height }} onContextMenu={handleContextMenu} onDoubleClick={handleDoubleClick}>
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
        data-drawing-render
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
      <PageClicks documentId={documentId} pageIndex={layout.pageIndex} pageWidth={pageWidthPt} pageHeight={pageHeightPt} pageRotation={pageRotation} onPagePoint={onPagePoint} scale={adapter?.scale ?? null} renderedWidth={width} renderedHeight={height} />
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
      {!checkMode && revisionOverlay && (
        <div style={{ position: 'absolute', inset: 0, pointerEvents: 'none' }}>
          <RevisionOverlayLayer projectId={projectId} page={layout.pageNumber} overlay={revisionOverlay} renderedSize={{ width, height }} pageSizePt={pageSizePt} pageRotation={pageRotation} />
        </div>
      )}
      {/* The sheet's zones (W5-B B2): outlined and named on hover, all of them with „Rodyti sritis"; pointer-transparent. */}
      {!checkMode && projectId && (
        <SheetZoneLayer projectId={projectId} page={layout.pageNumber} renderedSize={{ width, height }} shown={zonesShown} hoverable={!measureActive && !outlineEdit && !outlineTool} />
      )}
      {!checkMode && (
      <div style={{ position: 'absolute', inset: 0, pointerEvents: 'none' }}>
        <RoomZoneLayer
          rooms={displayRooms}
          page={layout.pageNumber}
          renderedSize={{ width, height }}
          focusedRoomNr={focusedRoomNr}
          selectedRoomNrs={selectedRoomNrs}
          hiddenRoomNrs={hiddenRoomNrs}
          hoveredRoomNrExternal={hoveredRoomNrExternal}
          zoneFillsVisible={zoneFillsVisible}
          interactive={!measureActive && !outlineEdit && !outlineTool}
          // Selecting is the page click's job (TakeoffViewer.handlePagePoint hit-tests what this layer draws, so
          // Shift+click can add a room); a zone of its own would re-focus the room after the page did. Without
          // the viewer's selection (`onPagePoint` absent) the zone still focuses its room as before.
          onRoomClick={onPagePoint ? () => {} : (zone) => onRoomZoneClick?.({ nr: zone.nr, puslapio_nr: layout.pageNumber })}
        />
      </div>
      )}
      {/* The room tool's proposal (Pathon v3 W1-D) — over the zones, under the measurements; pointer-transparent. */}
      {!checkMode && roomTool && (
        <div style={{ position: 'absolute', inset: 0, pointerEvents: 'none' }}>
          <RoomProposalLayer page={layout.pageNumber} state={roomTool} renderedSize={{ width, height }} />
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
            measurements={shownMeasurements}
            countTypes={countTypes}
            activeCountTypeId={activeCountTypeId}
            snapEnabled={snapEnabled}
            orthoEnabled={orthoEnabled}
            drawingSnapPolygons={drawingSnapPolygons}
            onCommit={onMeasureCommit}
            onCalibrate={onMeasureCalibrate}
            onSelect={onMeasureSelect}
            onBoxSelect={onMeasureBoxSelect}
            onSnapChange={onMeasureSnapChange}
            onTypeMenu={onCountTypeMenu}
            drawShape={drawShape}
            onDelete={onMeasureDelete}
            selectedIds={selectedMeasureIds}
            draft={measureDraft}
            onDraftAction={onMeasureDraftAction}
            calibA={measureCalibA}
            onCalibAChange={onMeasureCalibAChange}
          />
          {/* Where the selected mark is — the selection bar (v3 W1-B B6) stands right above it with
              Pervadinti · Keisti tipą · Rodyti sąraše · Ištrinti (the old one-icon ✕ lived here). */}
          {deleteAt && (
            <span
              aria-hidden="true"
              data-measure-anchor={selectedMeasurement.id}
              style={{ position: 'absolute', left: deleteAt.x - 12, top: deleteAt.y - 12, width: 24, height: 24, pointerEvents: 'none' }}
            />
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
      {/* „Pažymėti legendą" (W2-B) — the proposals, his box, the found marks; above the measurements, owns the pointer. */}
      {!checkMode && legend && width > 0 && (
        <div style={{ position: 'absolute', inset: 0 }}>
          <LegendLayer page={layout.pageNumber} width={width} height={height} legend={legend} />
        </div>
      )}
      {/* „Pastaba" pins (Pathon v3 W5-C, C11) — always shown; while the pin tool is armed the layer owns the click. */}
      {!checkMode && adapter && (
        <DrawingNoteLayer page={layout.pageNumber} measurements={measurements} adapter={adapter} onCommit={onMeasureCommit} onDelete={onMeasureDelete} />
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
            pageSizePt={pageSizePt}
            pageRotation={pageRotation}
            tableAreaM2={outlineEdit.tableAreaM2 ?? null}
            holes={outlineEdit.holes || []}
            closed={outlineEdit.closed !== false}
            minPoints={outlineEdit.minPoints || 3}
            selected={outlineEdit.selected || []}
            onSelect={onOutlineSelect}
            onMenu={onOutlineMenu}
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
            pageSizePt={pageSizePt}
            pageRotation={pageRotation}
            onRequestHole={onRequestHole ? (p) => onRequestHole({ page: layout.pageNumber, x_pct: p[0], y_pct: p[1] }) : null}
          />
        </div>
      )}
    </PagePointerProvider>
  );
}
