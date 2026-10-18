import test from 'node:test';
import assert from 'node:assert/strict';
import {
  VIEWS, PANEL_TABS, PANEL_LIMITS, MIN_SPLIT_CANVAS,
  panelForView, canvasModeForView, selectTab, tabForView,
  viewFromLocation, locationForView, patikraSubview,
  clampPanelWidth, readPanelWidth, writePanelWidth, panelWidthFor, revealTarget,
} from './workspaceViews.js';

const memoryStorage = (init = {}) => {
  const m = new Map(Object.entries(init));
  return { getItem: (k) => (m.has(k) ? m.get(k) : null), setItem: (k, v) => m.set(k, String(v)), map: m };
};

test('four views, in the order of the step rail', () => {
  assert.deepEqual(VIEWS, ['brezinys', 'patikra', 'samata', 'siusti']);
});

test('each view opens its own panel; Siųsti has none', () => {
  assert.equal(panelForView('brezinys'), 'patalpos');
  assert.equal(panelForView('patikra'), 'patikra');
  assert.equal(panelForView('samata'), 'samata');
  assert.equal(panelForView('siusti'), null);
  assert.equal(panelForView('nope'), null);
});

test('the panel tabs are the five the design names, Lithuanian labels', () => {
  assert.deepEqual(PANEL_TABS.map((t) => t.id), ['patalpos', 'kiekiai', 'patikra', 'samata', 'pokalbis']);
  assert.deepEqual(PANEL_TABS.map((t) => t.label), ['Patalpos ir eilutės', 'Kiekiai', 'Patikra', 'Sąmata', 'Pokalbis']);
});

test('the drawing gets the width on Brėžinys, half on Patikra and Sąmata, a strip on Siųsti', () => {
  assert.equal(canvasModeForView('brezinys'), 'full');
  assert.equal(canvasModeForView('patikra'), 'split');
  assert.equal(canvasModeForView('samata'), 'split');
  assert.equal(canvasModeForView('siusti'), 'strip');
});

test('„Išskleisti" on Sąmata collapses the drawing to a strip, and only there', () => {
  assert.equal(canvasModeForView('samata', { expanded: true }), 'strip');
  assert.equal(canvasModeForView('brezinys', { expanded: true }), 'full');
  assert.equal(canvasModeForView('patikra', { expanded: true }), 'split');
});

test('a project without a drawing gives Sąmata the whole width', () => {
  assert.equal(canvasModeForView('samata', { noDrawing: true }), 'strip');
  assert.equal(canvasModeForView('brezinys', { noDrawing: true }), 'full', 'Brėžinys keeps its place: it offers the upload');
});

test('a view tab switches the step; a drawing tab opens on the drawing view', () => {
  assert.deepEqual(selectTab('brezinys', 'samata'), { view: 'samata', tab: 'samata' });
  assert.deepEqual(selectTab('brezinys', 'patikra'), { view: 'patikra', tab: 'patikra' });
  assert.deepEqual(selectTab('brezinys', 'kiekiai'), { view: 'brezinys', tab: 'kiekiai' });
  assert.deepEqual(selectTab('samata', 'pokalbis'), { view: 'brezinys', tab: 'pokalbis' });
  assert.deepEqual(selectTab('patikra', 'patalpos'), { view: 'brezinys', tab: 'patalpos' });
  assert.deepEqual(selectTab('samata', 'nothing'), { view: 'samata', tab: 'samata' });
});

test('the drawing view remembers its tab; the others show their own panel', () => {
  assert.equal(tabForView('brezinys', 'kiekiai'), 'kiekiai');
  assert.equal(tabForView('brezinys', 'samata'), 'patalpos');
  assert.equal(tabForView('brezinys'), 'patalpos');
  assert.equal(tabForView('patikra', 'kiekiai'), 'patikra');
  assert.equal(tabForView('samata', 'pokalbis'), 'samata');
  assert.equal(tabForView('siusti', 'kiekiai'), null);
});

