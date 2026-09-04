import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import {
  mergeDarbuSarasasEdits,
  carriedOrphans,
  tierKey,
  normLabel,
  hasUserEdit,
} from './mergeDarbuSarasas.js';

const SNAPSHOT = new URL(
  '../../../backend/data/demo-objektas-a-snapshot-20260714.json', import.meta.url,
);

const money = (rows) => Math.round(
  rows.reduce((s, r) => s + (Number(r.kiekis) || 0) * (Number(r.kaina) || 0), 0) * 100,
) / 100;

// ── the P0: /recompute-interior deleted 15 priced rows worth 5 281,85 € ──────

test('P0: an unmatched PRICED row is carried, never deleted', () => {
  const old = [
    { aprasymas: 'Glaistymo kampai vidiniai', kiekis: 227.85, kaina: 19.49 },
    { aprasymas: 'Rozetės / jungiklio pajungimas', kiekis: 52, kaina: 12 },
  ];
  const rebuilt = [{ aprasymas: 'Sienų dažymas', kiekis: 100 }];
  const notes = [];
  const out = mergeDarbuSarasasEdits(rebuilt, old, notes);

  assert.equal(out.length, 3);
  const labels = out.map((r) => r.aprasymas);
  assert.ok(labels.includes('Glaistymo kampai vidiniai'));
  assert.ok(labels.includes('Rozetės / jungiklio pajungimas'));
  assert.equal(carriedOrphans(notes).length, 2);
  assert.ok(out.filter((r) => r._orphaned_after_rebuild).length === 2);
  // money intact
  assert.equal(money(out), money(old));
});

test('P0: an unmatched UNPRICED row is carried too', () => {
  // The old rule required source/manual_override — that is exactly how whole
  // 'Ventiliacijos' sections disappeared before the user got round to pricing.
  const old = [{ aprasymas: 'Ortakių D125 mm montavimas', kiekis: 24 }];
  const rebuilt = [{ aprasymas: 'Sienų dažymas', kiekis: 100 }];
  const notes = [];
  const out = mergeDarbuSarasasEdits(rebuilt, old, notes);
  assert.equal(out.length, 2);
  assert.equal(out[1].aprasymas, 'Ortakių D125 mm montavimas');
  assert.equal(out[1]._orphaned_after_rebuild, true);
  assert.equal(carriedOrphans(notes)[0].user_edit, false);
});

// ── the single exception: legitimate re-tiering ─────────────────────────────

test('an un-edited row re-tiered by the rebuild is NOT carried', () => {
  const old = [
    { aprasymas: 'Sienų, lubų glaistymas/dažymas (iki 3m aukščio)', kiekis: 80 },
    { aprasymas: 'Sienų, lubų glaistymas/dažymas (virš 3m aukščio)', kiekis: 40 },
  ];
  const rebuilt = [
    { aprasymas: 'Sienų, lubų glaistymas/dažymas (iki 3m aukščio)', kiekis: 120 },
  ];
  const notes = [];
  const out = mergeDarbuSarasasEdits(rebuilt, old, notes);
  assert.equal(out.length, 1, JSON.stringify(out));
  assert.deepEqual(notes.map((n) => n.reason), ['superseded_by_tier']);
});

test('…but a PRICED re-tiered row is carried anyway — money is not ours to drop', () => {
  const old = [
    { aprasymas: 'Sienų, lubų glaistymas/dažymas (iki 3m aukščio)', kiekis: 80, kaina: 3 },
    { aprasymas: 'Sienų, lubų glaistymas/dažymas (virš 3m aukščio)', kiekis: 40, kaina: 5 },
  ];
  const rebuilt = [
    { aprasymas: 'Sienų, lubų glaistymas/dažymas (iki 3m aukščio)', kiekis: 80 },
  ];
  const out = mergeDarbuSarasasEdits(rebuilt, old);
  const carried = out.filter((r) => r._orphaned_after_rebuild);
  assert.equal(carried.length, 1);
  assert.equal(carried[0].kaina, 5);
  assert.equal(money(out), 240 + 200);
});

test('GKP standartinis/virš-3m labels share a tier key', () => {
  assert.equal(
    tierKey('GKP lubų montavimas (standartinis aukštis)'),
    tierKey('GKP lubų montavimas (virš 3 m aukščio)'),
  );
  assert.equal(
    tierKey('Lubų glaistymas/dažymas (virš 3 m aukščio) — papildomas darbas dėl aukščio'),
    'lubų glaistymas/dažymas',
  );
});

