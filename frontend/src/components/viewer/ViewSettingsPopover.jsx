/**
 * ViewSettingsPopover — „Rodinys": how the drawing is shown (Pathon v3 W5-B, B4; coverage #141, #142, #111, #140,
 * and B2's „Rodyti sritis"). A button at the foot of the zoom column opens a card to its left. Everything here
 * is VIEW ONLY — no number moves — and is remembered per browser (lib/viewSettings).
 *
 *   Brėžinys   ryškumas · išvalyti foną · nespalvotai (the drawing only; the marks keep their colours)
 *   Užrašai    patalpų pavadinimai · matavimų ilgiai ir plotai (the same switch is „PDF su žymėjimais" „Užrašai")
 *   Sritys     „Rodyti sritis" — plan, legends, tables, title block and notes outlined and named
 *   Žymeklis   a crosshair across the whole drawing
 *   Profesionalams (off) → the room outlines' fill and line width — the founder decides whether this stays
 *
 * Esc or a click outside closes the card (taken here while it is open, like the scale chip's card), so the
 * viewer's own Esc order never sees that press.
 *
 * Also here: `CleanBgFilter` (the SVG filter „Išvalyti foną" points at) and `ViewCrosshair`.
 */
import { useEffect, useRef, useState } from 'react';
import { toast } from 'sonner';
import { SlidersHorizontal, RotateCcw } from 'lucide-react';
import { Switch } from '@/components/ui/switch';
import { Slider } from '@/components/ui/slider';
import { CLEAN_FILTER_ID, VIEW_DEFAULTS, cleanSlope, viewChanged } from '@/lib/viewSettings';

const btnCls = 'h-8 w-8 inline-flex items-center justify-center rounded text-viewer-chrome-foreground hover:bg-viewer-chrome-hover focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring';

function Row({ label, hint = null, children, htmlFor }) {
  return (
    <div className="py-1.5">
      <div className="flex items-center justify-between gap-3">
        <label htmlFor={htmlFor} className="text-ui text-foreground">{label}</label>
        {children}
      </div>
      {hint && <p className="mt-0.5 text-meta text-muted-foreground leading-snug">{hint}</p>}
    </div>
  );
}

function SliderRow({ id, label, value, min, max, step, format, onChange }) {
  return (
    <div className="py-1.5">
      <div className="flex items-center justify-between gap-3">
        <span id={`${id}-label`} className="text-ui text-foreground">{label}</span>
        <span className="mono tabular text-ui text-muted-foreground">{format(value)}</span>
      </div>
      <Slider
        className="mt-2"
        aria-labelledby={`${id}-label`}
        value={[value]}
        min={min}
        max={max}
        step={step}
        onValueChange={([v]) => onChange(v)}
        data-testid={id}
      />
    </div>
  );
}

const Section = ({ title, children }) => (
  <section className="px-3 py-2 border-t border-border first:border-t-0">
    <h3 className="text-meta font-semibold uppercase tracking-wide text-muted-foreground">{title}</h3>
    {children}
  </section>
);

