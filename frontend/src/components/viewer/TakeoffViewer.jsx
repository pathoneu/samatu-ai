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
import { useCallback, useEffect, useMemo, useReducer, useRef, useState } from 'react';
import { createPortal } from 'react-dom';
import { toast } from 'sonner';
import { useNavigate } from 'react-router';
import { EmbedPDF } from '@embedpdf/core/react';
import { usePdfiumEngine } from '@embedpdf/engines/react';
import { Viewport } from '@embedpdf/plugin-viewport/react';
import { Scroller, useScroll } from '@embedpdf/plugin-scroll/react';
import { DocumentContent, useActiveDocument } from '@embedpdf/plugin-document-manager/react';
import { useZoom, ZoomMode, ZoomGestureWrapper } from '@embedpdf/plugin-zoom/react';
import { ThumbnailsPane, ThumbImg } from '@embedpdf/plugin-thumbnail/react';
import { useSearch } from '@embedpdf/plugin-search/react';
import { usePrint } from '@embedpdf/plugin-print/react';
import { ChevronUp, ChevronDown, PanelLeft, Search, Printer, Download, History, ListChecks, Keyboard } from 'lucide-react';
import { engineOptions, makeViewerPlugins } from '@/lib/viewerEngine/embedEngine';
import { ROOM_POLYGON_FILLS_DEFAULT_VISIBLE, roomPageOf, roomTypeWord } from '@/lib/roomZones';
import { displayRotationFor, normalizeRotation, rotatePctPoint } from '@/lib/viewerEngine/pageRotation';
import { clickToFill } from '@/lib/clickToFillApi';
import { fetchHoleAt } from '@/lib/roomOutlineApi';
import { fetchPageGeometry } from '@/lib/pageGeometryApi';
import { makeCountType, makeMeasurement, countTypesFromMeasurements, measurementValue, newMeasurementId } from '@/lib/measurements';
import { draftReducer } from '@/lib/measureOverlayReducer';
import { uncalibratedScale, draftCommitPoints } from '@/lib/measureGeometry';
import { autoPageScalesFromRooms, confirmLaneScales } from '@/lib/durableScale';
import { mergePageScales } from '@/lib/pageScales';
import { dimensionStringsOf } from '@/lib/scaleOverview';
import { scaleCheckReadout } from '@/lib/scaleCheck';
import { visiblePageOf } from '@/lib/visiblePage';
import { scaleStatusText, scaleStatusTitle } from '@/lib/scaleLabel';
import { centreDelta } from '@/lib/checkOverlay';
import { SNAP_KIND_TEXT } from '@/lib/drawingSnap';
import { selfIntersects } from '@/lib/polygonGeometry';
import { usePageGeometry } from '@/hooks/usePageGeometry';
import { roomAtPoint, nextRoomSelection } from '@/lib/roomHitTest';
import { displayPointOf } from '@/lib/roomOutline';
import PageOverlayHost from './PageOverlayHost';
import { hitTest as hitTestMeasurement, MEASURE_HIT_TOL_PX } from './MeasureLayer';
import CalibrateDialog from './CalibrateDialog';
import { ScaleOverviewDock, ScaleGateChip } from './ScaleOverviewPanel';
import ScaleCheckCard from './ScaleCheckCard';
import ScaleChip from './ScaleChip';
import CountLegendPanel from './CountLegendPanel';
import ShortcutsGuide from './ShortcutsGuide';
import HistoryPanel from './HistoryPanel';
import ViewerCoachMarks from './ViewerCoachMarks';
import MeasureContextMenu, { RenameDialog } from './MeasureContextMenu';
import OutlineToolPanel from './OutlineToolPanel';
import OverlayLegend from './OverlayLegend';
import ToolRail, { RAIL_WIDTH, railHeight } from './ToolRail';
import SheetHeaderBadge from './SheetHeaderBadge';
import ZoomCluster from './ZoomCluster';
import ViewSettingsPopover, { CleanBgFilter, ViewCrosshair } from './ViewSettingsPopover';
import { browserStorage } from '@/lib/browserStorage';
import { readViewSettings, viewCss, writeViewSettings } from '@/lib/viewSettings';
import { cachedSheetZones, noRoomZoneAt } from '@/lib/sheetZonesApi';
import { scaleGateFromScale } from '@/lib/scaleGate';
import { pageScaleIn } from '@/lib/pageScales';
import { focusFrameForRoom } from '@/lib/focusFrame';
import { isNotNeeded, notNeededEntry, scaleForRatio } from '@/lib/scaleEntry';
import ModePill from './ModePill';
import SelectionBar from './SelectionBar';
import useChromeRects from './useChromeRects';
import { pickSpot } from '@/lib/selectionPlacement';
import CursorHint from './CursorHint';
import { cursorHintFor, flashCursorHint } from '@/lib/cursorHints';
import { escStep, openLayerInDocument } from '@/lib/escOrder';
import { frameForRoom, frameForMeasurements } from '@/lib/frameSelection';
import { modePillFor } from '@/lib/modePill';
import useDragPan, { PAN_CURSOR_CSS } from './useDragPan';
import useMiddlePan from './useMiddlePan';
import useOutlineTool, { roomHoles } from './useOutlineTool';
import useRoomTool from './useRoomTool';
import { RoomPickPanel } from './RoomProposalLayer';
import VertexPopover from './VertexPopover';
import CountTypePicker from './CountTypePicker';
import OpeningPopover from './OpeningPopover';
import { pointsToPct, pctToPoints, minPointsOf, deleteVertices, nudgeVertices, insertVertex, pathPositionM, cutGap, roomsInBox, similarRooms, copyMeasurement, wallFaceAt } from '@/lib/editGestures';
import { openingForEdge, addEdgeOpening, openingText, openingAt, openingState, applyOpeningEdit } from '@/lib/openingEdit';
import { matchViewerHotkey, withKey, keyText, isMacPlatform } from '@/lib/viewerShortcuts';
import { historyReducer, initHistory, describeChange } from '@/lib/measureHistory';
import SymbolReviewPanel, { useSymbolSearch, SYMBOL_HINTS } from './SymbolReviewPanel';
import { useLegendTool } from './LegendTool';
import LegendReviewPanel from './LegendReviewPanel';
import { applyCreate, legendGotoPage } from '@/lib/legendReview';
import { aiTallies as aiTalliesOf } from '@/lib/symbolSearch';
import SheetRail from './SheetRail';
import { buildSheetRail, setSheetOverride, clearSheetOverride, overrideFor, floatingPanelLeft, sheetRailWidth, readSheetRailFull, writeSheetRailFull } from '@/lib/sheetRail';

// A measurement's kind as the toasts and the selection bar say it.
const MEASURE_KIND_NAMES = { distance: 'Atstumas', perimeter: 'Perimetras', area: 'Plotas', count: 'Žymė' };
// The doorway „Iškirpti angą" cuts out of a length (W5-A A2): the standard interior door opening.
const DOORWAY_GAP_M = 0.9;

// Empty measurement draft (shape of measureOverlayReducer's state).
const EMPTY_DRAFT = { points: [], committed: false };

// „Atšaukti" in a save's toast (Pathon v3 W1-D, D3): the host's save resolves to `{undo}`; the toast keeps the
// button for 10 s. A save with nothing to undo gets the plain toast.
function undoAction(saved) {
  const undo = typeof saved?.undo === 'function' ? saved.undo : null;
  return undo ? { duration: 10_000, action: { label: 'Atšaukti', onClick: () => { undo(); } } } : {};
}

// The instruction for the armed tool is ONE sentence beside the pointer (lib/cursorHints, CursorHint —
// v3 W1-B B3); the mode pill holds the mode's name and buttons, the status bar the scale and the snap note.
// What this sheet snaps to, by its wall geometry status — said in the status bar while a snapping tool is
// armed (the tool's own instruction lives in the pill on the drawing, once — v3 W1-C). One snap colour;
// the mark's shape says what the click lands on (MeasureLayer SnapDot).
const SNAP_NOTE = {
  ok: 'Prilimpa prie brėžinio sienų kampų (kvadratas), sienų (rombas) ir jūsų matavimų (apskritimas)',
  no_walls: 'Šiame lape sienų programa neperskaitė — prilimpa tik prie jūsų matavimų',
};

// visiblePageOf moved to lib/visiblePage (2026-10-16): the scale panel reads the same page.

/**
 * SearchBox — inline toolbar search (Task 4.1). Debounced live query through
 * useSearch; jumping is OURS (the plugin's goToResult only mutates state — it
 * never scrolls), wired via onActiveResultChange → scrollToPage. The session
 * dies with the box (unmount → stopSearch) so highlights never linger.
 */
function SearchBox({ documentId, onClose }) {
  const { state: search, provides: searchApi } = useSearch(documentId);
  const { provides: scrollApi } = useScroll(documentId);
  const [query, setQuery] = useState('');
  // Live query, debounced ~300ms. Empty string clears results (plugin API).
  useEffect(() => {
    if (!searchApi) return undefined;
    const t = setTimeout(() => { searchApi.searchAllPages(query); }, 300);
    return () => clearTimeout(t);
  }, [query, searchApi]);
  // Active hit changed (fresh search lands on 0, Enter/chevrons navigate) →
  // scroll its page into view.
  useEffect(() => {
    if (!searchApi) return undefined;
    return searchApi.onActiveResultChange((idx) => {
      const hit = searchApi.getState().results[idx];
      if (hit) scrollApi?.scrollToPage({ pageNumber: hit.pageIndex + 1, behavior: 'smooth' });
    });
  }, [searchApi, scrollApi]);
  // stopSearch on unmount — via ref so the cleanup sees the live capability.
  const searchApiRef = useRef(searchApi);
  useEffect(() => { searchApiRef.current = searchApi; });
  useEffect(() => () => { searchApiRef.current?.stopSearch(); }, []);
  const total = search?.total ?? 0;
  const committed = search?.query ?? '';
  const hasQuery = committed !== '' && committed === query.trim();
  // Raster honesty: only after OUR typed query finished searching with 0 hits.
  const noHits = hasQuery && !search?.loading && total === 0;
  const btn = 'p-1 rounded text-viewer-chrome-foreground hover:bg-viewer-chrome-hover disabled:opacity-40 disabled:hover:bg-transparent';
  return (
    <span className="relative inline-flex items-center gap-1">
      <input
        autoFocus
        type="text"
        value={query}
        onChange={(e) => setQuery(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === 'Enter') {
            e.preventDefault();
            if (e.shiftKey) searchApi?.previousResult(); else searchApi?.nextResult();
          } else if (e.key === 'Escape') {
            e.preventDefault();
            onClose?.();
          }
        }}
        placeholder="Ieškoti brėžinyje…"
        aria-label="Paieška dokumente"
        title="Ieško teksto brėžinyje (patalpų pavadinimų, žymėjimų). Skenuotuose PDF teksto nėra — nerasta nieko."
        className="w-44 h-6 px-2 rounded border border-viewer-chrome-border bg-viewer-chrome-muted text-meta text-viewer-chrome-foreground placeholder:text-viewer-chrome-foreground/45 focus:outline-none focus:border-viewer-chrome-active"
      />
      {hasQuery && (
        <span className="mono tabular text-meta text-viewer-chrome-foreground/65 whitespace-nowrap px-0.5">
          {total > 0 ? `${(search.activeResultIndex ?? 0) + 1} / ${total}` : '0 / 0'}
        </span>
      )}
      <button className={btn} title="Ankstesnis rezultatas (Shift+Enter)" disabled={total === 0} onClick={() => searchApi?.previousResult()}><ChevronUp className="w-4 h-4" /></button>
      <button className={btn} title="Kitas rezultatas (Enter)" disabled={total === 0} onClick={() => searchApi?.nextResult()}><ChevronDown className="w-4 h-4" /></button>
      {noHits && (
        <span className="absolute left-0 top-full mt-2 z-40 px-2 py-1 rounded border border-viewer-chrome-border bg-viewer-chrome text-meta text-viewer-chrome-foreground/65 whitespace-nowrap shadow-sm">
          Rezultatų nėra — šis PDF greičiausiai skenuotas (be teksto)
        </span>
      )}
    </span>
  );
}

// The canvas chrome's cards (v3 W1-B B6, W5-B): the sheet header (SheetHeaderBadge) and the reading / editions
// buttons with the search at the top right, the zoom column (ZoomCluster) at the bottom right.
const chromeBtn = 'h-8 min-w-8 px-1.5 inline-flex items-center justify-center rounded text-viewer-chrome-foreground hover:bg-viewer-chrome-hover disabled:opacity-40 disabled:hover:bg-transparent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring';
const chromeCard = 'pointer-events-auto rounded-panel border border-border bg-card shadow-md flex items-center gap-0.5 px-1 py-1';

/** Top right: „Perskaityti iš naujo" and „Palyginti leidimus" (renderToolbarAddon), then the text search. */
function CanvasHeader({ documentId, totalPages, addon = null, addonContext = null, searchOpen, onToggleSearch, onCloseSearch }) {
  const { state: scroll } = useScroll(documentId);
  const cur = visiblePageOf(scroll);
  return (
    <div className={chromeCard} data-canvas-header>
      {addon && <span className="inline-flex items-center gap-1 px-0.5">{addon(cur, totalPages || 1, addonContext ? addonContext(cur) : null)}</span>}
      {searchOpen && <SearchBox documentId={documentId} onClose={onCloseSearch} />}
      <button
        type="button"
        className={`${chromeBtn} ${searchOpen ? 'bg-viewer-chrome-active/15 text-viewer-chrome-active' : ''}`}
        title={withKey('Paieška', 'openSearch')}
        aria-label={withKey('Paieška', 'openSearch')}
        aria-pressed={!!searchOpen}
        onClick={onToggleSearch}
      ><Search className="w-4 h-4" /></button>
    </div>
  );
}

// ISO A sheet sizes in mm (portrait). Matched in either orientation, ±2mm.
const ISO_A_SIZES = [
  ['A4', 210, 297],
  ['A3', 297, 420],
  ['A2', 420, 594],
  ['A1', 594, 841],
  ['A0', 841, 1189],
];

function isoALabel(wMm, hMm) {
  const lo = Math.min(wMm, hMm);
  const hi = Math.max(wMm, hMm);
  const hit = ISO_A_SIZES.find(([, a, b]) => Math.abs(lo - a) <= 2 && Math.abs(hi - b) <= 2);
  return hit ? hit[0] : null;
}

// The scale readout and its tooltip — what the page's scale is and where it
// comes from (written on the sheet, measured from the dimensions, the room
// areas, or his own) — live in lib/scaleLabel.js (2026-10-06), tested there.

/**
 * StatusBar — bottom h-6 strip: page/zoom · sheet size in mm (+ ISO-A label) ·
 * fill-mode hint or the current page's calibrated scale.
 */
function StatusBar({ documentId, totalPages, pages, fillFor, fillBusy = false, measureScales, measureTool = null, outlineEdit = null, projectId = null, symbolHint = null, scaleChipShown = false, snapKind = null }) {
  const { state: zoom } = useZoom(documentId);
  const { state: scroll } = useScroll(documentId);
  const pct = typeof zoom?.currentZoomLevel === 'number' ? Math.round(zoom.currentZoomLevel * 100) : 100;
  const cur = visiblePageOf(scroll);
  const size = pages?.[cur - 1]?.size;
  let sheet = null;
  if (size?.width && size?.height) {
    const wMm = Math.round((size.width * 25.4) / 72);
    const hMm = Math.round((size.height * 25.4) / 72);
    const label = isoALabel(wMm, hMm);
    sheet = `${wMm}×${hMm} mm${label ? ` (${label})` : ''}`;
  }
  const pageScale = measureScales?.[cur];
  const scaleText = scaleStatusText(pageScale);
  // Whether the visible sheet has wall geometry to snap to — same cache the page hosts fill, so this
  // costs no extra request; `select` and `count` do not snap, the others do.
  const snapsHere = measureTool != null && measureTool !== 'select' && measureTool !== 'count' && measureTool !== 'room';
  const { status: geometryStatus } = usePageGeometry(projectId, cur, snapsHere);
  // One place per instruction (v3 W1-C): the armed tool's sentence is the pill on the drawing — the status
  // bar no longer repeats it; it keeps the scale sentence and what this sheet snaps to.
  // the snap under the pointer is named (W5-A A6); otherwise what this sheet snaps to
  const snapNote = snapsHere && !symbolHint && !outlineEdit
    ? (snapKind && SNAP_KIND_TEXT[snapKind] ? `Prilimpa: ${SNAP_KIND_TEXT[snapKind]} · laikykite Ctrl — peršokti iki artimiausio` : (SNAP_NOTE[geometryStatus] || ''))
    : '';
  return (
    <div className="h-6 shrink-0 bg-viewer-chrome border-t border-viewer-chrome-border text-meta text-viewer-chrome-foreground/65 px-3 flex items-center gap-3">
      <span className="mono tabular whitespace-nowrap">psl. {cur} / {totalPages || 1} · {pct}%</span>
      {sheet && <span className="mono tabular whitespace-nowrap">{sheet}</span>}
      {fillFor != null ? (
        <span className="ml-auto whitespace-nowrap text-viewer-chrome-active">
          {fillBusy ? `Ieškoma patalpos ${fillFor} kontūro…` : `Spustelėkite patalpos ${fillFor} viduje`}
        </span>
      ) : (
        <>
          {snapNote && <span className="ml-auto min-w-0 truncate" title={snapNote}>{snapNote}</span>}
          {/* The scale readout and its way in are the scale chip on the drawing (Pathon v3 W1-D, ScaleChip);
              without one (a viewer with no project, the check view) the sentence stays here, read-only. */}
          {!scaleChipShown && (
            <span title={scaleStatusTitle(pageScale)} className={`${snapNote ? '' : 'ml-auto'} shrink-0 whitespace-nowrap`}>{scaleText}</span>
          )}
        </>
      )}
    </div>
  );
}

/**
 * ThumbnailRail — left collapsible page rail on @embedpdf/plugin-thumbnail.
 * ThumbnailsPane virtualizes rows; each ThumbMeta row is absolutely positioned
 * at meta.top inside the pane (that's the plugin's windowing contract).
 */
function ThumbnailRail({ documentId }) {
  const { state: scroll, provides: scrollApi } = useScroll(documentId);
  const cur = visiblePageOf(scroll);
  return (
    <aside className="w-[148px] shrink-0 bg-viewer-chrome border-r border-viewer-chrome-border">
      <ThumbnailsPane documentId={documentId} style={{ height: '100%' }}>
        {(m) => {
          const pageNumber = m.pageIndex + 1;
          const isCurrent = pageNumber === cur;
          return (
            <button
              key={m.pageIndex}
              type="button"
              title={`Puslapis ${pageNumber}`}
              onClick={() => scrollApi?.scrollToPage({ pageNumber, behavior: 'smooth' })}
              style={{ position: 'absolute', top: m.top, height: m.wrapperHeight, left: 0, right: 0 }}
              className="flex flex-col items-center group focus:outline-none"
            >
              <ThumbImg
                documentId={documentId}
                meta={m}
                style={{ width: m.width, height: m.height }}
                className={`bg-white rounded-[2px] ${isCurrent ? 'ring-2 ring-viewer-chrome-active' : 'ring-1 ring-viewer-chrome-border group-hover:ring-viewer-chrome-foreground/35'}`}
              />
              <span
                style={{ height: m.labelHeight, lineHeight: `${m.labelHeight}px` }}
                className={`mono tabular text-meta ${isCurrent ? 'text-viewer-chrome-active' : 'text-viewer-chrome-foreground/65'}`}
              >
                {pageNumber}
              </span>
            </button>
          );
        }}
      </ThumbnailsPane>
    </aside>
  );
}

