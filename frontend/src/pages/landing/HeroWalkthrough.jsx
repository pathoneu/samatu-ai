/**
 * HeroWalkthrough — the DEFAULT landing hero (founder-approved 2026-07-11),
 * restyled to the "Nordic Slate" system (Stitch export: parchment ground,
 * slate ink, one muted evergreen accent, hairline structure, sharp 2px).
 * Old measuring-instrument hero remains via ?hero=v1.
 *
 * Pattern: 21st.dev hero-section-5 — left-aligned headline + CTAs over a
 * full-bleed framed backdrop. The "video" is an 18s pure CSS/SVG story loop:
 *   Act 1  plan linework plots itself (outline, then partitions, then dims)
 *   Act 2  an instrument beam sweeps; rooms register as quiet duotone zones
 *          with numbered markers settling in (no bounce — precision easing)
 *   Act 3  the quantities panel composes: rows, confidence dots, total
 *   Act 4  the sąmata leaves for the client — "IŠSIŲSTA KLIENTUI ✓"
 * Then a slow dissolve and the cycle re-plots. prefers-reduced-motion →
 * the fully composed final frame. Scene micro-copy is LT draft.
 */
import { Link } from 'react-router';
import { useTranslation } from '@/i18n/react';

const mono = "'IBM Plex Mono', monospace";
const plex = "'IBM Plex Sans', sans-serif";

const CYCLE = '18s';
// Precision easing — decisive arrivals, zero overshoot ("grown", not springy).
const EASE = 'cubic-bezier(0.22, 1, 0.36, 1)';

const ROWS = [
  { name: 'Dažomas plotas', qty: '132,4 m²', conf: 'var(--ok)' },
  { name: 'Lubų glaistymas', qty: '165,6 m²', conf: 'var(--ok)' },
  { name: 'Grindjuostės', qty: '58,4 m', conf: 'var(--ok)' },
  { name: 'LED nišos', qty: '12,4 m', conf: 'var(--warn)' },
  { name: 'Angokraščiai', qty: '42,6 m', conf: 'var(--warn)' },
];

// Simplified L-shaped 6-room plan (viewBox 900×520). Nordic duotone: rooms
// alternate evergreen / slate translucent fills — no rainbow.
const TEAL = '63,102,92';   // #3F665C
const SLATE = '47,62,70';   // #2F3E46
const ROOMS = [
  { id: 101, d: 'M60,60 H400 V210 H60 Z', cx: 230, cy: 135, fill: TEAL, op: 0.14 },
  { id: 102, d: 'M400,60 H840 V210 H400 Z', cx: 620, cy: 135, fill: SLATE, op: 0.10 },
  { id: 103, d: 'M60,210 H340 V330 H60 Z', cx: 200, cy: 270, fill: SLATE, op: 0.08 },
  { id: 104, d: 'M340,210 H560 V460 H340 Z', cx: 450, cy: 335, fill: TEAL, op: 0.20 },
  { id: 105, d: 'M560,210 H840 V330 H560 Z', cx: 700, cy: 270, fill: TEAL, op: 0.10 },
  { id: 106, d: 'M560,330 H840 V460 H560 Z', cx: 700, cy: 395, fill: SLATE, op: 0.13 },
];

