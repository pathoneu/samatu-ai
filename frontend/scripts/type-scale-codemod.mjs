#!/usr/bin/env node
/**
 * type-scale-codemod.mjs — moves arbitrary font sizes onto the v3 type scale (Pathon v3, W1-C, C3).
 *
 * The scale (tailwind.config.js fontSize, design 2026-10-18 §6): 12 metadata only · 14 interface ·
 * 16 body · 18 · 24 · 30. Rewrites, in the files given:
 *   className  text-[Npx]            → text-meta | text-ui | text-body | text-lead
 *   JS style   fontSize: N           → fontSize: M
 *   SVG attr   fontSize={N}          → fontSize={M}
 * Mapping (px): 8–11.5 → 12 · 12 → 12 · 12.5–13.5 → 14 · 15 → 16 · 17 → 18. Anything else is left.
 * With --floor-only only the sizes under 12 move (8–11.5 → 12): for screens whose own scale is
 * already ≥ 12 (the room sheet, Patikra) and only the tiny leftovers need lifting.
 *
 * It is deterministic and idempotent, so a merge conflict in a shared file is resolved by taking the
 * other side and running it again:
 *   node scripts/type-scale-codemod.mjs [--floor-only] [--dry] <file> …
 * It never decides 12-vs-14 for you: a 10 px interface label lands on 12 — lift it to text-ui by hand.
 */
import { readFileSync, writeFileSync } from 'node:fs';

const args = process.argv.slice(2);
const floorOnly = args.includes('--floor-only');
const dry = args.includes('--dry');
const files = args.filter((a) => !a.startsWith('--'));

const CLASS_FOR = { 12: 'text-meta', 14: 'text-ui', 16: 'text-body', 18: 'text-lead' };

export function mapPx(px, { floor = false } = {}) {
  if (!Number.isFinite(px)) return null;
  if (px >= 8 && px < 12) return 12;
  if (floor) return null;
  if (px === 12) return 12;
  if (px > 12 && px < 14) return 14;
  if (px === 15) return 16;
  if (px === 17) return 18;
  return null;
}

export function rewrite(src, { floor = false } = {}) {
  let n = 0;
  let out = src.replace(/(?<![\w-])text-\[(\d+(?:\.\d+)?)px\]/g, (m, v) => {
    const to = mapPx(Number(v), { floor });
    if (to == null || !CLASS_FOR[to]) return m;
    n += 1;
    return CLASS_FOR[to];
  });
  out = out.replace(/\bfontSize(\s*:\s*|=\{\s*)(\d+(?:\.\d+)?)(?=\s*[,}\s])/g, (m, sep, v) => {
    const to = mapPx(Number(v), { floor });
    if (to == null || to === Number(v)) return m;
    n += 1;
    return `fontSize${sep}${to}`;
  });
  return { out, n };
}

if (files.length) {
  let total = 0;
  for (const f of files) {
    const src = readFileSync(f, 'utf8');
    const { out, n } = rewrite(src, { floor: floorOnly });
    if (n) {
      total += n;
      if (!dry) writeFileSync(f, out);
      console.log(`${dry ? '[dry] ' : ''}${f}: ${n}`);
    }
  }
  console.log(`${total} size(s) moved onto the scale${floorOnly ? ' (floor only)' : ''}.`);
}
