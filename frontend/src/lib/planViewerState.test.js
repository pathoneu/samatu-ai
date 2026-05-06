import test from 'node:test';
import assert from 'node:assert/strict';
import {
  clampPlanScale,
  getDefaultPlanPage,
  getNextPlanPage,
  getPlanFitScale,
  getVisiblePlanPages,
} from './planViewerState.js';

test('clampPlanScale: keeps plan zoom inside practical drawing bounds', () => {
  assert.equal(clampPlanScale(0.1), 0.35);
  assert.equal(clampPlanScale(1.234), 1.23);
  assert.equal(clampPlanScale(5), 2.5);
});

test('getNextPlanPage: keeps page navigation in document bounds', () => {
  assert.equal(getNextPlanPage(1, -1, 30), 1);
  assert.equal(getNextPlanPage(5, 1, 30), 6);
  assert.equal(getNextPlanPage(30, 1, 30), 30);
});

test('getPlanFitScale: calculates width and page fit from viewport and page dimensions', () => {
  const page = { width: 1000, height: 1400 };
  assert.equal(getPlanFitScale({ mode: 'width', viewportWidth: 900, viewportHeight: 700, page }), 0.82);
  assert.equal(getPlanFitScale({ mode: 'page', viewportWidth: 900, viewportHeight: 700, page }), 0.45);
});

test('getVisiblePlanPages: filters pages by label, number and type', () => {
  const pageMeta = {
    1: { label: 'Titulinis', type: 'title_page' },
    5: { label: 'Auksto planas', type: 'floor_plan' },
    8: { label: 'Elektros planas', type: 'electrical' },
  };
  assert.deepEqual(getVisiblePlanPages({ totalPages: 8, pageMeta, query: 'planas' }).map(p => p.nr), [5, 8]);
  assert.deepEqual(getVisiblePlanPages({ totalPages: 8, pageMeta, query: '8' }).map(p => p.nr), [8]);
  assert.equal(getVisiblePlanPages({ totalPages: 2, pageMeta: {}, query: '' }).length, 2);
});

test('getDefaultPlanPage: opens the first floor plan when metadata is available', () => {
  const pageMeta = {
    1: { label: 'Titulinis', type: 'title_page' },
    3: { label: 'Specifikacija', type: 'specification' },
    5: { label: 'Auksto planas', type: 'floor_plan' },
  };
  assert.equal(getDefaultPlanPage({ totalPages: 8, pageMeta }), 5);
  assert.equal(getDefaultPlanPage({ totalPages: 8, pageMeta: {} }), 1);
});
