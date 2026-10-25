import test from 'node:test';
import assert from 'node:assert/strict';
import { foldLabel, shouldFold } from './noticeFold.js';

test('two or more notices fold; one or none does not', () => {
  assert.equal(shouldFold(0), false);
  assert.equal(shouldFold(1), false);
  assert.equal(shouldFold(2), true);
  assert.equal(shouldFold(3), true);
});

test('the fold line counts every notice and names the ones it knows', () => {
  assert.deepEqual(foldLabel(['free-reread-banner', 'read-rating', 'reminders-patikra']), {
    title: 'Pranešimai (3)',
    names: 'nemokamas perskaitymas · skaitymo įvertinimas · priminimai',
  });
  assert.deepEqual(foldLabel(['read-rating', 'something-else']), { title: 'Pranešimai (2)', names: 'skaitymo įvertinimas' });
});

test('the workspace notices above the panel have names too', () => {
  assert.deepEqual(foldLabel(['server-refresh-notice', 'free-reread-banner', 'reread-diff-banner']), {
    title: 'Pranešimai (3)',
    names: 'atnaujinta iš serverio · nemokamas perskaitymas · kas pasikeitė',
  });
});

test('the free re-read offer leads the fold; the line counts only what it hides', async () => {
  const { leadNotice } = await import('./noticeFold.js');
  const ids = ['server-refresh-notice', 'free-reread-banner', 'reread-diff-banner'];
  assert.equal(leadNotice(ids), 'free-reread-banner');
  assert.deepEqual(foldLabel(ids, 'free-reread-banner'), { title: 'Dar pranešimai (2)', names: 'atnaujinta iš serverio · kas pasikeitė' });
  // after the read its done line takes the same place
  assert.equal(leadNotice(['read-rating', 'free-reread-done']), 'free-reread-done');
  assert.equal(leadNotice(['read-rating', 'reminders-patikra']), null);
  assert.equal(leadNotice([]), null);
});

test('the re-read change notice opens the fold when it arrives, not when the page loads with it', async () => {
  const { opensOnArrival } = await import('./noticeFold.js');
  assert.equal(opensOnArrival(null, ['free-reread-banner', 'reread-diff-banner']), false, 'first look');
  assert.equal(opensOnArrival(['free-reread-banner'], ['free-reread-banner', 'reread-diff-banner']), true);
  assert.equal(opensOnArrival(['reread-diff-banner'], ['reread-diff-banner', 'free-reread-banner']), false);
  assert.equal(opensOnArrival(['read-rating'], ['read-rating', 'free-reread-done']), false);
  // the same notice with a later re-read's stamp opens it again; the same stamp does not
  assert.equal(opensOnArrival(['reread-diff-banner@t1'], ['reread-diff-banner@t2']), true);
  assert.equal(opensOnArrival(['reread-diff-banner@t1'], ['reread-diff-banner@t1']), false);
});
