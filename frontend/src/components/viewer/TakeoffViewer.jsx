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
import { useEffect, useMemo, useRef, useState } from 'react';
import { EmbedPDF } from '@embedpdf/core/react';
import { usePdfiumEngine } from '@embedpdf/engines/react';
import { Viewport } from '@embedpdf/plugin-viewport/react';
import { Scroller, useScroll } from '@embedpdf/plugin-scroll/react';
import { DocumentContent, useActiveDocument } from '@embedpdf/plugin-document-manager/react';
import { useZoom, ZoomMode, ZoomGestureWrapper } from '@embedpdf/plugin-zoom/react';
import { ThumbnailsPane, ThumbImg } from '@embedpdf/plugin-thumbnail/react';
import { ZoomIn, ZoomOut, ChevronLeft, ChevronRight, MoveHorizontal, Maximize2, SquarePen, X, PanelLeft, MousePointer2, Ruler, Pentagon, Hash, Scaling, Magnet } from 'lucide-react';
import { engineOptions, makeViewerPlugins } from '@/lib/viewerEngine/embedEngine';
import { displayRotationFor, inverseRotatePctPoint } from '@/lib/viewerEngine/pageRotation';
import { clickToFill } from '@/lib/clickToFillApi';
import { DEFAULT_COUNT_TYPES } from '@/lib/measurements';
import { uncalibratedScale } from '@/lib/measureGeometry';
import PageOverlayHost from './PageOverlayHost';
import CalibrateDialog from './CalibrateDialog';
import CountLegendPanel from './CountLegendPanel';

// Measurement tool palette (Phase 3). 'select' exists so committed measurements
// can be picked (→ delete affordance); drawing keys 2/3/6 match the hotkeys.
const MEASURE_TOOLS = [
  { id: 'select', Icon: MousePointer2, title: 'Žymėti matavimą' },
  { id: 'distance', Icon: Ruler, title: 'Atstumas (2)' },
  { id: 'area', Icon: Pentagon, title: 'Plotas (3)' },
  { id: 'count', Icon: Hash, title: 'Skaičiuoti (6)' },
  { id: 'calibrate', Icon: Scaling, title: 'Kalibruoti mastelį' },
];

