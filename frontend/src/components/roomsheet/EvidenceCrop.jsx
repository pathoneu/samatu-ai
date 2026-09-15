/**
 * EvidenceCrop — the actual pixels the reader looked at.
 *
 * One image, lazily loaded, with a caption that is honest about what it is:
 * a framed rectangle when the backend measured one on that page, and „visas
 * lapas" when it did not. That distinction is a contract rule, not a nicety —
 * a whole-sheet crop dressed up as a pinpoint tells the contractor to look
 * somewhere the data never pointed (docs/ARCHITECTURE.md § Room facts).
 *
 * 2026-09-07 (founder: „nieko nesimato, negaliu nei pamatyti nei prisiartinti",
 * then „įsijungus turi būti visas lapas, o priartina žmogus pats"): every crop
 * is a button. A click opens the WHOLE sheet fitted to the screen with the
 * evidence rectangle outlined on it; „+" / „−", a click on the drawing or
 * Ctrl + wheel (trackpad pinch) zoom in, „Sutalpinti" fits the sheet again.
 * The endpoint caps every crop at 1600 px, so once the zoom settles the viewer
 * asks it for the region that is on screen and lays that sharp crop over the
 * fitted sheet (arithmetic in lib/sheetZoom.js).
 */

import { useCallback, useEffect, useLayoutEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Maximize2, Minus, Plus } from 'lucide-react';
import { Dialog, DialogContent, DialogDescription, DialogTitle } from '@/components/ui/dialog';
import { evidenceUrl } from '@/lib/roomSheetApi';
import {
  ZOOM_MAX, ZOOM_MIN, ZOOM_STEP, clampZoom, fullSheetUrl, paddedRect, rectCentre, rectKey,
  visibleRect, withRect, zoomForRect,
} from '@/lib/sheetZoom';

const SETTLE_MS = 220;
// Ask for a little more than what is on screen so a small pan needs no refetch.
const TILE_MARGIN = 0.1;

function toolBtn(label, onClick, disabled, icon, extra = '') {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={`inline-flex min-h-[36px] items-center gap-1 rounded-[2px] border border-border bg-card px-3 text-[14px] font-semibold hover:bg-muted disabled:cursor-not-allowed disabled:opacity-40 ${extra}`}
    >
      {icon}{label}
    </button>
  );
}

/**
 * The whole sheet in a fixed-height scroll box. `zoom` is relative to the
 * fitted size: 1 = the sheet fits, 8 = eight times wider than fitted.
 */
