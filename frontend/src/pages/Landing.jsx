/**
 * Pathon — public landing page (2026-07-03 brand redesign).
 *
 * Shown at "/" for unauthenticated visitors. Authenticated users get
 * redirected to /dashboard via the wrapper in App.jsx.
 *
 * Design language: confident modern construction-tech. Restraint of
 * Linear / Vercel / Stripe with a construction-document edge — warm
 * paper, graphite ink, one indigo accent used sparingly, blueprint
 * hairlines + mono numerals as the "precision" signature. Space Grotesk
 * for display headings, Inter for body, JetBrains Mono for numbers.
 */
import React, { useEffect, useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { PathonMark } from '@/components/layout/Logo';

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
      { rootMargin: opts.rootMargin || '-8% 0px -8% 0px', threshold: opts.threshold ?? 0.15 }
    );
    io.observe(el);
    return () => io.disconnect();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  return [ref, inView];
}

function Reveal({ children, delay = 0, className = '', as: Tag = 'div' }) {
  const [ref, inView] = useInView();
  return (
    <Tag
      ref={ref}
      className={`reveal ${inView ? 'in' : ''} ${className}`}
      style={{ transitionDelay: `${delay}ms` }}
    >
      {children}
    </Tag>
  );
}

// ─── Number formatting (LT convention: comma decimals) ──────────────

const fmt = (n, d = 1) =>
  n.toLocaleString('lt-LT', { minimumFractionDigits: d, maximumFractionDigits: d });
const fmt2 = (n) => n.toLocaleString('lt-LT', { minimumFractionDigits: 2, maximumFractionDigits: 2 });

// ─── Small primitives ────────────────────────────────────────────────

const Eyebrow = ({ children }) => (
  <div className="font-mono text-[11px] tracking-[0.14em] uppercase text-primary/80">
    {children}
  </div>
);

const Pill = ({ children }) => <span className="h-pill">{children}</span>;

// ─── Marketing constants ─────────────────────────────────────────────

const NAV_LINKS = [
  { href: '#eiga', label: 'Kaip veikia' },
  { href: '#kainos', label: 'Kainos' },
];

const HERO_ROOMS = [
  { k: 'Svetainė + virtuvė', p: 28.4, sienos: 58.6 },
  { k: 'Miegamasis',         p: 14.2, sienos: 40.5 },
  { k: 'Vaiko kambarys',     p: 11.8, sienos: 36.6 },
  { k: 'Vonia',              p:  4.6, sienos: 23.3 },
  { k: 'Koridorius',         p: 10.9, sienos: 38.2 },
];

const OUTCOMES = [
  { big: 'Per kelias min.', small: 'vietoj 3 val. rankinio matavimo' },
  { big: '72,0 m² · 213 m', small: 'plotai ir ilgiai — mono tikslumu' },
  { big: '8 017,46 €', small: 'paruošta sąmata su tavo kainynu' },
  { big: '21% PVM', small: 'LT sąmatos formatas, Excel + PDF' },
];

const STEPS = [
  { n: 1, t: 'Įkeli PDF', d: 'Aukšto planus, pjūvius, sienų išklotines, eksplikacijas. CAD\'o nereikia — užtenka PDF.' },
  { n: 2, t: 'AI ištraukia kiekius', d: 'Pathon randa patalpas, plotus, perimetrus, sienų ir lubų plotus, grindjuosčių ilgius. Kiekviena eilutė su šaltinio žyma.' },
  { n: 3, t: 'Pataisai ir eksportuoji', d: 'Suvedi savo kainyną, patikslini eilutes, eksportuoji į Excel arba PDF su 21% PVM.' },
];

const EXTRACTS = [
  { t: 'Dažomas plotas', d: 'Sienų ir lubų plotai atskirai — perimetras × aukštis, minus angos.' },
  { t: 'Angokraščiai', d: 'Langų ir durų angokraščių ilgiai iš angų perimetrų.' },
  { t: 'Grindjuostės', d: 'Ilgis iš patalpos perimetro, minus durų angos, su atsarga.' },
  { t: 'Plytelės', d: 'Plytelių zonos ir plotai iš sienų išklotinių.' },
  { t: 'Gipskartonis', d: 'Lapų kiekis iš sienų ploto, su 10% atsarga.' },
  { t: 'Dažų kiekis', d: 'Litrai pagal plotą, sluoksnius ir dengimo normą.' },
];

