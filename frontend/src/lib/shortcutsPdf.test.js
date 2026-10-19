import test from 'node:test';
import assert from 'node:assert/strict';
import { jpegToA4Pdf, drawShortcutSheet } from './shortcutsPdf.js';
import { shortcutGuideRows } from './viewerShortcuts.js';

const text = (bytes) => new TextDecoder('latin1').decode(bytes);

test('jpegToA4Pdf: one A4 page with the image, and a correct xref', () => {
  const jpeg = new Uint8Array([0xff, 0xd8, 1, 2, 3, 0xff, 0xd9]);
  const pdf = jpegToA4Pdf(jpeg, 1240, 1754);
  const s = text(pdf);
  assert.ok(s.startsWith('%PDF-1.4'));
  assert.ok(s.trimEnd().endsWith('%%EOF'));
  assert.match(s, /\/MediaBox \[0 0 595\.28 841\.89\]/);
  assert.match(s, /\/Width 1240 \/Height 1754/);
  assert.match(s, /\/Length 7 >>/);
  // every xref offset points at its "n 0 obj"
  const xrefAt = Number(s.match(/startxref\n(\d+)/)[1]);
  assert.ok(s.slice(xrefAt).startsWith('xref'));
  const offs = [...s.slice(xrefAt).matchAll(/^(\d{10}) 00000 n $/gm)].map((m) => Number(m[1]));
  assert.equal(offs.length, 5);
  offs.forEach((o, i) => assert.ok(s.slice(o).startsWith(`${i + 1} 0 obj`), `object ${i + 1}`));
});

test('drawShortcutSheet draws every row label on the page', () => {
  const drawn = [];
  const ctx = {
    fillStyle: '', font: '', textBaseline: '',
    fillRect() {}, measureText: (t) => ({ width: t.length * 9 }),
    fillText: (t, x, y) => drawn.push({ t, x, y }),
  };
  const rows = shortcutGuideRows({ mac: false });
  drawShortcutSheet(ctx, rows, { w: 1240, h: 1754, title: 'T', subtitle: 'S' });
  const all = drawn.map((d) => d.t).join(' ');
  for (const r of rows) {
    assert.ok(all.includes(r.title.toUpperCase()), r.title);
    for (const it of r.items) assert.ok(all.includes(it.label.split(' ')[0]), it.id);
  }
  for (const d of drawn) assert.ok(d.y < 1754 && d.x < 1240, `"${d.t}" drawn off the page at ${d.x},${d.y}`);
  // the list ends above the footer line (one A4 page, v3: the body shrinks to fit when the table grows)
  const footer = drawn.find((d) => d.t.startsWith('Pathon ·'));
  for (const d of drawn.filter((x) => x !== footer)) assert.ok(d.y < footer.y, `"${d.t}" runs into the footer`);
});
