// toolRail — what the viewer's left tool cards hold (Pathon v3 click model, plan W1-B task B1; design
// 2026-10-18 §5–§6, Togal §10, Kreo §11).
//
// Floating icon cards with a short Lithuanian label under each icon; the tooltip says the name, the key
// and one sentence. Keys are never written here — they come from lib/viewerShortcuts (the table the „?"
// guide prints), so a key changed there changes on the card too. Icons are the component's business
// (ToolRail.jsx maps ids to lucide icons); this module is pure so node:test can hold the contract:
// every tool has a key, and no two tools share one.

import { toolShortcut, shortcutById, keyText } from './viewerShortcuts.js';

/**
 * The cards, top to bottom. `tools` are modes (one at a time, pressed while armed); a `toggles` card
 * holds layer switches that stay on independently. `name` is the full name (aria-label, tooltip);
 * `label` is the short word under the icon (it must fit a 64 px card at 12 px).
 */
export const RAIL_GROUPS = [
  {
    id: 'navigate',
    title: 'Naršyti',
    tools: [
      { id: 'select', name: 'Žymėti', label: 'Žymėti', sentence: 'Spustelėkite nubrėžtą matavimą ar žymę — Delete ištrina, dešinysis klavišas atidaro meniu.' },
      { id: 'lasso', name: 'Laso', label: 'Laso', sentence: 'Apveskite kelis matavimus ir žymes — visi apvesti pažymimi; su Shift — pridedami.' },
      { id: 'pan', name: 'Rankutė', label: 'Rankutė', sentence: 'Tempkite brėžinį. Su bet kuriuo kitu įrankiu — laikykite tarpą.' },
    ],
  },
  {
    id: 'measure',
    title: 'Matuoti',
    tools: [
      { id: 'distance', name: 'Atstumas', label: 'Atstumas', sentence: 'Spustelėkite pradžią ir pabaigą — atstumas metrais įsirašo antru spustelėjimu; su Shift — tęsiate toliau.' },
      { id: 'area', name: 'Plotas', label: 'Plotas', sentence: 'Apveskite kontūrą — plotas m².' },
      { id: 'perimeter', name: 'Perimetras', label: 'Perimetras', sentence: 'Spustelėkite kampus iš eilės — kontūro ilgis metrais.' },
      { id: 'count', name: 'Kiekis', label: 'Kiekis', sentence: 'Pasirinkite tipą ir spustelėkite kiekvieną elementą (rozetę, šviestuvą).' },
    ],
  },
  {
    id: 'read',
    title: 'Skaityti brėžinį',
    tools: [
      { id: 'room', name: 'Patalpa', label: 'Patalpa', sentence: 'Spustelėkite patalpos viduje — kontūras pagal brėžinio sienas.' },
      { id: 'findSimilar', name: 'Rasti panašius', label: 'Panašūs', sentence: 'Apveskite vieną simbolį — programa suras panašius, jūs peržiūrite ir pridedate kaip kiekį.' },
      { id: 'calibrate', name: 'Mastelis', label: 'Mastelis', sentence: 'Pažymėkite atkarpą, kurios tikrą ilgį žinote, ir jį įrašykite.' },
    ],
  },
  {
    id: 'layers',
    title: 'Sluoksniai',
    toggles: true,
    tools: [
      { id: 'zones', name: 'Patalpų spalvos', label: 'Patalpos', shortcut: 'toggleZoneFills', sentence: 'Nuspalvinti patalpas pagal jų kontūrus arba palikti brėžinį švarų.' },
      { id: 'walls', name: 'Sienų sluoksnis', label: 'Sienos', shortcut: 'toggleWallsLayer', sentence: 'Sienos, patalpų kontūrai ir angos, kurias programa perskaitė iš brėžinio.' },
    ],
  },
];

export const RAIL_TOOLS = RAIL_GROUPS.flatMap((g) => g.tools.map((t) => ({ ...t, group: g.id, toggle: !!g.toggles })));

const BY_ID = new Map(RAIL_TOOLS.map((t) => [t.id, t]));

export function railTool(id) {
  return BY_ID.get(id) || null;
}

/** The shortcut entry behind a rail item: a tool's arming key, or a layer's own entry. */
export function railShortcut(id) {
  const t = railTool(id);
  if (!t) return null;
  return t.shortcut ? shortcutById(t.shortcut) : toolShortcut(id);
}

/** The key as the card shows it: „2", „V" … (every alternative: `all`). */
export function railKey(id, opts = {}) {
  const entry = railShortcut(id);
  return entry ? keyText(entry.id, opts) : '';
}

/** Tooltip text: „Atstumas (2) — Spustelėkite pradžią ir pabaigą …". */
export function railTooltip(id, opts = {}) {
  const t = railTool(id);
  if (!t) return '';
  const k = railKey(id, { ...opts, all: true });
  return `${t.name}${k ? ` (${k})` : ''} — ${t.sentence}`;
}
