// The viewer's keyboard and mouse shortcuts — ONE table (2026-10-16, Togal analysis §11;
// Pathon v3 click model, design 2026-10-18 §5).
//
// Everything that names a shortcut reads it from here: ViewerHotkeys matches key
// events through matchViewerHotkey(), the tool rail's tooltips and the pill's key
// reminders are built with keyText() / hintText(), and the „?" guide
// (ShortcutsGuide.jsx) plus its printable PDF list SHORTCUT_GROUPS × VIEWER_SHORTCUTS.
// A key changed here changes everywhere at once, so the guide cannot drift from what
// is bound.
//
// `bound` says who listens for the entry:
//   'hotkeys' — ViewerHotkeys in TakeoffViewer.jsx (tested: every id has a handler)
//   'esc'     — ViewerHotkeys' Esc step (lib/escOrder decides what one Esc undoes)
//   'pan'     — useDragPan: held Space drags the drawing from any tool
//   'draft'   — MeasureLayer, while a measurement is being drawn
//   'outline' — TakeoffViewer's outline-edit listener
//   'search'  — the search box
//   'mouse'   — a pointer gesture, listed for the guide only
//
// A tool on the rail (lib/toolRail) names its entry with `tool: '<rail id>'`.
//
// A combo: { keys: [KeyboardEvent.key values, first one is shown], mod?: 'primary'
// (⌘ on Mac, Ctrl elsewhere — both are accepted), shift?: true | false (absent =
// either) }. Mouse entries carry `display` instead: a string or { mac, other }.

export const SHORTCUT_GROUPS = [
  { id: 'tools', title: 'Įrankiai' },
  { id: 'navigation', title: 'Naršymas' },
  { id: 'measure', title: 'Braižant matavimą' },
  { id: 'room', title: 'Pažymėta patalpa' },
  { id: 'outline', title: 'Kontūro taisymas' },
  { id: 'selection', title: 'Žymėjimas ir istorija' },
  { id: 'layers', title: 'Sluoksniai' },
];

