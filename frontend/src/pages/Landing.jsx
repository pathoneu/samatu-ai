/**
 * Pathon — public landing page (2026-07-05 dark graphite rebuild).
 *
 * Shown at "/" for unauthenticated visitors. Authenticated users get
 * redirected to /dashboard via the wrapper in App.jsx.
 *
 * Design language: DARK, TECHNICAL, PREMIUM construction-AI. Orange
 * (#F76B1C) on graphite (#15181E). Reference bar: Togal.ai + Kreo (dark,
 * serious, product-led) — distinct via orange, not their green/blue.
 * Sora display, Hanken Grotesk body, JetBrains Mono for every quantity /
 * price / technical label. Editorial asymmetry, mono coordinate ticks
 * (01 / HERO), dimension-line + blueprint-grid motifs.
 *
 * Positioning is GENERAL across ALL trades — interior, facade, roof,
 * structural, earthworks, masonry — not interior-only.
 *
 * Motion: framer-motion for scroll reveals + count-ups; a CSS-driven SVG
 * "AI aptinka kiekius" detection panel in the hero (scan line sweeps, orange
 * detection boxes snap on one-by-one). ROBUSTNESS: every section renders at
 * final state when reduced-motion is on OR when a reveal never fires —
 * reveals start at a visible fallback and only the *transition* is deferred;
 * the hero panel's base (no `.play`) is the fully-detected end state.
 */
import React, { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import {
  motion,
  useReducedMotion,
  useInView,
  animate,
} from 'framer-motion';
import { PathonMark } from '@/components/layout/Logo';

// ─── Number formatting (LT convention: comma decimals) ──────────────

const fmt = (n, d = 1) =>
  n.toLocaleString('lt-LT', { minimumFractionDigits: d, maximumFractionDigits: d });

// ─── Reveal — scroll-triggered fade+rise, reduced-motion aware ───────

const EASE = [0.16, 1, 0.3, 1];

function Reveal({ children, delay = 0, y = 16, className = '', as = 'div' }) {
  const reduce = useReducedMotion();
  const MotionTag = motion[as] || motion.div;
  if (reduce) {
    const Tag = as;
    return <Tag className={className}>{children}</Tag>;
  }
  return (
    <MotionTag
      className={className}
      initial={{ opacity: 0, y }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true, amount: 0.2 }}
      transition={{ duration: 0.62, ease: EASE, delay: delay / 1000 }}
    >
      {children}
    </MotionTag>
  );
}

// ─── CountUp — animates a number when scrolled into view ─────────────

function CountUp({ to, decimals = 0, suffix = '', prefix = '', duration = 1.4 }) {
  const reduce = useReducedMotion();
  const ref = useRef(null);
  const inView = useInView(ref, { once: true, amount: 0.5 });
  const [val, setVal] = useState(reduce ? to : 0);

  useEffect(() => {
    if (reduce || !inView) return;
    const controls = animate(0, to, {
      duration,
      ease: EASE,
      onUpdate: (v) => setVal(v),
    });
    return () => controls.stop();
  }, [inView, to, reduce, duration]);

  return (
    <span ref={ref} className="tabular">
      {prefix}
      {fmt(val, decimals)}
      {suffix}
    </span>
  );
}

// ─── Small primitives ────────────────────────────────────────────────

const Eyebrow = ({ children, index }) => (
  <div className="flex items-center gap-2.5">
    {index && <span className="mono-tick">{index}</span>}
    <span className="font-mono text-[11px] tracking-[0.18em] uppercase text-primary">
      {children}
    </span>
  </div>
);

const ArrowIcon = ({ size = 16 }) => (
  <svg width={size} height={size} viewBox="0 0 16 16" fill="none" stroke="currentColor"
    strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
    <path d="M3 8h10M9 4l4 4-4 4" />
  </svg>
);

const CheckIcon = ({ size = 15, className = '' }) => (
  <svg width={size} height={size} viewBox="0 0 16 16" fill="none" stroke="hsl(var(--primary))"
    strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className={className}>
    <path d="M13 4L6 12l-3.5-3.5" />
  </svg>
);

// ─── Marketing constants ─────────────────────────────────────────────

const NAV_LINKS = [
  { href: '#galimybes', label: 'Galimybės' },
  { href: '#eiga', label: 'Kaip veikia' },
  { href: '#kainos', label: 'Kainos' },
];

const TRUST_PILLS = ['NRM2', 'DIN standartai', 'LT sąmata', '21% PVM', 'Excel & PDF'];

const OUTCOMES = [
  { big: 'kelios min.', small: 'vietoj valandų rankinio matavimo' },
  { big: 'bet kuris brėžinys', small: 'PDF, be CAD' },
  { big: 'LT sąmata · 21% PVM', small: 'paruoštas formatas' },
  { big: 'Excel + PDF', small: 'vienu paspaudimu' },
];

const STEPS = [
  {
    n: 1,
    t: 'Įkelk brėžinį',
    d: 'Bet koks statybų PDF: planai, pjūviai, išklotinės, fasadai.',
  },
  {
    n: 2,
    t: 'Pathon aptinka ir matuoja',
    d: 'Elementai, plotai, ilgiai, kiekiai. Kiekviena reikšmė su šaltinio žyma.',
  },
  {
    n: 3,
    t: 'Peržiūrėk ir eksportuok',
    d: 'Pakoreguok, įrašyk kainas, eksportuok į Excel ar PDF su PVM.',
  },
];

