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
  // the Notice draws meta as a full-width 12 px line, not as a title attribute
  assert.match(notice, /\{meta && <span className="basis-full text-meta text-muted-foreground" data-notice-meta>\{meta\}<\/span>\}/);
});
