import test from 'node:test';
import assert from 'node:assert/strict';
import { HELP_SECTIONS, WHATS_NEW } from './helpContent.js';
import { isBannedText } from './userText.js';

const allText = () => [
  ...HELP_SECTIONS.flatMap((s) => [s.title, ...s.steps]),
  ...WHATS_NEW.flatMap((r) => r.items),
];

test('the help page answers the three questions the brief names', () => {
  const titles = HELP_SECTIONS.map((s) => s.title);
  assert.ok(titles.includes('Kaip patikrinti skaičių'));
  assert.ok(titles.includes('Kaip pataisyti patalpos kontūrą'));
  assert.ok(titles.includes('Ką reiškia linijos brėžinyje'));
  const lines = HELP_SECTIONS.find((s) => s.id === 'linijos').steps.join(' ');
  assert.match(lines, /Ištisinė/);
  assert.match(lines, /Brūkšninė/);
  assert.match(lines, /Raudona — tik klaida/);
});

test('help text carries no pipeline words and names the current buttons', () => {
  for (const t of allText()) {
    assert.equal(isBannedText(t), false, t);
    assert.ok(!/„Prielaid/.test(t), `the panel is „Nustatymai" now: ${t}`);
    assert.ok(!/Redaguoti kontūr/.test(t), t);
  }
});

test('„Kas naujo" is newest first with ISO dates', () => {
  const dates = WHATS_NEW.map((r) => r.date);
  assert.deepEqual([...dates].sort().reverse(), dates);
  for (const d of dates) assert.match(d, /^\d{4}-\d{2}-\d{2}$/);
});