/**
 * RailHost — the tool cards (ToolRail) with the viewer's own „Daugiau" menu: the items the old toolbar
 * carried at its far end (Masteliai, Istorija, print, download, „?") and the wide sheet list (T).
 */
function RailHost({ documentId, compact, activeTool, onTool, available, layers, onToggleLayer, onDownload, scalesOpen = false, onToggleScales = null, historyOpen = false, onToggleHistory = null, railOpen = false, onToggleRail = null, onOpenGuide = null }) {
  const { provides: printApi } = usePrint(documentId);
  const mac = useMemo(() => isMacPlatform(), []);
  const more = [
    onToggleScales && { id: 'scales', label: 'Masteliai', Icon: ListChecks, checked: !!scalesOpen, onSelect: onToggleScales, testId: 'scales-toggle' },
    onToggleHistory && { id: 'history', label: 'Istorija', Icon: History, checked: !!historyOpen, onSelect: onToggleHistory, testId: 'viewer-history-toggle', shortcut: keyText('undo', { mac }) },
    'separator',
    onToggleRail && { id: 'rail', label: 'Plati lapų juosta', Icon: PanelLeft, checked: !!railOpen, onSelect: onToggleRail, shortcut: keyText('toggleThumbs', { mac }), testId: 'viewer-thumbs-toggle' },
    { id: 'print', label: 'Spausdinti brėžinį', Icon: Printer, onSelect: () => printApi?.print(), disabled: !printApi, shortcut: keyText('print', { mac }), testId: 'viewer-print' },
    { id: 'download', label: 'Atsisiųsti originalų PDF (be matavimų)', Icon: Download, onSelect: () => onDownload?.(), disabled: !onDownload, testId: 'viewer-download' },
    'separator',
    onOpenGuide && { id: 'guide', label: 'Spartieji klavišai', Icon: Keyboard, onSelect: onOpenGuide, shortcut: keyText('openGuide', { mac }), testId: 'viewer-shortcuts-open' },
  ].filter(Boolean).filter((item, i, all) => item !== 'separator' || (i > 0 && all[i - 1] !== 'separator' && i < all.length - 1));
  return (
    <ToolRail
      compact={compact}
      mac={mac}
      activeTool={activeTool}
      onTool={onTool}
      available={available}
      layers={layers}
      onToggleLayer={onToggleLayer}
      more={more}
    />
  );
}

/**
 * ViewerHotkeys — the viewer keyboard contract, one window keydown listener.
 * WHICH key does WHAT lives in lib/viewerShortcuts (the table the „?" guide
 * prints); this component only maps a matched entry id to its action. Guarded:
 * typing surfaces (input/textarea/select/contentEditable) are never intercepted,
 * and meta/ctrl combos the table does not list stay with the browser.
 * Notes kept from the hand-written switch: measure-tool keys are ignored while
 * fill is armed; Delete/Backspace only act in select mode with a selection (so
 * they never collide with MeasureLayer's Backspace = remove-last-vertex); Esc
 * chain: close search → measure (outline edit / calibration dialog / tool) →
 * cancel fill-mode → clear focused room.
 */
