#!/usr/bin/env node
/**
 * look-hygiene-codemod.mjs — spells colour classes through the configured Tailwind colours (Pathon v3, W6-A, G1).
 *
 * Rewrites, in the files given (or every src/ .js/.jsx file minus --skip):
 *   1. `<prefix>-[hsl(var(--token))]`          → `<prefix>-<name>`
 *      `<prefix>-[hsl(var(--token)/0.75)]`     → `<prefix>-<name>/75`      (a Tailwind opacity step)
 *      `<prefix>-[hsl(var(--token)/0.08)]`     → `<prefix>-<name>/[0.08]`  (not a step: arbitrary modifier)
 *      `<prefix>-[hsl(var(--token))]/45`       → `<prefix>-<name>/45`
 *      for the colour prefixes bg / text / border(-x) / ring / accent / fill / stroke / outline / divide /
 *      decoration / caret / placeholder, any variants in front (`hover:`, `group-hover/callout:` …) kept.
 *      `<name>` is the colour key in tailwind.config.js that resolves to `hsl(var(--token))` (TOKEN_NAMES).
 *   2. every `dark:` class is dropped — the app runs the light theme and no element carries `.dark`
 *      (CLAUDE.md „Operational rules"), so these rules never applied.
 * Nothing else is touched. A token with no configured colour is left as it was and listed.
 *
 * Deterministic and idempotent: a merge conflict in a rewritten file is resolved by taking the other side and
 * running it again.
 *   node scripts/look-hygiene-codemod.mjs [--dry] [--verify] [--skip a.jsx,b.jsx] [file …]
 * --verify compiles every (old, new) pair with this repo's Tailwind config and checks the CSS declarations are
 * the same (whitespace around `/` aside) and that tailwind-merge puts both in the same conflict group, so a
 * `cn()` call resolves the same way. Exit 1 when a pair differs.
 */
