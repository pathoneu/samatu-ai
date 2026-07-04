/**
 * Pathon — public landing page (2026-07-04 terracotta rebuild).
 *
 * Shown at "/" for unauthenticated visitors. Authenticated users get
 * redirected to /dashboard via the wrapper in App.jsx.
 *
 * Design language: a precise architectural document that's alive.
 * Clay terracotta accent on warm paper, blueprint hairlines + mono
 * numerals as the estimator-precision signature, editorial asymmetry.
 * Bricolage Grotesque display, Hanken Grotesk body, JetBrains Mono
 * for every quantity/price. Reference bar: Linear / Vercel / Framer.
 *
 * Motion: framer-motion for scroll reveals + count-ups; a CSS-driven
 * SVG "brėžinys → kiekiai" centerpiece in the hero. Robustness: every
 * section renders at final state when reduced-motion is on OR when a
 * reveal never fires — reveals start at a visible fallback and only the
 * *transition* is deferred, never the content.
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

// ─── Marketing constants ─────────────────────────────────────────────

const NAV_LINKS = [
  { href: '#eiga', label: 'Kaip veikia' },
  { href: '#skaito', label: 'Ką skaito' },
  { href: '#kainos', label: 'Kainos' },
];

const HERO_ROOMS = [
  { k: 'Svetainė + virtuvė', p: 28.4 },
  { k: 'Miegamasis', p: 14.2 },
  { k: 'Vaiko kambarys', p: 11.8 },
  { k: 'Vonia', p: 4.6 },
  { k: 'Koridorius', p: 10.9 },
];

const OUTCOMES = [
  { big: '3 val. → kelios min.', small: 'rankinio matavimo nebereikia' },
  { big: 'NRM2 · DIN', small: 'tarptautiniai matavimo standartai' },
  { big: 'LT sąmata · 21% PVM', small: 'paruoštas vietinis formatas' },
  { big: 'Excel + PDF', small: 'eksportas vienu paspaudimu' },
];

const STEPS = [
  {
    n: 1,
    t: 'Įkelk brėžinį',
    d: 'Aukšto planas, pjūvis, sienų išklotinės. PDF, be CAD.',
  },
  {
    n: 2,
    t: 'Pathon ištraukia kiekius',
    d: 'Patalpos, plotai, perimetrai, apdaila. Kiekviena reikšmė su šaltinio žyma.',
  },
  {
    n: 3,
    t: 'Peržiūrėk ir eksportuok',
    d: 'Pakoreguok, įrašyk kainas, eksportuok į Excel ar PDF su PVM.',
  },
];

const EXTRACTS = [
  { t: 'Dažomas plotas', d: 'Sienų ir lubų plotai, minus angos.' },
  { t: 'Angokraščiai', d: 'Langų ir durų angokraščių ilgiai.' },
  { t: 'Grindjuostės', d: 'Perimetras minus durų angos.' },
  { t: 'Plytelės', d: 'Zonos ir plotai iš išklotinių.' },
  { t: 'Gipskartonis', d: 'Lapų kiekis su atsarga.' },
  { t: 'Dažų kiekis', d: 'Litrai pagal plotą ir dengimo normą.' },
];

const AUDIENCES = [
  { t: 'Interjero meistrai', d: 'Apdailos kiekiai iš dizainerio brėžinių — be rankinio skaičiavimo.' },
  { t: 'Rangovai', d: 'Greiti, tikslūs pasiūlymai. Laimėk daugiau objektų.' },
  { t: 'Sąmatininkai', d: 'Rankinį matavimą palik Pathon’ui — tikrink, o ne skaičiuok iš naujo.' },
];

const TIERS = [
  { name: 'Vienkartinis', price: '12 €', unit: '/ projektas', desc: 'Vienas objektas, be prenumeratos.', feats: ['1 projektas', 'Excel + PDF eksportas', 'Visi apdailos kiekiai'], cta: 'Išbandyti', primary: false },
  { name: 'Pro', price: '49 €', unit: '/ mėn.', desc: 'Nuolat dirbančiam sąmatininkui.', feats: ['Neriboti projektai', 'Savo kainynas', 'Korekcijų įrankis', 'Prioritetinis palaikymas'], cta: 'Pradėti', primary: true },
  { name: 'Studio', price: '149 €', unit: '/ mėn.', desc: 'Komandai ir įmonei.', feats: ['Viskas iš Pro', 'Komandos paskyros', 'Bendri kainynai', 'API prieiga (netrukus)'], cta: 'Susisiekti', primary: false },
];

// ─── Hero centerpiece: floor plan SVG (draws + scans + fills) ─────────

function HeroPlanSVG({ play }) {
  return (
    <svg
      viewBox="0 0 418 300"
      className={`hero-plan w-full h-auto ${play ? 'play' : ''}`}
      role="img"
      aria-labelledby="hero-plan-title"
    >
      <title id="hero-plan-title">Pavyzdinis aukšto planas: 3-kambarių butas, 72 m²</title>
      <g transform="translate(24, 18)">
        {/* Room fills (behind strokes) */}
        <g>
          <rect className="room-fill room-1" x="1" y="1" width="132" height="132" fill="hsl(var(--primary))" />
          <rect className="room-fill room-2" x="135" y="1" width="102" height="132" fill="hsl(var(--primary))" />
          <rect className="room-fill room-3" x="239" y="1" width="130" height="132" fill="hsl(var(--primary))" />
          <rect className="room-fill room-4" x="1" y="135" width="176" height="94" fill="hsl(var(--primary))" />
          <rect className="room-fill room-5" x="179" y="135" width="102" height="94" fill="hsl(var(--primary))" />
          <rect className="room-fill room-6" x="283" y="135" width="86" height="94" fill="hsl(var(--primary))" />
        </g>

        {/* Outer + inner walls */}
        <path className="wall" d="M0,0 L0,230 L370,230 L370,0 L0,0" fill="none" stroke="hsl(var(--foreground))" strokeWidth="1.8" />
        <line className="wall" x1="0" y1="134" x2="370" y2="134" stroke="hsl(var(--foreground))" strokeWidth="1.5" />
        <line className="wall" x1="134" y1="0" x2="134" y2="134" stroke="hsl(var(--foreground))" strokeWidth="1.5" />
        <line className="wall" x1="238" y1="0" x2="238" y2="134" stroke="hsl(var(--foreground))" strokeWidth="1.5" />
        <line className="wall" x1="178" y1="134" x2="178" y2="230" stroke="hsl(var(--foreground))" strokeWidth="1.5" />
        <line className="wall" x1="282" y1="134" x2="282" y2="230" stroke="hsl(var(--foreground))" strokeWidth="1.5" />

        {/* Windows */}
        {[[44, 90], [164, 214], [282, 336]].map(([x1, x2], i) => (
          <g key={i} className="opening">
            <line x1={x1} y1="0" x2={x2} y2="0" stroke="hsl(var(--foreground))" strokeWidth="2.8" />
            <line x1={x1} y1="1.4" x2={x2} y2="1.4" stroke="hsl(var(--card))" strokeWidth="1" />
          </g>
        ))}

        {/* Door arcs */}
        <path className="opening" d="M64 134 a14 14 0 0 1 14 -14" fill="none" stroke="hsl(var(--foreground))" strokeWidth="0.8" />
        <path className="opening" d="M196 134 a13 13 0 0 0 -13 -13" fill="none" stroke="hsl(var(--foreground))" strokeWidth="0.8" />
        <path className="opening" d="M304 134 a12 12 0 0 1 12 -12" fill="none" stroke="hsl(var(--foreground))" strokeWidth="0.8" />

        {/* Scan line — terracotta sweep */}
        <g className="scan-line">
          <line x1="0" y1="-6" x2="0" y2="236" stroke="hsl(var(--primary))" strokeWidth="2" />
          <rect x="-14" y="-6" width="14" height="242" fill="hsl(var(--primary) / 0.10)" />
        </g>

        {/* Room labels */}
        <g fontFamily="JetBrains Mono, monospace">
          <g className="room-label room-1">
            <text x="67" y="60" textAnchor="middle" fontSize="8" fill="hsl(var(--foreground))">SVETAINĖ+VIRT.</text>
            <text x="67" y="74" textAnchor="middle" fontSize="7.5" fill="hsl(var(--muted-foreground))">28,4 m²</text>
          </g>
          <g className="room-label room-2">
            <text x="186" y="60" textAnchor="middle" fontSize="8" fill="hsl(var(--foreground))">MIEGAMASIS</text>
            <text x="186" y="74" textAnchor="middle" fontSize="7.5" fill="hsl(var(--muted-foreground))">14,2 m²</text>
          </g>
          <g className="room-label room-3">
            <text x="304" y="60" textAnchor="middle" fontSize="8" fill="hsl(var(--foreground))">VAIKO K.</text>
            <text x="304" y="74" textAnchor="middle" fontSize="7.5" fill="hsl(var(--muted-foreground))">11,8 m²</text>
          </g>
          <g className="room-label room-4">
            <text x="89" y="188" textAnchor="middle" fontSize="8" fill="hsl(var(--foreground))">KORIDORIUS</text>
            <text x="89" y="202" textAnchor="middle" fontSize="7.5" fill="hsl(var(--muted-foreground))">10,9 m²</text>
          </g>
          <g className="room-label room-5">
            <text x="230" y="188" textAnchor="middle" fontSize="8" fill="hsl(var(--foreground))">VONIA</text>
            <text x="230" y="202" textAnchor="middle" fontSize="7.5" fill="hsl(var(--muted-foreground))">4,6 m²</text>
          </g>
          <g className="room-label room-6">
            <text x="326" y="188" textAnchor="middle" fontSize="8" fill="hsl(var(--foreground))">WC</text>
            <text x="326" y="202" textAnchor="middle" fontSize="7.5" fill="hsl(var(--muted-foreground))">2,1 m²</text>
          </g>
        </g>

        {/* Dimension line (top) — coordinate-tick signature */}
        <g className="meta-element" fontFamily="JetBrains Mono, monospace">
          <line x1="0" y1="-12" x2="370" y2="-12" stroke="hsl(var(--muted-foreground))" strokeWidth="0.5" />
          <line x1="0" y1="-15" x2="0" y2="-9" stroke="hsl(var(--muted-foreground))" strokeWidth="0.6" />
          <line x1="370" y1="-15" x2="370" y2="-9" stroke="hsl(var(--muted-foreground))" strokeWidth="0.6" />
          <text x="185" y="-16" textAnchor="middle" fontSize="6.5" fill="hsl(var(--muted-foreground))">8 240</text>
        </g>

        {/* Title block */}
        <g className="meta-element" transform="translate(230, 250)" fontFamily="JetBrains Mono, monospace">
          <rect x="0" y="0" width="140" height="30" fill="none" stroke="hsl(var(--border-strong))" strokeWidth="0.7" />
          <line x1="70" y1="0" x2="70" y2="30" stroke="hsl(var(--border-strong))" strokeWidth="0.6" />
          <text x="6" y="12" fontSize="7" fill="hsl(var(--foreground))">M 1:50</text>
          <text x="76" y="12" fontSize="7" fill="hsl(var(--foreground))">72,0 m²</text>
          <text x="6" y="24" fontSize="7" fill="hsl(var(--muted-foreground))">SA-01</text>
          <text x="76" y="24" fontSize="7" fill="hsl(var(--muted-foreground))">3-kamb butas</text>
        </g>
      </g>
    </svg>
  );
}