function ViewerHotkeys({ documentId, onCopyMarks = null, onPasteMarks = null, onDuplicateMarks = null, fillArmed, onEscape, onToggleThumbs, onMeasureToolKey, canDeleteSelected, onDeleteSelected, onOpenSearch, onUndo, onRedo, onOpenGuide, onToggleZoneFills, onToggleWallsLayer, onToggleSymbolSearch = null, onToggleLegend = null, onRoomTool = null, onFrameSelection = null, onRoomEdit = null, onRoomMerge = null, onRoomSubtract = null }) {
  const { provides: zoomApi } = useZoom(documentId);
  const { state: scroll, provides: scrollApi } = useScroll(documentId);
  const { provides: printApi } = usePrint(documentId);
  // Scroll state through a ref so the window listener isn't re-bound on every
  // scroll tick — only the fit keys ('0'/'W') read it, to pre-sync the plugin's
  // lagging currentPage to the page actually on screen before fitting.
  const scrollRef = useRef(scroll);
  useEffect(() => { scrollRef.current = scroll; });
  useEffect(() => {
    const fitTo = (mode) => {
      const vp = visiblePageOf(scrollRef.current);
      if (vp !== (scrollRef.current?.currentPage ?? vp)) scrollApi?.scrollToPage({ pageNumber: vp });
      zoomApi?.requestZoom(mode);
    };
    const tool = (id) => (fillArmed || !onMeasureToolKey ? false : (onMeasureToolKey(id), true));
    const step = (d) => {
      const vp = visiblePageOf(scrollRef.current);
      const last = scrollRef.current?.totalPages ?? vp + 1;
      scrollApi?.scrollToPage({ pageNumber: Math.max(1, Math.min(last, vp + d)) });
      return true;
    };
    // Each handler returns true when it acted (→ preventDefault). One key per table id.
    const handlers = {
      // HOTKEY-HANDLERS:start
      zoomIn: () => { zoomApi?.zoomIn(); return true; },
      zoomOut: () => { zoomApi?.zoomOut(); return true; },
      fitPage: () => { fitTo(ZoomMode.FitPage); return true; },
      fitWidth: () => { fitTo(ZoomMode.FitWidth); return true; },
      nextPage: () => step(1),
      prevPage: () => step(-1),
      toggleThumbs: () => { onToggleThumbs?.(); return true; },
      openSearch: () => (onOpenSearch ? (onOpenSearch(), true) : false),
      print: () => (printApi ? (printApi.print(), true) : false),
      openGuide: () => (onOpenGuide ? (onOpenGuide(), true) : false),
      toolSelect: () => tool('select'),
      toolPan: () => tool('pan'),
      toolCalibrate: () => tool('calibrate'),
      toolFindSimilar: () => (fillArmed || !onToggleSymbolSearch ? false : (onToggleSymbolSearch(), true)),
      // G — „Pažymėti legendą" (Pathon v3 W2-B): the legend proposed, counted, reviewed, then created
      toolLegend: () => (fillArmed || !onToggleLegend ? false : (onToggleLegend(), true)),
      // R — the room tool (W1-D): one click inside a room, its outline off the walls, proposed, then saved.
      toolRoom: () => (fillArmed || !onRoomTool ? false : (onRoomTool(), true)),
      toolDistance: () => tool('distance'),
      toolArea: () => tool('area'),
      toolPerimeter: () => tool('perimeter'),
      toolCount: () => tool('count'),
      toolLasso: () => tool('lasso'),
      deleteSelected: () => (canDeleteSelected ? (onDeleteSelected?.(), true) : false),
      undo: () => (onUndo ? (onUndo(), true) : false),
      // W5-A A11: his measurements copied, pasted onto the sheet on screen, duplicated beside themselves
      copyMarks: () => (onCopyMarks ? onCopyMarks() : false),
      pasteMarks: () => (onPasteMarks ? onPasteMarks(visiblePageOf(scrollRef.current)) : false),
      duplicateMarks: () => (onDuplicateMarks ? onDuplicateMarks() : false),
      redo: () => (onRedo ? (onRedo(), true) : false),
      // One Esc = one step back (lib/escOrder): a point, the tool, a panel, then the selection.
      escape: () => (onEscape ? onEscape() : false),
      frameSelection: () => (onFrameSelection ? onFrameSelection() : false),
      roomEditOutline: () => (onRoomEdit ? (onRoomEdit(), true) : false),
      roomMerge: () => (onRoomMerge ? (onRoomMerge(), true) : false),
      roomSubtract: () => (onRoomSubtract ? (onRoomSubtract(), true) : false),
      toggleZoneFills: () => (onToggleZoneFills ? (onToggleZoneFills(), true) : false),
      toggleWallsLayer: () => (onToggleWallsLayer ? (onToggleWallsLayer(), true) : false),
      // HOTKEY-HANDLERS:end
    };
    const onKeyDown = (e) => {
      const t = e.target;
      if (t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.tagName === 'SELECT' || t.isContentEditable)) return;
      const id = matchViewerHotkey(e);
      if (id && handlers[id]?.()) e.preventDefault();
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [zoomApi, scrollApi, printApi, fillArmed, onEscape, onToggleThumbs, onMeasureToolKey, canDeleteSelected, onDeleteSelected, onOpenSearch, onUndo, onRedo, onOpenGuide, onToggleZoneFills, onToggleWallsLayer, onToggleSymbolSearch, onToggleLegend, onRoomTool, onFrameSelection, onRoomEdit, onRoomMerge, onRoomSubtract, onCopyMarks, onPasteMarks, onDuplicateMarks]);
  return null;
}

// Scroll the viewport to a focused room's page when it changes (panel → canvas
// nav). Page-only jumps (Matavimai rows, provenance links) carry no room —
// fall back to the focusedPage prop so they scroll the Embed viewer too.
//
// FOUNDER BUG 2026-07-25 ("scrolls to other pages by itself; zoom snaps to
// one spot"): scrollApi's identity churns with scroll/zoom state, and with a
// focused room the old effect re-ran scrollToPage on EVERY tick — the viewer
// literally fought the user's navigation. Jump ONCE per new target; re-arm
// only when the focus object itself changes (clicking a room again re-jumps).
function FocusScroller({ documentId, focusedRoom, focusedPage, skipJumpRef = null, rooms = null, onFrame = null }) {
  const { provides: scrollApi, state: scroll } = useScroll(documentId);
  const retriesRef = useRef(0);
  const lastPageRef = useRef(null);
  // roomPageOf is THE shared page-field precedence (roomZones owns it) — the
  // zone layer and this scroller must never disagree about a room's page.
  const targetPage = (focusedRoom ? roomPageOf(focusedRoom) : null) ?? focusedPage ?? null;
  const doneRef = useRef(null);
  // Re-armed when the focus moves to another ROOM or page (Pathon v3 W1-D) — not when the same room comes back
  // as a new object: every outline save re-derives the focused room from the saved project, and the old
  // identity rule threw the view to the page's top-left after each save.
  const focusKey = `${focusedRoom?.nr ?? ''}|${focusedPage ?? ''}`;
  useEffect(() => { doneRef.current = null; }, [focusKey]);
  useEffect(() => {
    if (!targetPage || !scrollApi?.scrollToPage) return;
    if (doneRef.current === focusKey) return; // one jump per focus — never re-yank (scrollApi churns)
    doneRef.current = focusKey;
    // A room he clicked ON the drawing is already on screen (Pathon v3 W1-D): jumping to its page would
    // throw the view back to the sheet's top-left corner under his cursor.
    const skip = skipJumpRef?.current;
    if (skip && focusedRoom && String(focusedRoom.nr) === skip.nr && Date.now() < skip.until) { lastPageRef.current = targetPage; return; }
    // A room focused from outside the drawing (a list row, Patikra, a search hit) is FRAMED — the room, not the
    // top of its sheet (W5-B B7, #132; lib/focusFrame). The host's FocusZoomer waits for the layout itself, so
    // the page-jump retries below stand down.
    if (focusedRoom && onFrame) {
      const full = (rooms || []).find((r) => String(r?.nr) === String(focusedRoom.nr)) || focusedRoom;
      const frame = focusFrameForRoom(full);
      if (frame) { retriesRef.current = 99; lastPageRef.current = frame.page; onFrame(frame); return; }
    }
    // No frame: the page, as before — and not again for another room on the page already shown.
    if (lastPageRef.current === targetPage && focusedRoom) return;
    lastPageRef.current = targetPage;
    scrollApi.scrollToPage({ pageNumber: targetPage, behavior: 'smooth' });
  }, [targetPage, scrollApi, focusKey]); // eslint-disable-line react-hooks/exhaustive-deps

  // THE JUMP CAN LAND ON NOTHING (2026-09-04, measured). `scrollToPage` is
  // callable before the pages have been measured, and calling it then computes
  // an offset of ~0 for every page: on a cold open the plugin's currentPage
  // became 2 while the viewport sat on the cover (scrollTop 4 of 9566, page 2
  // really starting at 784). Because the jump above fires exactly once per
  // target, that wasted call also consumed it, so a project would silently open
  // on its marketing render.
  //
  // So: confirm, and retry a bounded few times if it did not take. It stops the
  // moment the viewport is off page 1 — which is also what makes it safe. A
  // user who scrolls anywhere during that first second has left page 1, so this
  // can never fight him (founder bug 2026-07-25 "scrolls by itself").
  useEffect(() => { retriesRef.current = 0; }, [focusKey]);
  useEffect(() => {
    if (!targetPage || targetPage <= 1 || !scrollApi?.scrollToPage) return;
    if (retriesRef.current >= 8) return;
    // Read the METRICS, never `currentPage`: the failed jump already wrote 2
    // into currentPage, so trusting it would report success on a viewport that
    // never moved (which is exactly how this bug hid). Empty metrics = the
    // pages are not measured yet; page 1 = the viewport is still on the cover.
    // Anything else means it landed, or the user scrolled — both stop us.
    const m = scroll?.pageVisibilityMetrics;
    const measured = Array.isArray(m) && m.length > 0;
    if (measured && visiblePageOf(scroll) !== 1) return;
    const id = setTimeout(() => {
      retriesRef.current += 1;
      scrollApi.scrollToPage({ pageNumber: targetPage, behavior: 'auto' });
    }, 300);
    return () => clearTimeout(id);
  }, [targetPage, scrollApi, scroll]);
  return null;
}

/**
 * FocusZoomer — „show me THIS place": jump to a page and fit a rectangle of it
 * in the viewport (check-sheet mode). `focus = { page, rect: [x0, y0, x1, y1]
 * in display-space page fractions, nonce }`; a new nonce re-runs it.
 *
 * zoomToArea reads the scroll layout, and the target page's box only exists in
 * it once the scroller has laid it out — so: scroll to the page, then retry for
 * a few frames until the page is there (same lesson as FocusScroller: a jump can
 * land on nothing). The rect is given to the plugin in the page's DISPLAYED
 * frame at zoom 1, which is the frame its layout boxes live in.
 */
function FocusZoomer({ documentId, focus, pages }) {
  const { provides: scrollApi } = useScroll(documentId);
  const { provides: zoomApi } = useZoom(documentId);
  const scrollRef = useRef(scrollApi);
  const zoomRef = useRef(zoomApi);
  const pagesRef = useRef(pages);
  const anchorRef = useRef(null);            // a node inside the viewer, to find THIS viewer's pages in the DOM
  useEffect(() => { scrollRef.current = scrollApi; zoomRef.current = zoomApi; pagesRef.current = pages; });
  const nonce = focus?.nonce;
  useEffect(() => {
    if (!focus || !focus.page) return undefined;
    let cancelled = false;
    let tries = 0;
    let raf = 0;
    const pageIndex = Number(focus.page) - 1;
    const run = () => {
      if (cancelled) return;
      const sApi = scrollRef.current;
      const zApi = zoomRef.current;
      const size = pagesRef.current?.[pageIndex]?.size;
      const rot = normalizeRotation(pagesRef.current?.[pageIndex]?.rotation ?? 0);
      const laidOut = sApi?.getLayout?.()?.virtualItems?.some((it) => it.pageLayouts?.some((p) => p.pageIndex === pageIndex));
      if (!sApi || !zApi || !size || !laidOut) {
        if (tries++ < 60) raf = requestAnimationFrame(run);
        return;
      }
      const Wd = rot === 90 || rot === 270 ? size.height : size.width;
      const Hd = rot === 90 || rot === 270 ? size.width : size.height;
      const [x0, y0, x1, y1] = Array.isArray(focus.rect) && focus.rect.length === 4 ? focus.rect : [0, 0, 1, 1];
      sApi.scrollToPage({ pageNumber: Number(focus.page), behavior: 'auto' });
      // one more frame: the scroll position must be in place before the zoom
      // plugin measures where the rectangle's centre is on screen
      raf = requestAnimationFrame(() => {
        if (cancelled) return;
        zApi.zoomToArea(pageIndex, {
          origin: { x: x0 * Wd, y: y0 * Hd },
          size: { width: Math.max(1, (x1 - x0) * Wd), height: Math.max(1, (y1 - y0) * Hd) },
        });
        settle(0);
      });
    };
    // The engine's zoom-to-area is right about the ZOOM and, in a document of mixed
    // sheet sizes, wrong about the PLACE: a sheet narrower than the widest one is laid
    // out centred, and that offset is not in its arithmetic (measured 2026-09-20: a
    // room on a portrait A3 among landscape sheets landed ~420 px to the side). So
    // once the new zoom is laid out, the place is put in the middle from the DOM.
    const settle = (attempt) => {
      if (cancelled) return;
      raf = requestAnimationFrame(() => {
        if (cancelled) return;
        const root = anchorRef.current?.closest('[data-takeoff-viewer]');
        const host = root?.querySelector(`[data-page-number="${Number(focus.page)}"]`);
        let scroller = host?.parentElement || null;
        while (scroller && scroller !== root && !(scroller.scrollHeight > scroller.clientHeight + 1
          && /(auto|scroll)/.test(getComputedStyle(scroller).overflowY))) scroller = scroller.parentElement;
        if (!host || !scroller || scroller === root) {
          if (attempt < 30) settle(attempt + 1);
          return;
        }
        const d = centreDelta(host.getBoundingClientRect(), scroller.getBoundingClientRect(),
          Array.isArray(focus.rect) && focus.rect.length === 4 ? focus.rect : [0, 0, 1, 1]);
        if (Math.abs(d.dx) > 2 || Math.abs(d.dy) > 2) scroller.scrollBy({ left: d.dx, top: d.dy, behavior: 'auto' });
        // the first frames after a big zoom change are still laying tiles out — look again a few times
        if (attempt < 4) settle(attempt + 1);
      });
    };
    raf = requestAnimationFrame(run);
    return () => { cancelled = true; cancelAnimationFrame(raf); };
    // `focus` is read when its nonce changes — a new object with the same nonce is not a new request
  }, [nonce, documentId]);
  return <span ref={anchorRef} hidden data-focus-zoomer />;
}

// „Pažymėti legendą" (W2-B): which sheet is on screen — the legend is proposed on it, and proposed again when he
// scrolls to another sheet before choosing.
function LegendPageWatcher({ documentId, pageRef, onPage, gotoRef = null }) {
  const { state: scroll, provides: scrollApi } = useScroll(documentId);
  const cur = visiblePageOf(scroll);
  // B1-B: the pill's „Į 5 lapą" (the legend stands on another sheet) scrolls through this
  if (gotoRef) gotoRef.current = (page) => scrollApi?.scrollToPage({ pageNumber: page, behavior: 'smooth' });
  // W5-B B10: the sheet on screen is also told to the Matavimai list's „Šis lapas“ filter (MeasureGroups)
  useEffect(() => { pageRef.current = cur; onPage?.(cur); window.__pathonViewerPage = cur; window.dispatchEvent(new CustomEvent('samatu:viewer-page', { detail: { page: cur } })); }, [cur]); // eslint-disable-line react-hooks/exhaustive-deps
  return null;
}

function ViewerInner({ renderToolbarAddon = null, check = null, focus = null, rooms, focusedRoom, focusedPage, hiddenRoomNrs, hoveredRoomNrExternal, onRoomZoneClick, onPagePoint, onClearFocus, projectId, pdfBlob, exportFileName, onRoomPolygonFill, fillRequest, initialMeasurements, initialMeasureScales, initialCountTypes, onMeasureDataChange, laneScales = null, onRoomOutlineEdit = null, project = null, onOutlineTool = null, onRoomToolPreview = null, onRoomToolCommit = null, onRoomOpenings = null, sheetPages = null, sheetOverrides = null, onSheetOverridesChange = null, sheetLinksVersion = 0, revisionOverlay = null, active = true, legendPanelSlot = null, onLegendPanelChange = null, skippedPages = null, onSkippedPagesChange = null, onLegendBlankRows = null }) {
  const { activeDocumentId } = useActiveDocument();
  // ---- Sheets (Togal-v2 W7) ------------------------------------------------
  // The rail's names/types/groups (lib/sheetRail) from the classification + the user's overrides.
  // A rename or „Atkurti automatinį" is undone from its toast („Atšaukti"): the Istorija stack holds
  // measurements only (lib/measureHistory snapshots a measurement list), so sheet names stay out of it.
  const sheetOverridesRef = useRef(sheetOverrides);
  useEffect(() => { sheetOverridesRef.current = sheetOverrides; });
  const putSheetOverride = (page, entry) => {
    const cur = sheetOverridesRef.current || {};
    const next = entry ? { ...clearSheetOverride(cur, page), [String(page)]: entry } : clearSheetOverride(cur, page);
    sheetOverridesRef.current = next;
    onSheetOverridesChange?.(next);
  };
  const changeSheet = (sheet, next, message) => {
    const before = overrideFor(sheetOverridesRef.current, sheet.page);
    const after = overrideFor(next, sheet.page);
    if (JSON.stringify(before || null) === JSON.stringify(after || null)) return;
    putSheetOverride(sheet.page, after);
    toast.success(message, {
      action: { label: 'Atšaukti', onClick: () => putSheetOverride(sheet.page, before) },
    });
  };
  const renameSheet = (sheet, patch) => changeSheet(
    sheet,
    setSheetOverride(sheetOverridesRef.current, sheet.page, patch,
      { name: sheet.autoName, tipas: sheet.autoTipas, discipline: sheet.autoDiscipline }),
    `Lapas ${sheet.page} pakeistas`,
  );
  // „Neskaityti šio lapo" (W5-B B9): the pages the re-read and the detection run read as blank; Undo in the toast.
  const skippedRef = useRef(skippedPages);
  useEffect(() => { skippedRef.current = skippedPages; });
  const skippedSet = useMemo(() => new Set((skippedPages || []).map(Number)), [skippedPages]);
  const putSkipped = (pages) => {
    const next = [...new Set(pages.map(Number))].filter((n) => n >= 1).sort((a, b) => a - b);
    skippedRef.current = next;
    onSkippedPagesChange?.(next);
  };
  const toggleSkipSheet = (sheet) => {
    const before = (skippedRef.current || []).map(Number);
    const on = !before.includes(sheet.page);
    putSkipped(on ? [...before, sheet.page] : before.filter((p) => p !== sheet.page));
    toast.success(on ? `Lapas ${sheet.page} nebus skaitomas` : `Lapas ${sheet.page} vėl bus skaitomas`, {
      description: on ? 'Jis lieka PDF ir brėžinyje. Perskaitant brėžinį iš naujo ir „Perskaityti lapą“ programa jo neskaitys.' : undefined,
      duration: 10_000,
      action: { label: 'Atšaukti', onClick: () => putSkipped(before) },
    });
  };
  const resetSheet = (sheet) => changeSheet(
    sheet, clearSheetOverride(sheetOverridesRef.current, sheet.page),
    `Lapui ${sheet.page} grąžintas automatinis pavadinimas`,
  );
  const focusedRoomNr = focusedRoom?.nr ?? null;
  // ---- Select by click (Pathon v3 W1-D, D1) ---------------------------------
  // The focused room is the host's (the panel's room); Shift+click adds rooms beside it (`extraRoomNrs`), the
  // way Togal and Kreo select several shapes. A click on the drawing that focuses a room must not make the
  // viewer jump to that room's page — it is already under the cursor (FocusScroller reads `skipJumpRef`).
  const [extraRoomNrs, setExtraRoomNrs] = useState([]);
  const skipJumpRef = useRef(null);
  const selectionFromClickRef = useRef(false);
  // The host moved the focus (a list row, Patikra, Esc): the extra rooms were chosen beside the OLD room.
  useEffect(() => {
    if (selectionFromClickRef.current) { selectionFromClickRef.current = false; return; }
    setExtraRoomNrs([]);
  }, [focusedRoomNr]);
  const applyRoomSelection = (next) => {
    const cur = focusedRoomNr == null ? null : String(focusedRoomNr);
    if (next.focused !== cur) {
      selectionFromClickRef.current = true;
      if (next.focused == null) onClearFocus?.();
      else {
        const room = (rooms || []).find((r) => String(r?.nr) === next.focused);
        skipJumpRef.current = { nr: next.focused, until: Date.now() + 1500 };
        onRoomZoneClick?.({ nr: next.focused, puslapio_nr: roomPageOf(room) });
      }
    }
    setExtraRoomNrs(next.extra);
  };
  // A click at rest (or with „Žymėti") on the drawing: the room under it, else nothing (empty paper clears).
  const selectRoomAt = (pt) => {
    const where = displayPointOf(pt);
    let hit = where ? roomAtPoint(rooms, where, {
      renderedWidth: pt.renderedWidth, renderedHeight: pt.renderedHeight, hidden: hiddenRoomNrs,
    }) : null;
    // W5-B B2: a click in the title block, a legend, a table or a notes block outside the plan selects no room
    // (zones already read for this sheet; unknown zones never block) — the cursor says why.
    const refused = hit && where && projectId ? noRoomZoneAt(cachedSheetZones(projectId, where.page), where.x_pct, where.y_pct) : null;
    if (refused) { flashCursorHint(refused.sentence); hit = null; }
    applyRoomSelection(nextRoomSelection({ focused: focusedRoomNr, extra: extraRoomNrs }, hit?.nr ?? null, { shift: !!pt.shiftKey }));
  };
  // `fillFor` = the room nr currently armed for „Kontūras paspaudus" click-to-fill (2026-10-18: it was
  // „Taisyti kontūrą", the name the vertex editor now carries — one verb per outline fix).
  const [fillFor, setFillFor] = useState(null);
  // Round-trip in flight (backend flood-fill takes ~3-6 s) — drives the status
  // hint so the user sees progress instead of a silent stall (audit P0).
  const [fillBusy, setFillBusy] = useState(false);
  // Drop the armed room if focus changes away (avoid filling the wrong room).
  useEffect(() => { setFillFor(null); }, [focusedRoomNr]);
  // Room layer presentation. Founder decision 2026-07-11: numbered markers by
  // default; the toolbar Layers toggle re-enables the filled polygon zones.
  const [zoneFillsVisible, setZoneFillsVisible] = useState(ROOM_POLYGON_FILLS_DEFAULT_VISIBLE);
  // Walls layer (2026-10-16): the wall solid, every outline and every opening the program read on the
  // sheet. Off by default — the drawing stays clean — remembered per browser.
  const [wallsLayerVisible, setWallsLayerVisibleState] = useState(() => {
    try { return localStorage.getItem('samatu_viewer_walls') === '1'; } catch { return false; }
  });
  const setWallsLayerVisible = (next) => {
    try { localStorage.setItem('samatu_viewer_walls', next ? '1' : '0'); } catch { /* private mode */ }
    setWallsLayerVisibleState(next);
  };
  // Outline editing (2026-10-16): the focused room's polygon_pct, vertex by vertex. {nr, page, points} | null.
  // Saving goes through onRoomOutlineEdit → api outline-set (the ring is measured and its walls re-read
  // server side) → the usual samatu:project-recompute path. Nothing is saved until „Išsaugoti".
  const [outlineEdit, setOutlineEdit] = useState(null);
  const [outlineSaving, setOutlineSaving] = useState(false);
  const startOutlineEdit = (nrArg = null) => {
    const want = nrArg != null && typeof nrArg !== 'object' ? String(nrArg) : (focusedRoom ? String(focusedRoom.nr) : null);
    const r = want != null && (rooms || []).find((x) => String(x?.nr) === want);
    if (!r || !Array.isArray(r.polygon_pct) || r.polygon_pct.length < 3) {
      toast.info('Ši patalpa dar neturi kontūro — pirmiausia „Kontūras paspaudus"');
      return;
    }
    setMeasureTool(null); setSelectedMeasureId(null); setFillFor(null); if (symbol.active) symbol.close(); outlineTools.cancel();
    setOutlineEdit({
      target: 'room',
      nr: String(r.nr),
      page: roomPageOf(r),
      points: r.polygon_pct.map(([x, y]) => [Number(x), Number(y)]),
      holes: roomHoles(r),       // „Atimti" cut-outs ride along: a vertex edit keeps them
      history: [],
      selected: [],
      tableAreaM2: Number(r.plotas_m2) > 0 ? Number(r.plotas_m2) : null,
    });
  };
  const cancelOutlineEdit = () => { setOutlineEdit(null); setVertexMenu(null); };
  // A measurement edited point by point (Pathon v3 W5-A A1: double-click it): the same vertex editor, in the
  // display frame; „Išsaugoti" writes its points back as one entry of „Istorija" (Ctrl+Z, „Atšaukti").
  const pageSizeOf = (page) => docPagesRef.current?.[page - 1] || null;
  const startMeasureEdit = (id) => {
    const m = measurements.find((x) => x.id === id);
    const pg = m && pageSizeOf(m.page);
    if (!m || !['distance', 'perimeter', 'area'].includes(m.kind) || !pg?.size || !Array.isArray(m.points) || m.points.length < 2) return;
    setMeasureTool(null); setSelectedMeasureId(null); setFillFor(null); if (symbol.active) symbol.close(); outlineTools.cancel();
    setOutlineEdit({
      target: 'measure',
      id: m.id,
      kind: m.kind,
      nr: null,
      page: m.page,
      points: pointsToPct(m.points, { width: pg.size.width, height: pg.size.height, rotation: pg.rotation ?? 0 }),
      holes: [],
      history: [],
      selected: [],
      closed: m.kind === 'area',
      minPoints: minPointsOf(m.kind),
    });
  };
  // An opening being edited on the drawing (A9): {o, nr, state, x, y} | null.
  const [openingEdit, setOpeningEdit] = useState(null);
  const saveOpeningEdit = async ({ kind, plotisMm }) => {
    const ed = openingEdit;
    setOpeningEdit(null);
    if (!ed || !onRoomOpenings) return;
    try {
      const saved = await onRoomOpenings(ed.nr, (el) => applyOpeningEdit(el, ed.o, { kind, plotisMm }));
      if (!saved) { toast.info('Anga nepasikeitė'); return; }
      toast.success(`Patalpa ${ed.nr}: ${openingText(kind, plotisMm).toLowerCase()}`, { description: 'Kiekiai perskaičiuojami.', ...undoAction(saved) });
    } catch (e) {
      toast.error(e?.message || 'Angos išsaugoti nepavyko');
    }
  };
  // The corner / edge pop-up (A2): {kind, index, t?, x, y} | null.
  const [vertexMenu, setVertexMenu] = useState(null);
  // Undo: every drag / insert / delete snapshots the ring first (OutlineEditLayer.onGestureStart);
  // Z or the toolbar arrow steps back. Bounded, like the measurement draft's undo.
  const snapshotOutline = () => setOutlineEdit((cur) => (cur
    ? { ...cur, history: [...(cur.history || []).slice(-49), cur.points] }
    : cur));
  const undoOutline = () => setOutlineEdit((cur) => (cur && cur.history?.length
    ? { ...cur, points: cur.history[cur.history.length - 1], history: cur.history.slice(0, -1) }
    : cur));
  const outlineInvalid = !!outlineEdit && outlineEdit.closed !== false && selfIntersects(outlineEdit.points.map(([x, y]) => ({ x, y })));
  const saveMeasureEdit = () => {
    const ed = outlineEdit;
    const pg = pageSizeOf(ed.page);
    if (!pg?.size) return;
    const before = measurements.find((m) => m.id === ed.id);
    if (!before) { setOutlineEdit(null); return; }
    const points = pctToPoints(ed.points, { width: pg.size.width, height: pg.size.height, rotation: pg.rotation ?? 0 });
    setMeasurements((prev) => prev.map((m) => (m.id === ed.id ? { ...m, points } : m)));
    setOutlineEdit(null);
    setVertexMenu(null);
    toast.success(`${MEASURE_KIND_NAMES[before.kind] || 'Matavimas'}: taškai išsaugoti`, {
      duration: 10_000,
      action: { label: 'Atšaukti', onClick: () => setMeasurements((prev) => prev.map((m) => (m.id === before.id ? { ...m, points: before.points } : m))) },
    });
  };
  const saveOutlineEdit = async () => {
    if (outlineEdit?.target === 'measure') {
      if (outlineInvalid) { toast.error('Plotas kertasi pats su savimi — pataisykite taškus prieš išsaugant'); return; }
      saveMeasureEdit();
      return;
    }
    if (!outlineEdit || !onRoomOutlineEdit) return;
    if (outlineInvalid) { toast.error('Kontūras kertasi pats su savimi — pataisykite viršūnes prieš išsaugant'); return; }
    setOutlineSaving(true);
    try {
      const saved = await onRoomOutlineEdit(outlineEdit.nr, outlineEdit.page, outlineEdit.points, outlineEdit.holes);
      // „Atšaukti" for 10 s (Pathon v3 W1-D): the host PUTs the room's previous geometry back.
      toast.success(`Patalpos ${outlineEdit.nr} kontūras išsaugotas — sienos perskaitytos iš naujo`, undoAction(saved));
      setOutlineEdit(null);
      setVertexMenu(null);
    } catch (e) {
      toast.error(e?.userMessage || e?.message || 'Nepavyko išsaugoti kontūro');
    } finally {
      setOutlineSaving(false);
    }
  };
  // Focus moving to another room abandons an unsaved outline edit (the editor is bound to the focused room) — a
  // measurement being edited is not the room's; a double-click that moved the focus starts its edit here (A1).
  const pendingEditRef = useRef(null);
  useEffect(() => {
    const pending = pendingEditRef.current;
    pendingEditRef.current = null;
    if (pending != null && focusedRoomNr != null && String(focusedRoomNr) === pending) { startOutlineEdit(pending); return; }
    setOutlineEdit((cur) => (cur?.target === 'measure' ? cur : null));
  }, [focusedRoomNr]); // eslint-disable-line react-hooks/exhaustive-deps
  // The selected corners (A3): Delete removes them (never below the shape's minimum), the arrows nudge them.
  const editPageRect = (page) => tvRootRef.current?.querySelector(`[data-page-number="${page}"]`)?.getBoundingClientRect() || null;
  const vertexActions = {
    deleteSelected: () => {
      const ed = outlineEdit;
      if (!ed?.selected?.length) return false;
      const res = deleteVertices(ed.points, ed.selected, ed.minPoints || 3);
      if (res.refused) { flashCursorHint(`Mažiau nei ${ed.minPoints || 3} kampų likti negali`); return true; }
      snapshotOutline();
      setOutlineEdit((cur) => (cur ? { ...cur, points: res.points, selected: [] } : cur));
      setVertexMenu(null);
      return true;
    },
    nudge: (dxPx, dyPx) => {
      const ed = outlineEdit;
      const r = ed?.selected?.length ? editPageRect(ed.page) : null;
      if (!r?.width || !r?.height) return false;
      snapshotOutline();
      setOutlineEdit((cur) => (cur ? { ...cur, points: nudgeVertices(cur.points, cur.selected, dxPx / r.width, dyPx / r.height) } : cur));
      return true;
    },
  };
  const vertexActionsRef = useRef(vertexActions);
  vertexActionsRef.current = vertexActions;
  // Keyboard while editing: Enter saves, Z undoes (Esc is a step of ViewerHotkeys' lib/escOrder: leaves without saving).
  const saveOutlineEditRef = useRef(saveOutlineEdit);
  useEffect(() => { saveOutlineEditRef.current = saveOutlineEdit; });
  useEffect(() => {
    if (!outlineEdit) return undefined;
    const onKey = (e) => {
      if (e.target?.closest?.('input, textarea, select, [contenteditable]')) return;
      if (e.key === 'Enter') { e.preventDefault(); saveOutlineEditRef.current?.(); }
      else if ((e.key === 'z' || e.key === 'Z') && !e.metaKey && !e.ctrlKey && !e.altKey) { e.preventDefault(); undoOutline(); }
      else if (e.key === 'Delete' || e.key === 'Backspace') { e.preventDefault(); vertexActionsRef.current?.deleteSelected(); }
      else if (e.key.startsWith('Arrow')) {
        // A3: the arrow keys nudge the selected corners one screen pixel (Shift = 10)
        const step = e.shiftKey ? 10 : 1;
        const d = { ArrowLeft: [-step, 0], ArrowRight: [step, 0], ArrowUp: [0, -step], ArrowDown: [0, step] }[e.key];
        if (d && vertexActionsRef.current?.nudge(d[0], d[1])) e.preventDefault();
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [!!outlineEdit]); // eslint-disable-line react-hooks/exhaustive-deps

  // Outline tools (2026-10-16): „Padalyti" / „Sujungti" / „Atimti" on the focused room's outline —
  // state in useOutlineTool, the page half in OutlineToolLayer, numbers and choices in OutlineToolPanel.
  const outlineTools = useOutlineTool({
    rooms,
    focusedRoom,
    onSave: onOutlineTool,
    onBeforeStart: () => { setMeasureTool(null); setSelectedMeasureId(null); setFillFor(null); setOutlineEdit(null); },
  });

  // ---- Measurement subsystem (Phase 3) ------------------------------------
  // Tool: null (idle) | 'select' | 'distance' | 'area' | 'count' | 'calibrate'.
  // Measurements + per-page scales in PDF-point space (see MeasureLayer);
  // hydrated from the project, persisted back via onMeasureDataChange.
  const [measureTool, setMeasureTool] = useState(null);
  // ---- The room tool R (Pathon v3 W1-D, D2) -------------------------------
  // Armed as the measure tool 'room' (one pointer owner at a time, the same Esc and tool switching); its
  // state, the requests and the save live in useRoomTool, the host (InteriorWorkspace) does the network.
  const roomToolArmed = measureTool === 'room' && !check && Boolean(onRoomToolPreview && onRoomToolCommit);
  const roomTool = useRoomTool({
    active: roomToolArmed,
    rooms,
    projectId,
    sutapdinimas: project?._meta?.geometrija?.sutapdinimas || null,
    onPreview: onRoomToolPreview,
    onCommit: onRoomToolCommit,
    // No vector walls on the sheet: the raster click-fill is the fallback, shown first like every proposal.
    onRasterPreview: onRoomPolygonFill ? async (nr, where) => {
      const data = await clickToFill({ projectId, pageNr: where.page, clickXPct: where.x_pct, clickYPct: where.y_pct, sensitivity: 0.7, pdfBlob });
      const pw = Number(data?.page_width_pdf);
      const ph = Number(data?.page_height_pdf);
      const ring = Array.isArray(data?.polygon_pdf) && pw > 0 && ph > 0 ? data.polygon_pdf.map(([x, y]) => [x / pw, y / ph]) : null;
      return ring && ring.length >= 3 ? { ring, data } : null;
    } : null,
    onRasterCommit: onRoomPolygonFill ? (nr, data) => onRoomPolygonFill(nr, data) : null,
    // The room he just outlined becomes the selected one, so he sees it (the drawing stays where it is).
    onCommitted: (nr) => applyRoomSelection({ focused: String(nr), extra: [] }),
  });
  // The room tool owns the pointer alone: an outline being edited or a split/merge/subtract in progress stands down.
  useEffect(() => {
    if (!roomToolArmed) return;
    setOutlineEdit(null);
    outlineTools.cancel();
  }, [roomToolArmed]); // eslint-disable-line react-hooks/exhaustive-deps
  // Committed measurements + count marks live in a history (lib/measureHistory, 2026-10-16): every
  // change goes through setMeasurements(update) and becomes one undoable entry in „Istorija".
  const [measureHist, dispatchMeasureHist] = useReducer(historyReducer, initialMeasurements || [], initHistory);
  const measurements = measureHist.present;
  const [measureScales, setMeasureScales] = useState(() => initialMeasureScales || {});
  // Auto-calibration: pages whose traced rooms carry eksplikacija areas get a
  // derived meters-per-point — measurements read real meters with no manual
  // step. A user calibration (measureScales) always wins the merge.
  const autoScales = useMemo(() => autoPageScalesFromRooms(rooms), [rooms]);
  const effectiveScales = useMemo(
    () => mergePageScales(autoScales, laneScales || {}, measureScales),
    [autoScales, laneScales, measureScales]);
  // „Masteliai" (Togal-v2 W6): every sheet's scale, confirm a guessed one, check it against a known length.
  const [scalesOpen, setScalesOpen] = useState(false);
  // The last „Patikrinti mastelį" readout: {page, readout} | null. Nothing is saved.
  const [scaleCheck, setScaleCheck] = useState(null);
  // „Nustatyti mastelį“ next to the detection button (W5-B B7, #25): the scale chip's card opens (a nonce per click).
  const [scaleChipOpen, setScaleChipOpen] = useState(0);
  // W5-B B8: a typed or picked 1:N becomes his scale for the sheet; „nereikia" marks a schedule or specification.
  // Both are one undoable change (the toast's „Atšaukti" puts the sheet's previous entry back).
  const putSheetScale = (page, entry, message) => {
    const before = measureScales[page] ?? measureScales[String(page)] ?? null;
    const set = (value) => setMeasureScales((prev) => {
      const next = { ...prev };
      delete next[String(page)];
      if (value) next[page] = value; else delete next[page];
      return next;
    });
    set(entry);
    toast.success(message, { duration: 10_000, action: { label: 'Atšaukti', onClick: () => set(before) } });
  };
  const setSheetRatio = (page, ratio) => putSheetScale(page, scaleForRatio(ratio), `Lapo ${page} mastelis 1:${String(ratio).replace('.', ',')} — jūsų`);
  const setSheetNotNeeded = (page, on) => putSheetScale(page, on ? notNeededEntry() : null,
    on ? `Lapui ${page} mastelio nereikia — programa jo nebeklaus` : `Lapui ${page} mastelis vėl reikalingas`);
  const sheetNotNeeded = (page) => isNotNeeded(measureScales[page] ?? measureScales[String(page)]);
  const confirmScales = (pages) => {
    setMeasureScales((prev) => confirmLaneScales(prev, pages, laneScales || {}));
    toast.success(pages.length > 1 ? `Patvirtinta ${pages.length} lapų mastelis` : `Patvirtintas ${pages[0]} lapo mastelis`, {
      description: 'Mastelis dabar jūsų. Jei perskaičius brėžinį iš naujo matmenys rodys kitą, „Masteliai" tai parodys.',
    });
  };
  // Toolbar toggles removed 2026-07-14 (founder: confusing). Snap stays ON —
  // it only pulls to existing measurement endpoints; ortho off.
  const snapEnabled = true;
  const orthoEnabled = false;
  // User-defined count types (persisted with the measurements). Projects saved
  // before custom types existed hydrate their list from the marks themselves.
  const [countTypes, setCountTypes] = useState(() => (
    initialCountTypes?.length ? initialCountTypes : countTypesFromMeasurements(initialMeasurements || [])
  ));
  const [activeCountTypeId, setActiveCountTypeId] = useState(() => countTypes[0]?.id ?? null);
  // History labels read the latest scales and type names through a ref — the reducer stays pure.
  const describeCtxRef = useRef(null);
  describeCtxRef.current = {
    countTypeLabel: (id) => countTypes.find((t) => t.id === id)?.label || null,
    formatValue: (m) => {
      const sc = effectiveScales[m.page];
      if (!sc?.calibrated || m.kind === 'count') return null;
      const v = measurementValue(m, sc).value;
      return `${v.toLocaleString('lt-LT', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} ${m.kind === 'area' ? 'm²' : 'm'}`;
    },
  };
  const setMeasurements = useCallback((update) => dispatchMeasureHist({
    type: 'apply',
    update,
    describe: (before, after) => describeChange(before, after, describeCtxRef.current),
    at: Date.now(),
  }), []);
  const [historyOpen, setHistoryOpen] = useState(false);
  const tvRootRef = useRef(null);
  const [guideOpen, setGuideOpen] = useState(false);
  // Right-click on a committed mark: { id, clientX, clientY } | null (MeasureContextMenu).
  const [measureMenu, setMeasureMenu] = useState(null);
  // How Plotas / Perimetras draw (W5-A A11): 'free' | 'rect' | 'arc' — chosen in the pill.
  const [drawShape, setDrawShape] = useState('free');
  // What the pointer snaps to right now (W5-A A6) — the status line names it.
  const [snapKind, setSnapKind] = useState(null);
  const menuMeasurement = measureMenu ? measurements.find((m) => m.id === measureMenu.id) || null : null;
  const renameMeasurement = (id, name) => setMeasurements((prev) => prev.map((m) => {
    if (m.id !== id) return m;
    const next = { ...m };
    if (name) next.name = name; else delete next.name;
    return next;
  }));
  const changeCountType = (id, typeId) => {
    const t = countTypes.find((x) => x.id === typeId);
    setMeasurements((prev) => prev.map((m) => (m.id === id ? { ...m, typeId, color: t?.color || m.color } : m)));
  };
  // „Rodyti sąraše": the Matavimai list (WorkspacePanel) opens its section and scrolls to the row.
  const revealMeasurement = (m) => {
    window.dispatchEvent(new CustomEvent('samatu:measure-reveal', { detail: { id: m.id, kind: m.kind, typeId: m.typeId ?? null } }));
  };
  // Global undo / redo. A drawing in progress or an outline being edited owns the step first — the
  // same thing plain Z does there — so Ctrl+Z never jumps over the work under the cursor.
  const undoMeasure = () => {
    if (outlineEdit) { undoOutline(); return; }
    if (outlineTools.tool) { outlineTools.undo(); return; }
    if (draftPoints > 0) { dispatchDraft(draftSlot.pageNr, { type: 'undo' }); return; }
    const last = measureHist.past[measureHist.past.length - 1];
    if (!last) { toast.info('Nėra ką atšaukti'); return; }
    dispatchMeasureHist({ type: 'undo' });
    toast(`Atšaukta: ${last.label}`, { description: `${keyText('redo')} — grąžinti` });
  };
  const redoMeasure = () => {
    if (outlineEdit || outlineTools.tool || draftPoints > 0) return;
    const next = measureHist.future[measureHist.future.length - 1];
    if (!next) { toast.info('Nėra ką grąžinti'); return; }
    dispatchMeasureHist({ type: 'redo' });
    toast(`Grąžinta: ${next.label}`);
  };
  const addCountType = (label, shape = null) => {
    const t = makeCountType(label, countTypes, shape ? { shape } : {});
    setCountTypes((prev) => [...prev, t]);
    setActiveCountTypeId(t.id);
  };
  // The count-type picker beside the pointer (W5-A A7): {x, y} | null — opens when the count tool is armed and on
  // a right-click while it is; the last pointer position inside the viewer says where.
  const [countPicker, setCountPicker] = useState(null);
  const lastPointerRef = useRef(null);
  useEffect(() => {
    const el = tvRootRef.current;
    if (!el) return undefined;
    const onMove = (e) => { lastPointerRef.current = { x: e.clientX, y: e.clientY }; };
    el.addEventListener('pointermove', onMove, { passive: true });
    return () => el.removeEventListener('pointermove', onMove);
  });
  const openCountPicker = () => {
    const r = tvRootRef.current?.getBoundingClientRect();
    setCountPicker(lastPointerRef.current || (r ? { x: r.left + r.width / 2, y: r.top + r.height / 3 } : { x: 400, y: 300 }));
  };
  const removeCountType = (typeId) => {
    setCountTypes((prev) => prev.filter((t) => t.id !== typeId));
    setActiveCountTypeId((cur) => (cur === typeId ? (countTypes.find((t) => t.id !== typeId)?.id ?? null) : cur));
  };
  // „Rasti panašius" (2026-10-16): one box-search session; its marks join the count tool's.
  const symbol = useSymbolSearch({
    projectId,
    countTypes,
    onAdd: (marks, createdType) => {
      if (createdType) setCountTypes((prev) => [...prev, createdType]);
      setMeasurements((prev) => [...prev, ...marks]);
      if (marks[0]?.typeId) setActiveCountTypeId(marks[0].typeId);
    },
  });
  // „Pažymėti legendą" (Pathon v3 W2-B): the legend's rows counted and reviewed — NOTHING exists before „Sukurti
  // kiekius"; that click lands here as one history entry, with „Atšaukti" in its toast (types, marks, saved legend).
  const legendMeasRef = useRef(measurements);
  legendMeasRef.current = measurements;
  const legendTypesRef = useRef(countTypes);
  legendTypesRef.current = countTypes;
  const docPagesRef = useRef(null);
  const visiblePageRef = useRef(1);
  const legendGotoRef = useRef(null);
  const createFromLegend = (plan, { label, undoLegend } = {}) => {
    const beforeM = legendMeasRef.current || [];
    const beforeT = legendTypesRef.current || [];
    const next = applyCreate(beforeM, beforeT, plan);
    const added = new Set(plan.marks.map((m) => m.id));
    const kept = new Set(next.measurements);
    const gone = beforeM.filter((m) => !kept.has(m));
    const newTypeIds = new Set(plan.types.map((t) => t.id));
    const oldTypes = new Map(beforeT.map((t) => [t.id, t]));
    setCountTypes(next.countTypes);
    dispatchMeasureHist({ type: 'apply', update: next.measurements, label, at: Date.now() });
    // kept rows the drawing shows no mark of: blank sąmata rows with the question (the host writes them)
    const undoBlanks = plan.blanks?.length && onLegendBlankRows ? onLegendBlankRows(plan.blanks) : null;
    if (plan.made[0]?.type?.id) setActiveCountTypeId(plan.made[0].type.id);
    const undo = () => {
      setMeasurements((prev) => [...prev.filter((m) => !added.has(m.id)), ...gone]);
      setCountTypes((prev) => prev.filter((t) => !newTypeIds.has(t.id)).map((t) => oldTypes.get(t.id) || t));
      undoLegend?.();
      if (typeof undoBlanks === 'function') undoBlanks();
      toast('Atšaukta: kiekiai pagal legendą pašalinti');
    };
    toast.success(`Sukurta pagal legendą: ${plan.made.length} kiek., ${plan.marks.length} žym. brėžinyje`, {
      description: `Žymės tuščiavidurės — rastos automatiškai. Sąmatos eilutės skaičiuojasi pačios (skyrius „Matavimai").${plan.blanks?.length ? ` ${plan.blanks.length} eil. be ženklų sąmatoje tuščios — suskaičiuokite „Kiekis“ įrankiu.` : ''}`,
      duration: 10_000,
      action: { label: 'Atšaukti', onClick: undo },
    });
  };
  const legend = useLegendTool({ projectId, countTypes, pagesRef: docPagesRef, onCreate: createFromLegend });
  // The host opens its right panel for the review while the tool is on (InteriorWorkspace → RightPanelHost `cover`).
  const onLegendPanelChangeRef = useRef(onLegendPanelChange);
  onLegendPanelChangeRef.current = onLegendPanelChange;
  useEffect(() => { onLegendPanelChangeRef.current?.(legend.active); }, [legend.active]);
  useEffect(() => () => { onLegendPanelChangeRef.current?.(false); }, []);
  // Enter: „Taip" on the proposed legend, „Sukurti kiekius" in the review (design §5) — never while typing.
  const legendKeyRef = useRef(null);
  legendKeyRef.current = legend;
  useEffect(() => {
    if (!legend.active || !active) return undefined;
    const onKey = (e) => {
      if (e.key !== 'Enter' || e.target?.closest?.('input, textarea, select, [contenteditable], button')) return;
      const l = legendKeyRef.current;
      if (l.phase === 'proposed') { e.preventDefault(); l.accept(); }
      else if (l.phase === 'review' && (l.toCreate.length || l.blanks.length)) { e.preventDefault(); l.create(); }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [legend.active, active]);
  // Copy / paste / duplicate his measurements (W5-A A11 [#102]): Ctrl+C keeps the selected ones, Ctrl+V lays copies
  // on the sheet on screen (same place on the sheet; a hair aside on the sheet they came from), Ctrl+D copies them
  // beside themselves. One „Istorija" entry each, „Atšaukti" in the toast; a copy keeps no sąmata row link.
  const clipboardRef = useRef(null);
  const PASTE_OFFSET_PT = 12;
  const placeCopies = (copies, what) => {
    const ids = new Set(copies.map((c) => c.id));
    setMeasurements((prev) => [...prev, ...copies]);
    if (measureTool === 'select' || measureTool === 'lasso') setSelectedMeasureIds([...ids]);
    toast.success(what, { duration: 10_000, action: { label: 'Atšaukti', onClick: () => setMeasurements((prev) => prev.filter((m) => !ids.has(m.id))) } });
  };
  const copyMarks = () => {
    const marks = measurements.filter((m) => selectedMeasureIds.includes(m.id));
    if (!marks.length) return false;
    clipboardRef.current = marks;
    toast(`Nukopijuota: ${marks.length} — Ctrl+V įklijuoja matomame lape`);
    return true;
  };
  const pasteMarks = (page) => {
    const marks = clipboardRef.current;
    if (!marks?.length || !page) return false;
    const d = marks.some((m) => m.page === page) ? PASTE_OFFSET_PT : 0;
    placeCopies(marks.map((m) => copyMeasurement(m, { page, dx: d, dy: d, id: newMeasurementId() })), `Įklijuota ${marks.length} į ${page} lapą`);
    return true;
  };
  const duplicateMarks = () => {
    const marks = measurements.filter((m) => selectedMeasureIds.includes(m.id));
    if (!marks.length) return false;
    placeCopies(marks.map((m) => copyMeasurement(m, { dx: PASTE_OFFSET_PT, dy: PASTE_OFFSET_PT, id: newMeasurementId() })), `Padvigubinta: ${marks.length}`);
    return true;
  };
  // „Rasti panašius" from a count mark (W5-A A8 [#218]): the template box is the mark's own (a found mark keeps the
  // box it was found by) or a symbol-sized box round it; the found marks join the mark's type, so the type's row
  // link (W4-A `type:<id>` / a legend row's `eilute_id`) counts them on the same sąmata row.
  const findSimilarFrom = (m) => {
    const p = m?.points?.[0];
    if (!p) return;
    const box = Array.isArray(m.box) && m.box.length === 4 ? m.box : [p.x - 16, p.y - 16, p.x + 16, p.y + 16];
    setMeasureTool(null); setSelectedMeasureId(null); setFillFor(null); setOutlineEdit(null);
    symbol.openWith({ page: m.page, box, typeId: m.typeId || null });
  };
  // Floating count legend collapse — it swallows placement clicks underneath.
  const [countLegendCollapsed, setCountLegendCollapsed] = useState(false);
  // The selection: one mark („Žymėti") or several („Laso", 2026-10-16) — ONE list either way.
  const [selectedMeasureIds, setSelectedMeasureIds] = useState([]);
  const setSelectedMeasureId = useCallback((id) => setSelectedMeasureIds(id == null ? [] : (Array.isArray(id) ? id : [id])), []);
  // Right-click inside a multi-mark selection (or beside it with „Laso" armed) acts on the whole selection.
  const menuSelection = measureMenu && selectedMeasureIds.length > 1
    && (measureMenu.id == null || selectedMeasureIds.includes(measureMenu.id))
    ? measurements.filter((m) => selectedMeasureIds.includes(m.id)) : null;
  // Pending 2-point calibration pick: { pageNr, a, b, rotation } | null → CalibrateDialog.
  const [calibRequest, setCalibRequest] = useState(null);

  // ---- Draft ownership (audit P1) -----------------------------------------
  // The in-progress measurement and the first calibration click live HERE, not
  // in MeasureLayer: pages unmount when they leave the scroll virtualization
  // buffer (±2 pages), which used to destroy the drawing the user was in the
  // middle of. Exactly one draft exists at a time, so one {pageNr, draft} slot
  // is enough; MeasureLayer is controlled for both pieces and keeps its reducer.
  const [draftSlot, setDraftSlot] = useState({ pageNr: null, draft: EMPTY_DRAFT });
  const [calibSlot, setCalibSlot] = useState({ pageNr: null, point: null });
  const dispatchDraft = useCallback((pageNr, action) => {
    setDraftSlot((cur) => {
      const base = cur.pageNr === pageNr ? cur.draft : EMPTY_DRAFT;
      const next = draftReducer(base, action);
      return { pageNr: next.points.length ? pageNr : null, draft: next };
    });
  }, []);
  const draftPoints = draftSlot.draft.points.length;
  // A tool change always abandons the draft (MeasureLayer used to do this per
  // page; with the state lifted the owner must).
  useEffect(() => {
    setDraftSlot({ pageNr: null, draft: EMPTY_DRAFT });
    setCalibSlot({ pageNr: null, point: null });
  }, [measureTool]);

  // Fill-mode and measure tools are mutually exclusive pointer owners.
  const armMeasureTool = (tool) => {
    // Toggling the ACTIVE tool off mid-draft silently threw the drawing away
    // (audit P2) — keep it armed and point at the on-canvas exits instead.
    // Esc still cancels through the existing chain.
    if (measureTool === tool && draftPoints > 0) {
      toast.info('Pirmiausia užbaikite arba atšaukite braižomą matavimą (Baigti / Atšaukti)');
      return;
    }
    setFillFor(null);
    if (symbol.active) symbol.close();
    if (legend.active) legend.close();
    // Arming the count tool with no types yet would be a silent no-op (clicks
    // do nothing without an active type) — make the "Sukurkite tipą" hint
    // visible even if the legend was left collapsed.
    if (tool === 'count' && countTypes.length === 0) setCountLegendCollapsed(false);
    if (tool === 'count' && measureTool !== 'count') openCountPicker();
    else setCountPicker(null);
    setMeasureTool((cur) => {
      const next = cur === tool ? null : tool;
      if (next == null) setSelectedMeasureId(null);
      return next;
    });
  };
  const startFill = (nr) => { setMeasureTool(null); setSelectedMeasureId(null); if (symbol.active) symbol.close(); if (legend.active) legend.close(); setFillFor(nr); };
  // „Rasti panašius" owns the pointer alone: every other tool steps aside, and they close it in turn.
  const toggleSymbolSearch = () => {
    if (symbol.active) { symbol.close(); return; }
    setMeasureTool(null); setSelectedMeasureId(null); setFillFor(null); setOutlineEdit(null);
    if (legend.active) legend.close();
    symbol.open();
  };
  // „Pažymėti legendą" owns the pointer alone too: G again (or Esc) leaves it, nothing created.
  const toggleLegend = () => {
    if (legend.active) { legend.close(); return; }
    // B1-B: G in the middle of a drawing used to throw the drawing away without a word — say so instead
    if (draftPoints > 0 || outlineEdit?.history?.length || outlineTools.tool?.history?.length) {
      flashCursorHint('Pirmiausia užbaikite arba atšaukite braižomą (Enter / Esc), tada G — legenda');
      return;
    }
    setMeasureTool(null); setSelectedMeasureId(null); setFillFor(null); setOutlineEdit(null); outlineTools.cancel();
    if (symbol.active) symbol.close();
    legend.open(visiblePageRef.current || 1);
  };
  // External fill arming (review-queue pencil → „Kontūras paspaudus" armed here).
  // {nr, t} — t is a nonce so re-clicking the same room re-arms after Esc.
  useEffect(() => {
    if (fillRequest?.nr != null) startFill(fillRequest.nr);
  }, [fillRequest]);
  const deleteMeasurement = (idOrIds) => {
    const gone = new Set((Array.isArray(idOrIds) ? idOrIds : [idOrIds]).filter((x) => x != null));
    if (!gone.size) return;
    setMeasurements((prev) => prev.filter((m) => !gone.has(m.id)));
    setSelectedMeasureIds((cur) => cur.filter((x) => !gone.has(x)));
  };
  // A delete he chose (selection bar, Delete key, right-click menu) says what went and offers „Atšaukti" — the
  // undo, never a question (W5-B B6; Rimas §1.5). The count tool's one-click removal stays silent.
  const deleteMeasurementWithUndo = (idOrIds) => {
    const ids = new Set((Array.isArray(idOrIds) ? idOrIds : [idOrIds]).filter((x) => x != null));
    const removed = measurements.filter((m) => ids.has(m.id));
    if (!removed.length) return;
    deleteMeasurement([...ids]);
    toast(removed.length === 1 ? 'Matavimas ištrintas' : `Ištrinta matavimų: ${removed.length}`, {
      duration: 10_000,
      action: {
        label: 'Atšaukti',
        onClick: () => setMeasurements((prev) => [...prev, ...removed.filter((m) => !prev.some((x) => x.id === m.id))]),
      },
    });
  };
  // Batch actions on a lasso selection (one history entry each).
  const changeCountTypeMany = (ids, typeId) => {
    const t = countTypes.find((x) => x.id === typeId);
    const set = new Set(ids);
    setMeasurements((prev) => prev.map((m) => (set.has(m.id) && m.kind === 'count' && m.typeId !== typeId
      ? { ...m, typeId, color: t?.color || m.color } : m)));
  };
  const recolorMany = (ids, color) => {
    const set = new Set(ids);
    setMeasurements((prev) => prev.map((m) => (set.has(m.id) && m.kind !== 'count' && m.color !== color ? { ...m, color } : m)));
  };
  // ---- Text search (Task 4.1) ----------------------------------------------
  // Open/closed only — query + results live in SearchBox (its unmount ends the
  // plugin search session, clearing highlights).
  const [searchOpen, setSearchOpen] = useState(false);
  // The project workspace lends this one viewer to Patikra's check view and takes it back (Pathon v3,
  // InteriorWorkspace): when `check` arrives every tool stands down, so a click on the sheet reaches the
  // check's own pick and nothing else. (A viewer born in check mode has nothing armed — a no-op there.)
  const inCheck = !!check;
  useEffect(() => {
    if (!inCheck) return;
    setMeasureTool(null);
    setSelectedMeasureIds([]);
    setFillFor(null);
    setOutlineEdit(null);
    outlineTools.cancel();
    if (symbol.active) symbol.close();
    if (legend.active) legend.close();
  }, [inCheck]); // eslint-disable-line react-hooks/exhaustive-deps
  // A finished measurement (MeasureLayer, or the pill's „Baigti"): one history entry, and the value said aloud.
  const commitMeasurement = (m) => {
    setMeasurements((prev) => [...prev, m]);
    // Founder 2026-07-25 ("no way to get measurements"):
    // announce the committed value + where it lives. (A „Pastaba" pin announces itself — W5-C C11.)
    if (m.kind !== 'count' && m.kind !== 'note') {
      const sc = effectiveScales[m.page];
      const unit = m.kind === 'area' ? 'm²' : 'm';
      const label = sc?.calibrated
        ? `${measurementValue(m, sc).value.toLocaleString('lt-LT', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} ${unit}`
        : 'nekalibruota';
      const KIND_LT = { distance: 'Atstumas', perimeter: 'Perimetras', area: 'Plotas' };
      toast.success(`${KIND_LT[m.kind] || 'Matavimas'}: ${label}`, {
        description: 'Įrašyta dešinės pusės skydelyje „Matavimai".',
      });
    }
  };
  const countTallies = useMemo(() => measurements.reduce((acc, m) => {
    if (m.kind === 'count' && m.typeId) acc[m.typeId] = (acc[m.typeId] || 0) + 1;
    return acc;
  }, {}), [measurements]);
  // Persist measurement data to the parent (project save flow), DEBOUNCED, and
  // skipping the mount pass so hydration never writes back immediately. The
  // callback lives in a ref: the parent recreates it on every render (each save
  // triggers onProjectChange → re-render), and depending on its identity would
  // re-schedule saves of identical data forever.
  const onMeasureDataChangeRef = useRef(onMeasureDataChange);
  useEffect(() => { onMeasureDataChangeRef.current = onMeasureDataChange; });
  const measureDirtyRef = useRef(false);
  // Latest unsaved payload — flushed on unmount so switching views inside the
  // 600 ms debounce window can no longer DROP the last measurement (P0-2).
  const pendingMeasureSaveRef = useRef(null);
  useEffect(() => {
    if (!measureDirtyRef.current) { measureDirtyRef.current = true; return undefined; } // skip mount
    pendingMeasureSaveRef.current = { measurements, measureScales, countTypes };
    const t = setTimeout(() => {
      pendingMeasureSaveRef.current = null;
      onMeasureDataChangeRef.current?.({ measurements, measureScales, countTypes });
    }, 600);
    return () => clearTimeout(t);
  }, [measurements, measureScales, countTypes]);
  // Flush the pending payload synchronously. onMeasureDataChange writes through
  // to localStorage synchronously (the backend PUT is fire-and-forget), so a
  // plain call is enough — no sendBeacon needed.
  const flushMeasureSave = useCallback(() => {
    if (!pendingMeasureSaveRef.current) return;
    const payload = pendingMeasureSaveRef.current;
    pendingMeasureSaveRef.current = null;
    onMeasureDataChangeRef.current?.(payload);
  }, []);
  useEffect(() => () => flushMeasureSave(), [flushMeasureSave]);
  // Closing / reloading the tab inside the 600 ms debounce window dropped the
  // last measurement (audit P2) — unmount was the only flush point.
  useEffect(() => {
    window.addEventListener('beforeunload', flushMeasureSave);
    return () => window.removeEventListener('beforeunload', flushMeasureSave);
  }, [flushMeasureSave]);
  // Thumbnail rail preference: null = "no explicit choice yet" → default OPEN
  // when the document has more than one page (resolved where pageCount is known).
  const [thumbsPref, setThumbsPref] = useState(() => {
    try {
      const v = localStorage.getItem('samatu_viewer_thumbs');
      return v == null ? null : v === '1';
    } catch { return null; }
  });
  const setRailOpen = (next) => {
    try { localStorage.setItem('samatu_viewer_thumbs', next ? '1' : '0'); } catch { /* private mode */ }
    setThumbsPref(next);
  };
  // A sheet set (SheetRail) opens on its 56 px strip; the full rail is „Lapai" or T (Pathon v3 frame, A4).
  const [sheetRailFull, setSheetRailFullState] = useState(() => readSheetRailFull(browserStorage()));
  const setSheetRailFull = (next) => {
    writeSheetRailFull(browserStorage(), next);
    setSheetRailFullState(next);
  };

  // Download the ORIGINAL source PDF blob directly (pre-prod QA 2026-07-15:
  // EmbedPDF's exportApi.download() → pdfium saveAsCopy() silently no-ops on a
  // cold context ~1/3 of the time — a dead toolbar button in a demo). The
  // viewer never bakes edits into the PDF (measurements are an SVG overlay), so
  // the source blob IS the correct download — instant, reliable, no pdfium. A
  // toast guarantees the click is never silent.
  const handleDownload = pdfBlob ? () => {
    try {
      const url = URL.createObjectURL(pdfBlob);
      const a = document.createElement('a');
      a.href = url;
      a.download = exportFileName || 'brezinys.pdf';
      document.body.appendChild(a);
      a.click();
      a.remove();
      setTimeout(() => URL.revokeObjectURL(url), 4000);
      toast.success('Brėžinys atsisiunčiamas');
    } catch (e) {
      console.warn('[download] failed:', e?.message);
      toast.error('Nepavyko atsisiųsti brėžinio.');
    }
  } : null;

  // A wall face clicked with the walls layer on (W5-A A12 [#116]): the face's two ends (the wall solid the layer
  // draws, api/page_geometry) become a distance measurement — his, in „Matavimai", with „Atšaukti".
  const WALL_FACE_PX = 6;
  const measureWallFace = async (pt) => {
    const where = displayPointOf(pt);
    if (!where || !(pt.renderedWidth > 0) || !(pt.renderedHeight > 0)) return false;
    let geometry = null;
    try { geometry = await fetchPageGeometry(projectId, where.page); } catch { return false; }
    const W = pt.renderedWidth; const H = pt.renderedHeight;
    const rings = (Array.isArray(geometry?.walls_pct) ? geometry.walls_pct : []).map((r) => r.map(([x, y]) => ({ x: x * W, y: y * H })));
    const face = wallFaceAt(rings, { x: where.x_pct * W, y: where.y_pct * H }, WALL_FACE_PX);
    if (!face) return false;
    const points = pctToPoints([[face.a.x / W, face.a.y / H], [face.b.x / W, face.b.y / H]],
      { width: pt.pageWidth, height: pt.pageHeight, rotation: pt.pageRotation ?? 0 });
    const m = makeMeasurement('distance', where.page, points, { name: 'Siena' });
    setMeasurements((prev) => [...prev, m]);
    const sc = effectiveScales[where.page];
    const text = sc?.calibrated ? `${measurementValue(m, sc).value.toLocaleString('lt-LT', { minimumFractionDigits: 2, maximumFractionDigits: 2 })} m` : 'lapo mastelis nenustatytas';
    toast.success(`Sienos ilgis: ${text}`, {
      description: 'Įrašyta dešinės pusės skydelyje „Matavimai".',
      duration: 10_000,
      action: { label: 'Atšaukti', onClick: () => setMeasurements((prev) => prev.filter((x) => x.id !== m.id)) },
    });
    return true;
  };

  // „Žymėti" box selection (W5-A A5): the marks the box took, and the rooms — left→right whole ones, right→left
  // touched ones; Shift adds to what is selected. The click the browser sends after the drag is not a room click.
  const boxEndedRef = useRef(0);
  const handleBoxSelect = ({ ids, a, b, mode, add, pageNr }) => {
    boxEndedRef.current = Date.now();
    setSelectedMeasureIds((cur) => (add ? [...new Set([...cur, ...ids])] : ids));
    const pg = pageSizeOf(pageNr);
    if (!pg?.size) return;
    const rot = displayRotationFor(pg.rotation ?? 0);
    const A = rotatePctPoint(a.x / pg.size.width, a.y / pg.size.height, rot);
    const B = rotatePctPoint(b.x / pg.size.width, b.y / pg.size.height, rot);
    const nrs = roomsInBox(rooms, pageNr, A, B, mode, hiddenRoomNrs);
    if (add) {
      const all = [...new Set([...(focusedRoomNr != null ? [String(focusedRoomNr)] : []), ...extraRoomNrs.map(String), ...nrs])];
      applyRoomSelection({ focused: all[0] ?? null, extra: all.slice(1) });
    } else {
      applyRoomSelection({ focused: nrs[0] ?? null, extra: nrs.slice(1) });
    }
  };

  const handlePagePoint = async (pt) => {
    if (symbol.active) return;   // the box search owns the pointer (SymbolSearchLayer)
    if (Date.now() - boxEndedRef.current < 400) return;   // the click that ends a selection box (A5)
    if (legend.active) return;   // so does the legend tool (LegendLayer)
    if (roomToolArmed) { roomTool.click(pt); return; }   // the room tool R (Pathon v3 W1-D)
    if (fillFor == null) {
      // Plain canvas click (no fill, no measure tool) — Pathon v3 W1-D: the room under the click is SELECTED
      // (Shift adds or removes one), empty paper clears the selection (the audit P2 sticky-chip rule still
      // holds: a room stays selected only while he means it); the click is forwarded to any external
      // consumer. „Žymėti" selects rooms too, unless the click is on one of his measurements (MeasureLayer
      // selects that one). While another measure tool owns the pointer, leave focus alone. Same while an
      // outline is being edited: a drag that starts a hair off a vertex must not drop the focus (which would
      // abandon the edit, 2026-10-16). The check view lent to Patikra keeps its own click: clear, then the pick.
      if (!outlineEdit && !outlineTools.tool && (measureTool == null || measureTool === 'select')) {
        if (check) {
          if (measureTool == null) onClearFocus?.();
        } else {
          const tol = MEASURE_HIT_TOL_PX / (Number(pt.scale) > 0 ? Number(pt.scale) : 1);
          const onMark = measureTool === 'select' && hitTestMeasurement({ x: pt.x, y: pt.y }, measurements, pt.pageIndex + 1, tol);
          // an opening on the walls layer (W5-A A9): its pop-up, not a room click
          const where = !onMark && wallsLayerVisible && onRoomOpenings ? displayPointOf(pt) : null;
          const opening = where ? openingAt(rooms, where.page, [where.x_pct, where.y_pct], {
            w: pt.renderedWidth, h: pt.renderedHeight, preferNr: focusedRoomNr,
          }) : null;
          if (opening) {
            const room = (rooms || []).find((r) => String(r?.nr) === opening.nr);
            setOpeningEdit({ o: opening, nr: opening.nr, state: openingState(room, opening), x: pt.clientX ?? 400, y: pt.clientY ?? 300 });
            return;
          }
          // a wall face on the walls layer (W5-A A12): its length becomes a distance measurement
          if (!onMark && wallsLayerVisible && projectId && await measureWallFace(pt)) return;
          if (!onMark) selectRoomAt(pt);
        }
        if (measureTool == null) onPagePoint?.(pt);
      }
      return;
    }
    const { x, y, pageIndex, pageWidth, pageHeight, pageRotation } = pt;
    if (!pageWidth || !pageHeight) { setFillFor(null); return; }
    // COORDINATE CONTRACT (see PageClicks in PageOverlayHost): x/y arrive in
    // UNROTATED mediabox PDF points — EmbedPDF's PagePointerProvider already
    // un-rotated the display click by the page's /Rotate and divided by zoom
    // scale. pageWidth/pageHeight are the mediabox size in POINTS. The
    // click-to-fill backend rasters pages via pdf2image (poppler APPLIES
    // /Rotate — the same rotation-applied space the stored room pct live in),
    // so forward-rotate the mediabox pct into display space for the seed.
    // Zoom-independent by construction (points, not CSS px).
    const rot = displayRotationFor(pageRotation ?? 0);
    const [mx, my] = rotatePctPoint(x / pageWidth, y / pageHeight, rot);
    if (fillBusy) return;   // one request at a time
    setFillBusy(true);
    try {
      const data = await clickToFill({
        projectId,
        pageNr: pageIndex + 1,
        clickXPct: mx,
        clickYPct: my,
        sensitivity: 0.7,
        pdfBlob,
      });
      const saved = onRoomPolygonFill?.(fillFor, data);
      // The AREA stays table-read (eksplikacija beats a traced polygon for
      // accuracy) — say so, or redrawing "because the area looked wrong"
      // reads as a silent no-op. (final-regression finding 2, 2026-07-28)
      toast.success(`Patalpos ${fillFor} kontūras pažymėtas`, {
        description: 'Plotas ir kiekiai lieka iš eksplikacijos — kontūro pataisymas naudojamas žymėjimui ir tikslumo mokymui.',
        ...undoAction(saved),
      });
      setFillFor(null);
    } catch (e) {
      // Audit P0 (2026-07-12): failure used to be console-only + silent disarm
      // — the user concluded the feature is broken. Surface a human message
      // and KEEP fill mode armed so they can try another spot right away.
      console.warn('[click-to-fill] failed:', e?.message);
      toast.error(
        `Nepavyko automatiškai apvesti patalpos ${fillFor} šioje vietoje.`,
        { description: 'Spustelėkite kitą tašką patalpos viduje arba pažymėkite kontūrą ranka (Esc — atšaukti).' },
      );
    } finally {
      setFillBusy(false);
    }
  };

  // Double-click (Pathon v3 W5-A A1, design §5 Select: „room → edit outline; measurement → edit"): at rest or
  // with „Žymėti". The two clicks before it already selected the room; a room the focus has not reached yet
  // starts its edit once it has (pendingEditRef).
  const handlePageDoubleClick = (pt) => {
    if (check || outlineEdit || outlineTools.tool || symbol.active || fillFor != null) return;
    if (!(measureTool == null || measureTool === 'select')) return;
    if (pt.measureId) { startMeasureEdit(pt.measureId); return; }
    if (!onRoomOutlineEdit) return;
    const where = displayPointOf(pt);
    const hit = where ? roomAtPoint(rooms, where, { renderedWidth: pt.renderedWidth, renderedHeight: pt.renderedHeight, hidden: hiddenRoomNrs }) : null;
    if (!hit) return;
    if (focusedRoomNr != null && String(focusedRoomNr) === hit.nr) { startOutlineEdit(hit.nr); return; }
    pendingEditRef.current = hit.nr;
    applyRoomSelection({ focused: hit.nr, extra: [] });
  };

  // Damp DISCRETE mouse-wheel ctrl+zoom (pre-prod QA P2: EmbedPDF's gesture
  // handler applies factor = 1 − deltaY·0.01, i.e. ≈2.2× per 120-unit notch —
  // three notches overshoot 10×). Document-level CAPTURE listener (the viewer
  // root div mounts only after the document loads, so a ref-scoped listener
  // attached on mount misses it): swallow big-delta ctrl-wheel events inside
  // the viewer and re-dispatch a 0.125× clone (≈1.16×/notch), marked so we
  // don't re-intercept it. Small-delta trackpad streams pass through untouched.
  useEffect(() => {
    const onWheel = (e) => {
      if (!(e.ctrlKey || e.metaKey) || e.__pathonDamped) return;
      if (Math.abs(e.deltaY) < 60) return; // trackpad: already smooth
      if (!e.target?.closest?.('[data-tv-root]')) return;
      e.preventDefault();
      e.stopImmediatePropagation();
      const clone = new WheelEvent('wheel', {
        bubbles: true, cancelable: true, view: window,
        clientX: e.clientX, clientY: e.clientY,
        ctrlKey: e.ctrlKey, metaKey: e.metaKey,
        deltaX: e.deltaX, deltaY: e.deltaY * 0.125, deltaMode: e.deltaMode,
      });
      clone.__pathonDamped = true;
      e.target.dispatchEvent(clone);
    };
    document.addEventListener('wheel', onWheel, { capture: true, passive: false });
    return () => document.removeEventListener('wheel', onWheel, { capture: true });
  }, []);

  // ---- Click model chrome (Pathon v3 W1-B) ----------------------------------
  // The hand („Rankutė", H): a drag scrolls the drawing; no layer under it sees the pointer.
  const { panning } = useDragPan({ rootRef: tvRootRef, armed: measureTool === 'pan' && active && !check, space: active && !check });
  // The tool cards keep their labels while the canvas is tall enough for them, icons only below that.
  const [chromeHeight, setChromeHeight] = useState(0);
  const [chromeEl, setChromeEl] = useState(null);
  const chromeObserver = useRef(null);
  const chromeRef = useCallback((el) => {
    chromeObserver.current?.disconnect();
    chromeObserver.current = null;
    setChromeEl(el);
    if (!el || typeof ResizeObserver === 'undefined') return;
    const ro = new ResizeObserver(() => setChromeHeight(Math.round(el.getBoundingClientRect().height)));
    ro.observe(el);
    chromeObserver.current = ro;
  }, []);
  const railCompact = chromeHeight > 0 && chromeHeight < railHeight() + 16;
  // The middle button drags the drawing from any tool (W5-B B5); the chrome element exists once the document has.
  useMiddlePan({ rootRef: tvRootRef, enabled: !!chromeEl });
  // „Patalpa" (R, W1-D): the one-click room outline, armed as the measure tool 'room' when the host gives the
  // preview and the save; otherwise the card stays disabled with its reason.
  const onRoomTool = !check && onRoomToolPreview && onRoomToolCommit ? () => armMeasureTool('room') : null;
  // The tool the cards show pressed: the armed mode, „Rasti panašius" while its session is open.
  const railActiveTool = symbol.active ? 'findSimilar' : legend.active ? 'legend' : (measureTool === 'scalecheck' ? null : measureTool);
  const onRailTool = (id) => {
    if (id === 'findSimilar') { toggleSymbolSearch(); return; }
    if (id === 'legend') { toggleLegend(); return; }
    if (id === 'room') { onRoomTool?.(); return; }
    armMeasureTool(id);
  };
  // What the page layers and the status bar are told: neither the hand nor the room tool is a page tool (the hand
  // owns the pointer above them; the room tool takes the page's click in handlePagePoint and draws its own layer).
  const pageTool = measureTool === 'pan' || measureTool === 'room' ? null : measureTool;
  // The bottom pill (W1-B B2): only the active mode — its name, what it holds, its keys, finish / leave.
  const mac = useMemo(() => isMacPlatform(), []);
  const activeCountType = measureTool === 'count' ? countTypes.find((t) => t.id === activeCountTypeId) : null;
  const pill = check ? null : modePillFor({
    tool: measureTool,
    draftPoints,
    finishable: !!draftCommitPoints(draftSlot.draft.points, measureTool),
    calibPoint: calibSlot.point != null,
    outlineEdit: outlineEdit ? { nr: outlineEdit.nr, name: outlineEdit.target === 'measure' ? `${MEASURE_KIND_NAMES[outlineEdit.kind] || 'Matavimas'} · taškai` : null, saveLabel: outlineEdit.target === 'measure' ? 'Išsaugoti' : null, canUndo: !!outlineEdit.history?.length, invalid: outlineInvalid, saving: outlineSaving } : null,
    fill: fillFor != null ? { nr: fillFor, busy: fillBusy } : null,
    symbolActive: symbol.active,
    selectionCount: selectedMeasureIds.length,
    countType: activeCountType ? { label: activeCountType.label, n: countTallies[activeCountType.id] || 0, findable: !!projectId } : null,
    roomPhase: roomToolArmed ? roomTool.state.phase : null,
    legend: legend.active ? {
      phase: legend.phase, proposals: legend.proposals.length, toCreate: legend.toCreate.length, blanks: legend.blanks.length,
      notice: legend.notice, elapsed: legend.elapsed, outcome: legend.outcome, gotoPage: legendGotoPage(legend),
    } : null,
    mac,
    drawShape,
  });
  // The sentence beside the pointer (W1-B B3): the mode in front wins — outline edit, an outline tool, the
  // armed fill, „Rasti panašius", then the measure tool. Nothing at rest.
  const hintMode = outlineEdit ? 'outlineEdit'
    : outlineTools.tool ? outlineTools.tool.mode
      : fillFor != null ? 'fill'
        : symbol.active ? 'findSimilar'
          : legend.active ? 'legend'
            : measureTool;
  const resolveCursorHint = ({ shift }) => cursorHintFor({
    mode: hintMode,
    points: draftPoints,
    shift,
    calibPoint: calibSlot.point != null,
    countType: activeCountType ? { label: activeCountType.label, n: countTallies[activeCountType.id] || 0 } : null,
    symbolPhase: symbol.phase,
    fill: fillFor != null ? { nr: fillFor, busy: fillBusy } : null,
    selectionCount: selectedMeasureIds.length,
    outlineTool: outlineTools.tool,
    roomPhase: roomToolArmed ? roomTool.state.phase : null,
    legendPhase: legend.phase,
  });
  const onPillAction = (id) => {
    if (id.startsWith('shape:')) { setDrawShape(id.slice(6)); return; }
    if (id === 'outlineUndo') undoOutline();
    else if (id === 'outlineSave') saveOutlineEdit();
    else if (id === 'outlineCancel') cancelOutlineEdit();
    else if (id === 'fillCancel') setFillFor(null);
    else if (id === 'symbolClose') symbol.close();
    else if (id === 'legendAccept') legend.accept();
    else if (id === 'legendRedraw') legend.redraw();
    else if (id === 'legendCreate') legend.create();
    else if (id === 'legendExit') legend.close();
    else if (id === 'legendRetry') legend.retry();
    else if (id === 'legendGoto') { const p = legendGotoPage(legend); if (p) legendGotoRef.current?.(p); }
    else if (id === 'countFindSimilar') {
      // B1-B: he marked one symbol with „Kiekis" and expected the rest to be counted — the mark on screen (the
      // newest of the type) is the template for „Rasti panašius"; what it finds is a proposal he reviews
      const mine = measurements.filter((m) => m.kind === 'count' && m.typeId === activeCountTypeId);
      const here = mine.filter((m) => m.page === visiblePageRef.current);
      const m = (here.length ? here : mine)[(here.length ? here : mine).length - 1];
      if (m) findSimilarFrom(m);
    } else if (id === 'draftFinish') {
      const pts = draftCommitPoints(draftSlot.draft.points, measureTool);
      if (pts && draftSlot.pageNr != null) commitMeasurement(makeMeasurement(measureTool, draftSlot.pageNr, pts));
      setDraftSlot({ pageNr: null, draft: EMPTY_DRAFT });
    } else if (id === 'draftCancel') setDraftSlot({ pageNr: null, draft: EMPTY_DRAFT });
    else if (id === 'calibCancel') setCalibSlot({ pageNr: null, point: null });
    else if (id === 'deselect') setSelectedMeasureIds([]);
    else if (id === 'roomSave') roomTool.commit();
    else if (id === 'roomDrop') roomTool.escape();
    else if (id === 'toolExit') {
      if (measureTool === 'scalecheck') setScaleCheck(null);
      setMeasureTool(null);
      setSelectedMeasureId(null);
    }
  };

  // Esc (W1-B B4): one press, one step back — lib/escOrder says which, this does it.
  const handleEscape = () => {
    const step = escStep({
      popoverOpen: !!measureMenu || !!calibRequest || guideOpen || openLayerInDocument(),
      draftPoints,
      calibPoint: calibSlot.point != null,
      roomProposal: roomToolArmed && (roomTool.state.phase === 'proposed' || roomTool.state.phase === 'picking'),
      outlineEdit: !!outlineEdit,
      outlineTool: !!outlineTools.tool,
      outlineToolSteps: outlineTools.tool?.history?.length || 0,
      legend: legend.active,
      symbolSearch: symbol.active,
      fillArmed: fillFor != null,
      measureSelection: measureTool === 'select' || measureTool === 'lasso' ? selectedMeasureIds.length : 0,
      tool: measureTool,
      panelOpen: searchOpen || scalesOpen || historyOpen || !!scaleCheck,
      roomSelected: !check && focusedRoomNr != null,
    });
    switch (step) {
      case 'popover': return true;           // the menu / dialog closes itself (Radix); nothing under it moves
      case 'draftPoint': dispatchDraft(draftSlot.pageNr, { type: 'undo' }); return true;
      case 'calibPoint': setCalibSlot({ pageNr: null, point: null }); return true;
      case 'roomProposal': roomTool.escape(); return true;
      case 'outlineEdit': setOutlineEdit(null); return true;
      case 'outlineToolStep': outlineTools.undo(); return true;
      case 'outlineTool': outlineTools.cancel(); return true;
      case 'legend': legend.close(); return true;
      case 'symbolSearch': symbol.close(); return true;
      case 'fill': setFillFor(null); return true;
      case 'measureSelection': setSelectedMeasureIds([]); return true;
      case 'tool':
        if (measureTool === 'scalecheck') setScaleCheck(null);
        setMeasureTool(null);
        setSelectedMeasureId(null);
        return true;
      case 'panel':
        setSearchOpen(false); setScalesOpen(false); setHistoryOpen(false); setScaleCheck(null);
        return true;
      case 'room': onClearFocus?.(); return true;
      default: return false;
    }
  };
  // Shift+F / „." — the selection in the whole window: the selected marks, else the selected room.
  const frameNonce = useRef(0);
  const [frameFocus, setFrameFocus] = useState(null);
  const frameSelection = () => {
    const marks = measurements.filter((m) => selectedMeasureIds.includes(m.id));
    const room = focusedRoom ? (rooms || []).find((r) => String(r?.nr) === String(focusedRoom.nr)) || focusedRoom : null;
    const pages = docPagesRef.current || [];
    const target = marks.length
      ? frameForMeasurements(marks, {
        pageSizeOf: (p) => pages[p - 1]?.size || null,
        rotationOf: (p) => pages[p - 1]?.rotation ?? 0,
      })
      : frameForRoom(room);
    if (!target) {
      toast.info(room ? `Patalpa ${room.nr} brėžinyje nepažymėta — nėra ką parodyti` : 'Pirmiausia pažymėkite patalpą ar matavimą');
      return true;
    }
    frameNonce.current += 1;
    setFrameFocus({ page: target.page, rect: target.rect, nonce: `frame-${frameNonce.current}` });
    return true;
  };
  // E / M / X act on the selected room — never in the middle of a drawing or another outline action.
  const roomKeysFree = !check && focusedRoomNr != null && !outlineEdit && !outlineTools.tool && draftPoints === 0 && fillFor == null;
  const onRoomEdit = roomKeysFree && onRoomOutlineEdit ? startOutlineEdit : null;
  const onRoomMerge = roomKeysFree && onOutlineTool ? () => startMerge() : null;
  const onRoomSubtract = roomKeysFree && onOutlineTool ? () => outlineTools.start('subtract') : null;

  // ---- Selection bar (W1-B B6) ---------------------------------------------
  // A selected room's actions, or the selected marks' — where the eye is, never on the label.
  const navigate = useNavigate();
  const barRoom = !check && focusedRoomNr != null && (onRoomPolygonFill || onRoomOutlineEdit || onOutlineTool)
    ? (rooms || []).find((r) => String(r?.nr) === String(focusedRoomNr)) || null : null;
  const selectedMarks = measurements.filter((m) => selectedMeasureIds.includes(m.id));
  const marksBarOn = !check && (measureTool === 'select' || measureTool === 'lasso') && selectedMarks.length > 0;
  const roomBarOn = !!barRoom && !marksBarOn && !outlineEdit && !outlineTools.tool && fillFor == null && !symbol.active && !legend.active
    && (measureTool == null || measureTool === 'pan' || measureTool === 'select' || measureTool === 'lasso');
  const openRoomSheet = (nr) => {
    if (!projectId) return;
    navigate(`/project/${encodeURIComponent(projectId)}/patikra?kambarys=${encodeURIComponent(nr)}`);
  };
  const [renaming, setRenaming] = useState(null);     // { id, value } while „Pervadinti" is open
  // „Rodinys" (W5-B B4): how the drawing is shown — view only, remembered per browser (lib/viewSettings).
  const [viewSettings, setViewSettingsState] = useState(() => readViewSettings());
  const setViewSettings = (next) => { writeViewSettings(next); setViewSettingsState(next); };
  const viewRules = viewCss(viewSettings);
  const KIND_NAMES = { distance: 'Atstumas', perimeter: 'Perimetras', area: 'Plotas', count: 'Žymė' };
  const oneMark = selectedMarks.length === 1 ? selectedMarks[0] : null;
  const barMarks = marksBarOn ? {
    count: selectedMarks.length,
    kindLabel: oneMark ? [KIND_NAMES[oneMark.kind] || 'Matavimas',
      oneMark.kind === 'count' ? (countTypes.find((t) => t.id === oneMark.typeId)?.label || null) : null,
      oneMark.name ? `„${oneMark.name}"` : null].filter(Boolean).join(' · ') : null,
    countTypes: oneMark?.kind === 'count' ? countTypes : [],
    typeId: oneMark?.typeId ?? null,
    onRename: oneMark ? () => setRenaming({ id: oneMark.id, value: oneMark.name || '' }) : null,
    onChangeType: oneMark?.kind === 'count' ? (typeId) => changeCountType(oneMark.id, typeId) : null,
    onReveal: oneMark ? () => revealMeasurement(oneMark) : null,
    onDelete: () => deleteMeasurementWithUndo(selectedMeasureIds),
    onDeselect: () => setSelectedMeasureIds([]),
  } : null;
  // A room Shift+clicked beside the focused one (W1-D) is the merge target M / „Sujungti" starts with.
  const mergeTargetNr = extraRoomNrs.length === 1 ? String(extraRoomNrs[0]) : null;
  const startMerge = () => outlineTools.start('merge', mergeTargetNr ? { targetNr: mergeTargetNr } : undefined);
  const barRoomActions = roomBarOn ? {
    nr: [String(barRoom.nr), ...extraRoomNrs.map(String)].join(' + '),
    name: barRoom.pavadinimas || null,
    onEdit: onRoomOutlineEdit ? startOutlineEdit : null,
    onSplit: onOutlineTool ? () => outlineTools.start('split') : null,
    onMerge: onOutlineTool ? startMerge : null,
    mergeTargetNr,
    onSubtract: onOutlineTool ? () => outlineTools.start('subtract') : null,
    onExclude: projectId ? () => openRoomSheet(barRoom.nr) : null,
    onEvidence: projectId ? () => openRoomSheet(barRoom.nr) : null,
    onFill: onRoomPolygonFill ? () => startFill(barRoom.nr) : null,
    // „Pažymėti panašias" (W5-A A5): the rooms of the same purpose / the same floor covering join the selection
    similar: {
      paskirtis: barRoom.paskirtis ? similarRooms(rooms, barRoom.nr, 'paskirtis').length : 0,
      grindu_danga: barRoom.grindu_danga ? similarRooms(rooms, barRoom.nr, 'grindu_danga').length : 0,
      paskirtisWord: barRoom.paskirtis ? roomTypeWord(barRoom.paskirtis) || barRoom.paskirtis : null,
      grinduWord: ({ plyteles: 'plytelės', minksta: 'parketas ar laminatas', be_dangos: 'be dangos' })[barRoom.grindu_danga] || barRoom.grindu_danga || null,
    },
    onSimilar: (by) => {
      const like = similarRooms(rooms, barRoom.nr, by);
      applyRoomSelection({ focused: String(barRoom.nr), extra: like });
      toast.success(like.length ? `Pažymėta ${like.length + 1} patalpos` : 'Panašių patalpų nėra');
    },
  } : null;
  const roomLabelSelectors = focusedRoomNr != null
    ? [`[data-room-label="${focusedRoomNr}"]`, `[data-room-ring="${focusedRoomNr}"]`, `[data-room-zone="${focusedRoomNr}"]`] : [];
  // The scale chip (W1-D) sits at the drawing's bottom-left: the pill, the bar and the legend keep off it.
  const chromeRects = useChromeRects(chromeEl, {
    anchor: marksBarOn ? (oneMark ? [`[data-measure-anchor="${oneMark.id}"]`] : []) : (roomBarOn ? roomLabelSelectors : []),
    label: roomLabelSelectors,
    bar: '[data-testid="selection-bar"]',
    pill: '[data-testid="mode-pill"]',
    nav: '[data-nav-cluster]',
    header: '[data-canvas-header]',
    legend: '[data-layer-legend]',
    scaleChip: '[data-testid="scale-chip-root"]',
    zoom: '[data-zoom-cluster]',
  });
  // Where the top row of cards ends (pages / zoom and search may wrap to two rows on a narrow canvas).
  const chromeTopBottom = Math.max(
    (chromeRects.rects.nav ? chromeRects.rects.nav.top + chromeRects.rects.nav.height : 50),
    (chromeRects.rects.header ? chromeRects.rects.header.top + chromeRects.rects.header.height : 50),
  );
  // The layer legend takes the first corner that covers neither the selected room's label, the bar, the pill
  // nor the pages / zoom card (manager item 2026-10-18: it covered a selected zone's label at bottom right).
  const legendSpot = (() => {
    const f = chromeRects.frame;
    if (!f) return 'bottom-right';
    const r = chromeRects.rects;
    const size = { width: r.legend?.width || 280, height: r.legend?.height || 96 };
    const spots = [
      { id: 'bottom-right', left: f.width - 8 - size.width - (r.zoom ? r.zoom.width + 8 : 0), top: f.height - 8 - size.height },
      { id: 'top-right', left: f.width - 8 - size.width, top: chromeTopBottom + 8 },
      { id: 'bottom-left', left: (check ? 8 : RAIL_WIDTH + 16), top: f.height - 8 - size.height - (r.scaleChip ? r.scaleChip.height + 8 : 0) },
    ];
    return pickSpot({ spots, size, avoid: [r.label, r.bar, r.pill, r.nav, r.header, r.scaleChip, r.zoom].filter(Boolean) });
  })();

  // The pop-up's actions for the corner / edge it was opened on (A2).
  const vertexMenuActions = (() => {
    const ed = outlineEdit;
    const menu = vertexMenu;
    if (!ed || !menu) return null;
    const min = ed.minPoints || 3;
    const at = menu.kind === 'vertex'
      ? ed.points[menu.index]
      : (() => { const a = ed.points[menu.index]; const b = ed.points[(menu.index + 1) % ed.points.length]; const t = menu.t ?? 0.5; return [a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1])]; })();
    const out = {
      onDelete: () => {
        const res = deleteVertices(ed.points, [menu.index], min);
        if (res.refused) return;
        snapshotOutline();
        setOutlineEdit((cur) => (cur ? { ...cur, points: res.points, selected: [] } : cur));
      },
      deleteDisabled: ed.points.length <= min ? `Mažiau nei ${min} kampų likti negali` : null,
      onInsert: () => {
        snapshotOutline();
        setOutlineEdit((cur) => (cur ? { ...cur, points: insertVertex(cur.points, menu.index, at), selected: [menu.index + 1] } : cur));
      },
    };
    if (ed.target === 'measure') {
      if (ed.kind === 'area') {
        out.onCut = null;
        out.cutDisabled = 'Plote angos neiškerpamos — anga iškerpama perimetre ar atstume';
        return out;
      }
      const scale = effectiveScales[ed.page];
      out.cutLabel = `Iškirpti angą (${DOORWAY_GAP_M.toFixed(2).replace('.', ',')} m)`;
      out.cutTitle = 'Iš šios atkarpos išpjaunamas durų angos tarpas — lieka dvi atkarpos be angos';
      if (!scale?.calibrated) { out.onCut = null; out.cutDisabled = 'Lapo mastelis nenustatytas — angos plotis metrais nežinomas'; return out; }
      out.onCut = () => {
        const pg = pageSizeOf(ed.page);
        const before = measurements.find((m) => m.id === ed.id);
        if (!pg?.size || !before) return;
        const pts = pctToPoints(ed.points, { width: pg.size.width, height: pg.size.height, rotation: pg.rotation ?? 0 });
        const pos = menu.kind === 'vertex'
          ? pathPositionM(pts, scale, { vertex: menu.index })
          : pathPositionM(pts, scale, { edge: menu.index, t: menu.t ?? 0.5 });
        const pieces = cutGap(pts, scale, pos, DOORWAY_GAP_M);
        if (!pieces) { flashCursorHint('Atkarpa per trumpa angai'); return; }
        const { id: _id, points: _p, created_at: _c, ...rest } = before;
        const parts = pieces.map((points, i) => (i === 0 ? { ...before, points } : makeMeasurement(before.kind, before.page, points, { ...rest })));
        setMeasurements((prev) => prev.flatMap((m) => (m.id === before.id ? parts : [m])));
        setOutlineEdit(null);
        const ids = new Set(parts.map((x) => x.id));
        toast.success(`Iškirpta ${DOORWAY_GAP_M.toFixed(2).replace('.', ',')} m anga — ${parts.length === 2 ? 'liko dvi atkarpos' : 'liko viena atkarpa'}`, {
          duration: 10_000,
          action: { label: 'Atšaukti', onClick: () => setMeasurements((prev) => [...prev.filter((m) => !ids.has(m.id)), before]) },
        });
      };
      return out;
    }
    if (!onRoomOpenings) return out;
    const room = (rooms || []).find((r) => String(r?.nr) === String(ed.nr));
    const r = editPageRect(ed.page);
    const choice = openingForEdge(room, ed.page, at, { w: r?.width || 1000, h: r?.height || 1000 });
    const what = openingText(choice.kind, choice.plotisMm);
    out.cutLabel = `Iškirpti angą — ${what.toLowerCase()}`;
    out.cutTitle = choice.from === 'walls'
      ? `Šioje sienoje programa perskaitė angą (${what.toLowerCase()}) — ji bus skaičiuojama patalpoje ${ed.nr}`
      : `Šioje vietoje programa angos neperskaitė — patalpai ${ed.nr} pridedamos standartinės durys 0,90 × 2,10 m; dydį pakeisite spustelėję angą sienų sluoksnyje`;
    out.onCut = async () => {
      try {
        const saved = await onRoomOpenings(ed.nr, (el) => addEdgeOpening(el, choice));
        if (!saved) { toast.info(`Ši anga patalpoje ${ed.nr} jau skaičiuojama`); return; }
        toast.success(`Patalpai ${ed.nr} pridėta: ${what.toLowerCase()}`, { description: 'Kiekiai perskaičiuojami.', ...undoAction(saved) });
      } catch (e) {
        toast.error(e?.message || 'Angos pridėti nepavyko');
      }
    };
    return out;
  })();
  if (!activeDocumentId) return <div className="p-5 text-sm text-muted-foreground">Kraunamas dokumentas…</div>;
  return (
    <DocumentContent documentId={activeDocumentId}>
      {({ isLoaded, documentState }) => {
        if (!isLoaded) return <div className="p-5 text-sm text-muted-foreground">Kraunamas dokumentas…</div>;
        docPagesRef.current = documentState?.document?.pages || null;
        const totalPages = documentState?.document?.pageCount ?? documentState?.pageCount ?? documentState?.pages?.length ?? null;
        // No explicit user choice yet → open by default on multi-page documents.
        // The check sheet's drawing pane is narrow: the rail stays shut there unless asked for.
        const sheetRail = sheetPages && !check ? buildSheetRail({ puslapiai: sheetPages, overrides: sheetOverrides, pageCount: totalPages }) : null;
        // With sheets the toggle switches the full rail ⇄ the strip; without, the plain thumbnails on ⇄ off.
        const railOpen = sheetRail ? sheetRailFull : (thumbsPref ?? (check ? false : (totalPages ?? 1) > 1));
        const toggleRail = () => (sheetRail ? setSheetRailFull(!sheetRailFull) : setRailOpen(!railOpen));
        // Floating panels start right of whichever rail is showing — the full rail, the 56 px strip, the thumbnails.
        const panelLeft = floatingPanelLeft({ railOpen, sheetRail: !!sheetRail, strip: true, toolRail: check ? 0 : RAIL_WIDTH });
        // The chrome floating over the drawing starts where the sheet list ends, so nothing ever covers the list.
        const chromeLeft = sheetRailWidth({ railOpen, sheetRail: !!sheetRail, strip: true });
        return (
        <div className="flex flex-col h-full" data-tv-root ref={tvRootRef}>
          {!check && (
            <FocusScroller
              documentId={activeDocumentId} focusedRoom={focusedRoom} focusedPage={focusedPage} skipJumpRef={skipJumpRef}
              rooms={rooms}
              onFrame={(f) => { frameNonce.current += 1; setFrameFocus({ page: f.page, rect: f.rect, nonce: `focus-${frameNonce.current}` }); }}
            />
          )}
          {/* „show me this place" works outside the check view too (the workspace's onRevealEvidence) */}
          {(check || focus) && <FocusZoomer documentId={activeDocumentId} focus={focus} pages={documentState?.document?.pages} />}
          {/* Shift+F / „." — the selection framed (its own zoomer: its requests never collide with the host's) */}
          <LegendPageWatcher documentId={activeDocumentId} pageRef={visiblePageRef} gotoRef={legendGotoRef} onPage={legend.active ? legend.pageShown : null} />
          {frameFocus && <FocusZoomer documentId={activeDocumentId} focus={frameFocus} pages={documentState?.document?.pages} />}
          {/* `active` = false while the workspace keeps this viewer mounted behind a strip (Sąmata
              „Išskleisti", Siųsti): a key typed there must not arm a tool or undo a mark nobody sees. */}
          {active && <ViewerHotkeys
            documentId={activeDocumentId}
            fillArmed={fillFor != null}
            onEscape={handleEscape}
            onToggleThumbs={toggleRail}
            onMeasureToolKey={armMeasureTool}
            canDeleteSelected={(measureTool === 'select' || measureTool === 'lasso') && selectedMeasureIds.length > 0}
            onDeleteSelected={() => deleteMeasurementWithUndo(selectedMeasureIds)}
            onOpenSearch={() => setSearchOpen(true)}
            onUndo={check ? null : undoMeasure}
            onRedo={check ? null : redoMeasure}
            onOpenGuide={() => setGuideOpen((v) => !v)}
            onToggleZoneFills={check ? null : () => setZoneFillsVisible((v) => !v)}
            onToggleWallsLayer={check ? null : () => setWallsLayerVisible(!wallsLayerVisible)}
            onToggleSymbolSearch={check ? null : toggleSymbolSearch}
            onToggleLegend={check || !projectId ? null : toggleLegend}
            onRoomTool={check ? null : onRoomTool}
            onFrameSelection={check ? null : frameSelection}
            onRoomEdit={onRoomEdit}
            onRoomMerge={onRoomMerge}
            onRoomSubtract={onRoomSubtract}
            onCopyMarks={check ? null : copyMarks}
            onPasteMarks={check ? null : pasteMarks}
            onDuplicateMarks={check ? null : duplicateMarks}
          />}
          {panning && <style>{PAN_CURSOR_CSS}</style>}
          {viewRules && <style>{viewRules}</style>}
          {viewSettings.cleanBg > 0 && <CleanBgFilter t={viewSettings.cleanBg} />}
          <div className="relative flex flex-1 min-h-0">
            {sheetRail
              ? <SheetRail mode={railOpen ? 'full' : 'strip'} documentId={activeDocumentId} rail={sheetRail} currentPageOf={visiblePageOf} onRename={onSheetOverridesChange ? renameSheet : null} onReset={resetSheet} onExpand={() => setSheetRailFull(true)} skipped={skippedSet} onToggleSkip={onSkippedPagesChange ? toggleSkipSheet : null} />
              : railOpen && <ThumbnailRail documentId={activeDocumentId} />}
            {/* ZoomGestureWrapper must be INSIDE Viewport: useViewportElement()
                reads ViewportElementContext, whose Provider is rendered BY the
                Viewport component. As a parent it got null → setupZoomGestures
                never ran → no ctrl+wheel / pinch zoom (audit P2, root-caused
                2026-07-14 via defaultPrevented=false on a synthetic event). */}
            <Viewport documentId={activeDocumentId} data-testid="viewer-canvas" style={{ flex: 1, minHeight: 0, minWidth: 0, background: 'hsl(var(--viewer-blueprint-bg))' }}>
              <ZoomGestureWrapper documentId={activeDocumentId}>
                <Scroller
                  documentId={activeDocumentId}
                  renderPage={(layout) => (
                    <PageOverlayHost
                      documentId={activeDocumentId}
                      projectId={projectId}
                      layout={layout}
                      rooms={rooms}
                      pageRotation={documentState?.document?.pages?.[layout.pageIndex]?.rotation ?? 0}
                      pageSizePt={documentState?.document?.pages?.[layout.pageIndex]?.size ?? null}
                      checkMode={!!check}
                      checkData={check?.pages?.[layout.pageNumber] || null}
                      symbolSearch={symbol.active ? symbol : null}
                      legend={legend.active ? legend : null}
                      focusedRoomNr={focusedRoomNr}
                      selectedRoomNrs={extraRoomNrs}
                      hiddenRoomNrs={hiddenRoomNrs}
                      hoveredRoomNrExternal={hoveredRoomNrExternal}
                      zoneFillsVisible={zoneFillsVisible}
                      wallsLayerVisible={wallsLayerVisible}
                      outlineEdit={outlineEdit}
                      onOutlineEditChange={(points) => setOutlineEdit((cur) => (cur ? { ...cur, points } : cur))}
                      onOutlineGestureStart={snapshotOutline}
                      outlineTool={outlineTools.tool}
                      onOutlineToolChange={outlineTools.change}
                      onRequestHole={projectId && outlineTools.tool?.mode === 'subtract' ? (point) => fetchHoleAt(projectId, outlineTools.tool.nr, point) : null}
                      onRoomZoneClick={onRoomZoneClick}
                      onPagePoint={handlePagePoint}
                      onPageDoubleClick={handlePageDoubleClick}
                      onOutlineSelect={(selected) => setOutlineEdit((cur) => (cur ? { ...cur, selected } : cur))}
                      onOutlineMenu={setVertexMenu}
                      measureTool={pageTool === 'scalecheck' ? 'calibrate' : pageTool}
                      measurements={measurements}
                      measureScale={effectiveScales[layout.pageNumber] || null}
                      snapEnabled={snapEnabled}
                      orthoEnabled={orthoEnabled}
                      countTypes={countTypes}
                      activeCountTypeId={activeCountTypeId}
                      selectedMeasureIds={selectedMeasureIds}
                      selectionMenuOnMiss={measureTool === 'lasso' && selectedMeasureIds.length > 1}
                      onMeasureCommit={commitMeasurement}
                      onMeasureCalibrate={(pageNr, a, b) => (measureTool === 'scalecheck' ? setScaleCheck({
                        page: pageNr,
                        readout: scaleCheckReadout({
                          a, b,
                          scale: effectiveScales[pageNr],
                          pageSize: documentState?.document?.pages?.[layout.pageIndex]?.size,
                          rotation: documentState?.document?.pages?.[layout.pageIndex]?.rotation ?? 0,
                          strings: dimensionStringsOf(project)[pageNr] || [],
                        }),
                      }) : setCalibRequest({
                        pageNr, a, b,
                        // The page's /Rotate travels with the pick: the dialog's
                        // axis labels describe what the user SEES, while a/b are
                        // unrotated mediabox points (audit P1).
                        rotation: documentState?.document?.pages?.[layout.pageIndex]?.rotation ?? 0,
                      }))}
                      onMeasureSelect={setSelectedMeasureId}
                      onMeasureBoxSelect={handleBoxSelect}
                      onMeasureSnapChange={setSnapKind}
                      onCountTypeMenu={measureTool === 'count' ? setCountPicker : null}
                      drawShape={drawShape}
                      onMeasureDelete={deleteMeasurement}
                      onMeasureContextMenu={check ? null : setMeasureMenu}
                      measureDraft={draftSlot.pageNr === layout.pageNumber ? draftSlot.draft : EMPTY_DRAFT}
                      onMeasureDraftAction={(action) => dispatchDraft(layout.pageNumber, action)}
                      measureCalibA={calibSlot.pageNr === layout.pageNumber ? calibSlot.point : null}
                      onMeasureCalibAChange={(point) => setCalibSlot(
                        point ? { pageNr: layout.pageNumber, point } : { pageNr: null, point: null })}
                      sheetLinks={sheetRail ? { sheets: sheetRail.sheets, version: sheetLinksVersion } : null}
                      revisionOverlay={check ? null : revisionOverlay}
                      roomTool={roomToolArmed ? roomTool.state : null}
                      zonesShown={!check && viewSettings.zones}
                    />
                  )}
                />
              </ZoomGestureWrapper>
            </Viewport>
            {/* The chrome floating over the drawing (Pathon v3 click model): laid out right of the sheet list so it
                never covers it; click-through except on its own cards. */}
            <div
              ref={chromeRef}
              className="absolute inset-y-0 right-0 z-panel pointer-events-none"
              style={{ left: chromeLeft }}
              data-canvas-chrome
            >
              {!check && (
                <div className="absolute top-2 left-2">
                  <RailHost
                    documentId={activeDocumentId}
                    compact={railCompact}
                    activeTool={railActiveTool}
                    onTool={onRailTool}
                    available={{
                      room: onRoomTool ? undefined : 'Patalpos įrankis veikia projekto brėžinyje, kai jis atidarytas iš projekto.',
                      legend: projectId ? undefined : 'Legendos įrankis veikia projekto brėžinyje, kai jis atidarytas iš projekto.',
                    }}
                    layers={{ zones: zoneFillsVisible, walls: wallsLayerVisible }}
                    onToggleLayer={(id) => (id === 'zones' ? setZoneFillsVisible((v) => !v) : setWallsLayerVisible(!wallsLayerVisible))}
                    onDownload={handleDownload}
                    scalesOpen={scalesOpen}
                    onToggleScales={project ? () => setScalesOpen((v) => !v) : null}
                    historyOpen={historyOpen}
                    onToggleHistory={() => setHistoryOpen((v) => !v)}
                    railOpen={railOpen}
                    onToggleRail={toggleRail}
                    onOpenGuide={() => setGuideOpen(true)}
                  />
                </div>
              )}
              {/* Top right, one row: the sheet (badge, name, „← 1 iš N →", W5-B B1), then the reading / editions
                  buttons and the search. Zoom is the column at the bottom right (ZoomCluster). */}
              <div className="absolute top-2 right-2 flex flex-wrap items-start justify-end gap-2" style={{ left: check ? 8 : RAIL_WIDTH + 16 }} data-chrome-top>
                <SheetHeaderBadge documentId={activeDocumentId} totalPages={totalPages} sheets={sheetRail?.sheets || null} />
                <CanvasHeader
                  documentId={activeDocumentId}
                  totalPages={totalPages}
                  addon={check ? null : renderToolbarAddon}
                  addonContext={project ? (page) => ({ scaleGate: sheetNotNeeded(page) ? { ok: true, state: 'nereikia', reason: null } : scaleGateFromScale(pageScaleIn(effectiveScales, page)), onSetScale: () => setScaleChipOpen((n) => n + 1) }) : null}
                  searchOpen={searchOpen}
                  onToggleSearch={() => setSearchOpen((v) => !v)}
                  onCloseSearch={() => setSearchOpen(false)}
                />
              </div>
              {/* Zoom, area zoom, minimap, full screen — one column at the bottom right (W5-B B5). */}
              <ZoomCluster
                documentId={activeDocumentId}
                pages={documentState?.document?.pages}
                onAreaZoom={({ page, rect }) => { frameNonce.current += 1; setFrameFocus({ page, rect, nonce: `area-${frameNonce.current}` }); }}
                viewSettings={<ViewSettingsPopover settings={viewSettings} onChange={setViewSettings} />}
              />
              {/* The active mode's pill, bottom centre right of the tool cards. */}
              {pill && (
                <div className="absolute bottom-2 flex justify-center" style={{ left: Math.max(check ? 8 : RAIL_WIDTH + 16, chromeRects.rects.scaleChip ? chromeRects.rects.scaleChip.left + chromeRects.rects.scaleChip.width + 8 : 0), right: chromeRects.frame && chromeRects.rects.zoom ? chromeRects.frame.width - chromeRects.rects.zoom.left + 8 : 8 }}>
                  <ModePill pill={pill} onAction={onPillAction} />
                </div>
              )}
              {/* The selected room's or marks' actions, pinned under the top row of cards (Kreo's fly-menu default):
                  measured on demo-objektas_h at 1280 px, a bar standing next to the room covered the neighbour he
                  Shift+clicks next — the click pressed „Padalyti" instead. Pinned, it never moves under the cursor;
                  it steps below the selected label if that label is up there (lib/selectionPlacement). */}
              {(barRoomActions || barMarks) && (
                <SelectionBar
                  frame={chromeRects.frame}
                  anchor={null}
                  avoid={[chromeRects.rects.nav, chromeRects.rects.header, chromeRects.rects.pill, chromeRects.rects.scaleChip, chromeRects.rects.zoom, chromeRects.rects.label, chromeRects.rects.anchor].filter(Boolean)}
                  insetLeft={check ? 8 : RAIL_WIDTH + 16}
                  room={barRoomActions}
                  marks={barRoomActions ? null : barMarks}
                />
              )}
              {/* Layer legend (2026-10-16 walls; v3 W1-C zones too): what each line style on the sheet means,
                  named once, where the layers are — in the corner that covers nothing the user looks at. */}
              {(wallsLayerVisible || zoneFillsVisible) && !check && (
                <OverlayLegend
                  vertical
                  layers={[zoneFillsVisible && 'zones', wallsLayerVisible && 'walls'].filter(Boolean)}
                  className={`absolute max-w-[300px] ${legendSpot === 'top-right' ? 'right-2' : legendSpot === 'bottom-left' ? '' : 'right-2'}`}
                  style={legendSpot === 'top-right'
                    ? { top: chromeTopBottom + 8 }
                    : legendSpot === 'bottom-left'
                      ? { left: RAIL_WIDTH + 16, bottom: 8 + (chromeRects.rects.scaleChip ? chromeRects.rects.scaleChip.height + 8 : 0) }
                      : { bottom: 8 }}
                  data-layer-legend={legendSpot}
                  data-testid={wallsLayerVisible ? 'walls-legend' : 'zones-legend'}
                />
              )}
            </div>
            {/* Prominent tool instructions — the status-bar hint alone was
                invisible to the founder ("no buttons... or anything"). */}
            {roomToolArmed && (
              <RoomPickPanel
                picking={roomTool.state.phase === 'picking' ? roomTool.state.picking : null}
                onPick={roomTool.pick}
                onCancel={roomTool.cancelPick}
                left={panelLeft}
              />
            )}

            <div className="absolute inset-x-0 top-12 bottom-0 pointer-events-none z-30"><div className="pointer-events-auto">
            <OutlineToolPanel
              tool={outlineTools.tool}
              rooms={rooms}
              saving={outlineTools.saving}
              canSave={outlineTools.canSave}
              scale={outlineTools.tool ? effectiveScales[outlineTools.tool.page] || null : null}
              pageSizePt={outlineTools.tool ? documentState?.document?.pages?.[outlineTools.tool.page - 1]?.size ?? null : null}
              pageRotation={outlineTools.tool ? documentState?.document?.pages?.[outlineTools.tool.page - 1]?.rotation ?? 0 : 0}
              onChange={outlineTools.change}
              onUndo={outlineTools.undo}
              onCancel={outlineTools.cancel}
              onSave={outlineTools.save}
            />
            </div></div>
            {!check && (
              <div className="absolute inset-x-0 top-2 bottom-0 pointer-events-none z-30"><div className="pointer-events-auto">
                <ScaleGateChip documentId={activeDocumentId} scales={effectiveScales} tool={measureTool} onSetScale={() => armMeasureTool('calibrate')} />
              </div></div>
            )}
            {/* The sheet's scale, confirmed in one click (Pathon v3 W1-D, D4) — bottom-left of the drawing. */}
            {!check && project && (
              <ScaleChip
                documentId={activeDocumentId}
                scales={effectiveScales}
                project={project}
                durable={measureScales}
                totalPages={totalPages}
                left={panelLeft}
                onConfirm={confirmScales}
                onCalibrate={() => { setScaleCheck(null); if (measureTool !== 'calibrate') armMeasureTool('calibrate'); }}
                onCheck={() => { setScaleCheck(null); if (measureTool !== 'scalecheck') armMeasureTool('scalecheck'); }}
                onOverview={() => setScalesOpen(true)}
                openNonce={scaleChipOpen}
                pageSizeOf={(page) => documentState?.document?.pages?.[page - 1]?.size || null}
                isNotNeeded={sheetNotNeeded}
                onSetRatio={setSheetRatio}
                onNotNeeded={setSheetNotNeeded}
              />
            )}
            {(scalesOpen || scaleCheck) && !check && project && (
              <div className="absolute top-14 right-2 z-30 flex flex-col items-end gap-2">
                {scaleCheck && (
                  <ScaleCheckCard
                    readout={scaleCheck.readout}
                    page={scaleCheck.page}
                    scale={effectiveScales[scaleCheck.page]}
                    onClose={() => { setScaleCheck(null); if (measureTool === 'scalecheck') setMeasureTool(null); }}
                  />
                )}
                {scalesOpen && (
                  <ScaleOverviewDock
                    documentId={activeDocumentId}
                    project={project}
                    totalPages={totalPages}
                    durable={measureScales}
                    onConfirm={confirmScales}
                    onFix={() => { setScaleCheck(null); if (measureTool !== 'calibrate') armMeasureTool('calibrate'); }}
                    onCheck={() => { setScaleCheck(null); if (measureTool !== 'scalecheck') armMeasureTool('scalecheck'); }}
                    onClose={() => setScalesOpen(false)}
                  />
                )}
              </div>
            )}
            {historyOpen && !check && (
              <div className="absolute top-14 right-2 z-30">
                <HistoryPanel
                  history={measureHist}
                  onUndo={undoMeasure}
                  onRedo={redoMeasure}
                  onRevertTo={(entryId) => dispatchMeasureHist({ type: 'revertTo', entryId })}
                  onClose={() => setHistoryOpen(false)}
                />
              </div>
            )}
            {/* „Rasti panašius" review list (2026-10-16). */}
            {symbol.active && (
              <div className="absolute top-2 z-30 w-72" style={{ left: panelLeft }}>
                <SymbolReviewPanel documentId={activeDocumentId} search={symbol} countTypes={countTypes} totalPages={totalPages || 1} />
              </div>
            )}
            {/* „Pažymėti legendą" review (W2-B): in the workspace's right panel when the host gives a place there,
                else beside the drawing like the „Rasti panašius" list. */}
            {legend.active && (() => {
              const panel = (
                <LegendReviewPanel
                  documentId={activeDocumentId}
                  projectId={projectId}
                  legend={legend}
                  onMeasure={(tool) => { legend.close(); armMeasureTool(tool); }}
                />
              );
              if (legendPanelSlot) return createPortal(panel, legendPanelSlot);
              return (
                <div className="absolute top-2 bottom-2 z-30 w-80 overflow-hidden rounded-panel border border-border shadow-lg" style={{ left: panelLeft }}>
                  {panel}
                </div>
              );
            })()}
            {/* Floating count-type legend while the count tool is armed. */}
            {measureTool === 'count' && (
              <div
                className="absolute top-2 z-30 w-60 shadow-lg"
                style={{ left: panelLeft }}
              >
                <CountLegendPanel
                  countTypes={countTypes}
                  activeCountTypeId={activeCountTypeId}
                  onSelectType={setActiveCountTypeId}
                  tallies={countTallies}
                  aiTallies={aiTalliesOf(measurements)}
                  collapsed={countLegendCollapsed}
                  onToggleCollapse={() => setCountLegendCollapsed((v) => !v)}
                  onAddType={addCountType}
                  onRemoveType={removeCountType}
                  onClearType={(typeId) => setMeasurements((prev) =>
                    prev.filter((m) => !(m.kind === 'count' && m.typeId === typeId)))}
                />
              </div>
            )}
          </div>
          <StatusBar
            documentId={activeDocumentId}
            totalPages={totalPages}
            pages={documentState?.document?.pages}
            fillFor={fillFor}
            fillBusy={fillBusy}
            measureScales={effectiveScales}
            measureTool={pageTool}
            scaleChipShown={!check && !!project}
            outlineEdit={outlineEdit}
            projectId={projectId}
            symbolHint={symbol.active ? SYMBOL_HINTS[symbol.phase] : null}
            snapKind={snapKind}
          />
          <CalibrateDialog
            request={calibRequest}
            pageRotation={calibRequest?.rotation ?? 0}
            numPages={totalPages}
            currentScale={calibRequest ? (effectiveScales[calibRequest.pageNr] || uncalibratedScale()) : null}
            onConfirm={(scale, pages) => {
              setMeasureScales((prev) => {
                const next = { ...prev };
                for (const p of (pages || [calibRequest.pageNr])) next[p] = scale;
                return next;
              });
              // Calibration is a one-shot action: leaving the tool armed kept
              // the Mastelis button lit and the hint bar asking for 2 more
              // points, so the next click started ANOTHER calibration. Disarm
              // (the [measureTool] effect clears the draft + calib slots).
              // (2026-07-28 UX walkthrough.)
              setMeasureTool(null);
              setSelectedMeasureId(null);
              // Say what was set, in the status bar's words (2026-10-16): the dialog closes at once and
              // the status bar is small — a confirmation nobody has to look for.
              toast.success(scaleStatusText(scale), {
                description: pages ? `Pritaikyta visiems ${pages.length} lapams.` : `Pritaikyta ${calibRequest.pageNr} lapui. Patikrinkite „Atstumo" įrankiu ties žinomu matmeniu.`,
              });
            }}
            onClose={() => setCalibRequest(null)}
          />
          <ShortcutsGuide open={guideOpen} onOpenChange={setGuideOpen} />
          <OpeningPopover key={openingEdit ? `${openingEdit.nr}-${openingEdit.o.k}` : 'none'} target={openingEdit} onSave={saveOpeningEdit} onClose={() => setOpeningEdit(null)} />
          <CountTypePicker
            at={measureTool === 'count' ? countPicker : null}
            countTypes={countTypes}
            activeId={activeCountTypeId}
            tallies={countTallies}
            onPick={(id) => { setActiveCountTypeId(id); setCountPicker(null); }}
            onCreate={(label, shape) => { addCountType(label, shape); setCountPicker(null); }}
            onClose={() => setCountPicker(null)}
          />
          <VertexPopover menu={outlineEdit ? vertexMenu : null} actions={vertexMenuActions || {}} onClose={() => setVertexMenu(null)} />
          <RenameDialog
            state={renaming}
            onCancel={() => setRenaming(null)}
            onSave={(name) => { renameMeasurement(renaming.id, name); setRenaming(null); }}
          />
          {!check && (
            <MeasureContextMenu
              target={measureMenu}
              measurement={menuMeasurement}
              selection={menuSelection}
              onDeleteMany={deleteMeasurementWithUndo}
              onChangeTypeMany={changeCountTypeMany}
              onRecolorMany={recolorMany}
              onDeselect={() => setSelectedMeasureIds([])}
              countTypes={countTypes}
              onClose={() => setMeasureMenu(null)}
              onRename={renameMeasurement}
              onChangeType={changeCountType}
              onDelete={deleteMeasurementWithUndo}
              onReveal={revealMeasurement}
              onFindSimilar={projectId ? findSimilarFrom : null}
            />
          )}
          <ViewerCoachMarks rootRef={tvRootRef} enabled={!check && active} />
          <CursorHint rootRef={tvRootRef} resolve={resolveCursorHint} mode={hintMode} enabled={active && !check} />
          <ViewCrosshair rootRef={tvRootRef} enabled={active && viewSettings.crosshair && !!chromeEl} />
        </div>
        );
      }}
    </DocumentContent>
  );
}

export default function TakeoffViewer({
  fileUrl,
  // (nr, page, points_pct) => Promise — saves an outline edited vertex by vertex (2026-10-16).
  onRoomOutlineEdit = null,
  // (op) => Promise — saves an outline tool's result: split / merge / subtract (lib/outlineToolSave, 2026-10-16).
  onOutlineTool = null,
  // The room tool R (Pathon v3 W1-D): (nr, {page, x_pct, y_pct}) => the outline-at answer, read only („perziura");
  // (nr, outline-set body) => Promise<{undo?}> — saves the outline he reviewed.
  onRoomToolPreview = null,
  onRoomToolCommit = null,
  // (nr, elementai => elementai) => Promise<{undo}> — a door or window changed on the drawing (W5-A A2 / A9).
  onRoomOpenings = null,
  rooms = [],
  focusedRoom = null,
  focusedPage = null,
  hiddenRoomNrs = null,
  hoveredRoomNrExternal = null,
  onRoomZoneClick = null,
  onPagePoint = null,
  onClearFocus = null,
  projectId = null,
  pdfBlob = null,
  // Page scales the drawing states (dimension-string lane, lib/durableScale
  // pageScalesFromLane) — exact, so a sheet the engine already read as 1:50
  // never says „nekalibruotas". A user calibration still wins.
  laneScales = null,
  // The project (Togal-v2 W6): the „Masteliai" panel and the scale check read its lane record and rooms.
  project = null,
  onRoomPolygonFill = null,
  // External "arm click-to-fill for room nr" request: { nr, t } (t = nonce).
  fillRequest = null,
  // Download filename for the export button (defaults inside the engine).
  exportFileName = null,
  // Measurement persistence (Phase 3): hydrate from the project, report back
  // debounced ({ measurements, measureScales }) for the project save flow.
  initialMeasurements = null,
  initialMeasureScales = null,
  initialCountTypes = null,
  onMeasureDataChange = null,
  // Check-sheet mode (Patikra v2): `check = { pages: {[pageNr]: overlay} }` from
  // lib/checkOverlay draws what was READ about one room instead of the all-rooms
  // zones, the measuring tools step aside, and `focus = { page, rect, nonce }`
  // jumps to a place and fits it. Absent → the viewer is exactly what it was.
  check = null,
  focus = null,
  // (currentPage, totalPages, {scaleGate, onSetScale} | null) => node — a control at the head of the toolbar
  // („Perskaityti lapą", components/viewer/DetectRunButton; the third argument is the sheet's scale gate, W5-B B7).
  // Not drawn in the check sheet.
  renderToolbarAddon = null,
  // Sheets (Togal-v2 W7): the classification (`project.puslapiai`), the user's
  // `project.sheet_overrides` and their setter; `sheetLinksVersion` changes once a rename has been
  // saved, so the sheet links are read again. Absent → the plain thumbnail strip.
  sheetPages = null,
  sheetOverrides = null,
  onSheetOverridesChange = null,
  sheetLinksVersion = 0,
  // A later edition of the drawing laid over the sheets ({rid, record, mode, opacity}; RevisionCompareControl).
  revisionOverlay = null,
  // false while the project workspace keeps the viewer mounted out of sight (InteriorWorkspace strip mode):
  // no keyboard shortcuts, no first-run coach marks. Default true — every other host is unchanged.
  active = true,
  // „Pažymėti legendą" (W2-B): a DOM node in the host's right panel for the review, and a callback telling the
  // host when the tool is on (so it can show that node). Absent → the review floats beside the drawing.
  legendPanelSlot = null,
  onLegendPanelChange = null,
  // (rows) => undo — blank sąmata rows for kept legend rows with no marks (the host writes `darbu_sarasas`)
  onLegendBlankRows = null,
  // „Neskaityti šio lapo" (W5-B B9): `project.neskaitomi_lapai` and its setter. Absent → no button.
  skippedPages = null,
  onSkippedPagesChange = null,
}) {
  const { engine, isLoading, error } = usePdfiumEngine(engineOptions());
  const plugins = useMemo(
    () => (fileUrl ? makeViewerPlugins(fileUrl, exportFileName || undefined) : null),
    [fileUrl, exportFileName],
  );
  if (error) return <div className="p-5 text-sm text-destructive">Variklio klaida: {String(error.message || error)}</div>;
  if (isLoading || !engine || !plugins) return <div className="p-5 text-sm text-muted-foreground">Kraunamas PDF variklis…</div>;
  return (
    <div className="h-full" data-takeoff-viewer>
      <EmbedPDF engine={engine} plugins={plugins}>
        <ViewerInner
          renderToolbarAddon={renderToolbarAddon}
          onRoomOutlineEdit={onRoomOutlineEdit}
          onOutlineTool={onOutlineTool}
          onRoomToolPreview={onRoomToolPreview}
          onRoomToolCommit={onRoomToolCommit}
          onRoomOpenings={onRoomOpenings}
          check={check}
          focus={focus}
          rooms={rooms}
          focusedRoom={focusedRoom}
          focusedPage={focusedPage}
          hiddenRoomNrs={hiddenRoomNrs}
          hoveredRoomNrExternal={hoveredRoomNrExternal}
          onRoomZoneClick={onRoomZoneClick}
          onPagePoint={onPagePoint}
          onClearFocus={onClearFocus}
          projectId={projectId}
          pdfBlob={pdfBlob}
          exportFileName={exportFileName}
          onRoomPolygonFill={onRoomPolygonFill}
          fillRequest={fillRequest}
          initialMeasurements={initialMeasurements}
          initialMeasureScales={initialMeasureScales}
          initialCountTypes={initialCountTypes}
          onMeasureDataChange={onMeasureDataChange}
          laneScales={laneScales}
          project={project}
          sheetPages={sheetPages}
          sheetOverrides={sheetOverrides}
          onSheetOverridesChange={onSheetOverridesChange}
          sheetLinksVersion={sheetLinksVersion}
          revisionOverlay={revisionOverlay}
          active={active}
          legendPanelSlot={legendPanelSlot}
          onLegendPanelChange={onLegendPanelChange}
          onLegendBlankRows={onLegendBlankRows}
          skippedPages={skippedPages}
          onSkippedPagesChange={onSkippedPagesChange}
        />
      </EmbedPDF>
    </div>
  );
}