test("today's URLs keep landing where they did", () => {
  assert.deepEqual(viewFromLocation('/project/demo-objektas_h', ''), { view: 'brezinys', kambarys: null, etapas: null });
  assert.deepEqual(viewFromLocation('/project/abc', '?step=samata'), { view: 'samata', kambarys: null, etapas: null });
  assert.deepEqual(viewFromLocation('/project/abc', '?step=siusti'), { view: 'siusti', kambarys: null, etapas: null });
  assert.equal(viewFromLocation('/project/abc', '?step=brezinys').view, 'brezinys');
  assert.equal(viewFromLocation('/project/abc', '?step=patikra').view, 'patikra', 'the legacy spelling still opens Patikra');
  assert.equal(viewFromLocation('/project/abc', '?step=bogus').view, 'brezinys');
  assert.deepEqual(viewFromLocation('/project/abc/patikra', ''), { view: 'patikra', kambarys: null, etapas: null });
  assert.equal(viewFromLocation('/project/abc/patikra/', '').view, 'patikra');
});

test('the kambarys and etapas queries ride along with Patikra', () => {
  assert.deepEqual(viewFromLocation('/project/abc/patikra', '?kambarys=04'), { view: 'patikra', kambarys: '04', etapas: null });
  assert.deepEqual(viewFromLocation('/project/abc/patikra', '?etapas=bendri'), { view: 'patikra', kambarys: null, etapas: 'bendri' });
  assert.equal(viewFromLocation('/project/abc', '?kambarys=04').kambarys, null, 'only Patikra reads a room from the URL');
  assert.equal(viewFromLocation('/project/abc/patikra', new URLSearchParams('kambarys=110')).kambarys, '110');
});

test('which part of Patikra the panel shows', () => {
  assert.equal(patikraSubview({}), 'questions');
  assert.equal(patikraSubview({ kambarys: '04' }), 'room');
  assert.equal(patikraSubview({ etapas: 'bendri' }), 'general');
  assert.equal(patikraSubview({ kambarys: '04', etapas: 'bendri' }), 'general', 'PatikraEntry rule: the stage wins');
});

test('a view → its URL, round trip', () => {
  assert.equal(locationForView('demo-objektas_h', 'brezinys'), '/project/demo-objektas_h');
  assert.equal(locationForView('p1', 'samata'), '/project/p1?step=samata');
  assert.equal(locationForView('p1', 'siusti'), '/project/p1?step=siusti');
  assert.equal(locationForView('p1', 'patikra'), '/project/p1/patikra');
  assert.equal(locationForView('p1', 'patikra', { kambarys: '04' }), '/project/p1/patikra?kambarys=04');
  assert.equal(locationForView('p1', 'patikra', { etapas: 'bendri' }), '/project/p1/patikra?etapas=bendri');
  for (const view of VIEWS) {
    const url = new URL(`http://x${locationForView('p1', view)}`);
    assert.equal(viewFromLocation(url.pathname, url.search).view, view, view);
  }
});

test("a step change keeps parameters that are not the frame's own, and drops the old step", () => {
  assert.equal(locationForView('p1', 'samata', { keep: '?viewer=legacy' }), '/project/p1?viewer=legacy&step=samata');
  assert.equal(locationForView('p1', 'brezinys', { keep: '?step=samata&viewer=legacy' }), '/project/p1?viewer=legacy');
  assert.equal(locationForView('p1', 'samata', { keep: '?kambarys=04' }), '/project/p1?step=samata');
  assert.equal(locationForView('p1', 'patikra', { keep: '?step=samata' }), '/project/p1/patikra');
});

test('project ids are encoded into the path', () => {
  assert.equal(locationForView('a b/c', 'brezinys'), '/project/a%20b%2Fc');
});

