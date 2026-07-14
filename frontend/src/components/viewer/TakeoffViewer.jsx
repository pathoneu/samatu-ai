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
import { toast } from 'sonner';
import { EmbedPDF } from '@embedpdf/core/react';
import { usePdfiumEngine } from '@embedpdf/engines/react';
import { Viewport } from '@embedpdf/plugin-viewport/react';
import { Scroller, useScroll } from '@embedpdf/plugin-scroll/react';
import { DocumentContent, useActiveDocument } from '@embedpdf/plugin-document-manager/react';
import { useZoom, ZoomMode, ZoomGestureWrapper } from '@embedpdf/plugin-zoom/react';
import { ThumbnailsPane, ThumbImg } from '@embedpdf/plugin-thumbnail/react';
import { useSearch } from '@embedpdf/plugin-search/react';
import { usePrint } from '@embedpdf/plugin-print/react';
import { useExport } from '@embedpdf/plugin-export/react';
import { ZoomIn, ZoomOut, ChevronLeft, ChevronRight, ChevronUp, ChevronDown, MoveHorizontal, Maximize2, SquarePen, X, PanelLeft, MousePointer2, Ruler, Pentagon, Spline, Hash, Scaling, Magnet, Search, Printer, Download, Layers } from 'lucide-react';
import { engineOptions, makeViewerPlugins } from '@/lib/viewerEngine/embedEngine';
import { ROOM_POLYGON_FILLS_DEFAULT_VISIBLE } from '@/lib/roomZones';
import { displayRotationFor, rotatePctPoint } from '@/lib/viewerEngine/pageRotation';
import { clickToFill } from '@/lib/clickToFillApi';
import { DEFAULT_COUNT_TYPES } from '@/lib/measurements';
import { uncalibratedScale } from '@/lib/measureGeometry';
import PageOverlayHost from './PageOverlayHost';
import CalibrateDialog from './CalibrateDialog';
import CountLegendPanel from './CountLegendPanel';

// Measurement tool palette (Phase 3). 'select' exists so committed measurements
// can be picked (→ delete affordance); drawing keys 2/3/4/6 match the hotkeys.
const MEASURE_TOOLS = [
  { id: 'select', Icon: MousePointer2, title: 'Žymėti matavimą' },
  { id: 'distance', Icon: Ruler, title: 'Atstumas (2)' },
  { id: 'area', Icon: Pentagon, title: 'Plotas (3)' },
  { id: 'perimeter', Icon: Spline, title: 'Perimetras (4)' },
  { id: 'count', Icon: Hash, title: 'Skaičiuoti (6)' },
  { id: 'calibrate', Icon: Scaling, title: 'Kalibruoti mastelį' },
];

// The page the user is actually LOOKING at. The scroll plugin's `currentPage`
// goes stale under wheel-scrolling (audit P1: "psl. 2" while page 3 fills the
// screen; fit then yanks the viewport back) while pageVisibilityMetrics stay
// live — virtualization depends on them — so derive from the metrics and fall
// back to the plugin's field.
function visiblePageOf(scroll) {
  const m = scroll?.pageVisibilityMetrics;
  if (Array.isArray(m) && m.length) {
    let best = m[0];
    for (const x of m) if (x.visiblePercentage > best.visiblePercentage) best = x;
    return best.pageNumber;
  }
  return scroll?.currentPage ?? 1;
}

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
  const btn = 'p-1 rounded text-[hsl(var(--viewer-chrome-foreground))] hover:bg-[hsl(var(--viewer-chrome-hover))] disabled:opacity-40 disabled:hover:bg-transparent';
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
        className="w-44 h-6 px-2 rounded border border-[hsl(var(--viewer-chrome-border))] bg-[hsl(var(--viewer-chrome-muted))] text-[12px] text-[hsl(var(--viewer-chrome-foreground))] placeholder:text-[hsl(var(--viewer-chrome-foreground)/0.45)] focus:outline-none focus:border-[hsl(var(--viewer-chrome-active))]"
      />
      {hasQuery && (
        <span className="mono tabular text-[11px] text-[hsl(var(--viewer-chrome-foreground)/0.65)] whitespace-nowrap px-0.5">
          {total > 0 ? `${(search.activeResultIndex ?? 0) + 1} / ${total}` : '0 / 0'}
        </span>
      )}
      <button className={btn} title="Ankstesnis rezultatas (Shift+Enter)" disabled={total === 0} onClick={() => searchApi?.previousResult()}><ChevronUp className="w-4 h-4" /></button>
      <button className={btn} title="Kitas rezultatas (Enter)" disabled={total === 0} onClick={() => searchApi?.nextResult()}><ChevronDown className="w-4 h-4" /></button>
      {noHits && (
        <span className="absolute left-0 top-full mt-2 z-40 px-2 py-1 rounded border border-[hsl(var(--viewer-chrome-border))] bg-[hsl(var(--viewer-chrome))] text-[11px] text-[hsl(var(--viewer-chrome-foreground)/0.65)] whitespace-nowrap shadow-sm">
          Rezultatų nėra — PDF gali neturėti teksto sluoksnio
        </span>
      )}
    </span>
  );
}

