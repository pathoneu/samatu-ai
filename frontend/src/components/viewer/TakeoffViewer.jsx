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
import { ZoomIn, ZoomOut, ChevronLeft, ChevronRight, ChevronUp, ChevronDown, MoveHorizontal, Maximize2, SquarePen, X, PanelLeft, MousePointer2, Ruler, Pentagon, Spline, Hash, Scaling, Search, Printer, Download, Layers, BrickWall, Undo2, History, ScanSearch, ListChecks, Lasso } from 'lucide-react';
import { engineOptions, makeViewerPlugins } from '@/lib/viewerEngine/embedEngine';
import { ROOM_POLYGON_FILLS_DEFAULT_VISIBLE, roomPageOf } from '@/lib/roomZones';
import { displayRotationFor, normalizeRotation, rotatePctPoint } from '@/lib/viewerEngine/pageRotation';
import { clickToFill } from '@/lib/clickToFillApi';
import { makeCountType, countTypesFromMeasurements, measurementValue } from '@/lib/measurements';
import { draftReducer } from '@/lib/measureOverlayReducer';
import { uncalibratedScale } from '@/lib/measureGeometry';
import { autoPageScalesFromRooms, confirmLaneScales } from '@/lib/durableScale';
import { mergePageScales } from '@/lib/pageScales';
import { dimensionStringsOf } from '@/lib/scaleOverview';
import { scaleCheckReadout } from '@/lib/scaleCheck';
import { visiblePageOf } from '@/lib/visiblePage';
import { scaleStatusText, scaleStatusTitle } from '@/lib/scaleLabel';
import { centreDelta } from '@/lib/checkOverlay';
import { selfIntersects } from '@/lib/polygonGeometry';
import { usePageGeometry } from '@/hooks/usePageGeometry';
import PageOverlayHost from './PageOverlayHost';
import CalibrateDialog from './CalibrateDialog';
import { ScaleOverviewDock, ScaleGateChip } from './ScaleOverviewPanel';
import ScaleCheckCard from './ScaleCheckCard';
import CountLegendPanel from './CountLegendPanel';
import ShortcutsGuide from './ShortcutsGuide';
import HistoryPanel from './HistoryPanel';
import ViewerCoachMarks from './ViewerCoachMarks';
import MeasureContextMenu from './MeasureContextMenu';
import OutlineToolButtons from './OutlineToolButtons';
import OutlineToolPanel from './OutlineToolPanel';
import useOutlineTool, { roomHoles } from './useOutlineTool';
import { matchViewerHotkey, withKey, hintText, keyText } from '@/lib/viewerShortcuts';
import { historyReducer, initHistory, describeChange } from '@/lib/measureHistory';
import SymbolReviewPanel, { useSymbolSearch, SYMBOL_HINTS } from './SymbolReviewPanel';
import { aiTallies as aiTalliesOf } from '@/lib/symbolSearch';
import SheetRail from './SheetRail';
import { buildSheetRail, setSheetOverride, clearSheetOverride, overrideFor, floatingPanelLeft } from '@/lib/sheetRail';