import { readFileSync, writeFileSync, readdirSync, statSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
const ROOT = path.resolve(HERE, '..');

/** CSS variable → colour key in tailwind.config.js (theme.extend.colors). */
export const TOKEN_NAMES = {
  primary: 'primary',
  muted: 'muted',
  destructive: 'destructive',
  'ink-2': 'ink-2',
  'accent-2': 'accent-2',
  'surface-2': 'surface-2',
  'viewer-chrome': 'viewer-chrome',
  'viewer-chrome-foreground': 'viewer-chrome-foreground',
  'viewer-chrome-muted': 'viewer-chrome-muted',
  'viewer-chrome-border': 'viewer-chrome-border',
  'viewer-chrome-hover': 'viewer-chrome-hover',
  'viewer-chrome-active': 'viewer-chrome-active',
  'viewer-blueprint-bg': 'viewer-blueprint-bg',
  'conf-high': 'conf-high',
  'conf-med': 'conf-med',
  'conf-low': 'conf-low',
  'ov-read': 'ov-read',
  'ov-estimated': 'ov-estimated',
  'ov-proposed': 'ov-proposed',
  'ov-user': 'ov-user',
  'ov-opening': 'ov-opening',
  'ov-wall': 'ov-wall',
  'ov-selected': 'ov-selected',
  'ov-editing': 'ov-editing',
  'ov-error': 'ov-error',
};

const PREFIX = '(?:bg|text|border(?:-[trblxyse])?|ring|accent|fill|stroke|outline|divide|decoration|caret|placeholder)';
// variants: `hover:`, `group-hover/callout:`, `md:` …; the class starts after whitespace, a quote or a backtick
const HSL_RE = new RegExp(
  `(?<![\\w-])((?:[\\w-]+(?:/[\\w-]+)?:)*)(${PREFIX})-\\[hsl\\(var\\(--([a-z0-9-]+)\\)(?:\\s*/\\s*(\\d*\\.?\\d+))?\\)\\](?:/(\\d+))?`,
  'g',
);
const DARK_CLS = String.raw`(?:[\w-]+(?:/[\w-]+)?:)*dark:[^\s"'${'`'}]+`;
const END = String.raw`(?=[\s"'${'`'}]|$)`;
// a `dark:` class with the space before it (mid-string), right after an opening quote, or first on a line
const DARK_RES = [
  new RegExp(String.raw`(?<=\S)[ \t]+${DARK_CLS}${END}`, 'g'),
  new RegExp(String.raw`(?<=["'${'`'}])${DARK_CLS}${END}[ \t]*`, 'g'),
  new RegExp(String.raw`(?<=^[ \t]*)${DARK_CLS}${END}[ \t]*`, 'gm'),
];
const STEPS = new Set([0, 5, 10, 15, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 75, 80, 85, 90, 95, 100]);

export function opacitySuffix(alpha) {
  const pct = Math.round(Number(alpha) * 1000) / 10;
  if (STEPS.has(pct)) return `/${pct}`;
  return `/[${Number(alpha)}]`;
}

/** Returns { out, pairs: [[old, new]], dark: [removed], unknown: [tokens] }. */
export function rewrite(src) {
  const pairs = [];
  const unknown = [];
  let out = src.replace(HSL_RE, (m, variants, prefix, token, alpha, mod) => {
    const name = TOKEN_NAMES[token];
    if (!name || (alpha && mod)) {
      unknown.push(m);
      return m;
    }
    let to = `${variants}${prefix}-${name}`;
    if (alpha) to += opacitySuffix(alpha);
    else if (mod) to += `/${mod}`;
    pairs.push([m, to]);
    return to;
  });
  const dark = [];
  for (const re of DARK_RES) {
    out = out.replace(re, (m) => {
      dark.push(m.trim());
      return '';
    });
  }
  return { out, pairs, dark, unknown };
}

function walk(dir, acc = []) {
  for (const e of readdirSync(dir)) {
    const p = path.join(dir, e);
    if (statSync(p).isDirectory()) walk(p, acc);
    else if (/\.(jsx?|tsx?)$/.test(e) && !/\.test\.js$/.test(e)) acc.push(p);
  }
  return acc;
}

async function verify(pairs) {
  const { createRequire } = await import('node:module');
  const req = createRequire(path.join(ROOT, 'package.json'));
  const postcss = req('postcss');
  const tailwind = req('tailwindcss');
  const loadConfig = req('tailwindcss/loadConfig');
  const { twMerge } = await import(req.resolve('tailwind-merge'));
  const cfg = loadConfig(path.join(ROOT, 'tailwind.config.js'));
  const css = async (cls) => {
    const r = await postcss([tailwind({ ...cfg, content: [{ raw: `<i class="${cls}">` }] })])
      .process('@tailwind utilities;', { from: undefined });
    let decl = null;
    r.root.walkRules((rule) => {
      if (rule.parent?.type === 'atrule' && /keyframes/.test(rule.parent.name)) return;
      const d = [];
      // `hsl(var(--x) / 0.1)` = `hsl(var(--x)/0.10)`: spaces around `/` and trailing zeros do not change the value
      rule.walkDecls((x) => d.push(`${x.prop}:${x.value.replace(/\s*\/\s*/g, '/').replace(/(\.\d*?)0+(?=\D|$)/g, '$1').replace(/\.(?=\D)/g, '')}`));
      // the class's own (escaped) name → X, so only variants and pseudo-classes are compared
      const sel = rule.selector.replace(/\.(?:\\.|[\w-])+/g, (t) => (t.slice(1).replace(/\\(.)/g, '$1') === cls ? '.X' : t));
      decl = `${sel}{${d.join(';')}}`;
    });
    return decl;
  };
  let bad = 0;
  const seen = new Set();
  for (const [a, b] of pairs) {
    const k = `${a}→${b}`;
    if (seen.has(k)) continue;
    seen.add(k);
    const [ca, cb] = [await css(a), await css(b)];
    const sameCss = ca && ca === cb;
    const sameGroup = twMerge(`${a} ${b}`) === b && twMerge(`${b} ${a}`) === a;
    if (!sameCss || !sameGroup) {
      bad += 1;
      console.log(`DIFF ${a} → ${b}\n  old ${ca}\n  new ${cb}\n  twMerge same group: ${sameGroup}`);
    }
  }
  console.log(`verify: ${seen.size} distinct rewrites, ${bad} differ`);
  return bad;
}

const isMain = process.argv[1] && path.resolve(process.argv[1]) === fileURLToPath(import.meta.url);
if (isMain) {
  const args = process.argv.slice(2);
  const dry = args.includes('--dry');
  const doVerify = args.includes('--verify');
  const si = args.indexOf('--skip');
  const skip = new Set(si >= 0 ? args[si + 1].split(',').map((s) => s.trim()).filter(Boolean) : []);
  let files = args.filter((a, i) => !a.startsWith('--') && !(si >= 0 && i === si + 1));
  if (!files.length) files = walk(path.join(ROOT, 'src'));
  files = files.filter((f) => ![...skip].some((s) => f.endsWith(s)));
  const allPairs = [];
  let nPairs = 0;
  let nDark = 0;
  for (const f of files) {
    const src = readFileSync(f, 'utf8');
    const { out, pairs, dark, unknown } = rewrite(src);
    if (unknown.length) console.log(`${f}: left (no configured colour): ${[...new Set(unknown)].join(' ')}`);
    if (out === src) continue;
    nPairs += pairs.length;
    nDark += dark.length;
    allPairs.push(...pairs);
    console.log(`${path.relative(ROOT, f)}: ${pairs.length} hsl → utility, ${dark.length} dark: dropped`);
    if (!dry) writeFileSync(f, out);
  }
  console.log(`${dry ? '[dry] ' : ''}total: ${nPairs} hsl classes rewritten, ${nDark} dark: classes dropped`);
  if (doVerify && (await verify(allPairs))) process.exit(1);
}
