#!/usr/bin/env node
/**
 * ui-probe.mjs — the type and contrast probe for the viewer screen (Pathon v3, track W1-C, C5).
 *
 * Opens a project in headless chromium at 1440×900 against a RUNNING dev pair (Vite + backend) and
 * measures what the design contract (docs/superpowers/specs/2026-10-18-pathon-v3-design.md §6) promises:
 *
 *   1. Font-size census — every visible text element on the default viewer screen (HTML and the SVG
 *      labels on the drawing), clipped to the viewport and to scroll containers. PASS: ≤ 6 distinct
 *      sizes, none under 12 px.
 *   2. Contrast — every visible text element against its effective background (ancestor backgrounds
 *      alpha-composited; an SVG label against the pill behind it, else the white sheet): ≥ 4.5:1
 *      (≥ 3:1 for large text). Every overlay stroke on the sheet (zones, walls layer) against the white
 *      sheet: ≥ 3:1. Disabled controls are exempt (WCAG 1.4.3). Named checks — main text, muted text,
 *      units, the provenance link, zone strokes — must be found and must pass.
 *   3. With `--shots DIR`: before/after screenshots of the scenes the W1-C brief names (zones on/off,
 *      walls layer, a measurement draft, the count tool, „Rasti panašius" candidates, outline edit,
 *      the Patikra room sheet's check layer, the Sąmata first screen). Nothing is saved: drafts are
 *      dropped with Esc, the outline edit is cancelled, the symbol search is closed.
 *
 * Playwright is NOT a dependency of this app (same decision as og-shot.mjs / prerender.mjs):
 *   npm exec --yes --package=playwright@1.55.1 -- node scripts/ui-probe.mjs \
 *     --origin http://localhost:5205 --project demo-objektas_h [--shots /tmp/shots] [--report-only]
 * Exit code 1 when a check fails (unless --report-only). No AI call, no write.
 */