function Toolbar({ documentId, totalPages, focusedRoomNr, fillFor, onStartFill, onCancelFill, railOpen, onToggleThumbs, measureTool, onMeasureTool, snapEnabled, onToggleSnap, orthoEnabled, onToggleOrtho }) {
  const { state: zoom, provides: zoomApi } = useZoom(documentId);
  const { state: scroll, provides: scrollApi } = useScroll(documentId);
  const pct = typeof zoom?.currentZoomLevel === 'number' ? Math.round(zoom.currentZoomLevel * 100) : 100;
  const cur = scroll?.currentPage ?? 1;
  // scroll.totalPages is a scroll metric, not the page count — use the document's pageCount.
  const total = totalPages || 1;
  const btn = 'p-1 rounded hover:bg-[#efece6] disabled:opacity-40 disabled:hover:bg-transparent';
  const pressed = 'p-1 rounded bg-[#eef4fb] text-[#2a6fb5]';
  const canFill = focusedRoomNr != null && onStartFill;
  return (
    <div className="h-9 shrink-0 border-b border-[#e6e2da] bg-[#fbfaf7] px-3 flex items-center gap-1 text-[12px] text-[#4a4640]">
      <button
        className={btn + (railOpen ? ' bg-[#efece6] text-[#2a6fb5]' : '')}
        title="Puslapių juosta (T)"
        onClick={onToggleThumbs}
      ><PanelLeft className="w-4 h-4" /></button>
      <span className="w-px h-4 bg-[#e0dcd3] mx-1.5" />
      <button className={btn} title="Ankstesnis puslapis (PgUp)" disabled={cur <= 1} onClick={() => scrollApi?.scrollToPreviousPage()}><ChevronLeft className="w-4 h-4" /></button>
      <span className="mono tabular px-1 whitespace-nowrap">psl. {cur} / {total}</span>
      <button className={btn} title="Kitas puslapis (PgDn)" disabled={cur >= total} onClick={() => scrollApi?.scrollToNextPage()}><ChevronRight className="w-4 h-4" /></button>
      <span className="w-px h-4 bg-[#e0dcd3] mx-1.5" />
      <button className={btn} title="Tolinti (−)" onClick={() => zoomApi?.zoomOut()}><ZoomOut className="w-4 h-4" /></button>
      <span className="mono tabular w-11 text-center">{pct}%</span>
      <button className={btn} title="Artinti (+)" onClick={() => zoomApi?.zoomIn()}><ZoomIn className="w-4 h-4" /></button>
      <span className="w-px h-4 bg-[#e0dcd3] mx-1.5" />
      <button className={btn} title="Pritaikyti plotį (1)" onClick={() => zoomApi?.requestZoom(ZoomMode.FitWidth)}><MoveHorizontal className="w-4 h-4" /></button>
      <button className={btn} title="Visas puslapis (0)" onClick={() => zoomApi?.requestZoom(ZoomMode.FitPage)}><Maximize2 className="w-4 h-4" /></button>
      {onMeasureTool && (
        <>
          <span className="w-px h-4 bg-[#e0dcd3] mx-1.5" />
          {MEASURE_TOOLS.map(({ id, Icon, title }) => (
            <button
              key={id}
              className={measureTool === id ? pressed : btn}
              title={title}
              aria-pressed={measureTool === id}
              onClick={() => onMeasureTool(id)}
            ><Icon className="w-4 h-4" /></button>
          ))}
          <span className="w-px h-4 bg-[#e0dcd3] mx-1.5" />
          <button
            className={snapEnabled ? pressed : btn}
            title="Pritraukti prie taškų"
            aria-pressed={!!snapEnabled}
            onClick={onToggleSnap}
          ><Magnet className="w-4 h-4" /></button>
          <button
            className={(orthoEnabled ? pressed : btn) + ' w-7'}
            title="Statmenai (Shift)"
            aria-pressed={!!orthoEnabled}
            onClick={onToggleOrtho}
          ><span className="mono text-[10px] leading-none">90°</span></button>
        </>
      )}
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
            /* Armed: pressed button + X cancel. The click hint lives in the status bar. */
            <span className="inline-flex items-center gap-1">
              <button
                className="inline-flex items-center gap-1 px-2 py-1 rounded bg-[#eef4fb] border border-[#cfe0f2] text-[#2a6fb5]"
                title={`Taisyti patalpos ${fillFor} zoną — spustelėkite plane`}
                onClick={onCancelFill}
              >
                <SquarePen className="w-3.5 h-3.5" />
                <span>Taisyti zoną</span>
              </button>
              <button
                className="p-1 rounded hover:bg-[#efece6]"
                title="Atšaukti (Esc)"
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

// Human scale text for the status bar. PageScale stores metres of reality per
// PDF point; 1 pt = 1/72 inch of paper, so ratio = mpp / (0.0254/72). A named
// label (e.g. standard "1:50") wins over the computed ratio.
function scaleStatusText(pageScale) {
  if (!pageScale?.calibrated) return 'Mastelis: nekalibruotas';
  if (pageScale.label) return `Mastelis: ${pageScale.label}`;
  const mpp = pageScale.metersPerPointX || 0;
  const ratio = mpp > 0 ? Math.round((mpp * 72) / 0.0254) : 0;
  return ratio > 0 ? `Mastelis: 1:${ratio}` : 'Mastelis: kalibruotas';
}

/**
 * StatusBar — bottom h-6 strip: page/zoom · sheet size in mm (+ ISO-A label) ·
 * fill-mode hint or the current page's calibrated scale.
 */
function StatusBar({ documentId, totalPages, pages, fillFor, measureScales }) {
  const { state: zoom } = useZoom(documentId);
  const { state: scroll } = useScroll(documentId);
  const pct = typeof zoom?.currentZoomLevel === 'number' ? Math.round(zoom.currentZoomLevel * 100) : 100;
  const cur = scroll?.currentPage ?? 1;
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
  return (
    <div className="h-6 shrink-0 bg-[#fbfaf7] border-t border-[#e6e2da] text-[11px] text-[#8a857d] px-3 flex items-center gap-3">
      <span className="mono tabular whitespace-nowrap">psl. {cur} / {totalPages || 1} · {pct}%</span>
      {sheet && <span className="mono tabular whitespace-nowrap">{sheet}</span>}
      <span className={`ml-auto whitespace-nowrap ${fillFor != null ? 'text-[#2a6fb5]' : (pageScale?.calibrated ? 'text-[#4a4640]' : '')}`}>
        {fillFor != null ? `Spustelėkite patalpos ${fillFor} viduje` : scaleText}
      </span>
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
  const cur = scroll?.currentPage ?? 1;
  return (
    <aside className="w-[148px] shrink-0 bg-[#fbfaf7] border-r border-[#e6e2da]">
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
                className={`bg-white rounded-[2px] ${isCurrent ? 'ring-2 ring-[#2a6fb5]' : 'ring-1 ring-[#e6e2da] group-hover:ring-[#c9c4ba]'}`}
              />
              <span
                style={{ height: m.labelHeight, lineHeight: `${m.labelHeight}px` }}
                className={`mono tabular text-[10px] ${isCurrent ? 'text-[#2a6fb5]' : 'text-[#8a857d]'}`}
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
 * ViewerHotkeys — the viewer keyboard contract (Task 2.2 + 3.3), one window
 * keydown listener. Guarded: typing surfaces (input/textarea/select/content-
 * Editable) and browser combos (meta/ctrl) are never intercepted.
 *   +/= zoom in · − zoom out · 0 fit page · 1 fit width ·
 *   ]/PageDown next page · [/PageUp prev page · T thumbnail rail ·
 *   2 distance · 3 area · 6 count (measure tools; ignored while fill armed) ·
 *   Delete/Backspace delete the selected measurement (select mode only, so it
 *   can never collide with MeasureLayer's Backspace = remove-last-vertex) ·
 *   Esc chain: measure (close calibration dialog / drop tool) → cancel
 *   fill-mode → clear focused room.
 */
function ViewerHotkeys({ documentId, fillArmed, onCancelFill, onClearFocus, onToggleThumbs, onMeasureToolKey, onMeasureEscape, canDeleteSelected, onDeleteSelected }) {
  const { provides: zoomApi } = useZoom(documentId);
  const { provides: scrollApi } = useScroll(documentId);
  useEffect(() => {
    const onKeyDown = (e) => {
      const t = e.target;
      if (t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.tagName === 'SELECT' || t.isContentEditable)) return;
      if (e.metaKey || e.ctrlKey) return; // leave browser/app combos alone
      switch (e.key) {
        case '+': case '=': e.preventDefault(); zoomApi?.zoomIn(); break;
        case '-': e.preventDefault(); zoomApi?.zoomOut(); break;
        case '0': e.preventDefault(); zoomApi?.requestZoom(ZoomMode.FitPage); break;
        case '1': e.preventDefault(); zoomApi?.requestZoom(ZoomMode.FitWidth); break;
        case '2': if (!fillArmed && onMeasureToolKey) { e.preventDefault(); onMeasureToolKey('distance'); } break;
        case '3': if (!fillArmed && onMeasureToolKey) { e.preventDefault(); onMeasureToolKey('area'); } break;
        case '6': if (!fillArmed && onMeasureToolKey) { e.preventDefault(); onMeasureToolKey('count'); } break;
        case ']': case 'PageDown': e.preventDefault(); scrollApi?.scrollToNextPage(); break;
        case '[': case 'PageUp': e.preventDefault(); scrollApi?.scrollToPreviousPage(); break;
        case 't': case 'T': e.preventDefault(); onToggleThumbs?.(); break;
        case 'Delete': case 'Backspace':
          if (canDeleteSelected) { e.preventDefault(); onDeleteSelected?.(); }
          break;
        case 'Escape':
          if (onMeasureEscape?.()) e.preventDefault();
          else if (fillArmed) { e.preventDefault(); onCancelFill?.(); }
          else onClearFocus?.();
          break;
        default: break;
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [zoomApi, scrollApi, fillArmed, onCancelFill, onClearFocus, onToggleThumbs, onMeasureToolKey, onMeasureEscape, canDeleteSelected, onDeleteSelected]);
  return null;
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

function ViewerInner({ rooms, focusedRoom, hiddenRoomNrs, hoveredRoomNrExternal, onRoomZoneClick, onPagePoint, onClearFocus, projectId, pdfBlob, onRoomPolygonFill, initialMeasurements, initialMeasureScales, onMeasureDataChange }) {
  const { activeDocumentId } = useActiveDocument();
  const focusedRoomNr = focusedRoom?.nr ?? null;
  // `fillFor` = the room nr currently armed for "Taisyti zoną" click-to-fill.
  const [fillFor, setFillFor] = useState(null);
  // Drop the armed room if focus changes away (avoid filling the wrong room).
  useEffect(() => { setFillFor(null); }, [focusedRoomNr]);

  // ---- Measurement subsystem (Phase 3) ------------------------------------
  // Tool: null (idle) | 'select' | 'distance' | 'area' | 'count' | 'calibrate'.
  // Measurements + per-page scales in PDF-point space (see MeasureLayer);
  // hydrated from the project, persisted back via onMeasureDataChange.
  const [measureTool, setMeasureTool] = useState(null);
  const [measurements, setMeasurements] = useState(() => initialMeasurements || []);
  const [measureScales, setMeasureScales] = useState(() => initialMeasureScales || {});
  const [snapEnabled, setSnapEnabled] = useState(false);
  const [orthoEnabled, setOrthoEnabled] = useState(false);
  const [activeCountTypeId, setActiveCountTypeId] = useState(DEFAULT_COUNT_TYPES[0]?.id ?? null);
  const [selectedMeasureId, setSelectedMeasureId] = useState(null);
  // Pending 2-point calibration pick: { pageNr, a, b } | null → CalibrateDialog.
  const [calibRequest, setCalibRequest] = useState(null);
  // Fill-mode and measure tools are mutually exclusive pointer owners.
  const armMeasureTool = (tool) => {
    setFillFor(null);
    setMeasureTool((cur) => {
      const next = cur === tool ? null : tool;
      if (next == null) setSelectedMeasureId(null);
      return next;
    });
  };
  const startFill = (nr) => { setMeasureTool(null); setSelectedMeasureId(null); setFillFor(nr); };
  const deleteMeasurement = (id) => {
    if (id == null) return;
    setMeasurements((prev) => prev.filter((m) => m.id !== id));
    setSelectedMeasureId((cur) => (cur === id ? null : cur));
  };
  // Esc chain, measure segment: close the calibration dialog first, then drop
  // the active tool (MeasureLayer resets its own draft when the tool changes).
  const measureEscape = () => {
    if (calibRequest) { setCalibRequest(null); return true; }
    if (measureTool != null) { setMeasureTool(null); setSelectedMeasureId(null); return true; }
    return false;
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
  useEffect(() => {
    if (!measureDirtyRef.current) { measureDirtyRef.current = true; return undefined; } // skip mount
    const t = setTimeout(() => onMeasureDataChangeRef.current?.({ measurements, measureScales }), 600);
    return () => clearTimeout(t);
  }, [measurements, measureScales]);
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

  const handlePagePoint = async (pt) => {
    // Not in fill mode → normal viewing: forward to any external consumer.
    if (fillFor == null) {
      onPagePoint?.(pt);
      return;
    }
    const { x, y, pageIndex, pageWidth, pageHeight, pageRotation } = pt;
    if (!pageWidth || !pageHeight) { setFillFor(null); return; }
    // BUGFIX (2026-07-02): the click lands in DISPLAY space (page shown with
    // PDFium's /Rotate complement — see displayRotationFor), but the
    // click-to-fill backend rasters the UNROTATED mediabox page (pdf2image
    // ignores /Rotate). Inverse-rotate the pct so the flood-fill seed lands
    // where the user actually clicked. Zones render correctly because
    // PageOverlayHost applies the FORWARD transform with the same helper.
    const rot = displayRotationFor(pageRotation ?? 0);
    const [mx, my] = inverseRotatePctPoint(x / pageWidth, y / pageHeight, rot);
    try {
      const data = await clickToFill({
        projectId,
        pageNr: pageIndex + 1,
        clickXPct: mx,
        clickYPct: my,
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
      {({ isLoaded, documentState }) => {
        if (!isLoaded) return <div className="p-5 text-sm text-muted-foreground">Kraunamas dokumentas…</div>;
        const totalPages = documentState?.document?.pageCount ?? documentState?.pageCount ?? documentState?.pages?.length ?? null;
        // No explicit user choice yet → open by default on multi-page documents.
        const railOpen = thumbsPref ?? ((totalPages ?? 1) > 1);
        return (
        <div className="flex flex-col h-full">
          <Toolbar
            documentId={activeDocumentId}
            totalPages={totalPages}
            focusedRoomNr={onRoomPolygonFill ? focusedRoomNr : null}
            fillFor={fillFor}
            onStartFill={startFill}
            onCancelFill={() => setFillFor(null)}
            railOpen={railOpen}
            onToggleThumbs={() => setRailOpen(!railOpen)}
            measureTool={measureTool}
            onMeasureTool={armMeasureTool}
            snapEnabled={snapEnabled}
            onToggleSnap={() => setSnapEnabled((v) => !v)}
            orthoEnabled={orthoEnabled}
            onToggleOrtho={() => setOrthoEnabled((v) => !v)}
          />
          <FocusScroller documentId={activeDocumentId} focusedRoom={focusedRoom} />
          <ViewerHotkeys
            documentId={activeDocumentId}
            fillArmed={fillFor != null}
            onCancelFill={() => setFillFor(null)}
            onClearFocus={onClearFocus}
            onToggleThumbs={() => setRailOpen(!railOpen)}
            onMeasureToolKey={armMeasureTool}
            onMeasureEscape={measureEscape}
            canDeleteSelected={measureTool === 'select' && selectedMeasureId != null}
            onDeleteSelected={() => deleteMeasurement(selectedMeasureId)}
          />
          <div className="relative flex flex-1 min-h-0">
            {railOpen && <ThumbnailRail documentId={activeDocumentId} />}
            <ZoomGestureWrapper documentId={activeDocumentId} style={{ flex: 1, minHeight: 0, minWidth: 0 }}>
              <Viewport documentId={activeDocumentId} style={{ height: '100%', background: '#e9e7e2' }}>
                <Scroller
                  documentId={activeDocumentId}
                  renderPage={(layout) => (
                    <PageOverlayHost
                      documentId={activeDocumentId}
                      layout={layout}
                      rooms={rooms}
                      pageRotation={documentState?.document?.pages?.[layout.pageIndex]?.rotation ?? 0}
                      pageSizePt={documentState?.document?.pages?.[layout.pageIndex]?.size ?? null}
                      focusedRoomNr={focusedRoomNr}
                      hiddenRoomNrs={hiddenRoomNrs}
                      hoveredRoomNrExternal={hoveredRoomNrExternal}
                      onRoomZoneClick={onRoomZoneClick}
                      onPagePoint={handlePagePoint}
                      measureTool={measureTool}
                      measurements={measurements}
                      measureScale={measureScales[layout.pageNumber] || null}
                      snapEnabled={snapEnabled}
                      orthoEnabled={orthoEnabled}
                      countTypes={DEFAULT_COUNT_TYPES}
                      activeCountTypeId={activeCountTypeId}
                      selectedMeasureId={selectedMeasureId}
                      onMeasureCommit={(m) => setMeasurements((prev) => [...prev, m])}
                      onMeasureCalibrate={(pageNr, a, b) => setCalibRequest({ pageNr, a, b })}
                      onMeasureSelect={setSelectedMeasureId}
                      onMeasureDelete={deleteMeasurement}
                    />
                  )}
                />
              </Viewport>
            </ZoomGestureWrapper>
            {/* Floating count-type legend while the count tool is armed. */}
            {measureTool === 'count' && (
              <div
                className="absolute top-2 z-30 w-60 shadow-lg"
                style={{ left: railOpen ? 156 : 8 }}
              >
                <CountLegendPanel
                  countTypes={DEFAULT_COUNT_TYPES}
                  activeCountTypeId={activeCountTypeId}
                  onSelectType={setActiveCountTypeId}
                  tallies={countTallies}
                />
              </div>
            )}
          </div>
          <StatusBar
            documentId={activeDocumentId}
            totalPages={totalPages}
            pages={documentState?.document?.pages}
            fillFor={fillFor}
            measureScales={measureScales}
          />
          <CalibrateDialog
            request={calibRequest}
            numPages={totalPages}
            currentScale={calibRequest ? (measureScales[calibRequest.pageNr] || uncalibratedScale()) : null}
            onConfirm={(scale, pages) => {
              setMeasureScales((prev) => {
                const next = { ...prev };
                for (const p of (pages || [calibRequest.pageNr])) next[p] = scale;
                return next;
              });
            }}
            onClose={() => setCalibRequest(null)}
          />
        </div>
        );
      }}
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
  onClearFocus = null,
  projectId = null,
  pdfBlob = null,
  onRoomPolygonFill = null,
  // Measurement persistence (Phase 3): hydrate from the project, report back
  // debounced ({ measurements, measureScales }) for the project save flow.
  initialMeasurements = null,
  initialMeasureScales = null,
  onMeasureDataChange = null,
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
          onClearFocus={onClearFocus}
          projectId={projectId}
          pdfBlob={pdfBlob}
          onRoomPolygonFill={onRoomPolygonFill}
          initialMeasurements={initialMeasurements}
          initialMeasureScales={initialMeasureScales}
          onMeasureDataChange={onMeasureDataChange}
        />
      </EmbedPDF>
    </div>
  );
}
