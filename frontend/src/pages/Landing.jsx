/**
 * Pathon — public landing page.
 *
 * 2026-07-07: rebuilt as a 1:1 port of the founder-approved Claude Design
 * export "Pathon Landing v2" (palette D · paper + clay). The design's dc
 * bindings are reimplemented as React state:
 *   - hero "measuring instrument": crosshair + coordinate tip + room hit-test
 *     + cursor spotlight (mousemove over #virsus, skipped on reduced motion);
 *   - 11s CSS scan choreography over the background floor plan (landing.css);
 *   - self-playing product demo (animated cursor walks the UI: selects a room,
 *     opens Prielaidos, steps the ceiling height 2.70→3.20 — every dependent
 *     number recalculates live — then opens Export). Any manual interaction
 *     takes the demo over; ⏸/▶ toggles it.
 *   - section 5 live recalc (2,70 m ↔ 3,20 m buttons, rAF-animated numbers).
 *
 * Two-page language model: "/" (+ /about) is ALWAYS Lithuanian, "/en" always
 * English (hreflang pair; prerendered by build:seo). The footer language
 * switch navigates between the routes. All copy lives in i18n landing.* keys.
 *
 * Demo math mirrors the engine's shape, not its code: paint(h) = 61.8·h − 14.2
 * (walls = perimeter × H − openings), costs = qty × rate, gross = net × 1.21.
 */
