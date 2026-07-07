import { useEffect, useMemo, useRef, useState } from 'react';
import { Document, Page, pdfjs } from 'react-pdf';
import 'react-pdf/dist/Page/AnnotationLayer.css';
import 'react-pdf/dist/Page/TextLayer.css';
import {
  ArrowLeft, ArrowRight, BookOpen, Check, Crosshair, Loader2, Maximize2, Minus, Plus,
  Search, SidebarClose, SidebarOpen, Target, Trash2, Wand2, Zap,
} from 'lucide-react';
import { clickToFill } from '@/lib/clickToFillApi';
import { pageTypeColor, pageTypeLabel } from '@/lib/pageTypes';
import {
  clampPlanScale,
  getDefaultPlanPage,
  getNextPlanPage,
  getPlanFitScale,
  getVisiblePlanPages,
} from '@/lib/planViewerState';
import { getFocusedRoomRect, getTextLabelRect, pickOverlayRect } from '@/lib/planOverlayGeometry';
import { getAnchoredZoomScroll, nextWheelScale } from '@/lib/viewerViewport';
import {
  getConfirmableSymbolCounts,
  getSymbolPoints,
  getSymbolVisibleCount,
  removeSymbolPoint,
} from '@/lib/symbolOverlay';
import { getPlanSymbolTypes } from '@/lib/planSymbolTypes';
import { API_BASE } from '@/lib/apiBase';
import RoomZoneLayer from './RoomZoneLayer';

if (typeof pdfjs.version === 'string' && pdfjs.version !== '4.8.69') {
  console.error(`[PlanViewer] pdfjs version drift detected: API=${pdfjs.version}, expected 4.8.69`);
}
pdfjs.GlobalWorkerOptions.workerSrc = '/pdf.worker.mjs';

const ZOOM_PRESETS = [0.5, 0.75, 1, 1.25, 1.5, 2];
function fmtPercent(scale) {
  return `${Math.round(scale * 100)}%`;
}

function textItemRectFromPdfItem(item, viewport) {
  if (!item?.str || !viewport || !pdfjs?.Util) return null;
  const tx = pdfjs.Util.transform(viewport.transform, item.transform);
  const x = tx[4];
  const y = tx[5];
  const width = Math.max(1, (item.width || 0) * viewport.scale);
  const height = Math.max(1, (item.height || Math.abs(tx[3]) || 0) * viewport.scale);
  return {
    str: item.str,
    x,
    y: y - height,
    width,
    height,
  };
}

function PageRailItem({ item, active, onClick }) {
  const color = pageTypeColor(item.type);
  return (
    <button
      type="button"
      onClick={onClick}
      className={`w-full text-left rounded-md border transition-colors overflow-hidden ${
        active
          ? 'border-primary bg-primary/8 shadow-sm'
          : 'border-border bg-background hover:border-foreground/30 hover:bg-muted/40'
      }`}
    >
      <div className="h-24 bg-muted/50 overflow-hidden flex items-center justify-center">
        <Page
          pageNumber={item.nr}
          width={104}
          renderTextLayer={false}
          renderAnnotationLayer={false}
          loading={<div className="w-full h-full bg-muted" />}
        />
      </div>
      <div className="p-2">
        <div className="flex items-center gap-1.5">
          <span className="w-2 h-2 rounded-full shrink-0" style={{ background: color }} />
          <span className="text-[10px] uppercase tracking-wide text-muted-foreground tabular-nums">
            Psl. {item.nr}
          </span>
        </div>
        <div className="mt-0.5 text-xs text-foreground leading-tight line-clamp-2">
          {item.label || pageTypeLabel(item.type)}
        </div>
      </div>
    </button>
  );
}

function PlanOverlayLayer({ room, page, eksplikacijaPage, renderedSize, pdfSize, textLabelRect }) {
  const focusedRect = getFocusedRoomRect({
    room,
    page,
    eksplikacijaPage,
    renderedSize,
    pdfSize,
  });
  const rect = pickOverlayRect(focusedRect, textLabelRect);

  if (!rect) return null;

  // Room centre for the clean number marker. Reverted from the flood-fill
  // polygon (2026-06-17, founder): the auto-traced boundary wasn't accurate
  // enough, so we mark WHERE the room is (its number), not a wrong outline.
  // Accurate polygons stay available on demand via "Taisyti zoną".
  const cx = rect.left + rect.width / 2;
  const cy = rect.top + rect.height / 2;

  return (
    <div className="absolute inset-0 pointer-events-none" style={{ zIndex: 20 }}>
      <div
        style={{ position: 'absolute', left: cx, top: cy, transform: 'translate(-50%, -50%)' }}
        className="flex flex-col items-center"
      >
        <div
          className="flex items-center justify-center rounded-full font-semibold text-white text-sm tabular-nums ring-2 ring-white"
          style={{ width: 36, height: 36, background: 'hsl(var(--primary))', boxShadow: '0 4px 16px hsl(var(--primary) / 0.45)' }}
        >
          {room?.nr}
        </div>
        {room?.pavadinimas ? (
          <div className="mt-1.5 rounded-md bg-white/95 px-2 py-0.5 text-[11px] font-medium text-[#1f2937] shadow-sm whitespace-nowrap">
            {room.pavadinimas}
          </div>
        ) : null}
      </div>
    </div>
  );
}

// Phase C-3: simple SVG polygon overlay drawn after click-to-fill returns.
// No editing in v1 — visual confirmation only. User dismisses via toolbar.
function FillPolygonOverlay({
  polygon_pdf, page_width_pdf, page_height_pdf,
  pdfSize, renderedSize, confidence,
}) {
  if (!polygon_pdf?.length || !pdfSize || !renderedSize) return null;
  const sx = renderedSize.width / page_width_pdf;
  const sy = renderedSize.height / page_height_pdf;
  const points = polygon_pdf.map(([x, y]) => `${x * sx},${y * sy}`).join(' ');
  const stroke = confidence === 'high' ? '#10b981' : confidence === 'medium' ? '#f59e0b' : '#ef4444';
  return (
    <svg
      className="absolute inset-0 pointer-events-none"
      style={{ zIndex: 27, width: renderedSize.width, height: renderedSize.height }}
      viewBox={`0 0 ${renderedSize.width} ${renderedSize.height}`}
    >
      <polygon
        points={points}
        fill={stroke}
        fillOpacity="0.18"
        stroke={stroke}
        strokeWidth="2"
        strokeLinejoin="round"
      />
    </svg>
  );
}


