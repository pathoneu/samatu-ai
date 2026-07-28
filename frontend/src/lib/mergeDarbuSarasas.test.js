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
  '../../../backend/data/demo-berzu-24-snapshot-20260714.json', import.meta.url,
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
