// v3 W6-A (G1): colours are spelled through the configured Tailwind colours, never `[hsl(var(--x))]`, and no
// `dark:` class comes back (the app runs the light theme; nothing carries `.dark`). The codemod that did the
// rewrite is the rule: a file it would still change fails here — run `node scripts/look-hygiene-codemod.mjs <file>`.
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync, readdirSync, statSync } from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { rewrite, opacitySuffix } from '../../scripts/look-hygiene-codemod.mjs';

const SRC = path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..');

// Every file is rewritten (pass 2 ran after W5-A merged); a new file joins here only while another track edits it.
const PENDING = new Set([]);

function walk(dir, acc = []) {
  for (const e of readdirSync(dir)) {
    const p = path.join(dir, e);
    if (statSync(p).isDirectory()) walk(p, acc);
    else if (/\.(jsx?|tsx?)$/.test(e) && !e.endsWith('.test.js')) acc.push(p);
  }
  return acc;
}

test('no [hsl(var(--x))] colour class and no dark: class left in src/', () => {
  const left = [];
  for (const f of walk(SRC)) {
    const rel = path.relative(SRC, f).split(path.sep).join('/');
    if (PENDING.has(rel)) continue;
    const { pairs, dark } = rewrite(readFileSync(f, 'utf8'));
    if (pairs.length || dark.length) left.push(`${rel}: ${[...pairs.map((p) => p[0]), ...dark].slice(0, 3).join(' ')}`);
  }
  assert.deepEqual(left, []);
});

test('the codemod keeps variants and the opacity, and is idempotent', () => {
  const src = `<b className="hover:bg-[hsl(var(--accent-2)/0.08)] text-[hsl(var(--ink-2))] border-[hsl(var(--conf-med))]/45 dark:text-red-400 group-hover/callout:bg-[hsl(var(--ov-read)/0.22)]" />`;
  const { out, pairs, dark } = rewrite(src);
  assert.equal(out, '<b className="hover:bg-accent-2/[0.08] text-ink-2 border-conf-med/45 group-hover/callout:bg-ov-read/[0.22]" />');
  assert.equal(pairs.length, 4);
  assert.deepEqual(dark, ['dark:text-red-400']);
  assert.equal(rewrite(out).out, out);
  assert.equal(rewrite('"dark:bg-x foo"').out, '"foo"');
});

test('opacity: a Tailwind step stays a step, anything else is an arbitrary modifier', () => {
  assert.equal(opacitySuffix('0.75'), '/75');
  assert.equal(opacitySuffix('0.10'), '/10');
  assert.equal(opacitySuffix('0.08'), '/[0.08]');
});

test('an unknown token is left as it is', () => {
  const src = 'bg-[hsl(var(--not-a-colour))]';
  assert.equal(rewrite(src).out, src);
});