import { createRequire } from 'node:module';
import { mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';

function loadPlaywright() {
  try {
    return createRequire(import.meta.url)('playwright');
  } catch {
    /* expected: not a project dependency */
  }
  for (const bin of (process.env.PATH ?? '').split(path.delimiter)) {
    if (!bin.endsWith(path.join('node_modules', '.bin'))) continue;
    try {
      return createRequire(path.join(bin, '..', 'probe.js'))('playwright');
    } catch {
      /* keep scanning */
    }
  }
  throw new Error('playwright is not resolvable — run under `npm exec --yes --package=playwright@1.55.1 -- node scripts/ui-probe.mjs …`');
}

const args = process.argv.slice(2);
const opt = (name, fallback = null) => {
  const i = args.indexOf(`--${name}`);
  return i >= 0 && args[i + 1] && !args[i + 1].startsWith('--') ? args[i + 1] : fallback;
};
const flag = (name) => args.includes(`--${name}`);
const ORIGIN = opt('origin', 'http://localhost:5205');
const PROJECT = opt('project', 'demo-objektas_h');
const SHOTS = opt('shots');
const REPORT_ONLY = flag('report-only');
const MAX_SIZES = 6;
const MIN_PX = 12;

// ── in-page measurement (serialised into the page; keep it self-contained) ──────────────────────────
function measureInPage() {
  const parse = (s) => {
    if (!s || s === 'none' || s === 'transparent') return null;
    const m = s.match(/rgba?\(([^)]+)\)/);
    if (!m) return null;
    const p = m[1].split(/[ ,/]+/).filter(Boolean).map(Number);
    return { r: p[0], g: p[1], b: p[2], a: p.length > 3 ? p[3] : 1 };
  };
  const over = (top, under) => {
    const a = top.a + under.a * (1 - top.a);
    if (a <= 0) return { r: 255, g: 255, b: 255, a: 0 };
    const ch = (k) => (top[k] * top.a + under[k] * under.a * (1 - top.a)) / a;
    return { r: ch('r'), g: ch('g'), b: ch('b'), a };
  };
  const lum = (c) => {
    const f = (v) => { const x = v / 255; return x <= 0.03928 ? x / 12.92 : ((x + 0.055) / 1.055) ** 2.4; };
    return 0.2126 * f(c.r) + 0.7152 * f(c.g) + 0.0722 * f(c.b);
  };
  const ratio = (a, b) => { const la = lum(a); const lb = lum(b); return (Math.max(la, lb) + 0.05) / (Math.min(la, lb) + 0.05); };
  const hex = (c) => `#${[c.r, c.g, c.b].map((v) => Math.round(v).toString(16).padStart(2, '0')).join('')}`;
  const WHITE = { r: 255, g: 255, b: 255, a: 1 };

  const vw = window.innerWidth;
  const vh = window.innerHeight;
  // The part of an element that is really on screen: the viewport ∩ every clipping ancestor.
  const visibleRect = (el) => {
    const r = el.getBoundingClientRect();
    let x0 = Math.max(r.left, 0); let y0 = Math.max(r.top, 0);
    let x1 = Math.min(r.right, vw); let y1 = Math.min(r.bottom, vh);
    for (let a = el.parentElement; a && a !== document.documentElement; a = a.parentElement) {
      const s = getComputedStyle(a);
      if (s.display === 'none' || s.visibility === 'hidden') return null;
      if (/(hidden|auto|scroll|clip)/.test(`${s.overflowX}${s.overflowY}`)) {
        const q = a.getBoundingClientRect();
        x0 = Math.max(x0, q.left); y0 = Math.max(y0, q.top); x1 = Math.min(x1, q.right); y1 = Math.min(y1, q.bottom);
      }
    }
    return x1 - x0 >= 2 && y1 - y0 >= 2 ? { x0, y0, x1, y1 } : null;
  };
  const opacityOf = (el) => {
    let op = 1;
    for (let a = el; a && a.nodeType === 1; a = a.parentElement) op *= parseFloat(getComputedStyle(a).opacity || '1');
    return op;
  };
  // Effective background of an HTML element: ancestor backgrounds composited, white page underneath.
  const htmlBg = (el) => {
    const layers = [];
    for (let a = el; a && a.nodeType === 1; a = a.parentElement) {
      const c = parse(getComputedStyle(a).backgroundColor);
      if (c && c.a > 0) { layers.push(c); if (c.a >= 1) break; }
    }
    return layers.reverse().reduce((acc, c) => over(c, acc), WHITE);
  };
  // An SVG label: the pill (rect) drawn just before it in the same group, when it frames the text.
  const svgBg = (el) => {
    const box = el.getBoundingClientRect();
    const cx = (box.left + box.right) / 2; const cy = (box.top + box.bottom) / 2;
    for (let g = el.parentElement; g && g.tagName.toLowerCase() !== 'svg'; g = g.parentElement) {
      const rects = [...g.querySelectorAll(':scope > rect')];
      for (const rc of rects.reverse()) {
        const q = rc.getBoundingClientRect();
        if (cx >= q.left && cx <= q.right && cy >= q.top && cy <= q.bottom) {
          const s = getComputedStyle(rc);
          const c = parse(s.fill);
          if (c) return over({ ...c, a: c.a * parseFloat(s.fillOpacity || '1') * parseFloat(s.opacity || '1') }, WHITE);
        }
      }
    }
    return WHITE;
  };

  const texts = [];
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  const seen = new Set();
  while (walker.nextNode()) {
    const t = walker.currentNode;
    if (!t.nodeValue || !t.nodeValue.trim()) continue;
    const el = t.parentElement;
    if (!el || seen.has(el)) continue;
    seen.add(el);
    const tag = el.tagName.toLowerCase();
    if (['style', 'script', 'title', 'noscript', 'option'].includes(tag)) continue;
    const cs = getComputedStyle(el);
    if (cs.display === 'none' || cs.visibility === 'hidden') continue;
    const vr = visibleRect(el);
    if (!vr) continue;
    const op = opacityOf(el);
    if (op < 0.05) continue;
    const isSvg = el instanceof SVGElement;
    // Disabled controls are exempt from 1.4.3; so is decoration hidden from assistive tech („›").
    const disabled = !!el.closest('button:disabled, [aria-disabled="true"], fieldset:disabled, input:disabled, [aria-hidden="true"]');
    const fgRaw = parse(isSvg ? cs.fill : cs.color);
    const bg = isSvg ? svgBg(el) : htmlBg(el);
    let cr = null;
    if (fgRaw) {
      const fg = over({ ...fgRaw, a: fgRaw.a * op * (isSvg ? parseFloat(cs.fillOpacity || '1') : 1) }, bg);
      cr = ratio(fg, bg);
    }
    const size = parseFloat(cs.fontSize);
    const weight = parseInt(cs.fontWeight, 10) || 400;
    const large = size >= 24 || (size >= 18.66 && weight >= 700);
    texts.push({
      text: t.nodeValue.trim().replace(/\s+/g, ' ').slice(0, 48),
      size, weight, svg: isSvg, disabled, mono: /mono/i.test(cs.fontFamily),
      ratio: cr == null ? null : Math.round(cr * 100) / 100,
      need: large ? 3 : 4.5,
      fg: fgRaw ? hex(fgRaw) : null, bg: hex(bg),
      at: [Math.round(vr.x0), Math.round(vr.y0)],
    });
  }

  // Overlay strokes on the sheet (everything drawn in an SVG inside a page host).
  const strokes = [];
  for (const sh of document.querySelectorAll('[data-page-number] svg :is(polygon, path, line, rect, circle, polyline)')) {
    const s = getComputedStyle(sh);
    const c = parse(s.stroke);
    const w = parseFloat(s.strokeWidth || '0');
    if (!c || w < 1 || s.display === 'none' || s.visibility === 'hidden') continue;
    if (!visibleRect(sh)) continue;
    const op = parseFloat(s.strokeOpacity || '1') * opacityOf(sh);
    if (op < 0.05) continue;
    // A label pill's hairline border is decoration — the words inside carry the meaning (and are
    // checked as text above): skip shapes filled opaque white.
    const fill = parse(s.fill);
    if (fill && fill.r > 245 && fill.g > 245 && fill.b > 245 && fill.a * parseFloat(s.fillOpacity || '1') >= 0.85) continue;
    const eff = over({ ...c, a: c.a * op }, WHITE);
    const layer = sh.closest('[data-drawing-geometry-layer]') ? 'walls'
      : sh.closest('[data-check-layer]') ? 'check'
        : sh.closest('[data-room-zone-layer]') ? 'zones' : 'other';
    strokes.push({ layer, tag: sh.tagName.toLowerCase(), stroke: hex(c), opacity: Math.round(op * 100) / 100, width: w, ratio: Math.round(ratio(eff, WHITE) * 100) / 100 });
  }

  // Named checks.
  const named = {};
  const first = (sel, pred = () => true) => [...document.querySelectorAll(sel)].find((e) => visibleRect(e) && pred(e));
  const textRatio = (el) => {
    if (!el) return null;
    const cs = getComputedStyle(el);
    const fg = parse(cs.color);
    const bg = htmlBg(el);
    return { ratio: Math.round(ratio(over({ ...fg, a: fg.a * opacityOf(el) }, bg), bg) * 100) / 100, size: parseFloat(cs.fontSize), fg: hex(fg), bg: hex(bg), text: (el.textContent || '').trim().slice(0, 40) };
  };
  named.mainText = textRatio(first('[data-testid="room-row-name"]')
    || first('.text-foreground', (e) => (e.textContent || '').trim().length > 1));
  named.mutedText = textRatio(first('.text-muted-foreground', (e) => (e.textContent || '').trim().length > 1));
  named.units = textRatio(first('[data-testid="room-row-unit"]') || first('span', (e) => (e.textContent || '').trim() === 'm²'));
  named.provenance = textRatio(first('[data-testid^="provenance-chip-"] button'));
  return { texts, strokes, named, viewport: [vw, vh] };
}