test('tierKey does NOT fold the LED pair (backend _norm_label does — this must not)', () => {
  assert.notEqual(tierKey('LED nišų dažymas'), tierKey('LED nišų glaistymas/dažymas'));
  assert.notEqual(normLabel('LED nišų dažymas'), normLabel('LED nišų glaistymas/dažymas'));
});

test('the LED pair survives consolidation with its money', () => {
  const old = [
    { aprasymas: 'LED nišų glaistymas', kiekis: 40, kaina: 8 },
    { aprasymas: 'LED nišų dažymas', kiekis: 40, kaina: 8 },
  ];
  const rebuilt = [{ aprasymas: 'LED nišų glaistymas/dažymas', kiekis: 41.88 }];
  const out = mergeDarbuSarasasEdits(rebuilt, old);
  assert.equal(money(out), 640);
});

// ── behaviour that must NOT regress ─────────────────────────────────────────

test('pass 1 still carries price + manual count override onto the rebuilt row', () => {
  const old = [{
    aprasymas: 'Rozetės', kiekis: 50, kaina: 12.5,
    manual_override: true, quantity_source: 'manual_override', ai_kiekis_original: 52,
  }];
  const rebuilt = [{ aprasymas: 'Rozetės', kiekis: 52 }];
  const out = mergeDarbuSarasasEdits(rebuilt, old);
  assert.equal(out.length, 1);
  assert.equal(out[0].kiekis, 50);
  assert.equal(out[0].kaina, 12.5);
  assert.equal(out[0].suma, 625);
  assert.equal(out[0].ai_kiekis_original, 52);
});

test('pass 2 carries a price across a tier flip and re-sums on the new quantity', () => {
  const old = [{
    aprasymas: 'Sienų, lubų glaistymas/dažymas (virš 3m aukščio)', kiekis: 100, kaina: 5,
  }];
  const rebuilt = [{
    aprasymas: 'Sienų, lubų glaistymas/dažymas (iki 3m aukščio)', kiekis: 120,
  }];
  const notes = [];
  const out = mergeDarbuSarasasEdits(rebuilt, old, notes);
  assert.equal(out.length, 1);
  assert.equal(out[0].kaina, 5);
  assert.equal(out[0].suma, 600);
  assert.deepEqual(notes.map((n) => n.reason), ['relabeled']);
});

test('pass 2 refuses to guess when two rebuilt lines share the normalized key', () => {
  const old = [{
    aprasymas: 'Sienų, lubų glaistymas/dažymas (virš 3m aukščio)', kiekis: 40, kaina: 5,
  }];
  const rebuilt = [
    { aprasymas: 'Sienų, lubų glaistymas/dažymas (iki 3m aukščio)', kiekis: 80 },
    { aprasymas: 'Sienų, lubų glaistymas/dažymas (standartinis aukštis)', kiekis: 30 },
  ];
  const out = mergeDarbuSarasasEdits(rebuilt, old);
  // no rebuilt line inherits a price it can't be proven to own…
  assert.ok(out.filter((r) => !r._orphaned_after_rebuild).every((r) => r.kaina == null));
  // …and the price is carried, not destroyed.
  assert.equal(out.filter((r) => r._orphaned_after_rebuild)[0].kaina, 5);
});

test('drawing-marked user rows still survive (pre-existing contract)', () => {
  const old = [{ aprasymas: 'Rankinis skaičius', kiekis: 9, source: 'Pažymėjus brėžinyje' }];
  const rebuilt = [{ aprasymas: 'Sienų dažymas', kiekis: 100 }];
  const out = mergeDarbuSarasasEdits(rebuilt, old);
  assert.equal(out.length, 2);
  assert.equal(out[1].source, 'Pažymėjus brėžinyje');
  assert.equal(hasUserEdit(old[0]), true);
});

