import test from 'node:test';
import assert from 'node:assert/strict';
import {
  EXPORT_FALLBACK_SECTION,
  asksAboutPricesAfterDialog,
  exportLines,
  exportSectionOf,
  exportSections,
  linesForExport,
  linesWithQuantity,
  linesWithoutPrice,
  rowNeedsPrice,
  rowsWithoutQuantity,
  sendCheck,
  sharedLines,
} from './exportLines.js';
import { manualPricePatch } from './applyPriceList.js';

const row = (over = {}) => ({
  eil_nr: 1, aprasymas: 'Sienų dažymas', mato_vnt: 'm²', kiekis: 10, skyrius: 'Dažymas', ...over,
});

// ── exportLines: the rows the Excel / PDF print ─────────────────────────────

test('exportLines drops rows without a quantity and prints a missing price as 0', () => {
  const lines = exportLines({
    darbu_sarasas: [
      row({ eil_nr: 1, kaina: 5 }),
      row({ eil_nr: 2, kiekis: 0, kaina: 5 }),
      row({ eil_nr: 3, kiekis: null }),
      row({ eil_nr: 4 }),                       // kaina absent
    ],
  });
  assert.deepEqual(lines.map((l) => l.nr), ['1', '4']);
  assert.equal(lines[0].suma, 50);
  assert.equal(lines[1].kaina, 0);
  assert.equal(lines[1].suma, 0);
});

test('exportLines keeps only the ticked sections and names a bare row „Kiti darbai"', () => {
  const project = {
    darbu_sarasas: [
      row({ eil_nr: 1, skyrius: 'Dažymas' }),
      row({ eil_nr: 2, skyrius: 'Medžiagos' }),
      row({ eil_nr: 3, skyrius: undefined, kategorija: 'Elektra' }),
      row({ eil_nr: 4, skyrius: undefined }),
    ],
  };
  assert.deepEqual(exportLines(project).map((l) => l.skyrius),
    ['Dažymas', 'Medžiagos', 'Elektra', EXPORT_FALLBACK_SECTION]);
  assert.deepEqual(exportLines(project, new Set(['Dažymas', 'Elektra'])).map((l) => l.nr), ['1', '3']);
});

test('exportLines applies the floor multiplier to quantities and sums', () => {
  const lines = exportLines({
    prielaidos: { aukstu_skaicius: 3 },
    darbu_sarasas: [row({ kiekis: 2, kaina: 10 })],
  });
  assert.equal(lines[0].kiekis, 6);
  assert.equal(lines[0].suma, 60);
});

test('exportLines falls back to project.rows (KŽ) when there is no darbu_sarasas', () => {
  const lines = exportLines({
    darbu_sarasas: [],
    rows: [{ nr: '1', aprasymas: 'Kasimas', mato_vnt: 'm³', kiekis: 4, kaina: 0, skyrius: 'Žemės darbai' }],
  });
  assert.equal(lines.length, 1);
  assert.equal(lines[0].skyrius, 'Žemės darbai');
  assert.equal(lines[0].suma, 0);
});

test('exportSectionOf: skyrius, then kategorija, then the fallback', () => {
  assert.equal(exportSectionOf({ skyrius: 'A', kategorija: 'B' }), 'A');
  assert.equal(exportSectionOf({ kategorija: 'B' }), 'B');
  assert.equal(exportSectionOf({}), EXPORT_FALLBACK_SECTION);
  assert.equal(exportSectionOf(null), EXPORT_FALLBACK_SECTION);
});

// ── What „no price" means ────────────────────────────────────────────────────

test('null, undefined, empty and 0 are all „no price"; any positive price is a price', () => {
  const lines = exportLines({
    darbu_sarasas: [
      row({ eil_nr: 1, kaina: null }),
      row({ eil_nr: 2 }),
      row({ eil_nr: 3, kaina: '' }),
      row({ eil_nr: 4, kaina: 0 }),
      row({ eil_nr: 5, kaina: 0.01 }),
      row({ eil_nr: 6, kaina: 12.5 }),
    ],
  });
  assert.deepEqual(linesWithoutPrice(lines).map((l) => l.nr), ['1', '2', '3', '4']);
});

