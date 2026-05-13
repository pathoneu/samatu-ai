/**
 * Sąmatų AI — public landing page (v3, drafting-anchored aesthetic).
 *
 * Shown at "/" for unauthenticated visitors. Authenticated users get
 * redirected to /dashboard via the wrapper in App.jsx.
 *
 * Design language: LT architectural firm + technical specification.
 * Single owned blue, paper background, hairline borders, square corners,
 * JetBrains Mono for numbers, system sans for body, one editorial serif
 * moment (manifesto pull quote).
 */
import React, { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';

// ─── Hooks ───────────────────────────────────────────────────────────

function useInView(opts = {}) {
  const ref = useRef(null);
  const [inView, setInView] = useState(false);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const io = new IntersectionObserver(
      ([entry]) => {
        if (entry.isIntersecting) {
          setInView(true);
          io.unobserve(el);
        }
      },
      { rootMargin: opts.rootMargin || '-10% 0px -10% 0px', threshold: opts.threshold ?? 0.2 }
    );
    io.observe(el);
    return () => io.disconnect();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  return [ref, inView];
}

// ─── Pinned example datasets ────────────────────────────────────────

const EXAMPLES = {
  A: {
    id: 'A', label: '42 m² · 2 kamb.',
    sheet: 'SA-A1', scale: 'M 1:50', desc: '2-kamb butas',
    rooms: [
      { k: 'Svetainė + virtuvė', p: 18.4, perim: 17.4, h: 2.55 },
      { k: 'Miegamasis',         p: 12.8, perim: 14.4, h: 2.55 },
      { k: 'Vonia',              p:  4.2, perim:  8.4, h: 2.55 },
      { k: 'Koridorius',         p:  6.6, perim: 11.4, h: 2.55 },
    ],
    totals: { plotas: 42.0, perim: 51.6, sienos: 131.6 },
    pricing: [
      { l: 'Sienų lyginimas Q2',           q: 131.6, u: 'm²', def: 11.00 },
      { l: 'Sienų glaistymas + dažymas',   q: 131.6, u: 'm²', def: 14.00 },
      { l: 'Lubų glaistymas + dažymas',    q:  42.0, u: 'm²', def: 13.00 },
      { l: 'Grindjuostės (su montavimu)',  q:  46,   u: 'm',  def:  5.00 },
    ],
  },
  B: {
    id: 'B', label: '72 m² · 3 kamb.',
    sheet: 'SA-B1', scale: 'M 1:50', desc: '3-kamb butas',
    rooms: [
      { k: 'Svetainė + virtuvė', p: 28.4, perim: 22.1, h: 2.65 },
      { k: 'Miegamasis',         p: 14.2, perim: 15.3, h: 2.65 },
      { k: 'Vaiko kambarys',     p: 11.8, perim: 13.8, h: 2.65 },
      { k: 'Vonia',              p:  4.6, perim:  8.8, h: 2.65 },
      { k: 'WC',                 p:  2.1, perim:  5.9, h: 2.65 },
      { k: 'Koridorius',         p: 10.9, perim: 14.4, h: 2.65 },
    ],
    totals: { plotas: 72.0, perim: 80.3, sienos: 213.0 },
    pricing: [
      { l: 'Sienų lyginimas Q2',           q: 213.0, u: 'm²', def: 11.00 },
      { l: 'Sienų glaistymas + dažymas',   q: 213.0, u: 'm²', def: 14.00 },
      { l: 'Lubų glaistymas + dažymas',    q:  72.0, u: 'm²', def: 13.00 },
      { l: 'Grindjuostės (su montavimu)',  q:  73,   u: 'm',  def:  5.00 },
    ],
  },
  C: {
    id: 'C', label: '110 m² · 4 kamb.',
    sheet: 'SA-C1', scale: 'M 1:50', desc: '4-kamb butas',
    rooms: [
      { k: 'Svetainė + virtuvė', p: 38.2, perim: 26.4, h: 2.75 },
      { k: 'Miegamasis',         p: 16.4, perim: 16.2, h: 2.75 },
      { k: 'Vaiko kambarys',     p: 13.8, perim: 15.0, h: 2.75 },
      { k: 'Kabinetas',          p: 10.2, perim: 12.8, h: 2.75 },
      { k: 'Vonia',              p:  6.8, perim: 10.4, h: 2.75 },
      { k: 'WC',                 p:  2.4, perim:  6.2, h: 2.75 },
      { k: 'Koridorius',         p: 14.4, perim: 16.8, h: 2.75 },
      { k: 'Sandėliukas',        p:  7.8, perim: 11.2, h: 2.75 },
    ],
    totals: { plotas: 110.0, perim: 115.0, sienos: 316.3 },
    pricing: [
      { l: 'Sienų lyginimas Q2',           q: 316.3, u: 'm²', def: 11.00 },
      { l: 'Sienų glaistymas + dažymas',   q: 316.3, u: 'm²', def: 14.00 },
      { l: 'Lubų glaistymas + dažymas',    q: 110.0, u: 'm²', def: 13.00 },
      { l: 'Grindjuostės (su montavimu)',  q: 104,   u: 'm',  def:  5.00 },
    ],
  },
};

// ─── Number formatting (LT convention: comma decimals) ──────────────

const fmt = (n, d = 1) =>
  n.toLocaleString('lt-LT', { minimumFractionDigits: d, maximumFractionDigits: d });
const fmt0 = (n) => Math.round(n).toLocaleString('lt-LT');
const fmt2 = (n) => n.toLocaleString('lt-LT', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

// ─── Tiny components ─────────────────────────────────────────────────

const Pill = ({ children }) => (
  <span className="h-pill">{children}</span>
);

const Eyebrow = ({ children }) => (
  <div className="font-mono text-[11px] tracking-[0.08em] uppercase text-muted-foreground">
    {children}
  </div>
);

const Marginalia = ({ children }) => (
  <aside className="hidden lg:block lg:col-span-3 font-mono text-[11px] text-muted-foreground leading-relaxed pt-1">
    {children}
  </aside>
);

const NorthArrow = ({ size = 24, opacity = 1 }) => (
  <svg viewBox="0 0 24 24" width={size} height={size} fill="none"
    stroke="currentColor" strokeWidth="1.1" strokeLinecap="round"
    strokeLinejoin="round" style={{ opacity }}>
    <circle cx="12" cy="12" r="10.5" strokeOpacity="0.4" />
    <path d="M12 4 L8.5 17 L12 14 L15.5 17 Z" fill="currentColor" />
    <text x="12" y="3" textAnchor="middle" fontSize="3.4"
      fontFamily="JetBrains Mono, monospace" fill="currentColor">Š</text>
  </svg>
);

const ScaleBar = ({ width = 130 }) => {
  const ticks = [0, 1, 2, 5, 10];
  const max = 10;
  return (
    <svg viewBox={`0 0 ${width} 24`} width={width} height={24}
      className="text-foreground">
      <line x1="2" y1="10" x2={width - 2} y2="10"
        stroke="currentColor" strokeWidth="1" />
      {ticks.map((t) => {
        const x = 2 + (t / max) * (width - 4);
        const major = t === 0 || t === max;
        return (
          <g key={t}>
            <line x1={x} y1={major ? 5 : 7} x2={x} y2={major ? 15 : 13}
              stroke="currentColor" strokeWidth="1" />
            <text x={x} y="23" textAnchor="middle" fontSize="9"
              fontFamily="JetBrains Mono, monospace"
              className="fill-muted-foreground">
              {t === max ? '10 m' : t}
            </text>
          </g>
        );
      })}
    </svg>
  );
};

// ─── Floor plan SVG (drafting-style with reveal animation) ──────────

function FloorPlanSVG() {
  const [ref, inView] = useInView({ threshold: 0.15 });
  return (
    <svg
      ref={ref}
      viewBox="0 0 620 460"
      className={`hero-plan w-full h-auto ${inView ? 'in' : ''}`}
      role="img"
      aria-labelledby="hero-plan-title"
    >
      <title id="hero-plan-title">
        Pavyzdinis aukšto planas: 3-kambarių butas, 72 m²
      </title>

      {/* Sheet border */}
      <rect className="sheet-border" x="1" y="1" width="618" height="458"
        fill="hsl(var(--card))" stroke="hsl(var(--foreground))"
        strokeWidth="1" />

      {/* Drawing area inset */}
      <g transform="translate(40, 30)">

        {/* Outer walls */}
        <path className="wall" d="M0,0 L0,310 L500,310 L500,0 L0,0"
          fill="none" stroke="hsl(var(--foreground))" strokeWidth="1.8" />

        {/* Horizontal partition between rows */}
        <line className="wall" x1="0" y1="180" x2="500" y2="180"
          stroke="hsl(var(--foreground))" strokeWidth="1.6" />

        {/* Vertical partitions top row */}
        <line className="wall" x1="180" y1="0" x2="180" y2="180"
          stroke="hsl(var(--foreground))" strokeWidth="1.6" />
        <line className="wall" x1="320" y1="0" x2="320" y2="180"
          stroke="hsl(var(--foreground))" strokeWidth="1.6" />

        {/* Vertical partitions bottom row */}
        <line className="wall" x1="240" y1="180" x2="240" y2="310"
          stroke="hsl(var(--foreground))" strokeWidth="1.6" />
        <line className="wall" x1="380" y1="180" x2="380" y2="310"
          stroke="hsl(var(--foreground))" strokeWidth="1.6" />

        {/* Door arcs (90° arcs at openings) */}
        <path className="opening" d="M90 180 a18 18 0 0 1 18 -18"
          fill="none" stroke="hsl(var(--foreground))" strokeWidth="0.8" />
        <path className="opening" d="M260 180 a18 18 0 0 0 -18 -18"
          fill="none" stroke="hsl(var(--foreground))" strokeWidth="0.8" />
        <path className="opening" d="M410 180 a16 16 0 0 1 16 -16"
          fill="none" stroke="hsl(var(--foreground))" strokeWidth="0.8" />
        <path className="opening" d="M210 310 a16 16 0 0 0 16 -16"
          fill="none" stroke="hsl(var(--foreground))" strokeWidth="0.6" />

        {/* Windows (parallel lines on outer walls) */}
        <line className="opening" x1="60"  y1="0" x2="120" y2="0"
          stroke="hsl(var(--foreground))" strokeWidth="3" />
        <line className="opening" x1="60"  y1="1.5" x2="120" y2="1.5"
          stroke="hsl(var(--card))" strokeWidth="1" />
        <line className="opening" x1="220" y1="0" x2="290" y2="0"
          stroke="hsl(var(--foreground))" strokeWidth="3" />
        <line className="opening" x1="220" y1="1.5" x2="290" y2="1.5"
          stroke="hsl(var(--card))" strokeWidth="1" />
        <line className="opening" x1="380" y1="0" x2="450" y2="0"
          stroke="hsl(var(--foreground))" strokeWidth="3" />
        <line className="opening" x1="380" y1="1.5" x2="450" y2="1.5"
          stroke="hsl(var(--card))" strokeWidth="1" />

        {/* Room labels — JetBrains Mono */}
        <g fontFamily="JetBrains Mono, monospace">
          <g className="room-label room-1">
            <text x="90"  y="85" textAnchor="middle" fontSize="9.5"
              fill="hsl(var(--foreground))">SVETAINĖ +</text>
            <text x="90"  y="97" textAnchor="middle" fontSize="9.5"
              fill="hsl(var(--foreground))">VIRTUVĖ</text>
            <text x="90"  y="115" textAnchor="middle" fontSize="8.5"
              fill="hsl(var(--muted-foreground))">28,4 m²</text>
          </g>
          <g className="room-label room-2">
            <text x="250" y="85" textAnchor="middle" fontSize="9.5"
              fill="hsl(var(--foreground))">MIEGAMASIS</text>
            <text x="250" y="103" textAnchor="middle" fontSize="8.5"
              fill="hsl(var(--muted-foreground))">14,2 m²</text>
          </g>
          <g className="room-label room-3">
            <text x="410" y="85" textAnchor="middle" fontSize="9.5"
              fill="hsl(var(--foreground))">VAIKO K.</text>
            <text x="410" y="103" textAnchor="middle" fontSize="8.5"
              fill="hsl(var(--muted-foreground))">11,8 m²</text>
          </g>
          <g className="room-label room-4">
            <text x="120" y="240" textAnchor="middle" fontSize="9.5"
              fill="hsl(var(--foreground))">KORIDORIUS</text>
            <text x="120" y="258" textAnchor="middle" fontSize="8.5"
              fill="hsl(var(--muted-foreground))">10,9 m²</text>
          </g>
          <g className="room-label room-5">
            <text x="310" y="240" textAnchor="middle" fontSize="9.5"
              fill="hsl(var(--foreground))">VONIA</text>
            <text x="310" y="258" textAnchor="middle" fontSize="8.5"
              fill="hsl(var(--muted-foreground))">4,6 m²</text>
          </g>
          <g className="room-label room-6">
            <text x="440" y="240" textAnchor="middle" fontSize="9.5"
              fill="hsl(var(--foreground))">WC</text>
            <text x="440" y="258" textAnchor="middle" fontSize="8.5"
              fill="hsl(var(--muted-foreground))">2,1 m²</text>
          </g>
        </g>
      </g>

      {/* North arrow — top right */}
      <g className="meta-element" transform="translate(580, 36)"
         color="hsl(var(--foreground))">
        <NorthArrow size={28} />
      </g>

      {/* Scale bar — bottom left */}
      <g className="meta-element" transform="translate(40, 400)">
        <line x1="0" y1="0" x2="130" y2="0"
          stroke="hsl(var(--foreground))" strokeWidth="1" />
        <line x1="0"   y1="-4" x2="0"   y2="4" stroke="hsl(var(--foreground))" strokeWidth="1" />
        <line x1="32"  y1="-3" x2="32"  y2="3" stroke="hsl(var(--foreground))" strokeWidth="1" />
        <line x1="64"  y1="-3" x2="64"  y2="3" stroke="hsl(var(--foreground))" strokeWidth="1" />
        <line x1="97"  y1="-3" x2="97"  y2="3" stroke="hsl(var(--foreground))" strokeWidth="1" />
        <line x1="130" y1="-4" x2="130" y2="4" stroke="hsl(var(--foreground))" strokeWidth="1" />
        <g fontFamily="JetBrains Mono, monospace" fontSize="9"
           fill="hsl(var(--muted-foreground))">
          <text x="0"   y="16" textAnchor="middle">0</text>
          <text x="32"  y="16" textAnchor="middle">1</text>
          <text x="64"  y="16" textAnchor="middle">2</text>
          <text x="97"  y="16" textAnchor="middle">5</text>
          <text x="130" y="16" textAnchor="middle">10 m</text>
        </g>
      </g>

      {/* Title block — bottom right */}
      <g className="meta-element" transform="translate(400, 380)">
        <rect x="0" y="0" width="190" height="58" fill="none"
          stroke="hsl(var(--foreground))" strokeWidth="0.8" />
        <line x1="0" y1="20" x2="190" y2="20"
          stroke="hsl(var(--foreground))" strokeWidth="0.6" />
        <line x1="65" y1="0" x2="65" y2="58"
          stroke="hsl(var(--foreground))" strokeWidth="0.6" />
        <g fontFamily="JetBrains Mono, monospace" fontSize="8">
          <text x="6"  y="14" fill="hsl(var(--foreground))">SĄMATŲ AI</text>
          <text x="71" y="14" fill="hsl(var(--foreground))">Pavyzdys</text>
          <text x="6"  y="34" fill="hsl(var(--muted-foreground))">M 1:50</text>
          <text x="71" y="34" fill="hsl(var(--muted-foreground))">3-kamb butas</text>
          <text x="6"  y="50" fill="hsl(var(--muted-foreground))">SA-01</text>
          <text x="71" y="50" fill="hsl(var(--muted-foreground))">72,0 m²</text>
        </g>
      </g>
    </svg>
  );
}

// ─── Dimension chain (honest extracted quantities) ──────────────────

function DimensionChain() {
  const items = [
    { v: '72', u: 'm² grindys' },
    { v: '213', u: 'm² sienos' },
    { v: '73', u: 'm grindjuosčių' },
  ];
  return (
    <div className="flex flex-wrap items-center gap-x-8 gap-y-3 mt-8 mb-2">
      {items.map((it, i) => (
        <div key={i} className="flex items-center gap-2">
          <svg width="50" height="14" viewBox="0 0 50 14"
            className="text-foreground/60">
            <path d="M2 7 L48 7" stroke="currentColor" strokeWidth="1"
              strokeDasharray="2 2" />
            <path d="M2 4 L0 7 L2 10 Z" fill="currentColor" />
            <path d="M48 4 L50 7 L48 10 Z" fill="currentColor" />
          </svg>
          <span className="font-mono text-[14px] tabular text-foreground font-medium">
            {it.v} <span className="text-muted-foreground">{it.u}</span>
          </span>
          <svg width="50" height="14" viewBox="0 0 50 14"
            className="text-foreground/60">
            <path d="M2 7 L48 7" stroke="currentColor" strokeWidth="1"
              strokeDasharray="2 2" />
            <path d="M2 4 L0 7 L2 10 Z" fill="currentColor" />
            <path d="M48 4 L50 7 L48 10 Z" fill="currentColor" />
          </svg>
        </div>
      ))}
    </div>
  );
}

// ─── Section: Hero ───────────────────────────────────────────────────

function Hero() {
  return (
    <section className="border-b border-border">
      <div className="max-w-[1200px] mx-auto px-6 lg:px-10 pt-12 pb-16 lg:pt-20 lg:pb-24">
        <div className="grid lg:grid-cols-12 gap-8 lg:gap-12 items-start">
          <div className="lg:col-span-7">
            <Eyebrow>00 / Sąmatų AI</Eyebrow>
            <h1 className="mt-5 font-semibold text-foreground leading-[1.02] tracking-[-0.02em]
                           text-[44px] sm:text-[60px] lg:text-[78px]">
              Pasiūlymą tu turi iki <Pill>vakaro</Pill>.
              <br />
              <span className="text-muted-foreground">Ne iki ketvirtadienio.</span>
            </h1>
            <p className="mt-7 max-w-[560px] text-[17px] text-foreground/80 leading-[1.55]">
              Įkeli statybų projekto PDF — gauni patalpas, plotus, sienų
              ir lubų kiekius, paruoštus apdailos sąmatai pagal tavo
              kainyną.
            </p>
            <div className="mt-8 flex flex-wrap items-center gap-x-7 gap-y-3">
              <Link to="/register"
                className="text-[16px] text-primary underline underline-offset-[6px]
                           hover:underline-offset-4 transition-all">
                pradėk su savo brėžiniu →
              </Link>
              <Link to="/login"
                className="text-[14px] text-muted-foreground hover:text-foreground transition-colors">
                Jau turi paskyrą?
              </Link>
            </div>
            <p className="mt-5 text-[13px] text-muted-foreground">
              Pirmas bandymas — be įsipareigojimų.
            </p>
            <DimensionChain />
          </div>

          <div className="lg:col-span-5">
            <FloorPlanSVG />
          </div>
        </div>
      </div>
    </section>
  );
}

// ─── Section 01 — Skaitymas ─────────────────────────────────────────

function Skaitymas() {
  return (
    <section id="skaitymas" className="border-b border-border">
      <div className="max-w-[1200px] mx-auto px-6 lg:px-10 py-20 lg:py-28">
        <div className="grid lg:grid-cols-12 gap-8 lg:gap-12">
          <div className="lg:col-span-7 lg:col-start-2">
            <Eyebrow>01 / Skaitymas</Eyebrow>
            <h2 className="mt-3 text-[32px] sm:text-[44px] font-semibold tracking-[-0.015em]
                           leading-[1.08] text-foreground">
              Skaitome tavo <Pill>brėžinį</Pill>
            </h2>
            <p className="mt-6 text-[17px] text-foreground/80 leading-[1.65] max-w-[640px]">
              Sąmatų AI atpažįsta LT statybų brėžinių lapus — aukšto
              planus, pjūvius, sienų išklotines, eksplikacijas. Iš jų
              ištraukia reikiamus kiekius — plotus, perimetrus, sienų
              ir lubų plotus, grindjuosčių ir angokraščių ilgius.
              Tinka butų remontui, namų statybai ir komercinių patalpų
              įrengimui.
            </p>
            <p className="mt-4 text-[14px] text-muted-foreground">
              CAD'o nereikia — užtenka PDF.
            </p>
          </div>
          <Marginalia>
            <div className="border-l border-border pl-4 space-y-3">
              <div>Skaito: <span className="text-foreground">aukšto planai, pjūviai, sienų išklotinės, eksplikacijos</span></div>
              <div>Veikia su: <span className="text-foreground">interjero + apdailos projektais</span></div>
            </div>
          </Marginalia>
        </div>
      </div>
    </section>
  );
}

// ─── Section 02 — Kiekiai (multi-example + kainynas) ────────────────

function Kiekiai() {
  const [activeId, setActiveId] = useState('B');
  const ex = EXAMPLES[activeId];

  // €/vnt. inputs — keyed by line label so they persist across switcher
  const [prices, setPrices] = useState(() => {
    const init = {};
    Object.values(EXAMPLES).forEach(e => e.pricing.forEach(p => {
      if (!(p.l in init)) init[p.l] = p.def;
    }));
    return init;
  });

  const setPrice = (label, val) => {
    const n = parseFloat(val.replace(',', '.'));
    if (!isFinite(n)) return setPrices(p => ({ ...p, [label]: 0 }));
    setPrices(p => ({ ...p, [label]: n }));
  };

  const subtotal = ex.pricing.reduce(
    (s, r) => s + r.q * (prices[r.l] ?? r.def), 0
  );
  const vat = subtotal * 0.21;
  const total = subtotal + vat;

  return (
    <section id="kiekiai" className="border-b border-border bg-card/40">
      <div className="max-w-[1200px] mx-auto px-6 lg:px-10 py-20 lg:py-28">
        <div className="grid lg:grid-cols-12 gap-8 lg:gap-12">
          <div className="lg:col-span-9 lg:col-start-2">
            <Eyebrow>02 / Kiekiai</Eyebrow>
            <h2 className="mt-3 text-[32px] sm:text-[44px] font-semibold tracking-[-0.015em]
                           leading-[1.08] text-foreground">
              Štai, ką <Pill>gauni</Pill>
            </h2>

            {/* Example switcher */}
            <div className="mt-8 flex flex-wrap items-center gap-x-5 gap-y-2 font-mono text-[13px]">
              <span className="uppercase tracking-[0.08em] text-muted-foreground text-[11px]">Pavyzdys</span>
              {Object.values(EXAMPLES).map((e, i) => (
                <React.Fragment key={e.id}>
                  <button
                    onClick={() => setActiveId(e.id)}
                    className={`pb-1 transition-colors ${
                      activeId === e.id
                        ? 'text-foreground border-b-2 border-primary -mb-[2px]'
                        : 'text-muted-foreground hover:text-foreground'
                    }`}
                  >
                    {e.label}
                  </button>
                  {i < Object.keys(EXAMPLES).length - 1 && (
                    <span className="text-muted-foreground/40">·</span>
                  )}
                </React.Fragment>
              ))}
            </div>

            {/* Rooms table */}
            <div className="mt-8 border border-border bg-card">
              <div className="flex items-center justify-between px-5 py-3 border-b border-border">
                <div className="font-mono text-[12px] text-foreground">
                  Aukšto_planas.pdf — kiekiai
                </div>
                <div className="font-mono text-[11px] text-muted-foreground">
                  {fmt(ex.totals.plotas, 1)} m² · {ex.rooms.length} kamb.
                </div>
              </div>

              {/* Desktop: full table */}
              <div className="hidden md:block">
                <div className="grid grid-cols-[2fr,90px,110px,90px,110px] px-5 py-3
                                font-mono text-[10px] uppercase tracking-[0.08em]
                                text-muted-foreground border-b border-border">
                  <div>Kambarys</div>
                  <div className="text-right">Plotas</div>
                  <div className="text-right">Perimetras</div>
                  <div className="text-right">Lubos</div>
                  <div className="text-right">Sienos</div>
                </div>
                {ex.rooms.map((r) => (
                  <div key={r.k}
                    className="grid grid-cols-[2fr,90px,110px,90px,110px] items-center
                               px-5 py-3 border-b border-border/60 text-[14px]">
                    <div className="text-foreground">{r.k}</div>
                    <div className="font-mono tabular text-right text-foreground">{fmt(r.p, 1)} m²</div>
                    <div className="font-mono tabular text-right text-foreground/80">{fmt(r.perim, 1)} m</div>
                    <div className="font-mono tabular text-right text-foreground/80">{fmt(r.h, 2)} m</div>
                    <div className="font-mono tabular text-right text-foreground">{fmt(r.perim * r.h, 1)} m²</div>
                  </div>
                ))}
                <div className="grid grid-cols-[2fr,90px,110px,90px,110px] items-center
                                px-5 py-3 bg-muted/30 font-medium text-[14px]">
                  <div className="text-foreground">Viso</div>
                  <div className="font-mono tabular text-right text-foreground">{fmt(ex.totals.plotas, 1)} m²</div>
                  <div className="font-mono tabular text-right text-foreground">{fmt(ex.totals.perim, 1)} m</div>
                  <div className="font-mono tabular text-right text-muted-foreground">—</div>
                  <div className="font-mono tabular text-right text-foreground">{fmt(ex.totals.sienos, 1)} m²</div>
                </div>
              </div>

              {/* Mobile: cards */}
              <div className="md:hidden">
                {ex.rooms.map((r) => (
                  <div key={r.k} className="px-5 py-3.5 border-b border-border/60">
                    <div className="flex items-baseline justify-between">
                      <div className="text-[14.5px] text-foreground">{r.k}</div>
                      <div className="font-mono tabular text-[14px] text-foreground">{fmt(r.p, 1)} m²</div>
                    </div>
                    <div className="mt-1 flex items-center gap-4 font-mono text-[11.5px] text-muted-foreground">
                      <span>{fmt(r.perim, 1)} m perim.</span>
                      <span>{fmt(r.h, 2)} m lubos</span>
                      <span>{fmt(r.perim * r.h, 0)} m² sienos</span>
                    </div>
                  </div>
                ))}
                <div className="px-5 py-3.5 bg-muted/30 flex items-baseline justify-between">
                  <div className="text-foreground font-medium">Viso</div>
                  <div className="font-mono tabular text-foreground">{fmt(ex.totals.plotas, 1)} m² · {fmt(ex.totals.sienos, 1)} m² sienos</div>
                </div>
              </div>
            </div>

            {/* Bridge sentence */}
            <p className="mt-10 text-[15px] text-muted-foreground">
              Kainas suvedi tu — tai tavo kainynas, ne mūsų.
            </p>

            {/* Kainynas table */}
            <div className="mt-3 border border-border bg-card">
              <div className="hidden md:grid grid-cols-[2fr,110px,140px,140px] px-5 py-3
                              font-mono text-[10px] uppercase tracking-[0.08em]
                              text-muted-foreground border-b border-border">
                <div>Pozicija</div>
                <div className="text-right">Kiekis</div>
                <div className="text-right">€/vnt. (tavo)</div>
                <div className="text-right">Suma €</div>
              </div>
              {ex.pricing.map((row) => {
                const price = prices[row.l] ?? row.def;
                const sum = row.q * price;
                return (
                  <div key={row.l}
                    className="md:grid md:grid-cols-[2fr,110px,140px,140px] items-center
                               px-5 py-3 border-b border-border/60 text-[14px]
                               flex flex-wrap gap-y-2">
                    <div className="text-foreground flex-1 md:flex-none">{row.l}</div>
                    <div className="font-mono tabular text-right text-foreground/80 md:flex-none flex-1">
                      {Number.isInteger(row.q) ? row.q : fmt(row.q, 1)} {row.u}
                    </div>
                    <div className="md:flex md:justify-end md:flex-none w-full md:w-auto">
                      <input
                        type="text"
                        inputMode="decimal"
                        value={fmt2(price)}
                        onChange={e => setPrice(row.l, e.target.value)}
                        className="font-mono tabular text-right w-[110px] px-2 py-1
                                   bg-background border border-border focus:border-primary
                                   focus:outline-none text-foreground text-[14px]"
                      />
                    </div>
                    <div className="font-mono tabular text-right font-medium text-foreground">
                      {fmt2(sum)} €
                    </div>
                  </div>
                );
              })}
              <div className="bg-muted/30 px-5 py-4">
                <div className="grid grid-cols-2 gap-1 max-w-[420px] ml-auto font-mono text-[14px] text-right">
                  <div className="text-muted-foreground">Viso (be PVM):</div>
                  <div className="tabular text-foreground">{fmt2(subtotal)} €</div>
                  <div className="text-muted-foreground">PVM 21%:</div>
                  <div className="tabular text-foreground">{fmt2(vat)} €</div>
                  <div className="text-foreground font-semibold pt-1 border-t border-border/60">Iš viso:</div>
                  <div className="tabular text-foreground font-semibold pt-1 border-t border-border/60">{fmt2(total)} €</div>
                </div>
              </div>
            </div>

            <p className="mt-5 text-[13px] text-muted-foreground max-w-[640px]">
              Pavyzdžiai — apdailos sąmatos pagrindas iš AI ekstrahuotų
              kiekių. Tavo projekto sumos priklauso nuo tavo kainyno.
            </p>
          </div>
          <Marginalia>
            <div className="border-l border-border pl-4 space-y-3 pt-1">
              <div>Lapas: <span className="text-foreground">{ex.sheet}</span></div>
              <div>Mastelis: <span className="text-foreground">{ex.scale}</span></div>
              <div>{ex.totals.plotas.toLocaleString('lt-LT', { minimumFractionDigits: 1 })} m² · {ex.desc}</div>
              <div className="pt-3 border-t border-border/60">Excel ir PDF eksportas — v0.5</div>
            </div>
          </Marginalia>
        </div>
      </div>
    </section>
  );
}

// ─── Section 03 — Eiga (3 steps with ghost numerals) ────────────────

function Eiga() {
  const steps = [
    { n: 1, t: 'Įkeli PDF brėžinius',
      d: 'Aukšto planus, pjūvius, sienų išklotines, eksplikacijas. CAD\'o nereikia.' },
    { n: 2, t: 'AI ištraukia kiekius',
      d: 'Sistema randa patalpas, plotus, perimetrus, sienų ir lubų plotus, grindjuosčių ilgius. Žmogus tvirtina kiekvieną eilutę prieš eksportą.' },
    { n: 3, t: 'Pataisai ir eksportuoji',
      d: 'Suvedi savo kainyną, perkrauni eilutes, eksportuoji į Excel arba PDF su 21% PVM.' },
  ];
  return (
    <section id="eiga" className="border-b border-border">
      <div className="max-w-[1200px] mx-auto px-6 lg:px-10 py-20 lg:py-28">
        <div className="grid lg:grid-cols-12 gap-8 lg:gap-12">
          <div className="lg:col-span-9 lg:col-start-2">
            <Eyebrow>03 / Eiga</Eyebrow>
            <h2 className="mt-3 text-[32px] sm:text-[44px] font-semibold tracking-[-0.015em]
                           leading-[1.08] text-foreground">
              Kaip tai <Pill>veikia</Pill>
            </h2>
            <div className="mt-12 space-y-16">
              {steps.map((s) => (
                <div key={s.n} className="relative max-w-[560px]">
                  <div className="ghost-numeral" aria-hidden>{s.n}</div>
                  <div className="relative">
                    <div className="font-mono text-[12px] text-muted-foreground tracking-[0.08em]">
                      0{s.n}
                    </div>
                    <div className="mt-2 text-[22px] font-semibold text-foreground">{s.t}</div>
                    <p className="mt-2 text-[16px] text-foreground/80 leading-[1.55]">{s.d}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

// ─── Section 04 — Skaidrumas (Šiandien / Ruošiame) ──────────────────

function Skaidrumas() {
  const today = [
    'Patalpų plotai, perimetrai, lubų aukščiai',
    'Sienų plotai (perimetras × aukštis)',
    'Grindjuosčių ilgis (iš perimetro)',
    'Angokraščių ilgis (iš angų perimetrų)',
    'Eksportas į Excel ir PDF su 21% PVM',
    'Geriausiai veikia su vidaus apdailos brėžiniais',
  ];
  const next = [
    'Fasadų brėžinių skaitymas (ETICS, mastelis, angos)',
    'Stogų konstrukcijos kiekiai (šlaitai, dangos)',
    'Mūro darbų kiekiai (blokai, pertvarų ilgiai)',
    'MEP brėžinių skaitymas (elektra, santechnika, ŠVOK)',
    'Daugiabučių modernizavimas (APVA / BETA formatas)',
    'F2 / F3 forma eksportas',
  ];
  return (
    <section id="skaidrumas" className="border-b border-border bg-card/40">
      <div className="max-w-[1200px] mx-auto px-6 lg:px-10 py-20 lg:py-28">
        <div className="grid lg:grid-cols-12 gap-8 lg:gap-12">
          <div className="lg:col-span-9 lg:col-start-2">
            <Eyebrow>04 / Skaidrumas</Eyebrow>
            <h2 className="mt-3 text-[32px] sm:text-[44px] font-semibold tracking-[-0.015em]
                           leading-[1.08] text-foreground">
              Kas <Pill>veikia</Pill> šiandien
            </h2>
            <div className="mt-12 grid md:grid-cols-2 border border-border bg-card">
              <div className="p-7 border-b md:border-b-0 md:border-r border-border">
                <div className="font-mono text-[11px] uppercase tracking-[0.08em] text-muted-foreground mb-5">
                  Šiandien
                </div>
                <ul className="space-y-3.5 text-[15.5px] text-foreground leading-[1.5]">
                  {today.map((t) => (
                    <li key={t} className="flex gap-3">
                      <span className="mt-[8px] block w-[6px] h-[6px] bg-foreground shrink-0" />
                      <span>{t}</span>
                    </li>
                  ))}
                </ul>
              </div>
              <div className="p-7">
                <div className="font-mono text-[11px] uppercase tracking-[0.08em] text-muted-foreground mb-5">
                  Ruošiame
                </div>
                <ul className="space-y-3.5 text-[15.5px] text-muted-foreground leading-[1.5]">
                  {next.map((t) => (
                    <li key={t} className="flex gap-3">
                      <span className="mt-[8px] block w-[6px] h-[6px] bg-muted-foreground/60 shrink-0" />
                      <span>{t}</span>
                    </li>
                  ))}
                </ul>
              </div>
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}

// ─── Section 05 — Manifesto + Kontaktai ─────────────────────────────

function ManifestoCloser() {
  return (
    <section id="kontaktai" className="border-b border-border">
      <div className="max-w-[1200px] mx-auto px-6 lg:px-10 py-24 lg:py-32">
        <div className="grid lg:grid-cols-12 gap-8 lg:gap-12">
          <div className="lg:col-span-9 lg:col-start-2 max-w-[720px]">
            <blockquote className="font-serif italic text-[28px] sm:text-[34px] leading-[1.4]
                                   text-foreground"
              style={{ fontFamily: '"Instrument Serif", Georgia, serif' }}>
              „Iš statybų projekto, kuris atkeliauja PDF'u, sąmatininkas
              pirmas tris valandas tik matuoja patalpas, perimetrus ir
              sienų plotus. Tas valandas atliekam už tave. Tavo kainynas,
              tavo objektas, tavo pasiūlymas — lieka tau."
            </blockquote>

            <div className="mt-12">
              <Link to="/register"
                className="text-[18px] text-primary underline underline-offset-[6px]
                           hover:underline-offset-4 transition-all">
                pradėk su savo brėžiniu →
              </Link>
            </div>

            <div className="mt-8 flex flex-wrap items-center gap-x-6 gap-y-2
                            font-mono text-[14px] text-muted-foreground">
              <a href="mailto:solutions@pathon.eu?subject=S%C4%85mat%C5%B3%20AI%20%E2%80%94%20u%C5%BEklausa"
                 className="hover:text-foreground transition-colors">
                solutions@pathon.eu
              </a>
              <span className="text-muted-foreground/40">·</span>
              <a href="https://wa.me/37060271962"
                 target="_blank" rel="noopener noreferrer"
                 className="hover:text-foreground transition-colors">
                WhatsApp
              </a>
            </div>

            <p className="mt-5 text-[13px] text-muted-foreground">
              Atsakome darbo dienomis 9–18 — el. paštu arba WhatsApp.
            </p>
          </div>
        </div>
      </div>
    </section>
  );
}

// ─── Nav (slim 56px) ────────────────────────────────────────────────

function LandingNav() {
  return (
    <header className="sticky top-0 z-30 border-b border-border bg-background/85 backdrop-blur
                       supports-[backdrop-filter]:bg-background/75">
      <div className="max-w-[1200px] mx-auto px-6 lg:px-10 h-14 flex items-center justify-between">
        <Link to="/" className="flex items-center gap-2.5 text-foreground">
          <NorthArrow size={20} />
          <span className="font-semibold tracking-tight text-[15px]">Sąmatų AI</span>
          <span className="font-mono text-[11px] text-muted-foreground ml-1">v0.4 — beta</span>
        </Link>
        <nav className="hidden lg:flex items-center gap-7 font-mono text-[12px]
                        text-muted-foreground tracking-[0.04em]">
          <a href="#skaitymas" className="hover:text-foreground transition-colors">01 SKAITYMAS</a>
          <a href="#kiekiai" className="hover:text-foreground transition-colors">02 KIEKIAI</a>
          <a href="#eiga" className="hover:text-foreground transition-colors">03 EIGA</a>
          <a href="#skaidrumas" className="hover:text-foreground transition-colors">04 SKAIDRUMAS</a>
        </nav>
        <div className="flex items-center gap-4">
          <Link to="/login"
            className="hidden sm:inline text-[13px] text-muted-foreground hover:text-foreground transition-colors">
            Prisijungti
          </Link>
          <Link to="/register"
            className="text-[13px] text-primary underline underline-offset-4 hover:underline-offset-2 transition-all">
            Išbandyti →
          </Link>
        </div>
      </div>
    </header>
  );
}

// ─── Footer (title block + scale bar) ───────────────────────────────

function LandingFooter() {
  return (
    <footer className="bg-card/60">
      <div className="max-w-[1200px] mx-auto px-6 lg:px-10 py-12">
        <div className="grid md:grid-cols-3 gap-8 items-end">
          <div>
            <div className="text-muted-foreground font-mono text-[10px] uppercase tracking-[0.08em] mb-2">
              Mastelis
            </div>
            <ScaleBar />
          </div>
          <div className="text-center">
            <div className="flex items-center justify-center gap-2 text-foreground">
              <NorthArrow size={18} />
              <span className="font-semibold tracking-tight">Sąmatų AI</span>
            </div>
            <p className="mt-2 text-[13px] text-muted-foreground">
              Statybų sąmatos iš PDF brėžinių.
            </p>
          </div>
          <div className="md:justify-self-end">
            <div className="font-mono text-[10px] border border-border bg-card">
              <div className="grid grid-cols-[80px,1fr] border-b border-border">
                <div className="px-3 py-1.5 text-muted-foreground border-r border-border">M 1:1</div>
                <div className="px-3 py-1.5 text-foreground">v0.4 — beta</div>
              </div>
              <div className="grid grid-cols-[80px,1fr] border-b border-border">
                <div className="px-3 py-1.5 text-muted-foreground border-r border-border">Data</div>
                <div className="px-3 py-1.5 text-foreground">2026-05-12</div>
              </div>
              <div className="grid grid-cols-[80px,1fr]">
                <div className="px-3 py-1.5 text-muted-foreground border-r border-border">Lapas</div>
                <div className="px-3 py-1.5 text-foreground">SA-01</div>
              </div>
            </div>
          </div>
        </div>
        <div className="mt-10 pt-6 border-t border-border flex flex-col sm:flex-row items-start
                        sm:items-center justify-between gap-3 text-[12px] text-muted-foreground">
          <div>© 2026 Sąmatų AI · Produktas dar testavimo stadijoje</div>
          <div className="flex items-center gap-5">
            <Link to="/privacy" className="hover:text-foreground transition-colors">
              Privatumas
            </Link>
            <Link to="/terms" className="hover:text-foreground transition-colors">
              Naudojimo sąlygos
            </Link>
          </div>
        </div>
      </div>
    </footer>
  );
}

// ─── Default export ─────────────────────────────────────────────────

export default function Landing() {
  return (
    <div className="min-h-screen bg-background text-foreground">
      <LandingNav />
      <Hero />
      <Skaitymas />
      <Kiekiai />
      <Eiga />
      <Skaidrumas />
      <ManifestoCloser />
      <LandingFooter />
    </div>
  );
}