// Measurement tool palette (Phase 3). 'select' exists so committed measurements
// can be picked (→ delete affordance); drawing keys 2/3/4/6 match the hotkeys.
// Labeled: founder 2026-07-14 — unlabeled icons read as "all of these do the
// same thing". label renders next to the icon; title keeps the hotkey hint.
const MEASURE_TOOLS = [
  { id: 'select', Icon: MousePointer2, label: 'Žymėti', title: 'Pažymėti jau nubrėžtą matavimą — po to Delete jį ištrina' },
  { id: 'lasso', Icon: Lasso, label: 'Laso', title: withKey('Apvesti kelis matavimus ir žymes — visi apvesti pažymimi; Shift — pridėti; dešinysis klavišas — veiksmai su visais', 'toolLasso') },
  { id: 'distance', Icon: Ruler, label: 'Atstumas', title: withKey('Matuoti atstumą tarp dviejų taškų, rezultatas metrais', 'toolDistance') },
  { id: 'area', Icon: Pentagon, label: 'Plotas', title: withKey('Matuoti plotą apvedant kontūrą, rezultatas m²', 'toolArea') },
  { id: 'perimeter', Icon: Spline, label: 'Perimetras', title: withKey('Matuoti kontūro ilgį, rezultatas metrais', 'toolPerimeter') },
  { id: 'count', Icon: Hash, label: 'Kiekis', title: withKey('Skaičiuoti vienetus (rozetes, šviestuvus) spustelint kiekvieną', 'toolCount') },
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
  select: `Spustelėkite matavimą jam pažymėti · ${hintText(['deleteSelected'])} · dešinysis klavišas — meniu`,
  lasso: `Laso: apveskite matavimus ir žymes (Shift — pridėti) · dešinysis klavišas — veiksmai su visais · ${hintText(['deleteSelected'])}`,
  distance: 'Atstumas: spustelėkite pradžią ir pabaigą · „Baigti" arba dukart spustelėkite',
  area: 'Plotas: apveskite kontūrą (bent 3 taškai) · „Baigti" arba dukart spustelėkite',
  perimeter: 'Perimetras: spustelėkite kampus iš eilės · „Baigti" arba dukart spustelėkite',
  count: 'Kiekis: 1) pasirinkite tipą kairėje 2) spustelėkite elementus · ant žymės — pašalinti',
  calibrate: 'Mastelis: 1) spustelėkite atkarpos pradžią ir pabaigą 2) įrašykite jos tikrą ilgį',
  // Togal-v2 W6: a readout, not a calibration — the same two-click pick, nothing is changed.
  scalecheck: 'Mastelio patikra: spustelėkite atkarpos, kurios ilgį žinote, pradžią ir pabaigą · Esc — baigti',
};
// Outline editing (2026-10-16): one line, every exit named — the same rule as the measure hints.
// Key names come from lib/viewerShortcuts, the table the „?" guide prints.
const OUTLINE_HINT = `Kontūras: tempkite kampą · vidurio taškas — pridėti · dukart — pašalinti · ${hintText(['outlineUndo', 'outlineSave', 'outlineCancel'])}`;
// What the status bar adds to a measure hint about snapping, by the sheet's wall geometry status.
const SNAP_NOTE = {
  ok: ' · prilimpa prie brėžinio sienų (oranžinė žymė) ir prie matavimų (žalia)',
  no_walls: ' · šiame lape vektorinių sienų nėra — prilimpa tik prie matavimų',
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

function Toolbar({ documentId, totalPages, focusedRoomNr, fillFor, onStartFill, onCancelFill, railOpen, onToggleThumbs, measureTool, onMeasureTool, searchOpen, onToggleSearch, onCloseSearch, zoneFillsVisible, onToggleZoneFills, wallsLayerVisible, onToggleWallsLayer, outlineEdit = null, onStartOutlineEdit = null, onSaveOutlineEdit = null, onCancelOutlineEdit = null, onUndoOutlineEdit = null, outlineCanUndo = false, outlineInvalid = false, outlineSaving = false, outlineToolsSlot = null, onDownload, historyOpen = false, onToggleHistory = null, onOpenGuide = null, symbolSearchActive = false, onToggleSymbolSearch = null, addon = null, scalesOpen = false, onToggleScales = null }) {
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
        title={withKey('Puslapių juosta', 'toggleThumbs')}
        onClick={onToggleThumbs}
      ><PanelLeft className="w-4 h-4" /></button>
      <span className="w-px h-4 bg-[hsl(var(--viewer-chrome-border))] mx-1.5" />
      {/* The reading button („Perskaityti lapą", renderToolbarAddon) — first, so a narrow toolbar never hides it. */}
      {addon && <>{addon(cur, total)}<span className="w-px h-4 bg-[hsl(var(--viewer-chrome-border))] mx-1.5" /></>}
      {/* Deterministic: jump to visible page ± 1. The plugin's relative
          scrollToNext/PreviousPage steps from its own (stale) currentPage —
          under wheel scrolling that no-ops or bounces (founder: "page changer
          does not work"). */}
      <button className={btn} title={withKey('Ankstesnis puslapis', 'prevPage')} disabled={cur <= 1} onClick={() => scrollApi?.scrollToPage({ pageNumber: Math.max(1, cur - 1) })}><ChevronLeft className="w-4 h-4" /></button>
      <span className="mono tabular px-1 whitespace-nowrap">psl. {cur} / {total}</span>
      <button className={btn} title={withKey('Kitas puslapis', 'nextPage')} disabled={cur >= total} onClick={() => scrollApi?.scrollToPage({ pageNumber: Math.min(total, cur + 1) })}><ChevronRight className="w-4 h-4" /></button>
      <span className="w-px h-4 bg-[hsl(var(--viewer-chrome-border))] mx-1.5" />
      <button className={btn} title={withKey('Tolinti', 'zoomOut')} onClick={() => zoomApi?.zoomOut()}><ZoomOut className="w-4 h-4" /></button>
      <span className="mono tabular w-11 text-center">{pct}%</span>
      <button className={btn} title={withKey('Artinti', 'zoomIn')} onClick={() => zoomApi?.zoomIn()}><ZoomIn className="w-4 h-4" /></button>
      <span className="w-px h-4 bg-[hsl(var(--viewer-chrome-border))] mx-1.5" />
      <button className={btn} title={withKey('Sutalpinti per visą plotį', 'fitWidth')} onClick={() => syncPageThen(() => zoomApi?.requestZoom(ZoomMode.FitWidth))}><MoveHorizontal className="w-4 h-4" /></button>
      <button className={btn} title={withKey('Sutalpinti visą puslapį', 'fitPage')} onClick={() => syncPageThen(() => zoomApi?.requestZoom(ZoomMode.FitPage))}><Maximize2 className="w-4 h-4" /></button>
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
          {/* Walls layer (2026-10-16, Togal analysis §10): the wall solid, every room outline and
              every opening the program read from the vector PDF — the QA view of the geometry lane. */}
          {onToggleWallsLayer && (
            <button
              type="button"
              className={wallsLayerVisible ? pressed : btn}
              title={wallsLayerVisible
                ? 'Paslėpti sienų sluoksnį'
                : 'Sienų sluoksnis: brėžinio sienos, visų patalpų kontūrai ir angos, kurias programa perskaitė iš vektorinio PDF'}
              aria-pressed={!!wallsLayerVisible}
              aria-label="Sienų sluoksnis"
              data-testid="viewer-walls-layer"
              onClick={onToggleWallsLayer}
            ><BrickWall className="w-4 h-4" /></button>
          )}
        </>
      )}
      {onMeasureTool && (
        <>
          <span className="w-px h-4 bg-[hsl(var(--viewer-chrome-border))] mx-1.5" />
          {MEASURE_TOOLS.map(({ id, Icon, label, title }) => (
            <button
              key={id}
              data-coach={id}
              className={(measureTool === id ? pressed : btn) + ' inline-flex items-center gap-1'}
              title={title}
              aria-pressed={measureTool === id}
              onClick={() => onMeasureTool(id)}
            >
              <Icon className="w-4 h-4" />
              <span className="text-[11px] leading-none hidden lg:inline">{label}</span>
            </button>
          ))}
          {/* „Rasti panašius" (2026-10-16, Togal's AI Image Search): box one symbol → similar ones → count. */}
          {onToggleSymbolSearch && (
            <button
              type="button"
              className={(symbolSearchActive ? pressed : btn) + ' inline-flex items-center gap-1'}
              title="Rasti panašius: apveskite vieną simbolį (pvz., duris) — programa suras panašius pagal formą, jūs peržiūrite ir pridedate kaip kiekį"
              aria-pressed={!!symbolSearchActive}
              onClick={onToggleSymbolSearch}
              data-testid="viewer-symbol-search"
            >
              <ScanSearch className="w-4 h-4" />
              <span className="text-[11px] leading-none hidden lg:inline">Rasti panašius</span>
            </button>
          )}
          {onToggleScales && (
            <button
              type="button"
              className={(scalesOpen ? pressed : btn) + ' inline-flex items-center gap-1'}
              title="Visų lapų masteliai: koks nustatytas, iš kur jis, ar patvirtintas"
              aria-pressed={scalesOpen}
              onClick={onToggleScales}
              data-testid="scales-toggle"
            >
              <ListChecks className="w-4 h-4" />
              <span className="text-[11px] leading-none hidden lg:inline">Masteliai</span>
            </button>
          )}
        </>
      )}
      {canFill && (
        <>
          <span className="w-px h-4 bg-[hsl(var(--viewer-chrome-border))] mx-1.5" />
          {/* Outline editing (2026-10-16): the focused room's outline vertex by vertex, snapping to the
              drawing's walls; „Išsaugoti" re-reads its walls server side (api outline-set). */}
          {outlineEdit ? (
            <span className="inline-flex items-center gap-1 mr-1">
              <button
                type="button"
                className="inline-flex items-center gap-1 px-2 py-1 rounded bg-[hsl(var(--viewer-chrome-active))] text-white disabled:opacity-60"
                title={outlineInvalid
                  ? 'Kontūras kertasi pats su savimi — pataisykite viršūnes, tada išsaugokite'
                  : 'Išsaugoti pakeistą kontūrą (Enter) — jo sienos ir angos bus perskaitytos iš naujo, kiekiai perskaičiuoti'}
                disabled={outlineSaving || outlineInvalid}
                onClick={onSaveOutlineEdit}
                data-testid="outline-edit-save"
              >
                <Pentagon className="w-3.5 h-3.5" />
                <span>{outlineSaving ? 'Saugoma…' : `Išsaugoti kontūrą (${outlineEdit.nr})`}</span>
              </button>
              <button
                type="button"
                className={btn}
                title={withKey('Atšaukti paskutinį viršūnės pakeitimą', 'outlineUndo')}
                aria-label="Atgal"
                disabled={!outlineCanUndo}
                onClick={onUndoOutlineEdit}
                data-testid="outline-edit-undo"
              ><Undo2 className="w-4 h-4" /></button>
              <button
                type="button"
                className="inline-flex items-center gap-1 px-2 py-1 rounded border border-[hsl(var(--viewer-chrome-border))] hover:bg-[hsl(var(--viewer-chrome-hover))] text-[hsl(var(--viewer-chrome-foreground))]"
                title="Atšaukti kontūro redagavimą (Esc) — niekas neišsaugoma"
                onClick={onCancelOutlineEdit}
              >
                <X className="w-3.5 h-3.5" />
                <span>Atšaukti</span>
              </button>
            </span>
          ) : (onStartOutlineEdit && fillFor == null) ? (
            <button
              type="button"
              className="inline-flex items-center gap-1 px-2 py-1 rounded border border-[hsl(var(--viewer-chrome-border))] hover:bg-[hsl(var(--viewer-chrome-hover))] text-[hsl(var(--viewer-chrome-foreground))] mr-1"
              title={`Redaguoti patalpos ${focusedRoomNr} kontūrą viršūnėmis: tempkite kampą, spustelėkite vidurio tašką — pridėti, dukart spustelėkite kampą — pašalinti; prilimpa prie brėžinio sienų`}
              onClick={onStartOutlineEdit}
              data-testid="outline-edit-start"
              data-coach="outline-edit"
            >
              <Pentagon className="w-3.5 h-3.5" />
              <span>Redaguoti kontūrą</span>
            </button>
          ) : null}
          {!outlineEdit && fillFor == null && outlineToolsSlot}
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
        {onToggleHistory && (
          <button
            type="button"
            className={(historyOpen ? pressed : btn) + ' inline-flex items-center gap-1'}
            title={`Istorija: paskutiniai veiksmai su matavimais ir žymėmis, grįžimas į bet kurį žingsnį (${keyText('undo')} — atšaukti)`}
            aria-pressed={!!historyOpen}
            onClick={onToggleHistory}
            data-testid="viewer-history-toggle"
          >
            <History className="w-4 h-4" />
            <span className="text-[11px] leading-none hidden xl:inline">Istorija</span>
          </button>
        )}
        {onOpenGuide && (
          <button
            type="button"
            className={btn + ' w-6 h-6 inline-flex items-center justify-center font-semibold'}
            title={withKey('Spartieji klavišai', 'openGuide')}
            aria-label="Spartieji klavišai"
            onClick={onOpenGuide}
            data-testid="viewer-shortcuts-open"
          >?</button>
        )}
        <span className="w-px h-4 bg-[hsl(var(--viewer-chrome-border))] mx-1.5" />
        {searchOpen && <SearchBox documentId={documentId} onClose={onCloseSearch} />}
        <button
          className={searchOpen ? pressed : btn}
          title={withKey('Paieška', 'openSearch')}
          aria-pressed={!!searchOpen}
          onClick={onToggleSearch}
        ><Search className="w-4 h-4" /></button>
        <span className="w-px h-4 bg-[hsl(var(--viewer-chrome-border))] mx-1.5" />
        <button className={btn} title={withKey('Spausdinti brėžinį', 'print')} disabled={!printApi} onClick={() => printApi?.print()}><Printer className="w-4 h-4" /></button>
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

// The scale readout and its tooltip — what the page's scale is and where it
// comes from (written on the sheet, measured from the dimensions, the room
// areas, or his own) — live in lib/scaleLabel.js (2026-10-06), tested there.

/**
 * StatusBar — bottom h-6 strip: page/zoom · sheet size in mm (+ ISO-A label) ·
 * fill-mode hint or the current page's calibrated scale.
 */
function StatusBar({ documentId, totalPages, pages, fillFor, fillBusy = false, measureScales, measureTool = null, onCalibrateClick = null, outlineEdit = null, projectId = null, symbolHint = null }) {
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
  const snapsHere = measureTool != null && measureTool !== 'select' && measureTool !== 'count';
  const { status: geometryStatus } = usePageGeometry(projectId, cur, snapsHere);
  const snapNote = snapsHere ? (SNAP_NOTE[geometryStatus] || '') : '';
  const measureHint = symbolHint || (outlineEdit ? OUTLINE_HINT : (measureTool ? `${MEASURE_HINTS[measureTool]}${snapNote}` : null));
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
function ViewerHotkeys({ documentId, fillArmed, onCancelFill, onClearFocus, onToggleThumbs, onMeasureToolKey, onMeasureEscape, canDeleteSelected, onDeleteSelected, onOpenSearch, onSearchEscape, onUndo, onRedo, onOpenGuide, onToggleZoneFills, onToggleWallsLayer }) {
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
      toolDistance: () => tool('distance'),
      toolArea: () => tool('area'),
      toolPerimeter: () => tool('perimeter'),
      toolCount: () => tool('count'),
      toolLasso: () => tool('lasso'),
      deleteSelected: () => (canDeleteSelected ? (onDeleteSelected?.(), true) : false),
      undo: () => (onUndo ? (onUndo(), true) : false),
      redo: () => (onRedo ? (onRedo(), true) : false),
      escape: () => {
        if (onSearchEscape?.()) return true;
        if (onMeasureEscape?.()) return true;
        if (fillArmed) { onCancelFill?.(); return true; }
        onClearFocus?.();
        return false;
      },
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
  }, [zoomApi, scrollApi, printApi, fillArmed, onCancelFill, onClearFocus, onToggleThumbs, onMeasureToolKey, onMeasureEscape, canDeleteSelected, onDeleteSelected, onOpenSearch, onSearchEscape, onUndo, onRedo, onOpenGuide, onToggleZoneFills, onToggleWallsLayer]);
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

function ViewerInner({ renderToolbarAddon = null, check = null, focus = null, rooms, focusedRoom, focusedPage, hiddenRoomNrs, hoveredRoomNrExternal, onRoomZoneClick, onPagePoint, onClearFocus, projectId, pdfBlob, exportFileName, onRoomPolygonFill, fillRequest, initialMeasurements, initialMeasureScales, initialCountTypes, onMeasureDataChange, laneScales = null, onRoomOutlineEdit = null, project = null, onOutlineTool = null, sheetPages = null, sheetOverrides = null, onSheetOverridesChange = null, sheetLinksVersion = 0, revisionOverlay = null }) {
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
  const resetSheet = (sheet) => changeSheet(
    sheet, clearSheetOverride(sheetOverridesRef.current, sheet.page),
    `Lapui ${sheet.page} grąžintas automatinis pavadinimas`,
  );
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
  const startOutlineEdit = () => {
    const r = focusedRoom && (rooms || []).find((x) => String(x?.nr) === String(focusedRoom.nr));
    if (!r || !Array.isArray(r.polygon_pct) || r.polygon_pct.length < 3) {
      toast.info('Ši patalpa dar neturi kontūro — pirmiausia „Taisyti kontūrą"');
      return;
    }
    setMeasureTool(null); setSelectedMeasureId(null); setFillFor(null); if (symbol.active) symbol.close(); outlineTools.cancel();
    setOutlineEdit({
      nr: String(r.nr),
      page: roomPageOf(r),
      points: r.polygon_pct.map(([x, y]) => [Number(x), Number(y)]),
      holes: roomHoles(r),       // „Atimti" cut-outs ride along: a vertex edit keeps them
      history: [],
      tableAreaM2: Number(r.plotas_m2) > 0 ? Number(r.plotas_m2) : null,
    });
  };
  const cancelOutlineEdit = () => setOutlineEdit(null);
  // Undo: every drag / insert / delete snapshots the ring first (OutlineEditLayer.onGestureStart);
  // Z or the toolbar arrow steps back. Bounded, like the measurement draft's undo.
  const snapshotOutline = () => setOutlineEdit((cur) => (cur
    ? { ...cur, history: [...(cur.history || []).slice(-49), cur.points] }
    : cur));
  const undoOutline = () => setOutlineEdit((cur) => (cur && cur.history?.length
    ? { ...cur, points: cur.history[cur.history.length - 1], history: cur.history.slice(0, -1) }
    : cur));
  const outlineInvalid = !!outlineEdit && selfIntersects(outlineEdit.points.map(([x, y]) => ({ x, y })));
  const saveOutlineEdit = async () => {
    if (!outlineEdit || !onRoomOutlineEdit) return;
    if (outlineInvalid) { toast.error('Kontūras kertasi pats su savimi — pataisykite viršūnes prieš išsaugant'); return; }
    setOutlineSaving(true);
    try {
      await onRoomOutlineEdit(outlineEdit.nr, outlineEdit.page, outlineEdit.points, outlineEdit.holes);
      toast.success(`Patalpos ${outlineEdit.nr} kontūras išsaugotas — sienos perskaitytos iš naujo`);
      setOutlineEdit(null);
    } catch (e) {
      toast.error(e?.userMessage || e?.message || 'Nepavyko išsaugoti kontūro');
    } finally {
      setOutlineSaving(false);
    }
  };
  // Focus moving to another room abandons an unsaved edit (the editor is bound to the focused room).
  useEffect(() => { setOutlineEdit(null); }, [focusedRoomNr]);
  // Keyboard while editing: Enter saves, Z undoes (Esc is in ViewerHotkeys' chain via measureEscape).
  const saveOutlineEditRef = useRef(saveOutlineEdit);
  useEffect(() => { saveOutlineEditRef.current = saveOutlineEdit; });
  useEffect(() => {
    if (!outlineEdit) return undefined;
    const onKey = (e) => {
      if (e.target?.closest?.('input, textarea, select, [contenteditable]')) return;
      if (e.key === 'Enter') { e.preventDefault(); saveOutlineEditRef.current?.(); }
      else if ((e.key === 'z' || e.key === 'Z') && !e.metaKey && !e.ctrlKey && !e.altKey) { e.preventDefault(); undoOutline(); }
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
  const addCountType = (label) => {
    const t = makeCountType(label, countTypes);
    setCountTypes((prev) => [...prev, t]);
    setActiveCountTypeId(t.id);
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
  const startFill = (nr) => { setMeasureTool(null); setSelectedMeasureId(null); if (symbol.active) symbol.close(); setFillFor(nr); };
  // „Rasti panašius" owns the pointer alone: every other tool steps aside, and they close it in turn.
  const toggleSymbolSearch = () => {
    if (symbol.active) { symbol.close(); return; }
    setMeasureTool(null); setSelectedMeasureId(null); setFillFor(null); setOutlineEdit(null);
    symbol.open();
  };
  // External fill arming (review-queue pencil → "Taisyti kontūrą" armed here).
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
  // Esc chain, measure segment: close the calibration dialog first, then drop
  // the active tool (MeasureLayer resets its own draft when the tool changes).
  const measureEscape = () => {
    if (symbol.active) { symbol.close(); return true; }
    if (outlineEdit) { setOutlineEdit(null); return true; }
    if (outlineTools.tool) { outlineTools.cancel(); return true; }
    if (calibRequest) { setCalibRequest(null); return true; }
    if (scaleCheck && measureTool !== 'scalecheck') { setScaleCheck(null); return true; }
    if (measureTool === 'scalecheck') { setScaleCheck(null); }
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
    if (symbol.active) return;   // the box search owns the pointer (SymbolSearchLayer)
    if (fillFor == null) {
      // Plain canvas click (no fill, no measure tool): clear the focused-room
      // chip — a room stays "selected" only while the user means it (audit P2
      // sticky chip) — and forward to any external consumer. While a measure
      // tool owns the pointer, leave focus alone. Same while an outline is being
      // edited: a drag that starts a hair off a vertex must not drop the focus
      // (which would abandon the edit, 2026-10-16).
      if (measureTool == null && !outlineEdit && !outlineTools.tool) {
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
        const sheetRail = sheetPages && !check ? buildSheetRail({ puslapiai: sheetPages, overrides: sheetOverrides, pageCount: totalPages }) : null;
        const panelLeft = floatingPanelLeft({ railOpen, sheetRail: !!sheetRail });
        return (
        <div className="flex flex-col h-full" data-tv-root ref={tvRootRef}>
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
            wallsLayerVisible={wallsLayerVisible}
            onToggleWallsLayer={check ? null : () => setWallsLayerVisible(!wallsLayerVisible)}
            outlineEdit={outlineEdit}
            onStartOutlineEdit={check || !onRoomOutlineEdit ? null : startOutlineEdit}
            onSaveOutlineEdit={saveOutlineEdit}
            onCancelOutlineEdit={cancelOutlineEdit}
            onUndoOutlineEdit={undoOutline}
            outlineCanUndo={!!outlineEdit?.history?.length}
            outlineInvalid={outlineInvalid}
            outlineSaving={outlineSaving}
            outlineToolsSlot={check || !onOutlineTool ? null : (
              <OutlineToolButtons
                focusedRoomNr={focusedRoomNr}
                active={outlineTools.tool?.mode ?? null}
                onStart={outlineTools.start}
                onCancel={outlineTools.cancel}
              />
            )}
            onDownload={handleDownload}
            historyOpen={historyOpen}
            onToggleHistory={check ? null : () => setHistoryOpen((v) => !v)}
            onOpenGuide={() => setGuideOpen(true)}
            symbolSearchActive={symbol.active}
            onToggleSymbolSearch={check ? null : toggleSymbolSearch}
            addon={check ? null : renderToolbarAddon}
            scalesOpen={scalesOpen}
            onToggleScales={check || !project ? null : () => setScalesOpen((v) => !v)}
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
            canDeleteSelected={(measureTool === 'select' || measureTool === 'lasso') && selectedMeasureIds.length > 0}
            onDeleteSelected={() => deleteMeasurement(selectedMeasureIds)}
            onOpenSearch={() => setSearchOpen(true)}
            onSearchEscape={searchEscape}
            onUndo={check ? null : undoMeasure}
            onRedo={check ? null : redoMeasure}
            onOpenGuide={() => setGuideOpen((v) => !v)}
            onToggleZoneFills={check ? null : () => setZoneFillsVisible((v) => !v)}
            onToggleWallsLayer={check ? null : () => setWallsLayerVisible(!wallsLayerVisible)}
          />
          <div className="relative flex flex-1 min-h-0">
            {railOpen && (sheetRail
              ? <SheetRail documentId={activeDocumentId} rail={sheetRail} currentPageOf={visiblePageOf} onRename={onSheetOverridesChange ? renameSheet : null} onReset={resetSheet} />
              : <ThumbnailRail documentId={activeDocumentId} />)}
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
                      projectId={projectId}
                      layout={layout}
                      rooms={rooms}
                      pageRotation={documentState?.document?.pages?.[layout.pageIndex]?.rotation ?? 0}
                      pageSizePt={documentState?.document?.pages?.[layout.pageIndex]?.size ?? null}
                      checkMode={!!check}
                      checkData={check?.pages?.[layout.pageNumber] || null}
                      symbolSearch={symbol.active ? symbol : null}
                      focusedRoomNr={focusedRoomNr}
                      hiddenRoomNrs={hiddenRoomNrs}
                      hoveredRoomNrExternal={hoveredRoomNrExternal}
                      zoneFillsVisible={zoneFillsVisible}
                      wallsLayerVisible={wallsLayerVisible}
                      outlineEdit={outlineEdit}
                      onOutlineEditChange={(points) => setOutlineEdit((cur) => (cur ? { ...cur, points } : cur))}
                      onOutlineGestureStart={snapshotOutline}
                      outlineTool={outlineTools.tool}
                      onOutlineToolChange={outlineTools.change}
                      onRoomZoneClick={onRoomZoneClick}
                      onPagePoint={handlePagePoint}
                      measureTool={measureTool === 'scalecheck' ? 'calibrate' : measureTool}
                      measurements={measurements}
                      measureScale={effectiveScales[layout.pageNumber] || null}
                      snapEnabled={snapEnabled}
                      orthoEnabled={orthoEnabled}
                      countTypes={countTypes}
                      activeCountTypeId={activeCountTypeId}
                      selectedMeasureIds={selectedMeasureIds}
                      selectionMenuOnMiss={measureTool === 'lasso' && selectedMeasureIds.length > 1}
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
                      onMeasureDelete={deleteMeasurement}
                      onMeasureContextMenu={check ? null : setMeasureMenu}
                      measureDraft={draftSlot.pageNr === layout.pageNumber ? draftSlot.draft : EMPTY_DRAFT}
                      onMeasureDraftAction={(action) => dispatchDraft(layout.pageNumber, action)}
                      measureCalibA={calibSlot.pageNr === layout.pageNumber ? calibSlot.point : null}
                      onMeasureCalibAChange={(point) => setCalibSlot(
                        point ? { pageNr: layout.pageNumber, point } : { pageNr: null, point: null })}
                      sheetLinks={sheetRail ? { sheets: sheetRail.sheets, version: sheetLinksVersion } : null}
                      revisionOverlay={check ? null : revisionOverlay}
                    />
                  )}
                />
              </ZoomGestureWrapper>
            </Viewport>
            {/* Prominent tool instructions — the status-bar hint alone was
                invisible to the founder ("no buttons... or anything"). */}
            {(measureTool != null || outlineEdit || symbol.active) && (
              <div className={`absolute ${symbol.active ? 'bottom-2' : 'top-2'} left-1/2 -translate-x-1/2 z-30 px-3.5 py-1.5 rounded-full border border-border bg-card text-[12px] text-foreground shadow-md pointer-events-none whitespace-nowrap`}>
                {symbol.active ? SYMBOL_HINTS[symbol.phase] : outlineEdit ? OUTLINE_HINT : MEASURE_HINTS[measureTool]}
              </div>
            )}
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
            {/* Walls-layer legend (2026-10-16): the three things the layer draws, named once, where the layer is. */}
            {wallsLayerVisible && !check && (
              <div className="absolute bottom-2 right-2 z-30 px-3 py-1.5 rounded border border-border bg-card/95 text-[11px] text-foreground shadow-md pointer-events-none flex items-center gap-3" data-testid="walls-legend">
                <span className="inline-flex items-center gap-1.5"><span className="inline-block w-3 h-3 rounded-sm" style={{ background: 'rgba(71,85,105,0.5)' }} />Sienos (iš vektorinio PDF)</span>
                <span className="inline-flex items-center gap-1.5"><span className="inline-block w-5 border-t-2 border-dashed" style={{ borderColor: '#2f6b4f' }} />Kontūras, rastas automatiškai</span>
                <span className="inline-flex items-center gap-1.5"><span className="inline-block w-5 border-t-2" style={{ borderColor: '#2f6b4f' }} />Kontūras, patvirtintas jūsų</span>
                <span className="inline-flex items-center gap-1.5"><span className="inline-block w-5 border-t-4" style={{ borderColor: '#7c3aed' }} />Angos (D — durys, L — langas)</span>
              </div>
            )}
            {!check && <ScaleGateChip documentId={activeDocumentId} scales={effectiveScales} tool={measureTool} onSetScale={() => armMeasureTool('calibrate')} />}
            {(scalesOpen || scaleCheck) && !check && project && (
              <div className="absolute top-2 right-2 z-30 flex flex-col items-end gap-2">
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
              <div className="absolute top-2 right-2 z-30">
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
            measureTool={measureTool}
            onCalibrateClick={() => armMeasureTool('calibrate')}
            outlineEdit={outlineEdit}
            projectId={projectId}
            symbolHint={symbol.active ? SYMBOL_HINTS[symbol.phase] : null}
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
          {!check && (
            <MeasureContextMenu
              target={measureMenu}
              measurement={menuMeasurement}
              selection={menuSelection}
              onDeleteMany={deleteMeasurement}
              onChangeTypeMany={changeCountTypeMany}
              onRecolorMany={recolorMany}
              onDeselect={() => setSelectedMeasureIds([])}
              countTypes={countTypes}
              onClose={() => setMeasureMenu(null)}
              onRename={renameMeasurement}
              onChangeType={changeCountType}
              onDelete={deleteMeasurement}
              onReveal={revealMeasurement}
            />
          )}
          <ViewerCoachMarks rootRef={tvRootRef} enabled={!check} />
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
  // (currentPage, totalPages) => node — a control at the head of the toolbar, after the page-rail toggle
  // („Perskaityti lapą", components/viewer/DetectRunButton). Not drawn in the check sheet.
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
}) {
  const { engine, isLoading, error } = usePdfiumEngine(engineOptions());
  const plugins = useMemo(
    () => (fileUrl ? makeViewerPlugins(fileUrl, exportFileName || undefined) : null),
    [fileUrl, exportFileName],
  );
  if (error) return <div className="p-5 text-sm text-red-600">Variklio klaida: {String(error.message || error)}</div>;
  if (isLoading || !engine || !plugins) return <div className="p-5 text-sm text-muted-foreground">Kraunamas PDF variklis…</div>;
  return (
    <div className="h-full" data-takeoff-viewer>
      <EmbedPDF engine={engine} plugins={plugins}>
        <ViewerInner
          renderToolbarAddon={renderToolbarAddon}
          onRoomOutlineEdit={onRoomOutlineEdit}
          onOutlineTool={onOutlineTool}
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
        />
      </EmbedPDF>
    </div>
  );
}