// ─── Hero product frame — plan (left) + extracted quantities (right) ──

function HeroProductFrame() {
  const reduce = useReducedMotion();
  const ref = useRef(null);
  const inView = useInView(ref, { once: false, amount: 0.4 });
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
      <div className="flex items-center gap-2 px-4 h-9 border-b border-border bg-muted/60">
        <span className="w-2.5 h-2.5 rounded-full bg-border-strong" />
        <span className="w-2.5 h-2.5 rounded-full bg-border-strong" />
        <span className="w-2.5 h-2.5 rounded-full bg-border-strong" />
        <span className="ml-3 font-mono text-[11px] text-muted-foreground truncate">
          Aukšto_planas.pdf — 3-kamb butas
        </span>
        <span className="ml-auto font-mono text-[10px] text-primary hidden sm:inline">● ištraukta</span>
      </div>
      <div className="grid sm:grid-cols-[1.12fr_1fr]" key={key}>
        {/* plan */}
        <div className="blueprint-grid p-4 border-b sm:border-b-0 sm:border-r border-border bg-card">
          <HeroPlanSVG play={play} />
        </div>
        {/* extracted quantities */}
        <div className="p-4 sm:p-5">
          <div className="font-mono text-[10px] uppercase tracking-[0.14em] text-muted-foreground mb-3">
            Ištraukti kiekiai
          </div>
          <div className={`qty-table ${play ? 'play' : ''}`}>
            {HERO_ROOMS.map((r, i) => (
              <div
                key={r.k}
                className="qty-row flex items-baseline justify-between py-[7px] border-b border-border/60 text-[12.5px]"
                style={play ? { animationDelay: `${900 + i * 110}ms` } : undefined}
              >
                <span className="text-foreground/85 truncate pr-2">{r.k}</span>
                <span className="font-mono tabular text-foreground whitespace-nowrap">{fmt(r.p, 1)} m²</span>
              </div>
            ))}
            <div className="flex items-baseline justify-between pt-3 mt-1">
              <span className="text-[12px] font-medium text-foreground">Viso sienų</span>
              <span className="font-mono tabular text-[15px] font-semibold text-primary">
                <CountUp to={213} decimals={1} suffix=" m²" duration={1.2} />
              </span>
            </div>
          </div>
          <div className="mt-4 pt-3 border-t border-border grid grid-cols-2 gap-y-2 font-mono text-[11px]">
            <div className="text-muted-foreground">Grindys</div>
            <div className="tabular text-right text-foreground">72,0 m²</div>
            <div className="text-muted-foreground">Grindjuostės</div>
            <div className="tabular text-right text-foreground">73 m</div>
            <div className="text-foreground font-medium pt-2 border-t border-border/60">Sąmata su PVM</div>
            <div className="tabular text-right font-semibold text-foreground pt-2 border-t border-border/60">
              <CountUp to={8017.46} decimals={2} suffix=" €" duration={1.6} />
            </div>
          </div>
        </div>
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
      {/* layered blueprint texture + warm wash */}
      <div className="absolute inset-0 blueprint-grid-major opacity-70 pointer-events-none" aria-hidden />
      <div
        className="absolute -top-40 -right-40 w-[520px] h-[520px] rounded-full pointer-events-none"
        aria-hidden
        style={{
          background:
            'radial-gradient(circle, hsl(var(--primary) / 0.10), transparent 62%)',
        }}
      />
      <div className="relative max-w-[1200px] mx-auto px-5 lg:px-8 pt-14 pb-20 lg:pt-24 lg:pb-28">
        <div className="grid lg:grid-cols-[1.05fr_1fr] gap-12 lg:gap-16 items-center">
          <div>
            <Reveal>
              <Eyebrow index="01 / HERO">AI Sąmatininkas</Eyebrow>
            </Reveal>
            <Reveal delay={70} as="h1"
              className="mt-6 font-display font-bold text-foreground tracking-[-0.03em]
                         leading-[0.98] text-[46px] sm:text-[62px] lg:text-[76px]">
              Iš brėžinio —{' '}
              <br className="hidden sm:block" />
              <span className="h-accent">į tikslią sąmatą.</span>
            </Reveal>
            <Reveal delay={140} as="p"
              className="mt-7 max-w-[540px] text-[17px] sm:text-[18.5px] text-ink-2 leading-[1.6]">
              Pathon išmatuoja patalpas, plotus ir apdailos kiekius tiesiai iš
              PDF brėžinio. Tu tik peržiūri, pakoreguoji ir eksportuoji — per
              kelias minutes, ne per kelias dienas.
            </Reveal>
            <Reveal delay={210} className="mt-9 flex flex-col sm:flex-row items-stretch sm:items-center gap-3">
              <Link to="/register" className="btn-primary justify-center px-5 py-3 text-[15px]">
                Išbandyti nemokamai
                <ArrowIcon />
              </Link>
              <a href="#eiga" className="btn-ghost justify-center px-5 py-3 text-[15px]">
                Žiūrėti, kaip veikia
              </a>
            </Reveal>
            <Reveal delay={280} as="p" className="mt-6 font-mono text-[12px] text-muted-foreground">
              Pirmas projektas — nemokamai. Be įsipareigojimų.
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
              <div className="font-mono font-medium text-[17px] lg:text-[19px] text-foreground tracking-[-0.01em]">
                {o.big}
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
    <div className={`max-w-[680px] ${alignCls} ${className}`}>
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
      <div className="absolute inset-0 blueprint-grid opacity-40 pointer-events-none" aria-hidden />
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
                                border border-primary/25 bg-primary/[0.08] font-mono text-[14px] text-primary font-semibold">
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

// ─── Ką skaito (6-grid) ──────────────────────────────────────────────

function Extracts() {
  return (
    <section id="skaito" className="border-b border-border bg-card scroll-mt-20">
      <div className="max-w-[1200px] mx-auto px-5 lg:px-8 py-20 lg:py-28">
        <div className="grid lg:grid-cols-[0.9fr_1.1fr] gap-10 lg:gap-16 items-end">
          <SectionHead
            eyebrow="Ką Pathon skaito"
            index="03"
            title={<>Apdailos kiekiai, <span className="h-accent">skaitomi</span> už tave</>}
            sub="Pathon atpažįsta LT statybų brėžinių lapus ir ištraukia kiekius pagal tarptautines matavimo taisykles."
          />
          <Reveal delay={120} className="hidden lg:block font-mono text-[11px] text-muted-foreground leading-relaxed text-right">
            <div>NRM2 · DIN 18363</div>
            <div>Kiekviena eilutė su šaltinio žyma</div>
            <div className="text-primary mt-1">6 kategorijos → 1 sąmata</div>
          </Reveal>
        </div>
        <div className="mt-14 grid sm:grid-cols-2 lg:grid-cols-3 gap-px bg-border border border-border rounded-xl overflow-hidden">
          {EXTRACTS.map((e, i) => (
            <Reveal key={e.t} delay={(i % 3) * 80}
              className="card-lift bg-card p-6 lg:p-7 group relative">
              <span className="absolute top-6 right-6 font-mono text-[10px] text-muted-foreground/70">
                {String(i + 1).padStart(2, '0')}
              </span>
              <div className="flex items-center gap-2.5">
                <span className="w-6 h-6 rounded-md border border-primary/25 bg-primary/[0.08] flex items-center justify-center shrink-0">
                  <svg width="13" height="13" viewBox="0 0 16 16" fill="none" stroke="hsl(var(--primary))" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M13 4L6 12l-3.5-3.5" />
                  </svg>
                </span>
                <span className="font-display font-semibold text-[16px] text-foreground">{e.t}</span>
              </div>
              <p className="mt-3 text-[14px] text-ink-2 leading-[1.55]">{e.d}</p>
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
      <div className="absolute inset-0 blueprint-grid opacity-40 pointer-events-none" aria-hidden />
      <div className="relative max-w-[1200px] mx-auto px-5 lg:px-8 py-20 lg:py-28">
        <SectionHead
          eyebrow="Kam skirta"
          index="04"
          title={<>Vienas įrankis, <span className="h-accent">trys profesijos</span></>}
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
                  ? 'bg-card border-2 border-primary shadow-[0_18px_50px_-20px_hsl(var(--terracotta-deep)/0.45)]'
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
                    <svg width="15" height="15" viewBox="0 0 16 16" fill="none" stroke="hsl(var(--primary))" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" className="mt-[3px] shrink-0">
                      <path d="M13 4L6 12l-3.5-3.5" />
                    </svg>
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
      <div className="absolute inset-0 blueprint-grid-major opacity-60 pointer-events-none" aria-hidden />
      <div
        className="absolute -bottom-40 -left-40 w-[560px] h-[560px] rounded-full pointer-events-none"
        aria-hidden
        style={{ background: 'radial-gradient(circle, hsl(var(--primary) / 0.10), transparent 62%)' }}
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
          <Reveal delay={150} as="p" className="mt-6 max-w-[560px] text-[17px] sm:text-[18px] text-ink-2 leading-[1.6]">
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
        { l: 'Kaip veikia', href: '#eiga' },
        { l: 'Ką skaito', href: '#skaito' },
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
              Statybų sąmatos iš PDF brėžinių.
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
      <Extracts />
      <Audience />
      <Pricing />
      <Closing />
      <LandingFooter />
    </div>
  );
}
