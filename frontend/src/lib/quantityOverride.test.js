import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  acceptPositionQuantity,
  adjustPositionQuantity,
  updatePositionQuantity,
} from './quantityOverride.js';

test('updatePositionQuantity: updates quantity, sum, and manual override metadata', () => {
  const rows = [
    { _id: 'a', aprasymas: 'Dažymas', kiekis: 10, kaina: 4, suma: 40, confidence: 'low' },
    { _id: 'b', aprasymas: 'GKP', kiekis: 5, kaina: 8, suma: 40 },
  ];

  const updated = updatePositionQuantity(rows, 'a', 12.5);

  assert.equal(updated[0].kiekis, 12.5);
  assert.equal(updated[0].suma, 50);
  assert.equal(updated[0].confidence, 'high');
  assert.equal(updated[0].quantity_source, 'manual_override');
  assert.equal(updated[0].manual_override, true);
  assert.equal(updated[0].ai_kiekis_original, 10);
  assert.equal(updated[1], rows[1]);
});

test('updatePositionQuantity: keeps first AI quantity when edited repeatedly', () => {
  const rows = [
    {
      _id: 'a',
      aprasymas: 'Dažymas',
      kiekis: 12.5,
      kaina: 4,
      suma: 50,
      ai_kiekis_original: 10,
      manual_override: true,
    },
  ];

  const updated = updatePositionQuantity(rows, 'a', 14);

  assert.equal(updated[0].kiekis, 14);
  assert.equal(updated[0].suma, 56);
  assert.equal(updated[0].ai_kiekis_original, 10);
});

test('updatePositionQuantity: rejects invalid quantities', () => {
  const rows = [{ _id: 'a', aprasymas: 'Dažymas', kiekis: 10, kaina: 4 }];
  assert.throws(() => updatePositionQuantity(rows, 'a', -1), /Invalid quantity/);
  assert.throws(() => updatePositionQuantity(rows, 'a', Number.NaN), /Invalid quantity/);
});

test('adjustPositionQuantity: increments count rows without going below zero', () => {
  const rows = [{ _id: 'a', aprasymas: 'Rozetės', kiekis: 2, kaina: 5, suma: 10 }];

  assert.equal(adjustPositionQuantity(rows, 'a', 1)[0].kiekis, 3);
  assert.equal(adjustPositionQuantity(rows, 'a', -5)[0].kiekis, 0);
});

test('acceptPositionQuantity: marks AI quantity as user verified without changing amount', () => {
  const rows = [{ _id: 'a', aprasymas: 'Rozetės', kiekis: 2, kaina: 5, confidence: 'low' }];

  const updated = acceptPositionQuantity(rows, 'a');

  assert.equal(updated[0].kiekis, 2);
  assert.equal(updated[0].confidence, 'high');
  assert.equal(updated[0].quantity_source, 'user_verified_ai');
  assert.equal(typeof updated[0].user_verified_at, 'string');
});