// GENERAL multi-trade grid (the KEY change) ─────────────────────────
const TRADES = [
  { t: 'Interjero apdaila', d: 'Dažomi plotai, plytelės, grindys, gipskartonis.', icon: 'interior' },
  { t: 'Fasadai', d: 'ETICS plotai, tinkas, šiltinimas, angos.', icon: 'facade' },
  { t: 'Stogai', d: 'Dangos plotai su nuolydžiu, latakai, kraigas.', icon: 'roof' },
  { t: 'Konstrukcijos', d: 'Betonas, armatūra, klotinės (m³, kg).', icon: 'structure' },
  { t: 'Žemės darbai', d: 'Iškasos, pylimai, tūriai.', icon: 'earth' },
  { t: 'Mūras', d: 'Sienų plotai, blokai, mūro kiekiai.', icon: 'masonry' },
];

const TradeIcon = ({ kind, size = 18 }) => {
  const common = {
    width: size, height: size, viewBox: '0 0 24 24', fill: 'none',
    stroke: 'hsl(var(--primary))', strokeWidth: 1.7,
    strokeLinecap: 'round', strokeLinejoin: 'round',
  };
  switch (kind) {
    case 'interior': // room / paint roller
      return (<svg {...common}><rect x="3" y="4" width="18" height="16" rx="1" /><path d="M3 10h18M9 10v10" /></svg>);
    case 'facade': // building elevation
      return (<svg {...common}><rect x="4" y="3" width="16" height="18" rx="1" /><path d="M8 7h2M14 7h2M8 11h2M14 11h2M8 15h2M14 15h2" /></svg>);
    case 'roof': // pitched roof
      return (<svg {...common}><path d="M3 12l9-8 9 8" /><path d="M5 11v9h14v-9" /><path d="M12 4v0" /></svg>);
    case 'structure': // beams / rebar
      return (<svg {...common}><path d="M4 6h16M4 18h16M8 6v12M16 6v12" /></svg>);
    case 'earth': // excavation
      return (<svg {...common}><path d="M3 8l4 2 4-2 4 2 4-2" /><path d="M3 8v9a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2V8" /></svg>);
    case 'masonry': // brick bond
      return (<svg {...common}><rect x="3" y="5" width="18" height="14" rx="1" /><path d="M3 12h18M9 5v7M15 12v7" /></svg>);
    default:
      return null;
  }
};

const AUDIENCES = [
  { t: 'Rangovams', d: 'Greiti, tikslūs pasiūlymai. Laimėk daugiau objektų.' },
  { t: 'Sąmatininkams', d: 'Rankinį matavimą palik Pathon’ui — tikrink, o ne skaičiuok iš naujo.' },
  { t: 'Statybos įmonėms', d: 'Vienas įrankis visų tipų kiekiams — nuo pamatų iki apdailos.' },
];

const TIERS = [
  { name: 'Vienkartinis', price: '12 €', unit: '/ projektas', desc: 'Vienas objektas, be prenumeratos.', feats: ['1 projektas', 'Visi trade tipai', 'Excel + PDF eksportas'], cta: 'Išbandyti', primary: false },
  { name: 'Pro', price: '49 €', unit: '/ mėn.', desc: 'Nuolat dirbančiam sąmatininkui.', feats: ['Neriboti projektai', 'Savo kainynas', 'Korekcijų įrankis', 'Prioritetinis palaikymas'], cta: 'Pradėti', primary: true },
  { name: 'Studio', price: '149 €', unit: '/ mėn.', desc: 'Komandai ir įmonei.', feats: ['Viskas iš Pro', 'Komandos paskyros', 'Bendri kainynai', 'API prieiga (netrukus)'], cta: 'Susisiekti', primary: false },
];

// Hero panel: detected rooms + trade tabs ────────────────────────────
const HERO_ROOMS = [
  { k: 'Svetainė', p: '28,4 m²' },
  { k: 'Miegamasis', p: '14,2 m²' },
  { k: 'Vaiko k.', p: '11,8 m²' },
  { k: 'Koridorius', p: '10,9 m²' },
  { k: 'Vonia', p: '4,6 m²' },
];

const HERO_TABS = [
  { l: 'Interjeras', active: true },
  { l: 'Fasadai', active: true },
  { l: 'Stogai', active: true },
  { l: 'Konstrukcijos', active: false },
  { l: 'Žemės darbai', active: false },
  { l: 'Mūras', active: false },
];

// ─── Hero centerpiece: detection panel SVG ───────────────────────────
// A dark floor plan (blueprint hairlines), an orange scan line sweeping
// down, and orange detection boxes (with corner brackets) snapping onto
// each detected room one-by-one. Base state (no `.play`) = fully detected.

