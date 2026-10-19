// modePill — what the bottom pill on the drawing shows for the active mode (Pathon v3 click model,
// W1-B task B2; design 2026-10-18 §5–§6, Togal §3 „contextual bottom pill: only the active mode's
// options").
//
// One place per mode: the mode's name, what it holds right now (a count type and its tally, the points
// of a calibration), the keys that act on it, and the buttons that finish or leave it — always visible,
// never hover-only. Nothing for another mode is shown, and nothing at rest. Pure: ModePill.jsx renders
// it, TakeoffViewer maps the action ids to its handlers.

import { hintText } from './viewerShortcuts.js';
import { railTool } from './toolRail.js';
import { legendPill } from './legendReview.js';

const DRAFT_TOOLS = new Set(['distance', 'area', 'perimeter']);

const nameOf = (tool) => railTool(tool)?.name || null;

/**
 * state = {
 *   tool,                 // the armed mode (measureTool) or null
 *   draftPoints = 0, finishable = false,   // the measurement being drawn
 *   calibPoint = false,   // calibration / scale check: the first point is down
 *   outlineEdit = null,   // { nr, canUndo, invalid, saving }
 *   fill = null,          // { nr, busy } — „Kontūras paspaudus" armed for a room
 *   symbolActive = false, // „Rasti panašius" session open
 *   selectionCount = 0,   // measurements selected with „Žymėti" / „Laso"
 *   countType = null,     // { label, n } — the count tool's active type
 *   roomPhase = null,     // the room tool R (W1-D useRoomTool): idle | reading | proposed | saving | picking
 *   legend = null,        // „Pažymėti legendą" (W2-B): { phase, proposals, toCreate, notice } while its session is open
 *   mac,
 * }
 * → null | { id, name, detail, keys, actions: [{ id, label, primary?, disabled?, title? }] }
 */