export default function ViewSettingsPopover({ settings, onChange }) {
  const [open, setOpen] = useState(false);
  const rootRef = useRef(null);
  useEffect(() => {
    if (!open) return undefined;
    const onKey = (e) => { if (e.key === 'Escape') { e.stopPropagation(); setOpen(false); } };
    const onDown = (e) => { if (!rootRef.current?.contains(e.target)) setOpen(false); };
    window.addEventListener('keydown', onKey, true);
    window.addEventListener('pointerdown', onDown, true);
    return () => { window.removeEventListener('keydown', onKey, true); window.removeEventListener('pointerdown', onDown, true); };
  }, [open]);
  const set = (patch) => onChange({ ...settings, ...patch });
  const pct = (v) => `${Math.round(v * 100)} %`;
  const changed = viewChanged(settings);
  const reset = () => {
    const before = settings;
    onChange({ ...VIEW_DEFAULTS });
    toast('Rodinys grąžintas į numatytąjį', { duration: 10_000, action: { label: 'Atšaukti', onClick: () => onChange(before) } });
  };
  return (
    <div className="relative" ref={rootRef}>
      <button
        type="button"
        className={`${btnCls} ${open || changed ? 'bg-viewer-chrome-active/15 text-viewer-chrome-active' : ''}`}
        title={changed ? 'Rodinys — pakeistas (brėžinio ryškumas, užrašai, sritys…)' : 'Rodinys — brėžinio ryškumas, užrašai, sritys, kryželis'}
        aria-label="Rodinys"
        aria-expanded={open}
        aria-haspopup="dialog"
        onClick={() => setOpen((v) => !v)}
        data-testid="view-settings-toggle"
      ><SlidersHorizontal className="w-4 h-4" /></button>
      {open && (
        <div
          role="dialog"
          aria-label="Rodinys"
          className="absolute bottom-0 right-full mr-2 w-80 max-h-[min(560px,calc(100vh-160px))] overflow-y-auto rounded-panel border border-border bg-card text-card-foreground shadow-lg"
          data-testid="view-settings"
        >
          <div className="px-3 pt-2.5 pb-2">
            <p className="text-ui font-semibold">Rodinys</p>
            <p className="mt-0.5 text-meta text-muted-foreground leading-snug">Keičia tik tai, kaip matote brėžinį — kiekiai nesikeičia.</p>
          </div>
          <Section title="Brėžinys">
            <SliderRow id="view-opacity" label="Brėžinio ryškumas" value={settings.opacity} min={0.2} max={1} step={0.05} format={pct} onChange={(v) => set({ opacity: v })} />
            <SliderRow id="view-clean" label="Išvalyti foną" value={settings.cleanBg} min={0} max={0.4} step={0.05}
              format={(v) => (v > 0 ? pct(v) : 'išjungta')} onChange={(v) => set({ cleanBg: v })} />
            <Row label="Nespalvotai" htmlFor="view-gray" hint="Brėžinys pilkas — jūsų žymės ir matavimai lieka spalvoti.">
              <Switch id="view-gray" checked={settings.gray} onCheckedChange={(v) => set({ gray: v })} data-testid="view-gray" />
            </Row>
          </Section>
          <Section title="Užrašai brėžinyje">
            <Row label="Patalpų pavadinimai" htmlFor="view-names">
              <Switch id="view-names" checked={settings.names} onCheckedChange={(v) => set({ names: v })} data-testid="view-names" />
            </Row>
            <Row label="Matavimų ilgiai ir plotai" htmlFor="view-dims" hint="Tas pats pasirinkimas — eksportuojant „PDF su žymėjimais“.">
              <Switch id="view-dims" checked={settings.dims} onCheckedChange={(v) => set({ dims: v })} data-testid="view-dims" />
            </Row>
          </Section>
          <Section title="Lapo sritys">
            <Row label="Rodyti sritis" htmlFor="view-zones" hint="Apvedami planas, legendos, lentelės, antspaudas ir pastabos. Užvedus pelę ant legendos ar lentelės jos pavadinimas rodomas ir išjungus.">
              <Switch id="view-zones" checked={settings.zones} onCheckedChange={(v) => set({ zones: v })} data-testid="view-zones" />
            </Row>
          </Section>
          <Section title="Žymeklis">
            <Row label="Kryželis per visą brėžinį" htmlFor="view-crosshair" hint="Padeda sulyginti tašką su sienomis ir ašimis.">
              <Switch id="view-crosshair" checked={settings.crosshair} onCheckedChange={(v) => set({ crosshair: v })} data-testid="view-crosshair" />
            </Row>
          </Section>
          <Section title="Profesionalams">
            <Row label="Kontūrų išvaizda" htmlFor="view-pro" hint="Patalpų kontūrų užpildas ir linijos storis.">
              <Switch id="view-pro" checked={settings.pro} onCheckedChange={(v) => set({ pro: v })} data-testid="view-pro" />
            </Row>
            {settings.pro && (
              <>
                <SliderRow id="view-poly" label="Kontūrų užpildas" value={settings.polyOpacity} min={0} max={0.6} step={0.02} format={pct} onChange={(v) => set({ polyOpacity: v })} />
                <SliderRow id="view-line" label="Linijos storis" value={settings.lineWidth} min={1} max={6} step={0.5} format={(v) => `${v} px`} onChange={(v) => set({ lineWidth: v })} />
              </>
            )}
          </Section>
          <div className="px-3 py-2 border-t border-border">
            <button
              type="button"
              disabled={!changed && !settings.pro}
              onClick={reset}
              className="inline-flex items-center gap-1.5 text-ui text-primary hover:underline disabled:opacity-40 disabled:no-underline"
              data-testid="view-reset"
            ><RotateCcw className="w-4 h-4" />Grąžinti numatytąjį rodinį</button>
          </div>
        </div>
      )}
    </div>
  );
}

/** The SVG filter „Išvalyti foną" uses: greys lighter than 1 − t become white, darker ones lighten in step. */
export function CleanBgFilter({ t }) {
  const slope = cleanSlope(t);
  return (
    <svg width="0" height="0" aria-hidden="true" style={{ position: 'absolute' }}>
      <filter id={CLEAN_FILTER_ID} colorInterpolationFilters="sRGB">
        <feComponentTransfer>
          <feFuncR type="linear" slope={slope} intercept={0} />
          <feFuncG type="linear" slope={slope} intercept={0} />
          <feFuncB type="linear" slope={slope} intercept={0} />
        </feComponentTransfer>
      </filter>
    </svg>
  );
}

/** A crosshair across the whole drawing at the pointer — two hairlines, pointer-transparent. */
export function ViewCrosshair({ rootRef, enabled }) {
  const [at, setAt] = useState(null);
  useEffect(() => {
    const canvas = rootRef?.current?.querySelector('[data-testid="viewer-canvas"]');
    if (!enabled || !canvas) { setAt(null); return undefined; }
    let raf = 0;
    let last = null;
    const paint = () => {
      raf = 0;
      if (!last) { setAt(null); return; }
      const r = canvas.getBoundingClientRect();
      setAt({ x: last.x, y: last.y, top: r.top, left: r.left, w: r.width, h: r.height });
    };
    const move = (e) => { last = { x: e.clientX, y: e.clientY }; if (!raf) raf = requestAnimationFrame(paint); };
    const leave = () => { last = null; if (!raf) raf = requestAnimationFrame(paint); };
    canvas.addEventListener('pointermove', move, { passive: true });
    canvas.addEventListener('pointerleave', leave, { passive: true });
    return () => { canvas.removeEventListener('pointermove', move); canvas.removeEventListener('pointerleave', leave); if (raf) cancelAnimationFrame(raf); };
  }, [rootRef, enabled]);
  if (!enabled || !at) return null;
  // fixed, in client px: the lines span the canvas wherever the viewer sits on the page
  const line = 'fixed pointer-events-none z-panel bg-ov-selected/55';
  return (
    <div className="pointer-events-none" data-testid="view-crosshair-lines" aria-hidden="true">
      <span className={line} style={{ left: at.left, width: at.w, top: at.y, height: 1 }} />
      <span className={line} style={{ top: at.top, height: at.h, left: at.x, width: 1 }} />
    </div>
  );
}