test('a price he cleared to 0 counts as no price — the model does not keep a typed 0', () => {
  // This is the data-model check the count relies on: clearing a price resets
  // its source, so a typed 0 cannot be told apart from „never priced".
  const priced = row({ kaina: 8, kaina_source: 'manual' });
  const cleared = { ...priced, kaina: 0, ...manualPricePatch(priced, 0) };
  assert.equal(cleared.kaina_source, undefined);
  assert.equal(linesWithoutPrice(exportLines({ darbu_sarasas: [cleared] })).length, 1);
  assert.equal(rowNeedsPrice(cleared), true);
});

test('a row without a quantity is skipped, never counted as unpriced', () => {
  const lines = [{ kiekis: 0, kaina: 0 }, { kiekis: null, kaina: null }, { kiekis: 3, kaina: 0 }];
  assert.equal(linesWithQuantity(lines).length, 1);
  assert.equal(linesWithoutPrice(lines).length, 1);
});

// ── His own layout ('excel-template') ───────────────────────────────────────

test('linesForExport reads his rendered rows for his layout, ours otherwise', () => {
  const project = { darbu_sarasas: [row({ skyrius: 'Mūsų skyrius' })] };
  const templateRows = [
    { aprasymas: 'Glaistymas', skyrius: 'Jo darbai', kiekis: 4, kaina: 6, _sablonas: true },
    { aprasymas: 'Dažymas', skyrius: 'Jo darbai', kiekis: 4, kaina: null, _sablonas: true },
    { aprasymas: 'Plytelės', skyrius: 'Jo darbai', kiekis: null, _sablonas: true },   // blank cell
    { aprasymas: 'Kita', skyrius: 'Kita (iš brėžinio)', kiekis: 2, kaina: 0 },
  ];
  const his = linesForExport(project, { format: 'excel-template', templateRows });
  assert.equal(his.length, 4);
  assert.equal(linesWithoutPrice(his).length, 2, 'Dažymas + Kita; the blank cell is not counted');
  const ticked = linesForExport(project, {
    format: 'excel-template', templateRows, allowedSkyriai: new Set(['Jo darbai']),
  });
  assert.equal(linesWithoutPrice(ticked).length, 1);
  const ours = linesForExport(project, { format: 'excel' });
  assert.deepEqual(ours.map((l) => l.skyrius), ['Mūsų skyrius']);
  assert.deepEqual(linesForExport(project, { format: 'pdf' }), ours);
});

test('a merged line of his counts when part of it is unpriced, not when it has several prices', () => {
  const templateRows = [
    // fully priced at two prices: Kaina blank, Suma is the line's own amount
    { aprasymas: 'A', skyrius: 'S', kiekis: 5, kaina: null, suma: 40, _suma_be_vieneto_kainos: true },
    // part of its quantity has no price yet
    { aprasymas: 'B', skyrius: 'S', kiekis: 5, kaina: null, suma: 20,
      _suma_be_vieneto_kainos: true, _dalis_be_kainos: true },
  ];
  const lines = linesForExport({}, { format: 'excel-template', templateRows });
  assert.deepEqual(linesWithoutPrice(lines).map((l) => l.aprasymas), ['B']);
});

// ── The client link ──────────────────────────────────────────────────────────

test('sharedLines lists every section with a quantity — the link has no section filter', () => {
  const project = {
    darbu_sarasas: [
      row({ skyrius: 'Dažymas', kaina: 5 }),
      row({ skyrius: 'Medžiagos' }),
      row({ skyrius: 'Medžiagos', kiekis: 0 }),
      // a stale sum without a price still shows 0,00 € on the link
      row({ skyrius: 'Elektra', kaina: undefined, suma: 99 }),
    ],
  };
  const lines = sharedLines(project);
  assert.equal(lines.length, 3);
  assert.equal(linesWithoutPrice(lines).length, 2);
  assert.equal(sharedLines({}).length, 0);
});

// ── rowNeedsPrice: the row the Sąmata step opens ─────────────────────────────