export const VIEWER_SHORTCUTS = [
  // ── Įrankiai (the rail; every tool has a key)
  { id: 'toolSelect', tool: 'select', group: 'tools', bound: 'hotkeys', label: 'Žymėti — pažymėti nubrėžtą matavimą ar žymę', combos: [{ keys: ['1'] }, { keys: ['v', 'V'] }] },
  { id: 'toolLasso', tool: 'lasso', group: 'tools', bound: 'hotkeys', label: 'Laso — apvesti kelis matavimus ir žymes', combos: [{ keys: ['l', 'L'] }] },
  { id: 'toolPan', tool: 'pan', group: 'tools', bound: 'hotkeys', label: 'Rankutė — tempti brėžinį', combos: [{ keys: ['h', 'H'] }] },
  { id: 'panHold', group: 'tools', bound: 'pan', label: 'Laikyti tarpą ir tempti — brėžinys juda su bet kuriuo įrankiu, braižomas matavimas lieka', combos: [{ keys: [' '] }] },
  { id: 'toolDistance', tool: 'distance', group: 'tools', bound: 'hotkeys', label: 'Atstumas — matuoti metrais', combos: [{ keys: ['2'] }] },
  { id: 'toolArea', tool: 'area', group: 'tools', bound: 'hotkeys', label: 'Plotas — matuoti m²', combos: [{ keys: ['3'] }] },
  { id: 'toolPerimeter', tool: 'perimeter', group: 'tools', bound: 'hotkeys', label: 'Perimetras — kontūro ilgis metrais', combos: [{ keys: ['4'] }] },
  { id: 'toolCount', tool: 'count', group: 'tools', bound: 'hotkeys', label: 'Kiekis — skaičiuoti vienetus', combos: [{ keys: ['6'] }] },
  // the room tool (Pathon v3 W1-D): one click inside a room, its outline off the walls, proposed, then saved
  { id: 'toolRoom', tool: 'room', group: 'tools', bound: 'hotkeys', label: 'Patalpa — kontūras vienu spustelėjimu patalpos viduje; Enter arba kitas spustelėjimas išsaugo', combos: [{ keys: ['r', 'R'] }] },
  { id: 'toolFindSimilar', tool: 'findSimilar', group: 'tools', bound: 'hotkeys', label: 'Rasti panašius — apvesti vieną simbolį, programa suras panašius', combos: [{ keys: ['f', 'F'], shift: false }] },
  { id: 'toolCalibrate', tool: 'calibrate', group: 'tools', bound: 'hotkeys', label: 'Mastelis — nustatyti pagal atkarpą, kurios ilgį žinote', combos: [{ keys: ['k', 'K'] }] },

  // ── Naršymas
  { id: 'zoomIn', group: 'navigation', bound: 'hotkeys', label: 'Artinti', combos: [{ keys: ['+', '='] }] },
  { id: 'zoomOut', group: 'navigation', bound: 'hotkeys', label: 'Tolinti', combos: [{ keys: ['-'] }] },
  { id: 'fitPage', group: 'navigation', bound: 'hotkeys', label: 'Sutalpinti visą puslapį', combos: [{ keys: ['0'] }] },
  { id: 'fitWidth', group: 'navigation', bound: 'hotkeys', label: 'Sutalpinti per visą plotį', combos: [{ keys: ['w', 'W'] }] },
  { id: 'frameSelection', group: 'navigation', bound: 'hotkeys', label: 'Parodyti pažymėtą patalpą ar matavimą per visą langą', combos: [{ keys: ['F', 'f'], shift: true }, { keys: ['.'] }] },
  { id: 'nextPage', group: 'navigation', bound: 'hotkeys', label: 'Kitas puslapis', combos: [{ keys: ['PageDown'] }, { keys: [']'] }] },
  { id: 'prevPage', group: 'navigation', bound: 'hotkeys', label: 'Ankstesnis puslapis', combos: [{ keys: ['PageUp'] }, { keys: ['['] }] },
  { id: 'toggleThumbs', group: 'navigation', bound: 'hotkeys', label: 'Lapų juosta: plati arba siaura', combos: [{ keys: ['t', 'T'] }] },
  { id: 'openSearch', group: 'navigation', bound: 'hotkeys', label: 'Ieškoti teksto brėžinyje', combos: [{ keys: ['f', 'F'], mod: 'primary' }, { keys: ['/'] }] },
  { id: 'searchNext', group: 'navigation', bound: 'search', label: 'Paieškoje — kitas rezultatas', combos: [{ keys: ['Enter'] }] },
  { id: 'searchPrev', group: 'navigation', bound: 'search', label: 'Paieškoje — ankstesnis rezultatas', combos: [{ keys: ['Enter'], shift: true }] },
  { id: 'print', group: 'navigation', bound: 'hotkeys', label: 'Spausdinti brėžinį', combos: [{ keys: ['p', 'P'], mod: 'primary' }] },
  { id: 'wheelZoom', group: 'navigation', bound: 'mouse', label: 'Artinti ties žymekliu', display: { mac: '⌘ + ratukas arba suspausti du pirštus', other: 'Ctrl + pelės ratukas' } },
  { id: 'openGuide', group: 'navigation', bound: 'hotkeys', label: 'Šis sparčiųjų klavišų sąrašas', combos: [{ keys: ['?'] }] },

  // ── Braižant matavimą
  { id: 'draftFinish', group: 'measure', bound: 'draft', label: 'Baigti braižomą matavimą', hint: 'baigti', combos: [{ keys: ['Enter'] }] },
  { id: 'draftFinishMouse', group: 'measure', bound: 'mouse', label: 'Baigti braižomą matavimą', display: 'Dukart spustelėti' },
  { id: 'draftMenu', group: 'measure', bound: 'mouse', label: 'Braižant — „Baigti" arba „Atšaukti" prie žymeklio', display: 'Dešinysis pelės klavišas' },
  { id: 'draftStepBack', group: 'measure', bound: 'esc', label: 'Pašalinti paskutinį tašką; kai taškų nebėra — išeiti iš įrankio', hint: 'atgal', combos: [{ keys: ['Escape'] }] },
  { id: 'draftUndoPoint', group: 'measure', bound: 'draft', label: 'Pašalinti paskutinį nubrėžtą tašką', hint: 'atgal', combos: [{ keys: ['z', 'Z'] }, { keys: ['Backspace'] }] },
  { id: 'distanceChain', group: 'measure', bound: 'mouse', label: 'Atstumas įsirašo antru spustelėjimu; su Shift — tęsiamas toliau', display: 'Shift + spustelėti' },
  { id: 'orthoLock', group: 'measure', bound: 'mouse', label: 'Brėžti tik horizontaliai, vertikaliai arba 45° kampu', display: 'Laikyti Shift' },
  { id: 'countRemove', group: 'measure', bound: 'mouse', label: 'Kiekio įrankiu — pašalinti tą žymę', display: 'Spustelėti ant žymės' },

  // ── Pažymėta patalpa (the selection bar's actions)
  { id: 'roomEditOutline', group: 'room', bound: 'hotkeys', label: 'Taisyti kontūrą — tempti kampus, prilimpa prie sienų', combos: [{ keys: ['e', 'E'] }] },
  { id: 'roomMerge', group: 'room', bound: 'hotkeys', label: 'Sujungti su gretima patalpa', combos: [{ keys: ['m', 'M'] }] },
  { id: 'roomSubtract', group: 'room', bound: 'hotkeys', label: 'Atimti koloną, spintą ar šachtą iš patalpos', combos: [{ keys: ['x', 'X'] }] },
  { id: 'roomDoubleClick', group: 'room', bound: 'mouse', label: 'Taisyti patalpos kontūrą (kaip E); ant matavimo — taisyti jo taškus', display: 'Dukart spustelėti patalpą ar matavimą' },

  // ── Kontūro taisymas
  { id: 'outlineDrag', group: 'outline', bound: 'mouse', label: 'Perkelti viršūnę (prilimpa prie sienų)', display: 'Tempti kampą' },
  { id: 'outlineInsert', group: 'outline', bound: 'mouse', label: 'Pridėti viršūnę', display: 'Spustelėti kraštinę ar jos vidurio tašką' },
  { id: 'outlineRemove', group: 'outline', bound: 'mouse', label: 'Pašalinti viršūnę', display: 'Dukart spustelėti kampą' },
  { id: 'outlineEdgeDrag', group: 'outline', bound: 'mouse', label: 'Perkelti visą kraštinę (abu kampai prilimpa prie sienų)', display: 'Tempti kraštinę' },
  { id: 'outlineVertexMenu', group: 'outline', bound: 'mouse', label: 'Kampo veiksmai: ištrinti, iškirpti angą', display: 'Spustelėti kampą arba dešinysis klavišas' },
  { id: 'outlineBox', group: 'outline', bound: 'mouse', label: 'Pažymėti kelis kampus (su Ctrl — pridėti po vieną)', display: 'Tempti rėmelį tuščioje vietoje' },
  { id: 'outlineDeleteSelected', group: 'outline', bound: 'outline', label: 'Ištrinti pažymėtus kampus', hint: 'ištrinti kampus', combos: [{ keys: ['Delete'] }, { keys: ['Backspace'] }] },
  { id: 'outlineNudge', group: 'outline', bound: 'outline', label: 'Pastumti pažymėtus kampus (su Shift — 10 kartų toliau)', combos: [{ keys: ['ArrowLeft'] }, { keys: ['ArrowRight'] }, { keys: ['ArrowUp'] }, { keys: ['ArrowDown'] }] },
  { id: 'outlineUndo', group: 'outline', bound: 'outline', label: 'Atšaukti paskutinį viršūnės pakeitimą', hint: 'atgal', combos: [{ keys: ['z', 'Z'] }] },
  { id: 'outlineSave', group: 'outline', bound: 'outline', label: 'Išsaugoti kontūrą', hint: 'išsaugoti', combos: [{ keys: ['Enter'] }] },
  { id: 'outlineCancel', group: 'outline', bound: 'esc', label: 'Atšaukti redagavimą (niekas neišsaugoma)', hint: 'atšaukti', combos: [{ keys: ['Escape'] }] },

  // ── Žymėjimas ir istorija
  { id: 'deleteSelected', group: 'selection', bound: 'hotkeys', label: 'Ištrinti pažymėtus matavimus („Žymėti" arba „Laso" įrankiu)', hint: 'ištrinti pažymėtus', combos: [{ keys: ['Delete'] }, { keys: ['Backspace'] }] },
  { id: 'lassoAdd', group: 'selection', bound: 'mouse', label: 'Laso — pridėti prie pažymėtų', display: 'Laikyti Shift apvedant' },
  { id: 'contextMenu', group: 'selection', bound: 'mouse', label: 'Matavimo meniu: pervadinti, keisti tipą, ištrinti, rodyti sąraše; su laso — veiksmai su visais pažymėtais', display: 'Dešinysis pelės klavišas ant matavimo' },
  { id: 'undo', group: 'selection', bound: 'hotkeys', label: 'Atšaukti paskutinį veiksmą su matavimais ir žymėmis', combos: [{ keys: ['z', 'Z'], mod: 'primary', shift: false }] },
  { id: 'redo', group: 'selection', bound: 'hotkeys', label: 'Grąžinti atšauktą veiksmą', combos: [{ keys: ['z', 'Z'], mod: 'primary', shift: true }, { keys: ['y', 'Y'], mod: 'primary' }] },
  { id: 'escape', group: 'selection', bound: 'hotkeys', label: 'Žingsnis atgal: taškas → įrankis → skydelis → pažymėjimas (patalpa lieka, kol atidarytas skydelis)', combos: [{ keys: ['Escape'] }] },

  // ── Sluoksniai
  { id: 'toggleZoneFills', group: 'layers', bound: 'hotkeys', label: 'Nuspalvinti patalpas arba palikti brėžinį švarų', combos: [{ keys: ['u', 'U'] }] },
  { id: 'toggleWallsLayer', group: 'layers', bound: 'hotkeys', label: 'Sienų sluoksnis: sienos, kontūrai ir angos, kurias programa perskaitė', combos: [{ keys: ['s', 'S'] }] },
];