test('a server-declared rename is consumed, not double-counted', () => {
  // The backend folded 'LED nišų glaistymas' into the consolidated line and
  // carried its price there. Carrying the original here too would bill it twice.
  const old = [
    { aprasymas: 'LED nišų glaistymas', kiekis: 40, kaina: 8 },
    { aprasymas: 'LED nišų dažymas', kiekis: 40, kaina: 8 },
  ];
  const rebuilt = [
    { aprasymas: 'LED nišų glaistymas/dažymas', kiekis: 41.88, kaina: 8 },
    { aprasymas: 'LED nišų dažymas', kiekis: 40, kaina: 8 },
  ];
  const notes = [];
  const out = mergeDarbuSarasasEdits(rebuilt, old, notes,
    [{ reason: 'relabeled', aprasymas: 'LED nišų glaistymas', into: 'LED nišų glaistymas/dažymas' }]);
  assert.equal(out.length, 2, JSON.stringify(out.map((r) => r.aprasymas)));
  assert.equal(carriedOrphans(notes).length, 0);
  assert.ok(notes.some((n) => n.reason === 'relabeled_by_server'));
  assert.equal(money(out), Math.round(41.88 * 8 * 100) / 100 + 320);
});

test('a rename whose target is missing is IGNORED — the row is kept', () => {
  // Defensive: a bogus/stale note must never be able to delete money.
  const old = [{ aprasymas: 'LED nišų glaistymas', kiekis: 40, kaina: 8 }];
  const rebuilt = [{ aprasymas: 'Sienų dažymas', kiekis: 10 }];
  const out = mergeDarbuSarasasEdits(rebuilt, old, [],
    [{ reason: 'relabeled', aprasymas: 'LED nišų glaistymas', into: 'Nėra tokios eilutės' }]);
  assert.equal(out.length, 2);
  assert.equal(money(out), 320);
});

test('a non-array rebuilt payload leaves the old list untouched', () => {
  const old = [{ aprasymas: 'x', kiekis: 1 }];
  assert.equal(mergeDarbuSarasasEdits(undefined, old), old);
  assert.deepEqual(mergeDarbuSarasasEdits(null, undefined), []);
});

test('merging is idempotent — carried orphans do not multiply', () => {
  const old = [
    { aprasymas: 'Glaistymo kampai vidiniai', kiekis: 227.85, kaina: 19.49 },
    { aprasymas: 'Sienų dažymas', kiekis: 90, kaina: 4 },
  ];
  const rebuilt = [{ aprasymas: 'Sienų dažymas', kiekis: 100 }];
  const once = mergeDarbuSarasasEdits(rebuilt, old);
  const twice = mergeDarbuSarasasEdits(rebuilt, once);
  assert.equal(once.length, twice.length);
  assert.deepEqual(once.map((r) => r.aprasymas), twice.map((r) => r.aprasymas));
  assert.equal(money(once), money(twice));
});

// ── against the real 73-row blob ─────────────────────────────────────────────

test('the real demo blob loses no row and no euro on a 61-row rebuild', () => {
  const blob = JSON.parse(readFileSync(SNAPSHOT, 'utf-8'));
  const old = blob.darbu_sarasas.map((r, i) => ({
    ...r, kaina: r.kaina || 10 + i,
  }));
  // What /recompute-interior actually returns for this blob: the 61 rows the
  // canonical builder can regenerate (measured live 2026-07-28).
  const regenerable = new Set([
    'Glaistymo kampai vidiniai', 'Glaistymo kampai išoriniai',
    'LED nišų glaistymas', 'LED nišų dažymas', 'LED juostos pajungimas',
    'Ortakių D125 mm montavimas', 'Ortakių izoliacija (akmens vata + AlMg folija)',
    'Ortakių tvirtinimas (kabykės, rankės)', 'Rozetės / jungiklio pajungimas',
    'Lubinių priglaistomų šviestuvų montavimas', 'Skylių šviestuvams gręžimas',
    'Pakabinamų šviestuvų montavimas', 'Difūzorių montavimas (vėdinimo taškai)',
    'Difūzorių apdirbimas (priglaistomas)', 'Šviestuvų apdirbimai (gipsiniai priglaistomi)',
    'Šviestuvų apdirbimas (gipsiniai priglaistomi)',
  ]);
  const rebuilt = blob.darbu_sarasas
    .filter((r) => !regenerable.has(r.aprasymas))
    .map((r) => ({ ...r, kaina: undefined, suma: undefined }));
  assert.ok(rebuilt.length < old.length);

  const notes = [];
  const out = mergeDarbuSarasasEdits(rebuilt, old, notes);
  const after = new Set(out.map((r) => r.aprasymas));
  const lost = old.map((r) => r.aprasymas).filter((l) => !after.has(l));
  assert.deepEqual(lost, [], `rows deleted: ${lost}`);
  assert.equal(out.length, old.length);
  assert.equal(money(out), money(old));
  assert.equal(carriedOrphans(notes).length, old.length - rebuilt.length);
});

