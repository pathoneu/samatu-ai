/**
 * HeroWalkthrough — PROTOTYPE hero variant (2026-07-11), reachable only via
 * /about?hero=v2 (default landing untouched until the founder approves).
 *
 * Pattern reference: 21st.dev hero-section-5 — big left-aligned headline with
 * pill CTAs floating over a full-bleed rounded "video" backdrop. Instead of a
 * stock video, the backdrop is a ~16s pure CSS/SVG story loop of what Pathon
 * actually does:
 *   Act 1  plan linework draws itself (the PDF being read)
 *   Act 2  scan beam sweeps; rooms light up with numbered markers
 *   Act 3  quantities panel fills in (rows + confidence dots + total)
 *   Act 4  the sąmata document flies off to the client — "Išsiųsta klientui ✓"
 * Loops seamlessly. prefers-reduced-motion → the fully composed final frame.
 * All scene micro-copy is hardcoded LT draft (founder polishes on approval).
 */
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';

const mono = "'JetBrains Mono', monospace";
const sora = "'Sora', sans-serif";

// One master 16s timeline; every element's @keyframes use these act boundaries.
const CYCLE = '16s';

const ROWS = [
  { name: 'Dažomas plotas', qty: '132,4 m²', conf: 'var(--ok)' },
  { name: 'Lubų glaistymas', qty: '165,6 m²', conf: 'var(--ok)' },
  { name: 'Grindjuostės', qty: '58,4 m', conf: 'var(--ok)' },
  { name: 'LED nišos', qty: '12,4 m', conf: 'var(--warn)' },
  { name: 'Angokraščiai', qty: '42,6 m', conf: 'var(--warn)' },
];

// Simplified L-shaped 6-room plan (viewBox 900×520). Rooms get a fill polygon,
// a numbered marker, and stagger indices for the reveal order.
const ROOMS = [
  { id: 101, d: 'M60,60 H400 V210 H60 Z', cx: 230, cy: 135, fill: '16,185,129' },
  { id: 102, d: 'M400,60 H840 V210 H400 Z', cx: 620, cy: 135, fill: '245,158,11' },
  { id: 103, d: 'M60,210 H340 V330 H60 Z', cx: 200, cy: 270, fill: '59,130,246' },
  { id: 104, d: 'M340,210 H560 V460 H340 Z', cx: 450, cy: 335, fill: '6,182,212' },
  { id: 105, d: 'M560,210 H840 V330 H560 Z', cx: 700, cy: 270, fill: '167,139,250' },
  { id: 106, d: 'M560,330 H840 V460 H560 Z', cx: 700, cy: 395, fill: '34,197,94' },
];

