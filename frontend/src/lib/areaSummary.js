/**
 * areaSummary — the project's area three ways, each with where it comes from (Pathon v3 W5-D, D13).
 *
 *  · lentele  — the room table's total as the drawing writes it (`_ceiling_anchor`, the eksplikacija's
 *               „Iš viso" / „Bendras plotas"), else the sum of the room-table rows the rooms carry;
 *  · konturai — the sum of the wall-exact outlines' areas (`_konturas.plotas_m2` on rooms whose outline follows
 *               the walls), with how many rooms have one — the area INSIDE the walls;
 *  · uzstatymas — the plan footprint, only when the drawing writes it (a designer's figure whose words say so);
 *               otherwise a blank that says the drawing does not give it.
 *
 * Sums of numbers the project already holds — no new formula, nothing estimated. A room merged into another
 * („Sujungti") is counted in the one that kept it. Pure.
 */

const WALL_OUTLINES = new Set(['vektoriniai_konturai', 'sienu_konturas', 'corrected', 'manual']);
const TABLE_AREA_SOURCES = new Set(['eksplikacija', 'eksplikacija_lentele', 'lentele', 'specifikacija']);
const FOOTPRINT_RE = /u[žz]statym|pastato\s+plot|statinio\s+plot/i;

const isObj = (v) => !!v && typeof v === 'object' && !Array.isArray(v);
const num = (v) => (v != null && v !== '' && Number.isFinite(Number(v)) ? Number(v) : null);
const round2 = (v) => Math.round(v * 100) / 100;
const lt2 = (v) => round2(v).toFixed(2).replace('.', ',');

function roomsOf(project) {
  const stored = Array.isArray(project?.v8_rooms) && project.v8_rooms.length ? project.v8_rooms : project?.patalpos;
  return (Array.isArray(stored) ? stored : []).filter((r) => isObj(r) && !r._sujungta_i && !r._neskaiciuoti);
}

function tableEntry(project, rooms) {
  const a = isObj(project?._ceiling_anchor) ? project._ceiling_anchor : null;
  const total = num(a?.total_area_m2 ?? a?.value ?? a?.plotas_m2 ?? a?.viso_m2);
  const page = num(a?.page ?? a?.puslapio_nr);
  if (total != null && total > 0 && !String(a?.label || '').startsWith('plano užrašų')) {
    const label = String(a?.label || '').trim();
    return {
      key: 'lentele', value: round2(total), page,
      sentence: `Patalpų lentelėje${page ? ` (${page} psl.)` : ''} parašyta${label ? ` „${label}“` : ''}: ${lt2(total)} m².`,
    };
  }
  if (total != null && total > 0) {
    // no room table: the areas written on the plan itself, added up (the ceiling anchor's own fallback)
    return {
      key: 'lentele', value: round2(total), page,
      sentence: `Patalpų lentelės brėžinyje nėra — sudėti plane prie patalpų parašyti plotai${page ? ` (${page} psl.)` : ''}: ${lt2(total)} m².`,
    };
  }
  const fromTable = rooms.filter((r) => TABLE_AREA_SOURCES.has(String(r.plotas_saltinis || r.plotas_source || '')) && num(r.plotas_m2) > 0);
  if (fromTable.length) {
    const sum = fromTable.reduce((s, r) => s + num(r.plotas_m2), 0);
    return {
      key: 'lentele', value: round2(sum), page: num(fromTable[0].eksplikacija_source_page),
      sentence: `Bendros sumos lentelė neparašo — sudėtos ${fromTable.length} patalpų lentelės eilutės: ${lt2(sum)} m².`,
    };
  }
  return { key: 'lentele', value: null, page: null, sentence: 'Patalpų lentelės brėžinyje neradau — šio ploto nėra.' };
}

function outlineEntry(rooms) {
  const withOutline = rooms.filter((r) => WALL_OUTLINES.has(String(r.polygon_source || '')) && num(r?._konturas?.plotas_m2) > 0);
  if (!withOutline.length) {
    return { key: 'konturai', value: null, page: null, n: 0, of: rooms.length,
      sentence: 'Nė viena patalpa neturi kontūro pagal sienas — šio ploto nėra.' };
  }
  const sum = withOutline.reduce((s, r) => s + num(r._konturas.plotas_m2), 0);
  const pages = [...new Set(withOutline.map((r) => num(r._konturas.page)).filter((p) => p != null))].sort((a, b) => a - b);
  const all = withOutline.length === rooms.length;
  return {
    key: 'konturai', value: round2(sum), page: pages[0] ?? null, n: withOutline.length, of: rooms.length,
    sentence: `${all ? 'Visų' : `${withOutline.length} iš ${rooms.length}`} patalpų kontūrų pagal sienas plotų suma`
      + `${pages.length ? ` (${pages.length === 1 ? `${pages[0]} psl.` : `lapai ${pages.join(', ')}`})` : ''}: ${lt2(sum)} m²`
      + `${all ? '' : ' — be patalpų, kurių kontūro nėra'}.`,
  };
}

function footprintEntry(project) {
  const figures = Array.isArray(project?._autoriaus_kiekiai) ? project._autoriaus_kiekiai : [];
  const hit = figures.find((f) => isObj(f) && FOOTPRINT_RE.test(String(f.label || '')) && num(f.value) > 0
    && /m2|m²/.test(String(f.unit || 'm2')));
  if (hit) {
    return {
      key: 'uzstatymas', value: round2(num(hit.value)), page: num(hit.page),
      sentence: `Brėžinyje${hit.page ? ` (${hit.page} psl.)` : ''} parašyta „${String(hit.label).trim()}“: ${lt2(num(hit.value))} m².`,
    };
  }
  return { key: 'uzstatymas', value: null, page: null, sentence: 'Užstatymo ploto brėžinys neparašo — šio ploto nėra.' };
}

export const AREA_LABELS = Object.freeze({
  lentele: 'Pagal patalpų lentelę',
  konturai: 'Pagal kontūrus (sienų vidus)',
  uzstatymas: 'Užstatymo plotas',
});

/** [{key, label, value (m²) | null, page, sentence}] in the order lentele · konturai · uzstatymas. */
export function areaSummary(project) {
  const rooms = roomsOf(project);
  return [tableEntry(project, rooms), outlineEntry(rooms), footprintEntry(project)]
    .map((e) => ({ ...e, label: AREA_LABELS[e.key] }));
}