function SymbolOverlayLayer({ result, renderedSize, onRemovePoint = null }) {
  const points = getSymbolPoints(result);
  if (!points.length || !renderedSize) return null;
  return (
    <div className="absolute inset-0 pointer-events-none" style={{ zIndex: 25 }}>
      {points.map((point, index) => {
        const x = point.x_pct * renderedSize.width;
        const y = point.y_pct * renderedSize.height;
        const isTemplate = result?.symbol_type === 'template_symbol';
        const isMedium = String(point.confidence || '').toLowerCase() === 'medium';
        return (
          <button
            type="button"
            key={`${point.x_pct}-${point.y_pct}-${index}`}
            onClick={() => onRemovePoint?.(index)}
            title={`${point.confidence || 'symbol'} · spauskite pašalinti`}
            className={`absolute pointer-events-auto rounded-full border-2 shadow-[0_0_0_6px_rgba(239,68,68,0.16),0_10px_24px_rgba(127,29,29,0.3)] ${
              isTemplate
                ? 'border-red-600 bg-red-500/20'
                : isMedium
                  ? 'border-amber-500 bg-amber-400/20'
                  : 'border-blue-600 bg-blue-500/20'
            }`}
            style={{
              left: x - 10,
              top: y - 10,
              width: 20,
              height: 20,
            }}
          >
            <span className={`absolute left-1/2 top-1/2 h-1.5 w-1.5 -translate-x-1/2 -translate-y-1/2 rounded-full ${
              isMedium ? 'bg-amber-700' : 'bg-red-700'
            }`} />
          </button>
        );
      })}
      <div className="absolute left-3 top-3 rounded-md border border-red-300 bg-white/95 px-3 py-2 text-xs text-red-950 shadow">
        <span className="font-semibold">{points.length}</span>
        <span className="ml-1">ženklų juodraštis peržiūrai · spauskite tašką pašalinti</span>
      </div>
    </div>
  );
}