test('rowNeedsPrice agrees with the printed lines, with and without unticked sections', () => {
  const darbu = [
    row({ eil_nr: 1, kaina: 5 }),
    row({ eil_nr: 2 }),
    row({ eil_nr: 3, kiekis: 0 }),
    row({ eil_nr: 4, skyrius: 'Medžiagos', kaina: 0 }),
    row({ eil_nr: 5, skyrius: undefined, kategorija: 'Elektra', kaina: null }),
    row({ eil_nr: 6, skyrius: undefined }),
    row({ eil_nr: 7, kiekis: -2 }),
  ];
  for (const excluded of [null, new Set(['Medžiagos']), new Set(['Elektra', EXPORT_FALLBACK_SECTION])]) {
    const fromRows = darbu.filter((r) => rowNeedsPrice(r, excluded)).map((r) => String(r.eil_nr));
    const lines = exportLines({ darbu_sarasas: darbu }).filter((l) => !excluded?.has(l.skyrius));
    assert.deepEqual(fromRows, linesWithoutPrice(lines).map((l) => l.nr), String([...(excluded || [])]));
  }
  assert.equal(rowNeedsPrice(null), false);
});

// ── sendCheck: the Siųsti step ───────────────────────────────────────────────

function project116() {
  // The walkthrough's shape: 116 rows, 10 without a quantity, 12 priced by the
  // kainynas, the rest with a quantity and no price.
  const darbu = [];
  for (let i = 1; i <= 116; i += 1) {
    const skyrius = i <= 42 ? 'Medžiagos' : 'Darbai';
    if (i <= 10) darbu.push(row({ eil_nr: i, skyrius: 'Darbai', kiekis: null }));
    else if (i <= 22) darbu.push(row({ eil_nr: i, skyrius: 'Darbai', kaina: 7, kaina_source: 'kainynas' }));
    else darbu.push(row({ eil_nr: i, skyrius }));
  }
  return { id: 'p', darbu_sarasas: darbu };
}

test('sendCheck counts rows the documents would print without a price', () => {
  const p = project116();
  assert.deepEqual(sendCheck(p), { rows: 116, noQty: 10, noPrice: 94 });
});

test('sendCheck leaves out the sections he unticked for the export', () => {
  const p = project116();
  // rows 23..42 are Medžiagos (20 unpriced); the remaining 74 stay
  assert.deepEqual(sendCheck(p, new Set(['Medžiagos'])), { rows: 116, noQty: 10, noPrice: 74 });
});

test('sendCheck: a priced sąmata, an empty one, and a negative quantity', () => {
  assert.deepEqual(sendCheck({ darbu_sarasas: [row({ kaina: 3 })] }), { rows: 1, noQty: 0, noPrice: 0 });
  assert.deepEqual(sendCheck({}), { rows: 0, noQty: 0, noPrice: 0 });
  assert.deepEqual(sendCheck(null), { rows: 0, noQty: 0, noPrice: 0 });
  // the export drops a negative quantity, so it is „skipped", not unpriced
  assert.deepEqual(sendCheck({ darbu_sarasas: [row({ kiekis: -1 })] }), { rows: 1, noQty: 1, noPrice: 0 });
  assert.equal(rowsWithoutQuantity([null, { kiekis: '2' }, { kiekis: 'x' }]).length, 2);
});

// ── exportSections: the dialog lists what the export filters on ─────────────

test('a row with neither skyrius nor kategorija is listed and exported under one name — never dropped', () => {
  // 2026-10-06: the dialog called such a row „Kiti darbai", the export filed it under „Apdaila", so with every
  // listed section ticked the Excel / PDF still left it out without a word
  const project = {
    darbu_sarasas: [
      row({ eil_nr: 1, skyrius: 'Dažymas', kaina: 5 }),
      row({ eil_nr: 2, skyrius: undefined, kategorija: undefined }),
      row({ eil_nr: 3, skyrius: '', kategorija: '' }),
      row({ eil_nr: 4, skyrius: 'Kiti darbai', kaina: 2 }),          // a hand-added row in „Kiti darbai"
      row({ eil_nr: 5, skyrius: undefined, kiekis: 0 }),              // no quantity: printed nowhere, listed nowhere
    ],
  };
  const sections = exportSections(linesForExport(project, { format: 'excel' }));
  assert.equal(EXPORT_FALLBACK_SECTION, 'Kiti darbai', 'the name the Sąmata step shows such a row under');
  assert.deepEqual(sections, [{ name: 'Dažymas', count: 1 }, { name: 'Kiti darbai', count: 3 }]);
  // everything ticked — what the dialog sends by default — prints every row it listed
  const all = new Set(sections.map((s) => s.name));
  assert.deepEqual(exportLines(project, all).map((l) => l.nr), ['1', '2', '3', '4']);
  assert.deepEqual(exportLines(project, all).map((l) => l.skyrius), ['Dažymas', 'Kiti darbai', 'Kiti darbai', 'Kiti darbai']);
  // and unticking the section leaves out exactly the rows listed under it
  assert.deepEqual(exportLines(project, new Set(['Dažymas'])).map((l) => l.nr), ['1']);
  // the price warning counts the bare rows too (2 and 3 have no price)
  assert.equal(linesWithoutPrice(exportLines(project, all)).length, 2);
});