const HERO_BOXES = [
  { cls: 'd1', x: 4, y: 4, w: 128, h: 126, label: 'Svetainė', val: '28,4 m²', lx: 68, ly: 62 },
  { cls: 'd2', x: 136, y: 4, w: 98, h: 126, label: 'Miegamasis', val: '14,2 m²', lx: 185, ly: 62 },
  { cls: 'd3', x: 238, y: 4, w: 128, h: 126, label: 'Vaiko k.', val: '11,8 m²', lx: 302, ly: 62 },
  { cls: 'd4', x: 4, y: 134, w: 172, h: 92, label: 'Koridorius', val: '10,9 m²', lx: 90, ly: 184 },
  { cls: 'd5', x: 180, y: 134, w: 98, h: 92, label: 'Vonia', val: '4,6 m²', lx: 229, ly: 184 },
  { cls: 'd6', x: 282, y: 134, w: 84, h: 92, label: 'WC', val: '2,1 m²', lx: 324, ly: 184 },
];

// Corner brackets for a detection box (drawn at each corner)
function Brackets({ x, y, w, h }) {
  const L = 9; // bracket arm length
  const s = { stroke: 'hsl(var(--primary))', strokeWidth: 1.6, fill: 'none', strokeLinecap: 'round' };
  return (
    <g>
      <path d={`M${x} ${y + L} V${y} H${x + L}`} {...s} />
      <path d={`M${x + w - L} ${y} H${x + w} V${y + L}`} {...s} />
      <path d={`M${x + w} ${y + h - L} V${y + h} H${x + w - L}`} {...s} />
      <path d={`M${x + L} ${y + h} H${x} V${y + h - L}`} {...s} />
    </g>
  );
}

function HeroPlanSVG({ play }) {
  return (
    <svg
      viewBox="0 0 390 268"
      className={`hero-plan w-full h-auto ${play ? 'play' : ''}`}
      role="img"
      aria-labelledby="hero-plan-title"
    >
      <title id="hero-plan-title">
        Pathon aptinka patalpas ir kiekius aukšto plane: 6 patalpos, 72 m²
      </title>
      <g transform="translate(12, 14)">
        {/* Faint floor-plan hairlines (blueprint on graphite) */}
        <g>
          <path className="plan-line" d="M0,0 H366 V226 H0 Z" fill="none"
            stroke="hsl(var(--muted-foreground) / 0.55)" strokeWidth="1.4" />
          <line className="plan-line" x1="0" y1="130" x2="366" y2="130" stroke="hsl(var(--muted-foreground) / 0.4)" strokeWidth="1" />
          <line className="plan-line" x1="132" y1="0" x2="132" y2="130" stroke="hsl(var(--muted-foreground) / 0.4)" strokeWidth="1" />
          <line className="plan-line" x1="234" y1="0" x2="234" y2="130" stroke="hsl(var(--muted-foreground) / 0.4)" strokeWidth="1" />
          <line className="plan-line" x1="176" y1="130" x2="176" y2="226" stroke="hsl(var(--muted-foreground) / 0.4)" strokeWidth="1" />
          <line className="plan-line" x1="278" y1="130" x2="278" y2="226" stroke="hsl(var(--muted-foreground) / 0.4)" strokeWidth="1" />
          {/* Windows (double hairline on the top edge) */}
          {[[40, 92], [160, 210], [280, 336]].map(([x1, x2], i) => (
            <line key={i} className="plan-line" x1={x1} y1="0" x2={x2} y2="0"
              stroke="hsl(var(--foreground) / 0.7)" strokeWidth="2.4" />
          ))}
          {/* Door arcs */}
          <path className="plan-line" d="M62 130 a14 14 0 0 1 14 -14" fill="none" stroke="hsl(var(--muted-foreground) / 0.5)" strokeWidth="0.8" />
          <path className="plan-line" d="M300 130 a12 12 0 0 1 12 -12" fill="none" stroke="hsl(var(--muted-foreground) / 0.5)" strokeWidth="0.8" />
        </g>

        {/* Detection boxes — orange fill wash + brackets + labels */}
        {HERO_BOXES.map((b) => (
          <g key={b.cls}>
            <g className={`det-box ${b.cls}`}>
              <rect x={b.x} y={b.y} width={b.w} height={b.h} rx="2"
                fill="hsl(var(--primary) / 0.06)"
                stroke="hsl(var(--primary) / 0.45)" strokeWidth="1" />
              <Brackets x={b.x} y={b.y} w={b.w} h={b.h} />
            </g>
            <g className={`det-label ${b.cls}`} fontFamily="JetBrains Mono, monospace">
              <text x={b.lx} y={b.ly} textAnchor="middle" fontSize="8.5"
                fill="hsl(var(--foreground))" letterSpacing="0.02em">
                {b.label.toUpperCase()}
              </text>
              <text x={b.lx} y={b.ly + 13} textAnchor="middle" fontSize="8"
                fill="hsl(var(--primary))">{b.val}</text>
            </g>
          </g>
        ))}

        {/* Scan line — orange sweep, top → bottom */}
        <g className="scan-line">
          <rect x="-6" y="-8" width="378" height="10" fill="hsl(var(--primary) / 0.14)" />
          <line x1="-6" y1="0" x2="372" y2="0" stroke="hsl(var(--primary))" strokeWidth="2" />
          <circle cx="-6" cy="0" r="2.2" fill="hsl(var(--primary))" />
          <circle cx="372" cy="0" r="2.2" fill="hsl(var(--primary))" />
        </g>

        {/* Dimension line (top) — coordinate-tick signature */}
        <g fontFamily="JetBrains Mono, monospace">
          <line x1="0" y1="-9" x2="366" y2="-9" stroke="hsl(var(--muted-foreground) / 0.5)" strokeWidth="0.5" />
          <line x1="0" y1="-12" x2="0" y2="-6" stroke="hsl(var(--muted-foreground) / 0.5)" strokeWidth="0.6" />
          <line x1="366" y1="-12" x2="366" y2="-6" stroke="hsl(var(--muted-foreground) / 0.5)" strokeWidth="0.6" />
        </g>

        {/* Title block */}
        <g transform="translate(226, 246)" fontFamily="JetBrains Mono, monospace">
          <rect x="0" y="0" width="140" height="26" fill="hsl(var(--surface-2))"
            stroke="hsl(var(--border-strong))" strokeWidth="0.7" />
          <line x1="70" y1="0" x2="70" y2="26" stroke="hsl(var(--border-strong))" strokeWidth="0.6" />
          <text x="6" y="11" fontSize="7" fill="hsl(var(--foreground))">M 1:50</text>
          <text x="76" y="11" fontSize="7" fill="hsl(var(--foreground))">72,0 m²</text>
          <text x="6" y="21" fontSize="7" fill="hsl(var(--muted-foreground))">SA-01</text>
          <text x="76" y="21" fontSize="7" fill="hsl(var(--muted-foreground))">6 patalpos</text>
        </g>
      </g>
    </svg>
  );
}

