/**
 * Packaging beside a material quantity (v3 W5-E, E6): bags of putty (CLAUDE.md §1.11, ⌈kg / 25⌉) and
 * buckets of paint and primer (§1.10, full containers). A note — the row's kg and l never change.
 */
import test from 'node:test';
import assert from 'node:assert/strict';

import {
  BAG_KEY, BUCKET_KEY, DEFAULT_BAG_KG, DEFAULT_BUCKET_L, packagingNote, packagingSizes,
} from './packaging.js';

const row = (aprasymas, kiekis, mato_vnt) => ({ skyrius: 'Medžiagos', aprasymas, kiekis, mato_vnt });

test('putty kilograms are bags of 25 kg, rounded up (CLAUDE.md §1.11)', () => {
  assert.equal(packagingNote(row('Glaistas sienoms (pradinis + baigiamasis)', 405.56, 'kg')), '17 maišų po 25 kg');
  assert.equal(packagingNote(row('Glaistas luboms (pradinis + baigiamasis)', 25, 'kg')), '1 maišas po 25 kg');
  assert.equal(packagingNote(row('Glaistas luboms', 26, 'kg')), '2 maišai po 25 kg');
  assert.equal(packagingNote(row('Glaistas', 275.1, 'kg')), '12 maišų po 25 kg');
  assert.equal(packagingNote(row('Glaistas', 500.1, 'kg')), '21 maišas po 25 kg');
});

test('paint and primer litres are buckets, rounded up to full containers (§1.10)', () => {
  assert.equal(packagingNote(row('Dažai sienoms (2 sluoksniai)', 64.89, 'l')), '7 kibirai po 10 l');
  assert.equal(packagingNote(row('Gruntas luboms', 20.47, 'l')), '3 kibirai po 10 l');
  assert.equal(packagingNote(row('Gruntas sienoms', 100, 'l')), '10 kibirų po 10 l');
  assert.equal(packagingNote(row('Dažai luboms', 9.5, 'L')), '1 kibiras po 10 l');
});

test('other rows, other units and empty quantities carry no note', () => {
  assert.equal(packagingNote(row('Rotband (~10 kg/m² esant 5mm storiui)', 973.3, 'kg')), null);
  assert.equal(packagingNote(row('Sienų glaistymas/dažymas', 324.45, 'm²')), null);
  assert.equal(packagingNote(row('Glaistas', null, 'kg')), null);
  assert.equal(packagingNote(row('Glaistas', 0, 'kg')), null);
  assert.equal(packagingNote(null), null);
});

test('his own container sizes from Nustatymai win; nonsense falls back to the defaults', () => {
  assert.deepEqual(packagingSizes(undefined), { bagKg: DEFAULT_BAG_KG, bucketL: DEFAULT_BUCKET_L });
  const mine = packagingSizes({ [BAG_KEY]: 20, [BUCKET_KEY]: '2,7' });
  assert.deepEqual(mine, { bagKg: 20, bucketL: 2.7 });
  assert.equal(packagingNote(row('Glaistas', 405.56, 'kg'), mine), '21 maišas po 20 kg');
  assert.equal(packagingNote(row('Dažai sienoms', 64.89, 'l'), mine), '25 kibirai po 2,7 l');
  assert.deepEqual(packagingSizes({ [BAG_KEY]: 0, [BUCKET_KEY]: -3 }), { bagKg: 25, bucketL: 10 });
  assert.deepEqual(packagingSizes({ [BAG_KEY]: 'x', [BUCKET_KEY]: 999 }), { bagKg: 25, bucketL: 10 });
});

test('the row itself is never changed', () => {
  const r = row('Glaistas sienoms', 405.56, 'kg');
  const before = JSON.stringify(r);
  packagingNote(r);
  assert.equal(JSON.stringify(r), before);
});
