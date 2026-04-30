/**
 * PdfViewer — pilnas PDF brėžinių peržiūros komponentas su:
 * - Puslapių navigacija (sidebar thumbnails)
 * - Zoom in/out, pan
 * - Markup overlay per Konva.js (zonas, komentarus, ištrinti AI)
 * - Sync su RoomsGrid (paspaudus kambarį — PDF centruoja)
 *
 * Naudojam: react-pdf + react-konva.
 *
 * PDF.js worker — žr. workerSrc konfigūraciją žemiau (po importų, ~44 eil.).
 */

import { useState, useRef, useEffect, useMemo, useCallback } from 'react';
import { Document, Page, pdfjs } from 'react-pdf';
import 'react-pdf/dist/Page/AnnotationLayer.css';
import 'react-pdf/dist/Page/TextLayer.css';
import {
  ChevronLeft, ChevronRight, ZoomIn, ZoomOut, Maximize2,
  Pencil, Eraser, MessageSquare, Trash2, Eye, EyeOff, Ruler,
  Undo2, Redo2, AlertTriangle, BookOpen, SlidersHorizontal,
  MousePointer2, Hand, PenTool, Search, Layers,
} from 'lucide-react';
import { PAGE_TYPE_LABELS, PAGE_TYPE_COLOR } from '@/lib/pageTypes';
import { Stage, Layer, Rect, Line, Text as KonvaText, Group, Circle } from 'react-konva';
import {
  loadTakeoff, saveTakeoff,
  setPageScale, applyScaleToAll, getPageScale,
  addPolygon, removePolygon, getPolygonsForPage,
  polygonAreaM2, polygonPerimeterM, distanceM, snapToLines,
  undo as takeoffUndo, redo as takeoffRedo,
  canUndo, canRedo,
} from '@/lib/takeoffStore';
import ScaleCalibrationModal from './ScaleCalibrationModal';
import PolygonRoomModal from './PolygonRoomModal';
import AiRoomOverlay from './AiRoomOverlay';
import FocusFlashOverlay from './FocusFlashOverlay';
// Sprint §17 (2026-04-29): SymbolCounter file deleted along with its import.
// Symbol counting now flows through `detected_symbols_summary` in the main
// Vision prompt + symbol-driven pozicijų generation in vision_call.py.
import TraceOverlay from './TraceOverlay';
import { fetchPageLines } from '@/lib/pdfLinesApi';

// Worker is copied to /pdf.worker.mjs via vite-plugin-static-copy in vite.config.
// Set workerSrc here, not in main.jsx — Vite's module-execution order can let
// later imports overwrite a workerSrc set globally, breaking prod after deploy.
//
// Build-time guard: the worker version is the version we ship.
// If you upgrade react-pdf or pdfjs-dist and the version skews, this throws
// at module load instead of silently breaking PDFs at runtime.
if (typeof pdfjs.version === 'string' && pdfjs.version !== '4.8.69') {
  console.error(
    `[PdfViewer] pdfjs version drift detected: API=${pdfjs.version}, ` +
    `but /pdf.worker.mjs is shipped from react-pdf's bundled 4.8.69. ` +
    `Update vite.config viteStaticCopy src or pin pdfjs-dist to match.`
  );
}
pdfjs.GlobalWorkerOptions.workerSrc = '/pdf.worker.mjs';

// ── Markup data model ────────────────────────────────────────────────────────

const MARKUP_TYPES = {
  RECT: 'rect',           // Stačiakampis (zona)
  POLYGON: 'polygon',     // Polygon (sudėtinga zona)
  COMMENT: 'comment',     // Komentaras su rodyklėje
  AI_DELETE: 'ai_delete', // AI sugeneruota zona, kuria vartotojas ištrins
};

function makeMarkup(type, data) {
  return {
    id: `mk_${Date.now()}_${Math.random().toString(36).slice(2, 7)}`,
    type,
    page: data.page || 1,
    color: data.color || '#f59e0b',
    label: data.label || '',
    ...data,
    createdAt: Date.now(),
  };
}

// ── Persistence (localStorage per projekto) ──────────────────────────────────

function loadMarkups(projectId) {
  try {
    const raw = localStorage.getItem(`samatu_markups_${projectId}`);
    return raw ? JSON.parse(raw) : [];
  } catch {
    return [];
  }
}

function saveMarkups(projectId, markups) {
  try {
    localStorage.setItem(`samatu_markups_${projectId}`, JSON.stringify(markups));
  } catch (e) {
    console.error('Failed to save markups', e);
  }
}

// ── Tools toolbar ────────────────────────────────────────────────────────────

function ToolBar({
  tool, setTool, scale, setScale, page, setPage, totalPages,
  showMarkups, setShowMarkups,
  pageScaleInfo, onUndo, onRedo, undoOk, redoOk,
  eksplikacija_source_page,
  showAdvanced, setShowAdvanced,
  layers, setLayers,
}) {
  return (
    <div className="flex items-center gap-1 px-3 py-2 bg-stone-900 border-b border-stone-700 text-white">
      {/* — Pagrindiniai įrankiai (visada matomi) — */}

      {/* Puslapio navigacija. Sprint H4: tooltips + keyboard hints. */}
      <button onClick={() => setPage(Math.max(1, page - 1))}
        disabled={page <= 1}
        title="Ankstesnis puslapis (klavišas [ )"
        className="p-1.5 hover:bg-stone-700 rounded disabled:opacity-30">
        <ChevronLeft className="w-4 h-4" />
      </button>
      <span className="text-xs text-stone-300 mx-2 tabular-nums">
        {page} / {totalPages || '—'}
      </span>
      <button onClick={() => setPage(Math.min(totalPages, page + 1))}
        disabled={page >= totalPages}
        title="Kitas puslapis (klavišas ] )"
        className="p-1.5 hover:bg-stone-700 rounded disabled:opacity-30">
        <ChevronRight className="w-4 h-4" />
      </button>

      <div className="w-px h-5 bg-stone-700 mx-2" />

      {/* Mastelio keitimas. Sprint H5 (2026-04-29): preset dropdown vietoj
          plain procento span'o. Visi pasirinkimai grąžina exact mastelio
          reikšmę kad nebūtų kumuliacinio drift'o. */}
      <button onClick={() => setScale(s => Math.max(0.3, +(s - 0.2).toFixed(2)))}
        title="Mažinti (klavišas −)"
        className="p-1.5 hover:bg-stone-700 rounded">
        <ZoomOut className="w-4 h-4" />
      </button>
      <select
        value={(() => {
          const p = Math.round(scale * 100);
          // Match nearest preset for visual selection state
          const presets = [50, 75, 100, 125, 150, 200];
          return presets.includes(p) ? p : 'custom';
        })()}
        onChange={e => {
          const v = e.target.value;
          if (v === 'fit') setScale(1.2);  // fit-to-width default
          else if (v === 'page') setScale(0.7);  // fit-to-page approximation
          else setScale(parseInt(v, 10) / 100);
        }}
        title="Mastelio pasirinkimas"
        className="text-xs tabular-nums bg-stone-800 border border-stone-700 hover:bg-stone-700 rounded px-1 py-0.5 cursor-pointer outline-none focus:border-stone-500"
        style={{ minWidth: 76 }}
      >
        {/* Show current as a synthetic option when scale not in preset list */}
        <option value="custom" disabled style={{ display: 'none' }}>
          {Math.round(scale * 100)}%
        </option>
        <option value="50">50%</option>
        <option value="75">75%</option>
        <option value="100">100%</option>
        <option value="125">125%</option>
        <option value="150">150%</option>
        <option value="200">200%</option>
        <option value="fit">Pritaikyti pločiui</option>
        <option value="page">Pritaikyti puslapiui</option>
      </select>
      <button onClick={() => setScale(s => Math.min(3, +(s + 0.2).toFixed(2)))}
        title="Didinti (klavišas +)"
        className="p-1.5 hover:bg-stone-700 rounded">
        <ZoomIn className="w-4 h-4" />
      </button>
      <button onClick={() => setScale(1)}
        title="100% (klavišas 0)"
        className="p-1.5 hover:bg-stone-700 rounded">
        <Maximize2 className="w-4 h-4" />
      </button>

      {showAdvanced && (
        <>
          <div className="w-px h-5 bg-stone-700 mx-2" />

          {/* Mastelio kalibracija */}
          <button onClick={() => setTool(tool === 'scale' ? 'select' : 'scale')}
            className={`p-1.5 rounded flex items-center gap-1 ${tool === 'scale' ? 'bg-stone-100 text-stone-900' : 'hover:bg-stone-700'}`}
            title="Nustatyti mastelį (paspaudus 2 taškus brėžinyje)">
            <Ruler className="w-4 h-4" />
            {pageScaleInfo
              ? <span className="text-[10px] font-mono tabular-nums">
                  {(pageScaleInfo.pixels_per_meter).toFixed(0)} px/m
                </span>
              : <span className="text-[10px] text-amber-400">nenustatyta</span>
            }
          </button>

          <div className="w-px h-5 bg-stone-700 mx-2" />

          {/* Žymėjimo įrankiai */}
          <button onClick={() => setTool('select')}
            className={`p-1.5 rounded ${tool === 'select' ? 'bg-stone-100 text-stone-900' : 'hover:bg-stone-700'}`}
            title="Pasirinkti / žymėti zoną (klavišas Esc — grįžta į pasirinkimą)">
            <Pencil className="w-4 h-4" />
          </button>
          <button onClick={() => setTool('comment')}
            className={`p-1.5 rounded ${tool === 'comment' ? 'bg-stone-100 text-stone-900' : 'hover:bg-stone-700'}`}
            title="Pridėti komentarą">
            <MessageSquare className="w-4 h-4" />
          </button>
          <button onClick={() => setTool('erase')}
            className={`p-1.5 rounded ${tool === 'erase' ? 'bg-red-600' : 'hover:bg-stone-700'}`}
            title="Ištrinti žymėjimą">
            <Eraser className="w-4 h-4" />
          </button>

          <div className="w-px h-5 bg-stone-700 mx-2" />

          {/* Atšaukti / pakartoti */}
          <button onClick={onUndo} disabled={!undoOk}
            className="p-1.5 hover:bg-stone-700 rounded disabled:opacity-30"
            title="Atšaukti (Cmd+Z)">
            <Undo2 className="w-4 h-4" />
          </button>
          <button onClick={onRedo} disabled={!redoOk}
            className="p-1.5 hover:bg-stone-700 rounded disabled:opacity-30"
            title="Pakartoti (Cmd+Shift+Z)">
            <Redo2 className="w-4 h-4" />
          </button>

          <div className="w-px h-5 bg-stone-700 mx-2" />

          <button onClick={() => setShowMarkups(v => !v)}
            className={`p-1.5 rounded ${showMarkups ? 'hover:bg-stone-700' : 'bg-stone-700'}`}
            title={showMarkups ? 'Slėpti žymėjimus' : 'Rodyti žymėjimus'}>
            {showMarkups ? <Eye className="w-4 h-4" /> : <EyeOff className="w-4 h-4" />}
          </button>
        </>
      )}

      <div className="ml-auto" />

      {/* Sprint G8: Layers dropdown — multi-layer visibility toggle. */}
      {layers && setLayers && <LayersDropdown layers={layers} setLayers={setLayers} />}

      {/* Sprint H2 (2026-04-29): Pažangu — icon-only on small screens to
          declutter top toolbar; full label on lg+. */}
      <button
        onClick={() => setShowAdvanced(v => !v)}
        className={`p-1.5 rounded inline-flex items-center gap-1 text-[11px] ${
          showAdvanced ? 'bg-stone-100 text-stone-900' : 'hover:bg-stone-700 text-stone-300'
        }`}
        title={showAdvanced ? 'Slėpti pažangiuosius įrankius' : 'Pažangu — mastelis, žymėjimas, atšaukti'}>
        <SlidersHorizontal className="w-3.5 h-3.5" />
        <span className="hidden lg:inline">Pažangu</span>
      </button>

      {/* Eksplikacija jump — icon + page number only (no „Eksplikacija" label
          on small screens). Hover/title gives the full description. */}
      {eksplikacija_source_page && (
        <button
          onClick={() => setPage(eksplikacija_source_page)}
          className={`ml-1 inline-flex items-center gap-1 px-2 py-1 text-[11px] rounded border ${
            page === eksplikacija_source_page
              ? 'border-emerald-400 bg-emerald-500/20 text-emerald-200'
              : 'border-emerald-500/40 text-emerald-300 hover:bg-emerald-500/10'
          }`}
          title={page === eksplikacija_source_page
            ? 'Tu jau esi eksplikacijos puslapyje'
            : `Eiti į eksplikacijos puslapį (psl. ${eksplikacija_source_page})`}
        >
          <BookOpen className="w-3 h-3" />
          <span className="hidden lg:inline">
            {page === eksplikacija_source_page ? 'Eksplikacija ✓' : 'Eksplikacija'}
          </span>
          <span className="tabular-nums">psl. {eksplikacija_source_page}</span>
        </button>
      )}
    </div>
  );
}