export function SheetViewer({ cropUrl, alt, rect }) {
  const { t } = useTranslation();
  const boxRef = useRef(null);
  const imgRef = useRef(null);
  const natural = useRef(null);     // the base image's own pixel size
  const fitted = useRef(null);      // image size at zoom 1: natural scaled into the box
  const focus = useRef(null);       // {x, y, px, py}: keep image point (x,y) under box pixel (px,py)
  const settle = useRef(null);      // debounce for the sharp overlay
  const zoomRef = useRef(ZOOM_MIN);
  const [zoom, setZoom] = useState(ZOOM_MIN);
  const [ready, setReady] = useState(false);
  const [fittedSize, setFittedSize] = useState(null);
  const [failed, setFailed] = useState(false);
  const [tiles, setTiles] = useState([]); // sharp overlays, newest last
  zoomRef.current = zoom;

  const base = evidenceUrl(fullSheetUrl(cropUrl));

  const zoomTo = useCallback((next, at) => {
    const z = clampZoom(next);
    focus.current = z > ZOOM_MIN ? at || null : null;
    setZoom(z);
  }, []);

  /** Image fraction at the middle of the box — what „+" without a point keeps still. */
  const viewCentre = () => {
    const box = boxRef.current;
    const img = imgRef.current;
    const v = box && img && visibleRect(box.getBoundingClientRect(), img.getBoundingClientRect());
    return v ? rectCentre(v) : { x: 0.5, y: 0.5 };
  };

  const pointAt = (clientX, clientY) => {
    const b = boxRef.current.getBoundingClientRect();
    const r = imgRef.current.getBoundingClientRect();
    return {
      x: (clientX - r.left) / r.width, y: (clientY - r.top) / r.height,
      px: clientX - b.left, py: clientY - b.top,
    };
  };

  /** Fetch a sharp crop of what is on screen once scrolling / zooming stops. */
  const scheduleSharpen = useCallback(() => {
    if (settle.current) clearTimeout(settle.current);
    settle.current = setTimeout(() => {
      settle.current = null;
      const box = boxRef.current;
      const img = imgRef.current;
      if (!box || !img || zoomRef.current <= ZOOM_MIN) { setTiles([]); return; }
      // The fitted sheet is already sharp while it is shown at or below its own pixels.
      if (img.naturalWidth >= img.clientWidth) { setTiles([]); return; }
      const v = visibleRect(box.getBoundingClientRect(), img.getBoundingClientRect());
      if (!v) { setTiles([]); return; }
      const mw = (v[2] - v[0]) * TILE_MARGIN;
      const mh = (v[3] - v[1]) * TILE_MARGIN;
      const want = [Math.max(0, v[0] - mw), Math.max(0, v[1] - mh), Math.min(1, v[2] + mw), Math.min(1, v[3] + mh)];
      const z = zoomRef.current;
      setTiles((prev) => {
        const last = prev[prev.length - 1];
        const covered = last && last.zoom === z
          && last.rect[0] <= v[0] && last.rect[1] <= v[1] && last.rect[2] >= v[2] && last.rect[3] >= v[3];
        if (covered) return prev;
        const key = `${rectKey(want)}@${z}`;
        if (last && last.key === key) return prev;
        return [...prev.slice(-1), { key, zoom: z, url: evidenceUrl(withRect(cropUrl, want)), rect: paddedRect(want) }];
      });
    }, SETTLE_MS);
  }, [cropUrl]);

  // After a zoom change: keep the focused point where it was, then sharpen.
  useLayoutEffect(() => {
    const box = boxRef.current;
    const img = imgRef.current;
    const f = focus.current;
    if (box && img && f) {
      const b = box.getBoundingClientRect();
      const r = img.getBoundingClientRect();
      const left = r.left - b.left + box.scrollLeft;
      const top = r.top - b.top + box.scrollTop;
      const px = f.px ?? box.clientWidth / 2;
      const py = f.py ?? box.clientHeight / 2;
      box.scrollLeft = left + f.x * r.width - px;
      box.scrollTop = top + f.y * r.height - py;
    }
    scheduleSharpen();
  }, [zoom, scheduleSharpen]);

  // Ctrl/⌘ + wheel and trackpad pinch (which arrives as a ctrl-wheel) zoom at
  // the pointer. React registers wheel listeners passively, so this one is native.
  useEffect(() => {
    const box = boxRef.current;
    if (!box) return undefined;
    const onWheel = (e) => {
      if (!(e.ctrlKey || e.metaKey) || !imgRef.current || !fitted.current) return;
      e.preventDefault();
      zoomTo(zoomRef.current * Math.exp(-e.deltaY * 0.01), pointAt(e.clientX, e.clientY));
    };
    box.addEventListener('wheel', onWheel, { passive: false });
    return () => {
      box.removeEventListener('wheel', onWheel);
      if (settle.current) clearTimeout(settle.current);
    };
  }, [zoomTo]);

  // The fitted size is computed, not left to CSS: a percentage max-height
  // inside the auto-height wrapper resolves to nothing, and the sheet would
  // open at its own 1600 px (exactly the „prizoomintas" he complained about).
  const measure = useCallback(() => {
    const box = boxRef.current;
    const nat = natural.current;
    if (!box || !nat || !box.clientWidth || !box.clientHeight) return;
    const s = Math.min(box.clientWidth / nat.width, box.clientHeight / nat.height);
    const f = { width: Math.max(1, Math.floor(nat.width * s)), height: Math.max(1, Math.floor(nat.height * s)) };
    fitted.current = f;
    setFittedSize(f);
    setReady(true);
  }, []);

  const onBaseLoad = (e) => {
    const img = e.currentTarget;
    natural.current = { width: img.naturalWidth, height: img.naturalHeight };
    measure();
  };

  // Re-fit when the dialog (window) changes size.
  useEffect(() => {
    const box = boxRef.current;
    if (!box || typeof ResizeObserver === 'undefined') return undefined;
    const ro = new ResizeObserver(() => measure());
    ro.observe(box);
    return () => ro.disconnect();
  }, [measure]);

  const stepIn = () => zoomTo(zoom * ZOOM_STEP, { ...viewCentre() });
  const stepOut = () => zoomTo(zoom / ZOOM_STEP, { ...viewCentre() });
  const fit = () => zoomTo(ZOOM_MIN);
  const toSpot = () => {
    const box = boxRef.current;
    if (!box || !rect || !fitted.current) return;
    const z = zoomForRect(rect, { width: box.clientWidth, height: box.clientHeight }, fitted.current);
    zoomTo(z, z > ZOOM_MIN ? { ...rectCentre(rect) } : null);
  };
  const onImageClick = (e) => {
    if (!fitted.current) return;
    if (zoom >= ZOOM_MAX) { fit(); return; }
    zoomTo(zoom * ZOOM_STEP, pointAt(e.clientX, e.clientY));
  };

  const imgStyle = fittedSize
    ? { width: `${Math.round(fittedSize.width * zoom)}px`, height: 'auto', maxWidth: 'none' }
    : { width: '1px', height: '1px', visibility: 'hidden' };
  const factor = zoom.toFixed(1).replace('.', ',');

  return (
    <div className="min-w-0">
      <div className="mb-2 flex flex-wrap items-center gap-2" role="group" aria-label={t('project.roomSheet.cropZoom')}>
        {toolBtn(t('project.roomSheet.cropZoomOut'), stepOut, !ready || zoom <= ZOOM_MIN, <Minus className="h-4 w-4" />)}
        {toolBtn(t('project.roomSheet.cropZoomIn'), stepIn, !ready || zoom >= ZOOM_MAX, <Plus className="h-4 w-4" />)}
        {toolBtn(t('project.roomSheet.cropFit'), fit, !ready || zoom <= ZOOM_MIN, null)}
        {rect && toolBtn(t('project.roomSheet.cropToSpot'), toSpot, !ready, null)}
        <span className="ml-auto font-mono text-[13px] text-muted-foreground" data-testid="sheet-zoom">
          {t('project.roomSheet.cropZoomLevel', { factor })}
        </span>
      </div>
      <div
        ref={boxRef}
        onScroll={scheduleSharpen}
        className="relative h-[72vh] overflow-auto rounded-[2px] border border-border bg-muted leading-none"
        data-testid="sheet-viewer"
      >
        <div className="inline-grid min-h-full min-w-full place-items-center align-top">
          <span className="relative inline-block">
            {!failed && (
              <img
                ref={imgRef}
                src={base}
                alt={alt || ''}
                decoding="async"
                draggable={false}
                onLoad={onBaseLoad}
                onError={() => setFailed(true)}
                onClick={onImageClick}
                title={zoom >= ZOOM_MAX ? t('project.roomSheet.cropFit') : t('project.roomSheet.cropZoomIn')}
                style={{ ...imgStyle, display: 'block', background: '#fff', cursor: zoom >= ZOOM_MAX ? 'zoom-out' : 'zoom-in' }}
              />
            )}
            {tiles.map((tile) => (
              <img
                key={tile.key}
                src={tile.url}
                alt=""
                aria-hidden="true"
                decoding="async"
                draggable={false}
                onLoad={() => setTiles((prev) => {
                  const i = prev.findIndex((p) => p.key === tile.key);
                  return i <= 0 ? prev : prev.slice(i);
                })}
                onError={() => setTiles((prev) => prev.filter((p) => p.key !== tile.key))}
                className="pointer-events-none absolute"
                style={{
                  left: `${tile.rect[0] * 100}%`, top: `${tile.rect[1] * 100}%`,
                  width: `${(tile.rect[2] - tile.rect[0]) * 100}%`, height: `${(tile.rect[3] - tile.rect[1]) * 100}%`,
                }}
              />
            ))}
            {ready && Array.isArray(rect) && rect.length === 4 && (
              <span
                aria-hidden="true"
                data-testid="sheet-outline"
                className="pointer-events-none absolute rounded-[2px] border-2 border-[hsl(var(--accent-2))]"
                style={{
                  left: `${rect[0] * 100}%`, top: `${rect[1] * 100}%`,
                  width: `${(rect[2] - rect[0]) * 100}%`, height: `${(rect[3] - rect[1]) * 100}%`,
                  boxShadow: '0 0 0 2px rgba(255,255,255,0.75)',
                }}
              />
            )}
          </span>
        </div>
        {!ready && !failed && (
          <p className="absolute inset-x-0 top-1/2 -translate-y-1/2 text-center text-[13px] text-muted-foreground">
            {t('project.roomSheet.cropLoading')}
          </p>
        )}
        {failed && (
          <p className="absolute inset-x-0 top-1/2 -translate-y-1/2 text-center text-[13px] text-muted-foreground">
            {t('project.roomSheet.cropFailed')}
          </p>
        )}
      </div>
    </div>
  );
}