export default function HeroWalkthrough() {
  const { t } = useTranslation();
  return (
    <section className="plwt-sec" style={{ position: 'relative', overflow: 'hidden', borderBottom: '1px solid var(--line)' }}>
      <style>{css}</style>

      {/* ── Full-bleed rounded story backdrop (the "video") ── */}
      <div className="plwt-frame" aria-hidden>
        <div className="plwt-scene">
          {/* plan (left ~62%) */}
          <svg className="plwt-plan" viewBox="0 0 900 520" fill="none">
            {/* sheet */}
            <rect x="20" y="20" width="860" height="480" rx="6" fill="var(--bg1)" stroke="var(--line2)" />
            {/* walls — draw themselves in act 1 */}
            <g className="plwt-ink" stroke="var(--ink)" strokeWidth="3" strokeLinecap="square">
              <path pathLength="1" d="M60,60 H840 V460 H340 V330 H60 Z" />
              <path pathLength="1" d="M400,60 V210 M60,210 H840 M340,210 V460 M560,210 V460 M560,330 H840" strokeWidth="2" />
            </g>
            {/* door gaps (light strokes over walls, appear with linework) */}
            <g className="plwt-ink" stroke="var(--bg1)" strokeWidth="5">
              <path pathLength="1" d="M370,210 h40 M560,250 v40 M470,460 h50 M400,120 v40" />
            </g>
            {/* dimension ticks */}
            <g className="plwt-dims" stroke="var(--mut)" strokeWidth="1">
              <path d="M60,485 H840 M60,480 v10 M840,480 v10" />
              <text x="450" y="478" textAnchor="middle" fontFamily={mono} fontSize="13" fill="var(--mut)" stroke="none">14 200</text>
            </g>
            {/* scan beam — act 2 */}
            <g className="plwt-beam">
              <rect x="-3" y="40" width="6" height="440" fill="var(--acc)" opacity="0.85" />
              <rect x="-46" y="40" width="44" height="440" fill="url(#plwtTrail)" />
            </g>
            {/* room zones + numbered markers */}
            {ROOMS.map((r, i) => (
              <g key={r.id}>
                <path className={`plwt-zone plwt-z${i}`} d={r.d} fill={`rgba(${r.fill},0.30)`} stroke={`rgba(${r.fill},0.85)`} strokeWidth="1.5" />
                <g className={`plwt-mark plwt-m${i}`} style={{ transformOrigin: `${r.cx}px ${r.cy}px` }}>
                  <circle cx={r.cx} cy={r.cy} r="17" fill="var(--bg1)" stroke="var(--ink)" strokeWidth="1.4" />
                  <text x={r.cx} y={r.cy + 4.5} textAnchor="middle" fontFamily={mono} fontSize="13" fontWeight="600" fill="var(--ink)">{r.id}</text>
                </g>
              </g>
            ))}
            <defs>
              <linearGradient id="plwtTrail" x1="0" y1="0" x2="1" y2="0">
                <stop offset="0" stopColor="var(--acc)" stopOpacity="0" />
                <stop offset="1" stopColor="var(--acc)" stopOpacity="0.28" />
              </linearGradient>
            </defs>
          </svg>

          {/* quantities panel (right) — act 3 */}
          <div className="plwt-table">
            <div className="plwt-thead">
              <span>KIEKIAI</span>
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

          {/* act 4 — the sąmata flies to the client */}
          <div className="plwt-doc">
            <svg width="46" height="58" viewBox="0 0 46 58">
              <rect x="1" y="1" width="44" height="56" rx="5" fill="var(--bg1)" stroke="var(--ink)" strokeWidth="1.4" />
              <path d="M9 12h28M9 20h28M9 28h18" stroke="var(--mut)" strokeWidth="2" strokeLinecap="round" />
              <path d="M9 40h12" stroke="var(--acc)" strokeWidth="2.5" strokeLinecap="round" />
              <path d="M28 42l4 4 7-8" stroke="var(--ok)" strokeWidth="2.4" fill="none" strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          </div>
          <div className="plwt-sent">
            <svg width="13" height="13" viewBox="0 0 16 16" fill="none" stroke="var(--ok)" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"><path d="M13 4L6 12l-3.5-3.5" /></svg>
            Išsiųsta klientui
          </div>
        </div>
        {/* fade the scene under the headline zone so text stays crisp */}
        <div className="plwt-veil" />
      </div>

      {/* ── Hero copy over the backdrop (reference layout) ── */}
      <div className="plwt-copy">
        <div className="plwt-eyebrow">{t('landing.hero.eyebrow')}</div>
        <h1 className="plwt-h1" style={{ fontFamily: sora }}>
          {t('landing.hero.titleA')}<br />{t('landing.hero.titleB')}
        </h1>
        <p className="plwt-sub">{t('landing.hero.sub')}</p>
        <div className="plwt-ctas">
          <Link to="/register" className="pl-btn-primary" style={{ borderRadius: 999, height: 46, paddingLeft: 22, paddingRight: 16 }}>
            {t('landing.hero.ctaPrimary')}
            <svg width="15" height="15" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><path d="M3 8h10M9 4l4 4-4 4" /></svg>
          </Link>
          <a href="#produktas" className="pl-btn-ghost" style={{ borderRadius: 999, height: 46 }}>
            <svg width="13" height="13" viewBox="0 0 16 16" fill="currentColor"><path d="M4 2.5v11l9-5.5z" /></svg>
            {t('landing.hero.ctaDemo')}
          </a>
        </div>
        <p className="plwt-micro" style={{ fontFamily: mono }}>{t('landing.hero.micro')}</p>
      </div>
    </section>
  );
}

