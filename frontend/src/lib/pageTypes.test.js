import test from 'node:test';
import assert from 'node:assert/strict';
import { firstPlanPage, missingInteriorTypes } from './pageTypes.js';

test('firstPlanPage: skips the cover and opens on the first floor plan', () => {
  // The shape the dev project actually stores: page 1 is a marketing render.
  const project = {
    puslapiai: [
      { nr: 1, tipas: 'title_page' },
      { nr: 2, tipas: 'floor_plan' },
      { nr: 3, tipas: 'floor_plan' },
      { nr: 6, tipas: 'ceiling_plan' },
    ],
  };
  assert.equal(firstPlanPage(project), 2);
});

test('firstPlanPage: a project with no floor plan falls back through the plan types', () => {
  assert.equal(firstPlanPage({ puslapiai: [
    { nr: 1, tipas: 'title_page' }, { nr: 4, tipas: 'ceiling_plan' },
  ] }), 4);
  assert.equal(firstPlanPage({ puslapiai: [
    { nr: 1, tipas: 'specification' }, { nr: 5, tipas: 'wall_elevation' },
  ] }), 5);
  assert.equal(firstPlanPage({ puslapiai: [
    { nr: 2, tipas: 'facade' }, { nr: 7, tipas: 'section' },
  ] }), 7);
});

test('firstPlanPage: no classified plan → the eksplikacija page the rooms came from', () => {
  assert.equal(firstPlanPage({
    puslapiai: [{ nr: 1, tipas: 'title_page' }],
    _eksplikacija: { eksplikacija_source_page: 3 },
  }), 3);
});

test('firstPlanPage: no classification at all → the first page a room lives on', () => {
  assert.equal(firstPlanPage({ patalpos: [
    { nr: '103', puslapio_nr: 5 }, { nr: '101', puslapio_nr: 2 },
  ] }), 2);
});

test('firstPlanPage: an empty or junk project opens page 1, never 0 or NaN', () => {
  for (const p of [{}, null, undefined, { puslapiai: [] }, { puslapiai: [{ tipas: 'floor_plan' }] }]) {
    assert.equal(firstPlanPage(p), 1);
  }
});

test('firstPlanPage: reads the v8_pages shape too (page/type keys)', () => {
  assert.equal(firstPlanPage({ v8_pages: [
    { page: 1, type: 'title_page' }, { page: 4, type: 'floor_plan' },
  ] }), 4);
});

test('missingInteriorTypes: unchanged behaviour (regression guard for the new export)', () => {
  assert.deepEqual(missingInteriorTypes([]), []);
  assert.deepEqual(missingInteriorTypes([{ tipas: 'floor_plan' }]),
    ['wall_elevation', 'ceiling_plan']);
});
