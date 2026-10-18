import test from 'node:test';
import assert from 'node:assert/strict';
import { ESC_STEPS, escStep, openLayerInDocument, OPEN_LAYER_SELECTOR } from './escOrder.js';

// Press Esc until nothing is left, applying each step the way TakeoffViewer does.
function pressUntilRest(start) {
  const s = { ...start };
  const steps = [];
  for (let i = 0; i < 20; i += 1) {
    const step = escStep(s);
    if (!step) break;
    steps.push(step);
    if (step === 'popover') s.popoverOpen = false;
    else if (step === 'draftPoint') s.draftPoints -= 1;
    else if (step === 'calibPoint') s.calibPoint = false;
    else if (step === 'outlineEdit') s.outlineEdit = false;
    else if (step === 'outlineToolStep') s.outlineToolSteps -= 1;
    else if (step === 'outlineTool') s.outlineTool = false;
    else if (step === 'symbolSearch') s.symbolSearch = false;
    else if (step === 'fill') s.fillArmed = false;
    else if (step === 'measureSelection') s.measureSelection = 0;
    else if (step === 'tool') s.tool = null;
    else if (step === 'panel') s.panelOpen = false;
    else if (step === 'room') s.roomSelected = false;
  }
  return steps;
}

test('nothing to step back from at rest', () => {
  assert.equal(escStep({}), null);
  assert.equal(escStep({ tool: null, draftPoints: 0 }), null);
});

test('a 3-point draft: Esc removes one point at a time, then leaves the tool — the room stays until last', () => {
  const steps = pressUntilRest({ tool: 'area', draftPoints: 3, roomSelected: true });
  assert.deepEqual(steps, ['draftPoint', 'draftPoint', 'draftPoint', 'tool', 'room']);
});

test('tool → panel → selection: an open Masteliai is closed before the room is dropped', () => {
  assert.deepEqual(pressUntilRest({ tool: 'distance', panelOpen: true, roomSelected: true }), ['tool', 'panel', 'room']);
  assert.equal(escStep({ panelOpen: true, roomSelected: true }), 'panel');
});

test('a menu or dialog on top takes the first Esc alone', () => {
  assert.equal(escStep({ popoverOpen: true, draftPoints: 2, tool: 'area', roomSelected: true }), 'popover');
});

test('calibration never leaves mid-pick: the first point goes first, then the tool', () => {
  assert.deepEqual(pressUntilRest({ tool: 'calibrate', calibPoint: true }), ['calibPoint', 'tool']);
});

test('outline tools step back through their clicks before they close; an edit is left unsaved', () => {
  assert.deepEqual(pressUntilRest({ outlineTool: true, outlineToolSteps: 2, roomSelected: true }), ['outlineToolStep', 'outlineToolStep', 'outlineTool', 'room']);
  assert.deepEqual(pressUntilRest({ outlineEdit: true, roomSelected: true }), ['outlineEdit', 'room']);
});

test('selected marks clear before the select tool itself is left', () => {
  assert.deepEqual(pressUntilRest({ tool: 'lasso', measureSelection: 5 }), ['measureSelection', 'tool']);
});

test('find similar and the armed fill close before anything under them', () => {
  assert.deepEqual(pressUntilRest({ symbolSearch: true, panelOpen: true }), ['symbolSearch', 'panel']);
  assert.deepEqual(pressUntilRest({ fillArmed: true, roomSelected: true }), ['fill', 'room']);
});

test('the step list is unique and ends with the room', () => {
  const ids = ESC_STEPS.map((s) => s.id);
  assert.equal(new Set(ids).size, ids.length);
  assert.equal(ids[ids.length - 1], 'room');
  assert.equal(ids[0], 'popover');
});

test('an open menu or dialog is found in the document', () => {
  const doc = (found) => ({ querySelector: (sel) => (sel === OPEN_LAYER_SELECTOR && found ? {} : null) });
  assert.equal(openLayerInDocument(doc(true)), true);
  assert.equal(openLayerInDocument(doc(false)), false);
  assert.equal(openLayerInDocument(null), false);
});