const css = `
/* ─── layout ─── */
.plwt-frame { position: absolute; inset: 12px; border-radius: 28px; border: 1px solid var(--line2);
  overflow: hidden; background: var(--bg); }
.plwt-scene { position: absolute; inset: 0; }
.plwt-plan { position: absolute; left: 50%; top: 50%; transform: translateY(-50%); width: 42%; height: auto; }
.plwt-veil { position: absolute; inset: 0; pointer-events: none;
  background: linear-gradient(100deg, var(--bg) 34%, color-mix(in srgb, var(--bg) 55%, transparent) 46%, transparent 60%); }
.plwt-copy { position: relative; z-index: 2; max-width: 1200px; margin: 0 auto;
  padding: 150px 40px 150px; min-height: 720px; box-sizing: border-box; }
.plwt-eyebrow { font-family: ${mono}; font-size: 11px; letter-spacing: 0.18em; text-transform: uppercase; color: var(--acc); }
.plwt-h1 { margin: 22px 0 0; max-width: 600px; font-weight: 700; letter-spacing: -0.035em; line-height: 1.05;
  font-size: clamp(34px, 3.9vw, 54px); text-wrap: balance; }
.plwt-sub { margin: 22px 0 0; max-width: 460px; font-size: 17px; line-height: 1.6; color: var(--ink2); }
.plwt-ctas { margin-top: 32px; display: flex; align-items: center; gap: 12px; flex-wrap: wrap; }
.plwt-micro { margin: 18px 0 0; font-size: 12px; color: var(--mut); }

/* ─── quantities panel ─── */
.plwt-table { position: absolute; right: 3.5%; bottom: 9%; width: min(300px, 26%);
  background: var(--bg1); border: 1px solid var(--line2); border-radius: 12px; overflow: hidden;
  box-shadow: 0 28px 60px -30px var(--shadow); opacity: 0;
  animation: plwt-panel ${CYCLE} cubic-bezier(.3,.1,.2,1) infinite; }
.plwt-thead { display: flex; justify-content: space-between; padding: 9px 13px; border-bottom: 1px solid var(--line);
  font-family: ${mono}; font-size: 9.5px; letter-spacing: 0.13em; color: var(--mut); }
.plwt-count { color: var(--acc); }
.plwt-row { display: flex; align-items: center; gap: 8px; padding: 7px 13px;
  border-bottom: 1px solid color-mix(in srgb, var(--line) 55%, transparent);
  font-size: 12px; opacity: 0; }
.plwt-dot { width: 7px; height: 7px; border-radius: 50%; flex-shrink: 0; }
.plwt-name { flex: 1; }
.plwt-qty { font-family: ${mono}; font-size: 11.5px; font-variant-numeric: tabular-nums; }
.plwt-total { display: flex; justify-content: space-between; padding: 9px 13px; font-size: 12px;
  font-weight: 600; opacity: 0; animation: plwt-total ${CYCLE} ease infinite; }
.plwt-sum { font-family: ${mono}; font-variant-numeric: tabular-nums; }

/* ─── act 4: document → client ─── */
.plwt-doc { position: absolute; right: 12%; bottom: 42%; opacity: 0;
  animation: plwt-doc ${CYCLE} cubic-bezier(.45,.05,.4,1) infinite; }
.plwt-sent { position: absolute; right: 4%; top: 16%; display: inline-flex; align-items: center; gap: 6px;
  font-size: 12.5px; color: var(--ok); background: var(--bg1);
  border: 1px solid color-mix(in srgb, var(--ok) 40%, transparent); border-radius: 999px;
  padding: 6px 13px; opacity: 0; animation: plwt-sent ${CYCLE} ease infinite; }

/* ─── act 1: linework draws ─── */
.plwt-ink path { stroke-dasharray: 1; stroke-dashoffset: 1;
  animation: plwt-draw ${CYCLE} linear infinite; }
.plwt-dims { opacity: 0; animation: plwt-dims ${CYCLE} ease infinite; }

/* ─── act 2: beam + zones + markers ─── */
.plwt-beam { opacity: 0; animation: plwt-beam ${CYCLE} linear infinite; }
.plwt-zone { opacity: 0; animation: plwt-zone ${CYCLE} ease infinite; }
.plwt-mark { opacity: 0; animation: plwt-mark ${CYCLE} cubic-bezier(.34,1.45,.6,1) infinite; }

/* zone/marker stagger (act 2 spans ~16%→38% of the cycle) */
.plwt-z0 { animation-delay: 0s; }    .plwt-m0 { animation-delay: .3s; }
.plwt-z1 { animation-delay: .55s; }  .plwt-m1 { animation-delay: .85s; }
.plwt-z2 { animation-delay: 1.1s; }  .plwt-m2 { animation-delay: 1.4s; }
.plwt-z3 { animation-delay: 1.65s; } .plwt-m3 { animation-delay: 1.95s; }
.plwt-z4 { animation-delay: 2.2s; }  .plwt-m4 { animation-delay: 2.5s; }
.plwt-z5 { animation-delay: 2.75s; } .plwt-m5 { animation-delay: 3.05s; }
/* table row stagger (act 3 spans ~44%→60%) */
.plwt-r0 { animation: plwt-row ${CYCLE} ease infinite; animation-delay: 0s; }
.plwt-r1 { animation: plwt-row ${CYCLE} ease infinite; animation-delay: .35s; }
.plwt-r2 { animation: plwt-row ${CYCLE} ease infinite; animation-delay: .7s; }
.plwt-r3 { animation: plwt-row ${CYCLE} ease infinite; animation-delay: 1.05s; }
.plwt-r4 { animation: plwt-row ${CYCLE} ease infinite; animation-delay: 1.4s; }

/* ─── master timeline keyframes (percent of ${CYCLE}) ─── */
@keyframes plwt-draw  { 0% { stroke-dashoffset: 1; } 4% { stroke-dashoffset: 1; } 15% { stroke-dashoffset: 0; }
  92% { stroke-dashoffset: 0; opacity: 1; } 97%,100% { stroke-dashoffset: 0; opacity: 1; } }
@keyframes plwt-dims  { 0%,12% { opacity: 0; } 16%,92% { opacity: 1; } 97%,100% { opacity: 0; } }
@keyframes plwt-beam  { 0%,14% { opacity: 0; transform: translateX(40px); }
  16% { opacity: 1; } 36% { opacity: 1; transform: translateX(860px); }
  38%,100% { opacity: 0; transform: translateX(860px); } }
@keyframes plwt-zone  { 0%,17% { opacity: 0; } 21%,92% { opacity: 1; } 96%,100% { opacity: 0; } }
@keyframes plwt-mark  { 0%,18% { opacity: 0; transform: scale(.4); }
  21% { opacity: 1; transform: scale(1.12); } 23%,92% { opacity: 1; transform: scale(1); }
  96%,100% { opacity: 0; transform: scale(1); } }
@keyframes plwt-panel { 0%,40% { opacity: 0; transform: translateX(26px); }
  44%,92% { opacity: 1; transform: translateX(0); } 96%,100% { opacity: 0; } }
@keyframes plwt-row   { 0%,44% { opacity: 0; transform: translateY(7px); }
  47%,92% { opacity: 1; transform: translateY(0); } 96%,100% { opacity: 0; } }
@keyframes plwt-total { 0%,58% { opacity: 0; } 61%,92% { opacity: 1; } 96%,100% { opacity: 0; } }
@keyframes plwt-doc   { 0%,63% { opacity: 0; transform: translate(0,14px) scale(.85); }
  66% { opacity: 1; transform: translate(0,0) scale(1); }
  71% { opacity: 1; transform: translate(0,0) scale(1); }
  80% { opacity: 0; transform: translate(150px,-130px) scale(.7) rotate(8deg); }
  100% { opacity: 0; } }
@keyframes plwt-sent  { 0%,78% { opacity: 0; transform: translateY(8px); }
  81%,93% { opacity: 1; transform: translateY(0); } 97%,100% { opacity: 0; } }

/* ─── responsive: stack copy above a fixed-aspect scene panel ─── */
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
  .plwt-ink path, .plwt-dims, .plwt-zone, .plwt-mark, .plwt-table, .plwt-row,
  .plwt-total, .plwt-sent { animation: none !important; opacity: 1 !important; stroke-dashoffset: 0 !important; }
  .plwt-beam, .plwt-doc { animation: none !important; opacity: 0 !important; }
}
`;