// ── helpers ────────────────────────────────────────────────────────────────────────────────────────
async function openViewer(page) {
  await page.goto(`${ORIGIN}/project/${PROJECT}`, { waitUntil: 'networkidle' });
  await page.waitForSelector('[data-page-number]', { timeout: 30_000 });
  await page.waitForTimeout(2500);
}

async function pageBox(page, n = 1) {
  const el = await page.$(`[data-page-number="${n}"]`);
  return el ? el.boundingBox() : null;
}

async function shot(page, dir, name) {
  if (!dir) return;
  await page.screenshot({ path: path.join(dir, `${name}.png`) });
  console.log(`  shot ${name}.png`);
}

async function scene(name, fn) {
  try {
    await fn();
  } catch (err) {
    console.log(`  scene ${name} failed: ${String(err?.message || err).split('\n')[0]}`);
  }
}

async function runShots(page, dir) {
  await mkdir(dir, { recursive: true });
  await openViewer(page);
  await shot(page, dir, '01-viewer-default');
  await scene('reread-chip', async () => {
    const toggle = page.locator('[data-testid="reread-diff-toggle"]');
    if (!(await toggle.count())) return;
    await toggle.click();
    await page.waitForTimeout(400);
    await shot(page, dir, '01b-reread-list-open');
    await toggle.click();
    await page.waitForTimeout(300);
  });
  await page.mouse.click(5, 5);

  await scene('zones', async () => {
    await page.keyboard.press('u');
    await page.waitForTimeout(600);
    await shot(page, dir, '02-zones-on');
    const row = page.locator('.row-hover-halo', { hasText: 'Virtuvė/valgomasis' }).first();
    await row.click();
    await page.waitForTimeout(1500);
    await shot(page, dir, '03-zones-on-room-focused');
    await page.keyboard.press('u');
    await page.waitForTimeout(600);
    await shot(page, dir, '04-zones-off-room-focused');
  });

  await scene('outline-edit', async () => {
    const start = page.locator('[data-testid="outline-edit-start"]');
    await start.click();
    await page.waitForTimeout(1000);
    await shot(page, dir, '05-outline-edit');
    await page.keyboard.press('Escape');
    await page.waitForTimeout(400);
    await page.keyboard.press('Escape');
    await page.waitForTimeout(400);
  });

  await scene('walls', async () => {
    await page.keyboard.press('s');
    await page.waitForTimeout(1500);
    await shot(page, dir, '06-walls-layer');
    await page.keyboard.press('s');
    await page.waitForTimeout(400);
  });

  await scene('measure', async () => {
    const box = await pageBox(page, 1);
    await page.keyboard.press('2');
    await page.waitForTimeout(500);
    // inside the part of the sheet that is on screen (the page runs below the status bar)
    const y = Math.min(box.y + box.height * 0.45, 760);
    for (const fx of [0.42, 0.52]) {
      await page.mouse.move(box.x + box.width * fx, y, { steps: 3 });
      await page.mouse.down();
      await page.mouse.up();
      await page.waitForTimeout(250);
    }
    await page.mouse.move(box.x + box.width * 0.58, y - 40, { steps: 4 });
    await page.waitForTimeout(500);
    await shot(page, dir, '07-measure-draft');
    await page.keyboard.press('Escape');
    await page.keyboard.press('Escape');
    await page.waitForTimeout(300);
  });

  await scene('count', async () => {
    await page.keyboard.press('6');
    await page.waitForTimeout(800);
    await shot(page, dir, '08-count-tool');
    await page.keyboard.press('Escape');
    await page.waitForTimeout(300);
  });

  await scene('symbol-search', async () => {
    await page.locator('[data-testid="viewer-symbol-search"]').click();
    await page.waitForTimeout(600);
    const box = await pageBox(page, 1);
    const rel = (fx, fy) => [box.x + box.width * fx, box.y + box.height * fy];
    const [ax, ay] = rel(Number(opt('sym-x0', '0.585')), Number(opt('sym-y0', '0.555')));
    const [bx, by] = rel(Number(opt('sym-x1', '0.612')), Number(opt('sym-y1', '0.585')));
    await page.mouse.move(ax, ay);
    await page.mouse.down();
    await page.mouse.move(bx, by, { steps: 6 });
    await page.mouse.up();
    await page.waitForSelector('[data-testid="symbol-candidate"]', { timeout: 30_000 }).catch(() => null);
    await page.waitForTimeout(800);
    await shot(page, dir, '09-symbol-search-candidates');
    await page.keyboard.press('Escape');
    await page.waitForTimeout(400);
  });

  await scene('patikra-room-sheet', async () => {
    await page.goto(`${ORIGIN}/project/${PROJECT}/patikra?kambarys=04`, { waitUntil: 'networkidle' });
    await page.waitForSelector('[data-check-layer]', { timeout: 30_000 }).catch(() => null);
    await page.waitForTimeout(2500);
    await shot(page, dir, '10-patikra-room-sheet');
  });

  await scene('samata', async () => {
    await page.goto(`${ORIGIN}/project/${PROJECT}?step=samata`, { waitUntil: 'networkidle' });
    await page.waitForTimeout(2500);
    await shot(page, dir, '11-samata-first-screen');
    const toggle = page.locator('[data-testid="sanity-toggle"]');
    if (await toggle.count()) {
      await toggle.click();
      await page.waitForTimeout(400);
      await shot(page, dir, '12-samata-checks-open');
    }
  });
}