// ── the Medžiagos section (2026-09-02, contractor ask F2) ────────────────────
//
// Materials moved out of the work rows into one global section at the end. For
// a project priced BEFORE that move, the rebuild adds rows that never existed —
// so the invariant to pin is that gaining rows costs nothing: no priced row is
// deleted, and no price migrates onto a material.

test('Medžiagos rows appear without deleting a priced row or moving a price', () => {
  const old = [
    { aprasymas: 'Sienų glaistymas/dažymas', kiekis: 100, kaina: 12 },
    { aprasymas: 'Sienų lyginimas Knauf Rotband', kiekis: 30, kaina: 9 },
  ];
  const rebuilt = [
    { aprasymas: 'Sienų glaistymas/dažymas', kiekis: 100, skyrius: 'Sienų glaistymas dažymas' },
    { aprasymas: 'Sienų lyginimas Knauf Rotband', kiekis: 30, skyrius: 'Sienų glaistymas dažymas' },
    { aprasymas: 'Glaistas sienoms (pradinis + baigiamasis)', kiekis: 125, skyrius: 'Medžiagos',
      susijes_darbas: 'Sienų glaistymas/dažymas' },
    { aprasymas: 'Rotband (~10 kg/m² esant 5mm storiui)', kiekis: 300, skyrius: 'Medžiagos',
      susijes_darbas: 'Sienų lyginimas Knauf Rotband' },
  ];
  const notes = [];
  const out = mergeDarbuSarasasEdits(rebuilt, old, notes);

  assert.equal(out.length, 4, 'no orphan carried — every old row was matched');
  assert.equal(carriedOrphans(notes).length, 0);
  const by = Object.fromEntries(out.map((r) => [r.aprasymas, r]));
  // the two priced work rows keep their €/vnt …
  assert.equal(by['Sienų glaistymas/dažymas'].kaina, 12);
  assert.equal(by['Sienų lyginimas Knauf Rotband'].kaina, 9);
  // … and the money did not follow the material into the shopping list.
  assert.equal(by['Glaistas sienoms (pradinis + baigiamasis)'].kaina, undefined);
  assert.equal(by['Rotband (~10 kg/m² esant 5mm storiui)'].kaina, undefined);
  assert.equal(money(out), money(old));
});

test('a priced material keeps its price across the next rebuild', () => {
  const mat = {
    aprasymas: 'Glaistas luboms (pradinis + baigiamasis)', kiekis: 200,
    skyrius: 'Medžiagos', susijes_darbas: 'Lubų glaistymas/dažymas', kaina: 0.9,
  };
  const rebuilt = [{ ...mat, kiekis: 180, kaina: undefined, suma: undefined }];
  const out = mergeDarbuSarasasEdits(rebuilt, [mat]);
  assert.equal(out.length, 1);
  assert.equal(out[0].kaina, 0.9);
  assert.equal(out[0].kiekis, 180, 'the quantity is the rebuild’s, the price is the user’s');
  assert.equal(out[0].suma, 162);
});

// ── the kainynas fill must not turn a benign tier fold into over-billing ─────
//
// Before the automatic price fill (2026-09-02) every row arrived unpriced, so
// pass 3's "an un-edited superseded tier line is dropped" rule fired and a
// lowered ceiling simply re-tiered the work. Now `autoFillFromDefaultPriceList`
// prices EVERY matched row at extraction, `hasUserEdit` reads any non-zero
// kaina as the user's hand, and the same edit left the old (virš 3m) line on
// the books next to its own successor — 240 m² billed where 200 m² exist.

const FOLD_KEPT = 'Sienų glaistymas/dažymas (iki 3m aukščio)';
const FOLD_GONE = 'Sienų glaistymas/dažymas (virš 3m aukščio)';

function foldCase(kainaSource) {
  const price = kainaSource ? { kaina: 7.5, kaina_source: kainaSource } : { kaina: 7.5 };
  return {
    rebuilt: [{ aprasymas: FOLD_KEPT, kiekis: 240, vnt: 'm2' }],
    old: [
      { aprasymas: FOLD_KEPT, kiekis: 200, vnt: 'm2', ...price },
      { aprasymas: FOLD_GONE, kiekis: 40, vnt: 'm2', ...price },
    ],
  };
}

