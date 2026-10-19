/**
 * openingsBySize — the doors and windows the rooms list, grouped by kind and size: „Durys 900 × 2100 — 7"
 * (Pathon v3 W5-D, D11 #76). A count, not a quantity: what the room lists already say, added up. A door two
 * rooms both list is counted once — in the room the engine counts it in (`_bendra_su_n`, universal_rules
 * mark_shared_doors). Rooms switched off („Neskaičiuoju") and rooms merged into another are left out; a size the
 * reading did not give is grouped as „dydis nežinomas". Pure.
 */

const KIND_LABEL = {
  duris: 'Durys', pasleptos_duris: 'Paslėptos durys', stumdomos_duris: 'Stumdomos durys', langas: 'Langai',
};
const ORDER = ['duris', 'pasleptos_duris', 'stumdomos_duris', 'langas'];

const num = (v) => (v != null && v !== '' && Number.isFinite(Number(v)) ? Number(v) : null);

export function openingsBySize(project) {
  const stored = Array.isArray(project?.v8_rooms) && project.v8_rooms.length ? project.v8_rooms : project?.patalpos;
  const rooms = (Array.isArray(stored) ? stored : []).filter((r) => r && !r._neskaiciuoti && !r._sujungta_i);
  const groups = new Map();
  for (const r of rooms) {
    for (const el of Array.isArray(r.elementai) ? r.elementai : []) {
      const kind = String(el?.tipas || '');
      if (!KIND_LABEL[kind]) continue;
      const n = Math.max(0, (num(el.kiekis) ?? 1) - (num(el._bendra_su_n) ?? 0));
      if (!n) continue;
      const w = num(el.plotis_mm);
      const h = num(el.aukstis_mm);
      const key = `${kind}|${w ?? ''}|${h ?? ''}`;
      const g = groups.get(key) || { kind, label: KIND_LABEL[kind], plotis_mm: w, aukstis_mm: h, n: 0, rooms: [] };
      g.n += n;
      const nr = String(r.nr ?? '').trim();
      if (nr && !g.rooms.includes(nr)) g.rooms.push(nr);
      groups.set(key, g);
    }
  }
  return [...groups.values()]
    .map((g) => ({ ...g, size: g.plotis_mm && g.aukstis_mm ? `${g.plotis_mm} × ${g.aukstis_mm}` : 'dydis nežinomas' }))
    .sort((a, b) => ORDER.indexOf(a.kind) - ORDER.indexOf(b.kind) || b.n - a.n
      || (a.plotis_mm ?? 1e9) - (b.plotis_mm ?? 1e9) || (a.aukstis_mm ?? 1e9) - (b.aukstis_mm ?? 1e9));
}