export default function EvidenceCrop({
  fact, alt, className = '', imgClassName = '', showCaption = true, enlargeable = true,
}) {
  const { t } = useTranslation();
  const [failed, setFailed] = useState(false);
  const [loaded, setLoaded] = useState(false);
  const [open, setOpen] = useState(false);

  const src = evidenceUrl(fact?.crop_url);
  const page = fact?.source?.page;
  const rect = Array.isArray(fact?.source?.rect_pct) && fact.source.rect_pct.length === 4 ? fact.source.rect_pct : null;
  const whole = !rect;

  if (!src) return null;

  const caption = [
    page != null ? t('project.roomSheet.sourcePage', { page }) : null,
    whole ? t('project.roomSheet.wholeSheet') : null,
  ].filter(Boolean).join(' · ');

  const image = failed ? (
    <p className="p-2 text-[13px] leading-snug text-muted-foreground">
      {t('project.roomSheet.cropFailed')}
    </p>
  ) : (
    <img
      src={src}
      alt={alt || ''}
      loading="lazy"
      decoding="async"
      onLoad={() => setLoaded(true)}
      onError={() => setFailed(true)}
      // A whole-sheet crop cropped again to a thumbnail shows nothing but
      // the sheet's white margin; `contain` at least renders as a page.
      className={`block w-full ${whole ? 'h-[68px] object-contain' : imgClassName}`}
    />
  );

  return (
    <figure className={`m-0 ${className}`}>
      {enlargeable && !failed ? (
        <button
          type="button"
          onClick={() => setOpen(true)}
          aria-label={t('project.roomSheet.cropEnlarge', { page: page ?? '' })}
          title={t('project.roomSheet.cropEnlarge', { page: page ?? '' })}
          className="group relative block w-full overflow-hidden rounded-[2px] border border-border bg-card text-left hover:border-[hsl(var(--accent-2))] focus:outline-none focus-visible:ring-2 focus-visible:ring-[hsl(var(--accent-2))]"
        >
          {!loaded && (
            <div className="absolute inset-0 animate-pulse bg-muted" aria-hidden="true" />
          )}
          {image}
          <span
            aria-hidden="true"
            className="absolute bottom-1 right-1 inline-flex h-6 w-6 items-center justify-center rounded-[2px] border border-border bg-card/90 text-[hsl(var(--ink-2))] opacity-80 group-hover:opacity-100"
          >
            <Maximize2 className="h-3.5 w-3.5" />
          </span>
        </button>
      ) : (
        <div className="relative overflow-hidden rounded-[2px] border border-border bg-card">
          {!loaded && !failed && (
            <div className="absolute inset-0 animate-pulse bg-muted" aria-hidden="true" />
          )}
          {image}
        </div>
      )}
      {showCaption && (
        <figcaption className="mt-1 font-mono text-[12px] leading-tight text-muted-foreground">
          {caption}
        </figcaption>
      )}
      {enlargeable && (
        <Dialog open={open} onOpenChange={setOpen}>
          <DialogContent className="max-h-[96vh] w-[min(96vw,1500px)] max-w-none gap-2 overflow-hidden p-4">
            <div className="min-w-0 pr-8">
              <DialogTitle className="text-[16px] font-semibold">{alt || t('project.roomSheet.cropTitle')}</DialogTitle>
              <DialogDescription className="font-mono text-[13px] text-muted-foreground">
                {[
                  page != null ? t('project.roomSheet.sourcePage', { page }) : null,
                  rect ? t('project.roomSheet.cropOutlined') : t('project.roomSheet.wholeSheet'),
                ].filter(Boolean).join(' · ')}
              </DialogDescription>
            </div>
            {open && <SheetViewer cropUrl={fact.crop_url} alt={alt} rect={rect} />}
            <p className="text-[13px] text-muted-foreground">{t('project.roomSheet.cropHint')}</p>
          </DialogContent>
        </Dialog>
      )}
    </figure>
  );
}
