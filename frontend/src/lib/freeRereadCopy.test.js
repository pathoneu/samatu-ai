/**
 * The free re-read offer's promise is on screen, never only in a tooltip (B2-B follow-up, manager: nothing
 * hover-only): FreeRereadBanner passes it to the Notice as its visible meta line.
 */
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';

const lt = JSON.parse(readFileSync(new URL('../i18n/lt.json', import.meta.url), 'utf8'));
const banner = readFileSync(new URL('../components/project/FreeRereadBanner.jsx', import.meta.url), 'utf8');
const notice = readFileSync(new URL('../components/ui/Notice.jsx', import.meta.url), 'utf8');

test('the offer says what stays as a visible second line', () => {
  assert.equal(lt.project.freeReread.keeps, 'Pataisymai, kainos ir patikrintos patalpos lieka.');
  assert.equal(lt.project.freeReread.titleLine, 'Tiksliau, nemokamai');
  assert.equal(lt.project.freeReread.ctaShort, 'Perskaityti');
  assert.match(banner, /meta=\{t\('project\.freeReread\.keeps'\)\}/);
  // the Notice draws meta as a full-width 12 px line, not as a title attribute (with a fold's control beside it
  // when the offer leads a NoticeFold — still visible text in a span, never a tooltip)
  assert.match(notice, /\{meta && !metaAction && <span className="basis-full text-meta text-muted-foreground" data-notice-meta>\{meta\}<\/span>\}/);
  assert.match(notice, /<span className="text-meta text-muted-foreground" data-notice-meta>\{meta\}<\/span>/);
  assert.match(banner, /metaAction=\{<NoticeFoldMore notice="free-reread-banner" \/>\}/);
});

test('the done line says how many rooms took the drawing numbers', async () => {
  const { freeRereadDoneText } = await import('./freeReread.js');
  const t = (k, o = {}) => {
    const path = k.split('.');
    let node = lt;
    for (const p of path) node = node?.[p];
    if (node == null) {
      const base = path.reduce((n, p, i) => (i === path.length - 1 ? n : n?.[p]), lt);
      const leaf = path[path.length - 1];
      const form = o.count === 1 ? 'one' : (o.count % 10 >= 2 && o.count % 10 <= 9 && !(o.count % 100 >= 11 && o.count % 100 <= 19) ? 'few' : 'other');
      node = base?.[`${leaf}_${form}`];
    }
    return String(node).replace(/\{\{(\w+)\}\}/g, (_, v) => String(o[v]));
  };
  const text = freeRereadDoneText({ count: 17, konturai: 17, perimetrai: 0, jusu: 0, dangos: 0, numeriai: 17 }, t);
  assert.match(text, /^Brėžinys perskaitytas\. Iš 17 patalpų: tikslus kontūras — 17\./);
  assert.match(text, / 17 patalpų gavo brėžinio numerius — buvę numeriai parodyti prie jų, kol jas patikrinsite\.$/);
  assert.doesNotMatch(freeRereadDoneText({ count: 2, konturai: 2 }, t), /numer/);
});