// ─── Hero product frame — plan (left) + extracted quantities (right) ──

function HeroProductFrame() {
  const reduce = useReducedMotion();
  const ref = useRef(null);
  const inView = useInView(ref, { once: false, amount: 0.35 });
  // Replay on scroll-into-view: key remounts the animated children.
  const [key, setKey] = useState(0);
  const wasOut = useRef(true);
  useEffect(() => {
    if (reduce) return;
    if (inView && wasOut.current) {
      setKey((k) => k + 1);
      wasOut.current = false;
    } else if (!inView) {
      wasOut.current = true;
    }
  }, [inView, reduce]);

  const play = !reduce;

  return (
    <div ref={ref} className="product-frame overflow-hidden">
      {/* window chrome bar */}
      <div className="flex items-center gap-2 px-4 h-9 border-b border-border bg-surface-2">
        <span className="w-2.5 h-2.5 rounded-full bg-border-strong" />
        <span className="w-2.5 h-2.5 rounded-full bg-border-strong" />
        <span className="w-2.5 h-2.5 rounded-full bg-border-strong" />
        <span className="ml-3 font-mono text-[11px] text-muted-foreground truncate">
          projektas_A3.pdf — aptikta 6 patalpų
        </span>
        <span className="ml-auto font-mono text-[10px] text-primary hidden sm:inline">● aptikta</span>
      </div>
      <div className="grid sm:grid-cols-[1.18fr_1fr]" key={key}>
        {/* plan */}
        <div className="relative blueprint-grid p-4 border-b sm:border-b-0 sm:border-r border-border bg-background">
          <HeroPlanSVG play={play} />
        </div>
        {/* extracted quantities */}
        <div className="p-4 sm:p-5 bg-card">
          <div className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground mb-3">
            Ištraukti kiekiai
          </div>
          <div className={`qty-table ${play ? 'play' : ''}`}>
            {HERO_ROOMS.map((r, i) => (
              <div
                key={r.k}
                className="qty-row flex items-baseline justify-between py-[7px] border-b border-border/70 text-[12.5px]"
                style={play ? { animationDelay: `${1000 + i * 130}ms` } : undefined}
              >
                <span className="text-foreground/80 truncate pr-2">{r.k}</span>
                <span className="font-mono tabular text-foreground whitespace-nowrap">{r.p}</span>
              </div>
            ))}
            <div className="flex items-baseline justify-between pt-3 mt-1">
              <span className="text-[12px] font-medium text-foreground">Sienų plotas</span>
              <span className="font-mono tabular text-[15px] font-semibold text-primary">
                <CountUp to={213} decimals={1} suffix=" m²" duration={1.3} />
              </span>
            </div>
          </div>
          <div className="mt-4 pt-3 border-t border-border grid grid-cols-2 gap-y-2 font-mono text-[11px]">
            <div className="text-muted-foreground">Grindys</div>
            <div className="tabular text-right text-foreground">
              <CountUp to={72} decimals={1} suffix=" m²" duration={1.3} />
            </div>
            <div className="text-muted-foreground">Grindjuostės</div>
            <div className="tabular text-right text-foreground">73 m</div>
            <div className="text-foreground font-medium pt-2 border-t border-border/70">Sąmata su PVM</div>
            <div className="tabular text-right font-semibold text-primary pt-2 border-t border-border/70">
              <CountUp to={8017} decimals={0} suffix=" €" duration={1.7} />
            </div>
          </div>
        </div>
      </div>

      {/* Trade tabs — active ones highlighted orange */}
      <div className="flex flex-wrap items-center gap-1.5 px-4 py-3 border-t border-border bg-surface-2">
        {HERO_TABS.map((t) => (
          <span
            key={t.l}
            className={`trade-tab font-mono text-[10.5px] px-2.5 py-1 rounded-md border ${
              t.active
                ? 'text-primary border-primary/40 bg-primary/[0.08]'
                : 'text-muted-foreground/70 border-border bg-transparent'
            }`}
          >
            {t.l}
          </span>
        ))}
      </div>
    </div>
  );
}

