// First-run coach marks for the viewer (2026-10-16, Togal analysis §11): three
// steps anchored to their buttons — the tool cards on the left, the selected room's action bar (v3 W1-B) —
// shown once per browser.
import { keyText } from './viewerShortcuts.js';

export const COACH_STORAGE_KEY = 'samatu_viewer_onboarded';

export const COACH_STEPS = [
  {
    id: 'calibrate',
    anchor: 'calibrate',
    title: 'Mastelis',
    body: 'Prieš matuojant patikrinkite lapo mastelį — jis parašytas apačioje, būsenos juostoje, kartu su tuo, iš kur jis paimtas. '
      + `Jei rašo „Mastelis nenustatytas", kairėje spauskite „Mastelis" (${keyText('toolCalibrate', { mac: false })}), spustelėkite atkarpos, kurios tikrą ilgį žinote, pradžią ir pabaigą ir įrašykite tą ilgį. `
      + 'Programa pasiūlys artimiausią įprastą mastelį (1:50, 1:100…).',
  },
  {
    id: 'distance',
    anchor: 'distance',
    title: 'Atstumas',
    body: 'Spustelėkite pradžią ir pabaigą — atstumas įsirašo antru spustelėjimu, rezultatas metrais atsiras dešinėje, skiltyje „Matavimai". '
      + 'Žymeklis prilimpa: kvadratas — prie brėžinio sienos kampo, rombas — prie sienos, apskritimas — prie jau nubrėžto matavimo taško. '
      + 'Ką spustelėti toliau, sako sakinys prie žymeklio. '
      + `Klaviatūra: ${keyText('toolDistance', { mac: false })} — atstumas, ${keyText('toolArea', { mac: false })} — plotas, tarpas — tempti brėžinį; „?" — visi klavišai.`,
  },
  {
    id: 'outline',
    anchor: 'outline-edit',
    title: 'Taisyti kontūrą',
    body: `Pasirinkite patalpą sąraše arba brėžinyje — prie jos užrašo atsiras juosta su „Taisyti kontūrą" (${keyText('roomEditOutline', { mac: false })}). Tempkite kampus (jie prilimpa prie sienų), `
      + 'spustelėkite vidurio tašką — pridėsite kampą, dukart spustelėkite kampą — pašalinsite. Enter išsaugo: sienos ir angos perskaitomos iš naujo, kiekiai perskaičiuojami.',
    // The button exists only while a room is selected — say where it will appear instead of pointing at nothing.
    missingAnchorNote: 'Juosta su šiuo mygtuku atsiras pasirinkus patalpą.',
  },
];

function store(storage) {
  if (storage) return storage;
  try { return typeof localStorage !== 'undefined' ? localStorage : null; } catch { return null; }
}

/** True when the coach marks were finished or dismissed in this browser (or storage is unavailable). */
export function coachMarksDone(storage) {
  try {
    const s = store(storage);
    if (!s) return true;                 // private mode / no storage: never nag on every open
    return s.getItem(COACH_STORAGE_KEY) === '1';
  } catch { return true; }
}

export function markCoachMarksDone(storage) {
  try { store(storage)?.setItem(COACH_STORAGE_KEY, '1'); } catch { /* private mode */ }
}

/**
 * Where the card goes for an anchor rect (viewport px): below it — or, with side 'right', beside it (the
 * tool cards stand in a column, so a card below would cover the next tools) — clamped into the viewport.
 * No anchor → centred near the top. Returns { left, top, arrowLeft|null, arrowTop|null }.
 */
export function coachCardPosition(rect, { vw, vh, cardW = 320, cardH = 220, gap = 10, margin = 12, side = 'below' } = {}) {
  if (!rect) return { left: Math.max(margin, (vw - cardW) / 2), top: Math.min(96, vh / 4), arrowLeft: null, arrowTop: null };
  if (side === 'right') {
    const right = rect.left + rect.width;
    const left = Math.min(right + gap, Math.max(margin, vw - cardW - margin));
    const top = Math.min(Math.max(margin, rect.top - 12), Math.max(margin, vh - cardH - margin));
    const mid = rect.top + (rect.height || 0) / 2;
    return { left, top, arrowLeft: null, arrowTop: Math.min(Math.max(14, mid - top), cardH - 14) };
  }
  const centre = rect.left + rect.width / 2;
  const left = Math.min(Math.max(margin, centre - cardW / 2), Math.max(margin, vw - cardW - margin));
  const top = rect.bottom + gap;
  return { left, top, arrowLeft: Math.min(Math.max(14, centre - left), cardW - 14), arrowTop: null };
}
