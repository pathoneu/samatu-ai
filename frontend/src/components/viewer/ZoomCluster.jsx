/**
 * ZoomCluster — the drawing's zoom controls, one narrow column at the bottom right (Pathon v3 W5-B, B5; coverage
 * #152, #178; design §3 „zoom cluster bottom-right"): artinti, the level, tolinti, sutalpinti visą lapą / per
 * plotį, priartinti pasirinktą vietą (a box), lapo apžvalga (the minimap) and visas ekranas. The view settings'
 * button (B4) sits at its foot when the host gives one.
 *
 * A column, not a row: measured on demo-objektas_h, a row of these at the bottom right left the mode pill
 * 217 px at 1280 × 720 (the pill is 311 px) — it wrapped, which is why W1-B moved pages and zoom to the top.
 * The column is 42 px wide and leaves the pill its room (numbers in the W5-B report).
 *
 * Area zoom: while armed, a drag on the drawing draws a box and that box fills the window (the host frames it
 * through its FocusZoomer — `onAreaZoom({page, rect})`, rect in the page's displayed fractions); a click
 * without a drag zooms in twice at that spot. Esc leaves it (taken here, in the capture phase, only while it is
 * armed — the viewer's own Esc order is untouched). The minimap shows the sheet on screen with the part in the
 * window outlined; a click or a drag on it moves the window there.
 */
import { useEffect, useRef, useState } from 'react';
import { useScroll } from '@embedpdf/plugin-scroll/react';
import { useZoom, ZoomMode } from '@embedpdf/plugin-zoom/react';
import { ThumbImg } from '@embedpdf/plugin-thumbnail/react';
import { Maximize, Minimize, Maximize2, MoveHorizontal, ScanSearch, Map as MapIcon, ZoomIn, ZoomOut } from 'lucide-react';
import { visiblePageOf } from '@/lib/visiblePage';
import { withKey } from '@/lib/viewerShortcuts';
import { dragToPageRect, scrollToCentre, visibleShare } from '@/lib/zoomCluster';
import { normalizeRotation } from '@/lib/viewerEngine/pageRotation';

const btn = 'h-8 w-8 inline-flex items-center justify-center rounded text-viewer-chrome-foreground hover:bg-viewer-chrome-hover disabled:opacity-40 disabled:hover:bg-transparent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring';
const on = 'bg-viewer-chrome-active/15 text-viewer-chrome-active';
const MINIMAP_W = 184;

function canvasOf(anchor) {
  return anchor?.closest('[data-tv-root]')?.querySelector('[data-testid="viewer-canvas"]') || null;
}
function hostOf(anchor, page) {
  return anchor?.closest('[data-tv-root]')?.querySelector(`[data-page-number="${Number(page)}"]`) || null;
}

/** The box being dragged with the area zoom, over the whole canvas. */
function AreaZoomOverlay({ anchorRef, onDone, onCancel }) {
  const [drag, setDrag] = useState(null);
  const startRef = useRef(null);
  useEffect(() => {
    const onKey = (e) => { if (e.key === 'Escape') { e.stopPropagation(); e.preventDefault(); onCancel(); } };
    window.addEventListener('keydown', onKey, true);
    return () => window.removeEventListener('keydown', onKey, true);
  }, [onCancel]);
  const finish = (e) => {
    const s = startRef.current;
    startRef.current = null;
    if (!s) return;
    const d = { x0: s.x, y0: s.y, x1: e.clientX, y1: e.clientY };
    setDrag(null);
    // the page under the box's centre (the overlay itself is skipped)
    const cx = (d.x0 + d.x1) / 2;
    const cy = (d.y0 + d.y1) / 2;
    const host = document.elementsFromPoint(cx, cy).map((el) => el.closest?.('[data-page-number]')).find(Boolean);
    const canvas = canvasOf(anchorRef.current)?.getBoundingClientRect() || null;
    if (!host) { onCancel(); return; }
    const rect = dragToPageRect(d, host.getBoundingClientRect(), { canvas });
    if (rect) onDone({ page: Number(host.getAttribute('data-page-number')), rect });
    else onCancel();
  };
  const box = drag ? {
    left: Math.min(drag.x0, drag.x1), top: Math.min(drag.y0, drag.y1),
    width: Math.abs(drag.x1 - drag.x0), height: Math.abs(drag.y1 - drag.y0),
  } : null;
  return (
    <div
      className="absolute inset-0 pointer-events-auto cursor-crosshair"
      data-testid="area-zoom-overlay"
      onPointerDown={(e) => {
        if (e.button !== 0) return;
        e.preventDefault();
        e.currentTarget.setPointerCapture?.(e.pointerId);
        startRef.current = { x: e.clientX, y: e.clientY };
        setDrag({ x0: e.clientX, y0: e.clientY, x1: e.clientX, y1: e.clientY });
      }}
      onPointerMove={(e) => { if (startRef.current) setDrag((d) => (d ? { ...d, x1: e.clientX, y1: e.clientY } : d)); }}
      onPointerUp={finish}
    >
      {box && (
        <div
          className="fixed border-2 border-dashed border-[hsl(var(--ov-proposed))] bg-[hsl(var(--ov-proposed)/0.08)] pointer-events-none"
          style={box}
        />
      )}
    </div>
  );
}