// ─── Sticky top nav ──────────────────────────────────────────────────

function LandingNav() {
  const [open, setOpen] = useState(false);
  const [scrolled, setScrolled] = useState(false);
  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8);
    onScroll();
    window.addEventListener('scroll', onScroll, { passive: true });
    return () => window.removeEventListener('scroll', onScroll);
  }, []);
  return (
    <header
      className={`sticky top-0 z-40 transition-colors duration-300 ${
        scrolled
          ? 'border-b border-border bg-background/85 backdrop-blur-md supports-[backdrop-filter]:bg-background/70'
          : 'border-b border-transparent'
      }`}
    >
      <div className="max-w-[1200px] mx-auto px-5 lg:px-8 h-16 flex items-center justify-between">
        <Link to="/" className="flex items-center gap-2.5 text-foreground">
          <PathonMark icon={26} />
          <span className="font-display font-bold tracking-tight text-[19px]">Pathon</span>
        </Link>

        <nav className="hidden md:flex items-center gap-8 text-[14px] text-muted-foreground">
          {NAV_LINKS.map((l) => (
            <a key={l.href} href={l.href} className="link-draw">{l.label}</a>
          ))}
          <Link to="/login" className="link-draw">Prisijungti</Link>
        </nav>

        <div className="hidden md:flex items-center gap-3">
          <Link to="/register" className="btn-primary text-[14px] px-4 py-2">
            Išbandyti nemokamai
          </Link>
        </div>

        {/* Mobile hamburger */}
        <button
          className="md:hidden inline-flex items-center justify-center w-10 h-10 -mr-2 text-foreground"
          aria-label="Meniu" aria-expanded={open}
          onClick={() => setOpen((v) => !v)}
        >
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round">
            {open ? <><path d="M6 6l12 12" /><path d="M18 6L6 18" /></>
                  : <><path d="M4 7h16" /><path d="M4 12h16" /><path d="M4 17h16" /></>}
          </svg>
        </button>
      </div>

      {open && (
        <div className="md:hidden border-t border-border bg-background/97 backdrop-blur-md">
          <div className="px-5 py-4 flex flex-col gap-1 text-[15px]">
            {NAV_LINKS.map((l) => (
              <a key={l.href} href={l.href} onClick={() => setOpen(false)}
                className="py-2.5 text-foreground/85 hover:text-foreground">{l.label}</a>
            ))}
            <Link to="/login" onClick={() => setOpen(false)} className="py-2.5 text-foreground/85 hover:text-foreground">Prisijungti</Link>
            <Link to="/register" onClick={() => setOpen(false)} className="btn-primary mt-2 justify-center py-2.5">
              Išbandyti nemokamai
            </Link>
          </div>
        </div>
      )}
    </header>
  );
}

// ─── Hero ────────────────────────────────────────────────────────────

function Hero() {
  const reduce = useReducedMotion();
  return (
    <section className="relative border-b border-border overflow-hidden">
      {/* layered blueprint texture + orange radial glow */}
      <div className="absolute inset-0 blueprint-grid-major opacity-80 pointer-events-none" aria-hidden />
      <div
        className="absolute -top-52 -right-40 w-[620px] h-[620px] rounded-full pointer-events-none"
        aria-hidden
        style={{
          background:
            'radial-gradient(circle, hsl(var(--primary) / 0.16), transparent 62%)',
        }}
      />
      <div className="relative max-w-[1200px] mx-auto px-5 lg:px-8 pt-14 pb-20 lg:pt-24 lg:pb-28">
        <div className="grid lg:grid-cols-[1.02fr_1fr] gap-12 lg:gap-16 items-center">
          <div>
            <Reveal>
              <Eyebrow index="01 / HERO">Statybų AI · Kiekiai iš brėžinių</Eyebrow>
            </Reveal>
            <Reveal delay={70} as="h1"
              className="mt-6 font-display font-bold text-foreground tracking-[-0.03em]
                         leading-[0.98] text-[44px] sm:text-[60px] lg:text-[74px]">
              Bet koks brėžinys —{' '}
              <br className="hidden sm:block" />
              <span className="h-accent">tikslūs kiekiai.</span>
            </Reveal>
            <Reveal delay={140} as="p"
              className="mt-7 max-w-[560px] text-[17px] sm:text-[18.5px] text-ink-2 leading-[1.6]">
              Pathon skaito interjero, fasadų, stogų ir konstrukcijų brėžinius,
              išmatuoja kiekius ir paruošia sąmatą — automatiškai, Lietuvos
              formatu.
            </Reveal>
            <Reveal delay={210} className="mt-9 flex flex-col sm:flex-row items-stretch sm:items-center gap-3">
              <Link to="/register" className="btn-primary justify-center px-5 py-3 text-[15px]">
                Išbandyti nemokamai
                <ArrowIcon />
              </Link>
              <a href="#eiga" className="btn-ghost justify-center px-5 py-3 text-[15px]">
                Žiūrėti demo
              </a>
            </Reveal>
            <Reveal delay={280} as="p" className="mt-6 font-mono text-[12px] text-muted-foreground">
              Pirmas projektas — nemokamai. Be įsipareigojimų.
            </Reveal>

            {/* Trust pills */}
            <Reveal delay={340} className="mt-8 flex flex-wrap gap-x-4 gap-y-2 items-center">
              {TRUST_PILLS.map((p, i) => (
                <React.Fragment key={p}>
                  {i > 0 && <span className="text-border-strong hidden sm:inline">·</span>}
                  <span className="font-mono text-[11px] tracking-[0.04em] text-muted-foreground">{p}</span>
                </React.Fragment>
              ))}
            </Reveal>
          </div>

          <motion.div
            className="lg:pl-2"
            initial={reduce ? false : { opacity: 0, y: 24 }}
            animate={reduce ? undefined : { opacity: 1, y: 0 }}
            transition={{ duration: 0.7, ease: EASE, delay: 0.15 }}
          >
            <HeroProductFrame />
          </motion.div>
        </div>
      </div>
    </section>
  );
}