export default function PlanViewer({
  fileUrl,
  pdfFile = null,
  onSymbolCountResult = null,
  onRoomPolygonFill = null,
  pageMeta = {},
  missingTypes = [],
  focusedPage = null,
  focusedRoom = null,
  eksplikacija_source_page = null,
  rooms = [],
  onRoomZoneClick = null,
}) {
  const viewportRef = useRef(null);
  const [numPages, setNumPages] = useState(null);
  const [pageNumber, setPageNumber] = useState(1);
  const [scale, setScale] = useState(1);
  const [pageSize, setPageSize] = useState(null);
  const [query, setQuery] = useState('');
  const [railOpen, setRailOpen] = useState(true);
  const [isPanning, setIsPanning] = useState(false);
  const [didAutoPickPage, setDidAutoPickPage] = useState(false);
  const [pdfDoc, setPdfDoc] = useState(null);
  const [textLabelRect, setTextLabelRect] = useState(null);
  const [symbolToolsOpen, setSymbolToolsOpen] = useState(false);
  const [symbolPickMode, setSymbolPickMode] = useState(false);
  const [symbolLoading, setSymbolLoading] = useState(false);
  const [symbolResult, setSymbolResult] = useState(null);
  const [symbolError, setSymbolError] = useState(null);
  const [symbolType, setSymbolType] = useState(null);
  // Phase C-3 click-to-fill state
  const [fillMode, setFillMode] = useState(false);
  const [fillLoading, setFillLoading] = useState(false);
  const [fillResult, setFillResult] = useState(null); // {polygon_pdf, page_width_pdf, page_height_pdf, confidence}
  const [fillError, setFillError] = useState(null);
  // Cache the project_id used for fill cache. We mint one once per session
  // since the upstream caller doesn't always know the persisted project id.
  const fillProjectIdRef = useRef(null);
  if (!fillProjectIdRef.current) {
    fillProjectIdRef.current = `fill-session-${Math.random().toString(36).slice(2, 12)}`;
  }
  const [fillPdfUploaded, setFillPdfUploaded] = useState(false);
  const symbolVisibleCount = getSymbolVisibleCount(symbolResult);
  const symbolConfirmCounts = useMemo(() => getConfirmableSymbolCounts(symbolResult), [symbolResult]);
  // CV V2 tools (Skaičiuoti pažymint / Pažymėti patalpą) were unwired
  // from this viewer on 2026-05-11 after real-PDF testing exposed the
  // pdf.js drag-interaction limit. Components, backend, and training-
  // data writer remain on disk — see
  // docs/superpowers/research/2026-05-11-cv-tools-real-world-limits.md
  // and 2026-05-11-session-handoff.md for next-session context.

  // 2026-05-06: track dismissed room (Esc key) so user can navigate pages
  // freely after focusing a room without the marker re-snapping.
  const [dismissedRoomKey, setDismissedRoomKey] = useState(null);
  const focusedRoomKey = focusedRoom ? String(focusedRoom.id || focusedRoom.nr || '') : null;
  // Reset dismiss state when a NEW room is selected (different key from prior).
  useEffect(() => {
    if (focusedRoomKey && focusedRoomKey !== dismissedRoomKey) {
      setDismissedRoomKey(null);
    }
  }, [focusedRoomKey]);   

  useEffect(() => {
    if (focusedPage && focusedRoomKey !== dismissedRoomKey) setPageNumber(focusedPage);
  }, [focusedPage, focusedRoomKey, dismissedRoomKey]);

  useEffect(() => {
    if (!numPages || didAutoPickPage || focusedPage) return;
    const defaultPage = getDefaultPlanPage({ totalPages: numPages, pageMeta });
    if (defaultPage) {
      setPageNumber(defaultPage);
      setDidAutoPickPage(true);
    }
  }, [numPages, pageMeta, didAutoPickPage, focusedPage]);

  useEffect(() => {
    const onKey = (event) => {
      if (event.target?.closest?.('input, textarea, select')) return;
      if (event.key === '[') setPageNumber(p => getNextPlanPage(p, -1, numPages));
      if (event.key === ']') setPageNumber(p => getNextPlanPage(p, 1, numPages));
      if (event.key === '+' || event.key === '=') setScale(s => clampPlanScale(s + 0.15));
      if (event.key === '-') setScale(s => clampPlanScale(s - 0.15));
      if (event.key.toLowerCase() === 'f') fitPage('width');
      // Esc: clear focused room marker so user can navigate freely.
      if (event.key === 'Escape' && focusedRoomKey) {
        setDismissedRoomKey(focusedRoomKey);
        setTextLabelRect(null);
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [numPages, pageSize, focusedRoomKey]);

  const visiblePages = useMemo(() => getVisiblePlanPages({
    totalPages: numPages || 0,
    pageMeta,
    query,
  }), [numPages, pageMeta, query]);

  const currentMeta = pageMeta[pageNumber] || {};
  const currentType = currentMeta.type || 'unknown';
  const currentLabel = currentMeta.label || pageTypeLabel(currentType);
  const currentSymbolTypes = useMemo(() => getPlanSymbolTypes(currentType), [currentType]);
  // Page-identity guard: pageSize is tagged with the page it was measured on.
  // During an async page switch the previous page's dims linger for a frame;
  // scaling a polygon by the wrong page's dims is the navigation-drift bug.
  const renderedSize = (pageSize && pageSize.pageNumber === pageNumber)
    ? { width: pageSize.width * scale, height: pageSize.height * scale }
    : null;

  const runSymbolDetect = async (nextType) => {
    if (!pdfFile) {
      setSymbolError('PDF failas nerastas šiame naršyklės porte.');
      return;
    }
    setSymbolLoading(true);
    setSymbolError(null);
    setSymbolType(nextType);
    setSymbolPickMode(false);
    try {
      const form = new FormData();
      form.append('files', pdfFile, 'project.pdf');
      form.append('symbol_type', nextType);
      form.append('page_nr', String(pageNumber));
      const res = await fetch(`${API_BASE}/v9/symbols/detect`, { method: 'POST', credentials: 'include', body: form });
      const json = await res.json();
      if (!res.ok || json.status === 'error' || json.error) {
        throw new Error(json.error || `HTTP ${res.status}`);
      }
      const points = json.symbols || [];
      const normalized = { ...json, count: json.count ?? points.length, symbols: points, page_nr: pageNumber, symbol_type: nextType };
      setSymbolResult(normalized);
    } catch (error) {
      setSymbolError(error.message || 'Nepavyko aptikti simbolių');
    } finally {
      setSymbolLoading(false);
    }
  };

  const runPageSymbolDetect = async () => {
    if (!pdfFile) {
      setSymbolError('PDF failas nerastas šiame naršyklės porte.');
      return;
    }
    setSymbolLoading(true);
    setSymbolError(null);
    setSymbolType('page_scan');
    setSymbolPickMode(false);
    try {
      const form = new FormData();
      form.append('files', pdfFile, 'project.pdf');
      form.append('page_nr', String(pageNumber));
      form.append('page_type', currentType);
      const res = await fetch(`${API_BASE}/v9/symbols/detect-page`, { method: 'POST', credentials: 'include', body: form });
      const json = await res.json();
      if (!res.ok || json.status === 'error' || json.error) {
        throw new Error(json.error || `HTTP ${res.status}`);
      }
      const total = Object.values(json.summary || {}).reduce((sum, value) => sum + Number(value || 0), 0);
      const normalized = { ...json, count: total, symbol_type: 'page_scan' };
      setSymbolResult(normalized);
    } catch (error) {
      setSymbolError(error.message || 'Nepavyko nuskaityti puslapio ženklų');
    } finally {
      setSymbolLoading(false);
    }
  };

  const runFillFromClick = async (event) => {
    if (!fillMode || !pdfFile || !renderedSize) return;
    const pageEl = event.currentTarget;
    const rect = pageEl.getBoundingClientRect();
    const xPct = (event.clientX - rect.left) / rect.width;
    const yPct = (event.clientY - rect.top) / rect.height;
    if (xPct < 0 || xPct > 1 || yPct < 0 || yPct > 1) return;
    setFillLoading(true);
    setFillError(null);
    setFillResult(null);
    try {
      const data = await clickToFill({
        projectId: fillProjectIdRef.current,
        pageNr: pageNumber,
        clickXPct: xPct,
        clickYPct: yPct,
        sensitivity: 0.7,
        // First click sends PDF; subsequent clicks rely on server cache.
        pdfBlob: fillPdfUploaded ? null : pdfFile,
      });
      setFillPdfUploaded(true);
      setFillResult(data);
    } catch (err) {
      // Show friendly LT message + the raw backend detail in parens so
      // the user can copy/paste it when reporting bugs.
      const friendly = err.userMessage || 'Nepavyko užpildyti.';
      const raw = err.rawDetail ? ` (${String(err.rawDetail).slice(0, 80)})` : '';
      setFillError(friendly + raw);
      // If server lost cache (TTL expired), allow re-upload on next click.
      if ((err.userMessage || '').includes('cache')) setFillPdfUploaded(false);
    } finally {
      setFillLoading(false);
    }
  };

  const runTemplateCount = async (event) => {
    if (!symbolPickMode || !pdfFile || !renderedSize) return;
    const pageEl = event.currentTarget;
    const rect = pageEl.getBoundingClientRect();
    const xPct = (event.clientX - rect.left) / rect.width;
    const yPct = (event.clientY - rect.top) / rect.height;
    if (xPct < 0 || xPct > 1 || yPct < 0 || yPct > 1) return;
    setSymbolLoading(true);
    setSymbolError(null);
    setSymbolType('template_symbol');
    try {
      const form = new FormData();
      form.append('files', pdfFile, 'project.pdf');
      form.append('template_x_pct', String(xPct));
      form.append('template_y_pct', String(yPct));
      form.append('template_size_pct', '0.024');
      form.append('page_nr', String(pageNumber));
      const res = await fetch(`${API_BASE}/v9/symbols/count-by-template`, { method: 'POST', credentials: 'include', body: form });
      const json = await res.json();
      if (!res.ok || json.status === 'error' || json.error) {
        throw new Error(json.error || `HTTP ${res.status}`);
      }
      const points = json.matches || [];
      const normalized = { ...json, count: json.count ?? points.length, matches: points, page_nr: pageNumber, symbol_type: 'template_symbol' };
      setSymbolResult(normalized);
      setSymbolPickMode(getSymbolVisibleCount(normalized) === 0);
    } catch (error) {
      setSymbolError(error.message || 'Nepavyko suskaičiuoti pagal pasirinktą ženklą');
    } finally {
      setSymbolLoading(false);
    }
  };

  const confirmSymbolResult = () => {
    if (!symbolResult || !onSymbolCountResult) return;
    const points = getSymbolPoints(symbolResult);
    if (!points.length) return;
    Object.entries(symbolConfirmCounts).forEach(([type, count]) => {
      const typePoints = points.filter(point => point.type === type);
      const base = symbolResult.by_type?.[type] || symbolResult;
      const key = type === 'template_symbol' ? 'matches' : 'symbols';
      onSymbolCountResult(type, {
        ...base,
        [key]: typePoints,
        count,
        page_nr: pageNumber,
        symbol_type: type,
        status: 'user_confirmed',
      });
    });
    setSymbolResult(null);
  };

  useEffect(() => {
    let cancelled = false;
    setTextLabelRect(null);
    if (!focusedRoom || !renderedSize || !pageSize || !pdfDoc) return () => { cancelled = true; };

    const rect = getFocusedRoomRect({
      room: focusedRoom,
      page: pageNumber,
      eksplikacijaPage: eksplikacija_source_page,
      renderedSize,
      pdfSize: pageSize,
    });
    // Only short-circuit when we already have the BEST overlay (precise
    // polygon). When the only match is an eksplikacija row, keep going so
    // the text-layer label search can still find the room number on the
    // drawing — the label is preferred over a row in the corner table.
    if (rect && rect.type === 'room') return () => { cancelled = true; };

    const roomPage = focusedRoom.page_nr ?? focusedRoom.puslapio_nr;
    if (roomPage !== pageNumber || !focusedRoom.nr) return () => { cancelled = true; };

    pdfDoc.getPage(pageNumber)
      .then(page => Promise.all([page.getTextContent(), page]))
      .then(([textContent, page]) => {
        if (cancelled) return;
        const viewport = page.getViewport({ scale });
        const target = String(focusedRoom.nr).trim();
        // 2026-05-06: page may have multiple "01" text instances — title
        // block "Lapas: 01", page header, eksplikacija row, mazgas callout,
        // AND the actual floor plan room number. Filter + pick the one most
        // likely to be on the floor plan:
        //   1. exact-match string (already)
        //   2. NOT in the right 22% of page (LT title blocks live here)
        //   3. NOT in the bottom 5% (page numbers live here)
        //   4. Among survivors, pick closest to bbox_pct center if known,
        //      else the one with the most "isolated" text neighbourhood
        //      (room numbers are alone; eksplikacija rows have nearby text)
        const allRects = (textContent.items || [])
          .map(item => textItemRectFromPdfItem(item, viewport))
          .filter(Boolean);
        const exactMatches = allRects.filter(
          r => String(r.str || '').trim() === target,
        );
        const pageW = viewport.width || 1;
        const pageH = viewport.height || 1;
        const onFloorPlan = exactMatches.filter(r => {
          const rightPct = (r.x + r.width) / pageW;
          const bottomPct = (r.y + r.height) / pageH;
          return rightPct < 0.78 && bottomPct < 0.95;
        });
        const candidates = onFloorPlan.length > 0 ? onFloorPlan : exactMatches;

        let chosen = candidates[0];
        if (candidates.length > 1) {
          const bb = focusedRoom.bbox_pct;
          if (bb && typeof bb.x === 'number' && typeof bb.y === 'number') {
            const cx = (bb.x + (bb.w || 0) / 2) * pageW;
            const cy = (bb.y + (bb.h || 0) / 2) * pageH;
            chosen = candidates.reduce((best, r) => {
              const d = Math.hypot(r.x + r.width / 2 - cx, r.y + r.height / 2 - cy);
              const bestD = Math.hypot(best.x + best.width / 2 - cx, best.y + best.height / 2 - cy);
              return d < bestD ? r : best;
            });
          } else {
            // No bbox — prefer the most "isolated" instance: minimum number
            // of other text rects within 60 px (eksplikacija rows have many
            // neighbours; floor-plan numbers are alone).
            chosen = candidates.reduce((best, r) => {
              const score = (rect) => allRects.filter(o =>
                o !== rect &&
                Math.abs((o.y + o.height / 2) - (rect.y + rect.height / 2)) < 30 &&
                Math.abs((o.x + o.width / 2) - (rect.x + rect.width / 2)) < 60,
              ).length;
              return score(r) < score(best) ? r : best;
            });
          }
        }
        const nextRect = getTextLabelRect(chosen, { roomNr: target, padding: 14 });
        if (nextRect) setTextLabelRect(nextRect);
      })
      .catch(() => {
        if (!cancelled) setTextLabelRect(null);
      });

    return () => { cancelled = true; };
  }, [focusedRoom, renderedSize?.width, renderedSize?.height, pageSize, pageNumber, eksplikacija_source_page, pdfDoc, scale]);

  const activeOverlayRect = useMemo(() => {
    if (!focusedRoom || !renderedSize || !pageSize) return null;
    const rect = getFocusedRoomRect({
      room: focusedRoom,
      page: pageNumber,
      eksplikacijaPage: eksplikacija_source_page,
      renderedSize,
      pdfSize: pageSize,
    });
    return pickOverlayRect(rect, textLabelRect);
  }, [focusedRoom, renderedSize, pageSize, pageNumber, eksplikacija_source_page, textLabelRect]);

  useEffect(() => {
    if (focusedRoomKey === dismissedRoomKey) return;  // Esc-dismissed: don't auto-scroll
    const rect = activeOverlayRect;
    if (!rect) return;
    const el = viewportRef.current;
    if (!el) return;
    requestAnimationFrame(() => {
      el.scrollLeft = Math.max(0, rect.left + rect.width / 2 - el.clientWidth / 2 + 32);
      el.scrollTop = Math.max(0, rect.top + rect.height / 2 - el.clientHeight / 2 + 32);
    });
  }, [activeOverlayRect, focusedRoomKey, dismissedRoomKey]);

  const fitPage = (mode) => {
    const el = viewportRef.current;
    if (!el || !pageSize) return;
    setScale(getPlanFitScale({
      mode,
      viewportWidth: el.clientWidth,
      viewportHeight: el.clientHeight,
      page: pageSize,
    }));
    requestAnimationFrame(() => {
      el.scrollLeft = mode === 'page' ? 0 : Math.max(0, (el.scrollWidth - el.clientWidth) / 2);
      el.scrollTop = 0;
    });
  };

  if (!fileUrl) {
    return (
      <div className="h-full flex items-center justify-center bg-muted/20 text-muted-foreground text-sm">
        PDF brėžinys nepateiktas
      </div>
    );
  }

  return (
    <div className="h-full min-h-0 bg-[hsl(var(--viewer-blueprint-bg))] flex flex-col border-0">
      <div className="h-14 shrink-0 border-b border-[hsl(var(--viewer-chrome-border))] bg-[hsl(var(--viewer-chrome))] flex items-center justify-between px-3 gap-3">
        <div className="flex items-center gap-2 min-w-0">
          <button
            type="button"
            onClick={() => setRailOpen(v => !v)}
            className="h-9 w-9 rounded-md border border-[hsl(var(--viewer-chrome-border))] bg-[hsl(var(--viewer-chrome))] hover:bg-[hsl(var(--viewer-chrome-hover))] flex items-center justify-center"
            title={railOpen ? 'Slėpti puslapius' : 'Rodyti puslapius'}
          >
            {railOpen ? <SidebarClose className="w-4 h-4" /> : <SidebarOpen className="w-4 h-4" />}
          </button>
          <div className="min-w-0">
            <div className="flex items-center gap-2 min-w-0">
              <span
                className="w-2.5 h-2.5 rounded-full shrink-0"
                style={{ background: pageTypeColor(currentType) }}
              />
              <div className="text-sm font-semibold text-[hsl(var(--viewer-chrome-foreground))] truncate">{currentLabel}</div>
            </div>
            <div className="text-[11px] text-[hsl(var(--viewer-chrome-foreground)/0.65)] tabular-nums">
              Puslapis {pageNumber} / {numPages || '-'} · {pageTypeLabel(currentType)}
            </div>
          </div>
        </div>

        <div className="flex items-center gap-1 shrink-0">
          <button
            type="button"
            onClick={() => setPageNumber(p => getNextPlanPage(p, -1, numPages))}
            disabled={pageNumber <= 1}
            className="h-9 w-9 rounded-md border border-[hsl(var(--viewer-chrome-border))] bg-[hsl(var(--viewer-chrome))] hover:bg-[hsl(var(--viewer-chrome-hover))] disabled:opacity-40"
            title="Ankstesnis puslapis"
          >
            <ArrowLeft className="w-4 h-4 mx-auto" />
          </button>
          <button
            type="button"
            onClick={() => setPageNumber(p => getNextPlanPage(p, 1, numPages))}
            disabled={pageNumber >= numPages}
            className="h-9 w-9 rounded-md border border-[hsl(var(--viewer-chrome-border))] bg-[hsl(var(--viewer-chrome))] hover:bg-[hsl(var(--viewer-chrome-hover))] disabled:opacity-40"
            title="Kitas puslapis"
          >
            <ArrowRight className="w-4 h-4 mx-auto" />
          </button>
          <div className="w-px h-8 bg-[hsl(var(--viewer-chrome-border))] mx-1" />
          <button
            type="button"
            onClick={() => setScale(s => clampPlanScale(s - 0.15))}
            className="h-9 w-9 rounded-md border border-[hsl(var(--viewer-chrome-border))] bg-[hsl(var(--viewer-chrome))] hover:bg-[hsl(var(--viewer-chrome-hover))]"
            title="Mažinti"
          >
            <Minus className="w-4 h-4 mx-auto" />
          </button>
          <select
            value={ZOOM_PRESETS.includes(scale) ? String(scale) : 'custom'}
            onChange={e => setScale(clampPlanScale(Number(e.target.value)))}
            className="h-9 rounded-md border border-[hsl(var(--viewer-chrome-border))] bg-[hsl(var(--viewer-chrome))] px-2 text-sm tabular-nums outline-none"
            title="Mastelis"
          >
            <option value="custom" disabled>{fmtPercent(scale)}</option>
            {ZOOM_PRESETS.map(preset => (
              <option key={preset} value={preset}>{fmtPercent(preset)}</option>
            ))}
          </select>
          <button
            type="button"
            onClick={() => setScale(s => clampPlanScale(s + 0.15))}
            className="h-9 w-9 rounded-md border border-[hsl(var(--viewer-chrome-border))] bg-[hsl(var(--viewer-chrome))] hover:bg-[hsl(var(--viewer-chrome-hover))]"
            title="Didinti"
          >
            <Plus className="w-4 h-4 mx-auto" />
          </button>
          <button
            type="button"
            onClick={() => fitPage('width')}
            className="h-9 px-3 rounded-md border border-[hsl(var(--viewer-chrome-border))] bg-[hsl(var(--viewer-chrome))] hover:bg-[hsl(var(--viewer-chrome-hover))] text-sm"
            title="Pritaikyti pločiui"
          >
            <Maximize2 className="w-4 h-4 inline mr-1.5" />
            Plotis
          </button>
          {/* Manual room-contour correction (core): visible when a room is
              focused. Click inside the room → flood-fill → Išsaugoti persists
              it as that room's accurate polygon. */}
          {focusedRoom?.nr && (
            <button
              type="button"
              onClick={() => {
                setFillMode(v => !v);
                setFillError(null);
                setFillResult(null);
                if (symbolPickMode) setSymbolPickMode(false);
              }}
              className={`h-9 px-3 rounded-md border text-sm ${
                fillMode
                  ? 'border-violet-500 bg-violet-500/10 text-violet-300'
                  : 'border-[hsl(var(--viewer-chrome-border))] bg-[hsl(var(--viewer-chrome))] hover:bg-[hsl(var(--viewer-chrome-hover))]'
              } disabled:opacity-50`}
              disabled={fillLoading || !pdfFile}
              title={`Taisyti patalpos ${focusedRoom.nr} kontūrą — spustelėk patalpos viduje`}
            >
              <Wand2 className="w-4 h-4 inline mr-1.5" />
              {fillMode ? `Spustelėk patalpos ${focusedRoom.nr} viduje` : 'Taisyti zoną'}
            </button>
          )}
          {fillLoading && (
            <span className="inline-flex items-center gap-1.5 text-sm text-[hsl(var(--viewer-chrome-foreground)/0.65)]">
              <Loader2 className="w-4 h-4 animate-spin" /> Užpildoma...
            </span>
          )}
          {fillError && !fillLoading && (
            <span className="inline-flex items-center gap-1.5 rounded-md border border-red-500/50 bg-red-500/10 px-2.5 py-1 text-xs text-red-300">
              {fillError}
            </span>
          )}
          {fillResult && !fillLoading && (
            <span className="inline-flex items-center gap-1.5 rounded-md border border-violet-500/50 bg-violet-500/10 px-2.5 py-1 text-xs text-violet-300">
              ✓ {fillResult.polygon_pdf.length} taškų · {fillResult.confidence}
              {focusedRoom?.nr && onRoomPolygonFill && (
                <button
                  type="button"
                  onClick={() => {
                    onRoomPolygonFill(focusedRoom.nr, fillResult);
                    setFillResult(null);
                    setFillMode(false);
                  }}
                  className="ml-1 inline-flex items-center gap-1 rounded bg-violet-600 px-2 py-0.5 text-white hover:bg-violet-700"
                  title={`Išsaugoti kaip patalpos ${focusedRoom.nr} kontūrą`}
                >
                  <Check className="w-3 h-3" /> Išsaugoti
                </button>
              )}
              <button
                type="button"
                onClick={() => { setFillResult(null); setFillError(null); }}
                className="ml-1 hover:text-violet-700"
                title="Atmesti"
              >
                <Trash2 className="w-3 h-3" />
              </button>
            </span>
          )}
          {/* 2026-05-06: Ženklai toolbar (symbol counting + click-to-fill)
              hidden by default — accuracy isn't production-ready yet.
              Re-enable via DevTools:
                localStorage.setItem('samatu_experimental_tools', '1')
              Symbol counting via Vision was 49% accurate in bake-off;
              cv2.matchTemplate over-counts 100×. Will rewire when a
              commercial CAD-aware backend is integrated. */}
          {/* Experimental Ženklai panel — stays gated behind localStorage
              flag (no dev auto-show) since 2026-05-11. CV V2 buttons were
              unwired; the panel still exposes the working V1 flows. */}
          {(typeof window !== 'undefined' &&
            window.localStorage?.getItem('samatu_experimental_tools') === '1') && (
            <button
              type="button"
              onClick={() => setSymbolToolsOpen(v => !v)}
              className={`h-9 px-3 rounded-md border text-sm ${
                symbolToolsOpen
                  ? 'border-red-500/50 bg-red-500/10 text-red-300'
                  : 'border-[hsl(var(--viewer-chrome-border))] bg-[hsl(var(--viewer-chrome))] hover:bg-[hsl(var(--viewer-chrome-hover))]'
              }`}
              title="Sutartiniai ženklai (eksperimentinis)"
            >
              <Zap className="w-4 h-4 inline mr-1.5" />
              Ženklai (β)
            </button>
          )}
        </div>
      </div>

      {symbolToolsOpen && (
        <div className="shrink-0 border-b border-[hsl(var(--viewer-chrome-border))] bg-[hsl(var(--viewer-chrome))] px-3 py-2">
          <div className="flex flex-wrap items-center gap-2">
            <button
              type="button"
              onClick={() => {
                setSymbolPickMode(v => !v);
                setSymbolError(null);
              }}
              className={`h-8 px-3 rounded-md border text-xs font-medium ${
                symbolPickMode
                  ? 'border-red-500 bg-red-500/10 text-red-300'
                  : 'border-[hsl(var(--viewer-chrome-border))] bg-[hsl(var(--viewer-chrome))] hover:bg-[hsl(var(--viewer-chrome-hover))]'
              }`}
              disabled={symbolLoading || !pdfFile}
              title="Paspauskite ant simbolio brėžinyje, tada AI ieškos panašių"
            >
              <Target className="w-3.5 h-3.5 inline mr-1.5" />
              {symbolPickMode ? 'Paspauskite simbolį brėžinyje' : 'Skaičiuoti pagal paspaudimą'}
            </button>
            <button
              type="button"
              onClick={runPageSymbolDetect}
              className="h-8 px-3 rounded-md border border-blue-500/50 bg-blue-500/10 text-xs font-medium text-blue-300 hover:bg-blue-500/20 disabled:opacity-50"
              disabled={symbolLoading || !pdfFile}
              title="Vienu AI kvietimu rasti visus tikėtinus simbolius šiame puslapyje"
            >
              <Crosshair className="w-3.5 h-3.5 inline mr-1.5" />
              AI nuskaityti puslapį
            </button>
            {/* Fill flow moved to the main toolbar (core manual-correction feature). */}
            <div className="h-6 w-px bg-[hsl(var(--viewer-chrome-border))]" />
            {currentSymbolTypes.map(item => (
              <button
                key={item.id}
                type="button"
                onClick={() => runSymbolDetect(item.id)}
                disabled={symbolLoading || !pdfFile}
                className={`h-8 px-2.5 rounded-md border text-xs ${
                  symbolType === item.id
                    ? 'border-red-400 bg-red-500/10 text-red-300'
                    : 'border-[hsl(var(--viewer-chrome-border))] bg-[hsl(var(--viewer-chrome))] hover:bg-[hsl(var(--viewer-chrome-hover))]'
                } disabled:opacity-50`}
              >
                {item.label}
              </button>
            ))}
            {symbolLoading && (
              <span className="inline-flex items-center gap-1.5 text-xs text-[hsl(var(--viewer-chrome-foreground)/0.65)]">
                <Loader2 className="w-3.5 h-3.5 animate-spin" />
                AI ieško ženklų...
              </span>
            )}
            {symbolResult && !symbolLoading && (
              <>
                <span className={`inline-flex items-center gap-1.5 rounded-md border px-2.5 py-1 text-xs ${
                  symbolVisibleCount > 0
                    ? 'border-amber-300 bg-amber-500/10 text-amber-300'
                    : 'border-[hsl(var(--viewer-chrome-border))] bg-[hsl(var(--viewer-chrome-muted))] text-[hsl(var(--viewer-chrome-foreground)/0.65)]'
                }`}>
                  <Crosshair className="w-3.5 h-3.5" />
                  {symbolVisibleCount > 0
                    ? `${symbolVisibleCount} ženklai peržiūrai · neįkelta į kiekius`
                    : 'Ženklų peržiūrai nerasta'}
                </span>
                {symbolVisibleCount > 0 && (
                  <button
                    type="button"
                    onClick={confirmSymbolResult}
                    className="h-8 px-3 rounded-md border border-emerald-300 bg-emerald-500/10 text-xs font-medium text-emerald-300 hover:bg-emerald-500/20"
                    title="Tik po patvirtinimo šie ženklai bus įrašyti į kiekius"
                  >
                    <Check className="w-3.5 h-3.5 inline mr-1.5" />
                    Patvirtinti į kiekius
                  </button>
                )}
                <button
                  type="button"
                  onClick={() => setSymbolResult(null)}
                  className="h-8 px-2.5 rounded-md border border-[hsl(var(--viewer-chrome-border))] bg-[hsl(var(--viewer-chrome))] text-xs font-medium hover:bg-[hsl(var(--viewer-chrome-hover))]"
                  title="Išvalyti dabartinį AI žymėjimą"
                >
                  <Trash2 className="w-3.5 h-3.5 inline mr-1.5" />
                  Išvalyti
                </button>
              </>
            )}
            {symbolError && (
              <span className="text-xs text-red-300">{symbolError}</span>
            )}
          </div>
        </div>
      )}

      <div className="flex-1 min-h-0 flex">
        {railOpen && (
          <aside className="w-[172px] shrink-0 border-r border-[hsl(var(--viewer-chrome-border))] bg-[hsl(var(--viewer-chrome))] flex flex-col">
            <div className="p-3 border-b border-[hsl(var(--viewer-chrome-border))]">
              <div className="relative">
                <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-[hsl(var(--viewer-chrome-foreground)/0.65)]" />
                <input
                  value={query}
                  onChange={e => setQuery(e.target.value)}
                  placeholder="Puslapiai..."
                  className="w-full h-8 pl-8 pr-2 rounded-md border border-[hsl(var(--viewer-chrome-border))] bg-[hsl(var(--viewer-chrome))] text-xs outline-none focus:border-primary"
                />
              </div>
              {missingTypes.length > 0 && (
                <div className="mt-2 text-[11px] text-amber-300 leading-tight">
                  Trūksta: {missingTypes.map(pageTypeLabel).join(', ')}
                </div>
              )}
            </div>
            <div className="flex-1 overflow-auto p-2">
              <Document file={fileUrl} loading={null} error={null}>
                <div className="space-y-2">
                  {visiblePages.map(item => (
                    <PageRailItem
                      key={item.nr}
                      item={item}
                      active={item.nr === pageNumber}
                      onClick={() => setPageNumber(item.nr)}
                    />
                  ))}
                </div>
              </Document>
            </div>
          </aside>
        )}

        <main className="flex-1 min-w-0 flex flex-col">
          <div
            ref={viewportRef}
            className={`flex-1 min-h-0 overflow-auto bg-[hsl(var(--viewer-blueprint-bg))] relative ${isPanning ? 'cursor-grabbing' : 'cursor-grab'}`}
            onMouseDown={(event) => {
              if (symbolPickMode) return;
              if (event.target.closest('button, a, input, select, textarea')) return;
              const el = viewportRef.current;
              if (!el) return;
              setIsPanning(true);
              const startX = event.clientX;
              const startY = event.clientY;
              const startScrollLeft = el.scrollLeft;
              const startScrollTop = el.scrollTop;
              const onMove = (moveEvent) => {
                el.scrollLeft = startScrollLeft - (moveEvent.clientX - startX);
                el.scrollTop = startScrollTop - (moveEvent.clientY - startY);
              };
              const onUp = () => {
                setIsPanning(false);
                window.removeEventListener('mousemove', onMove);
                window.removeEventListener('mouseup', onUp);
              };
              window.addEventListener('mousemove', onMove);
              window.addEventListener('mouseup', onUp);
            }}
            onWheel={(event) => {
              if (!(event.ctrlKey || event.metaKey)) return;
              event.preventDefault();
              const el = viewportRef.current;
              if (!el) return;
              const rect = el.getBoundingClientRect();
              const viewportX = event.clientX - rect.left;
              const viewportY = event.clientY - rect.top;
              setScale(oldScale => {
                const newScale = clampPlanScale(nextWheelScale(oldScale, event.deltaY));
                const nextScroll = getAnchoredZoomScroll({
                  scrollLeft: el.scrollLeft,
                  scrollTop: el.scrollTop,
                  viewportX,
                  viewportY,
                  oldScale,
                  newScale,
                });
                requestAnimationFrame(() => {
                  el.scrollLeft = nextScroll.scrollLeft;
                  el.scrollTop = nextScroll.scrollTop;
                });
                return newScale;
              });
            }}
          >
            <div className="min-h-full min-w-full flex items-start justify-center p-8">
              <div className="relative bg-white shadow-[0_24px_70px_rgba(40,34,25,0.22)] ring-1 ring-black/10">
                <Document
                  file={fileUrl}
                  onLoadSuccess={(pdf) => {
                    setNumPages(pdf.numPages);
                    setPdfDoc(pdf);
                  }}
                  loading={<div className="w-[680px] h-[820px] bg-white flex items-center justify-center text-sm text-muted-foreground">Kraunamas PDF...</div>}
                  error={<div className="w-[680px] h-[400px] bg-white flex items-center justify-center text-sm text-red-600">Nepavyko atidaryti PDF.</div>}
                >
                  <Page
                    pageNumber={pageNumber}
                    scale={scale}
                    devicePixelRatio={Math.min(3, (window.devicePixelRatio || 1) * 1.6)}
                    renderTextLayer={false}
                    renderAnnotationLayer={false}
                    onLoadSuccess={(page) => {
                      // Use the ROTATION-APPLIED viewport, not page.width/height
                      // (= unrotated MediaBox view[2]/view[3]). For a /Rotate 90|270
                      // page the canvas renders landscape while page.width/height
                      // report portrait — that transposes every overlay. getViewport
                      // applies page.rotate by default; it's a no-op for unrotated pages.
                      const vp = page.getViewport ? page.getViewport({ scale: 1 }) : { width: page.width, height: page.height };
                      setPageSize({ width: vp.width, height: vp.height, pageNumber });
                    }}
                    loading={<div className="w-[680px] h-[820px] bg-white flex items-center justify-center text-sm text-muted-foreground">Renderiuojamas puslapis...</div>}
                  />
                </Document>

                {renderedSize && rooms.length > 0 && (
                  <RoomZoneLayer
                    rooms={rooms}
                    page={pageNumber}
                    renderedSize={renderedSize}
                    focusedRoomNr={focusedRoom?.nr ?? null}
                    onRoomClick={(zone) => onRoomZoneClick?.({ nr: zone.nr, puslapio_nr: pageNumber })}
                  />
                )}

                {symbolPickMode && (
                  <button
                    type="button"
                    onClick={runTemplateCount}
                    className="absolute inset-0 z-[30] cursor-crosshair bg-red-500/0"
                    aria-label="Pasirinkti sutartinį ženklą"
                  />
                )}

                {fillMode && (
                  <button
                    type="button"
                    onClick={runFillFromClick}
                    className="absolute inset-0 z-[30] cursor-crosshair bg-violet-500/0"
                    aria-label="Spustelėkite patalpos viduje"
                  />
                )}

                {fillResult && pageSize && renderedSize && (
                  <FillPolygonOverlay
                    polygon_pdf={fillResult.polygon_pdf}
                    page_width_pdf={fillResult.page_width_pdf}
                    page_height_pdf={fillResult.page_height_pdf}
                    pdfSize={pageSize}
                    renderedSize={renderedSize}
                    confidence={fillResult.confidence}
                  />
                )}

                {renderedSize && (
                  <SymbolOverlayLayer
                    result={symbolResult}
                    renderedSize={renderedSize}
                    onRemovePoint={(index) => setSymbolResult(current => removeSymbolPoint(current, index))}
                  />
                )}

                {renderedSize && pageSize && focusedRoomKey !== dismissedRoomKey && (
                  <>
                    <PlanOverlayLayer
                      room={focusedRoom}
                      page={pageNumber}
                      eksplikacijaPage={eksplikacija_source_page}
                      renderedSize={renderedSize}
                      pdfSize={pageSize}
                      textLabelRect={textLabelRect}
                    />
                    {focusedRoom && (
                      <button
                        type="button"
                        onClick={() => {
                          setDismissedRoomKey(focusedRoomKey);
                          setTextLabelRect(null);
                        }}
                        className="absolute right-3 top-3 z-30 inline-flex items-center gap-1 rounded-md border border-[hsl(var(--viewer-chrome-border))] bg-[hsl(var(--viewer-chrome))] px-2.5 py-1 text-[11px] text-[hsl(var(--viewer-chrome-foreground))] hover:bg-[hsl(var(--viewer-chrome-hover))] shadow"
                        title="Pašalinti pažymėjimą (Esc)"
                      >
                        ✕ Atšaukti pažymėjimą
                        <span className="text-[hsl(var(--viewer-chrome-foreground)/0.65)] text-[10px] ml-1">Esc</span>
                      </button>
                    )}
                  </>
                )}
              </div>
            </div>
          </div>

          <div className="h-9 shrink-0 border-t border-[hsl(var(--viewer-chrome-border))] bg-[hsl(var(--viewer-chrome))] px-3 flex items-center justify-between text-[11px] text-[hsl(var(--viewer-chrome-foreground)/0.65)]">
            <div className="flex items-center gap-2">
              <BookOpen className="w-3.5 h-3.5" />
              <span>Vilkite brėžinį pele · Ctrl/Cmd + ratukas keičia mastelį · [ / ] keičia puslapį</span>
            </div>
            {eksplikacija_source_page && (
              <button
                type="button"
                onClick={() => setPageNumber(eksplikacija_source_page)}
                className="text-primary hover:underline"
              >
                Eksplikacija psl. {eksplikacija_source_page}
              </button>
            )}
          </div>
        </main>
      </div>
    </div>
  );
}