// ── Sprint G8 (2026-04-29): Layers dropdown ────────────────────────────────
// Multi-layer visibility toggle. Replaces the single eye/eyeoff button.
// Each layer state persists in localStorage so user preference holds across
// sessions. Today: Markups + AI Rooms + Eksplikacija highlight. Future
// layers (Symbols overlay, Heatmap) plug in by adding to LAYERS array.

const LAYERS_STORAGE_KEY = 'samatu_layers_state';

const DEFAULT_LAYERS = {
  markups: true,
  rooms: false,           // AI Vision room polygons (off by default — future G1 feature)
  eksplikacija: true,     // Eksplikacija row highlight on table page
  source_dots: false,     // Provenance dots in side panel (legacy showProvenance)
};

function loadLayersState() {
  try {
    const raw = localStorage.getItem(LAYERS_STORAGE_KEY);
    if (!raw) return DEFAULT_LAYERS;
    return { ...DEFAULT_LAYERS, ...JSON.parse(raw) };
  } catch {
    return DEFAULT_LAYERS;
  }
}

function saveLayersState(state) {
  try { localStorage.setItem(LAYERS_STORAGE_KEY, JSON.stringify(state)); } catch {}
}

function LayersDropdown({ layers, setLayers }) {
  const [open, setOpen] = useState(false);
  const ref = useRef(null);

  useEffect(() => {
    if (!open) return;
    const onClick = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    };
    document.addEventListener('mousedown', onClick);
    return () => document.removeEventListener('mousedown', onClick);
  }, [open]);

  const toggleLayer = (key) => {
    const next = { ...layers, [key]: !layers[key] };
    setLayers(next);
    saveLayersState(next);
  };

  const visibleCount = Object.values(layers).filter(Boolean).length;
  const totalCount = Object.keys(DEFAULT_LAYERS).length;

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen(v => !v)}
        title={`Sluoksniai (${visibleCount} iš ${totalCount} matomi)`}
        className={`p-1.5 rounded inline-flex items-center gap-1 text-[11px] ${
          open ? 'bg-stone-100 text-stone-900' : 'hover:bg-stone-700 text-stone-300'
        }`}
      >
        <Layers className="w-3.5 h-3.5" />
        <span className="hidden lg:inline">Sluoksniai</span>
        <span className="mono tabular text-[10px]">
          {visibleCount}/{totalCount}
        </span>
      </button>
      {open && (
        <div
          className="absolute right-0 top-full mt-1 z-50 rounded-md border shadow-lg p-1 min-w-[200px]"
          style={{
            background: 'hsl(var(--card))',
            borderColor: 'hsl(var(--border))',
          }}
        >
          {[
            { id: 'markups',     label: 'Žymėjimai',                 hint: 'Pažymėti polygonai + matavimai' },
            { id: 'eksplikacija', label: 'Eksplikacijos paryškinimas', hint: 'Geltona eilutė ant eksplikacijos puslapio' },
            { id: 'rooms',       label: 'AI patalpų polygonai',      hint: 'Vision-aptiktos patalpos ant brėžinio' },
            { id: 'source_dots', label: 'Šaltinio taškai',           hint: 'Provenance žymės dešiniajame panel\'e' },
          ].map(layer => {
            const on = layers[layer.id];
            return (
              <button
                key={layer.id}
                onClick={() => toggleLayer(layer.id)}
                title={layer.hint}
                className="w-full flex items-center gap-2 px-2 py-1.5 rounded text-left text-xs hover:bg-muted/40"
                style={{ color: 'hsl(var(--foreground))' }}
              >
                {on
                  ? <Eye className="w-3 h-3 shrink-0" style={{ color: 'hsl(var(--primary))' }} />
                  : <EyeOff className="w-3 h-3 shrink-0 text-muted-foreground" />}
                <span className={on ? 'font-medium' : 'text-muted-foreground'}>
                  {layer.label}
                </span>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}

// ── Sprint H1 (2026-04-29): Left vertical tool rail ─────────────────────────
// Togal-style icon-only sidebar showing current tool mode. Active tool
// highlighted in primary blue. Replaces scattered toolbar buttons; user
// always knows what mode they're in.

function LeftToolRail({ tool, setTool, showAdvanced, setShowAdvanced }) {
  const TOOLS = [
    { id: 'select',  Icon: MousePointer2, label: 'Pasirinkti',         hint: 'Pasirinkti / pan (Esc)' },
    { id: 'polygon', Icon: PenTool,       label: 'Polygon (zona)',     hint: 'Brūkšnioti zoną — Enter užbaigti, Backspace anuliuoti tašką' },
    { id: 'scale',   Icon: Ruler,         label: 'Mastelis',           hint: 'Nustatyti mastelį — paspausk 2 taškus brėžinyje, įrašyk metrų atstumą' },
    { id: 'comment', Icon: MessageSquare, label: 'Komentaras',         hint: 'Pridėti komentaro žymą' },
    { id: 'erase',   Icon: Eraser,        label: 'Trinti',             hint: 'Ištrinti spustelėtą žymėjimą' },
  ];

  return (
    <div className="w-12 shrink-0 bg-stone-900 border-r border-stone-700 flex flex-col items-stretch py-1.5">
      {TOOLS.map(t => {
        const active = tool === t.id;
        return (
          <button
            key={t.id}
            onClick={() => setTool(t.id)}
            title={`${t.label} — ${t.hint}`}
            className={`relative mx-1 my-0.5 p-2 rounded transition-colors flex items-center justify-center ${
              active
                ? 'bg-stone-100 text-stone-900'
                : 'text-stone-400 hover:bg-stone-800 hover:text-stone-100'
            }`}
          >
            <t.Icon className="w-4 h-4" />
            {active && (
              <span
                className="absolute left-0 top-1 bottom-1 w-0.5 bg-stone-100 rounded-r"
                aria-hidden
              />
            )}
          </button>
        );
      })}

      <div className="flex-1" />

      {/* Bottom: advanced toggle as belt-and-suspenders for old toolbar */}
      <button
        onClick={() => setShowAdvanced(v => !v)}
        title={showAdvanced ? 'Slėpti pažangiuosius įrankius' : 'Rodyti pažangiuosius įrankius (žymėjimo + atšaukimo mygtukai)'}
        className={`mx-1 my-0.5 p-2 rounded transition-colors flex items-center justify-center ${
          showAdvanced
            ? 'bg-stone-100 text-stone-900'
            : 'text-stone-400 hover:bg-stone-800 hover:text-stone-100'
        }`}
      >
        <SlidersHorizontal className="w-4 h-4" />
      </button>
    </div>
  );
}

// ── Page thumbnails sidebar ──────────────────────────────────────────────────

const CONFIDENCE_DOT = {
  high:   'bg-emerald-500',
  medium: 'bg-amber-500',
  low:    'bg-red-500',
};

const CONFIDENCE_LABEL = {
  high:   'Aukšta',
  medium: 'Vidutinė',
  low:    'Žema',
};

// Highlights the eksplikacija table row corresponding to a focused room.
// Bbox is in pdfplumber coords (top-left origin, PDF points). We scale to
// the rendered Page's pixel size. Pulse animation guides the eye on click;
// pointer-events: none lets clicks fall through to MarkupCanvas / page.
function EksplikacijaRowOverlay({ width, height, room, page, eksplikacijaPage }) {
  if (!room || page !== eksplikacijaPage) return null;
  const bbox = room.eksplikacija_row_bbox;
  const pdfW = room.eksplikacija_page_width_pdf;
  const pdfH = room.eksplikacija_page_height_pdf;
  if (!bbox || !pdfW || !pdfH || !width || !height) return null;
  const [x0, y0, x1, y1] = bbox;
  const sx = width / pdfW;
  const sy = height / pdfH;
  // Pad horizontally so the highlight visibly extends a few px past the row's
  // text bounds (pdfplumber's row bbox can be tight to character glyphs).
  const PAD = 6;
  const left = Math.max(0, x0 * sx - PAD);
  const top = Math.max(0, y0 * sy - 2);
  const w = Math.min(width - left, (x1 - x0) * sx + PAD * 2);
  const h = (y1 - y0) * sy + 4;
  return (
    <>
      <div
        className="absolute pointer-events-none animate-pulse"
        style={{
          left, top, width: w, height: h,
          background: 'rgba(251, 191, 36, 0.30)',
          border: '2px solid rgba(245, 158, 11, 0.95)',
          borderRadius: 4,
          boxShadow: '0 0 0 4px rgba(251, 191, 36, 0.15)',
          zIndex: 5,
        }}
      />
      <div
        className="absolute pointer-events-none text-[11px] font-semibold tracking-tight"
        style={{
          left, top: Math.max(0, top - 22),
          padding: '2px 6px',
          background: '#f59e0b',
          color: '#78350f',
          borderRadius: 4,
          zIndex: 6,
        }}
      >
        ← {room.nr ? `#${room.nr} ` : ''}{room.pavadinimas || 'Patalpa'}
        {room.plotas_m2 != null && ` · ${room.plotas_m2} m²`}
      </div>
    </>
  );
}

// Inline skeleton with subtle shimmer — used while PDF or a Page is loading.
// Sized to match A4 portrait at the given scale so the surrounding layout
// doesn't jump when content arrives.
function PdfSkeleton({ width = 600, height = 800, label = 'Krauname brėžinį…' }) {
  return (
    <div
      className="relative overflow-hidden bg-stone-100 rounded"
      style={{ width, height }}
    >
      <div className="absolute inset-0 flex flex-col items-center justify-center text-stone-400 text-xs gap-2">
        <svg className="w-6 h-6 animate-spin" viewBox="0 0 24 24" fill="none">
          <circle cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="2" opacity="0.25" />
          <path d="M22 12a10 10 0 0 1-10 10" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
        </svg>
        <span>{label}</span>
      </div>
      <div
        className="absolute inset-0 animate-pulse"
        style={{
          background: 'linear-gradient(90deg, rgba(0,0,0,0.04) 0%, rgba(0,0,0,0) 50%, rgba(0,0,0,0.04) 100%)',
        }}
      />
    </div>
  );
}

// Single thumbnail row — uses IntersectionObserver to lazy-render <Page>
// only when visible in the scroll viewport. Once rendered, stays rendered
// (cached) so scrolling back is instant. Placeholder before render keeps
// layout stable.
function ThumbnailItem({ pageNr, currentPage, setPage, meta }) {
  const [visible, setVisible] = useState(false);
  const ref = useRef(null);
  const isActive = currentPage === pageNr;

  useEffect(() => {
    if (visible) return;
    const el = ref.current;
    if (!el) return;
    const observer = new IntersectionObserver(
      (entries) => {
        if (entries.some(e => e.isIntersecting)) {
          setVisible(true);
          observer.disconnect();
        }
      },
      { rootMargin: '400px 0px', threshold: 0.01 },  // pre-render 400px ahead
    );
    observer.observe(el);
    return () => observer.disconnect();
  }, [visible]);

  // When this thumb becomes the current page (via toolbar nav or room jump),
  // ensure it's scrolled into view in the sidebar — otherwise user can't see
  // which page they're on for jumps that move past visible thumbs.
  useEffect(() => {
    if (!isActive || !ref.current) return;
    ref.current.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
  }, [isActive]);

  const color = meta?.type ? PAGE_TYPE_COLOR[meta.type] : '#78716c';
  const typeLabel = meta?.type ? PAGE_TYPE_LABELS[meta.type] : null;
  const dotClass = CONFIDENCE_DOT[meta?.confidence] || 'bg-stone-500';
  const tooltip = meta
    ? `${typeLabel || 'Nežinomas'}${
        meta.label && meta.label !== typeLabel ? ` — ${meta.label}` : ''
      }${meta.confidence ? ` · ${CONFIDENCE_LABEL[meta.confidence]} pasitikėjimas` : ''}${
        meta.pastabos ? `\n${meta.pastabos}` : ''
      }`
    : `Puslapis ${pageNr}`;

  return (
    <button
      ref={ref}
      onClick={() => setPage(pageNr)}
      title={tooltip}
      className={`w-full p-1 rounded border-2 transition-colors text-left ${
        isActive ? 'border-amber-500' : 'border-stone-700 hover:border-stone-500'
      }`}
    >
      <div
        className="bg-white rounded overflow-hidden relative"
        style={{ minHeight: 180 }}
      >
        {visible ? (
          <Page
            pageNumber={pageNr}
            width={140}
            renderTextLayer={false}
            renderAnnotationLayer={false}
            loading={
              <div className="flex items-center justify-center h-[180px] text-stone-400 text-[11px]">
                #{pageNr}
              </div>
            }
          />
        ) : (
          <div className="flex items-center justify-center h-[180px] text-stone-300 text-[11px]">
            #{pageNr}
          </div>
        )}
        {meta?.confidence && (
          <span
            className={`absolute top-1 right-1 w-2 h-2 rounded-full ring-1 ring-white/80 ${dotClass}`}
            title={`Pasitikėjimas: ${CONFIDENCE_LABEL[meta.confidence] || meta.confidence}`}
          />
        )}
      </div>
      <div className="flex items-start gap-1 mt-1.5 px-0.5">
        <span
          className="w-1.5 h-1.5 rounded-full shrink-0 mt-1"
          style={{ background: color }}
        />
        <div className="min-w-0 flex-1">
          <div className="text-[11px] text-stone-200 font-semibold leading-tight">
            Psl. {pageNr}
            {typeLabel && (
              <span className="font-normal text-stone-300"> · {typeLabel}</span>
            )}
          </div>
          {meta?.label && meta.label !== typeLabel && (
            <div className="text-[10px] text-stone-400 truncate leading-tight">
              {meta.label}
            </div>
          )}
        </div>
      </div>
    </button>
  );
}

// Sidebar with all page thumbnails. ONE <Document> instance shared by all
// thumbs (was: one per thumb = 65× PDF parses on rangovas P1). Pages render
// lazily through ThumbnailItem's IntersectionObserver.
//
// Sprint H6 (2026-04-29): collapsible. When collapsed, narrow strip with
// just page numbers + active dot. Toggle persists in localStorage so user
// preference holds across sessions.
function PageThumbnails({ totalPages, currentPage, setPage, pageMeta, fileUrl, missingTypes }) {
  const [collapsed, setCollapsed] = useState(() => {
    try { return localStorage.getItem('samatu_thumbs_collapsed') === '1'; }
    catch { return false; }
  });
  const toggle = () => {
    setCollapsed(c => {
      const next = !c;
      try { localStorage.setItem('samatu_thumbs_collapsed', next ? '1' : '0'); } catch {}
      return next;
    });
  };

  if (collapsed) {
    return (
      <div className="w-10 shrink-0 bg-stone-900 border-r border-stone-700 overflow-y-auto flex flex-col items-stretch">
        <button
          onClick={toggle}
          title="Išplėsti puslapių miniatiūras"
          className="text-stone-400 hover:bg-stone-700 hover:text-stone-100 py-1.5 border-b border-stone-700"
        >
          <ChevronRight className="w-4 h-4 mx-auto" />
        </button>
        {Array.from({ length: totalPages || 0 }, (_, i) => i + 1).map(p => {
          const isActive = p === currentPage;
          return (
            <button
              key={p}
              onClick={() => setPage(p)}
              title={`Puslapis ${p}`}
              className={`text-[10px] tabular-nums py-1.5 border-b border-stone-800 transition-colors ${
                isActive ? 'bg-stone-100 text-stone-900 font-semibold' : 'text-stone-400 hover:bg-stone-700'
              }`}
            >
              {p}
            </button>
          );
        })}
      </div>
    );
  }

  return (
    <div className="w-40 shrink-0 bg-stone-900 border-r border-stone-700 overflow-y-auto p-2 space-y-2 relative">
      <button
        onClick={toggle}
        title="Suskleisti miniatiūras"
        className="absolute top-1 right-1 z-10 p-1 text-stone-400 hover:bg-stone-700 hover:text-stone-100 rounded"
      >
        <ChevronLeft className="w-3 h-3" />
      </button>
      {missingTypes && missingTypes.length > 0 && (
        <div className="bg-amber-950/60 border border-amber-700/60 rounded p-2 mb-1">
          <div className="flex items-center gap-1.5 mb-1">
            <AlertTriangle className="w-3 h-3 text-amber-400 shrink-0" />
            <span className="text-[10px] font-semibold text-amber-200">
              Trūksta brėžinių
            </span>
          </div>
          <ul className="text-[10px] text-amber-100/80 leading-tight space-y-0.5">
            {missingTypes.map(t => (
              <li key={t}>• {PAGE_TYPE_LABELS[t] || t}</li>
            ))}
          </ul>
        </div>
      )}
      {fileUrl && (totalPages || 0) > 0 && (
        <Document file={fileUrl} loading={null} error={null}>
          {Array.from({ length: totalPages }, (_, i) => i + 1).map(p => (
            <ThumbnailItem
              key={p}
              pageNr={p}
              currentPage={currentPage}
              setPage={setPage}
              meta={pageMeta?.[p]}
            />
          ))}
        </Document>
      )}
    </div>
  );
}

// ── Markup canvas (Konva overlay) ────────────────────────────────────────────

function MarkupCanvas({
  width, height, markups, page, tool,
  onAddMarkup, onDeleteMarkup, showMarkups,
  calibPoints, onCalibPick,
  pageScale,
  polygons, polygonDraft, onPolygonDraftChange, onFinalizePolygon,
  onDeletePolygon,
  pageLines, linesLoading,
}) {
  // Linijų scale faktorius: PDF unitai → canvas px
  // Konva canvas dydis = width/height. PDF dokumentas turi page_width_pdf.
  const linesScaleX = pageLines && pageLines.page_width_pdf
    ? width / pageLines.page_width_pdf : 1;
  const linesScaleY = pageLines && pageLines.page_height_pdf
    ? height / pageLines.page_height_pdf : 1;

  // Konvertuotos linijos canvas pikseliais
  const canvasLines = useMemo(() => {
    if (!pageLines || !pageLines.lines) return [];
    return pageLines.lines.map(ln => ({
      x1: ln.x1 * linesScaleX,
      y1: ln.y1 * linesScaleY,
      x2: ln.x2 * linesScaleX,
      y2: ln.y2 * linesScaleY,
    }));
  }, [pageLines, linesScaleX, linesScaleY]);

  // Snap kursoriaus point'ą prie artimiausios linijos endpoint'o (corner)
  // arba prie linijos vidurio (perpendicular projection)
  const snapPoint = (pos) => {
    if (tool !== 'polygon' || canvasLines.length === 0) return pos;
    const SNAP_RADIUS = 8;
    let best = { ...pos, snapped: false };
    let bestDist = SNAP_RADIUS;

    // Pirma — endpoint snap (kampai svarbesni nei vidurys linijos)
    for (const ln of canvasLines) {
      for (const ep of [{ x: ln.x1, y: ln.y1 }, { x: ln.x2, y: ln.y2 }]) {
        const d = Math.sqrt((ep.x - pos.x) ** 2 + (ep.y - pos.y) ** 2);
        if (d < bestDist) {
          bestDist = d;
          best = { x: ep.x, y: ep.y, snapped: true, snapType: 'corner' };
        }
      }
    }

    // Jei nepakliuvo į endpoint'ą, bandom projection į linijos segmentą
    if (!best.snapped) {
      for (const ln of canvasLines) {
        const dx = ln.x2 - ln.x1;
        const dy = ln.y2 - ln.y1;
        const lenSq = dx * dx + dy * dy;
        if (lenSq === 0) continue;
        const t = Math.max(0, Math.min(1,
          ((pos.x - ln.x1) * dx + (pos.y - ln.y1) * dy) / lenSq,
        ));
        const px = ln.x1 + t * dx;
        const py = ln.y1 + t * dy;
        const d = Math.sqrt((px - pos.x) ** 2 + (py - pos.y) ** 2);
        if (d < bestDist) {
          bestDist = d;
          best = { x: px, y: py, snapped: true, snapType: 'edge' };
        }
      }
    }

    return best;
  };
  const [drawing, setDrawing] = useState(null);
  const [hoverPos, setHoverPos] = useState(null);
  const stageRef = useRef(null);

  const pageMarkups = markups.filter(m => m.page === page);
  const pagePolygons = (polygons || []).filter(p => p.page === page);

  const handleMouseDown = (e) => {
    const pos = e.target.getStage().getPointerPosition();

    if (tool === 'scale') {
      if (!calibPoints.p1) {
        onCalibPick({ p1: pos, p2: null });
      } else if (!calibPoints.p2) {
        onCalibPick({ p1: calibPoints.p1, p2: pos });
      }
      return;
    }

    if (tool === 'polygon') {
      // Polygon brūkšniojimas — su snap'u į vector linijas
      const snapped = snapPoint(pos);
      // Jei spaudžiu ant pirmo point'o (radiusu 10px) — closing → finalize
      if (polygonDraft && polygonDraft.points.length >= 3) {
        const first = polygonDraft.points[0];
        const dist = Math.sqrt((snapped.x - first.x)**2 + (snapped.y - first.y)**2);
        if (dist < 10) {
          onFinalizePolygon();
          return;
        }
      }
      const points = polygonDraft ? polygonDraft.points : [];
      onPolygonDraftChange({ points: [...points, { x: snapped.x, y: snapped.y }] });
      return;
    }

    if (tool === 'select' || tool === 'erase') return;

    if (tool === 'rect') {
      setDrawing({ type: 'rect', x: pos.x, y: pos.y, w: 0, h: 0 });
    } else if (tool === 'comment') {
      const text = window.prompt('Komentaras:', '');
      if (text) {
        onAddMarkup(makeMarkup(MARKUP_TYPES.COMMENT, {
          page, x: pos.x, y: pos.y, text, color: '#f59e0b',
        }));
      }
    }
  };

  const handleDoubleClick = (e) => {
    if (tool === 'polygon' && polygonDraft && polygonDraft.points.length >= 3) {
      onFinalizePolygon();
    }
  };

  // Live area + perimeter skaičiavimas polygon draft'ui
  const draftMeasurements = (() => {
    if (!polygonDraft || polygonDraft.points.length < 2 || !pageScale) return null;
    const pxPm = pageScale.pixels_per_meter;
    // Su hover position — preview "kaip atrodytų jei dabar uždarytume"
    const previewPoints = hoverPos
      ? [...polygonDraft.points, hoverPos]
      : polygonDraft.points;
    if (previewPoints.length < 3) return null;
    const area = polygonAreaM2(previewPoints, pxPm);
    const perim = polygonPerimeterM(previewPoints, pxPm);
    return { area, perim };
  })();

  const handleMouseMove = (e) => {
    const rawPos = e.target.getStage().getPointerPosition();
    // Polygon mode'e — snap'inam hover poziciją vizualizacijai
    const pos = tool === 'polygon' ? snapPoint(rawPos) : rawPos;
    setHoverPos(pos);
    if (!drawing) return;
    if (drawing.type === 'rect') {
      setDrawing({ ...drawing, w: rawPos.x - drawing.x, h: rawPos.y - drawing.y });
    }
  };

  const handleMouseUp = () => {
    if (!drawing) return;
    if (drawing.type === 'rect' && (Math.abs(drawing.w) > 5 && Math.abs(drawing.h) > 5)) {
      const label = window.prompt('Pavadinimas (pvz. „Vonia 6m²"):', '') || '';
      onAddMarkup(makeMarkup(MARKUP_TYPES.RECT, {
        page,
        x: Math.min(drawing.x, drawing.x + drawing.w),
        y: Math.min(drawing.y, drawing.y + drawing.h),
        w: Math.abs(drawing.w),
        h: Math.abs(drawing.h),
        label,
        color: '#f59e0b',
      }));
    }
    setDrawing(null);
  };

  const handleMarkupClick = (markup) => {
    if (tool === 'erase') {
      if (window.confirm(`Ištrinti pažymėjimą „${markup.label || 'be pavadinimo'}"?`)) {
        onDeleteMarkup(markup.id);
      }
    }
  };

  // Scale / polygon tool aktyvuotas — visada matomas (net jei showMarkups=false)
  const isScaleMode = tool === 'scale';
  const isPolygonMode = tool === 'polygon';

  if (!showMarkups && !isScaleMode && !isPolygonMode) return null;

  // Scale preview: linija tarp p1 ir hover/p2
  const scalePreviewEnd = calibPoints.p1 && !calibPoints.p2 ? hoverPos : calibPoints.p2;

  return (
    <Stage
      ref={stageRef}
      width={width}
      height={height}
      onMouseDown={handleMouseDown}
      onMouseMove={handleMouseMove}
      onMouseUp={handleMouseUp}
      onDblClick={handleDoubleClick}
      style={{
        position: 'absolute',
        top: 0,
        left: 0,
        cursor: isScaleMode ? 'crosshair' :
                isPolygonMode ? 'crosshair' :
                tool === 'rect' || tool === 'comment' ? 'crosshair' :
                tool === 'erase' ? 'not-allowed' : 'default',
      }}
    >
      <Layer>
        {/* SAVED POLYGONS (matuoti zonos) */}
        {showMarkups && pagePolygons.map(poly => {
          const flatPoints = poly.points.flatMap(p => [p.x, p.y]);
          const isAi = poly.source === 'ai';
          const color = poly.color || (isAi ? '#3b82f6' : '#10b981');
          // Centroid label pozicijai
          const cx = poly.points.reduce((s, p) => s + p.x, 0) / poly.points.length;
          const cy = poly.points.reduce((s, p) => s + p.y, 0) / poly.points.length;
          return (
            <Group key={poly.id}
              onClick={() => {
                if (tool === 'erase') {
                  if (window.confirm(`Ištrinti „${poly.label || 'patalpą'}"?`)) {
                    onDeletePolygon?.(poly.id);
                  }
                }
              }}>
              <Line
                points={flatPoints}
                closed
                fill={`${color}22`}
                stroke={color}
                strokeWidth={2}
              />
              <KonvaText
                x={cx - 30} y={cy - 12}
                text={`${poly.label || 'Patalpa'}\n${(poly.area_m2 || 0).toFixed(1)} m²`}
                fontSize={11} fontStyle="bold"
                fill={color}
                align="center"
                width={60}
              />
            </Group>
          );
        })}

        {/* POLYGON DRAFT (brūkšniojama) */}
        {isPolygonMode && polygonDraft && polygonDraft.points.length > 0 && (
          <Group>
            {/* Užbaigtas iki dabartinio point'o */}
            {polygonDraft.points.length >= 2 && (
              <Line
                points={polygonDraft.points.flatMap(p => [p.x, p.y])}
                stroke="#10b981" strokeWidth={2}
              />
            )}
            {/* Linija nuo paskutinio point'o iki kursoriaus */}
            {hoverPos && (
              <Line
                points={[
                  polygonDraft.points[polygonDraft.points.length - 1].x,
                  polygonDraft.points[polygonDraft.points.length - 1].y,
                  hoverPos.x, hoverPos.y,
                ]}
                stroke="#10b981" strokeWidth={2} dash={[4, 4]} opacity={0.6}
              />
            )}
            {/* Kursoriaus → pirmas point (close hint) */}
            {hoverPos && polygonDraft.points.length >= 3 && (() => {
              const first = polygonDraft.points[0];
              const dist = Math.sqrt((hoverPos.x - first.x)**2 + (hoverPos.y - first.y)**2);
              if (dist < 10) {
                return (
                  <Circle x={first.x} y={first.y} radius={8}
                    fill="#10b98144" stroke="#10b981" strokeWidth={2} />
                );
              }
              return null;
            })()}
            {/* Point dot'ai */}
            {polygonDraft.points.map((p, i) => (
              <Circle key={i} x={p.x} y={p.y} radius={4}
                fill="white" stroke="#10b981" strokeWidth={2} />
            ))}
            {/* Real-time area + perimeter rodyklė */}
            {draftMeasurements && hoverPos && (
              <Group>
                <Rect
                  x={hoverPos.x + 12} y={hoverPos.y + 8}
                  width={130} height={36}
                  fill="white" stroke="#10b981" strokeWidth={1}
                  cornerRadius={4}
                />
                <KonvaText
                  x={hoverPos.x + 18} y={hoverPos.y + 13}
                  text={`Plotas: ${draftMeasurements.area.toFixed(1)} m²\nPerim: ${draftMeasurements.perim.toFixed(1)} m`}
                  fontSize={10} fontStyle="bold"
                  fill="#065f46"
                />
              </Group>
            )}
          </Group>
        )}

        {isPolygonMode && !polygonDraft && hoverPos && (
          <KonvaText
            x={hoverPos.x + 10} y={hoverPos.y - 18}
            text={hoverPos.snapped
              ? `✓ Pritraukta: ${hoverPos.snapType === 'corner' ? 'kampas' : 'siena'}`
              : 'Spauskite pirmą kambario kampą'}
            fontSize={11} fontStyle="bold"
            fill={hoverPos.snapped ? '#059669' : '#10b981'}
          />
        )}
        {isPolygonMode && hoverPos && hoverPos.snapped && (
          <Circle x={hoverPos.x} y={hoverPos.y} radius={6}
            fill="#10b98144" stroke="#10b981" strokeWidth={2} />
        )}
        {isPolygonMode && !pageScale && (
          <Group>
            <Rect x={10} y={10} width={300} height={28}
              fill="#fef3c7" stroke="#d97706" strokeWidth={1} cornerRadius={4} />
            <KonvaText x={18} y={18}
              text="⚠ Pirma kalibruok mastelį (Ruler ikona)"
              fontSize={11} fontStyle="bold" fill="#92400e"
            />
          </Group>
        )}

        {/* SCALE CALIBRATION OVERLAY */}
        {isScaleMode && calibPoints.p1 && (
          <Group>
            <Circle x={calibPoints.p1.x} y={calibPoints.p1.y} radius={5}
              fill="#dc2626" stroke="white" strokeWidth={2} />
            {scalePreviewEnd && (
              <>
                <Line
                  points={[
                    calibPoints.p1.x, calibPoints.p1.y,
                    scalePreviewEnd.x, scalePreviewEnd.y,
                  ]}
                  stroke="#dc2626" strokeWidth={2} dash={[4, 4]}
                />
                <Circle x={scalePreviewEnd.x} y={scalePreviewEnd.y} radius={5}
                  fill={calibPoints.p2 ? "#dc2626" : "#fff"}
                  stroke="#dc2626" strokeWidth={2} />
                {(() => {
                  const dx = scalePreviewEnd.x - calibPoints.p1.x;
                  const dy = scalePreviewEnd.y - calibPoints.p1.y;
                  const px = Math.sqrt(dx * dx + dy * dy);
                  const realM = pageScale ? px / pageScale.pixels_per_meter : null;
                  const midX = (calibPoints.p1.x + scalePreviewEnd.x) / 2;
                  const midY = (calibPoints.p1.y + scalePreviewEnd.y) / 2 - 12;
                  return (
                    <KonvaText
                      x={midX} y={midY}
                      text={realM ? `${px.toFixed(0)} px ≈ ${realM.toFixed(2)} m`
                                  : `${px.toFixed(0)} px`}
                      fontSize={11} fontStyle="bold"
                      fill="#dc2626"
                    />
                  );
                })()}
              </>
            )}
          </Group>
        )}
        {isScaleMode && !calibPoints.p1 && hoverPos && (
          <KonvaText
            x={hoverPos.x + 10} y={hoverPos.y - 18}
            text="Spauskite pradžios tašką"
            fontSize={11} fontStyle="bold" fill="#dc2626"
          />
        )}

        {/* Existing markups */}
        {pageMarkups.map(m => {
          if (m.type === MARKUP_TYPES.RECT) {
            return (
              <Group key={m.id} onClick={() => handleMarkupClick(m)}>
                <Rect
                  x={m.x} y={m.y} width={m.w} height={m.h}
                  fill={`${m.color}33`}
                  stroke={m.color}
                  strokeWidth={2}
                />
                {m.label && (
                  <KonvaText
                    x={m.x + 4} y={m.y + 4}
                    text={m.label}
                    fontSize={12}
                    fill={m.color}
                    fontStyle="bold"
                  />
                )}
              </Group>
            );
          }
          if (m.type === MARKUP_TYPES.COMMENT) {
            return (
              <Group key={m.id} onClick={() => handleMarkupClick(m)}>
                <Rect
                  x={m.x - 4} y={m.y - 4}
                  width={Math.max(80, m.text.length * 7)}
                  height={20}
                  fill="#fef3c7"
                  stroke={m.color}
                  strokeWidth={1}
                  cornerRadius={3}
                />
                <KonvaText
                  x={m.x} y={m.y}
                  text={m.text}
                  fontSize={11}
                  fill="#78350f"
                />
              </Group>
            );
          }
          return null;
        })}

        {/* Drawing in progress */}
        {drawing && drawing.type === 'rect' && (
          <Rect
            x={drawing.x} y={drawing.y}
            width={drawing.w} height={drawing.h}
            fill="#f59e0b22"
            stroke="#f59e0b"
            strokeWidth={2}
            dash={[5, 5]}
          />
        )}
      </Layer>
    </Stage>
  );
}

// ── Main PdfViewer komponentas ───────────────────────────────────────────────

export default function PdfViewer({
  fileUrl, projectId, onMarkupChange,
  // Sprint F4: focusedRoom carries the room user just clicked. When user is
  // viewing the eksplikacija page and the room has bbox info from pdfplumber,
  // we overlay a highlight on its table row.
  focusedRoom = null, pageMeta = null,
  missingTypes = null,       // Phase 14 / QW02: drawing types absent from puslapiai[]
  aiRooms = null,            // Togal-style AI auto-detect rooms su bbox_pct
  onAiRoomClick = null,      // klikus ant AI zonos — koregavimo modal'as
  onAiRoomHover = null,      // hoveris virš AI zonos (Phase 14 / QW05)
  highlightRoomNrs = null,   // Set<roomNr> highlight overlay (Phase 14 / QW05)
  pdfFile = null,            // Original File/Blob for symbol detection (V9 click-to-count)
  onSymbolCountResult = null,// callback when SymbolCounter finds matches
  focusedPage = null,        // Etap 2: tėvinis komponentas nori parodyti specific page
  activeRowId = null,        // Etap 3 placeholder
  hoveredRowId = null,       // Etap 3 placeholder
  darbuSarasas = null,       // Etap 3 placeholder
  eksplikacija_source_page = null,  // ground-truth eksplikacija page jump button
}) {
  const [numPages, setNumPages] = useState(null);
  const [pageNumber, setPageNumber] = useState(1);

  // Auto-switch puslapį, kai focusedPage prop pakeičiamas
  useEffect(() => {
    if (focusedPage && focusedPage !== pageNumber) {
      setPageNumber(focusedPage);
    }
  }, [focusedPage]);  // eslint-disable-line

  // F2: on first load, navigate to first `floor_plan` page if pageMeta classifies
  // any. Skips if focusedPage prop is already set (user-driven nav wins).
  //
  // Sprint §AUDIT (2026-04-29): set autoNavDone=true IMMEDIATELY on entry to
  // prevent re-runs from streaming pageMeta updates. Previously the gate was
  // set AFTER reading pageMeta, so a chunked extraction (pageMeta arrives in
  // 2 updates) could fire navigation twice and overwrite user's deliberate
  // page selection between the two updates.
  const [autoNavDone, setAutoNavDone] = useState(false);
  useEffect(() => {
    if (autoNavDone || !numPages) return;
    setAutoNavDone(true);  // gate FIRST — prevents stream-driven re-runs
    if (focusedPage) return;
    if (pageMeta) {
      for (let p = 1; p <= numPages; p++) {
        if (pageMeta[p]?.type === 'floor_plan') {
          setPageNumber(p);
          return;
        }
      }
    }
  }, [numPages, pageMeta, focusedPage, autoNavDone]);
  const [scale, setScale] = useState(1.2);
  const [tool, setTool] = useState('select');

  // Sprint G8 (2026-04-29): unified Layers state. showMarkups now derives
  // from layers.markups so toggling either path stays in sync.
  const [layers, setLayers] = useState(loadLayersState);
  const showMarkups = layers.markups;
  const setShowMarkups = (v) => {
    setLayers(prev => {
      const next = { ...prev, markups: typeof v === 'function' ? v(prev.markups) : v };
      saveLayersState(next);
      return next;
    });
  };

  // Production-grade UI: hide power-user tools (mastelis, markup, undo/redo)
  // until user opts into "Pažangu" mode. Setting persisted per browser.
  const [showAdvanced, setShowAdvanced] = useState(() => {
    try { return localStorage.getItem('samatu_pdf_advanced') === '1'; } catch { return false; }
  });
  useEffect(() => {
    try { localStorage.setItem('samatu_pdf_advanced', showAdvanced ? '1' : '0'); } catch {}
  }, [showAdvanced]);
  const [markups, setMarkups] = useState(() => loadMarkups(projectId));
  const [pageDims, setPageDims] = useState({ width: 800, height: 1000 });
  const containerRef = useRef(null);

  // Phase C-1 (2026-04-29) Task 1: explicit pdf.destroy() + page.cleanup() on
  // unmount. Without this, long sessions leak ~30 MB/page in pdf.js worker
  // memory because react-pdf doesn't tear down the PDFDocumentProxy on unmount.
  const pdfDocRef = useRef(null);
  const pageProxyRef = useRef(null);

  // Diena 6: SymbolCounter shared state (toolbar viewport-fixed + overlay PDF coords)
  const [symbolState, setSymbolState] = useState({
    active: false, loading: false, matches: null,
    error: null, selectedType: null, lastClick: null,
  });

  // Takeoff state — masteliai, polygon'ai, undo/redo (V2)
  const [takeoff, setTakeoff] = useState(() => loadTakeoff(projectId));

  // Mastelio kalibracijos pickup state'as
  const [calibPoints, setCalibPoints] = useState({ p1: null, p2: null });

  // Polygon brūkšniojimo state'as: dabartinis polygon's su points masyvu
  const [polygonDraft, setPolygonDraft] = useState(null); // {points: [{x,y}, ...]}
  const [pendingPolygon, setPendingPolygon] = useState(null); // baigtas, laukiam modal'o

  // Vector PDF linijos snap'ui — fetch'inamos kai polygon mode aktyvuotas
  const [pageLines, setPageLines] = useState(null);  // {lines, page_width_pdf, page_height_pdf}
  const [linesLoading, setLinesLoading] = useState(false);

  useEffect(() => {
    if (tool !== 'polygon') return;
    // Sprint §AUDIT (2026-04-29): cancel-on-stale to prevent race conditions
    // when user rapidly switches tools / pages. `cancelled` guards setState
    // so a slow fetch from page A doesn't overwrite a fast fetch from page B.
    let cancelled = false;
    setLinesLoading(true);
    fetchPageLines(projectId, pageNumber)
      .then(data => {
        if (!cancelled) {
          setPageLines(data);
          setLinesLoading(false);
        }
      })
      .catch(err => {
        if (!cancelled) {
          console.warn('[PdfViewer] fetchPageLines failed:', err);
          setLinesLoading(false);
        }
      });
    return () => { cancelled = true; };
  }, [tool, projectId, pageNumber]);

  // Auto-save markups
  useEffect(() => {
    saveMarkups(projectId, markups);
    onMarkupChange?.(markups);
  }, [markups, projectId, onMarkupChange]);

  // Auto-save takeoff
  useEffect(() => {
    saveTakeoff(projectId, takeoff);
  }, [takeoff, projectId]);

  // Reset calibration points / polygon draft kai keičiasi page arba tool
  useEffect(() => {
    setCalibPoints({ p1: null, p2: null });
    setPolygonDraft(null);
  }, [pageNumber, tool]);

  // Phase C-1 (2026-04-29) Task 1: explicit PDF teardown on unmount. react-pdf
  // does not destroy the underlying PDFDocumentProxy / PDFPageProxy when its
  // component unmounts, which leaks the rendered page bitmap (~30 MB/page) and
  // its worker-side memory. Empty deps array → runs ONLY on unmount.
  useEffect(() => {
    return () => {
      try {
        pageProxyRef.current?.cleanup?.();
      } catch (e) {
        console.warn('[PdfViewer] page.cleanup failed', e);
      }
      try {
        pdfDocRef.current?.destroy?.();
      } catch (e) {
        console.warn('[PdfViewer] pdf.destroy failed', e);
      }
      pageProxyRef.current = null;
      pdfDocRef.current = null;
    };
  }, []);

  // Enter / Escape klavišai polygon brūkšniojimui
  useEffect(() => {
    const onKey = (e) => {
      if (tool !== 'polygon' || !polygonDraft) return;
      if (e.key === 'Enter' && polygonDraft.points.length >= 3) {
        e.preventDefault();
        finalizePolygon();
      } else if (e.key === 'Escape') {
        e.preventDefault();
        setPolygonDraft(null);
      } else if (e.key === 'Backspace' && polygonDraft.points.length > 0) {
        e.preventDefault();
        setPolygonDraft(d => ({ points: d.points.slice(0, -1) }));
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [tool, polygonDraft]);

  const finalizePolygon = () => {
    if (!polygonDraft || polygonDraft.points.length < 3) return;
    const scale = getPageScale(takeoff, pageNumber);
    const pxPerMeter = scale?.pixels_per_meter || 1;
    const area = polygonAreaM2(polygonDraft.points, pxPerMeter);
    const perim = polygonPerimeterM(polygonDraft.points, pxPerMeter);
    setPendingPolygon({
      points: polygonDraft.points,
      page: pageNumber,
      area_m2: area,
      perimeter_m: perim,
      pxPerMeter,
    });
    setPolygonDraft(null);
  };

  const handlePolygonRoomConfirm = ({ label, paskirtis, lubu_aukstis_m }) => {
    if (!pendingPolygon) return;
    const newRoomNr = `M${(takeoff.polygons || []).length + 1}`;
    setTakeoff(t => addPolygon(t, {
      page: pendingPolygon.page,
      points: pendingPolygon.points,
      room_nr: newRoomNr,
      type: 'room',
      label,
      paskirtis,
      lubu_aukstis_m,
      area_m2: pendingPolygon.area_m2,
      perimeter_m: pendingPolygon.perimeter_m,
      source: 'manual',
    }));
    setPendingPolygon(null);
  };

  // Cmd+Z / Cmd+Shift+Z keyboard shortcuts
  useEffect(() => {
    const onKey = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'z' && !e.shiftKey) {
        e.preventDefault();
        if (canUndo(takeoff)) setTakeoff(t => takeoffUndo(t));
      } else if ((e.metaKey || e.ctrlKey) && (e.key === 'Z' || (e.key === 'z' && e.shiftKey))) {
        e.preventDefault();
        if (canRedo(takeoff)) setTakeoff(t => takeoffRedo(t));
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [takeoff]);

  // Sprint G7: industry keyboard shortcuts (Togal/Bluebeam/Kreo conventions).
  // Skip when user is typing in inputs/textarea/contenteditable so we don't
  // hijack number entry in price fields etc.
  useEffect(() => {
    const isTyping = (target) => {
      if (!target) return false;
      const tag = target.tagName;
      if (tag === 'INPUT' || tag === 'TEXTAREA' || tag === 'SELECT') return true;
      return target.isContentEditable === true;
    };
    const onKey = (e) => {
      if (isTyping(e.target)) return;
      // Modifier-bearing chords are owned elsewhere (undo/redo, browser zoom).
      if (e.metaKey || e.ctrlKey || e.altKey) return;

      if (e.key === '+' || e.key === '=') {
        e.preventDefault();
        setScale(s => Math.min(3, +(s + 0.2).toFixed(2)));
      } else if (e.key === '-' || e.key === '_') {
        e.preventDefault();
        setScale(s => Math.max(0.3, +(s - 0.2).toFixed(2)));
      } else if (e.key === '0') {
        e.preventDefault();
        setScale(1);
      } else if (e.key === 'f' || e.key === 'F') {
        // Fit-to-width: reset to default scale (1.2). Real fit-to-width would
        // require viewport math vs page width; 1.2 is the visual default.
        e.preventDefault();
        setScale(1.2);
      } else if (e.key === '[') {
        e.preventDefault();
        setPageNumber(p => Math.max(1, p - 1));
      } else if (e.key === ']') {
        e.preventDefault();
        setPageNumber(p => Math.min(numPages || p, p + 1));
      } else if (e.key === 'Escape') {
        // Esc returns to select tool when not drawing polygon (drawing-mode
        // Esc is handled by the polygon useEffect above and runs first via
        // its own listener; this is only the fallthrough).
        if (tool !== 'select' && !polygonDraft) {
          e.preventDefault();
          setTool('select');
        }
      }
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [numPages, tool, polygonDraft]);

  const currentScale = getPageScale(takeoff, pageNumber);

  const handleCalibrationConfirm = ({ pixels_per_meter, apply_all_pages }) => {
    setTakeoff(t => apply_all_pages
      ? applyScaleToAll(t, pixels_per_meter, numPages || 1)
      : setPageScale(t, pageNumber, pixels_per_meter, 'manual')
    );
    setCalibPoints({ p1: null, p2: null });
    setTool('select');
  };

  const handleCalibrationCancel = () => {
    setCalibPoints({ p1: null, p2: null });
    setTool('select');
  };

  // F4: focusedRoom no longer drives page navigation — parent computes the
  // target page (eksplikacija_source_page if room has bbox, else puslapio_nr)
  // and passes it via focusedPage. The room object is used here only for the
  // EksplikacijaRowOverlay to know which row to highlight.

  const handleAddMarkup = (m) => setMarkups(prev => [...prev, m]);
  const handleDeleteMarkup = (id) => setMarkups(prev => prev.filter(x => x.id !== id));
  const handleClearAll = () => {
    if (window.confirm(`Ištrinti VISUS ${markups.length} pažymėjimus?`)) {
      setMarkups([]);
    }
  };

  if (!fileUrl) {
    return (
      <div className="flex items-center justify-center h-full bg-stone-100 text-stone-500 p-8">
        <p>PDF brėžinys nepateiktas</p>
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full bg-stone-950">
      <ToolBar
        tool={tool} setTool={setTool}
        scale={scale} setScale={setScale}
        page={pageNumber} setPage={setPageNumber}
        totalPages={numPages}
        showMarkups={showMarkups} setShowMarkups={setShowMarkups}
        pageScaleInfo={currentScale}
        onUndo={() => setTakeoff(t => takeoffUndo(t))}
        onRedo={() => setTakeoff(t => takeoffRedo(t))}
        undoOk={canUndo(takeoff)}
        redoOk={canRedo(takeoff)}
        eksplikacija_source_page={eksplikacija_source_page}
        showAdvanced={showAdvanced} setShowAdvanced={setShowAdvanced}
        layers={layers} setLayers={(next) => { setLayers(next); saveLayersState(next); }}
      />

      <div className="flex flex-1 overflow-hidden">
        {/* Sprint H1: Togal-style left tool rail — always visible, shows
            current tool mode (Select/Polygon/Mastelis/etc) with icons. */}
        <LeftToolRail
          tool={tool}
          setTool={setTool}
          showAdvanced={showAdvanced}
          setShowAdvanced={setShowAdvanced}
        />

        <PageThumbnails
          totalPages={numPages}
          currentPage={pageNumber}
          setPage={setPageNumber}
          pageMeta={pageMeta}
          missingTypes={missingTypes}
          fileUrl={fileUrl}
        />

        <div
          ref={containerRef}
          className="flex-1 overflow-auto bg-stone-800 p-4 flex items-center justify-center relative"
          style={{
            // Default cursor = grab (drag-to-pan when no markup tool active)
            cursor: tool === 'select' ? 'grab' : 'default',
            // Prevent text selection while panning
            userSelect: 'none',
          }}
          onMouseDown={(e) => {
            // Only enable drag-pan in default 'select' tool — markup tools own their own cursor.
            if (tool !== 'select') return;
            // Skip if click landed on a button or interactive element
            if (e.target.closest('button, a, input, [role="button"]')) return;
            const el = containerRef.current;
            if (!el) return;
            const startX = e.clientX;
            const startY = e.clientY;
            const startScrollLeft = el.scrollLeft;
            const startScrollTop = el.scrollTop;
            el.style.cursor = 'grabbing';
            const onMove = (mv) => {
              el.scrollLeft = startScrollLeft - (mv.clientX - startX);
              el.scrollTop = startScrollTop - (mv.clientY - startY);
            };
            const onUp = () => {
              el.style.cursor = 'grab';
              window.removeEventListener('mousemove', onMove);
              window.removeEventListener('mouseup', onUp);
            };
            window.addEventListener('mousemove', onMove);
            window.addEventListener('mouseup', onUp);
          }}
          onWheel={(e) => {
            // Ctrl+wheel (or Cmd+wheel on Mac) → zoom; plain wheel → scroll
            if (!(e.ctrlKey || e.metaKey)) return;
            e.preventDefault();
            const delta = e.deltaY < 0 ? 0.1 : -0.1;
            setScale(s => Math.max(0.3, Math.min(3, +(s + delta).toFixed(2))));
          }}
        >
          <div className="relative inline-block bg-white shadow-2xl">
            <Document
              file={fileUrl}
              onLoadSuccess={(pdf) => {
                // Phase C-1 Task 1: capture PDFDocumentProxy for unmount cleanup.
                pdfDocRef.current = pdf;
                setNumPages(pdf.numPages);
              }}
              loading={<PdfSkeleton label="Krauname brėžinį…" />}
              error={
                <div className="p-8 bg-red-50 text-red-600 rounded border border-red-200" style={{ minWidth: 480 }}>
                  <div className="font-semibold mb-1">Nepavyko įkelti brėžinio</div>
                  <div className="text-xs text-red-500/80">
                    Patikrink, ar PDF nesugadintas. Atsinaujink puslapį arba įkelk projektą iš naujo.
                  </div>
                </div>
              }
            >
              <Page
                pageNumber={pageNumber}
                scale={scale}
                onLoadSuccess={(p) => {
                  // Phase C-1 Task 1: capture PDFPageProxy for unmount cleanup.
                  // react-pdf 9.x passes the underlying PDFPageProxy directly
                  // (extended with width/height shortcuts). Use optional
                  // chaining defensively in case of future API changes.
                  pageProxyRef.current = p;
                  setPageDims({ width: p.width * scale, height: p.height * scale });
                }}
                renderTextLayer={false}
                renderAnnotationLayer={false}
                loading={
                  <PdfSkeleton
                    width={pageDims.width || 600}
                    height={pageDims.height || 800}
                    label={`Renderiame psl. ${pageNumber}…`}
                  />
                }
              />
            </Document>

            {/* AI Auto-Detect Rooms Overlay (Togal-style). Sprint G8: gated
                by layers.rooms — independent of markups visibility. */}
            {aiRooms && layers.rooms && (
              <AiRoomOverlay
                width={pageDims.width}
                height={pageDims.height}
                page={pageNumber}
                rooms={aiRooms}
                onRoomClick={onAiRoomClick}
                onRoomHover={onAiRoomHover}
                highlightRoomNrs={highlightRoomNrs}
              />
            )}

            {/* F4: Eksplikacija page row highlight — when on the eksplikacija
                page and a focused room has bbox, pulse a yellow rect over its
                table row so the user can verify the area's source. */}
            {focusedRoom && eksplikacija_source_page && layers.eksplikacija && (
              <EksplikacijaRowOverlay
                width={pageDims.width}
                height={pageDims.height}
                room={focusedRoom}
                page={pageNumber}
                eksplikacijaPage={eksplikacija_source_page}
              />
            )}

            {/* Sprint G6: room polygon flash on floor plan page when user
                clicks a room in the side panel. bbox_pct (Vision-emitted
                fractional coords) drives the rectangle position. */}
            {focusedRoom && focusedRoom.bbox_pct && (
              <FocusFlashOverlay
                width={pageDims.width}
                height={pageDims.height}
                room={focusedRoom}
                page={pageNumber}
              />
            )}

            {/* Trace Overlay (Etap 3): pagal active/hovered row — dot/poly/line */}
            {(activeRowId || hoveredRowId) && pageDims.width > 0 && darbuSarasas && (() => {
              const activeRow = darbuSarasas.find(d => d._id === activeRowId);
              const hoveredRow = darbuSarasas.find(d => d._id === hoveredRowId);
              if (!activeRow && !hoveredRow) return null;
              // page_width/height_pdf — gauname iš pirmo trace_link, kuris jį turi
              const anyLink = (activeRow?.trace_links || hoveredRow?.trace_links || [])
                .find(l => l.page_width_pdf);
              return (
                <TraceOverlay
                  width={pageDims.width}
                  height={pageDims.height}
                  page={pageNumber}
                  activeRow={activeRow}
                  hoveredRow={hoveredRow}
                  pageWidthPdf={anyLink?.page_width_pdf}
                  pageHeightPdf={anyLink?.page_height_pdf}
                />
              );
            })()}

            {/* SymbolCounter removed — replaced by `detected_symbols_summary`
                in main Vision prompt that auto-fills Elektros pozicijos.
                If user wants per-page click-to-count back, route via toolbar
                button drawer (not always-on overlay). */}

            <MarkupCanvas
              width={pageDims.width}
              height={pageDims.height}
              markups={markups}
              page={pageNumber}
              tool={tool}
              onAddMarkup={handleAddMarkup}
              onDeleteMarkup={handleDeleteMarkup}
              showMarkups={showMarkups}
              calibPoints={calibPoints}
              onCalibPick={setCalibPoints}
              pageScale={currentScale}
              polygons={takeoff.polygons}
              polygonDraft={polygonDraft}
              onPolygonDraftChange={setPolygonDraft}
              onFinalizePolygon={finalizePolygon}
              onDeletePolygon={(id) => setTakeoff(t => removePolygon(t, id))}
              pageLines={pageLines}
              linesLoading={linesLoading}
            />
          </div>
        </div>
      </div>

      {/* Sprint H3 (2026-04-29): bottom status bar — ALWAYS visible.
          Shows current tool, scale, and contextual keyboard hint so
          fresh users discover shortcuts and know what mode they're in. */}
      <div className="flex items-center justify-between px-3 py-1.5 bg-stone-900 border-t border-stone-700 text-xs text-stone-400">
        <div className="flex items-center gap-3">
          {/* Always-visible: current tool */}
          <span>
            Įrankis: <strong className="text-stone-200">{
              { select: 'Žymėjimas', polygon: 'Polygon', scale: 'Mastelis',
                comment: 'Komentaras', erase: 'Trinti' }[tool] || tool
            }</strong>
          </span>
          {/* Always-visible: page scale (mastelis) */}
          {currentScale ? (
            <span>
              Mastelis: <strong className="text-stone-200">
                {currentScale.pixels_per_meter.toFixed(0)} px/m
              </strong>
              {currentScale.source === 'inherited' && (
                <span className="text-stone-500 ml-1">(paveldėtas)</span>
              )}
            </span>
          ) : (
            <span className="text-amber-400">
              Mastelis nenustatytas — naudok „Pažangu" → liniuotė
            </span>
          )}
          {/* Always-visible: keyboard hint */}
          <span className="text-stone-500 hidden md:inline">
            ⌨ <kbd className="px-1 rounded bg-stone-800">F</kbd> pritaikyti
            {' · '}<kbd className="px-1 rounded bg-stone-800">+</kbd>/<kbd className="px-1 rounded bg-stone-800">−</kbd> mastelis
            {' · '}<kbd className="px-1 rounded bg-stone-800">[</kbd>/<kbd className="px-1 rounded bg-stone-800">]</kbd> psl
            {' · '}<kbd className="px-1 rounded bg-stone-800">Esc</kbd> grįžti
          </span>
          {showAdvanced && (
            <>
              <span>Žymėjimai: <strong className="text-stone-200">{markups.length}</strong></span>
              {(takeoff.polygons || []).length > 0 && (
                <span>Zonos: <strong className="text-stone-200">{(takeoff.polygons || []).length}</strong></span>
              )}
            </>
          )}
          {tool === 'scale' && (
            <span className="text-red-400">
              {!calibPoints.p1
                ? 'Spauskite pradžios tašką brėžinyje'
                : !calibPoints.p2
                  ? 'Spauskite pabaigos tašką'
                  : 'Įveskite atstumą'}
            </span>
          )}
          {tool === 'polygon' && (
            <span className="text-emerald-400">
              {!polygonDraft
                ? 'Spauskite kambario kampus (Esc atšaukti)'
                : polygonDraft.points.length < 3
                  ? `${polygonDraft.points.length}/3 taškai. Spauskite daugiau (Backspace = ištrinti paskutinį)`
                  : `${polygonDraft.points.length} taškai. Enter = baigti, arba spauskite ant pirmo taško`}
            </span>
          )}
        </div>
        {markups.length > 0 && (
          <button onClick={handleClearAll}
            className="text-red-400 hover:text-red-300 flex items-center gap-1">
            <Trash2 className="w-3 h-3" />
            Ištrinti viską
          </button>
        )}
      </div>

      {/* Scale calibration modal — atsiranda kai 2 taškai pažymėti */}
      {tool === 'scale' && calibPoints.p1 && calibPoints.p2 && (
        <ScaleCalibrationModal
          point1={calibPoints.p1}
          point2={calibPoints.p2}
          totalPages={numPages || 1}
          currentPage={pageNumber}
          onCancel={handleCalibrationCancel}
          onConfirm={handleCalibrationConfirm}
        />
      )}

      {/* Polygon room modal — atsiranda kai polygon baigtas */}
      {pendingPolygon && (
        <PolygonRoomModal
          area_m2={pendingPolygon.area_m2}
          perimeter_m={pendingPolygon.perimeter_m}
          onCancel={() => setPendingPolygon(null)}
          onConfirm={handlePolygonRoomConfirm}
        />
      )}
    </div>
  );
}
