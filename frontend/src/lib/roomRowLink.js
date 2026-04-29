// roomRowLink — bridge darbu_sarasas rows to patalpos[] rooms by name matching
// (Phase 14 / QW05 bidirectional highlight). The simplified extractor doesn't
// emit explicit trace_links, so we lean on case-insensitive substring match
// of room name in row aprasymas.

function norm(s) {
  return (s || '').toString().toLowerCase().trim();
}

// Returns Set<roomNr> for rooms whose name appears in row.aprasymas.
// Empty set if row is null or no match.
export function roomNrsForRow(row, rooms) {
  const out = new Set();
  if (!row || !Array.isArray(rooms)) return out;
  const txt = norm(row.aprasymas);
  if (!txt) return out;
  for (const r of rooms) {
    const name = norm(r?.pavadinimas);
    if (!name || name.length < 3) continue;
    if (txt.includes(name)) out.add(r.nr);
  }
  return out;
}

// Returns Set<rowId> for rows whose aprasymas contains the given room's name.
export function rowIdsForRoom(room, darbai) {
  const out = new Set();
  if (!room || !Array.isArray(darbai)) return out;
  const name = norm(room.pavadinimas);
  if (!name || name.length < 3) return out;
  for (const d of darbai) {
    const txt = norm(d.aprasymas);
    if (txt && txt.includes(name) && d._id) out.add(d._id);
  }
  return out;
}
