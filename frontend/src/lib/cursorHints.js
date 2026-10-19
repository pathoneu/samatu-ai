// cursorHints — the one Lithuanian sentence beside the pointer (Pathon v3 click model, W1-B task B3;
// Kreo §3 „a cursor hint sentence sits to the right of the pointer in every mode", design §5 last column).
//
// The instruction lives HERE and nowhere else: the mode pill says which mode is on and holds its
// buttons, the status bar keeps the scale sentence; neither repeats what to click next. Each sentence
// says the next action for the mode's current state; a click that changed nothing can say why for a
// moment (flashCursorHint). Pure; CursorHint.jsx renders it.

import { legendCursorHint } from './legendReview.js';

/** Every mode that has a hint. Rest (no tool) has none: the drawing stays quiet. */
export const CURSOR_HINT_MODES = [
  'select', 'lasso', 'pan', 'distance', 'area', 'perimeter', 'count', 'calibrate', 'scalecheck',
  'room', 'findSimilar', 'legend', 'outlineEdit', 'split', 'merge', 'subtract', 'fill',
];

/** The window event a layer fires to say, for a moment, why its click did nothing. */
export const CURSOR_HINT_EVENT = 'samatu:cursor-hint';
export const CURSOR_HINT_FLASH_MS = 2600;

/**
 * state = {
 *   mode,                      // one of CURSOR_HINT_MODES, or null at rest
 *   points = 0,                // points of the measurement being drawn
 *   shift = false,             // Shift held (distance: the chain goes on)
 *   calibPoint = false,        // calibration / scale check: the first point is down
 *   countType = null,          // { label, n } — the count tool's active type
 *   symbolPhase = 'box',       // „Rasti panašius": box | searching | review
 *   fill = null,               // { nr, busy } — „Kontūras paspaudus"
 *   selectionCount = 0,        // marks selected with „Žymėti" / „Laso"
 *   outlineTool = null,        // useOutlineTool's state for split / merge / subtract
 *   roomPhase = null,          // the room tool R (W1-D): idle | reading | proposed | saving | picking
 *   legendPhase = null,        // „Pažymėti legendą" (W2-B): lib/legendReview LEGEND_PHASES
 * }
 * → the sentence, or null.
 */
export function cursorHintFor(state = {}) {
  const { mode = null, points = 0, shift = false, calibPoint = false, countType = null, symbolPhase = 'box',
    fill = null, selectionCount = 0, outlineTool = null, roomPhase = null, legendPhase = null } = state;
  switch (mode) {
    // with a selection the keys are in the pill and the actions in the bar above it — the hint says what a click does
    case 'select':
      return selectionCount ? 'Spustelėkite kitą matavimą arba tuščią vietą — atžymėti' : 'Spustelėkite matavimą ar žymę';
    case 'lasso':
      return selectionCount ? 'Apveskite kitus (su Shift — pridėti) · dešinysis klavišas — meniu' : 'Apveskite matavimus ir žymes (Shift — pridėti)';
    case 'pan':
      return 'Tempkite brėžinį';
    case 'distance':
      // the second plain click ends a distance; Shift + click keeps the chain going (v3 W1-B B5)
      if (points === 0) return 'Spustelėkite pradžią';
      if (shift) return 'Spustelėkite kitą tašką — atstumas tęsiamas';
      return 'Spustelėkite pabaigą — atstumas įsirašys · su Shift — tęsti';
    case 'area':
      if (points === 0) return 'Spustelėkite pirmą kampą';
      if (points < 3) return 'Spustelėkite kitą kampą';
      return 'Kitas kampas · dukart arba Enter — baigti';
    case 'perimeter':
      if (points === 0) return 'Spustelėkite pirmą tašką';
      if (points < 2) return 'Spustelėkite kitą tašką';
      return 'Kitas taškas · dukart arba Enter — baigti';
    case 'count':
      if (!countType) return 'Pirmiausia pasirinkite arba sukurkite tipą kairėje';
      return `${countType.label}: spustelėkite elementą (pažymėta ${countType.n}) · ant žymės — pašalinti`;
    case 'calibrate':
      return calibPoint ? 'Spustelėkite žinomo ilgio pabaigą' : 'Spustelėkite žinomo ilgio pradžią';
    case 'scalecheck':
      return calibPoint ? 'Spustelėkite atkarpos pabaigą' : 'Spustelėkite atkarpos, kurios ilgį žinote, pradžią';
    case 'room':
      if (roomPhase === 'reading') return 'Skaitomas kontūras pagal sienas…';
      if (roomPhase === 'saving') return 'Saugoma…';
      if (roomPhase === 'picking') return 'Kuri tai patalpa? Pasirinkite sąraše kairėje';
      if (roomPhase === 'proposed') return 'Spustelėkite — išsaugoti · kitoje patalpoje — išsaugoti ir siūlyti ją';
      return 'Spustelėkite patalpos viduje';
    case 'findSimilar':
      if (symbolPhase === 'searching') return 'Ieškoma panašių simbolių…';
      if (symbolPhase === 'review') return 'Spustelėkite neteisingą žymę — pašalinti · naujas rėmelis — nauja paieška';
      return 'Tempdami apveskite vieną simbolį kuo glaudžiau';
    case 'legend':
      return legendCursorHint(legendPhase) || 'Spustelėkite pasiūlytą legendą arba apveskite ją rėmeliu';
    case 'outlineEdit':
      return 'Tempkite kampą ar kraštinę · spustelėkite kampą — veiksmai · Enter — išsaugoti';
    case 'split':
      if (!outlineTool?.a) return 'Spustelėkite, kur prasideda skirianti linija';
      if (!outlineTool?.b) return 'Spustelėkite, kur linija baigiasi';
      if (outlineTool?.keep == null) return 'Spustelėkite dalį, kuri lieka patalpai';
      return 'Pasirinkite, kam priskirti kitą dalį, ir išsaugokite';
    case 'merge':
      return outlineTool?.targetNr ? 'Patikrinkite skaičius ir išsaugokite' : 'Spustelėkite gretimą patalpą';
    case 'subtract':
      return outlineTool?.shape === 'poly'
        ? 'Spustelėkite kampus patalpos viduje · dukart — baigti'
        : 'Tempkite stačiakampį patalpos viduje';
    case 'fill':
      if (fill?.busy) return `Ieškoma patalpos ${fill.nr} kontūro…`;
      return fill?.nr != null ? `Spustelėkite patalpos ${fill.nr} viduje` : 'Spustelėkite patalpos viduje';
    default:
      return null;
  }
}

/** Say, for a moment, why a click did nothing — beside the pointer, where the eye is. */
export function flashCursorHint(text, target = (typeof window !== 'undefined' ? window : null)) {
  if (!target || !text) return;
  target.dispatchEvent(new CustomEvent(CURSOR_HINT_EVENT, { detail: { text: String(text) } }));
}