/** The sheet on screen in small, the window's part outlined; a click or drag moves the window there. */
function Minimap({ documentId, anchorRef, pages }) {
  const { state: scroll } = useScroll(documentId);
  const page = visiblePageOf(scroll);
  const [frame, setFrame] = useState(null);
  const draggingRef = useRef(false);
  const size = pages?.[page - 1]?.size;
  const rot = normalizeRotation(pages?.[page - 1]?.rotation ?? 0);
  const aspect = size?.width && size?.height ? ((rot === 90 || rot === 270) ? size.width / size.height : size.height / size.width) : 0.7;
  useEffect(() => {
    let raf = 0;
    const measure = () => {
      raf = 0;
      const host = hostOf(anchorRef.current, page)?.getBoundingClientRect();
      const canvas = canvasOf(anchorRef.current)?.getBoundingClientRect();
      const next = host && canvas ? visibleShare(host, canvas) : null;
      setFrame((cur) => (JSON.stringify(cur) === JSON.stringify(next) ? cur : next));
    };
    const schedule = () => { if (!raf) raf = requestAnimationFrame(measure); };
    measure();
    const canvas = canvasOf(anchorRef.current);
    canvas?.addEventListener('scroll', schedule, { passive: true });
    const id = setInterval(schedule, 300);
    return () => { canvas?.removeEventListener('scroll', schedule); clearInterval(id); if (raf) cancelAnimationFrame(raf); };
  }, [page, anchorRef]);
  const moveTo = (e) => {
    const box = e.currentTarget.getBoundingClientRect();
    const host = hostOf(anchorRef.current, page)?.getBoundingClientRect();
    const canvasEl = canvasOf(anchorRef.current);
    if (!host || !canvasEl) return;
    const { dx, dy } = scrollToCentre(host, canvasEl.getBoundingClientRect(), (e.clientX - box.left) / box.width, (e.clientY - box.top) / box.height);
    canvasEl.scrollBy({ left: dx, top: dy, behavior: 'auto' });
  };
  return (
    <div className="pointer-events-auto mb-16 rounded-panel border border-border bg-card shadow-md p-1.5" data-minimap data-testid="minimap">
      <p className="text-meta text-muted-foreground px-0.5 pb-1">Lapas {page} — spustelėkite, kur rodyti</p>
      <div
        className="relative bg-white ring-1 ring-border cursor-pointer select-none"
        style={{ width: MINIMAP_W, height: Math.round(MINIMAP_W * aspect) }}
        onPointerDown={(e) => { if (e.button !== 0) return; draggingRef.current = true; e.currentTarget.setPointerCapture?.(e.pointerId); moveTo(e); }}
        onPointerMove={(e) => { if (draggingRef.current) moveTo(e); }}
        onPointerUp={() => { draggingRef.current = false; }}
        role="presentation"
      >
        <ThumbImg documentId={documentId} meta={{ pageIndex: page - 1 }} style={{ width: '100%', height: '100%', display: 'block', objectFit: 'fill' }} />
        {frame && (
          <span
            className="absolute border-2 border-viewer-chrome-active bg-viewer-chrome-active/10 pointer-events-none"
            style={{ left: `${frame[0] * 100}%`, top: `${frame[1] * 100}%`, width: `${(frame[2] - frame[0]) * 100}%`, height: `${(frame[3] - frame[1]) * 100}%` }}
            data-testid="minimap-frame"
          />
        )}
      </div>
    </div>
  );
}