test('„show me this place" becomes the viewer focus: page, rect, a fresh nonce', () => {
  assert.deepEqual(revealTarget({ page: 3, rect_pct: [0.1, 0.2, 0.4, 0.5] }, 7), { page: 3, rect: [0.1, 0.2, 0.4, 0.5], nonce: 7 });
  assert.deepEqual(revealTarget({ page: '2' }, 1), { page: 2, rect: [0, 0, 1, 1], nonce: 1 }, 'no rect → the whole sheet');
  assert.deepEqual(revealTarget({ page: 2, rect_pct: [0, 0, 1] }, 2).rect, [0, 0, 1, 1], 'a malformed rect → the whole sheet');
  assert.deepEqual(revealTarget({ page: 2, rect_pct: [0, 'x', 1, 1] }, 2).rect, [0, 0, 1, 1]);
  assert.deepEqual(revealTarget({ page: 2, rect_pct: ['0.5', 0, 1, 1] }, 2).rect, [0.5, 0, 1, 1], 'numbers as strings are numbers');
  assert.equal(revealTarget({ page: 0 }), null);
  assert.equal(revealTarget({ page: null }), null);
  assert.equal(revealTarget({ page: 1.5 }), null);
  assert.equal(revealTarget(), null);
});

test('panel width is clamped to its mode, the full panel starts at 340 px', () => {
  assert.equal(PANEL_LIMITS.full.initial, 340);
  assert.equal(PANEL_LIMITS.full.key, 'samatu_panel_width');
  assert.equal(clampPanelWidth(200), 300);
  assert.equal(clampPanelWidth(900), 480);
  assert.equal(clampPanelWidth(377.4), 377);
  assert.equal(clampPanelWidth('x'), 340);
  assert.equal(clampPanelWidth(100, 'split'), 480);
  assert.equal(clampPanelWidth(2000, 'split'), 960);
  assert.equal(clampPanelWidth(NaN, 'split'), null);
});

test('the dragged width is kept in localStorage under samatu_panel_width', () => {
  const s = memoryStorage();
  assert.equal(readPanelWidth(s), null);
  assert.equal(writePanelWidth(s, 'full', 412), 412);
  assert.equal(s.map.get('samatu_panel_width'), '412');
  assert.equal(readPanelWidth(s), 412);
  writePanelWidth(s, 'full', 999);
  assert.equal(readPanelWidth(s), 480, 'clamped on the way in');
  assert.equal(readPanelWidth(memoryStorage({ samatu_panel_width: 'garbage' })), null);
  assert.equal(readPanelWidth(memoryStorage({ samatu_panel_width: '250' })), 300, 'clamped on the way out');
  writePanelWidth(s, 'split', 700);
  assert.equal(readPanelWidth(s, 'split'), 700);
  assert.equal(s.map.get('samatu_panel_split_width'), '700');
});

test('a storage that throws (private mode) never breaks the frame', () => {
  const broken = { getItem: () => { throw new Error('denied'); }, setItem: () => { throw new Error('denied'); } };
  assert.equal(readPanelWidth(broken), null);
  assert.equal(writePanelWidth(broken, 'full', 400), 400);
  assert.equal(readPanelWidth(null), null);
});

test('panel width per canvas mode', () => {
  assert.equal(panelWidthFor('full', { workspaceWidth: 1384 }), 340);
  assert.equal(panelWidthFor('full', { workspaceWidth: 1384, stored: 420 }), 420);
  assert.equal(panelWidthFor('strip', { workspaceWidth: 1384 }), null, 'the content takes what is left');
  assert.equal(panelWidthFor('split', { workspaceWidth: 1384 }), 803, '58 % of the workspace');
  assert.equal(panelWidthFor('split', { workspaceWidth: 1384, stored: 600 }), 600);
});

test('a split panel always leaves the drawing readable', () => {
  for (const ws of [800, 1024, 1224, 1384, 1864]) {
    const w = panelWidthFor('split', { workspaceWidth: ws, stored: 960 });
    assert.ok(ws - w >= MIN_SPLIT_CANVAS, `${ws}: panel ${w}`);
  }
  assert.equal(panelWidthFor('split', { workspaceWidth: 0 }), 480, 'before the first measurement: the minimum');
});