export default function HeroWalkthrough() {
  const { t } = useTranslation();
  return (
    <section className="plwt-sec" style={{ position: 'relative', overflow: 'hidden', borderBottom: '1px solid var(--line)' }}>
      <style>{css}</style>

      {/* ── Full-bleed framed story backdrop (the "video") ── */}
      <div className="plwt-frame" aria-hidden>
        <div className="plwt-scene">
          {/* plan */}
          <svg className="plwt-plan" viewBox="0 0 900 520" fill="none">
            {/* sheet */}
            <rect x="20" y="20" width="860" height="480" fill="var(--bg1)" stroke="var(--line)" />
            {/* walls — the outline plots first, partitions follow */}
            <g stroke="var(--ink)" strokeLinecap="square">
              <path className="plwt-ink1" pathLength="1" strokeWidth="2.5" d="M60,60 H840 V460 H340 V330 H60 Z" />
              <path className="plwt-ink2" pathLength="1" strokeWidth="1.5" d="M400,60 V210 M60,210 H840 M340,210 V460 M560,210 V460 M560,330 H840" />
            </g>
            {/* door gaps */}
            <g className="plwt-ink2" stroke="var(--bg1)" strokeWidth="5">
              <path pathLength="1" d="M370,210 h40 M560,250 v40 M470,460 h50 M400,120 v40" />
            </g>
            {/* dimension lines — horizontal + vertical, architectural notation */}
            <g className="plwt-dims" stroke="var(--mut)" strokeWidth="1">
              <path d="M60,486 H840 M60,481 v10 M840,481 v10" />
              <text x="450" y="479" textAnchor="middle" fontFamily={mono} fontSize="12" fill="var(--mut)" stroke="none" letterSpacing="0.08em">14 200</text>
              <path d="M42,60 V460 M37,60 h10 M37,460 h10" />
              <text x="34" y="264" textAnchor="middle" fontFamily={mono} fontSize="12" fill="var(--mut)" stroke="none" letterSpacing="0.08em" transform="rotate(-90 34 264)">7 300</text>
            </g>
            {/* instrument beam — eased sweep, hairline + soft wash */}
            <g className="plwt-beam">
              <rect x="-1" y="40" width="1.5" height="440" fill="var(--acc)" opacity="0.9" />
              <rect x="-64" y="40" width="62" height="440" fill="url(#plwtTrail)" />
            </g>
            {/* room zones + markers */}
            {ROOMS.map((r, i) => (
              <g key={r.id}>
                <path className={`plwt-zone plwt-z${i}`} d={r.d} fill={`rgba(${r.fill},${r.op})`} stroke={`rgba(${r.fill},0.55)`} strokeWidth="1" />
                <g className={`plwt-mark plwt-m${i}`} style={{ transformOrigin: `${r.cx}px ${r.cy}px` }}>
                  <circle cx={r.cx} cy={r.cy} r="16" fill="var(--bg1)" stroke="var(--ink)" strokeWidth="1.2" />
                  <text x={r.cx} y={r.cy + 4} textAnchor="middle" fontFamily={mono} fontSize="12" fontWeight="500" fill="var(--ink)">{r.id}</text>
                </g>
              </g>
            ))}
            <defs>
              <linearGradient id="plwtTrail" x1="0" y1="0" x2="1" y2="0">
                <stop offset="0" stopColor="var(--acc)" stopOpacity="0" />
                <stop offset="1" stopColor="var(--acc)" stopOpacity="0.16" />
              </linearGradient>
            </defs>
          </svg>

          {/* quantities panel — act 3 */}
          <div className="plwt-table">
            <div className="plwt-thead">
              <span>Kiekiai</span>
              <span className="plwt-count">46 eil.</span>
            </div>
            {ROWS.map((row, i) => (
              <div className={`plwt-row plwt-r${i}`} key={row.name}>
                <span className="plwt-dot" style={{ background: row.conf }} />
                <span className="plwt-name">{row.name}</span>
                <span className="plwt-qty">{row.qty}</span>
              </div>
            ))}
            <div className="plwt-total">
              <span>Iš viso, be PVM</span>
              <span className="plwt-sum">108 206 €</span>
            </div>
          </div>

          {/* act 4 — the sąmata leaves for the client */}
          <div className="plwt-doc">
            <svg width="44" height="56" viewBox="0 0 46 58">
              <rect x="1" y="1" width="44" height="56" rx="2" fill="var(--bg1)" stroke="var(--ink)" strokeWidth="1.2" />
              <path d="M9 12h28M9 20h28M9 28h18" stroke="var(--mut)" strokeWidth="2" strokeLinecap="round" />
              <path d="M9 40h12" stroke="var(--acc)" strokeWidth="2.5" strokeLinecap="round" />
              <path d="M28 42l4 4 7-8" stroke="var(--ok)" strokeWidth="2.4" fill="none" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </div>
          <div className="plwt-sent">
            <svg width="12" height="12" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"><path d="M13 4L6 12l-3.5-3.5" /></svg>
            Išsiųsta klientui
          </div>
        </div>
        {/* fade the scene under the headline column so the copy owns its space */}
        <div className="plwt-veil" />
      </div>

      {/* ── Hero copy ── */}
      <div className="plwt-copy">
        <div className="plwt-eyebrow">{t('landing.hero.eyebrow')}</div>
        <h1 className="plwt-h1" style={{ fontFamily: plex }}>
          {t('landing.hero.titleA')}<br />{t('landing.hero.titleB')}
        </h1>
        <p className="plwt-sub">{t('landing.hero.sub')}</p>
        <div className="plwt-ctas">
          <Link to="/register" className="pl-btn-primary">
            {t('landing.hero.ctaPrimary')}
            <svg width="14" height="14" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><path d="M3 8h10M9 4l4 4-4 4" /></svg>
          </Link>
          <a href="#produktas" className="pl-btn-ghost">{t('landing.hero.ctaDemo')}</a>
        </div>
        <p className="plwt-micro" style={{ fontFamily: mono }}>{t('landing.hero.micro')}</p>
      </div>
    </section>
  );
}

