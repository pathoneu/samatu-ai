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
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
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
import { ZoomIn, ZoomOut, ChevronLeft, ChevronRight, ChevronUp, ChevronDown, MoveHorizontal, Maximize2, SquarePen, X, PanelLeft, MousePointer2, Ruler, Pentagon, Spline, Hash, Scaling, Search, Printer, Download, Layers } from 'lucide-react';
import { engineOptions, makeViewerPlugins } from '@/lib/viewerEngine/embedEngine';
import { ROOM_POLYGON_FILLS_DEFAULT_VISIBLE, roomPageOf } from '@/lib/roomZones';
import { displayRotationFor, normalizeRotation, rotatePctPoint } from '@/lib/viewerEngine/pageRotation';
import { clickToFill } from '@/lib/clickToFillApi';
import { makeCountType, countTypesFromMeasurements, measurementValue } from '@/lib/measurements';
import { draftReducer } from '@/lib/measureOverlayReducer';
import { uncalibratedScale } from '@/lib/measureGeometry';
import { autoPageScalesFromRooms } from '@/lib/durableScale';
import PageOverlayHost from './PageOverlayHost';
import CalibrateDialog from './CalibrateDialog';
import CountLegendPanel from './CountLegendPanel';

// Measurement tool palette (Phase 3). 'select' exists so committed measurements
// can be picked (→ delete affordance); drawing keys 2/3/4/6 match the hotkeys.
// Labeled: founder 2026-07-14 — unlabeled icons read as "all of these do the
// same thing". label renders next to the icon; title keeps the hotkey hint.
const MEASURE_TOOLS = [
  { id: 'select', Icon: MousePointer2, label: 'Žymėti', title: 'Pažymėti jau nubrėžtą matavimą — po to Delete jį ištrina' },
  { id: 'distance', Icon: Ruler, label: 'Atstumas', title: 'Matuoti atstumą tarp dviejų taškų, rezultatas metrais (2)' },
  { id: 'area', Icon: Pentagon, label: 'Plotas', title: 'Matuoti plotą apvedant kontūrą, rezultatas m² (3)' },
  { id: 'perimeter', Icon: Spline, label: 'Perimetras', title: 'Matuoti kontūro ilgį, rezultatas metrais (4)' },
  { id: 'count', Icon: Hash, label: 'Kiekis', title: 'Skaičiuoti vienetus (rozetes, šviestuvus) spustelint kiekvieną (6)' },
  { id: 'calibrate', Icon: Scaling, label: 'Mastelis', title: 'Nustatyti brėžinio mastelį: pažymėkite atkarpą, kurios tikrą ilgį žinote, ir jį įrašykite' },
];

// Empty measurement draft (shape of measureOverlayReducer's state).
const EMPTY_DRAFT = { points: [], committed: false };

// One-line instruction per armed tool (status bar) — the tools LOOK similar,
// the hint says what each one is doing right now.
// 2026-07-28 explainability pass: every draft has a „Baigti" / „Atšaukti"
// button next to the last point, but the hints only advertised double-click —
// so the visible exit was the one nobody was told about. Multi-step flows
// (kalibravimas, kiekis) now number their steps.
const MEASURE_HINTS = {
  select: 'Spustelėkite matavimą jam pažymėti · Delete — ištrinti pažymėtą',
  distance: 'Atstumas: spustelėkite pradžią ir pabaigą · „Baigti" arba dukart spustelėkite',
  area: 'Plotas: apveskite kontūrą (bent 3 taškai) · „Baigti" arba dukart spustelėkite',
  perimeter: 'Perimetras: spustelėkite kampus iš eilės · „Baigti" arba dukart spustelėkite',
  count: 'Kiekis: 1) pasirinkite tipą dešinėje 2) spustelėkite elementus · ant žymės — pašalinti',
  calibrate: 'Mastelis: 1) spustelėkite atkarpos pradžią ir pabaigą 2) įrašykite jos tikrą ilgį',
};

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
        title="Ieško teksto brėžinyje (patalpų pavadinimų, žymėjimų). Skenuotuose PDF teksto nėra — nerasta nieko."
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
          Rezultatų nėra — šis PDF greičiausiai skenuotas (be teksto)
        </span>
      )}
    </span>
  );
}