const TIERS = [
  { name: 'Vienkartinis', price: '12 €', unit: '/ projektas', desc: 'Vienas objektas, be prenumeratos.', feats: ['1 projektas', 'Excel + PDF eksportas', 'Visi apdailos kiekiai'], cta: 'Išbandyti', primary: false },
  { name: 'Pro', price: '49 €', unit: '/ mėn.', desc: 'Nuolat dirbančiam sąmatininkui.', feats: ['Neriboti projektai', 'Savo kainynas', 'Korekcijų įrankis', 'Prioritetinis palaikymas'], cta: 'Pradėti', primary: true },
  { name: 'Studio', price: '149 €', unit: '/ mėn.', desc: 'Komandai ir įmonei.', feats: ['Viskas iš Pro', 'Komandos paskyros', 'Bendri kainynai', 'API prieiga (netrukus)'], cta: 'Susisiekti', primary: false },
];

// ─── Hero product visual — floor plan → extracted quantities ─────────

function HeroPlanSVG() {
  const [ref, inView] = useInView({ threshold: 0.15 });
  return (
    <svg
      ref={ref}
      viewBox="0 0 460 340"
      className={`hero-plan w-full h-auto ${inView ? 'in' : ''}`}
      role="img"
      aria-labelledby="hero-plan-title"
    >
      <title id="hero-plan-title">Pavyzdinis aukšto planas: 3-kambarių butas, 72 m²</title>
      <g transform="translate(24, 20)">
        {/* Outer walls */}
        <path className="wall" d="M0,0 L0,230 L370,230 L370,0 L0,0"
          fill="none" stroke="hsl(var(--foreground))" strokeWidth="1.6" />
        <line className="wall" x1="0" y1="134" x2="370" y2="134"
          stroke="hsl(var(--foreground))" strokeWidth="1.4" />
        <line className="wall" x1="134" y1="0" x2="134" y2="134"
          stroke="hsl(var(--foreground))" strokeWidth="1.4" />
        <line className="wall" x1="238" y1="0" x2="238" y2="134"
          stroke="hsl(var(--foreground))" strokeWidth="1.4" />
        <line className="wall" x1="178" y1="134" x2="178" y2="230"
          stroke="hsl(var(--foreground))" strokeWidth="1.4" />
        <line className="wall" x1="282" y1="134" x2="282" y2="230"
          stroke="hsl(var(--foreground))" strokeWidth="1.4" />

        {/* Windows */}
        {[[44, 90], [164, 214], [282, 336]].map(([x1, x2], i) => (
          <g key={i} className="opening">
            <line x1={x1} y1="0" x2={x2} y2="0" stroke="hsl(var(--foreground))" strokeWidth="2.6" />
            <line x1={x1} y1="1.3" x2={x2} y2="1.3" stroke="hsl(var(--card))" strokeWidth="0.9" />
          </g>
        ))}

        {/* Door arcs */}
        <path className="opening" d="M64 134 a14 14 0 0 1 14 -14" fill="none" stroke="hsl(var(--foreground))" strokeWidth="0.7" />
        <path className="opening" d="M196 134 a13 13 0 0 0 -13 -13" fill="none" stroke="hsl(var(--foreground))" strokeWidth="0.7" />
        <path className="opening" d="M304 134 a12 12 0 0 1 12 -12" fill="none" stroke="hsl(var(--foreground))" strokeWidth="0.7" />

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

        {/* Scale bar */}
        <g className="meta-element" transform="translate(0, 258)">
          <line x1="0" y1="0" x2="96" y2="0" stroke="hsl(var(--muted-foreground))" strokeWidth="1" />
          {[0, 24, 48, 72, 96].map((x, i) => (
            <line key={i} x1={x} y1={i === 0 || i === 4 ? -4 : -3} x2={x} y2={i === 0 || i === 4 ? 4 : 3}
              stroke="hsl(var(--muted-foreground))" strokeWidth="1" />
          ))}
          <text x="0" y="15" fontSize="7.5" fontFamily="JetBrains Mono, monospace" fill="hsl(var(--muted-foreground))">0</text>
          <text x="96" y="15" fontSize="7.5" fontFamily="JetBrains Mono, monospace" fill="hsl(var(--muted-foreground))" textAnchor="end">10 m</text>
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

function HeroProductFrame() {
  return (
    <div className="product-frame overflow-hidden">
      {/* window chrome bar */}
      <div className="flex items-center gap-2 px-4 h-9 border-b border-border bg-muted/50">
        <span className="w-2.5 h-2.5 rounded-full bg-border-strong" />
        <span className="w-2.5 h-2.5 rounded-full bg-border-strong" />
        <span className="w-2.5 h-2.5 rounded-full bg-border-strong" />
        <span className="ml-3 font-mono text-[11px] text-muted-foreground truncate">
          Aukšto_planas.pdf — 3-kamb butas
        </span>
        <span className="ml-auto font-mono text-[10px] text-primary/80 hidden sm:inline">● ištraukta</span>
      </div>
      <div className="grid sm:grid-cols-[1.15fr_1fr]">
        {/* plan */}
        <div className="blueprint-grid p-4 border-b sm:border-b-0 sm:border-r border-border">
          <HeroPlanSVG />
        </div>
        {/* extracted quantities */}
        <div className="p-4">
          <div className="font-mono text-[10px] uppercase tracking-[0.1em] text-muted-foreground mb-3">
            Ištraukti kiekiai
          </div>
          <div className="space-y-0">
            {HERO_ROOMS.map((r, i) => (
              <div key={r.k}
                className="flex items-baseline justify-between py-[7px] border-b border-border/60 text-[12.5px]"
                style={{ opacity: 0, animation: `fadeRow 500ms cubic-bezier(.16,1,.3,1) ${900 + i * 90}ms forwards` }}>
                <span className="text-foreground/85 truncate pr-2">{r.k}</span>
                <span className="font-mono tabular text-foreground whitespace-nowrap">{fmt(r.p, 1)} m²</span>
              </div>
            ))}
            <div className="flex items-baseline justify-between pt-3 mt-1">
              <span className="text-[12px] font-medium text-foreground">Viso sienų</span>
              <span className="font-mono tabular text-[15px] font-semibold text-primary">213,0 m²</span>
            </div>
          </div>
          <div className="mt-4 pt-3 border-t border-border grid grid-cols-2 gap-2 font-mono text-[11px]">
            <div className="text-muted-foreground">Grindys</div>
            <div className="tabular text-right text-foreground">72,0 m²</div>
            <div className="text-muted-foreground">Grindjuostės</div>
            <div className="tabular text-right text-foreground">73 m</div>
            <div className="text-foreground font-medium pt-1 border-t border-border/60">Sąmata su PVM</div>
            <div className="tabular text-right font-semibold text-foreground pt-1 border-t border-border/60">8 017,46 €</div>
          </div>
        </div>
      </div>
    </div>
  );
}

// ─── Sticky top nav ──────────────────────────────────────────────────

function LandingNav() {
  const [open, setOpen] = useState(false);
  return (
    <header className="sticky top-0 z-40 border-b border-border bg-background/80 backdrop-blur-md
                       supports-[backdrop-filter]:bg-background/70">
      <div className="max-w-[1180px] mx-auto px-5 lg:px-8 h-16 flex items-center justify-between">
        <Link to="/" className="flex items-center gap-2.5 text-foreground">
          <PathonMark icon={26} />
          <span className="font-display font-semibold tracking-tight text-[18px]">Pathon</span>
        </Link>

        <nav className="hidden md:flex items-center gap-8 text-[14px] text-muted-foreground">
          {NAV_LINKS.map((l) => (
            <a key={l.href} href={l.href} className="hover:text-foreground transition-colors">{l.label}</a>
          ))}
          <Link to="/login" className="hover:text-foreground transition-colors">Prisijungti</Link>
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
        <div className="md:hidden border-t border-border bg-background/95 backdrop-blur-md">
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
  return (
    <section className="relative border-b border-border overflow-hidden">
      <div className="absolute inset-0 blueprint-grid opacity-60 pointer-events-none" aria-hidden />
      <div className="relative max-w-[1180px] mx-auto px-5 lg:px-8 pt-16 pb-20 lg:pt-24 lg:pb-28">
        <div className="grid lg:grid-cols-2 gap-12 lg:gap-16 items-center">
          <div>
            <Reveal>
              <Eyebrow>Statybų sąmatos iš PDF</Eyebrow>
            </Reveal>
            <Reveal delay={60} as="h1"
              className="mt-5 font-display font-semibold text-foreground tracking-[-0.02em]
                         leading-[1.03] text-[40px] sm:text-[54px] lg:text-[64px]">
              Pasiūlymą turi iki <Pill>vakaro</Pill>.
              <br className="hidden sm:block" />
              <span className="text-muted-foreground"> Ne iki ketvirtadienio.</span>
            </Reveal>
            <Reveal delay={120} as="p"
              className="mt-6 max-w-[520px] text-[17px] sm:text-[18px] text-foreground/75 leading-[1.6]">
              Įkelk statybų projekto PDF — Pathon per kelias minutes ištraukia
              patalpas, plotus ir paruošia apdailos sąmatą pagal tavo kainyną.
            </Reveal>
            <Reveal delay={180} className="mt-8 flex flex-col sm:flex-row items-stretch sm:items-center gap-3">
              <Link to="/register" className="btn-primary justify-center px-5 py-3 text-[15px]">
                Išbandyti nemokamai
                <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M3 8h10M9 4l4 4-4 4" />
                </svg>
              </Link>
              <a href="#eiga" className="btn-ghost justify-center px-5 py-3 text-[15px]">
                Žiūrėti kaip veikia
              </a>
            </Reveal>
            <Reveal delay={240} as="p" className="mt-5 font-mono text-[12px] text-muted-foreground">
              Pirmas projektas — be įsipareigojimų · CAD'o nereikia
            </Reveal>
          </div>

          <Reveal delay={200} className="lg:pl-4">
            <HeroProductFrame />
          </Reveal>
        </div>
      </div>
    </section>
  );
}

// ─── Outcome strip ───────────────────────────────────────────────────

function OutcomeStrip() {
  return (
    <section className="border-b border-border bg-card">
      <div className="max-w-[1180px] mx-auto px-5 lg:px-8">
        <div className="grid grid-cols-2 lg:grid-cols-4 divide-y divide-x divide-border
                        [&>*]:border-border">
          {OUTCOMES.map((o, i) => (
            <Reveal key={i} delay={i * 70} className="p-6 lg:p-8">
              <div className="font-display font-semibold text-[22px] lg:text-[26px] text-foreground tracking-[-0.01em] tabular">
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

function SectionHead({ eyebrow, title, sub, id }) {
  return (
    <div className="max-w-[640px]">
      <Reveal><Eyebrow>{eyebrow}</Eyebrow></Reveal>
      <Reveal delay={60} as="h2"
        className="mt-4 font-display font-semibold text-foreground tracking-[-0.015em]
                   leading-[1.08] text-[30px] sm:text-[40px]">
        {title}
      </Reveal>
      {sub && (
        <Reveal delay={120} as="p" className="mt-4 text-[16px] sm:text-[17px] text-foreground/75 leading-[1.6]">
          {sub}
        </Reveal>
      )}
    </div>
  );
}

// ─── Kaip tai veikia (steps) ─────────────────────────────────────────

function Eiga() {
  return (
    <section id="eiga" className="border-b border-border scroll-mt-20">
      <div className="max-w-[1180px] mx-auto px-5 lg:px-8 py-20 lg:py-28">
        <SectionHead
          eyebrow="Kaip tai veikia"
          title={<>Nuo PDF iki sąmatos — <Pill>trys žingsniai</Pill></>}
          sub="Jokio CAD'o, jokio rankinio matavimo. Tu tik peržiūri ir patvirtini."
        />
        <div className="mt-14 grid md:grid-cols-3 gap-5 lg:gap-6">
          {STEPS.map((s, i) => (
            <Reveal key={s.n} delay={i * 90}
              className="relative bg-card border border-border rounded-lg p-7 overflow-hidden">
              <div className="ghost-numeral" aria-hidden>{s.n}</div>
              <div className="relative">
                <div className="inline-flex items-center justify-center w-9 h-9 rounded-md
                                border border-primary/25 bg-primary/[0.07] font-mono text-[13px] text-primary font-medium">
                  0{s.n}
                </div>
                <div className="mt-5 font-display font-semibold text-[19px] text-foreground">{s.t}</div>
                <p className="mt-2 text-[14.5px] text-foreground/70 leading-[1.55]">{s.d}</p>
              </div>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  );
}

// ─── Ką skaito (value props grid) ────────────────────────────────────

function Extracts() {
  return (
    <section className="border-b border-border bg-card scroll-mt-20">
      <div className="max-w-[1180px] mx-auto px-5 lg:px-8 py-20 lg:py-28">
        <SectionHead
          eyebrow="Ką ištraukia"
          title={<>Apdailos kiekiai, kuriuos <Pill>skaito</Pill> už tave</>}
          sub="Pathon atpažįsta LT statybų brėžinių lapus ir ištraukia kiekius pagal tarptautines matavimo taisykles (NRM2, DIN)."
        />
        <div className="mt-14 grid sm:grid-cols-2 lg:grid-cols-3 gap-px bg-border border border-border rounded-lg overflow-hidden">
          {EXTRACTS.map((e, i) => (
            <Reveal key={e.t} delay={(i % 3) * 70} className="bg-card p-6 lg:p-7 group">
              <div className="flex items-center gap-2.5">
                <span className="w-6 h-6 rounded-md border border-primary/25 bg-primary/[0.07] flex items-center justify-center shrink-0">
                  <svg width="13" height="13" viewBox="0 0 16 16" fill="none" stroke="hsl(var(--primary))" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M13 4L6 12l-3.5-3.5" />
                  </svg>
                </span>
                <span className="font-display font-medium text-[16px] text-foreground">{e.t}</span>
              </div>
              <p className="mt-3 text-[14px] text-foreground/65 leading-[1.55]">{e.d}</p>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  );
}

// ─── Pricing teaser ──────────────────────────────────────────────────

function Pricing() {
  return (
    <section id="kainos" className="border-b border-border scroll-mt-20">
      <div className="max-w-[1180px] mx-auto px-5 lg:px-8 py-20 lg:py-28">
        <SectionHead
          eyebrow="Kainos"
          title={<>Skaidru, be paslėptų <Pill>mokesčių</Pill></>}
          sub="Pradėk nemokamai. Mokėk tik tada, kai matai vertę savo objektuose."
        />
        <div className="mt-14 grid md:grid-cols-3 gap-5 lg:gap-6">
          {TIERS.map((t, i) => (
            <Reveal key={t.name} delay={i * 80}
              className={`relative rounded-xl p-7 flex flex-col ${
                t.primary
                  ? 'bg-card border-2 border-primary shadow-[0_12px_40px_-16px_hsl(var(--primary)/0.4)]'
                  : 'bg-card border border-border'
              }`}>
              {t.primary && (
                <span className="absolute -top-3 left-7 font-mono text-[10px] uppercase tracking-[0.1em]
                                 bg-primary text-primary-foreground px-2.5 py-1 rounded-full">
                  Populiariausias
                </span>
              )}
              <div className="font-display font-semibold text-[17px] text-foreground">{t.name}</div>
              <div className="mt-3 flex items-baseline gap-1.5">
                <span className="font-display font-semibold text-[36px] text-foreground tracking-[-0.02em] tabular">{t.price}</span>
                <span className="text-[13px] text-muted-foreground">{t.unit}</span>
              </div>
              <p className="mt-2 text-[13.5px] text-muted-foreground">{t.desc}</p>
              <ul className="mt-6 space-y-2.5 flex-1">
                {t.feats.map((f) => (
                  <li key={f} className="flex items-start gap-2.5 text-[14px] text-foreground/80">
                    <svg width="15" height="15" viewBox="0 0 16 16" fill="none" stroke="hsl(var(--primary))" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" className="mt-[3px] shrink-0">
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
          Kainos be PVM. Renovacijos darbams — atvirkštinis PVM (reverse-charge).
        </Reveal>
      </div>
    </section>
  );
}

// ─── Outcome quote ───────────────────────────────────────────────────

function QuoteCloser() {
  return (
    <section className="border-b border-border bg-card">
      <div className="max-w-[1180px] mx-auto px-5 lg:px-8 py-24 lg:py-32">
        <div className="max-w-[760px] mx-auto text-center">
          <Reveal>
            <span className="font-mono text-[11px] uppercase tracking-[0.14em] text-primary/80">Kodėl Pathon</span>
          </Reveal>
          <Reveal delay={80} as="blockquote"
            className="mt-7 text-[24px] sm:text-[30px] leading-[1.4] text-foreground italic"
            style={{ fontFamily: '"Instrument Serif", Georgia, serif' }}>
            „Iš statybų projekto, kuris atkeliauja PDF'u, sąmatininkas pirmas
            tris valandas tik matuoja patalpas, perimetrus ir sienų plotus.
            Tas valandas atliekam už tave. Tavo kainynas, tavo objektas, tavo
            pasiūlymas — lieka tau."
          </Reveal>
          <Reveal delay={160} className="mt-10 flex flex-col sm:flex-row items-center justify-center gap-3">
            <Link to="/register" className="btn-primary justify-center px-6 py-3 text-[15px]">
              Išbandyti nemokamai
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" strokeLinejoin="round">
                <path d="M3 8h10M9 4l4 4-4 4" />
              </svg>
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
    { h: 'Produktas', links: [
      { l: 'Kaip veikia', to: '#eiga', anchor: true },
      { l: 'Ką ištraukia', to: '#kainos', anchor: false, href: '#kainos' },
    ] },
    { h: 'Kainos', links: [
      { l: 'Planai', to: '/pricing' },
      { l: 'Vienkartinis', to: '/pricing' },
    ] },
    { h: 'Paskyra', links: [
      { l: 'Prisijungti', to: '/login' },
      { l: 'Registruotis', to: '/register' },
    ] },
  ];
  return (
    <footer className="bg-background">
      <div className="max-w-[1180px] mx-auto px-5 lg:px-8 py-14">
        <div className="grid gap-10 lg:grid-cols-[1.5fr_1fr_1fr_1fr]">
          <div>
            <div className="flex items-center gap-2.5 text-foreground">
              <PathonMark icon={24} />
              <span className="font-display font-semibold tracking-tight text-[17px]">Pathon</span>
            </div>
            <p className="mt-3 text-[13.5px] text-muted-foreground max-w-[260px] leading-relaxed">
              Statybų sąmatos iš PDF brėžinių. Patalpos, plotai ir apdailos
              kiekiai per kelias minutes.
            </p>
            <a href="mailto:solutions@pathon.eu"
              className="mt-4 inline-block font-mono text-[12.5px] text-muted-foreground hover:text-foreground transition-colors">
              solutions@pathon.eu
            </a>
          </div>
          {cols.map((c) => (
            <div key={c.h}>
              <div className="font-mono text-[10px] uppercase tracking-[0.12em] text-muted-foreground mb-4">{c.h}</div>
              <ul className="space-y-2.5 text-[14px]">
                {c.links.map((lk) => (
                  <li key={lk.l}>
                    {lk.to?.startsWith('#') || lk.anchor ? (
                      <a href={lk.href || lk.to} className="text-foreground/75 hover:text-foreground transition-colors">{lk.l}</a>
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
          <div>© 2026 Pathon · Produktas dar testavimo stadijoje</div>
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
    <div className="min-h-screen bg-background text-foreground antialiased">
      <LandingNav />
      <Hero />
      <OutcomeStrip />
      <Eiga />
      <Extracts />
      <Pricing />
      <QuoteCloser />
      <LandingFooter />
    </div>
  );
}
