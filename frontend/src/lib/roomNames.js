// roomNames — „Ar tai virtuvė? [Taip] [Kita…]" (Pathon v3 W5-C, C3 / coverage #39).
//
// A room outlined without a row in the room table has no name the program can trust. The server reads the
// words the drawing writes inside the room's outline (GET …/rooms/{nr}/name-hints) and proposes a name; this
// module decides WHEN to ask, and builds the room patch the answer saves (down the room edit path — so the
// sheet offers „Atšaukti pataisymą" like for any fact). Pure; fetchNameHints is the one network call.

import { API_BASE } from './apiBase.js';

// the area sources that mean „this room is a row of the room table"
const TABLE_SOURCES = new Set(['eksplikacija', 'eksplikacija_sujungta']);

// the names offered under „Kita…" — the room kinds the engine knows (paskirtis), in the builder's words
export const ROOM_NAME_CHOICES = [
  { pavadinimas: 'Svetainė', paskirtis: 'gyvenamoji' },
  { pavadinimas: 'Miegamasis', paskirtis: 'miegamoji' },
  { pavadinimas: 'Virtuvė', paskirtis: 'virtuve' },
  { pavadinimas: 'Vonios kambarys', paskirtis: 'vonia' },
  { pavadinimas: 'WC', paskirtis: 'wc' },
  { pavadinimas: 'Koridorius', paskirtis: 'koridorius' },
  { pavadinimas: 'Drabužinė', paskirtis: 'drabuzine' },
  { pavadinimas: 'Sandėliukas', paskirtis: 'sandeliukas' },
  { pavadinimas: 'Katilinė', paskirtis: 'katiline' },
  { pavadinimas: 'Darbo kambarys', paskirtis: 'kabinetas' },
];

const fold = (s) => String(s || '').normalize('NFKD').replace(/[̀-ͯ]/g, '').toLowerCase().trim();

/** True when the room is outlined on the drawing and is not a row of the room table — then it may be asked. */
export function namesAreAsked(room) {
  if (!room || typeof room !== 'object') return false;
  if (!Array.isArray(room.polygon_pct) || room.polygon_pct.length < 3) return false;
  if (room._pavadinimas_user_at) return false;               // he already named it
  const src = room.plotas_saltinis || room.plotas_source || null;
  if (TABLE_SOURCES.has(src)) return false;
  if (Number.isFinite(Number(room.eksplikacija_row_idx)) && room.eksplikacija_row_idx != null) return false;
  return true;
}

/** The proposals worth asking: the ones whose name the room does not already carry. */
export function openHints(room, hints) {
  const have = fold(room?.pavadinimas);
  return (Array.isArray(hints) ? hints : []).filter((h) => h?.pavadinimas && fold(h.pavadinimas) !== have);
}

/** The room patch an answer saves: the name and the kind, both marked as his (a re-read keeps them). */
export function namePatch(choice, now = new Date().toISOString()) {
  const patch = { pavadinimas: String(choice?.pavadinimas || '').trim(), _pavadinimas_user_at: now };
  if (choice?.paskirtis) {
    patch.paskirtis = choice.paskirtis;
    patch._paskirtis_user_at = now;
  }
  return patch;
}

export async function fetchNameHints(projectId, roomNr, { signal } = {}) {
  const url = `${API_BASE}/api/projects/${encodeURIComponent(projectId)}/rooms/${encodeURIComponent(roomNr)}/name-hints`;
  const res = await fetch(url, { credentials: 'include', signal });
  if (!res.ok) {
    const err = new Error(`HTTP ${res.status}`);
    err.status = res.status;
    throw err;
  }
  return res.json();
}