const BY_ID = new Map(VIEWER_SHORTCUTS.map((s) => [s.id, s]));
const BY_TOOL = new Map(VIEWER_SHORTCUTS.filter((s) => s.tool).map((s) => [s.tool, s]));

export function shortcutById(id) {
  return BY_ID.get(id) || null;
}

/** The entry that arms a rail tool ('distance' → toolDistance), or null. */
export function toolShortcut(toolId) {
  return BY_TOOL.get(toolId) || null;
}

/** True for the key event that starts or ends a Space-held pan (the table's `panHold` entry). */
export function isPanHoldKey(e) {
  if (!e || e.metaKey || e.ctrlKey || e.altKey) return false;
  return (shortcutById('panHold')?.combos || []).some((c) => c.keys.includes(e.key));
}

export function isMacPlatform(nav = (typeof navigator !== 'undefined' ? navigator : null)) {
  const p = nav?.userAgentData?.platform || nav?.platform || nav?.userAgent || '';
  return /mac|iphone|ipad|ipod/i.test(p);
}

const KEY_NAMES = {
  PageDown: 'PgDn', PageUp: 'PgUp', Escape: 'Esc', '-': '−', ' ': 'Tarpas',
  ArrowLeft: '←', ArrowRight: '→', ArrowUp: '↑', ArrowDown: '↓',
};