import React, { useCallback, useEffect, useRef, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { changeAppLanguage } from '@/i18n';
import { PathonMark } from '@/components/layout/Logo';
import { openCookieSettings } from '@/components/CookieBanner';
import { setPageMeta, setHreflang } from '@/lib/seo';
import './landing/landing.css';

// Founder-approved palette (Claude Design export default: "D · Popierius ir
// molis"). One-letter switch: A graphite · B navy · C blue · D clay · E ink ·
// F orange · G plum — definitions in landing/landing.css.
const PALETTE = 'D';
const HERO_SCAN = true;
const WA_URL = 'https://wa.me/37060271962';
const MAIL_URL = 'mailto:solutions@pathon.eu';

const calcPaint = (h) => 61.8 * h - 14.2;
const easeOut = (t) => 1 - Math.pow(1 - t, 3);

const mono = "'JetBrains Mono', monospace";
const sora = "'Sora', sans-serif";

export default function Landing({ lang }) {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();

  const locale = (i18n.language || 'lt').startsWith('en') ? 'en-GB' : 'lt-LT';
  const fmt = useCallback(
    (n, d) => n.toLocaleString(locale, { minimumFractionDigits: d, maximumFractionDigits: d }),
    [locale]
  );

  // ── Deterministic two-page language model + per-route meta/hreflang ──
  useEffect(() => {
    const target = lang || 'lt';
    if (i18n.language !== target) i18n.changeLanguage(target);
    try {
      document.documentElement.lang = target;
    } catch { /* no-op */ }
    setPageMeta(
      target === 'en'
        ? {
            title: 'Construction quantities from drawings',
            description:
              'Upload a construction PDF — Pathon measures rooms and finishing quantities and prepares a Lithuanian-format estimate in minutes. You review flagged items and set your own prices.',
            path: '/en',
          }
        : {
            title: 'Statybų kiekiai iš brėžinių',
            description:
              'Įkelk statybų PDF brėžinį — Pathon išmatuoja kiekius ir paruošia sąmatą Lietuvos formatu per kelias minutes. Kainas suvedi pats.',
            path: window.location.pathname === '/about' ? '/about' : '/',
          }
    );
    setHreflang([
      { hrefLang: 'lt', href: 'https://pathon.eu/' },
      { hrefLang: 'en', href: 'https://pathon.eu/en' },
      { hrefLang: 'x-default', href: 'https://pathon.eu/' },
    ]);
    return () => setHreflang([]);
  }, [lang, i18n]);

  const reduceRef = useRef(false);

  // ── Scroll reveals ──
  useEffect(() => {
    reduceRef.current = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    // Robustness: under automation (navigator.webdriver — the build:seo
    // prerender driver, screenshots) or reduced motion, IntersectionObserver
    // never fires for below-fold content in a no-scroll context, which would
    // bake opacity-0 sections into the prerendered HTML. Reveal everything
    // immediately there; real visitors get the staggered scroll reveals.
    const els = document.querySelectorAll('#plr [data-reveal]');
    if (navigator.webdriver || reduceRef.current || !('IntersectionObserver' in window)) {
      els.forEach((el) => el.classList.add('plin'));
      return undefined;
    }
    const io = new IntersectionObserver(
      (entries) => {
        entries.forEach((e) => {
          if (e.isIntersecting) {
            e.target.classList.add('plin');
            io.unobserve(e.target);
          }
        });
      },
      { threshold: 0.15 }
    );
    els.forEach((el) => io.observe(el));
    return () => io.disconnect();
    // Re-run on language change: translated content re-renders, and any DOM
    // node React recreated would otherwise be left without .plin (invisible).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [i18n.resolvedLanguage]);

  // ── Parallax + product-frame tilt (rAF-throttled, cheap transforms) ──
  useEffect(() => {
    let raf = null;
    const onScroll = () => {
      if (raf) return;
      raf = requestAnimationFrame(() => {
        raf = null;
        if (reduceRef.current) return;
        const bg = document.getElementById('plHeroBg');
        if (bg) bg.style.transform = `translateY(${window.scrollY * 0.16}px)`;
        const fr = document.getElementById('plFrame');
        if (fr) {
          const r = fr.getBoundingClientRect();
          const vh = window.innerHeight;
          const p = Math.max(0, Math.min(1, (vh - r.top) / (vh * 0.7)));
          const k = 1 - p;
          fr.style.transform = `perspective(1400px) rotateX(${(k * 6).toFixed(2)}deg) translateY(${(k * 28).toFixed(1)}px) scale(${(0.985 + p * 0.015).toFixed(4)})`;
        }
      });
    };
    window.addEventListener('scroll', onScroll, { passive: true });
    onScroll();
    return () => {
      window.removeEventListener('scroll', onScroll);
      if (raf) cancelAnimationFrame(raf);
    };
  }, []);

  // ── Hero measuring instrument ──
  const [hoverRoom, setHoverRoom] = useState(null);
  const heroRooms = [
    { id: 'svet', x0: 60, x1: 460, y0: 60, y1: 560 },
    { id: 'mieg', x0: 460, x1: 800, y0: 60, y1: 330 },
    { id: 'virt', x0: 800, x1: 1120, y0: 60, y1: 330 },
    { id: 'von', x0: 460, x1: 690, y0: 330, y1: 560 },
    { id: 'kor', x0: 690, x1: 920, y0: 330, y1: 560 },
    { id: 'kab', x0: 920, x1: 1120, y0: 330, y1: 560 },
  ];
  const roomLabels = t('landing.heroRooms', { returnObjects: true });

  const heroMove = (e) => {
    if (reduceRef.current) return;
    const hero = document.getElementById('virsus');
    const svg = document.getElementById('plPlanSvg');
    if (!hero || !svg) return;
    const hr = hero.getBoundingClientRect();
    const x = e.clientX - hr.left;
    const y = e.clientY - hr.top;

    const ch = document.getElementById('plCh');
    if (ch) {
      ch.style.opacity = '1';
      const v = document.getElementById('plChV');
      const h = document.getElementById('plChH');
      if (v) v.style.left = `${x}px`;
      if (h) h.style.top = `${y}px`;
    }
    const spot = document.getElementById('plSpot');
    if (spot) {
      spot.style.opacity = '1';
      spot.style.transform = `translate(${x - 240}px, ${y - 240}px)`;
    }

    const sr = svg.getBoundingClientRect();
    const vx = ((e.clientX - sr.left) / sr.width) * 1180;
    const vy = ((e.clientY - sr.top) / sr.height) * 620;
    const mx = Math.max(0, Math.min(11.2, ((vx - 60) / 1060) * 11.2));
    const my = Math.max(0, Math.min(5.3, ((vy - 60) / 500) * 5.3));
    const idx = heroRooms.findIndex(
      (r) => vx >= r.x0 && vx <= r.x1 && vy >= r.y0 && vy <= r.y1
    );
    const tip = document.getElementById('plChTip');
    if (tip) {
      const coords = `x ${fmt(mx, 2)} m · y ${fmt(my, 2)} m`;
      tip.textContent = idx >= 0 ? `${roomLabels[idx]}  —  ${coords}` : coords;
      tip.style.left = `${Math.min(x + 16, hr.width - 190)}px`;
      tip.style.top = `${Math.min(y + 16, hr.height - 60)}px`;
    }
    const id = idx >= 0 ? heroRooms[idx].id : null;
    setHoverRoom((prev) => (prev === id ? prev : id));
  };

  const heroLeave = () => {
    const ch = document.getElementById('plCh');
    if (ch) ch.style.opacity = '0';
    const spot = document.getElementById('plSpot');
    if (spot) spot.style.opacity = '0';
    setHoverRoom(null);
  };

  // ── Section 5: live recalc ──
  const [rc, setRc] = useState({ h: 2.7, paint: calcPaint(2.7), glaist: calcPaint(2.7) * 1.1 });
  const [rcTarget, setRcTarget] = useState(2.7);
  const rcRaf = useRef(null);
  const animateTo = (hTarget) => {
    setRcTarget(hTarget);
    if (rcRaf.current) cancelAnimationFrame(rcRaf.current);
    const from = { ...rc };
    const p = calcPaint(hTarget);
    const to = { h: hTarget, paint: p, glaist: p * 1.1 };
    const t0 = performance.now();
    const dur = 550;
    const tick = (now) => {
      const k = easeOut(Math.min(1, (now - t0) / dur));
      setRc({
        h: from.h + (to.h - from.h) * k,
        paint: from.paint + (to.paint - from.paint) * k,
        glaist: from.glaist + (to.glaist - from.glaist) * k,
      });
      if (k < 1) rcRaf.current = requestAnimationFrame(tick);
    };
    rcRaf.current = requestAnimationFrame(tick);
  };

  // ── Product demo state machine ──
  const [demo, setDemo] = useState({
    playing: true,
    dh: 2.7,
    curL: '55%',
    curT: '72%',
    curClick: false,
    popVis: false,
    expVis: false,
    stepUpOn: false,
    rowFlash: false,
    sel: null,
    tab: 'brez',
  });
  const demoRef = useRef(demo);
  demoRef.current = demo;
  const timersRef = useRef([]);
  const drafRef = useRef(null);
  const dhTargetRef = useRef(null);
  const flashTRef = useRef(null);
  const runningRef = useRef(false);

  const patch = (p) => setDemo((s) => ({ ...s, ...p }));

  const clearDemo = useCallback(() => {
    timersRef.current.forEach(clearTimeout);
    timersRef.current = [];
    runningRef.current = false;
    if (drafRef.current) cancelAnimationFrame(drafRef.current);
  }, []);

  const animDh = useCallback((target, dur) => {
    if (drafRef.current) cancelAnimationFrame(drafRef.current);
    const from = demoRef.current.dh;
    const t0 = performance.now();
    const tick = (now) => {
      const k = easeOut(Math.min(1, (now - t0) / dur));
      patch({ dh: from + (target - from) * k });
      if (k < 1) drafRef.current = requestAnimationFrame(tick);
    };
    drafRef.current = requestAnimationFrame(tick);
  }, []);

  const demoClick = useCallback((fn) => {
    patch({ curClick: true });
    if (fn) fn();
    timersRef.current.push(setTimeout(() => patch({ curClick: false }), 600));
  }, []);

  const runDemo = useCallback(() => {
    clearDemo();
    runningRef.current = true;
    const at = (ms, fn) => timersRef.current.push(setTimeout(fn, ms));
    at(300, () => patch({ curL: '24%', curT: '52%' }));
    at(1400, () => demoClick(() => patch({ sel: 'svet' })));
    at(2600, () => patch({ curL: '80%', curT: '5%' }));
    at(3700, () => demoClick(() => patch({ popVis: true })));
    at(4700, () => patch({ curL: '86%', curT: '22%' }));
    at(5800, () =>
      demoClick(() => {
        patch({ stepUpOn: true, rowFlash: true });
        animDh(3.2, 700);
      })
    );
    at(6600, () => patch({ stepUpOn: false }));
    at(8000, () => patch({ curL: '93.5%', curT: '5%', popVis: false, rowFlash: false }));
    at(9100, () => demoClick(() => patch({ expVis: true })));
    at(11400, () => {
      patch({ expVis: false, sel: null, curL: '55%', curT: '72%' });
      animDh(2.7, 500);
    });
    at(12800, () => {
      if (demoRef.current.playing) runDemo();
    });
  }, [animDh, clearDemo, demoClick]);

  const takeover = useCallback(() => {
    clearDemo();
    if (demoRef.current.playing) patch({ playing: false });
  }, [clearDemo]);

  const manualSelect = (room) => {
    takeover();
    patch({
      sel: demoRef.current.sel === room ? null : room,
      popVis: false,
      expVis: false,
    });
  };

  const step = (dir) => {
    takeover();
    dhTargetRef.current = Math.max(
      2.2,
      Math.min(4.0, (dhTargetRef.current ?? Math.round(demoRef.current.dh * 10) / 10) + dir * 0.1)
    );
    patch({ popVis: true, rowFlash: true });
    animDh(dhTargetRef.current, 280);
    clearTimeout(flashTRef.current);
    flashTRef.current = setTimeout(() => patch({ rowFlash: false }), 900);
  };

  const toggleDemo = () => {
    const next = !demoRef.current.playing;
    patch({ playing: next });
    if (next) runDemo();
    else clearDemo();
  };

  // Autoplay when the frame scrolls into view; full cleanup on unmount.
  useEffect(() => {
    const fr = document.getElementById('plFrame');
    let dio = null;
    if (fr && !reduceRef.current) {
      dio = new IntersectionObserver(
        (es) => {
          es.forEach((e) => {
            if (e.isIntersecting && demoRef.current.playing && !runningRef.current) runDemo();
          });
        },
        { threshold: 0.35 }
      );
      dio.observe(fr);
    }
    return () => {
      if (dio) dio.disconnect();
      clearDemo();
      if (rcRaf.current) cancelAnimationFrame(rcRaf.current);
      clearTimeout(flashTRef.current);
    };
  }, [runDemo, clearDemo]);

  // ── Demo derived values (identical math to the design export) ──
  const dPaint = calcPaint(demo.dh);
  const dPaintCost = dPaint * 3.2;
  const dGlaistCost = dPaint * 4.5;
  const baseNet = 6626.45 - 152.66 * 3.2 - 152.66 * 4.5;
  const dNet = baseNet + dPaintCost + dGlaistCost;
  const dGross = dNet * 1.21;

  const switchLang = (lng) => {
    changeAppLanguage(lng);
    navigate(lng === 'en' ? '/en' : '/');
  };

  const eyebrowTick = <span style={{ width: 22, height: 1, background: 'var(--line2)', display: 'inline-block' }} />;
  const steps = t('landing.steps.items', { returnObjects: true });
  const readsList = t('landing.reads.list', { returnObjects: true });
  const chips = t('landing.reads.chips', { returnObjects: true });
  const trustCards = t('landing.trust.cards', { returnObjects: true });
  const audienceCards = t('landing.audience.cards', { returnObjects: true });
  const tiers = t('landing.pricing.tiers', { returnObjects: true });

  return (
    <div id="plr" data-palette={PALETTE}>
      {/* film grain overlay */}
      <div className="plgrain" aria-hidden style={{ position: 'fixed', inset: 0, zIndex: 40, pointerEvents: 'none', opacity: 'var(--grainop)' }} />

      {/* ═══════════ NAV ═══════════ */}
      <header style={{ position: 'sticky', top: 0, zIndex: 50, background: 'color-mix(in srgb, var(--bg) 86%, transparent)', backdropFilter: 'blur(12px)', borderBottom: '1px solid var(--line)' }}>
        <div className="pl-wrap" style={{ height: 64, display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 24 }}>
          <a href="#virsus" style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <PathonMark icon={26} />
            <span style={{ fontFamily: sora, fontWeight: 700, letterSpacing: '-0.02em', fontSize: 19 }}>Pathon</span>
          </a>
          <nav className="pl-navlinks" style={{ alignItems: 'center', gap: 32, fontSize: 14, color: 'var(--mut)' }}>
            <a href="#galimybes">{t('landing.nav.galimybes')}</a>
            <a href="#kaip-veikia">{t('landing.nav.kaipVeikia')}</a>
            <Link to="/duk">{t('landing.nav.duk')}</Link>
            <a href="#kainos">{t('landing.nav.kainos')}</a>
          </nav>
          <div className="pl-navauth" style={{ alignItems: 'center', gap: 18 }}>
            <Link className="pl-login" to="/login" style={{ fontSize: 14, color: 'var(--mut)' }}>{t('landing.nav.login')}</Link>
            <Link to="/register" className="pl-navbtn">{t('landing.nav.cta')}</Link>
          </div>
        </div>
      </header>

      {/* ═══════════ HERO ═══════════ */}
      <section id="virsus" onMouseMove={heroMove} onMouseLeave={heroLeave} style={{ position: 'relative', overflow: 'hidden', borderBottom: '1px solid var(--line)' }}>
        {/* drafting-paper grid */}
        <div aria-hidden style={{ position: 'absolute', inset: 0, pointerEvents: 'none', backgroundImage: 'linear-gradient(color-mix(in srgb, var(--ink) 4%, transparent) 1px, transparent 1px), linear-gradient(90deg, color-mix(in srgb, var(--ink) 4%, transparent) 1px, transparent 1px)', backgroundSize: '56px 56px', WebkitMaskImage: 'radial-gradient(ellipse 85% 75% at 50% 40%, #000 45%, transparent 100%)', maskImage: 'radial-gradient(ellipse 85% 75% at 50% 40%, #000 45%, transparent 100%)' }} />

        {/* scanned floor plan background (parallax target) */}
        <div id="plHeroBg" data-scan={String(HERO_SCAN)} aria-hidden style={{ position: 'absolute', inset: 0, display: 'flex', alignItems: 'center', justifyContent: 'center', pointerEvents: 'none', willChange: 'transform', WebkitMaskImage: 'radial-gradient(ellipse 75% 68% at 50% 46%, #000 45%, transparent 98%)', maskImage: 'radial-gradient(ellipse 75% 68% at 50% 46%, #000 45%, transparent 98%)' }}>
          <svg id="plPlanSvg" viewBox="0 0 1180 620" style={{ width: 1180, maxWidth: '100%', height: 'auto' }} preserveAspectRatio="xMidYMid meet">
            <g fill="none" stroke="var(--planink)" strokeWidth="1.6">
              <path d="M60 60 H1120 V560 H60 Z" />
              <line x1="460" y1="60" x2="460" y2="560" />
              <line x1="800" y1="60" x2="800" y2="330" />
              <line x1="460" y1="330" x2="1120" y2="330" />
              <line x1="690" y1="330" x2="690" y2="560" />
              <line x1="920" y1="330" x2="920" y2="560" />
            </g>
            <g stroke="var(--planink)" strokeWidth="4">
              <line x1="140" y1="60" x2="300" y2="60" />
              <line x1="560" y1="60" x2="720" y2="60" />
              <line x1="880" y1="60" x2="1040" y2="60" />
            </g>
            <g fill="none" stroke="var(--planink)" strokeWidth="1.2">
              <path d="M460 400 a52 52 0 0 1 52 -52" />
              <path d="M690 470 a44 44 0 0 1 44 -44" />
              <path d="M920 400 a44 44 0 0 1 44 -44" />
            </g>
            <g className="plzone" style={{ animationDelay: '0.9s' }}>
              <rect x="64" y="64" width="392" height="492" fill="var(--acc)" opacity="0.10" />
              <text x="260" y="300" textAnchor="middle" fontFamily={mono} fontSize="15" fill="var(--acc)" opacity="0.8">{t('landing.heroSvg.a1')}</text>
              <text x="260" y="324" textAnchor="middle" fontFamily={mono} fontSize="11" fill="var(--mut)" opacity="0.8">{t('landing.heroSvg.tag1')}</text>
            </g>
            <g className="plzone" style={{ animationDelay: '2.2s' }}>
              <rect x="464" y="64" width="332" height="262" fill="var(--acc)" opacity="0.09" />
              <text x="630" y="188" textAnchor="middle" fontFamily={mono} fontSize="14" fill="var(--acc)" opacity="0.8">{t('landing.heroSvg.a2')}</text>
              <text x="630" y="210" textAnchor="middle" fontFamily={mono} fontSize="11" fill="var(--mut)" opacity="0.8">{t('landing.heroSvg.h')}</text>
            </g>
            <g className="plzone" style={{ animationDelay: '3.4s' }}>
              <rect x="804" y="64" width="312" height="262" fill="var(--acc)" opacity="0.09" />
              <text x="960" y="200" textAnchor="middle" fontFamily={mono} fontSize="14" fill="var(--acc)" opacity="0.8">{t('landing.heroSvg.a3')}</text>
            </g>
            <g className="plzone" style={{ animationDelay: '2.4s' }}>
              <rect x="464" y="334" width="222" height="222" fill="var(--acc)" opacity="0.08" />
              <text x="575" y="450" textAnchor="middle" fontFamily={mono} fontSize="13" fill="var(--acc)" opacity="0.8">{t('landing.heroSvg.a4')}</text>
            </g>
            <g className="plzone" style={{ animationDelay: '3.7s' }}>
              <rect x="924" y="334" width="192" height="222" fill="var(--acc)" opacity="0.08" />
              <text x="1020" y="450" textAnchor="middle" fontFamily={mono} fontSize="13" fill="var(--acc)" opacity="0.8">{t('landing.heroSvg.a5')}</text>
            </g>
            <g className="plzone" style={{ animationDelay: '2.0s' }}>
              <line x1="430" y1="376" x2="490" y2="376" stroke="var(--acc)" strokeWidth="1" opacity="0.7" />
              <line x1="460" y1="346" x2="460" y2="406" stroke="var(--acc)" strokeWidth="1" opacity="0.7" />
              <circle cx="460" cy="376" r="10" fill="none" stroke="var(--acc)" strokeWidth="1" opacity="0.7" />
              <rect x="474" y="352" width="66" height="20" rx="4" fill="var(--bg1)" stroke="var(--acc)" strokeWidth="0.8" opacity="0.9" />
              <text x="507" y="366" textAnchor="middle" fontFamily={mono} fontSize="11" fill="var(--acc)">{t('landing.heroSvg.count')}</text>
            </g>
            <g>
              <line className="pldim" x1="60" y1="34" x2="460" y2="34" stroke="var(--acc)" strokeWidth="0.9" opacity="0.55" style={{ animationDelay: '0.6s' }} />
              <line x1="60" y1="28" x2="60" y2="40" stroke="var(--planink)" strokeWidth="1.2" />
              <line x1="460" y1="28" x2="460" y2="40" stroke="var(--planink)" strokeWidth="1.2" />
              <g className="plzone" style={{ animationDelay: '1.2s' }}>
                <text x="260" y="26" textAnchor="middle" fontFamily={mono} fontSize="11" fill="var(--mut)" opacity="0.85">4 240</text>
              </g>
            </g>
            {/* hover highlights (mouse instrument) */}
            {heroRooms.map((r) => (
              <g key={r.id} className="hz" data-on={String(hoverRoom === r.id)}>
                <rect x={r.x0 + 4} y={r.y0 + 4} width={r.x1 - r.x0 - 8} height={r.y1 - r.y0 - 8} fill="var(--acc)" opacity="0.14" />
                <rect x={r.x0 + 4} y={r.y0 + 4} width={r.x1 - r.x0 - 8} height={r.y1 - r.y0 - 8} fill="none" stroke="var(--acc)" strokeWidth="1.4" opacity="0.7" />
              </g>
            ))}
            <g className="plbeam">
              <rect x="-90" y="40" width="90" height="540" fill="url(#plgrad)" />
              <line x1="0" y1="40" x2="0" y2="580" stroke="var(--acc)" strokeWidth="1.6" opacity="0.65" />
              <line x1="0" y1="34" x2="0" y2="46" stroke="var(--acc)" strokeWidth="3" opacity="0.9" />
              <line x1="0" y1="574" x2="0" y2="586" stroke="var(--acc)" strokeWidth="3" opacity="0.9" />
            </g>
            <defs>
              <linearGradient id="plgrad" x1="0" y1="0" x2="1" y2="0">
                <stop offset="0" stopColor="var(--acc)" stopOpacity="0" />
                <stop offset="1" stopColor="var(--acc)" stopOpacity="0.07" />
              </linearGradient>
            </defs>
          </svg>
        </div>

        {/* cursor spotlight */}
        <div id="plSpot" aria-hidden style={{ position: 'absolute', left: 0, top: 0, width: 480, height: 480, borderRadius: '50%', background: 'radial-gradient(circle, var(--frameglow), transparent 62%)', pointerEvents: 'none', zIndex: 1 }} />

        <div style={{ position: 'relative', zIndex: 2, maxWidth: 1200, margin: '0 auto', padding: '112px 24px 100px', display: 'flex', flexDirection: 'column', alignItems: 'center', textAlign: 'center' }}>
          <div className="plu1" style={{ display: 'flex', alignItems: 'center', gap: 10, fontFamily: mono, fontSize: 11, letterSpacing: '0.18em', textTransform: 'uppercase', color: 'var(--mut)' }}>
            {eyebrowTick}
            {t('landing.hero.eyebrow')}
            {eyebrowTick}
          </div>
          <h1 className="pl-h1 plu2" style={{ margin: '26px 0 0', fontFamily: sora, fontWeight: 700, letterSpacing: '-0.035em', lineHeight: 1.02, fontSize: 70, maxWidth: 1000, textWrap: 'balance' }}>
            {t('landing.hero.titleA')}<br />{t('landing.hero.titleB')}
          </h1>
          <p className="pl-hsub plu3" style={{ margin: '26px 0 0', maxWidth: 640, fontSize: 17.5, lineHeight: 1.6, color: 'var(--ink2)' }}>
            {t('landing.hero.sub1')}
            <span style={{ fontFamily: mono, fontSize: 16 }}>€200–500</span>
            {t('landing.hero.sub2')}
          </p>
          <div className="pl-ctas plu4" style={{ marginTop: 36, display: 'flex', alignItems: 'center', gap: 14 }}>
            <Link to="/register" className="pl-btn-primary">
              {t('landing.hero.ctaPrimary')}
              <svg width="15" height="15" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round"><path d="M3 8h10M9 4l4 4-4 4" /></svg>
            </Link>
            <a href="#produktas" className="pl-btn-ghost">
              <svg width="13" height="13" viewBox="0 0 16 16" fill="currentColor"><path d="M4 2.5v11l9-5.5z" /></svg>
              {t('landing.hero.ctaDemo')}
            </a>
          </div>
          <p className="plu5" style={{ margin: '22px 0 0', fontFamily: mono, fontSize: 12, color: 'var(--mut)' }}>{t('landing.hero.micro')}</p>
        </div>

        {/* measuring crosshair (follows the mouse) */}
        <div id="plCh" aria-hidden style={{ position: 'absolute', inset: 0, pointerEvents: 'none', zIndex: 3 }}>
          <span id="plChV" style={{ position: 'absolute', top: 0, bottom: 0, width: 1, background: 'color-mix(in srgb, var(--acc) 38%, transparent)' }} />
          <span id="plChH" style={{ position: 'absolute', left: 0, right: 0, height: 1, background: 'color-mix(in srgb, var(--acc) 38%, transparent)' }} />
          <span id="plChTip" style={{ position: 'absolute', fontFamily: mono, fontSize: 11, lineHeight: 1.5, color: 'var(--acc)', background: 'color-mix(in srgb, var(--bg1) 88%, transparent)', border: '1px solid var(--line2)', borderRadius: 6, padding: '4px 9px', whiteSpace: 'nowrap' }} />
        </div>
      </section>

      {/* ═══════════ 01 · PRODUCT DEMO ═══════════ */}
      <section id="produktas" style={{ position: 'relative', borderBottom: '1px solid var(--line)' }}>
        <div className="pl-sec" style={{ padding: '88px 24px' }}>
          <div id="plFrame" style={{ willChange: 'transform' }}>
            <div data-reveal="" style={{ position: 'relative', borderRadius: 14, border: '1px solid var(--line2)', background: 'var(--bg1)', overflow: 'hidden', boxShadow: '0 0 0 1px color-mix(in srgb, var(--acc) 14%, transparent), inset 0 1px 0 color-mix(in srgb, var(--bg1) 60%, transparent), 0 40px 90px -40px var(--shadow)' }}>

              {/* animated cursor */}
              <div className="dcur" data-click={String(demo.curClick)} data-hide={String(!demo.playing)} style={{ position: 'absolute', left: demo.curL, top: demo.curT, zIndex: 30, pointerEvents: 'none', transition: 'left .95s cubic-bezier(.4,.1,.2,1), top .95s cubic-bezier(.4,.1,.2,1), opacity .4s ease' }}>
                <span className="dring" />
                <svg width="20" height="20" viewBox="0 0 24 24" style={{ position: 'relative' }}><path d="M5 3l14 8-6.5 1.5L9 19z" fill="var(--ink)" stroke="var(--bg1)" strokeWidth="1.4" /></svg>
              </div>

              {/* Prielaidos popover */}
              <div className="dvis" data-vis={String(demo.popVis)} style={{ position: 'absolute', right: '4%', top: '15%', width: 250, background: 'var(--bg1)', border: '1px solid var(--line2)', borderRadius: 10, boxShadow: '0 22px 55px -18px var(--shadow)', padding: '14px 16px', zIndex: 20 }}>
                <div style={{ fontFamily: mono, fontSize: 10, letterSpacing: '0.14em', textTransform: 'uppercase', color: 'var(--mut)' }}>{t('landing.demo.popTitle')}</div>
                <div style={{ marginTop: 10, display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12 }}>
                  <span style={{ fontSize: 13 }}>{t('landing.demo.popHeight')}</span>
                  <span style={{ display: 'inline-flex', alignItems: 'center', gap: 8 }}>
                    <span style={{ fontFamily: mono, fontSize: 14, fontVariantNumeric: 'tabular-nums', border: '1px solid var(--line2)', borderRadius: 6, padding: '4px 10px', background: 'var(--bg)' }}>{fmt(demo.dh, 2)} m</span>
                    <span style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
                      <span className="dstep" data-on={String(demo.stepUpOn)} onClick={() => step(1)} style={{ width: 18, height: 14, display: 'inline-flex', alignItems: 'center', justifyContent: 'center', border: '1px solid var(--line2)', borderRadius: 3, color: 'var(--mut)', fontSize: 9, lineHeight: 1, transition: 'color .15s ease, border-color .15s ease' }}>▲</span>
                      <span className="dstep" onClick={() => step(-1)} style={{ width: 18, height: 14, display: 'inline-flex', alignItems: 'center', justifyContent: 'center', border: '1px solid var(--line2)', borderRadius: 3, color: 'var(--mut)', fontSize: 9, lineHeight: 1, transition: 'color .15s ease, border-color .15s ease' }}>▼</span>
                    </span>
                  </span>
                </div>
                <div style={{ marginTop: 10, fontSize: 11.5, lineHeight: 1.45, color: 'var(--mut)' }}>{t('landing.demo.popNote')}</div>
              </div>

              {/* Export dropdown */}
              <div className="dvis" data-vis={String(demo.expVis)} style={{ position: 'absolute', right: '2%', top: '13%', width: 230, background: 'var(--bg1)', border: '1px solid var(--line2)', borderRadius: 10, boxShadow: '0 22px 55px -18px var(--shadow)', padding: 8, zIndex: 20 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '9px 10px', borderRadius: 7, background: 'color-mix(in srgb, var(--acc) 8%, transparent)', fontSize: 13 }}>
                  <span style={{ fontFamily: mono, fontSize: 10, color: 'var(--ok)', border: '1px solid color-mix(in srgb, var(--ok) 40%, transparent)', borderRadius: 3, padding: '1px 5px' }}>XLSX</span>
                  {t('landing.demo.expXlsx')}
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '9px 10px', borderRadius: 7, fontSize: 13 }}>
                  <span style={{ fontFamily: mono, fontSize: 10, color: 'var(--bad)', border: '1px solid color-mix(in srgb, var(--bad) 40%, transparent)', borderRadius: 3, padding: '1px 5px' }}>PDF</span>
                  {t('landing.demo.expPdf')}
                </div>
              </div>

              {/* project top bar */}
              <div style={{ display: 'flex', alignItems: 'center', gap: 12, minHeight: 52, padding: '8px 16px', borderBottom: '1px solid var(--line)', flexWrap: 'wrap' }}>
                <span style={{ display: 'inline-flex', alignItems: 'center', gap: 7, fontFamily: mono, fontSize: 10, letterSpacing: '0.1em', textTransform: 'uppercase', color: 'var(--acc)' }}>
                  <span style={{ width: 7, height: 7, borderRadius: '50%', background: 'var(--acc)' }} />
                  {t('landing.demo.badge')}
                </span>
                <span style={{ fontSize: 13, fontWeight: 600 }}>{t('landing.demo.project')}</span>
                <span style={{ fontFamily: mono, fontSize: 10, letterSpacing: '0.06em', textTransform: 'uppercase', padding: '2px 7px', borderRadius: 3, border: '1px solid var(--line2)', color: 'var(--mut)', background: 'var(--bg1)' }}>{t('landing.demo.tag')}</span>
                <span style={{ flex: 1 }} />
                <span style={{ display: 'flex', alignItems: 'baseline', gap: 6, paddingRight: 14, borderRight: '1px solid var(--line)' }}>
                  <span style={{ fontSize: 10, letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--mut)', fontWeight: 600 }}>{t('landing.demo.noVat')}</span>
                  <span style={{ fontFamily: mono, fontSize: 13, color: 'var(--ink2)', fontVariantNumeric: 'tabular-nums' }}>{fmt(dNet, 2)} €</span>
                </span>
                <span style={{ display: 'flex', alignItems: 'baseline', gap: 6 }}>
                  <span style={{ fontSize: 10, letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--mut)', fontWeight: 600 }}>{t('landing.demo.withVat')}</span>
                  <span style={{ fontFamily: mono, fontSize: 17, fontWeight: 600, fontVariantNumeric: 'tabular-nums' }}>{fmt(dGross, 2)} €</span>
                </span>
                <span className="plhbtn dbtn" data-on={String(demo.popVis)} onClick={() => { takeover(); patch({ popVis: !demoRef.current.popVis, expVis: false }); }} style={{ display: 'inline-flex', alignItems: 'center', gap: 6, height: 30, padding: '0 12px', border: '1px solid var(--line2)', background: 'var(--bg1)', borderRadius: 6, fontSize: 12, fontWeight: 500, color: 'var(--ink2)', transition: 'all .2s ease' }}>{t('landing.demo.assumptions')}</span>
                <span className="dbtn" onClick={() => { takeover(); patch({ expVis: !demoRef.current.expVis, popVis: false }); }} style={{ display: 'inline-flex', alignItems: 'center', gap: 6, height: 30, padding: '0 12px', background: 'var(--acc)', color: 'var(--accink)', borderRadius: 6, fontSize: 12, fontWeight: 500 }}>{t('landing.demo.exportBtn')}</span>
              </div>

              {/* tab bar + player control */}
              <div style={{ display: 'flex', alignItems: 'center', paddingLeft: 16, paddingRight: 12, borderBottom: '1px solid var(--line)', fontSize: 13 }}>
                <span className="dtab" data-on={String(demo.tab === 'brez')} onClick={() => { takeover(); patch({ tab: 'brez' }); }}>{t('landing.demo.tabBrez')}</span>
                <span className="dtab" data-on={String(demo.tab === 'kiek')} onClick={() => { takeover(); patch({ tab: 'kiek' }); }}>{t('landing.demo.tabKiek')}</span>
                <span style={{ padding: '10px 16px', color: 'var(--mut)', fontWeight: 500, opacity: 0.55 }}>{t('landing.demo.tabAsist')}</span>
                <span style={{ flex: 1 }} />
                <button onClick={toggleDemo} style={{ display: 'inline-flex', alignItems: 'center', gap: 7, fontFamily: mono, fontSize: 11, color: 'var(--mut)', background: 'none', border: '1px solid var(--line2)', borderRadius: 6, padding: '5px 12px', cursor: 'pointer', transition: 'color .15s ease, border-color .15s ease' }}>
                  {demo.playing ? t('landing.demo.pause') : t('landing.demo.play')}
                </button>
              </div>

              {/* plan viewer + positions panel */}
              <div className="pl-framebody" data-tab={demo.tab === 'kiek' ? 'kiekiai' : 'brezinys'} style={{ display: 'grid', gridTemplateColumns: '1.25fr 1fr' }}>
                <div className="dplanpane" style={{ position: 'relative', background: 'var(--bg)', padding: 26, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                  <svg viewBox="0 0 520 340" style={{ width: '100%', height: 'auto' }}>
                    <rect x="0" y="0" width="520" height="340" fill="var(--bg2)" opacity="0.5" />
                    <g fill="none" stroke="color-mix(in srgb, var(--ink) 38%, transparent)" strokeWidth="1.3">
                      <path d="M30 26 H490 V314 H30 Z" />
                      <line x1="210" y1="26" x2="210" y2="314" />
                      <line x1="360" y1="26" x2="360" y2="170" />
                      <line x1="210" y1="170" x2="490" y2="170" />
                      <line x1="316" y1="170" x2="316" y2="314" />
                      <line x1="410" y1="170" x2="410" y2="314" />
                    </g>
                    <g stroke="color-mix(in srgb, var(--ink) 55%, transparent)" strokeWidth="3.4">
                      <line x1="60" y1="26" x2="140" y2="26" />
                      <line x1="250" y1="26" x2="330" y2="26" />
                      <line x1="390" y1="26" x2="460" y2="26" />
                    </g>
                    {/* clickable room zones */}
                    <rect className="dz" onClick={() => manualSelect('svet')} x="32" y="28" width="176" height="284" fill="var(--acc)" opacity="0.13" />
                    <rect className="dz" onClick={() => manualSelect('mieg')} x="212" y="28" width="146" height="140" fill="var(--ok)" opacity="0.12" />
                    <rect className="dz" onClick={() => manualSelect('mieg')} x="362" y="28" width="126" height="140" fill="var(--acc)" opacity="0.09" />
                    <rect className="dz" onClick={() => manualSelect('von')} x="212" y="172" width="102" height="140" fill="var(--warn)" opacity="0.13" />
                    <rect className="dz" onClick={() => manualSelect('von')} x="318" y="172" width="90" height="140" fill="var(--ok)" opacity="0.10" />
                    <rect className="dz" onClick={() => manualSelect('von')} x="412" y="172" width="76" height="140" fill="var(--acc)" opacity="0.09" />
                    {/* selection outlines + chips */}
                    <g className="dzsel" data-sel={String(demo.sel === 'svet')}>
                      <rect x="32" y="28" width="176" height="284" fill="none" stroke="var(--acc)" strokeWidth="1.6" />
                      <rect x="52" y="150" width="136" height="26" rx="6" fill="var(--bg1)" stroke="var(--line2)" strokeWidth="0.8" />
                      <circle cx="66" cy="163" r="3" fill="var(--ok)" />
                      <text x="76" y="167" fontFamily={mono} fontSize="10.5" fill="var(--ink)">{t('landing.demo.zoneSvet')}</text>
                    </g>
                    <g className="dzsel" data-sel={String(demo.sel === 'mieg')}>
                      <rect x="212" y="28" width="146" height="140" fill="none" stroke="var(--acc)" strokeWidth="1.6" />
                      <rect x="222" y="86" width="126" height="26" rx="6" fill="var(--bg1)" stroke="var(--line2)" strokeWidth="0.8" />
                      <circle cx="236" cy="99" r="3" fill="var(--ok)" />
                      <text x="246" y="103" fontFamily={mono} fontSize="10.5" fill="var(--ink)">{t('landing.demo.zoneMieg')}</text>
                    </g>
                    <g className="dzsel" data-sel={String(demo.sel === 'von')}>
                      <rect x="212" y="172" width="102" height="140" fill="none" stroke="var(--warn)" strokeWidth="1.6" />
                      <rect x="216" y="228" width="120" height="26" rx="6" fill="var(--bg1)" stroke="var(--line2)" strokeWidth="0.8" />
                      <circle cx="230" cy="241" r="3" fill="var(--warn)" />
                      <text x="240" y="245" fontFamily={mono} fontSize="10.5" fill="var(--ink)">{t('landing.demo.zoneVon')}</text>
                    </g>
                    <g fontFamily={mono}>
                      <rect x="380" y="288" width="106" height="22" fill="var(--bg1)" stroke="var(--line2)" strokeWidth="0.6" />
                      <text x="388" y="298" fontSize="6.5" fill="var(--ink2)">M 1:50</text>
                      <text x="388" y="306" fontSize="6.5" fill="var(--mut)">SA-01</text>
                      <text x="430" y="298" fontSize="6.5" fill="var(--ink2)">74,2 m²</text>
                      <text x="430" y="306" fontSize="6.5" fill="var(--mut)">{t('landing.demo.planRooms')}</text>
                    </g>
                  </svg>
                </div>

                <div className="pl-frame-side" style={{ borderLeft: '1px solid var(--line)', background: 'var(--bg1)', fontSize: 12 }}>
                  <div style={{ padding: '12px 14px 8px', fontFamily: mono, fontSize: 10, letterSpacing: '0.14em', textTransform: 'uppercase', color: 'var(--mut)' }}>{t('landing.demo.posTitle')}</div>
                  <div style={{ padding: '4px 14px 6px', fontSize: 10, letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--mut)', fontWeight: 600, borderBottom: '1px solid var(--line)' }}>{t('landing.demo.secPaint')}</div>
                  <div style={{ display: 'flex', flexDirection: 'column' }}>
                    <div className="drow" data-flash={String(demo.rowFlash)} style={{ display: 'flex', alignItems: 'flex-start', gap: 8, padding: '7px 14px', borderBottom: '1px solid color-mix(in srgb, var(--line) 55%, transparent)' }}>
                      <span className="pl-dot" style={{ background: 'var(--ok)' }} />
                      <span style={{ flex: 1, minWidth: 0 }}>
                        <span style={{ display: 'block', color: 'var(--ink)', lineHeight: 1.35 }}>{t('landing.demo.rowPaint')}</span>
                        <span style={{ display: 'block', fontFamily: mono, fontSize: 11, color: 'var(--mut)', marginTop: 2 }}>{fmt(dPaint, 1)} m² · 3,20 €/m²</span>
                      </span>
                      <span style={{ fontFamily: mono, fontVariantNumeric: 'tabular-nums', color: 'var(--ink2)' }}>{fmt(dPaintCost, 2)} €</span>
                    </div>
                    <div className="drow" data-flash={String(demo.rowFlash)} style={{ display: 'flex', alignItems: 'flex-start', gap: 8, padding: '7px 14px', borderBottom: '1px solid color-mix(in srgb, var(--line) 55%, transparent)' }}>
                      <span className="pl-dot" style={{ background: 'var(--ok)' }} />
                      <span style={{ flex: 1, minWidth: 0 }}>
                        <span style={{ display: 'block', color: 'var(--ink)', lineHeight: 1.35 }}>{t('landing.demo.rowGlaist')}</span>
                        <span style={{ display: 'block', fontFamily: mono, fontSize: 11, color: 'var(--mut)', marginTop: 2 }}>{fmt(dPaint, 1)} m² · 4,50 €/m²</span>
                      </span>
                      <span style={{ fontFamily: mono, fontVariantNumeric: 'tabular-nums', color: 'var(--ink2)' }}>{fmt(dGlaistCost, 2)} €</span>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8, padding: '7px 14px', borderBottom: '1px solid color-mix(in srgb, var(--line) 55%, transparent)', background: 'color-mix(in srgb, var(--warn) 6%, transparent)' }}>
                      <span className="pl-dot" style={{ background: 'var(--warn)' }} />
                      <span style={{ flex: 1, minWidth: 0 }}>
                        <span style={{ display: 'block', color: 'var(--ink)', lineHeight: 1.35 }}>{t('landing.demo.rowAngok')}</span>
                        <span style={{ display: 'block', fontFamily: mono, fontSize: 11, color: 'var(--mut)', marginTop: 2 }}>{t('landing.demo.angokMeta')}</span>
                      </span>
                      <span style={{ fontFamily: mono, color: 'var(--mut)' }}>— €</span>
                    </div>
                    <div style={{ padding: '8px 14px 6px', fontSize: 10, letterSpacing: '0.08em', textTransform: 'uppercase', color: 'var(--mut)', fontWeight: 600, borderBottom: '1px solid var(--line)' }}>{t('landing.demo.secGkp')}</div>
                    <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8, padding: '7px 14px', borderBottom: '1px solid color-mix(in srgb, var(--line) 55%, transparent)' }}>
                      <span className="pl-dot" style={{ background: 'var(--ok)' }} />
                      <span style={{ flex: 1, minWidth: 0 }}>
                        <span style={{ display: 'block', color: 'var(--ink)', lineHeight: 1.35 }}>{t('landing.demo.rowGkp')}</span>
                        <span style={{ display: 'block', fontFamily: mono, fontSize: 11, color: 'var(--mut)', marginTop: 2 }}>{t('landing.demo.gkpMeta')}</span>
                      </span>
                      <span style={{ fontFamily: mono, fontVariantNumeric: 'tabular-nums', color: 'var(--ink2)' }}>1 261,40 €</span>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8, padding: '7px 14px', borderBottom: '1px solid color-mix(in srgb, var(--line) 55%, transparent)', background: 'color-mix(in srgb, var(--bad) 7%, transparent)' }}>
                      <span className="pl-dot" style={{ background: 'var(--bad)' }} />
                      <span style={{ flex: 1, minWidth: 0 }}>
                        <span style={{ display: 'block', color: 'var(--ink)', lineHeight: 1.35 }}>{t('landing.demo.rowLed')}</span>
                        <span style={{ display: 'block', fontFamily: mono, fontSize: 11, color: 'var(--mut)', marginTop: 2 }}>{t('landing.demo.ledMeta')}</span>
                      </span>
                      <span style={{ fontFamily: mono, color: 'var(--mut)' }}>— €</span>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'flex-start', gap: 8, padding: '7px 14px', borderBottom: '1px solid color-mix(in srgb, var(--line) 55%, transparent)' }}>
                      <span className="pl-dot" style={{ background: 'var(--ok)' }} />
                      <span style={{ flex: 1, minWidth: 0 }}>
                        <span style={{ display: 'block', color: 'var(--ink)', lineHeight: 1.35 }}>{t('landing.demo.rowGrind')}</span>
                        <span style={{ display: 'block', fontFamily: mono, fontSize: 11, color: 'var(--mut)', marginTop: 2 }}>{t('landing.demo.grindMeta')}</span>
                      </span>
                      <span style={{ fontFamily: mono, fontVariantNumeric: 'tabular-nums', color: 'var(--ink2)' }}>239,44 €</span>
                    </div>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 14, padding: '10px 14px', borderTop: '1px solid var(--line)', fontFamily: mono, fontSize: 10.5, color: 'var(--mut)' }}>
                    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5 }}><span style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--ok)' }} />{t('landing.demo.legendOk')}</span>
                    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5 }}><span style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--warn)' }} />{t('landing.demo.legendWarn')}</span>
                    <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5 }}><span style={{ width: 6, height: 6, borderRadius: '50%', background: 'var(--bad)' }} />{t('landing.demo.legendBad')}</span>
                  </div>
                </div>
              </div>
            </div>
          </div>
          <p data-reveal="" style={{ margin: '18px 0 0', textAlign: 'center', fontFamily: mono, fontSize: 11.5, color: 'var(--mut)' }}>{t('landing.demo.hint')}</p>
        </div>
      </section>

      {/* ═══════════ 02 · KAIP VEIKIA ═══════════ */}
      <section id="kaip-veikia" style={{ borderBottom: '1px solid var(--line)' }}>
        <div className="pl-sec">
          <div className="pl-eyebrow" data-reveal="">{t('landing.steps.eyebrow')}</div>
          <h2 className="pl-h2" data-reveal="" style={{ transitionDelay: '70ms' }}>{t('landing.steps.title')}</h2>
          <div className="pl-grid3" style={{ marginTop: 56, display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 0, borderTop: '1px solid var(--line2)', position: 'relative' }}>
            {steps.map((s, i) => (
              <div key={i} data-reveal="" style={{ transitionDelay: `${i * 100}ms`, padding: `32px ${i === 2 ? 0 : 28}px 8px 0`, position: 'relative' }}>
                <span style={{ position: 'absolute', top: -5, left: 0, width: 1, height: 10, background: 'var(--line2)' }} />
                <div className="pl-step-num">{String(i + 1).padStart(2, '0')}</div>
                <div className="pl-step-title">{s.t}</div>
                <p style={{ margin: '10px 0 0', fontSize: 14.5, lineHeight: 1.55, color: 'var(--ink2)', maxWidth: 320 }}>{s.d}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ═══════════ 03 · KĄ PERSKAITO ═══════════ */}
      <section id="galimybes" style={{ borderBottom: '1px solid var(--line)', background: 'var(--bg1)' }}>
        <div className="pl-sec">
          <div className="pl-eyebrow" data-reveal="">{t('landing.reads.eyebrow')}</div>
          <h2 className="pl-h2" data-reveal="" style={{ transitionDelay: '70ms' }}>{t('landing.reads.title')}</h2>
          <div className="pl-grid2" style={{ marginTop: 56, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 48, alignItems: 'start' }}>
            <div data-reveal="" style={{ display: 'flex', flexDirection: 'column', borderTop: '1px solid var(--line2)' }}>
              {readsList.map((label, i) => (
                <div key={i} className="pl-readrow">
                  <span className="n">{String(i + 1).padStart(2, '0')}</span>
                  <span style={{ fontSize: 15.5 }}>{label}</span>
                </div>
              ))}
            </div>
            <div data-reveal="" style={{ transitionDelay: '120ms' }}>
              <div style={{ fontFamily: mono, fontSize: 10.5, letterSpacing: '0.16em', textTransform: 'uppercase', color: 'var(--mut)', marginBottom: 18 }}>{t('landing.reads.chipsLabel')}</div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 10 }}>
                {chips.map((c, i) => (
                  <span key={i} className="pl-chip">{c.label} <span className="v">{c.val}</span></span>
                ))}
              </div>
              <p style={{ margin: '24px 0 0', fontSize: 14, lineHeight: 1.6, color: 'var(--mut)', maxWidth: 420 }}>{t('landing.reads.note')}</p>
            </div>
          </div>
        </div>
      </section>

      {/* ═══════════ 04 · PASITIKĖJIMO SISTEMA ═══════════ */}
      <section style={{ borderBottom: '1px solid var(--line)' }}>
        <div className="pl-sec">
          <div className="pl-eyebrow" data-reveal="">{t('landing.trust.eyebrow')}</div>
          <h2 className="pl-trust-copy pl-h2" data-reveal="" style={{ transitionDelay: '70ms', lineHeight: 1.12, maxWidth: 860, textWrap: 'balance' }}>
            {t('landing.trust.titleA')}<br />{t('landing.trust.titleB')}
          </h2>
          <p className="pl-sub" data-reveal="" style={{ transitionDelay: '140ms' }}>{t('landing.trust.sub')}</p>

          <div className="pl-grid2" style={{ marginTop: 56, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 48, alignItems: 'start' }}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
              {trustCards.map((c, i) => (
                <div key={i} data-reveal="" style={{ transitionDelay: `${i * 90}ms`, display: 'flex', gap: 16, padding: '20px 22px', border: '1px solid var(--line)', borderRadius: 12, background: 'var(--bg1)' }}>
                  <span style={{ width: 10, height: 10, borderRadius: '50%', background: `var(--${['ok', 'warn', 'bad'][i]})`, marginTop: 6, flexShrink: 0 }} />
                  <span>
                    <span style={{ display: 'block', fontWeight: 600, fontSize: 15.5 }}>{c.t}</span>
                    <span style={{ display: 'block', marginTop: 4, fontSize: 14, lineHeight: 1.5, color: 'var(--ink2)' }}>{c.d}</span>
                  </span>
                </div>
              ))}
            </div>

            <div data-reveal="" style={{ transitionDelay: '120ms', border: '1px solid var(--line2)', borderRadius: 12, background: 'var(--bg1)', overflow: 'hidden' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '13px 18px', borderBottom: '1px solid var(--line)' }}>
                <span style={{ fontFamily: mono, fontSize: 11, letterSpacing: '0.14em', textTransform: 'uppercase', color: 'var(--mut)' }}>{t('landing.trust.panelTitle')}</span>
                <span style={{ fontFamily: mono, fontSize: 11, color: 'var(--warn)' }}>{t('landing.trust.panelCount')}</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '13px 18px', borderBottom: '1px solid color-mix(in srgb, var(--line) 60%, transparent)', background: 'color-mix(in srgb, var(--bad) 6%, transparent)' }}>
                <span style={{ width: 7, height: 7, borderRadius: '50%', background: 'var(--bad)', flexShrink: 0 }} />
                <span style={{ flex: 1, fontSize: 13.5 }}>{t('landing.trust.rowLed')} <span style={{ fontFamily: mono, fontSize: 12.5 }}>12,4 m</span></span>
                <span style={{ fontSize: 12, color: 'var(--mut)', border: '1px solid var(--line2)', borderRadius: 5, padding: '3px 10px' }}>{t('landing.trust.showBtn')}</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '13px 18px', borderBottom: '1px solid color-mix(in srgb, var(--line) 60%, transparent)', background: 'color-mix(in srgb, var(--warn) 5%, transparent)' }}>
                <span style={{ width: 7, height: 7, borderRadius: '50%', background: 'var(--warn)', flexShrink: 0 }} />
                <span style={{ flex: 1, fontSize: 13.5 }}>{t('landing.trust.rowAngok')} <span style={{ fontFamily: mono, fontSize: 12.5 }}>42,6 m</span></span>
                <span style={{ fontSize: 12, color: 'var(--mut)', border: '1px solid var(--line2)', borderRadius: 5, padding: '3px 10px' }}>{t('landing.trust.showBtn')}</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: 12, padding: '13px 18px', background: 'color-mix(in srgb, var(--warn) 5%, transparent)' }}>
                <span style={{ width: 7, height: 7, borderRadius: '50%', background: 'var(--warn)', flexShrink: 0 }} />
                <span style={{ flex: 1, fontSize: 13.5 }}>{t('landing.trust.rowVon')} <span style={{ fontFamily: mono, fontSize: 12.5 }}>H = 2,45</span></span>
                <span style={{ display: 'inline-flex', alignItems: 'center', gap: 5, fontSize: 12, color: 'var(--ok)', border: '1px solid color-mix(in srgb, var(--ok) 40%, transparent)', borderRadius: 5, padding: '3px 10px' }}>
                  <svg width="11" height="11" viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="M13 4L6 12l-3.5-3.5" /></svg>
                  {t('landing.trust.confirmed')}
                </span>
              </div>
              <div style={{ padding: '13px 18px', borderTop: '1px solid var(--line)', fontFamily: mono, fontSize: 11.5, color: 'var(--mut)' }}>{t('landing.trust.panelFoot')}</div>
            </div>
          </div>
        </div>
      </section>

      {/* ═══════════ 05 · GYVAS PERSKAIČIAVIMAS ═══════════ */}
      <section style={{ borderBottom: '1px solid var(--line)', background: 'var(--bg1)' }}>
        <div className="pl-sec">
          <div className="pl-grid2" style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 48, alignItems: 'center' }}>
            <div>
              <div className="pl-eyebrow" data-reveal="">{t('landing.recalc.eyebrow')}</div>
              <h2 className="pl-h2" data-reveal="" style={{ transitionDelay: '70ms', lineHeight: 1.08 }}>{t('landing.recalc.title')}</h2>
              <p className="pl-sub" data-reveal="" style={{ transitionDelay: '140ms', maxWidth: 480 }}>{t('landing.recalc.sub')}</p>
              <div data-reveal="" style={{ transitionDelay: '200ms', marginTop: 28, display: 'flex', alignItems: 'center', gap: 12 }}>
                <span style={{ fontSize: 14, color: 'var(--ink2)' }}>{t('landing.recalc.heightLabel')}</span>
                <button className="plhbtn" data-testid="rc-270" data-on={String(rcTarget === 2.7)} onClick={() => animateTo(2.7)} style={{ fontFamily: mono, fontSize: 14, padding: '8px 18px', borderRadius: 7, border: '1px solid var(--line2)', background: 'var(--bg)', color: 'var(--ink)', cursor: 'pointer', transition: 'all .15s ease' }}>2,70 m</button>
                <button className="plhbtn" data-testid="rc-320" data-on={String(rcTarget === 3.2)} onClick={() => animateTo(3.2)} style={{ fontFamily: mono, fontSize: 14, padding: '8px 18px', borderRadius: 7, border: '1px solid var(--line2)', background: 'var(--bg)', color: 'var(--ink)', cursor: 'pointer', transition: 'all .15s ease' }}>3,20 m</button>
              </div>
            </div>
            <div data-reveal="" style={{ transitionDelay: '120ms', border: '1px solid var(--line2)', borderRadius: 12, background: 'var(--bg)', overflow: 'hidden' }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '13px 20px', borderBottom: '1px solid var(--line)' }}>
                <span style={{ fontFamily: mono, fontSize: 11, letterSpacing: '0.14em', textTransform: 'uppercase', color: 'var(--mut)' }}>{t('landing.recalc.panelTitle')}</span>
                <span style={{ fontFamily: mono, fontSize: 11, color: 'var(--mut)' }}>H = <span style={{ color: 'var(--acc)' }}>{fmt(rc.h, 2)}</span> m</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: 16, padding: '17px 20px', borderBottom: '1px solid color-mix(in srgb, var(--line) 60%, transparent)' }}>
                <span style={{ fontSize: 14.5 }}>{t('landing.recalc.rowPaint')}</span>
                <span data-testid="rc-paint" style={{ fontFamily: mono, fontSize: 19, fontVariantNumeric: 'tabular-nums', color: 'var(--acc)' }}>{fmt(rc.paint, 1)} m²</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: 16, padding: '17px 20px', borderBottom: '1px solid color-mix(in srgb, var(--line) 60%, transparent)' }}>
                <span style={{ fontSize: 14.5 }}>{t('landing.recalc.rowGlaist')}</span>
                <span style={{ fontFamily: mono, fontSize: 19, fontVariantNumeric: 'tabular-nums', color: 'var(--acc)' }}>{fmt(rc.glaist, 1)} kg</span>
              </div>
              <div style={{ display: 'flex', alignItems: 'baseline', justifyContent: 'space-between', gap: 16, padding: '17px 20px' }}>
                <span style={{ fontSize: 14.5 }}>{t('landing.recalc.rowGrind')} <span style={{ fontSize: 12, color: 'var(--mut)' }}>{t('landing.recalc.grindNote')}</span></span>
                <span style={{ fontFamily: mono, fontSize: 19, fontVariantNumeric: 'tabular-nums', color: 'var(--ink2)' }}>58,4 m</span>
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ═══════════ 06 · EKSPORTAS ═══════════ */}
      <section style={{ borderBottom: '1px solid var(--line)' }}>
        <div className="pl-sec">
          <div className="pl-eyebrow" data-reveal="">{t('landing.exportSec.eyebrow')}</div>
          <h2 className="pl-h2" data-reveal="" style={{ transitionDelay: '70ms' }}>{t('landing.exportSec.title')}</h2>
          <div className="pl-docs" style={{ marginTop: 56, display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 28 }}>
            <div data-reveal="">
              <div style={{ border: '1px solid var(--line2)', borderRadius: 12, background: 'var(--bg1)', overflow: 'hidden' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '10px 16px', borderBottom: '1px solid var(--line)' }}>
                  <span style={{ fontFamily: mono, fontSize: 11, color: 'var(--mut)' }}>fx</span>
                  <span style={{ fontFamily: mono, fontSize: 12, color: 'var(--acc)', border: '1px solid var(--line)', borderRadius: 4, padding: '3px 10px', flex: 1 }}>=D8*E8</span>
                </div>
                <div style={{ fontFamily: mono, fontSize: 11.5 }}>
                  <div style={{ display: 'grid', gridTemplateColumns: '34px 2fr 0.8fr 0.9fr 0.9fr 1fr', borderBottom: '1px solid var(--line)', color: 'var(--mut)', textAlign: 'center' }}>
                    <span style={{ padding: '6px 4px' }} /><span style={{ padding: '6px 4px' }}>B</span><span style={{ padding: '6px 4px' }}>C</span><span style={{ padding: '6px 4px' }}>D</span><span style={{ padding: '6px 4px' }}>E</span><span style={{ padding: '6px 4px' }}>F</span>
                  </div>
                  <div style={{ display: 'grid', gridTemplateColumns: '34px 2fr 0.8fr 0.9fr 0.9fr 1fr', borderBottom: '1px solid color-mix(in srgb, var(--line) 60%, transparent)', color: 'var(--ink2)' }}>
                    <span style={{ padding: '7px 4px', color: 'var(--mut)', textAlign: 'center' }}>7</span><span style={{ padding: '7px 8px', fontFamily: "'Hanken Grotesk', sans-serif", fontSize: 12.5 }}>{t('landing.demo.rowPaint')}</span><span style={{ padding: '7px 4px', textAlign: 'center' }}>m²</span><span style={{ padding: '7px 8px', textAlign: 'right' }}>152,7</span><span style={{ padding: '7px 8px', textAlign: 'right' }}>3,20</span><span style={{ padding: '7px 8px', textAlign: 'right' }}>488,64</span>
                  </div>
                  <div style={{ display: 'grid', gridTemplateColumns: '34px 2fr 0.8fr 0.9fr 0.9fr 1fr', borderBottom: '1px solid color-mix(in srgb, var(--line) 60%, transparent)', color: 'var(--ink2)', background: 'color-mix(in srgb, var(--acc) 6%, transparent)' }}>
                    <span style={{ padding: '7px 4px', color: 'var(--mut)', textAlign: 'center' }}>8</span><span style={{ padding: '7px 8px', fontFamily: "'Hanken Grotesk', sans-serif", fontSize: 12.5 }}>{t('landing.demo.rowGkp')}</span><span style={{ padding: '7px 4px', textAlign: 'center' }}>m²</span><span style={{ padding: '7px 8px', textAlign: 'right' }}>74,2</span><span style={{ padding: '7px 8px', textAlign: 'right' }}>17,00</span><span style={{ padding: '7px 8px', textAlign: 'right', color: 'var(--acc)', outline: '1.5px solid var(--acc)', outlineOffset: -1.5 }}>1 261,40</span>
                  </div>
                  <div style={{ display: 'grid', gridTemplateColumns: '34px 2fr 0.8fr 0.9fr 0.9fr 1fr', color: 'var(--ink2)' }}>
                    <span style={{ padding: '7px 4px', color: 'var(--mut)', textAlign: 'center' }}>9</span><span style={{ padding: '7px 8px', fontFamily: "'Hanken Grotesk', sans-serif", fontSize: 12.5 }}>{t('landing.demo.rowGrind')}</span><span style={{ padding: '7px 4px', textAlign: 'center' }}>m</span><span style={{ padding: '7px 8px', textAlign: 'right' }}>58,4</span><span style={{ padding: '7px 8px', textAlign: 'right' }}>4,10</span><span style={{ padding: '7px 8px', textAlign: 'right' }}>239,44</span>
                  </div>
                </div>
              </div>
              <p style={{ margin: '16px 0 0', fontSize: 14, color: 'var(--ink2)' }}><strong style={{ fontWeight: 600, color: 'var(--ink)' }}>{t('landing.exportSec.excelStrong')}</strong>{t('landing.exportSec.excelRest')}</p>
            </div>
            <div data-reveal="" style={{ transitionDelay: '110ms' }}>
              <div style={{ border: '1px solid var(--line2)', borderRadius: 12, background: 'var(--bg1)', overflow: 'hidden', padding: '22px 26px' }}>
                <div style={{ textAlign: 'center', fontFamily: mono, fontSize: 12, letterSpacing: '0.22em', color: 'var(--ink)' }}>LOKALINĖ SĄMATA</div>
                <div style={{ textAlign: 'center', fontFamily: mono, fontSize: 10, color: 'var(--mut)', marginTop: 4 }}>Nr. S-001 · 2026-07-07</div>
                <div style={{ marginTop: 18, borderTop: '1px solid var(--line)', fontSize: 12.5 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, padding: '8px 0', borderBottom: '1px solid color-mix(in srgb, var(--line) 60%, transparent)', color: 'var(--ink2)' }}><span>1. Dažymo darbai</span><span style={{ fontFamily: mono, fontVariantNumeric: 'tabular-nums' }}>2 214,30</span></div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, padding: '8px 0', borderBottom: '1px solid color-mix(in srgb, var(--line) 60%, transparent)', color: 'var(--ink2)' }}><span>2. GKP darbai</span><span style={{ fontFamily: mono, fontVariantNumeric: 'tabular-nums' }}>2 897,15</span></div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, padding: '8px 0', borderBottom: '1px solid color-mix(in srgb, var(--line) 60%, transparent)', color: 'var(--ink2)' }}><span>3. Grindų darbai</span><span style={{ fontFamily: mono, fontVariantNumeric: 'tabular-nums' }}>1 515,00</span></div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, padding: '8px 0', borderBottom: '1px solid color-mix(in srgb, var(--line) 60%, transparent)' }}><span>Iš viso be PVM</span><span style={{ fontFamily: mono, fontVariantNumeric: 'tabular-nums' }}>6 626,45</span></div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, padding: '8px 0', borderBottom: '1px solid color-mix(in srgb, var(--line) 60%, transparent)', color: 'var(--ink2)' }}><span>PVM 21%</span><span style={{ fontFamily: mono, fontVariantNumeric: 'tabular-nums' }}>1 391,51</span></div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', gap: 12, padding: '9px 0', fontWeight: 600 }}><span>Iš viso su PVM</span><span style={{ fontFamily: mono, fontVariantNumeric: 'tabular-nums', color: 'var(--acc)' }}>8 017,96 €</span></div>
                </div>
                <div style={{ marginTop: 20, display: 'flex', justifyContent: 'space-between', gap: 24, fontFamily: mono, fontSize: 10.5, color: 'var(--mut)' }}>
                  <span style={{ flex: 1 }}>Sudarė<br /><span style={{ display: 'block', borderBottom: '1px solid var(--line2)', height: 20 }} /></span>
                  <span style={{ flex: 1 }}>Tvirtinu<br /><span style={{ display: 'block', borderBottom: '1px solid var(--line2)', height: 20 }} /></span>
                </div>
              </div>
              <p style={{ margin: '16px 0 0', fontSize: 14, color: 'var(--ink2)' }}><strong style={{ fontWeight: 600, color: 'var(--ink)' }}>{t('landing.exportSec.pdfStrong')}</strong>{t('landing.exportSec.pdfRest')}</p>
            </div>
          </div>
        </div>
      </section>

      {/* ═══════════ 07 · KAM SKIRTA ═══════════ */}
      <section style={{ borderBottom: '1px solid var(--line)', background: 'var(--bg1)' }}>
        <div className="pl-sec">
          <div className="pl-eyebrow" data-reveal="">{t('landing.audience.eyebrow')}</div>
          <h2 className="pl-h2" data-reveal="" style={{ transitionDelay: '70ms' }}>{t('landing.audience.title')}</h2>
          <div className="pl-grid3" style={{ marginTop: 56, display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 20 }}>
            {audienceCards.map((c, i) => (
              <div key={i} data-reveal="" style={{ transitionDelay: `${i * 100}ms`, border: '1px solid var(--line)', borderRadius: 12, background: 'var(--bg)', padding: 28 }}>
                <div style={{ fontFamily: mono, fontSize: 11, letterSpacing: '0.14em', color: 'var(--acc)' }}>{String(i + 1).padStart(2, '0')}</div>
                <div style={{ marginTop: 14, fontFamily: sora, fontWeight: 600, fontSize: 19, letterSpacing: '-0.01em' }}>{c.t}</div>
                <p style={{ margin: '10px 0 0', fontSize: 14.5, lineHeight: 1.55, color: 'var(--ink2)' }}>{c.d}</p>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* ═══════════ 08 · KAINOS ═══════════ */}
      <section id="kainos" style={{ borderBottom: '1px solid var(--line)' }}>
        <div className="pl-sec">
          <div className="pl-eyebrow" data-reveal="">{t('landing.pricing.eyebrow')}</div>
          <h2 className="pl-h2" data-reveal="" style={{ transitionDelay: '70ms' }}>{t('landing.pricing.title')}</h2>
          <div className="pl-grid4" style={{ marginTop: 56, display: 'grid', gridTemplateColumns: '1fr 1fr 1fr 1fr', gap: 16, alignItems: 'stretch' }}>
            {tiers.map((tier, i) => (
              <div key={i} data-reveal="" style={{ transitionDelay: `${i * 80}ms`, border: i === 2 ? '1.5px solid var(--acc)' : '1px solid var(--line)', borderRadius: 12, background: 'var(--bg1)', padding: 26, display: 'flex', flexDirection: 'column', gap: 6, position: 'relative' }}>
                {i === 2 && (
                  <span style={{ position: 'absolute', top: -10, left: 24, fontFamily: mono, fontSize: 10, letterSpacing: '0.1em', textTransform: 'uppercase', background: 'var(--acc)', color: 'var(--accink)', padding: '3px 10px', borderRadius: 20 }}>{t('landing.pricing.popular')}</span>
                )}
                <div style={{ fontSize: 15, fontWeight: 600 }}>{tier.name}</div>
                <div style={{ fontFamily: mono, fontSize: 30, fontWeight: 600, letterSpacing: '-0.02em', marginTop: 8 }}>{tier.price}</div>
                <div style={{ fontSize: 13, color: 'var(--mut)' }}>{tier.per}</div>
                <p style={{ margin: '12px 0 0', fontSize: 13.5, lineHeight: 1.5, color: 'var(--ink2)', flex: 1 }}>{tier.desc}</p>
                <Link to="/register" style={{ marginTop: 14, fontFamily: mono, fontSize: 12.5, color: 'var(--acc)' }}>{t('landing.pricing.tierCta')} →</Link>
              </div>
            ))}
          </div>
          <p className="pl-mono-note" data-reveal="" style={{ margin: '22px 0 0' }}>{t('landing.pricing.note')}</p>
        </div>
      </section>

      {/* ═══════════ 09 · CTA + FOOTER ═══════════ */}
      <section style={{ borderBottom: '1px solid var(--line)', position: 'relative', overflow: 'hidden' }}>
        <div aria-hidden style={{ position: 'absolute', inset: 0, background: 'repeating-linear-gradient(-45deg, transparent 0 90px, color-mix(in srgb, var(--ink) 4%, transparent) 90px 91px)', pointerEvents: 'none' }} />
        <div className="pl-sec" style={{ position: 'relative', padding: '110px 24px', textAlign: 'center', display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
          <h2 className="pl-h2" data-reveal="" style={{ margin: 0, fontWeight: 700, letterSpacing: '-0.03em', fontSize: 48, lineHeight: 1.05, maxWidth: 760, textWrap: 'balance' }}>{t('landing.cta.title')}</h2>
          <p className="pl-sub" data-reveal="" style={{ transitionDelay: '80ms', margin: '20px 0 0', maxWidth: 540 }}>{t('landing.cta.sub')}</p>
          <div className="pl-ctas" data-reveal="" style={{ transitionDelay: '160ms', marginTop: 34, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 14 }}>
            <Link to="/register" className="pl-btn-primary">{t('landing.cta.primary')}</Link>
            <a href={MAIL_URL} className="pl-btn-ghost">{t('landing.cta.contact')}</a>
            <a href={WA_URL} target="_blank" rel="noopener noreferrer" className="pl-btn-ghost">
              <svg width="15" height="15" viewBox="0 0 24 24" fill="currentColor" aria-hidden><path d="M12 2a10 10 0 0 0-8.6 15.1L2 22l5.1-1.3A10 10 0 1 0 12 2zm0 18.2a8.2 8.2 0 0 1-4.2-1.2l-.3-.2-3 .8.8-3-.2-.3A8.2 8.2 0 1 1 12 20.2zm4.6-6.1c-.3-.1-1.5-.7-1.7-.8-.2-.1-.4-.1-.6.1-.2.3-.7.8-.8 1-.1.2-.3.2-.5.1a6.7 6.7 0 0 1-3.4-3c-.3-.4 0-.5.1-.7l.4-.5c.1-.2.1-.3 0-.5l-.8-1.9c-.2-.5-.4-.4-.6-.4h-.5c-.2 0-.5.1-.7.3-.2.3-.9.9-.9 2.2s.9 2.5 1.1 2.7c.1.2 1.9 2.9 4.6 4 .6.3 1.1.4 1.5.6.6.2 1.2.2 1.6.1.5-.1 1.5-.6 1.7-1.2.2-.6.2-1.1.2-1.2l-.5-.3z" /></svg>
              WhatsApp
            </a>
          </div>
        </div>
      </section>

      <footer style={{ background: 'var(--bg)' }}>
        <div style={{ maxWidth: 1200, margin: '0 auto', padding: '48px 24px 40px' }}>
          <div className="pl-footcols" style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 40, flexWrap: 'wrap' }}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
              <span style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                <PathonMark icon={24} />
                <span style={{ fontFamily: sora, fontWeight: 700, letterSpacing: '-0.02em', fontSize: 17 }}>Pathon</span>
              </span>
              <span style={{ fontSize: 13.5, color: 'var(--mut)' }}>{t('landing.footer.tagline')}</span>
              <a href={MAIL_URL} style={{ fontFamily: mono, fontSize: 12.5, color: 'var(--mut)' }}>solutions@pathon.eu</a>
              <a href={WA_URL} target="_blank" rel="noopener noreferrer" style={{ fontFamily: mono, fontSize: 12.5, color: 'var(--mut)' }}>WhatsApp +370 602 71962</a>
            </div>
            <div style={{ display: 'flex', gap: 28, flexWrap: 'wrap', fontSize: 13.5, color: 'var(--mut)', paddingTop: 4 }}>
              <Link to="/duk">{t('landing.footer.duk')}</Link>
              <Link to="/privacy">{t('landing.footer.privacy')}</Link>
              <Link to="/cookies">{t('landing.footer.cookies')}</Link>
              <Link to="/terms">{t('landing.footer.terms')}</Link>
              <button type="button" onClick={openCookieSettings} style={{ background: 'none', border: 'none', padding: 0, cursor: 'pointer', fontSize: 13.5, color: 'var(--mut)' }}>{t('landing.footer.cookieSettings')}</button>
            </div>
          </div>
          <div style={{ marginTop: 36, paddingTop: 20, borderTop: '1px solid var(--line)', fontSize: 12.5, color: 'var(--mut)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 16, flexWrap: 'wrap' }}>
            <span>{t('landing.footer.copyright')}</span>
            <span style={{ display: 'inline-flex', alignItems: 'center', gap: 14 }}>
              <span style={{ display: 'inline-flex', gap: 2, fontFamily: mono, fontSize: 11 }}>
                <button type="button" onClick={() => switchLang('lt')} style={{ background: 'none', border: 'none', padding: '2px 6px', cursor: 'pointer', fontFamily: mono, fontSize: 11, color: (lang || 'lt') === 'lt' ? 'var(--acc)' : 'var(--mut)' }}>LT</button>
                <button type="button" onClick={() => switchLang('en')} style={{ background: 'none', border: 'none', padding: '2px 6px', cursor: 'pointer', fontFamily: mono, fontSize: 11, color: lang === 'en' ? 'var(--acc)' : 'var(--mut)' }}>EN</button>
              </span>
              <span style={{ fontFamily: mono, fontSize: 11 }}>{t('landing.footer.location')}</span>
            </span>
          </div>
        </div>
      </footer>
    </div>
  );
}