const billed = (rows) => Math.round(
  rows.reduce((s, r) => s + (Number(r.kiekis) || 0), 0) * 100) / 100;

test('a kainynas price does not veto a tier fold (240 m², billed once)', () => {
  const { rebuilt, old } = foldCase('kainynas');
  const notes = [];
  const out = mergeDarbuSarasasEdits(rebuilt, old, notes);
  assert.equal(billed(out), 240, JSON.stringify(out.map((r) => [r.aprasymas, r.kiekis])));
  assert.equal(out.filter((r) => r._orphaned_after_rebuild).length, 0,
    'the re-tiered line came back as a priced orphan — the client pays twice');
  assert.deepEqual(
    notes.filter((n) => n.aprasymas === FOLD_GONE).map((n) => n.reason),
    ['superseded_by_tier']);
  // …and the contractor does not lose the price either.
  assert.equal(out[0].kaina, 7.5);
  assert.equal(out[0].suma, 1800);
});

test('an unpriced fold still folds', () => {
  const { rebuilt, old } = foldCase(null);
  for (const o of old) delete o.kaina;
  assert.equal(billed(mergeDarbuSarasasEdits(rebuilt, old)), 240);
});

test('a hand-typed price still vetoes the fold', () => {
  const { rebuilt, old } = foldCase('manual');
  const out = mergeDarbuSarasasEdits(rebuilt, old);
  assert.deepEqual(
    out.filter((r) => r._orphaned_after_rebuild).map((r) => r.aprasymas), [FOLD_GONE]);
});

test('a corrected quantity vetoes the fold even when the kainynas priced it', () => {
  const { rebuilt, old } = foldCase('kainynas');
  old[1].manual_override = true;
  const out = mergeDarbuSarasasEdits(rebuilt, old);
  assert.deepEqual(
    out.filter((r) => r._orphaned_after_rebuild).map((r) => r.aprasymas), [FOLD_GONE]);
});

test('the fold transfers the price when only the old tier was priced', () => {
  const rebuilt = [{ aprasymas: FOLD_KEPT, kiekis: 240, vnt: 'm2' }];
  const old = [{ aprasymas: FOLD_GONE, kiekis: 40, vnt: 'm2',
                 kaina: 7.5, kaina_source: 'kainynas' }];
  const out = mergeDarbuSarasasEdits(rebuilt, old);
  assert.equal(out.length, 1);
  assert.equal(out[0].kaina, 7.5);
  assert.equal(out[0].kaina_source, 'kainynas');
});

// ── a hand-typed price keeps its 'manual' flag across a rebuild ──────────────

test('price provenance survives the merge', () => {
  const old = [
    { aprasymas: 'Sienų dažymas', kiekis: 100, kaina: 15, kaina_source: 'manual' },
    { aprasymas: 'Lubų dažymas', kiekis: 50, kaina: 7,
      kaina_source: 'kainynas', kaina_match_score: 0.92 },
  ];
  const rebuilt = [
    { aprasymas: 'Sienų dažymas', kiekis: 110 },
    { aprasymas: 'Lubų dažymas', kiekis: 50 },
  ];
  const by = Object.fromEntries(
    mergeDarbuSarasasEdits(rebuilt, old).map((r) => [r.aprasymas, r]));
  assert.equal(by['Sienų dažymas'].kaina_source, 'manual');
  assert.equal(by['Lubų dažymas'].kaina_source, 'kainynas');
  assert.equal(by['Lubų dažymas'].kaina_match_score, 0.92);
});

// ── the paint split must not orphan a priced legacy row ─────────────────────

test('a legacy merged paint row survives a tiered → untiered rebuild', () => {
  const old = [{ aprasymas: 'Sienų, lubų glaistymas/dažymas (virš 3m aukščio)',
                 kiekis: 100, kaina: 9 }];
  const rebuilt = [
    { aprasymas: 'Sienų glaistymas/dažymas', kiekis: 120 },
    { aprasymas: 'Lubų glaistymas/dažymas', kiekis: 60 },
  ];
  const out = mergeDarbuSarasasEdits(rebuilt, old);
  const by = Object.fromEntries(out.map((r) => [r.aprasymas, r]));
  assert.equal(by['Sienų glaistymas/dažymas'].kaina, 9);
  // the ceiling half comes back unpriced — visible and correct
  assert.equal(by['Lubų glaistymas/dažymas'].kaina, undefined);
  assert.equal(out.filter((r) => r._orphaned_after_rebuild).length, 0);
});

