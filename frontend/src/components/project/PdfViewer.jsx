/**
 * PdfViewer — pilnas PDF brėžinių peržiūros komponentas su:
 * - Puslapių navigacija (sidebar thumbnails)
 * - Zoom in/out, pan
 * - Markup overlay per Konva.js (zonas, komentarus, ištrinti AI)
 * - Sync su RoomsGrid (paspaudus kambarį — PDF centruoja)
 *
 * Naudojam: react-pdf + react-konva.
 *
 * IMPORTANT: PDF.js worker turi būti sukonfigūruotas globally.
 * Šitai daroma vienoj vietoj — žr. main.jsx arba app entry.
 */

import { useState, useRef, useEffect, useMemo, useCallback } from 'react';
import { Document, Page, pdfjs } from 'react-pdf';
import 'react-pdf/dist/Page/AnnotationLayer.css';
import 'react-pdf/dist/Page/TextLayer.css';
import {
  ChevronLeft, ChevronRight, ZoomIn, ZoomOut, Maximize2,
  Pencil, Eraser, MessageSquare, Trash2, Eye, EyeOff, Ruler,
  Undo2, Redo2,
} from 'lucide-react';
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
import SymbolCounter from './SymbolCounter';
import TraceOverlay from './TraceOverlay';
import { fetchPageLines } from '@/lib/pdfLinesApi';

// PDF.js worker config — naudojam tą patį pdfjs-dist version'ą per CDN.
// Variantas su `new URL(... import.meta.url)` neveikia su Vite worker'iam.
// CDN patikimas, ne reikia copy'inti worker file'o į public/.
pdfjs.GlobalWorkerOptions.workerSrc =
  `https://cdnjs.cloudflare.com/ajax/libs/pdf.js/${pdfjs.version}/pdf.worker.min.mjs`;

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
}) {
  return (
    <div className="flex items-center gap-1 px-3 py-2 bg-stone-900 border-b border-stone-700 text-white">
      {/* Page nav */}
      <button onClick={() => setPage(Math.max(1, page - 1))}
        disabled={page <= 1}
        className="p-1.5 hover:bg-stone-700 rounded disabled:opacity-30">
        <ChevronLeft className="w-4 h-4" />
      </button>
      <span className="text-xs text-stone-300 mx-2 tabular-nums">
        {page} / {totalPages || '—'}
      </span>
      <button onClick={() => setPage(Math.min(totalPages, page + 1))}
        disabled={page >= totalPages}
        className="p-1.5 hover:bg-stone-700 rounded disabled:opacity-30">
        <ChevronRight className="w-4 h-4" />
      </button>

      <div className="w-px h-5 bg-stone-700 mx-2" />

      {/* Zoom */}
      <button onClick={() => setScale(s => Math.max(0.3, s - 0.2))}
        className="p-1.5 hover:bg-stone-700 rounded">
        <ZoomOut className="w-4 h-4" />
      </button>
      <span className="text-xs text-stone-300 mx-1 tabular-nums w-12 text-center">
        {Math.round(scale * 100)}%
      </span>
      <button onClick={() => setScale(s => Math.min(3, s + 0.2))}
        className="p-1.5 hover:bg-stone-700 rounded">
        <ZoomIn className="w-4 h-4" />
      </button>
      <button onClick={() => setScale(1)}
        title="Originalus dydis"
        className="p-1.5 hover:bg-stone-700 rounded">
        <Maximize2 className="w-4 h-4" />
      </button>

      <div className="w-px h-5 bg-stone-700 mx-2" />

      {/* Mastelio kalibracija */}
      <button onClick={() => setTool(tool === 'scale' ? 'select' : 'scale')}
        className={`p-1.5 rounded flex items-center gap-1 ${tool === 'scale' ? 'bg-stone-100 text-stone-900' : 'hover:bg-stone-700'}`}
        title="Mastelio kalibracija (pažymėk 2 taškus)">
        <Ruler className="w-4 h-4" />
        {pageScaleInfo
          ? <span className="text-[10px] font-mono tabular-nums">
              {(pageScaleInfo.pixels_per_meter).toFixed(0)} px/m
            </span>
          : <span className="text-[10px] text-amber-400">nekalibruota</span>
        }
      </button>

      <div className="w-px h-5 bg-stone-700 mx-2" />

      {/* Markup tools */}
      <button onClick={() => setTool('select')}
        className={`p-1.5 rounded ${tool === 'select' ? 'bg-stone-100 text-stone-900' : 'hover:bg-stone-700'}`}
        title="Pažymėti">
        <Pencil className="w-4 h-4" />
      </button>
      {/* Polygon brūkšniojimas — atsisakyta. Togal stilius = AI auto-detect,
          ne manualus polygon. Realus Togal Button bus per Sprint 2 (V7 prompt
          su bbox koordinatėmis). */}
      <button onClick={() => setTool('comment')}
        className={`p-1.5 rounded ${tool === 'comment' ? 'bg-stone-100 text-stone-900' : 'hover:bg-stone-700'}`}
        title="Pridėti komentarą">
        <MessageSquare className="w-4 h-4" />
      </button>
      <button onClick={() => setTool('erase')}
        className={`p-1.5 rounded ${tool === 'erase' ? 'bg-red-600' : 'hover:bg-stone-700'}`}
        title="Trinti pažymėjimą">
        <Eraser className="w-4 h-4" />
      </button>

      <div className="w-px h-5 bg-stone-700 mx-2" />

      {/* Undo / Redo */}
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
        title={showMarkups ? 'Slėpti pažymėjimus' : 'Rodyti pažymėjimus'}>
        {showMarkups ? <Eye className="w-4 h-4" /> : <EyeOff className="w-4 h-4" />}
      </button>

      <div className="ml-auto" />
    </div>
  );
}