// ── main ───────────────────────────────────────────────────────────────────────────────────────────
const { chromium } = loadPlaywright();
const browser = await chromium.launch();
const context = await browser.newContext({ viewport: { width: 1440, height: 900 } });
await context.addInitScript(() => {
  try {
    localStorage.setItem('pathon_cookie_consent', JSON.stringify({ categories: { necessary: true, analytics: false, marketing: false }, timestamp: Date.now() }));
    localStorage.setItem('samatu_viewer_onboarded', '1');
  } catch { /* storage blocked */ }
});
const page = await context.newPage();

let failed = false;
try {
  console.log(`[ui-probe] ${ORIGIN}/project/${PROJECT} at 1440×900`);
  await openViewer(page);
  const base = await page.evaluate(measureInPage);
  // zone strokes: the zones layer on (key U), then measured, then off again
  await page.mouse.click(5, 5);
  await page.keyboard.press('u');
  await page.waitForTimeout(800);
  const withZones = await page.evaluate(measureInPage);
  await page.keyboard.press('u');
  await page.keyboard.press('s');
  await page.waitForTimeout(1500);
  const withWalls = await page.evaluate(measureInPage);
  await page.keyboard.press('s');

  // 1. census
  const sizes = new Map();
  for (const t of base.texts) sizes.set(t.size, (sizes.get(t.size) || 0) + 1);
  const sorted = [...sizes.entries()].sort((a, b) => a[0] - b[0]);
  const small = base.texts.filter((t) => t.size < MIN_PX);
  const total = base.texts.length;
  const le12 = base.texts.filter((t) => t.size <= 12).length;
  const mono = base.texts.filter((t) => t.mono).length;
  console.log(`\n1. Font sizes on the default viewer screen: ${sorted.length} distinct over ${total} text elements`);
  console.log(`   ${sorted.map(([s, n]) => `${s}px×${n}`).join(' · ')}`);
  console.log(`   ≤ 12 px: ${le12} (${Math.round((le12 / Math.max(total, 1)) * 100)} %) · under ${MIN_PX} px: ${small.length} · monospace: ${mono} (${Math.round((mono / Math.max(total, 1)) * 100)} %)`);
  if (sorted.length > MAX_SIZES) { failed = true; console.log(`   FAIL: more than ${MAX_SIZES} sizes`); }
  if (small.length) { failed = true; console.log(`   FAIL: text under ${MIN_PX} px: ${small.slice(0, 8).map((t) => `"${t.text}" ${t.size}px`).join(', ')}`); }

  // 2. contrast
  const textFails = [base, withZones, withWalls]
    .flatMap((m) => m.texts)
    .filter((t) => !t.disabled && t.ratio != null && t.ratio < t.need);
  const uniqFails = [...new Map(textFails.map((t) => [`${t.text}|${t.fg}|${t.bg}`, t])).values()];
  console.log(`\n2. Text contrast: ${uniqFails.length} failing element(s)`);
  for (const t of uniqFails.slice(0, 25)) console.log(`   FAIL "${t.text}" ${t.size}px ${t.fg} on ${t.bg} = ${t.ratio}:1 (needs ${t.need})`);
  if (uniqFails.length) failed = true;

  const strokeFails = [...withZones.strokes, ...withWalls.strokes].filter((s) => s.ratio < 3);
  const strokeKinds = [...new Map([...withZones.strokes, ...withWalls.strokes].map((s) => [`${s.layer}|${s.stroke}|${s.opacity}`, s])).values()];
  console.log(`   Overlay strokes on the sheet (zones + walls layer): ${strokeKinds.length} kinds, ${strokeFails.length} under 3:1`);
  for (const s of strokeKinds) console.log(`   ${s.ratio < 3 ? 'FAIL' : 'ok  '} ${s.layer} ${s.tag} ${s.stroke} @${s.opacity} w${s.width} = ${s.ratio}:1`);
  if (strokeFails.length) failed = true;

  console.log('\n   Named checks:');
  const zoneStroke = withZones.strokes.filter((s) => s.layer === 'zones');
  const namedRows = [
    ['main text', base.named.mainText, 4.5],
    ['muted text', base.named.mutedText, 4.5],
    ['units', base.named.units, 4.5],
    ['provenance', base.named.provenance, 4.5],
  ];
  for (const [label, v, need] of namedRows) {
    if (!v) { failed = true; console.log(`   FAIL ${label}: not found on the screen`); continue; }
    const ok = v.ratio >= need;
    if (!ok) failed = true;
    console.log(`   ${ok ? 'ok  ' : 'FAIL'} ${label}: "${v.text}" ${v.size}px ${v.fg} on ${v.bg} = ${v.ratio}:1`);
  }
  if (!zoneStroke.length) { failed = true; console.log('   FAIL zone strokes: none drawn with the zones layer on'); } else {
    const worst = zoneStroke.reduce((a, b) => (a.ratio <= b.ratio ? a : b));
    if (worst.ratio < 3) failed = true;
    console.log(`   ${worst.ratio >= 3 ? 'ok  ' : 'FAIL'} zone strokes: ${zoneStroke.length} drawn, weakest ${worst.stroke} = ${worst.ratio}:1`);
  }

  if (SHOTS) {
    console.log(`\n3. Screenshots → ${SHOTS}`);
    await runShots(page, SHOTS);
    await writeFile(path.join(SHOTS, 'probe.json'), JSON.stringify({ base, withZones, withWalls }, null, 2));
  }
} finally {
  await browser.close();
}
console.log(`\n[ui-probe] ${failed ? 'FAIL' : 'PASS'}`);
if (failed && !REPORT_ONLY) process.exit(1);