test('a legacy tier line lands on its own tier when both exist', () => {
  const old = [{ aprasymas: 'Sienų, lubų glaistymas/dažymas (virš 3m aukščio)',
                 kiekis: 100, kaina: 9 }];
  const rebuilt = [
    { aprasymas: 'Sienų glaistymas/dažymas (iki 3m aukščio)', kiekis: 120 },
    { aprasymas: 'Sienų glaistymas/dažymas (virš 3m aukščio)', kiekis: 60 },
  ];
  const by = Object.fromEntries(
    mergeDarbuSarasasEdits(rebuilt, old).map((r) => [r.aprasymas, r]));
  assert.equal(by['Sienų glaistymas/dažymas (virš 3m aukščio)'].kaina, 9);
  assert.equal(by['Sienų glaistymas/dažymas (iki 3m aukščio)'].kaina, undefined);
});

test('the tier rename still refuses to guess a tier', () => {
  const old = [{ aprasymas: 'Sienų, lubų glaistymas/dažymas', kiekis: 100, kaina: 9 }];
  const rebuilt = [
    { aprasymas: 'Sienų glaistymas/dažymas (iki 3m aukščio)', kiekis: 120 },
    { aprasymas: 'Sienų glaistymas/dažymas (virš 3m aukščio)', kiekis: 60 },
  ];
  const out = mergeDarbuSarasasEdits(rebuilt, old);
  assert.ok(out.filter((r) => !r._orphaned_after_rebuild).every((r) => r.kaina == null));
  const carried = out.filter((r) => r._orphaned_after_rebuild);
  assert.equal(carried.length, 1);
  assert.equal(carried[0].kaina, 9);
});

test('a legacy row never shadows a row that owns the new label', () => {
  const old = [
    { aprasymas: 'Sienų, lubų glaistymas/dažymas', kiekis: 100, kaina: 9 },
    { aprasymas: 'Sienų glaistymas/dažymas', kiekis: 120, kaina: 12 },
  ];
  const rebuilt = [{ aprasymas: 'Sienų glaistymas/dažymas', kiekis: 120 }];
  const out = mergeDarbuSarasasEdits(rebuilt, old);
  const walls = out.find((r) => r.aprasymas === 'Sienų glaistymas/dažymas'
    && !r._orphaned_after_rebuild);
  assert.equal(walls.kaina, 12, 'the legacy row shadowed the user’s own row');
});

// ── the shopping list stays at the foot of the sąmata ───────────────────────

test('a carried orphan never lands below the shopping list', () => {
  const old = [{ aprasymas: 'Ventiliacijos ortakiai', kiekis: 12, kaina: 30,
                 skyrius: 'Ventiliacijos darbai' }];
  const rebuilt = [
    { aprasymas: 'Sienų dažymas', kiekis: 100, skyrius: 'Sienų glaistymas dažymas' },
    { aprasymas: 'Dažai sienoms', kiekis: 20, skyrius: 'Medžiagos' },
  ];
  const out = mergeDarbuSarasasEdits(rebuilt, old);
  assert.equal(out[out.length - 1].skyrius, 'Medžiagos',
    JSON.stringify(out.map((r) => [r.aprasymas, r.skyrius])));
});

// ── pass 0: the stable id (2026-09-02, Patikra P0) ──────────────────────────

test('pass 0 carries a price across a RELABEL when both rows share an id', () => {
  const old = [{ id: 'abc123abc123', aprasymas: 'Sienų šlifavimas', kiekis: 100, kaina: 7 }];
  const rebuilt = [{
    id: 'abc123abc123',
    aprasymas: 'Sienų šlifavimas Q4 (80–120 grit, 100% paviršius)',
    kiekis: 100,
  }];
  const notes = [];
  const out = mergeDarbuSarasasEdits(rebuilt, old, notes);
  assert.equal(out.length, 1, 'the relabeled row was carried alongside its successor');
  assert.equal(out[0].kaina, 7);
  assert.equal(notes.filter((n) => n.reason === 'relabeled').length, 1);
});

