/**
 * The learning loop's browser half (togal-v2 W11, Togal capability L) — pure.
 *
 * Every accept, reject or edit of an AI result becomes ONE `corrections` row through
 * `POST /api/projects/{id}/corrections` (body shape unchanged). The server writes the
 * outline („konturas") and symbol („simbolis") rows itself; everything else is found
 * here:
 *   - `learningEventsFromChange(prev, next)` compares a project before and after a save
 *     (projectStore.updateProject is the one path every surface saves through), so a row
 *     „Teisinga", a typed quantity and a room „patvirtinta" are recorded whichever table
 *     or rail they were made in;
 *   - `questionCorrection` for a Patikra question answer („Tinka" = the program's own
 *     proposal taken, „Netinka" = his own answer);
 *   - `chatFeedbackCorrection` for the thumbs under a chat answer.
 * The server drops the same fix sent twice within 60 s, so a repeat here is harmless.
 */

export const LEARNING_SOURCES = Object.freeze([
  'eilute_teisinga', 'eilute_kiekis', 'patalpa_patvirtinta', 'klausimas_tinka', 'klausimas_netinka',
  'konturas', 'simbolis', 'pokalbis_taip', 'pokalbis_ne', 'prielaidos', 'patalpa_pertvaros',
  // written by the server when an outline save is undone („Atšaukti", Pathon v3 W1-D; api/room_outline.py)
  'atsaukta',
]);

/** The row's id in the app's own vocabulary: the stable hash first, then the legacy keys. */
export function rowIdOf(row) {
  if (!row || typeof row !== 'object') return '';
  return String(row.id || row._id || `${row.eil_nr ?? ''}-${row.aprasymas ?? ''}`);
}

const num = (v) => (Number.isFinite(Number(v)) && v !== null && v !== '' ? Number(v) : null);

function roomsByNr(project) {
  const out = new Map();
  for (const key of ['patalpos', 'v8_rooms']) {
    for (const r of Array.isArray(project?.[key]) ? project[key] : []) {
      if (r && r.nr != null && !out.has(String(r.nr))) out.set(String(r.nr), r);
    }
  }
  return out;
}

/**
 * What a save changed that a person decided about an AI result → correction payloads.
 * Only NEW stamps count: a recompute that carries the same `user_verified_at` /
 * `manual_override_at` over is not a decision.
 */
export function learningEventsFromChange(prev, next) {
  if (!next || typeof next !== 'object') return [];
  const events = [];

  if (Array.isArray(next.darbu_sarasas)) {
    const before = new Map((Array.isArray(prev?.darbu_sarasas) ? prev.darbu_sarasas : []).map((r) => [rowIdOf(r), r]));
    for (const row of next.darbu_sarasas) {
      const id = rowIdOf(row);
      if (!id) continue;
      const old = before.get(id);
      if (row.manual_override && row.manual_override_at && row.manual_override_at !== old?.manual_override_at) {
        events.push({
          field_path: `eilute.${id}.kiekis`, source: 'eilute_kiekis',
          old_value: num(row.ai_kiekis_original), new_value: num(row.kiekis), room_nr: null, note: null,
        });
      } else if (row.user_verified_at && row.user_verified_at !== old?.user_verified_at) {
        events.push({
          field_path: `eilute.${id}.kiekis`, source: 'eilute_teisinga',
          old_value: num(old?.kiekis ?? row.kiekis), new_value: num(row.kiekis), room_nr: null, note: null,
        });
      }
    }
  }

  if (Array.isArray(next.patalpos) || Array.isArray(next.v8_rooms)) {
    const before = roomsByNr(prev);
    for (const [nr, room] of roomsByNr(next)) {
      // „Pertvarų sienos atviroje erdvėje" he typed on the room sheet (2026-10-17)
      if (room._n_partition_walls_user_at && room._n_partition_walls_user_at !== before.get(nr)?._n_partition_walls_user_at) {
        events.push({
          field_path: `patalpa.${nr}.pertvaros`, source: 'patalpa_pertvaros',
          old_value: num(before.get(nr)?.n_partition_walls) ?? 0, new_value: num(room.n_partition_walls), room_nr: nr, note: null,
        });
      }
      if (room.user_verified_at && room.user_verified_at !== before.get(nr)?.user_verified_at) {
        events.push({
          field_path: `patalpa.${nr}.patvirtinta`, source: 'patalpa_patvirtinta',
          old_value: null, new_value: num(room.plotas_m2), room_nr: nr, note: null,
        });
      }
    }
  }
  return events;
}