function keyName(k) {
  if (KEY_NAMES[k]) return KEY_NAMES[k];
  return k.length === 1 ? k.toUpperCase() : k;
}

/** One combo as the person reads it: „Ctrl + Shift + Z" / „⌘ ⇧ Z". */
export function formatCombo(combo, { mac = isMacPlatform() } = {}) {
  const parts = [];
  if (combo.mod === 'primary') parts.push(mac ? '⌘' : 'Ctrl');
  if (combo.shift === true) parts.push(mac ? '⇧' : 'Shift');
  parts.push(keyName(combo.keys[0]));
  return parts.join(mac ? ' ' : ' + ');
}

/** Every way to trigger the entry, for the guide: ['Ctrl + F', '/', 'F'] or the mouse text. */
export function displayKeys(entry, { mac = isMacPlatform() } = {}) {
  if (!entry) return [];
  if (entry.display) {
    return [typeof entry.display === 'string' ? entry.display : (mac ? entry.display.mac : entry.display.other)];
  }
  return (entry.combos || []).map((c) => formatCombo(c, { mac }));
}

/** The shortest key text for a title: „(2)", „Ctrl + Z". Alternatives joined with „ / ". */
export function keyText(id, { mac = isMacPlatform(), all = false } = {}) {
  const keys = displayKeys(shortcutById(id), { mac });
  return all ? keys.join(' / ') : (keys[0] || '');
}

/** A button title with its key: „Tolinti (−)". Unknown id → the title alone. */
export function withKey(title, id, opts) {
  const k = keyText(id, opts);
  return k ? `${title} (${k})` : title;
}

/** Status-bar hint pieces: „Z — atgal · Enter — išsaugoti · Esc — atšaukti". */
export function hintText(ids, { mac = isMacPlatform() } = {}) {
  return ids
    .map((id) => {
      const e = shortcutById(id);
      if (!e) return null;
      return `${keyText(id, { mac, all: true })} — ${e.hint || e.label.toLowerCase()}`;
    })
    .filter(Boolean)
    .join(' · ');
}

function comboMatches(combo, e) {
  if (!combo.keys.includes(e.key)) return false;
  const primary = !!(e.metaKey || e.ctrlKey);
  if (combo.mod === 'primary') {
    if (!primary || e.altKey) return false;
  } else if (primary) {
    return false;
  }
  if (combo.shift === true && !e.shiftKey) return false;
  if (combo.shift === false && e.shiftKey) return false;
  return true;
}

/**
 * The ViewerHotkeys entry a key event triggers, or null. Only `bound: 'hotkeys'`
 * entries take part; the first match in table order wins (undo is listed before
 * redo, and they differ by Shift).
 */
export function matchViewerHotkey(e) {
  if (!e || typeof e.key !== 'string') return null;
  for (const s of VIEWER_SHORTCUTS) {
    if (s.bound !== 'hotkeys') continue;
    if ((s.combos || []).some((c) => comboMatches(c, e))) return s.id;
  }
  return null;
}

/** The guide's rows: [{ group, title, items: [{ id, label, keys: [..] }] }]. */
export function shortcutGuideRows({ mac = isMacPlatform() } = {}) {
  return SHORTCUT_GROUPS.map((g) => ({
    group: g.id,
    title: g.title,
    items: VIEWER_SHORTCUTS.filter((s) => s.group === g.id).map((s) => ({
      id: s.id, label: s.label, keys: displayKeys(s, { mac }), mouse: !!s.display,
    })),
  }));
}