// ── Page thumbnails sidebar ──────────────────────────────────────────────────

// Spalvos pagal puslapio tipą (suderinta su PageStructureCard)
const TYPE_COLOR = {
  floor_plan:     '#2563eb',  // mėlyna
  ceiling_plan:   '#9333ea',  // violetinė
  wall_elevation: '#d97706',  // gintaras
  facade:         '#16a34a',  // žalia
  section:        '#57534e',  // taupe
  electrical:     '#ca8a04',  // tamsi geltona
  plumbing:       '#0891b2',  // ciano
  specification:  '#4f46e5',  // indigo
  unknown:        '#78716c',  // pilkstvo
  title:          '#78716c',
};

function PageThumbnails({ totalPages, currentPage, setPage, pageMeta, fileUrl }) {
  return (
    <div className="w-36 shrink-0 bg-stone-900 border-r border-stone-700 overflow-y-auto p-2 space-y-2">
      {Array.from({ length: totalPages || 0 }, (_, i) => i + 1).map(p => {
        const meta = pageMeta?.[p];
        const color = meta?.type ? TYPE_COLOR[meta.type] : '#78716c';
        const isActive = currentPage === p;
        return (
          <button
            key={p}
            onClick={() => setPage(p)}
            className={`w-full p-1 rounded border-2 transition-colors text-left ${
              isActive ? 'border-amber-500' : 'border-stone-700 hover:border-stone-500'
            }`}
          >
            <div className="bg-white rounded overflow-hidden">
              {fileUrl && (
                <Document file={fileUrl} loading="" error="">
                  <Page pageNumber={p} width={120}
                    renderTextLayer={false} renderAnnotationLayer={false} />
                </Document>
              )}
            </div>
            <div className="flex items-center gap-1 mt-1.5 px-0.5">
              <span className="w-1.5 h-1.5 rounded-full shrink-0"
                    style={{ background: color }} />
              <div className="min-w-0 flex-1">
                <div className="text-xs text-stone-200 font-medium leading-tight">
                  Psl. {p}
                </div>
                {meta?.label && (
                  <div className="text-[10px] text-stone-400 truncate leading-tight">
                    {meta.label}
                  </div>
                )}
              </div>
            </div>
          </button>
        );
      })}
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
              ? `✓ Snap: ${hoverPos.snapType === 'corner' ? 'kampas' : 'siena'}`
              : 'Spauskite pirmą polygon\'o tašką'}
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
  focusedRoom = null, pageMeta = null,
  aiRooms = null,            // Togal-style AI auto-detect rooms su bbox_pct
  onAiRoomClick = null,      // klikus ant AI zonos — koregavimo modal'as
  pdfFile = null,            // Original File/Blob for symbol detection (V9 click-to-count)
  onSymbolCountResult = null,// callback when SymbolCounter finds matches
  focusedPage = null,        // Etap 2: tėvinis komponentas nori parodyti specific page
  activeRowId = null,        // Etap 3 placeholder
  hoveredRowId = null,       // Etap 3 placeholder
  darbuSarasas = null,       // Etap 3 placeholder
}) {
  const [numPages, setNumPages] = useState(null);
  const [pageNumber, setPageNumber] = useState(1);

  // Auto-switch puslapį, kai focusedPage prop pakeičiamas
  useEffect(() => {
    if (focusedPage && focusedPage !== pageNumber) {
      setPageNumber(focusedPage);
    }
  }, [focusedPage]);  // eslint-disable-line
  const [scale, setScale] = useState(1.2);
  const [tool, setTool] = useState('select');
  const [showMarkups, setShowMarkups] = useState(true);
  const [markups, setMarkups] = useState(() => loadMarkups(projectId));
  const [pageDims, setPageDims] = useState({ width: 800, height: 1000 });
  const containerRef = useRef(null);

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
    setLinesLoading(true);
    fetchPageLines(projectId, pageNumber).then(data => {
      setPageLines(data);
      setLinesLoading(false);
    });
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

  // Fokuso sinchronizacija — kai vartotojas spaudžia kambarį RoomsGrid'e,
  // PDF perjungia į tinkamą puslapį
  useEffect(() => {
    if (focusedRoom?.page) {
      setPageNumber(focusedRoom.page);
    }
  }, [focusedRoom]);

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
      />

      <div className="flex flex-1 overflow-hidden">
        <PageThumbnails
          totalPages={numPages}
          currentPage={pageNumber}
          setPage={setPageNumber}
          pageMeta={pageMeta}
          fileUrl={fileUrl}
        />

        <div ref={containerRef}
          className="flex-1 overflow-auto bg-stone-800 p-4 flex items-center justify-center relative">
          {/* Symbol counter TOOLBAR — viewport-fixed (NE PDF coordinatėse) */}
          {pdfFile && (
            <SymbolCounter
              pdfFile={pdfFile}
              pageNr={pageNumber}
              imgWidth={pageDims.width}
              imgHeight={pageDims.height}
              onResultClick={onSymbolCountResult}
              state={symbolState}
              onState={setSymbolState}
              renderToolbar
            />
          )}
          <div className="relative inline-block bg-white shadow-2xl">
            <Document
              file={fileUrl}
              onLoadSuccess={({ numPages: n }) => setNumPages(n)}
              loading={<div className="p-8 text-stone-500">Krauname PDF…</div>}
              error={<div className="p-8 text-red-500">Klaida kraunant PDF</div>}
            >
              <Page
                pageNumber={pageNumber}
                scale={scale}
                onLoadSuccess={(p) => setPageDims({ width: p.width * scale, height: p.height * scale })}
                renderTextLayer={false}
                renderAnnotationLayer={false}
              />
            </Document>

            {/* AI Auto-Detect Rooms Overlay (Togal-style) */}
            {aiRooms && showMarkups && (
              <AiRoomOverlay
                width={pageDims.width}
                height={pageDims.height}
                page={pageNumber}
                rooms={aiRooms}
                onRoomClick={onAiRoomClick}
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

            {/* Symbol Counter OVERLAY — click target + raudoni dots (PDF coords) */}
            {pdfFile && pageDims.width > 0 && (
              <SymbolCounter
                pdfFile={pdfFile}
                pageNr={pageNumber}
                imgWidth={pageDims.width}
                imgHeight={pageDims.height}
                onResultClick={onSymbolCountResult}
                state={symbolState}
                onState={setSymbolState}
                renderOverlay
              />
            )}

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

      {/* Bottom info bar */}
      <div className="flex items-center justify-between px-3 py-1.5 bg-stone-900 border-t border-stone-700 text-xs text-stone-400">
        <div className="flex items-center gap-3">
          <span>Pažymėjimai: <strong className="text-stone-200">{markups.length}</strong></span>
          <span>Polygon'ai: <strong className="text-stone-200">{(takeoff.polygons || []).length}</strong></span>
          {currentScale && (
            <span>
              Mastelis psl. {pageNumber}: <strong className="text-stone-200">
                {currentScale.pixels_per_meter.toFixed(0)} px/m
              </strong>
              {currentScale.source === 'inherited' && (
                <span className="text-stone-500 ml-1">(paveldėtas)</span>
              )}
            </span>
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