test('in every layout the listed sections cover every printed line', () => {
  const project = {
    darbu_sarasas: [
      row({ eil_nr: 1 }),
      row({ eil_nr: 2, skyrius: undefined, kategorija: 'Elektra' }),
      row({ eil_nr: 3, skyrius: undefined }),
    ],
  };
  const templateRows = [
    { aprasymas: 'Glaistymas', skyrius: 'Jo darbai', kiekis: 4, kaina: 6, _sablonas: true },
    { aprasymas: 'Plytelės', skyrius: 'Jo darbai', kiekis: null, _sablonas: true },     // a blank cell: listed too
    { aprasymas: 'Rozetės', kategorija: 'Elektra', kiekis: 2, kaina: 0 },               // no skyrius: „Kita (iš brėžinio)"
    { aprasymas: 'Kita', kiekis: 1, kaina: 3 },
  ];
  for (const format of ['excel', 'pdf', 'excel-template']) {
    const lines = linesForExport(project, { format, templateRows });
    const names = new Set(exportSections(lines).map((s) => s.name));
    const ticked = linesForExport(project, { format, templateRows, allowedSkyriai: names });
    assert.equal(ticked.length, lines.length, `${format}: a listed section missed a printed line`);
    assert.equal(exportSections(lines).reduce((n, s) => n + s.count, 0), lines.length, format);
  }
  const his = exportSections(linesForExport(project, { format: 'excel-template', templateRows }));
  assert.deepEqual(his, [{ name: 'Jo darbai', count: 2 }, { name: 'Kita (iš brėžinio)', count: 2 }]);
  assert.deepEqual(exportSections(null), []);
});

// ── asksAboutPricesAfterDialog: no second question after the dialog's line ───

test('the dialog already said how many lines have no price — the export asks nothing more', () => {
  const some = { darbu_sarasas: [row({ eil_nr: 1, kaina: 5 }), row({ eil_nr: 2 })] };
  assert.equal(asksAboutPricesAfterDialog(some, exportLines(some)), false, 'partly priced: the line says 1');
  const none = { darbu_sarasas: [row({ eil_nr: 1 }), row({ eil_nr: 2 })] };
  assert.equal(asksAboutPricesAfterDialog(none, exportLines(none)), false, 'nothing priced: the line says 2');
  const all = { darbu_sarasas: [row({ kaina: 4 })] };
  assert.equal(asksAboutPricesAfterDialog(all, exportLines(all)), false, 'all priced: nothing to say');
  assert.equal(asksAboutPricesAfterDialog({}, []), false, 'an empty sąmata');
});

test('his own layout with every cell blank and no price anywhere still asks once', () => {
  // the dialog's line counts lines WITH a quantity; here there is none, so the line is silent
  const project = { darbu_sarasas: [row({ kiekis: 3 })] };
  const blank = [{ aprasymas: 'Plytelės', skyrius: 'Jo darbai', kiekis: null, _sablonas: true }];
  const lines = linesForExport(project, { format: 'excel-template', templateRows: blank });
  assert.equal(linesWithoutPrice(lines).length, 0);
  assert.equal(asksAboutPricesAfterDialog(project, lines), true);
  // …not when the sąmata does carry a price somewhere
  const priced = { darbu_sarasas: [row({ kiekis: 3, kaina: 2 })] };
  assert.equal(asksAboutPricesAfterDialog(priced, linesForExport(priced, { format: 'excel-template', templateRows: blank })), false);
});