export function modePillFor(state = {}) {
  const { tool = null, draftPoints = 0, finishable = false, calibPoint = false, outlineEdit = null, fill = null,
    symbolActive = false, selectionCount = 0, countType = null, roomPhase = null, legend = null, mac = false } = state;
  const exit = { id: 'toolExit', label: 'Išeiti', title: 'Išeiti iš įrankio (Esc)' };

  if (outlineEdit) {
    return {
      id: 'outlineEdit',
      name: outlineEdit.name || `Kontūras · patalpa ${outlineEdit.nr}`,
      detail: outlineEdit.invalid ? 'Kontūras kertasi pats su savimi — pataisykite viršūnes' : null,
      keys: hintText(['outlineUndo', 'outlineSave', 'outlineCancel'], { mac }),
      actions: [
        { id: 'outlineUndo', label: 'Atgal', disabled: !outlineEdit.canUndo, title: 'Atšaukti paskutinį viršūnės pakeitimą (Z)' },
        {
          id: 'outlineSave',
          label: outlineEdit.saving ? 'Saugoma…' : (outlineEdit.saveLabel || 'Išsaugoti kontūrą'),
          primary: true,
          disabled: !!(outlineEdit.saving || outlineEdit.invalid),
          title: outlineEdit.invalid
            ? 'Kontūras kertasi pats su savimi — pataisykite viršūnes, tada išsaugokite'
            : 'Išsaugoti pakeistą kontūrą (Enter) — jo sienos ir angos bus perskaitytos iš naujo, kiekiai perskaičiuoti',
        },
        { id: 'outlineCancel', label: 'Atšaukti', title: 'Atšaukti kontūro redagavimą (Esc) — niekas neišsaugoma' },
      ],
    };
  }
  if (fill) {
    return {
      id: 'fill',
      name: `Kontūras paspaudus · patalpa ${fill.nr}`,
      detail: fill.busy ? 'Ieškoma kontūro…' : null,
      keys: 'Esc — atšaukti',
      actions: [{ id: 'fillCancel', label: 'Atšaukti', title: 'Atšaukti (Esc) — niekas nepakeičiama' }],
    };
  }
  if (legend?.phase) return legendPill(legend);
  if (symbolActive) {
    return {
      id: 'findSimilar',
      name: nameOf('findSimilar'),
      detail: null,
      keys: 'Esc — baigti',
      actions: [{ id: 'symbolClose', label: 'Baigti', title: 'Baigti paiešką — nepridėti rasti simboliai išmetami (Esc)' }],
    };
  }
  if (!tool) return null;

  if (DRAFT_TOOLS.has(tool)) {
    const drawing = draftPoints > 0;
    return {
      id: tool,
      name: nameOf(tool),
      detail: null,
      keys: drawing
        ? hintText(['draftFinish', 'draftStepBack'], { mac })
        : (tool === 'distance' ? 'Antras spustelėjimas įrašo · Shift — tęsti, tik tiesiai arba 45°' : 'Shift — tik tiesiai arba 45°'),
      actions: drawing
        ? [
            {
              id: 'draftFinish',
              label: 'Baigti',
              primary: true,
              disabled: !finishable,
              title: finishable
                ? 'Užbaigti matavimą ir įrašyti rezultatą (Enter arba dukart spustelėkite)'
                : 'Pažymėkite dar bent vieną tašką, tada galėsite baigti',
            },
            { id: 'draftCancel', label: 'Atšaukti', title: 'Atsisakyti šio matavimo — nubrėžti taškai bus ištrinti' },
          ]
        : [exit],
    };
  }
  if (tool === 'count') {
    return {
      id: 'count',
      name: nameOf('count'),
      detail: countType ? `${countType.label}: ${countType.n} vnt.` : 'Pirmiausia pasirinkite arba sukurkite tipą',
      keys: null,
      actions: [exit],
    };
  }
  if (tool === 'calibrate' || tool === 'scalecheck') {
    return {
      id: tool,
      name: tool === 'calibrate' ? nameOf('calibrate') : 'Mastelio patikra',
      detail: calibPoint ? '1 taškas iš 2' : null,
      keys: null,
      actions: calibPoint
        ? [{ id: 'calibCancel', label: 'Atšaukti tašką', title: 'Pašalinti pirmą tašką ir pradėti iš naujo' }, exit]
        : [exit],
    };
  }
  if (tool === 'select' || tool === 'lasso') {
    return {
      id: tool,
      name: nameOf(tool),
      detail: selectionCount ? `Pažymėta: ${selectionCount}` : null,
      keys: selectionCount ? hintText(['deleteSelected'], { mac }) : null,
      actions: selectionCount ? [{ id: 'deselect', label: 'Atžymėti' }, exit] : [exit],
    };
  }
  if (tool === 'room') {
    // review before it exists (W1-D): the outline is proposed on the drawing; saving and dropping it are here too
    const proposed = roomPhase === 'proposed';
    return {
      id: 'room',
      name: nameOf('room'),
      detail: roomPhase === 'reading' ? 'Skaitomas kontūras…'
        : roomPhase === 'saving' ? 'Saugoma…'
          : roomPhase === 'picking' ? 'Pasirinkite patalpą sąraše kairėje'
            : proposed ? 'Siūlomas kontūras — peržiūrėkite' : null,
      keys: proposed ? 'Enter — išsaugoti · Esc — atmesti' : null,
      actions: proposed
        ? [
            { id: 'roomSave', label: 'Išsaugoti', primary: true, title: 'Išsaugoti siūlomą kontūrą (Enter) — po to galėsite atšaukti' },
            { id: 'roomDrop', label: 'Atmesti', title: 'Atmesti siūlomą kontūrą (Esc) — niekas neišsaugoma' },
          ]
        : [exit],
    };
  }
  if (tool === 'pan') {
    return { id: 'pan', name: nameOf('pan'), detail: null, keys: null, actions: [exit] };
  }
  return { id: tool, name: nameOf(tool) || tool, detail: null, keys: null, actions: [exit] };
}