const sameNumber = (a, b) => num(a) != null && num(b) != null && Math.abs(num(a) - num(b)) < 1e-9;

/**
 * Did his answer take the program's proposal? `payload` is what the question body
 * reported (`{value, perRoom}` / `{values}` / `{picked, edits}`); `how` names the outline
 * ways: 'accepted' (Tinka on the proposed outline or boundary) or 'own' (a click, a line, a typed length).
 */
export function questionVerdict(question, payload = {}, how = null) {
  if (how === 'accepted') return 'tinka';
  if (how === 'own') return 'netinka';
  const items = Array.isArray(question?.items) ? question.items : [];
  switch (question?.answer) {
    case 'number_all': {
      const own = Object.values(payload?.perRoom || {}).filter((v) => v !== '' && v != null);
      return sameNumber(payload?.value, question?.proposed) && own.every((v) => sameNumber(v, question?.proposed))
        ? 'tinka' : 'netinka';
    }
    case 'numbers':
    case 'choices': {
      const values = payload?.values || {};
      return items.every((i) => {
        const typed = values[String(i?.room_nr)];
        if (typed === undefined || typed === null || typed === '') return true;
        return sameNumber(typed, i?.proposed) || String(typed) === String(i?.proposed);
      }) ? 'tinka' : 'netinka';
    }
    case 'openings': {
      const allPicked = !Array.isArray(payload?.picked) || payload.picked.every((p) => p !== false);
      const noEdits = !payload?.edits || Object.keys(payload.edits).length === 0;
      return allPicked && noEdits ? 'tinka' : 'netinka';
    }
    default:
      return 'tinka';
  }
}

/** A question answered → the payload; the question id rides in `note`, as the journal reads it. */
export function questionCorrection(question, verdict, touched = []) {
  if (!question?.id) return null;
  const ok = verdict === 'tinka';
  const rooms = (Array.isArray(touched) ? touched : []).map(String).sort((a, b) => a.localeCompare(b, 'lt', { numeric: true }));
  return {
    field_path: `klausimas.${question.id}`,
    source: ok ? 'klausimas_tinka' : 'klausimas_netinka',
    old_value: null,
    new_value: { atsakymas: ok ? 'tinka' : 'netinka', patalpos: rooms },
    room_nr: rooms.length === 1 ? rooms[0] : null,
    note: String(question.id),
  };
}

/** A short stable hash of an answer's text, so one answer is one `field_path`. */
export function textHash(text) {
  let h = 5381;
  const s = String(text || '');
  for (let i = 0; i < s.length; i += 1) h = ((h * 33) ^ s.charCodeAt(i)) >>> 0;
  return h.toString(36);
}

/**
 * Thumbs under a chat answer → the payload. `note` keeps the person's own question text (cut to 200
 * characters) — what he asked, nothing the code adds; `new_value` says which way and what the chat was given.
 */
export function chatFeedbackCorrection({ question, answer, up, selection } = {}) {
  if (!answer) return null;
  const rooms = Array.isArray(selection?.rooms) ? selection.rooms.map(String) : [];
  const rows = Array.isArray(selection?.rows) ? selection.rows.map(String) : [];
  return {
    field_path: `pokalbis.${textHash(answer)}`,
    source: up ? 'pokalbis_taip' : 'pokalbis_ne',
    old_value: null,
    new_value: { ivertinimas: up ? 'taip' : 'ne', patalpos: rooms, eilutes: rows },
    room_nr: rooms.length === 1 ? rooms[0] : null,
    note: String(question || '').slice(0, 200) || null,
  };
}