function Toolbar({ documentId, totalPages, focusedRoomNr, fillFor, onStartFill, onCancelFill, railOpen, onToggleThumbs, measureTool, onMeasureTool, searchOpen, onToggleSearch, onCloseSearch, zoneFillsVisible, onToggleZoneFills, onDownload }) {
  const { state: zoom, provides: zoomApi } = useZoom(documentId);
  const { state: scroll, provides: scrollApi } = useScroll(documentId);
  const { provides: printApi } = usePrint(documentId);
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
    <div className="h-9 shrink-0 border-b border-[hsl(var(--viewer-chrome-border))] bg-[hsl(var(--viewer-chrome))] px-3 flex items-center gap-1 text-[12px] text-[hsl(var(--viewer-chrome-foreground))] overflow-x-auto">
      <button
        className={btn + (railOpen ? ' bg-[hsl(var(--viewer-chrome-hover))] text-[hsl(var(--viewer-chrome-active))]' : '')}
        title="Puslapių juosta (T)"
        onClick={onToggleThumbs}
      ><PanelLeft className="w-4 h-4" /></button>
      <span className="w-px h-4 bg-[hsl(var(--viewer-chrome-border))] mx-1.5" />
      {/* Deterministic: jump to visible page ± 1. The plugin's relative
          scrollToNext/PreviousPage steps from its own (stale) currentPage —
          under wheel scrolling that no-ops or bounces (founder: "page changer
          does not work"). */}
      <button className={btn} title="Ankstesnis puslapis (PgUp)" disabled={cur <= 1} onClick={() => scrollApi?.scrollToPage({ pageNumber: Math.max(1, cur - 1) })}><ChevronLeft className="w-4 h-4" /></button>
      <span className="mono tabular px-1 whitespace-nowrap">psl. {cur} / {total}</span>
      <button className={btn} title="Kitas puslapis (PgDn)" disabled={cur >= total} onClick={() => scrollApi?.scrollToPage({ pageNumber: Math.min(total, cur + 1) })}><ChevronRight className="w-4 h-4" /></button>
      <span className="w-px h-4 bg-[hsl(var(--viewer-chrome-border))] mx-1.5" />
      <button className={btn} title="Tolinti (−)" onClick={() => zoomApi?.zoomOut()}><ZoomOut className="w-4 h-4" /></button>
      <span className="mono tabular w-11 text-center">{pct}%</span>
      <button className={btn} title="Artinti (+)" onClick={() => zoomApi?.zoomIn()}><ZoomIn className="w-4 h-4" /></button>
      <span className="w-px h-4 bg-[hsl(var(--viewer-chrome-border))] mx-1.5" />
      <button className={btn} title="Sutalpinti per visą plotį (1)" onClick={() => syncPageThen(() => zoomApi?.requestZoom(ZoomMode.FitWidth))}><MoveHorizontal className="w-4 h-4" /></button>
      <button className={btn} title="Sutalpinti visą puslapį (0)" onClick={() => syncPageThen(() => zoomApi?.requestZoom(ZoomMode.FitPage))}><Maximize2 className="w-4 h-4" /></button>
      {onToggleZoneFills && (
        <>
          <span className="w-px h-4 bg-[hsl(var(--viewer-chrome-border))] mx-1.5" />
          {/* Zone-fill layer toggle. Founder decision 2026-07-11: markers are the
              default; this re-enables the filled room polygons.
              2026-07-28: the old title named the CURRENT state and then the
              OTHER state's action in one breath ("užpildai: įjungta (rodyti
              žymeklius)") — both readings were wrong. Say only what the click
              will do, and say what a "zona" is. */}
          <button
            className={zoneFillsVisible ? pressed : btn}
            title={zoneFillsVisible
              ? 'Rodyti tik patalpų numerių žymeklius (dabar matomos nuspalvintos patalpų zonos)'
              : 'Nuspalvinti patalpų zonas brėžinyje (dabar matomi tik numerių žymekliai)'}
            aria-pressed={!!zoneFillsVisible}
            onClick={onToggleZoneFills}
          ><Layers className="w-4 h-4" /></button>
        </>
      )}
      {onMeasureTool && (
        <>
          <span className="w-px h-4 bg-[hsl(var(--viewer-chrome-border))] mx-1.5" />
          {MEASURE_TOOLS.map(({ id, Icon, label, title }) => (
            <button
              key={id}
              className={(measureTool === id ? pressed : btn) + ' inline-flex items-center gap-1'}
              title={title}
              aria-pressed={measureTool === id}
              onClick={() => onMeasureTool(id)}
            >
              <Icon className="w-4 h-4" />
              <span className="text-[11px] leading-none hidden lg:inline">{label}</span>
            </button>
          ))}
        </>
      )}
      {canFill && (
        <>
          <span className="w-px h-4 bg-[hsl(var(--viewer-chrome-border))] mx-1.5" />
          {fillFor == null ? (
            <button
              className="inline-flex items-center gap-1 px-2 py-1 rounded border border-[hsl(var(--viewer-chrome-border))] hover:bg-[hsl(var(--viewer-chrome-hover))] text-[hsl(var(--viewer-chrome-foreground))]"
              title={`Perbrėžti patalpos ${focusedRoomNr} zoną: paspaudus — spustelėkite patalpos viduje brėžinyje, kontūras bus surastas automatiškai`}
              onClick={() => onStartFill(focusedRoomNr)}
            >
              <SquarePen className="w-3.5 h-3.5" />
              <span>Taisyti kontūrą</span>
            </button>
          ) : (
            /* Armed: pressed button + X cancel. The click hint lives in the status bar. */
            <span className="inline-flex items-center gap-1">
              <button
                className="inline-flex items-center gap-1 px-2 py-1 rounded bg-[hsl(var(--viewer-chrome-active)/0.18)] border border-[hsl(var(--viewer-chrome-active)/0.4)] text-[hsl(var(--viewer-chrome-active))]"
                title={`Laukiama spustelėjimo patalpos ${fillFor} viduje. Paspauskite čia arba Esc — atšaukti.`}
                onClick={onCancelFill}
              >
                <SquarePen className="w-3.5 h-3.5" />
                <span>Taisyti kontūrą</span>
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
        <button className={btn} title="Spausdinti brėžinį (Ctrl+P)" disabled={!printApi} onClick={() => printApi?.print()}><Printer className="w-4 h-4" /></button>
        {/* Honest title: this hands back the ORIGINAL uploaded PDF — the
            measurements and zones are not burned into it. (2026-07-28.) */}
        <button className={btn} title="Atsisiųsti originalų PDF (be matavimų ir kontūrų)" disabled={!onDownload} onClick={onDownload || undefined}><Download className="w-4 h-4" /></button>
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
  if (!pageScale?.calibrated) return 'Mastelis: nekalibruotas — spustelėkite čia';
  // The dimension strings on the sheet gave the ratio — exact, from the drawing.
  if (pageScale.source === 'plan' && pageScale.label) return `Mastelis: ${pageScale.label} (iš brėžinio)`;
  if (pageScale.label) return `Mastelis: ${pageScale.label}`;
  const mpp = pageScale.metersPerPointX || 0;
  const ratio = mpp > 0 ? Math.round((mpp * 72) / 0.0254) : 0;
  if (ratio <= 0) return 'Mastelis: kalibruotas';
  // Auto scale is derived from the eksplikacija areas — honest ~ + disclosure.
  return pageScale.source === 'auto' ? `Mastelis: ~1:${ratio} (automatinis)` : `Mastelis: 1:${ratio}`;
}

// Tooltip for the scale readout. The whole viewer's numbers depend on the
// scale, but nothing explained what "automatinis" or the "~" meant, or why
// 1:105 is not a drafting scale. Say it in one line per state.
// (2026-07-28 explainability pass.)
function scaleStatusTitle(pageScale) {
  if (!pageScale?.calibrated) {
    return 'Mastelis dar nenustatytas — matavimai bus be metrų. Spustelėkite ir pažymėkite atkarpą, kurios tikrą ilgį žinote.';
  }
  if (pageScale.source === 'plan') {
    return 'Mastelis perskaitytas iš brėžinyje užrašytų matmenų — tikslus. Spustelėkite, jei norite kalibruoti pagal kitą žinomą atstumą.';
  }
  if (pageScale.source === 'auto') {
    return 'Mastelis apskaičiuotas iš patalpų plotų eksplikacijoje — todėl apytikslis (~). Norėdami tikslesnio, spustelėkite ir nustatykite mastelį pagal žinomą atstumą.';
  }
  return 'Mastelis kalibruotas rankiniu būdu pagal jūsų nurodytą atstumą. Spustelėkite, jei norite kalibruoti iš naujo.';
}

/**
 * StatusBar — bottom h-6 strip: page/zoom · sheet size in mm (+ ISO-A label) ·
 * fill-mode hint or the current page's calibrated scale.
 */
function StatusBar({ documentId, totalPages, pages, fillFor, fillBusy = false, measureScales, measureTool = null, onCalibrateClick = null }) {
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
  const measureHint = measureTool ? MEASURE_HINTS[measureTool] : null;
  return (
    <div className="h-6 shrink-0 bg-[hsl(var(--viewer-chrome))] border-t border-[hsl(var(--viewer-chrome-border))] text-[11px] text-[hsl(var(--viewer-chrome-foreground)/0.65)] px-3 flex items-center gap-3">
      <span className="mono tabular whitespace-nowrap">psl. {cur} / {totalPages || 1} · {pct}%</span>
      {sheet && <span className="mono tabular whitespace-nowrap">{sheet}</span>}
      {fillFor != null ? (
        <span className="ml-auto whitespace-nowrap text-[hsl(var(--viewer-chrome-active))]">
          {fillBusy ? `Ieškoma patalpos ${fillFor} kontūro…` : `Spustelėkite patalpos ${fillFor} viduje`}
        </span>
      ) : measureHint ? (
        <span className="ml-auto whitespace-nowrap text-[hsl(var(--viewer-chrome-active))]">{measureHint}</span>
      ) : (
        /* Idle: the scale readout doubles as the calibration entry point. */
        <button
          type="button"
          onClick={onCalibrateClick || undefined}
          title={scaleStatusTitle(pageScale)}
          className={`ml-auto whitespace-nowrap ${onCalibrateClick ? 'hover:underline cursor-pointer' : ''} ${pageScale?.calibrated ? 'text-[hsl(var(--viewer-chrome-foreground))]' : 'text-[hsl(var(--viewer-chrome-active))]'}`}
        >
          {scaleText}
        </button>
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
        case ']': case 'PageDown': {
          e.preventDefault();
          const vp = visiblePageOf(scrollRef.current);
          scrollApi?.scrollToPage({ pageNumber: Math.min(scrollRef.current?.totalPages ?? vp + 1, vp + 1) });
          break;
        }
        case '[': case 'PageUp': {
          e.preventDefault();
          const vp = visiblePageOf(scrollRef.current);
          scrollApi?.scrollToPage({ pageNumber: Math.max(1, vp - 1) });
          break;
        }
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
//
// FOUNDER BUG 2026-07-25 ("scrolls to other pages by itself; zoom snaps to
// one spot"): scrollApi's identity churns with scroll/zoom state, and with a
// focused room the old effect re-ran scrollToPage on EVERY tick — the viewer
// literally fought the user's navigation. Jump ONCE per new target; re-arm
// only when the focus object itself changes (clicking a room again re-jumps).
function FocusScroller({ documentId, focusedRoom, focusedPage }) {
  const { provides: scrollApi, state: scroll } = useScroll(documentId);
  // roomPageOf is THE shared page-field precedence (roomZones owns it) — the
  // zone layer and this scroller must never disagree about a room's page.
  const targetPage = (focusedRoom ? roomPageOf(focusedRoom) : null) ?? focusedPage ?? null;
  const doneRef = useRef(null);
  useEffect(() => { doneRef.current = null; }, [focusedRoom, focusedPage]);
  useEffect(() => {
    if (!targetPage || !scrollApi?.scrollToPage) return;
    if (doneRef.current === targetPage) return; // one jump per target — never re-yank
    doneRef.current = targetPage;
    scrollApi.scrollToPage({ pageNumber: targetPage, behavior: 'smooth' });
  }, [targetPage, scrollApi]);

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
  const retriesRef = useRef(0);
  useEffect(() => { retriesRef.current = 0; }, [focusedRoom, focusedPage]);
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
      });
    };
    raf = requestAnimationFrame(run);
    return () => { cancelled = true; cancelAnimationFrame(raf); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [nonce, documentId]);
  return null;
}

function ViewerInner({ check = null, focus = null, rooms, focusedRoom, focusedPage, hiddenRoomNrs, hoveredRoomNrExternal, onRoomZoneClick, onPagePoint, onClearFocus, projectId, pdfBlob, exportFileName, onRoomPolygonFill, fillRequest, initialMeasurements, initialMeasureScales, initialCountTypes, onMeasureDataChange, laneScales = null }) {
  const { activeDocumentId } = useActiveDocument();
  const focusedRoomNr = focusedRoom?.nr ?? null;
  // `fillFor` = the room nr currently armed for "Taisyti kontūrą" click-to-fill.
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
  // Auto-calibration: pages whose traced rooms carry eksplikacija areas get a
  // derived meters-per-point — measurements read real meters with no manual
  // step. A user calibration (measureScales) always wins the merge.
  const autoScales = useMemo(() => autoPageScalesFromRooms(rooms), [rooms]);
  const effectiveScales = useMemo(
    () => ({ ...autoScales, ...(laneScales || {}), ...measureScales }),
    [autoScales, laneScales, measureScales]);
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
  const addCountType = (label) => {
    const t = makeCountType(label, countTypes);
    setCountTypes((prev) => [...prev, t]);
    setActiveCountTypeId(t.id);
  };
  const removeCountType = (typeId) => {
    setCountTypes((prev) => prev.filter((t) => t.id !== typeId));
    setActiveCountTypeId((cur) => (cur === typeId ? (countTypes.find((t) => t.id !== typeId)?.id ?? null) : cur));
  };
  // Floating count legend collapse — it swallows placement clicks underneath.
  const [countLegendCollapsed, setCountLegendCollapsed] = useState(false);
  const [selectedMeasureId, setSelectedMeasureId] = useState(null);
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
    // Arming the count tool with no types yet would be a silent no-op (clicks
    // do nothing without an active type) — make the "Sukurkite tipą" hint
    // visible even if the legend was left collapsed.
    if (tool === 'count' && countTypes.length === 0) setCountLegendCollapsed(false);
    setMeasureTool((cur) => {
      const next = cur === tool ? null : tool;
      if (next == null) setSelectedMeasureId(null);
      return next;
    });
  };
  const startFill = (nr) => { setMeasureTool(null); setSelectedMeasureId(null); setFillFor(nr); };
  // External fill arming (review-queue pencil → "Taisyti kontūrą" armed here).
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
      // The AREA stays table-read (eksplikacija beats a traced polygon for
      // accuracy) — say so, or redrawing "because the area looked wrong"
      // reads as a silent no-op. (final-regression finding 2, 2026-07-28)
      toast.success(`Patalpos ${fillFor} kontūras pažymėtas`, {
        description: 'Plotas ir kiekiai lieka iš eksplikacijos — kontūro pataisymas naudojamas žymėjimui ir tikslumo mokymui.',
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

  if (!activeDocumentId) return <div className="p-5 text-sm text-muted-foreground">Kraunamas dokumentas…</div>;
  return (
    <DocumentContent documentId={activeDocumentId}>
      {({ isLoaded, documentState }) => {
        if (!isLoaded) return <div className="p-5 text-sm text-muted-foreground">Kraunamas dokumentas…</div>;
        const totalPages = documentState?.document?.pageCount ?? documentState?.pageCount ?? documentState?.pages?.length ?? null;
        // No explicit user choice yet → open by default on multi-page documents.
        // The check sheet's drawing pane is narrow: the rail stays shut there unless asked for.
        const railOpen = thumbsPref ?? (check ? false : (totalPages ?? 1) > 1);
        return (
        <div className="flex flex-col h-full" data-tv-root>
          <Toolbar
            documentId={activeDocumentId}
            totalPages={totalPages}
            focusedRoomNr={onRoomPolygonFill && !check ? focusedRoomNr : null}
            fillFor={fillFor}
            onStartFill={startFill}
            onCancelFill={() => setFillFor(null)}
            railOpen={railOpen}
            onToggleThumbs={() => setRailOpen(!railOpen)}
            measureTool={measureTool}
            onMeasureTool={check ? null : armMeasureTool}
            searchOpen={searchOpen}
            onToggleSearch={() => setSearchOpen((v) => !v)}
            onCloseSearch={() => setSearchOpen(false)}
            zoneFillsVisible={zoneFillsVisible}
            onToggleZoneFills={check ? null : () => setZoneFillsVisible((v) => !v)}
            onDownload={handleDownload}
          />
          {!check && <FocusScroller documentId={activeDocumentId} focusedRoom={focusedRoom} focusedPage={focusedPage} />}
          {check && <FocusZoomer documentId={activeDocumentId} focus={focus} pages={documentState?.document?.pages} />}
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
                      checkMode={!!check}
                      checkData={check?.pages?.[layout.pageNumber] || null}
                      focusedRoomNr={focusedRoomNr}
                      hiddenRoomNrs={hiddenRoomNrs}
                      hoveredRoomNrExternal={hoveredRoomNrExternal}
                      zoneFillsVisible={zoneFillsVisible}
                      onRoomZoneClick={onRoomZoneClick}
                      onPagePoint={handlePagePoint}
                      measureTool={measureTool}
                      measurements={measurements}
                      measureScale={effectiveScales[layout.pageNumber] || null}
                      snapEnabled={snapEnabled}
                      orthoEnabled={orthoEnabled}
                      countTypes={countTypes}
                      activeCountTypeId={activeCountTypeId}
                      selectedMeasureId={selectedMeasureId}
                      onMeasureCommit={(m) => {
                        setMeasurements((prev) => [...prev, m]);
                        // Founder 2026-07-25 ("no way to get measurements"):
                        // announce the committed value + where it lives.
                        if (m.kind !== 'count') {
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
                      }}
                      onMeasureCalibrate={(pageNr, a, b) => setCalibRequest({
                        pageNr, a, b,
                        // The page's /Rotate travels with the pick: the dialog's
                        // axis labels describe what the user SEES, while a/b are
                        // unrotated mediabox points (audit P1).
                        rotation: documentState?.document?.pages?.[layout.pageIndex]?.rotation ?? 0,
                      })}
                      onMeasureSelect={setSelectedMeasureId}
                      onMeasureDelete={deleteMeasurement}
                      measureDraft={draftSlot.pageNr === layout.pageNumber ? draftSlot.draft : EMPTY_DRAFT}
                      onMeasureDraftAction={(action) => dispatchDraft(layout.pageNumber, action)}
                      measureCalibA={calibSlot.pageNr === layout.pageNumber ? calibSlot.point : null}
                      onMeasureCalibAChange={(point) => setCalibSlot(
                        point ? { pageNr: layout.pageNumber, point } : { pageNr: null, point: null })}
                    />
                  )}
                />
              </ZoomGestureWrapper>
            </Viewport>
            {/* Prominent tool instructions — the status-bar hint alone was
                invisible to the founder ("no buttons... or anything"). */}
            {measureTool != null && (
              <div className="absolute top-2 left-1/2 -translate-x-1/2 z-30 px-3.5 py-1.5 rounded-full border border-border bg-card text-[12px] text-foreground shadow-md pointer-events-none whitespace-nowrap">
                {MEASURE_HINTS[measureTool]}
              </div>
            )}
            {/* Floating count-type legend while the count tool is armed. */}
            {measureTool === 'count' && (
              <div
                className="absolute top-2 z-30 w-60 shadow-lg"
                style={{ left: railOpen ? 156 : 8 }}
              >
                <CountLegendPanel
                  countTypes={countTypes}
                  activeCountTypeId={activeCountTypeId}
                  onSelectType={setActiveCountTypeId}
                  tallies={countTallies}
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
            measureTool={measureTool}
            onCalibrateClick={() => armMeasureTool('calibrate')}
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
  // Page scales the drawing states (dimension-string lane, lib/durableScale
  // pageScalesFromLane) — exact, so a sheet the engine already read as 1:50
  // never says „nekalibruotas". A user calibration still wins.
  laneScales = null,
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
        />
      </EmbedPDF>
    </div>
  );
}