// ─── Outcome strip (4 mono facts) ────────────────────────────────────

function OutcomeStrip() {
  return (
    <section className="border-b border-border bg-card">
      <div className="max-w-[1200px] mx-auto px-5 lg:px-8">
        <div className="grid grid-cols-2 lg:grid-cols-4 divide-y divide-x divide-border [&>*]:border-border">
          {OUTCOMES.map((o, i) => (
            <Reveal key={i} delay={i * 70} className="p-6 lg:p-8">
              <div className="font-mono font-medium text-[16px] lg:text-[18px] text-foreground tracking-[-0.01em]">
                «{o.big}»
              </div>
              <div className="mt-2 text-[13px] text-muted-foreground leading-snug">{o.small}</div>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  );
}

// ─── Section header helper ───────────────────────────────────────────

function SectionHead({ eyebrow, index, title, sub, align = 'left', className = '' }) {
  const alignCls = align === 'center' ? 'mx-auto text-center items-center flex flex-col' : '';
  return (
    <div className={`max-w-[700px] ${alignCls} ${className}`}>
      <Reveal><Eyebrow index={index}>{eyebrow}</Eyebrow></Reveal>
      <Reveal delay={70} as="h2"
        className="mt-5 font-display font-semibold text-foreground tracking-[-0.02em]
                   leading-[1.04] text-[32px] sm:text-[46px]">
        {title}
      </Reveal>
      {sub && (
        <Reveal delay={140} as="p" className="mt-5 text-[16px] sm:text-[17px] text-ink-2 leading-[1.6]">
          {sub}
        </Reveal>
      )}
    </div>
  );
}

// ─── Kaip tai veikia (3 steps, editorial numbered cards) ─────────────

function Eiga() {
  return (
    <section id="eiga" className="border-b border-border scroll-mt-20 relative overflow-hidden">
      <div className="absolute inset-0 blueprint-grid opacity-50 pointer-events-none" aria-hidden />
      <div className="relative max-w-[1200px] mx-auto px-5 lg:px-8 py-20 lg:py-28">
        <SectionHead
          eyebrow="Kaip tai veikia"
          index="02"
          title={<>Nuo PDF iki sąmatos — <span className="h-accent">trys žingsniai</span></>}
          sub="Jokio CAD, jokio rankinio matavimo. Tu tik peržiūri ir patvirtini."
        />
        <div className="mt-14 grid md:grid-cols-3 gap-5 lg:gap-6">
          {STEPS.map((s, i) => (
            <Reveal key={s.n} delay={i * 100}
              className="card-lift relative bg-card border border-border rounded-xl p-7 overflow-hidden">
              <div className="ghost-numeral" aria-hidden>{s.n}</div>
              <div className="relative">
                <div className="inline-flex items-center justify-center w-10 h-10 rounded-lg
                                border border-primary/30 bg-primary/[0.10] font-mono text-[14px] text-primary font-semibold">
                  0{s.n}
                </div>
                <div className="mt-6 font-display font-semibold text-[20px] text-foreground tracking-[-0.01em]">{s.t}</div>
                <p className="mt-2.5 text-[14.5px] text-ink-2 leading-[1.55]">{s.d}</p>
              </div>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  );
}

// ─── Ką Pathon skaito (GENERAL trades grid — 6) ──────────────────────

function Trades() {
  return (
    <section id="galimybes" className="border-b border-border bg-card scroll-mt-20">
      <div className="max-w-[1200px] mx-auto px-5 lg:px-8 py-20 lg:py-28">
        <div className="grid lg:grid-cols-[0.95fr_1.05fr] gap-10 lg:gap-16 items-end">
          <SectionHead
            eyebrow="Ką Pathon skaito"
            index="03"
            title={<>Visi statybų tipai — <span className="h-accent">viena sistema</span></>}
            sub="Pathon atpažįsta LT statybų brėžinių lapus ir ištraukia kiekius pagal tarptautines matavimo taisykles — nuo pamatų iki apdailos."
          />
          <Reveal delay={120} className="hidden lg:block font-mono text-[11px] text-muted-foreground leading-relaxed text-right">
            <div>NRM2 · DIN 18363</div>
            <div>Kiekviena eilutė su šaltinio žyma</div>
            <div className="text-primary mt-1">6 trade tipai → 1 sąmata</div>
          </Reveal>
        </div>
        <div className="mt-14 grid sm:grid-cols-2 lg:grid-cols-3 gap-px bg-border border border-border rounded-xl overflow-hidden">
          {TRADES.map((e, i) => (
            <Reveal key={e.t} delay={(i % 3) * 80}
              className="card-lift bg-card p-6 lg:p-7 group relative">
              <span className="absolute top-6 right-6 font-mono text-[10px] text-muted-foreground/60">
                {String(i + 1).padStart(2, '0')}
              </span>
              <div className="flex items-center gap-2.5">
                <span className="w-9 h-9 rounded-lg border border-primary/25 bg-primary/[0.09] flex items-center justify-center shrink-0">
                  <TradeIcon kind={e.icon} />
                </span>
                <span className="font-display font-semibold text-[16px] text-foreground">{e.t}</span>
              </div>
              <p className="mt-3.5 text-[14px] text-ink-2 leading-[1.55]">{e.d}</p>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  );
}

// ─── Kam skirta (3) ──────────────────────────────────────────────────

function Audience() {
  return (
    <section className="border-b border-border scroll-mt-20 relative overflow-hidden">
      <div className="absolute inset-0 blueprint-grid opacity-50 pointer-events-none" aria-hidden />
      <div className="relative max-w-[1200px] mx-auto px-5 lg:px-8 py-20 lg:py-28">
        <SectionHead
          eyebrow="Kam skirta"
          index="04"
          title={<>Vienas įrankis, <span className="h-accent">visai komandai</span></>}
        />
        <div className="mt-14 grid md:grid-cols-3 gap-5 lg:gap-6">
          {AUDIENCES.map((a, i) => (
            <Reveal key={a.t} delay={i * 100}
              className="card-lift bg-card border border-border rounded-xl p-7">
              <div className="font-mono text-[11px] text-primary tracking-[0.14em]">
                {String(i + 1).padStart(2, '0')}
              </div>
              <div className="mt-4 font-display font-semibold text-[20px] text-foreground tracking-[-0.01em]">{a.t}</div>
              <p className="mt-3 text-[14.5px] text-ink-2 leading-[1.55]">{a.d}</p>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  );
}

// ─── Pricing teaser (3 compact cards → /pricing) ─────────────────────

function Pricing() {
  return (
    <section id="kainos" className="border-b border-border bg-card scroll-mt-20">
      <div className="max-w-[1200px] mx-auto px-5 lg:px-8 py-20 lg:py-28">
        <SectionHead
          eyebrow="Kainos"
          index="05"
          title={<>Skaidru, be paslėptų <span className="h-accent">mokesčių</span></>}
          sub="Pradėk nemokamai. Mokėk tik tada, kai matai vertę savo objektuose."
        />
        <div className="mt-14 grid md:grid-cols-3 gap-5 lg:gap-6">
          {TIERS.map((t, i) => (
            <Reveal key={t.name} delay={i * 90}
              className={`card-lift relative rounded-2xl p-7 flex flex-col ${
                t.primary
                  ? 'bg-card border-2 border-primary shadow-[0_18px_50px_-20px_hsl(var(--primary)/0.4)]'
                  : 'bg-card border border-border'
              }`}>
              {t.primary && (
                <span className="absolute -top-3 left-7 font-mono text-[10px] uppercase tracking-[0.12em]
                                 bg-primary text-primary-foreground px-2.5 py-1 rounded-full">
                  Populiariausias
                </span>
              )}
              <div className="font-display font-semibold text-[17px] text-foreground">{t.name}</div>
              <div className="mt-3 flex items-baseline gap-1.5">
                <span className="font-mono font-semibold text-[38px] text-foreground tracking-[-0.02em] tabular">{t.price}</span>
                <span className="text-[13px] text-muted-foreground">{t.unit}</span>
              </div>
              <p className="mt-2 text-[13.5px] text-muted-foreground">{t.desc}</p>
              <ul className="mt-6 space-y-2.5 flex-1">
                {t.feats.map((f) => (
                  <li key={f} className="flex items-start gap-2.5 text-[14px] text-foreground/85">
                    <CheckIcon className="mt-[3px] shrink-0" />
                    <span>{f}</span>
                  </li>
                ))}
              </ul>
              <Link to="/pricing"
                className={`mt-7 justify-center py-2.5 text-[14px] ${t.primary ? 'btn-primary' : 'btn-ghost'}`}>
                {t.cta}
              </Link>
            </Reveal>
          ))}
        </div>
        <Reveal delay={120} as="p" className="mt-6 font-mono text-[12px] text-muted-foreground">
          Kainos be PVM — verslo klientams taikomas atvirkštinis apmokestinimas.
        </Reveal>
      </div>
    </section>
  );
}

// ─── Closing band ────────────────────────────────────────────────────

function Closing() {
  return (
    <section className="border-b border-border relative overflow-hidden">
      <div className="absolute inset-0 blueprint-grid-major opacity-70 pointer-events-none" aria-hidden />
      <div
        className="absolute -bottom-52 -left-40 w-[640px] h-[640px] rounded-full pointer-events-none"
        aria-hidden
        style={{ background: 'radial-gradient(circle, hsl(var(--primary) / 0.14), transparent 62%)' }}
      />
      <div className="relative max-w-[1200px] mx-auto px-5 lg:px-8 py-24 lg:py-32">
        <div className="max-w-[820px]">
          <Reveal><Eyebrow index="06">Kodėl Pathon</Eyebrow></Reveal>
          <Reveal delay={80} as="h2"
            className="mt-6 font-display font-semibold text-foreground tracking-[-0.025em]
                       leading-[1.02] text-[36px] sm:text-[54px]">
            Matavimus atlieka Pathon.{' '}
            <span className="h-accent">Sprendimus priimi tu.</span>
          </Reveal>
          <Reveal delay={150} as="p" className="mt-6 max-w-[600px] text-[17px] sm:text-[18px] text-ink-2 leading-[1.6]">
            Tavo kainos, tavo objektas, tavo pasiūlymas — Pathon tik greitai ir
            tiksliai išmatuoja.
          </Reveal>
          <Reveal delay={210} className="mt-9 flex flex-col sm:flex-row items-stretch sm:items-center gap-3">
            <Link to="/register" className="btn-primary justify-center px-6 py-3 text-[15px]">
              Išbandyti nemokamai
              <ArrowIcon />
            </Link>
            <a href="mailto:solutions@pathon.eu?subject=Pathon%20%E2%80%94%20u%C5%BEklausa"
              className="btn-ghost justify-center px-6 py-3 text-[15px]">
              Susisiekti
            </a>
          </Reveal>
        </div>
      </div>
    </section>
  );
}

// ─── Footer ──────────────────────────────────────────────────────────

function LandingFooter() {
  const cols = [
    {
      h: 'Produktas',
      links: [
        { l: 'Galimybės', href: '#galimybes' },
        { l: 'Kaip veikia', href: '#eiga' },
        { l: 'Kainos', href: '#kainos' },
      ],
    },
    {
      h: 'Paskyra',
      links: [
        { l: 'Prisijungti', to: '/login' },
        { l: 'Registruotis', to: '/register' },
      ],
    },
  ];
  return (
    <footer className="bg-background">
      <div className="max-w-[1200px] mx-auto px-5 lg:px-8 py-14">
        <div className="grid gap-10 lg:grid-cols-[1.6fr_1fr_1fr]">
          <div>
            <div className="flex items-center gap-2.5 text-foreground">
              <PathonMark icon={26} />
              <span className="font-display font-bold tracking-tight text-[18px]">Pathon</span>
            </div>
            <p className="mt-3 text-[13.5px] text-muted-foreground max-w-[280px] leading-relaxed">
              Statybų kiekiai iš brėžinių.
            </p>
            <a href="mailto:solutions@pathon.eu"
              className="mt-4 inline-block font-mono text-[12.5px] text-muted-foreground hover:text-foreground transition-colors">
              solutions@pathon.eu
            </a>
          </div>
          {cols.map((c) => (
            <div key={c.h}>
              <div className="font-mono text-[10px] uppercase tracking-[0.14em] text-muted-foreground mb-4">{c.h}</div>
              <ul className="space-y-2.5 text-[14px]">
                {c.links.map((lk) => (
                  <li key={lk.l}>
                    {lk.href ? (
                      <a href={lk.href} className="text-foreground/75 hover:text-foreground transition-colors">{lk.l}</a>
                    ) : (
                      <Link to={lk.to} className="text-foreground/75 hover:text-foreground transition-colors">{lk.l}</Link>
                    )}
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </div>

        <div className="mt-12 pt-6 border-t border-border flex flex-col sm:flex-row items-start
                        sm:items-center justify-between gap-4 text-[12.5px] text-muted-foreground">
          <div>© 2026 Pathon</div>
          <div className="flex items-center gap-5">
            <Link to="/privacy" className="hover:text-foreground transition-colors">Privatumas</Link>
            <Link to="/cookies" className="hover:text-foreground transition-colors">Slapukai</Link>
            <Link to="/terms" className="hover:text-foreground transition-colors">Sąlygos</Link>
          </div>
        </div>
      </div>
    </footer>
  );
}

// ─── Default export ─────────────────────────────────────────────────

export default function Landing() {
  return (
    <div className="pathon-landing min-h-screen bg-background text-foreground antialiased">
      <LandingNav />
      <Hero />
      <OutcomeStrip />
      <Eiga />
      <Trades />
      <Audience />
      <Pricing />
      <Closing />
      <LandingFooter />
    </div>
  );
}