function Toolbar({ documentId, totalPages, focusedRoomNr, fillFor, onStartFill, onCancelFill, railOpen, onToggleThumbs, measureTool, onMeasureTool, snapEnabled, onToggleSnap, orthoEnabled, onToggleOrtho, searchOpen, onToggleSearch, onCloseSearch, zoneFillsVisible, onToggleZoneFills }) {
  const { state: zoom, provides: zoomApi } = useZoom(documentId);
  const { state: scroll, provides: scrollApi } = useScroll(documentId);
  const { provides: printApi } = usePrint(documentId);
  const { provides: exportApi } = useExport(documentId);
  const pct = typeof zoom?.currentZoomLevel === 'number' ? Math.round(zoom.currentZoomLevel * 100) : 100;
  const cur = visiblePageOf(scroll);
  // scroll.totalPages is a scroll metric, not the page count — use the document's pageCount.
  const total = totalPages || 1;
  // Fit actions consult the PLUGIN's currentPage, which can lag the viewport
  // (audit P1: fit yanked the view back to a stale page) — sync it first.
  const syncPageThen = (fn) => {
    if (cur !== (scroll?.currentPage ?? cur)) scrollApi?.scrollToPage({ pageNumber: cur });
    fn();
  };
  const btn = 'p-1 rounded text-[hsl(var(--viewer-chrome-foreground))] hover:bg-[hsl(var(--viewer-chrome-hover))] disabled:opacity-40 disabled:hover:bg-transparent';
  const pressed = 'p-1 rounded bg-[hsl(var(--viewer-chrome-active)/0.18)] text-[hsl(var(--viewer-chrome-active))]';
  const canFill = focusedRoomNr != null && onStartFill;
  return (
    <div className="h-9 shrink-0 border-b border-[hsl(var(--viewer-chrome-border))] bg-[hsl(var(--viewer-chrome))] px-3 flex items-center gap-1 text-[12px] text-[hsl(var(--viewer-chrome-foreground))]">
      <button
        className={btn + (railOpen ? ' bg-[hsl(var(--viewer-chrome-hover))] text-[hsl(var(--viewer-chrome-active))]' : '')}
        title="Puslapių juosta (T)"
        onClick={onToggleThumbs}
      ><PanelLeft className="w-4 h-4" /></button>
      <span className="w-px h-4 bg-[hsl(var(--viewer-chrome-border))] mx-1.5" />
      <button className={btn} title="Ankstesnis puslapis (PgUp)" disabled={cur <= 1} onClick={() => syncPageThen(() => scrollApi?.scrollToPreviousPage())}><ChevronLeft className="w-4 h-4" /></button>
      <span className="mono tabular px-1 whitespace-nowrap">psl. {cur} / {total}</span>
      <button className={btn} title="Kitas puslapis (PgDn)" disabled={cur >= total} onClick={() => syncPageThen(() => scrollApi?.scrollToNextPage())}><ChevronRight className="w-4 h-4" /></button>
      <span className="w-px h-4 bg-[hsl(var(--viewer-chrome-border))] mx-1.5" />
      <button className={btn} title="Tolinti (−)" onClick={() => zoomApi?.zoomOut()}><ZoomOut className="w-4 h-4" /></button>
      <span className="mono tabular w-11 text-center">{pct}%</span>
      <button className={btn} title="Artinti (+)" onClick={() => zoomApi?.zoomIn()}><ZoomIn className="w-4 h-4" /></button>
      <span className="w-px h-4 bg-[hsl(var(--viewer-chrome-border))] mx-1.5" />
      <button className={btn} title="Pritaikyti plotį (1)" onClick={() => syncPageThen(() => zoomApi?.requestZoom(ZoomMode.FitWidth))}><MoveHorizontal className="w-4 h-4" /></button>
      <button className={btn} title="Visas puslapis (0)" onClick={() => syncPageThen(() => zoomApi?.requestZoom(ZoomMode.FitPage))}><Maximize2 className="w-4 h-4" /></button>
      {onToggleZoneFills && (
        <>
          <span className="w-px h-4 bg-[hsl(var(--viewer-chrome-border))] mx-1.5" />
          {/* Zone-fill layer toggle. Founder decision 2026-07-11: markers are the
              default; this re-enables the filled room polygons. */}
          <button
            className={zoneFillsVisible ? pressed : btn}
            title={zoneFillsVisible ? 'Patalpų zonų užpildai: įjungta (rodyti žymeklius)' : 'Patalpų zonų užpildai: išjungta (rodyti užpildus)'}
            aria-pressed={!!zoneFillsVisible}
            onClick={onToggleZoneFills}
          ><Layers className="w-4 h-4" /></button>
        </>
      )}
      {onMeasureTool && (
        <>
          <span className="w-px h-4 bg-[hsl(var(--viewer-chrome-border))] mx-1.5" />
          {MEASURE_TOOLS.map(({ id, Icon, title }) => (
            <button
              key={id}
              className={measureTool === id ? pressed : btn}
              title={title}
              aria-pressed={measureTool === id}
              onClick={() => onMeasureTool(id)}
            ><Icon className="w-4 h-4" /></button>
          ))}
          <span className="w-px h-4 bg-[hsl(var(--viewer-chrome-border))] mx-1.5" />
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
          <span className="w-px h-4 bg-[hsl(var(--viewer-chrome-border))] mx-1.5" />
          {fillFor == null ? (
            <button
              className="inline-flex items-center gap-1 px-2 py-1 rounded border border-[hsl(var(--viewer-chrome-border))] hover:bg-[hsl(var(--viewer-chrome-hover))] text-[hsl(var(--viewer-chrome-foreground))]"
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
                className="inline-flex items-center gap-1 px-2 py-1 rounded bg-[hsl(var(--viewer-chrome-active)/0.18)] border border-[hsl(var(--viewer-chrome-active)/0.4)] text-[hsl(var(--viewer-chrome-active))]"
                title={`Taisyti patalpos ${fillFor} zoną — spustelėkite plane`}
                onClick={onCancelFill}
              >
                <SquarePen className="w-3.5 h-3.5" />
                <span>Taisyti zoną</span>
              </button>
              <button
                className="p-1 rounded text-[hsl(var(--viewer-chrome-foreground))] hover:bg-[hsl(var(--viewer-chrome-hover))]"
                title="Atšaukti (Esc)"
                onClick={onCancelFill}
              >
                <X className="w-3.5 h-3.5" />
              </button>
            </span>
          )}
        </>
      )}
      {/* Right group: search + print + download. */}
      <div className="ml-auto flex items-center gap-1">
        {searchOpen && <SearchBox documentId={documentId} onClose={onCloseSearch} />}
        <button
          className={searchOpen ? pressed : btn}
          title="Paieška (Ctrl+F)"
          aria-pressed={!!searchOpen}
          onClick={onToggleSearch}
        ><Search className="w-4 h-4" /></button>
        <span className="w-px h-4 bg-[hsl(var(--viewer-chrome-border))] mx-1.5" />
        <button className={btn} title="Spausdinti (Ctrl+P)" disabled={!printApi} onClick={() => printApi?.print()}><Printer className="w-4 h-4" /></button>
        <button className={btn} title="Atsisiųsti PDF" disabled={!exportApi} onClick={() => exportApi?.download()}><Download className="w-4 h-4" /></button>
      </div>
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
function StatusBar({ documentId, totalPages, pages, fillFor, fillBusy = false, measureScales }) {
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
  return (
    <div className="h-6 shrink-0 bg-[hsl(var(--viewer-chrome))] border-t border-[hsl(var(--viewer-chrome-border))] text-[11px] text-[hsl(var(--viewer-chrome-foreground)/0.65)] px-3 flex items-center gap-3">
      <span className="mono tabular whitespace-nowrap">psl. {cur} / {totalPages || 1} · {pct}%</span>
      {sheet && <span className="mono tabular whitespace-nowrap">{sheet}</span>}
      <span className={`ml-auto whitespace-nowrap ${fillFor != null ? 'text-[hsl(var(--viewer-chrome-active))]' : (pageScale?.calibrated ? 'text-[hsl(var(--viewer-chrome-foreground))]' : '')}`}>
        {fillFor != null
          ? (fillBusy ? `Ieškoma patalpos ${fillFor} kontūro…` : `Spustelėkite patalpos ${fillFor} viduje`)
          : scaleText}
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
  const cur = visiblePageOf(scroll);
  return (
    <aside className="w-[148px] shrink-0 bg-[hsl(var(--viewer-chrome))] border-r border-[hsl(var(--viewer-chrome-border))]">
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
                className={`bg-white rounded-[2px] ${isCurrent ? 'ring-2 ring-[hsl(var(--viewer-chrome-active))]' : 'ring-1 ring-[hsl(var(--viewer-chrome-border))] group-hover:ring-[hsl(var(--viewer-chrome-foreground)/0.35)]'}`}
              />
              <span
                style={{ height: m.labelHeight, lineHeight: `${m.labelHeight}px` }}
                className={`mono tabular text-[10px] ${isCurrent ? 'text-[hsl(var(--viewer-chrome-active))]' : 'text-[hsl(var(--viewer-chrome-foreground)/0.65)]'}`}
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
 *   2 distance · 3 area · 4 perimeter · 6 count (measure tools; ignored while fill armed) ·
 *   Delete/Backspace delete the selected measurement (select mode only, so it
 *   can never collide with MeasureLayer's Backspace = remove-last-vertex) ·
 *   Ctrl/Cmd+F, / or F open search · Ctrl/Cmd+P print · Esc chain: close search
 *   → measure (close calibration dialog / drop tool) → cancel fill-mode →
 *   clear focused room. (When focus is IN the search input, its own onKeyDown
 *   handles Esc — the input guard below keeps this listener out of typing
 *   surfaces.)
 */
function ViewerHotkeys({ documentId, fillArmed, onCancelFill, onClearFocus, onToggleThumbs, onMeasureToolKey, onMeasureEscape, canDeleteSelected, onDeleteSelected, onOpenSearch, onSearchEscape }) {
  const { provides: zoomApi } = useZoom(documentId);
  const { state: scroll, provides: scrollApi } = useScroll(documentId);
  const { provides: printApi } = usePrint(documentId);
  // Scroll state through a ref so the window listener isn't re-bound on every
  // scroll tick — only the fit keys ('0'/'1') read it, to pre-sync the plugin's
  // lagging currentPage to the page actually on screen before fitting.
  const scrollRef = useRef(scroll);
  useEffect(() => { scrollRef.current = scroll; });
  useEffect(() => {
    const fitTo = (mode) => {
      const vp = visiblePageOf(scrollRef.current);
      if (vp !== (scrollRef.current?.currentPage ?? vp)) scrollApi?.scrollToPage({ pageNumber: vp });
      zoomApi?.requestZoom(mode);
    };
    const onKeyDown = (e) => {
      const t = e.target;
      if (t && (t.tagName === 'INPUT' || t.tagName === 'TEXTAREA' || t.tagName === 'SELECT' || t.isContentEditable)) return;
      if (e.metaKey || e.ctrlKey) {
        // Our explicit combos; everything else stays with the browser.
        if (!e.altKey && (e.key === 'f' || e.key === 'F') && onOpenSearch) { e.preventDefault(); onOpenSearch(); }
        else if (!e.altKey && (e.key === 'p' || e.key === 'P') && printApi) { e.preventDefault(); printApi.print(); }
        return;
      }
      switch (e.key) {
        case '+': case '=': e.preventDefault(); zoomApi?.zoomIn(); break;
        case '-': e.preventDefault(); zoomApi?.zoomOut(); break;
        case '0': e.preventDefault(); fitTo(ZoomMode.FitPage); break;
        case '1': e.preventDefault(); fitTo(ZoomMode.FitWidth); break;
        case '2': if (!fillArmed && onMeasureToolKey) { e.preventDefault(); onMeasureToolKey('distance'); } break;
        case '3': if (!fillArmed && onMeasureToolKey) { e.preventDefault(); onMeasureToolKey('area'); } break;
        case '4': if (!fillArmed && onMeasureToolKey) { e.preventDefault(); onMeasureToolKey('perimeter'); } break;
        case '6': if (!fillArmed && onMeasureToolKey) { e.preventDefault(); onMeasureToolKey('count'); } break;
        case ']': case 'PageDown': e.preventDefault(); scrollApi?.scrollToNextPage(); break;
        case '[': case 'PageUp': e.preventDefault(); scrollApi?.scrollToPreviousPage(); break;
        case 't': case 'T': e.preventDefault(); onToggleThumbs?.(); break;
        case '/': case 'f': case 'F': if (onOpenSearch) { e.preventDefault(); onOpenSearch(); } break;
        case 'Delete': case 'Backspace':
          if (canDeleteSelected) { e.preventDefault(); onDeleteSelected?.(); }
          break;
        case 'Escape':
          if (onSearchEscape?.()) e.preventDefault();
          else if (onMeasureEscape?.()) e.preventDefault();
          else if (fillArmed) { e.preventDefault(); onCancelFill?.(); }
          else onClearFocus?.();
          break;
        default: break;
      }
    };
    window.addEventListener('keydown', onKeyDown);
    return () => window.removeEventListener('keydown', onKeyDown);
  }, [zoomApi, scrollApi, printApi, fillArmed, onCancelFill, onClearFocus, onToggleThumbs, onMeasureToolKey, onMeasureEscape, canDeleteSelected, onDeleteSelected, onOpenSearch, onSearchEscape]);
  return null;
}

// Scroll the viewport to a focused room's page when it changes (panel → canvas
// nav). Page-only jumps (Matavimai rows, provenance links) carry no room —
// fall back to the focusedPage prop so they scroll the Embed viewer too.
function FocusScroller({ documentId, focusedRoom, focusedPage }) {
  const { provides: scrollApi } = useScroll(documentId);
  const targetPage = focusedRoom?.puslapio_nr ?? focusedRoom?.page_nr ?? focusedPage ?? null;
  useEffect(() => {
    if (targetPage && scrollApi?.scrollToPage) {
      scrollApi.scrollToPage({ pageNumber: targetPage, behavior: 'smooth' });
    }
  }, [targetPage, scrollApi]);
  return null;
}

function ViewerInner({ rooms, focusedRoom, focusedPage, hiddenRoomNrs, hoveredRoomNrExternal, onRoomZoneClick, onPagePoint, onClearFocus, projectId, pdfBlob, onRoomPolygonFill, fillRequest, initialMeasurements, initialMeasureScales, onMeasureDataChange }) {
  const { activeDocumentId } = useActiveDocument();
  const focusedRoomNr = focusedRoom?.nr ?? null;
  // `fillFor` = the room nr currently armed for "Taisyti zoną" click-to-fill.
  const [fillFor, setFillFor] = useState(null);
  // Round-trip in flight (backend flood-fill takes ~3-6 s) — drives the status
  // hint so the user sees progress instead of a silent stall (audit P0).
  const [fillBusy, setFillBusy] = useState(false);
  // Drop the armed room if focus changes away (avoid filling the wrong room).
  useEffect(() => { setFillFor(null); }, [focusedRoomNr]);
  // Room layer presentation. Founder decision 2026-07-11: numbered markers by
  // default; the toolbar Layers toggle re-enables the filled polygon zones.
  const [zoneFillsVisible, setZoneFillsVisible] = useState(ROOM_POLYGON_FILLS_DEFAULT_VISIBLE);

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
  // Floating count legend collapse — it swallows placement clicks underneath.
  const [countLegendCollapsed, setCountLegendCollapsed] = useState(false);
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
  // External fill arming (review-queue pencil → "Taisyti zoną" armed here).
  // {nr, t} — t is a nonce so re-clicking the same room re-arms after Esc.
  useEffect(() => {
    if (fillRequest?.nr != null) startFill(fillRequest.nr);
  }, [fillRequest]);
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
  // ---- Text search (Task 4.1) ----------------------------------------------
  // Open/closed only — query + results live in SearchBox (its unmount ends the
  // plugin search session, clearing highlights).
  const [searchOpen, setSearchOpen] = useState(false);
  const searchEscape = () => {
    if (searchOpen) { setSearchOpen(false); return true; }
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
  // Latest unsaved payload — flushed on unmount so switching views inside the
  // 600 ms debounce window can no longer DROP the last measurement (P0-2).
  const pendingMeasureSaveRef = useRef(null);
  useEffect(() => {
    if (!measureDirtyRef.current) { measureDirtyRef.current = true; return undefined; } // skip mount
    pendingMeasureSaveRef.current = { measurements, measureScales };
    const t = setTimeout(() => {
      pendingMeasureSaveRef.current = null;
      onMeasureDataChangeRef.current?.({ measurements, measureScales });
    }, 600);
    return () => clearTimeout(t);
  }, [measurements, measureScales]);
  useEffect(() => () => {
    if (pendingMeasureSaveRef.current) {
      onMeasureDataChangeRef.current?.(pendingMeasureSaveRef.current);
    }
  }, []);
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
    if (fillFor == null) {
      // Plain canvas click (no fill, no measure tool): clear the focused-room
      // chip — a room stays "selected" only while the user means it (audit P2
      // sticky chip) — and forward to any external consumer. While a measure
      // tool owns the pointer, leave focus alone.
      if (measureTool == null) {
        onClearFocus?.();
        onPagePoint?.(pt);
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
      onRoomPolygonFill?.(fillFor, data);
      toast.success(`Patalpos ${fillFor} kontūras pažymėtas`);
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
            searchOpen={searchOpen}
            onToggleSearch={() => setSearchOpen((v) => !v)}
            onCloseSearch={() => setSearchOpen(false)}
            zoneFillsVisible={zoneFillsVisible}
            onToggleZoneFills={() => setZoneFillsVisible((v) => !v)}
          />
          <FocusScroller documentId={activeDocumentId} focusedRoom={focusedRoom} focusedPage={focusedPage} />
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
            onOpenSearch={() => setSearchOpen(true)}
            onSearchEscape={searchEscape}
          />
          <div className="relative flex flex-1 min-h-0">
            {railOpen && <ThumbnailRail documentId={activeDocumentId} />}
            {/* ZoomGestureWrapper must be INSIDE Viewport: useViewportElement()
                reads ViewportElementContext, whose Provider is rendered BY the
                Viewport component. As a parent it got null → setupZoomGestures
                never ran → no ctrl+wheel / pinch zoom (audit P2, root-caused
                2026-07-14 via defaultPrevented=false on a synthetic event). */}
            <Viewport documentId={activeDocumentId} style={{ flex: 1, minHeight: 0, minWidth: 0, background: 'hsl(var(--viewer-blueprint-bg))' }}>
              <ZoomGestureWrapper documentId={activeDocumentId}>
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
                      zoneFillsVisible={zoneFillsVisible}
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
              </ZoomGestureWrapper>
            </Viewport>
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
                  collapsed={countLegendCollapsed}
                  onToggleCollapse={() => setCountLegendCollapsed((v) => !v)}
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
  focusedPage = null,
  hiddenRoomNrs = null,
  hoveredRoomNrExternal = null,
  onRoomZoneClick = null,
  onPagePoint = null,
  onClearFocus = null,
  projectId = null,
  pdfBlob = null,
  onRoomPolygonFill = null,
  // External "arm click-to-fill for room nr" request: { nr, t } (t = nonce).
  fillRequest = null,
  // Download filename for the export button (defaults inside the engine).
  exportFileName = null,
  // Measurement persistence (Phase 3): hydrate from the project, report back
  // debounced ({ measurements, measureScales }) for the project save flow.
  initialMeasurements = null,
  initialMeasureScales = null,
  onMeasureDataChange = null,
}) {
  const { engine, isLoading, error } = usePdfiumEngine(engineOptions());
  const plugins = useMemo(
    () => (fileUrl ? makeViewerPlugins(fileUrl, exportFileName || undefined) : null),
    [fileUrl, exportFileName],
  );
  if (error) return <div className="p-5 text-sm text-red-600">Variklio klaida: {String(error.message || error)}</div>;
  if (isLoading || !engine || !plugins) return <div className="p-5 text-sm text-muted-foreground">Kraunamas PDF variklis…</div>;
  return (
    <div className="h-full">
      <EmbedPDF engine={engine} plugins={plugins}>
        <ViewerInner
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
          onRoomPolygonFill={onRoomPolygonFill}
          fillRequest={fillRequest}
          initialMeasurements={initialMeasurements}
          initialMeasureScales={initialMeasureScales}
          onMeasureDataChange={onMeasureDataChange}
        />
      </EmbedPDF>
    </div>
  );
}