const css = `
/* ─── layout ─── */
.plwt-frame { position: absolute; inset: 12px; border-radius: 2px; border: 1px solid var(--line);
  overflow: hidden; background: var(--bg); }
.plwt-scene { position: absolute; inset: 0; }
.plwt-plan { position: absolute; left: 50%; top: 50%; transform: translateY(-50%); width: 42%; height: auto;
  animation: plwt-breath ${CYCLE} ease-in-out infinite; }
.plwt-veil { position: absolute; inset: 0; pointer-events: none;
  background: linear-gradient(100deg, var(--bg) 34%, color-mix(in srgb, var(--bg) 55%, transparent) 46%, transparent 60%); }
.plwt-copy { position: relative; z-index: 2; max-width: 1200px; margin: 0 auto;
  padding: 150px 40px 150px; min-height: 720px; box-sizing: border-box; }
.plwt-eyebrow { display: inline-flex; align-items: center; font-family: ${mono}; font-size: 11px;
  letter-spacing: 0.18em; text-transform: uppercase; color: var(--acc);
  border: 1px solid color-mix(in srgb, var(--acc) 30%, transparent);
  background: color-mix(in srgb, var(--acc) 7%, transparent); border-radius: 2px; padding: 7px 12px; }
.plwt-h1 { margin: 26px 0 0; max-width: 600px; font-weight: 600; letter-spacing: -0.03em; line-height: 1.07;
  font-size: clamp(34px, 3.9vw, 54px); text-wrap: balance; }
.plwt-sub { margin: 22px 0 0; max-width: 460px; font-size: 17px; line-height: 1.65; color: var(--ink2); }
.plwt-ctas { margin-top: 34px; display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.plwt-micro { margin: 20px 0 0; font-size: 11.5px; letter-spacing: 0.04em; color: var(--mut); }

/* ─── quantities panel ─── */
.plwt-table { position: absolute; right: 3.5%; bottom: 9%; width: min(300px, 26%);
  background: var(--bg1); border: 1px solid var(--line); border-radius: 2px; overflow: hidden;
  box-shadow: 0 40px 80px -48px var(--shadow); opacity: 0;
  animation: plwt-panel ${CYCLE} ${EASE} infinite; }
.plwt-thead { display: flex; justify-content: space-between; padding: 10px 14px; border-bottom: 1px solid var(--line);
  font-family: ${mono}; font-size: 9.5px; letter-spacing: 0.16em; text-transform: uppercase; color: var(--mut); }
.plwt-count { color: var(--acc); }
.plwt-row { display: flex; align-items: center; gap: 8px; padding: 8px 14px;
  border-bottom: 1px solid color-mix(in srgb, var(--line) 60%, transparent);
  font-size: 12px; opacity: 0; }
.plwt-dot { width: 6px; height: 6px; border-radius: 50%; flex-shrink: 0; }
.plwt-name { flex: 1; color: var(--ink2); }
.plwt-qty { font-family: ${mono}; font-size: 11.5px; font-variant-numeric: tabular-nums; color: var(--ink); }
.plwt-total { display: flex; justify-content: space-between; padding: 10px 14px; font-size: 12.5px;
  font-weight: 600; color: var(--acc); opacity: 0; animation: plwt-total ${CYCLE} ${EASE} infinite; }
.plwt-sum { font-family: ${mono}; font-variant-numeric: tabular-nums; }

/* ─── act 4: document → client ─── */
.plwt-doc { position: absolute; right: 12%; bottom: 42%; opacity: 0;
  animation: plwt-doc ${CYCLE} cubic-bezier(0.6, 0.05, 0.3, 1) infinite; }
.plwt-sent { position: absolute; right: 4%; top: 14%; display: inline-flex; align-items: center; gap: 7px;
  font-family: ${mono}; font-size: 10.5px; letter-spacing: 0.14em; text-transform: uppercase; color: var(--acc);
  background: color-mix(in srgb, var(--acc) 9%, var(--bg1)); border: 1px solid color-mix(in srgb, var(--acc) 30%, transparent);
  border-radius: 2px; padding: 8px 13px; opacity: 0; animation: plwt-sent ${CYCLE} ${EASE} infinite; }

/* ─── act 1: the plan plots itself ─── */
.plwt-ink1 { stroke-dasharray: 1; stroke-dashoffset: 1; animation: plwt-draw1 ${CYCLE} ease-in-out infinite; }
.plwt-ink2 { stroke-dasharray: 1; stroke-dashoffset: 1; animation: plwt-draw2 ${CYCLE} ease-in-out infinite; }
.plwt-ink2 path { stroke-dasharray: 1; }
.plwt-dims { opacity: 0; animation: plwt-dims ${CYCLE} ${EASE} infinite; }

/* ─── act 2: beam + zones + markers ─── */
.plwt-beam { opacity: 0; animation: plwt-beam ${CYCLE} cubic-bezier(0.45, 0.05, 0.55, 0.95) infinite; }
.plwt-zone { opacity: 0; animation: plwt-zone ${CYCLE} ${EASE} infinite; }
.plwt-mark { opacity: 0; animation: plwt-mark ${CYCLE} ${EASE} infinite; }

/* stagger — the beam reaches each room left-to-right */
.plwt-z0 { animation-delay: 0s; }    .plwt-m0 { animation-delay: .25s; }
.plwt-z2 { animation-delay: .4s; }   .plwt-m2 { animation-delay: .65s; }
.plwt-z3 { animation-delay: .9s; }   .plwt-m3 { animation-delay: 1.15s; }
.plwt-z1 { animation-delay: 1.35s; } .plwt-m1 { animation-delay: 1.6s; }
.plwt-z4 { animation-delay: 1.8s; }  .plwt-m4 { animation-delay: 2.05s; }
.plwt-z5 { animation-delay: 2.2s; }  .plwt-m5 { animation-delay: 2.45s; }
.plwt-r0 { animation: plwt-row ${CYCLE} ${EASE} infinite; animation-delay: 0s; }
.plwt-r1 { animation: plwt-row ${CYCLE} ${EASE} infinite; animation-delay: .3s; }
.plwt-r2 { animation: plwt-row ${CYCLE} ${EASE} infinite; animation-delay: .6s; }
.plwt-r3 { animation: plwt-row ${CYCLE} ${EASE} infinite; animation-delay: .9s; }
.plwt-r4 { animation: plwt-row ${CYCLE} ${EASE} infinite; animation-delay: 1.2s; }

/* ─── master timeline (percent of ${CYCLE}) ─── */
@keyframes plwt-breath { 0%,100% { transform: translateY(-50%) scale(1); } 50% { transform: translateY(-50%) scale(1.006); } }
@keyframes plwt-draw1 { 0%,3% { stroke-dashoffset: 1; opacity: 1; } 12% { stroke-dashoffset: 0; }
  94% { stroke-dashoffset: 0; opacity: 1; } 99%,100% { stroke-dashoffset: 0; opacity: 0; } }
@keyframes plwt-draw2 { 0%,8% { stroke-dashoffset: 1; opacity: 1; } 17% { stroke-dashoffset: 0; }
  94% { stroke-dashoffset: 0; opacity: 1; } 99%,100% { stroke-dashoffset: 0; opacity: 0; } }
@keyframes plwt-dims  { 0%,14% { opacity: 0; } 18%,94% { opacity: 1; } 99%,100% { opacity: 0; } }
@keyframes plwt-beam  { 0%,16% { opacity: 0; transform: translateX(50px); }
  18% { opacity: 1; } 34% { opacity: 1; transform: translateX(855px); }
  36%,100% { opacity: 0; transform: translateX(855px); } }
@keyframes plwt-zone  { 0%,18% { opacity: 0; } 22%,94% { opacity: 1; } 98%,100% { opacity: 0; } }
@keyframes plwt-mark  { 0%,19% { opacity: 0; transform: scale(.94); }
  23%,94% { opacity: 1; transform: scale(1); } 98%,100% { opacity: 0; transform: scale(1); } }
@keyframes plwt-panel { 0%,40% { opacity: 0; transform: translateY(14px); }
  45%,94% { opacity: 1; transform: translateY(0); } 98%,100% { opacity: 0; } }
@keyframes plwt-row   { 0%,44% { opacity: 0; transform: translateY(6px); }
  48%,94% { opacity: 1; transform: translateY(0); } 98%,100% { opacity: 0; } }
@keyframes plwt-total { 0%,58% { opacity: 0; } 62%,94% { opacity: 1; } 98%,100% { opacity: 0; } }
@keyframes plwt-doc   { 0%,64% { opacity: 0; transform: translate(0,10px) scale(.96); }
  67% { opacity: 1; transform: translate(0,0) scale(1); }
  72% { opacity: 1; transform: translate(0,0) scale(1); }
  81% { opacity: 0; transform: translate(130px,-150px) scale(.82); }
  100% { opacity: 0; } }
@keyframes plwt-sent  { 0%,79% { opacity: 0; transform: translateY(6px); }
  83%,95% { opacity: 1; transform: translateY(0); } 99%,100% { opacity: 0; } }

/* ─── responsive: copy first, scene below ─── */
@media (max-width: 1023px) {
  .plwt-sec { display: flex; flex-direction: column; }
  .plwt-copy { order: -1; padding: 80px 24px 20px; min-height: 0; text-align: center; }
  .plwt-h1, .plwt-sub { margin-left: auto; margin-right: auto; }
  .plwt-ctas { justify-content: center; }
  .plwt-frame { position: relative; inset: auto; margin: 0 16px 40px; height: 360px; }
  .plwt-veil { display: none; }
  .plwt-plan { left: 3%; top: 50%; width: 60%; }
  .plwt-table { right: 3%; bottom: 8%; width: 37%; min-width: 150px; }
  .plwt-sent { right: 3%; top: 4%; }
  .plwt-doc { right: 16%; bottom: 46%; }
}

/* ─── reduced motion: the fully composed final frame, static ─── */
@media (prefers-reduced-motion: reduce) {
  .plwt-plan { animation: none !important; }
  .plwt-ink1, .plwt-ink2, .plwt-dims, .plwt-zone, .plwt-mark, .plwt-table, .plwt-row,
  .plwt-total, .plwt-sent { animation: none !important; opacity: 1 !important; stroke-dashoffset: 0 !important; }
  .plwt-beam, .plwt-doc { animation: none !important; opacity: 0 !important; }
}
`;