test('pass 0 never spends one old row on two rebuilt rows', () => {
  const old = [{ id: 'dup', aprasymas: 'Sienų dažymas', kiekis: 100, kaina: 5 }];
  const rebuilt = [
    { id: 'dup', aprasymas: 'Sienų dažymas', kiekis: 100 },
    { id: 'dup', aprasymas: 'Sienų dažymas', kiekis: 100 },
  ];
  const out = mergeDarbuSarasasEdits(rebuilt, old);
  assert.equal(out.filter((r) => r.kaina === 5).length, 1);
});

test('an id mismatch falls through to the label passes, unchanged', () => {
  const old = [{ id: 'rnk-aaaa', aprasymas: 'Sienų dažymas', kiekis: 100, kaina: 5 }];
  const rebuilt = [{ id: 'bbbb', aprasymas: 'Sienų dažymas', kiekis: 110 }];
  const out = mergeDarbuSarasasEdits(rebuilt, old);
  assert.equal(out.length, 1);
  assert.equal(out[0].kaina, 5);
  assert.equal(out[0].kiekis, 110);
});

test('rows with no id at all behave exactly as before', () => {
  const old = [
    { aprasymas: 'Sienų dažymas', kiekis: 100, kaina: 5 },
    { aprasymas: 'Rozetės / jungiklio pajungimas', kiekis: 52, kaina: 12 },
  ];
  const rebuilt = [{ aprasymas: 'Sienų dažymas', kiekis: 110 }];
  const notes = [];
  const out = mergeDarbuSarasasEdits(rebuilt, old, notes);
  assert.equal(out.length, 2);
  assert.equal(out[0].kaina, 5);
  assert.equal(carriedOrphans(notes).length, 1);
});

// ── id uniqueness after the merge (JS twin of backend `_reassign_duplicate_ids`) ──
import { reassignDuplicateIds } from './mergeDarbuSarasas.js';

test('reassignDuplicateIds: the rebuilt row keeps the clean id, the orphan takes -2', () => {
  const rows = [
    { id: 'abc', aprasymas: 'Nauja', _orphaned_after_rebuild: true },   // orphan listed FIRST
    { id: 'abc', aprasymas: 'Nauja' },                                   // canonical rebuilt row
    { id: 'xyz', aprasymas: 'Kita' },
  ];
  const out = reassignDuplicateIds(rows);
  assert.equal(out[1].id, 'abc');      // canonical keeps the clean id regardless of order
  assert.equal(out[0].id, 'abc-2');    // orphan renamed
  assert.equal(out[2].id, 'xyz');
  assert.equal(rows[0].id, 'abc');     // input not mutated
});

test('reassignDuplicateIds: counts up past an id that already carries a suffix', () => {
  const rows = [
    { id: 'abc' },
    { id: 'abc-2', _orphaned_after_rebuild: true },
    { id: 'abc', _orphaned_after_rebuild: true },
  ];
  const ids = reassignDuplicateIds(rows).map(r => r.id);
  assert.deepEqual(ids, ['abc', 'abc-2', 'abc-3']);
  assert.equal(new Set(ids).size, ids.length);
});

test('reassignDuplicateIds: rows without ids are left alone', () => {
  const rows = [{ aprasymas: 'sena' }, { id: '', aprasymas: 'tuščias' }, { id: 'k1' }];
  const out = reassignDuplicateIds(rows);
  assert.equal(out[0].id, undefined);
  assert.equal(out[1].id, '');
  assert.equal(out[2].id, 'k1');
});

import { newlyCarriedOrphans } from './mergeDarbuSarasas.js';

test('newlyCarriedOrphans: an already-orphaned prior row is not announced again', () => {
  const notes = [
    { reason: 'orphan_carried', id: 'old-1', aprasymas: 'Sienų pirminis glaistymas Q1' },
    { reason: 'orphan_carried', aprasymas: 'Nauja pasenusi eilutė' },
    { reason: 'relabeled', aprasymas: 'kažkas kita' },
  ];
  const prior = [
    { id: 'old-1', aprasymas: 'Sienų pirminis glaistymas Q1', _orphaned_after_rebuild: true },
    { id: 'live', aprasymas: 'Nauja pasenusi eilutė' },   // was live → orphaned NOW → news
  ];
  assert.deepEqual(newlyCarriedOrphans(notes, prior).map(n => n.aprasymas), ['Nauja pasenusi eilutė']);
  assert.equal(newlyCarriedOrphans(notes, []).length, 2);   // no prior flags → all are news
});