export default function ZoomCluster({ documentId, pages = null, onAreaZoom = null, viewSettings = null }) {
  const { state: zoom, provides: zoomApi } = useZoom(documentId);
  const { state: scroll, provides: scrollApi } = useScroll(documentId);
  const anchorRef = useRef(null);
  const [areaArmed, setAreaArmed] = useState(false);
  const [minimapOpen, setMinimapOpen] = useState(() => {
    try { return localStorage.getItem('samatu_viewer_minimap') === '1'; } catch { return false; }
  });
  const [full, setFull] = useState(() => typeof document !== 'undefined' && !!document.fullscreenElement);
  useEffect(() => {
    const onChange = () => setFull(!!document.fullscreenElement);
    document.addEventListener('fullscreenchange', onChange);
    return () => document.removeEventListener('fullscreenchange', onChange);
  }, []);
  const pct = typeof zoom?.currentZoomLevel === 'number' ? Math.round(zoom.currentZoomLevel * 100) : 100;
  const cur = visiblePageOf(scroll);
  // Fit consults the plugin's currentPage, which can lag the viewport (audit P1) — sync it first.
  const fit = (mode) => {
    if (cur !== (scroll?.currentPage ?? cur)) scrollApi?.scrollToPage({ pageNumber: cur });
    zoomApi?.requestZoom(mode);
  };
  const toggleMinimap = () => setMinimapOpen((v) => {
    try { localStorage.setItem('samatu_viewer_minimap', v ? '0' : '1'); } catch { /* private mode */ }
    return !v;
  });
  // The whole app goes full screen, not the viewer alone: menus, toasts and dialogs render at the page's root
  // and would be hidden behind a full-screen viewer element.
  const toggleFull = () => {
    if (document.fullscreenElement) document.exitFullscreen?.().catch(() => {});
    else document.documentElement.requestFullscreen?.().catch(() => {});
  };
  const sep = <span aria-hidden="true" className="h-px w-6 bg-border my-0.5" />;
  return (
    <>
      {areaArmed && (
        <AreaZoomOverlay
          anchorRef={anchorRef}
          onDone={(target) => { setAreaArmed(false); onAreaZoom?.(target); }}
          onCancel={() => setAreaArmed(false)}
        />
      )}
      <div className="absolute bottom-2 right-2 flex items-end gap-2 pointer-events-none" ref={anchorRef} data-zoom-cluster-root>
        {minimapOpen && <Minimap documentId={documentId} anchorRef={anchorRef} pages={pages} />}
        <div
          className="pointer-events-auto rounded-panel border border-border bg-card shadow-md flex flex-col items-center gap-0.5 px-1 py-1"
          data-zoom-cluster
          role="group"
          aria-label="Mastelis ekrane"
        >
          <button type="button" className={btn} title={withKey('Artinti', 'zoomIn')} aria-label="Artinti" onClick={() => zoomApi?.zoomIn()} data-testid="zoom-in"><ZoomIn className="w-4 h-4" /></button>
          <span className="mono tabular text-meta text-foreground w-10 text-center" data-testid="zoom-level" aria-label={`Mastelis ekrane ${pct} %`}>{pct}%</span>
          <button type="button" className={btn} title={withKey('Tolinti', 'zoomOut')} aria-label="Tolinti" onClick={() => zoomApi?.zoomOut()} data-testid="zoom-out"><ZoomOut className="w-4 h-4" /></button>
          {sep}
          <button type="button" className={btn} title={withKey('Sutalpinti visą lapą', 'fitPage')} aria-label="Sutalpinti visą lapą" onClick={() => fit(ZoomMode.FitPage)} data-testid="zoom-fit-page"><Maximize2 className="w-4 h-4" /></button>
          <button type="button" className={btn} title={withKey('Sutalpinti per visą plotį', 'fitWidth')} aria-label="Sutalpinti per visą plotį" onClick={() => fit(ZoomMode.FitWidth)} data-testid="zoom-fit-width"><MoveHorizontal className="w-4 h-4" /></button>
          {sep}
          <button
            type="button"
            className={`${btn} ${areaArmed ? on : ''}`}
            title="Priartinti vietą — apveskite ją brėžinyje (Esc — atšaukti)"
            aria-label="Priartinti pasirinktą vietą"
            aria-pressed={areaArmed}
            disabled={!onAreaZoom}
            onClick={() => setAreaArmed((v) => !v)}
            data-testid="zoom-area"
          ><ScanSearch className="w-4 h-4" /></button>
          <button
            type="button"
            className={`${btn} ${minimapOpen ? on : ''}`}
            title={minimapOpen ? 'Slėpti lapo apžvalgą' : 'Lapo apžvalga — matosi, kurią lapo dalį rodo langas'}
            aria-label="Lapo apžvalga"
            aria-pressed={minimapOpen}
            onClick={toggleMinimap}
            data-testid="zoom-minimap"
          ><MapIcon className="w-4 h-4" /></button>
          <button
            type="button"
            className={`${btn} ${full ? on : ''}`}
            title={full ? 'Išeiti iš viso ekrano (Esc)' : 'Visas ekranas'}
            aria-label={full ? 'Išeiti iš viso ekrano' : 'Visas ekranas'}
            aria-pressed={full}
            onClick={toggleFull}
            data-testid="zoom-fullscreen"
          >{full ? <Minimize className="w-4 h-4" /> : <Maximize className="w-4 h-4" />}</button>
          {viewSettings && (<>{sep}{viewSettings}</>)}
        </div>
      </div>
    </>
  );
}
