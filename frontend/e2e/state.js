/**
 * The smoke suite's data state: a pristine snapshot of the backend's SQLite file and pdf_store taken before
 * the run, the guide's start state derived from it, and the restore that puts either back.
 *
 * Why the SQLite online-backup API (the sqlite3 CLI's `.backup` / `.restore`) and not a file copy: the
 * backend runs while the suite restores, its database is in WAL mode, and a plain `cp` over a live WAL
 * database can leave a -wal file whose frames belong to the old file (a corrupt or half-old database).
 * `.restore` runs sqlite3_backup_step(-1) into the live file under SQLite's own write lock: every other
 * connection sees either the whole old or the whole new database, never a mix, and the -wal/-shm pair
 * stays consistent. The backend opens a fresh connection per call (db._conn) and holds none between
 * requests, so nothing keeps a stale page cache; after every restore the suite runs `PRAGMA quick_check`
 * and reads the project back through the API and compares it with the snapshot's fingerprint.
 *
 * pdf_store is restored by a manifest: files the run added are deleted, files it changed or removed are
 * copied back from the snapshot; untouched files (the project's own drawing) are never rewritten.
 */
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';

const HERE = path.dirname(fileURLToPath(import.meta.url));
export const REPO = path.resolve(HERE, '..', '..');
export const DATA_DIR = process.env.E2E_DATA_DIR || path.join(REPO, 'backend', 'data');
export const DB = path.join(DATA_DIR, 'samatu.db');
export const STORE = path.join(DATA_DIR, 'pdf_store');
export const STATE = path.join(HERE, '.state');
export const PRISTINE_DB = path.join(STATE, 'pristine.db');
export const PRISTINE_STORE = path.join(STATE, 'pristine_store');
export const STORE_MANIFEST = path.join(STATE, 'pdf_store.manifest.json');
export const START_DB = path.join(STATE, 'start.db');
export const START_JSON = path.join(STATE, 'start.json');
export const PRISTINE_JSON = path.join(STATE, 'pristine.json');
export const RUNNING = path.join(STATE, 'RUNNING');

export const API = (process.env.E2E_API_URL || 'http://localhost:8121').replace(/\/$/, '');
export const BASE = (process.env.E2E_BASE_URL || 'http://localhost:5201').replace(/\/$/, '');
export const PROJECT = 'demo-objektas_h';

// ── SQLite ─────────────────────────────────────────────────────────────────────────────────────────

function sqlite(args) {
  return execFileSync('sqlite3', args, { encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] });
}

const quoted = (p) => `'${p.replace(/'/g, "''")}'`;

/** Online backup of the live database into `to` (a consistent copy even while the backend writes). */
export function backupDb(to) {
  fs.mkdirSync(path.dirname(to), { recursive: true });
  fs.rmSync(to, { force: true });
  sqlite([DB, '.timeout 15000', `.backup ${quoted(to)}`]);
}

/** Replace the live database's content with `from` through the backup API, then check it. */
export function restoreDb(from) {
  if (!fs.existsSync(from)) throw new Error(`snapshot missing: ${from}`);
  sqlite([DB, '.timeout 15000', `.restore ${quoted(from)}`]);
  const check = sqlite([DB, '.timeout 15000', 'PRAGMA quick_check;']).trim();
  if (check !== 'ok') throw new Error(`database check after restore failed: ${check}`);
}

/**
 * Tables whose rows differ between the live database and `other` (rows in one and not the other, by
 * every column, blobs included). An empty list proves the restore: the live file holds exactly the
 * snapshot's content, table for table.
 */
export function diffDb(other) {
  const tables = sqlite([other, "SELECT name FROM sqlite_master WHERE type = 'table' AND name NOT LIKE 'sqlite_%' ORDER BY name;"])
    .split('\n').map((t) => t.trim()).filter(Boolean);
  const q = (t) => `"${t.replace(/"/g, '""')}"`;
  const sql = [`ATTACH ${quoted(other)} AS snap;`];
  for (const t of tables) {
    sql.push(`SELECT '${t}', (SELECT count(*) FROM (SELECT * FROM main.${q(t)} EXCEPT SELECT * FROM snap.${q(t)}))`
      + ` + (SELECT count(*) FROM (SELECT * FROM snap.${q(t)} EXCEPT SELECT * FROM main.${q(t)}));`);
  }
  const out = sqlite([DB, '.timeout 15000', '.separator |', ...sql]);
  return out.split('\n').map((l) => l.trim()).filter(Boolean)
    .map((l) => l.split('|')).filter(([, n]) => Number(n) !== 0).map(([t, n]) => `${t} (${n} rows)`);
}

// ── pdf_store ──────────────────────────────────────────────────────────────────────────────────────

function walk(dir, base = dir, out = new Map()) {
  if (!fs.existsSync(dir)) return out;
  for (const ent of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, ent.name);
    if (ent.isDirectory()) walk(full, base, out);
    else if (ent.isFile()) {
      const st = fs.statSync(full);
      out.set(path.relative(base, full), { size: st.size, mtimeMs: st.mtimeMs });
    }
  }
  return out;
}

export function snapshotStore() {
  fs.rmSync(PRISTINE_STORE, { recursive: true, force: true });
  if (fs.existsSync(STORE)) fs.cpSync(STORE, PRISTINE_STORE, { recursive: true });
  fs.writeFileSync(STORE_MANIFEST, JSON.stringify(Object.fromEntries(walk(STORE)), null, 1));
}

/** Put pdf_store back to the snapshot; returns what it changed (+copied back, -removed). */
export function restoreStore() {
  const want = new Map(Object.entries(JSON.parse(fs.readFileSync(STORE_MANIFEST, 'utf8'))));
  const have = walk(STORE);
  const changed = [];
  for (const rel of have.keys()) {
    if (!want.has(rel)) {
      fs.rmSync(path.join(STORE, rel), { force: true });
      changed.push(`-${rel}`);
    }
  }
  for (const [rel, st] of want) {
    const cur = have.get(rel);
    if (cur && cur.size === st.size && cur.mtimeMs === st.mtimeMs) continue;
    const dst = path.join(STORE, rel);
    fs.mkdirSync(path.dirname(dst), { recursive: true });
    fs.copyFileSync(path.join(PRISTINE_STORE, rel), dst);
    changed.push(`+${rel}`);
  }
  return changed;
}

// ── The project as the API serves it ───────────────────────────────────────────────────────────────

export async function api(pathname, init = {}) {
  const res = await fetch(`${API}${pathname}`, init);
  if (!res.ok) throw new Error(`${init.method || 'GET'} ${pathname} → ${res.status} ${await res.text().catch(() => '')}`);
  return res.json();
}

export const getProject = () => api(`/api/projects/${PROJECT}`);

export function roomsByNr(p) {
  return Object.fromEntries((p.patalpos || []).map((r) => [String(r.nr), r]));
}

export function rowQty(p, name) {
  const row = (p.darbu_sarasas || []).find((r) => r.pavadinimas === name);
  return row ? row.kiekis : undefined;
}

/** The numbers the guide talks about, plus what a writing step leaves behind. */
export function fingerprint(p) {
  const rooms = roomsByNr(p);
  const scales = Object.values(p.pageScalesDurable || {});
  return {
    updated_at: p.updated_at,
    rooms: (p.patalpos || []).length,
    a04: rooms['04']?.plotas_m2 ?? null,
    merged05: rooms['05']?._sujungta_i ?? null,
    kampai: p.v8_totals?.kampai_m ?? null,
    lubos: p.v8_totals?.bendras_plotas_m2 == null ? null : Math.round(p.v8_totals.bendras_plotas_m2 * 100) / 100,
    confirmedScales: scales.filter((s) => s && s.confirmed).length,
    measurements: (p.measurements || []).length,
    countTypes: (p.countTypes || []).length,
    revisions: (p._meta?.brezinio_leidimai || []).length,
    sheetOverrides: Object.keys(p.sheet_overrides || {}).length,
  };
}

/** The state the guide starts from (togal-v2 founder review: before he merged 04 + 05). */
export const START = { rooms: 11, a04: 26.31, merged05: null, kampai: 475.66, lubos: 143.27, confirmedScales: 0, measurements: 0, countTypes: 0, revisions: 0, sheetOverrides: 0 };

export function startMismatch(fp) {
  return Object.entries(START)
    .filter(([k, v]) => fp[k] !== v)
    .map(([k, v]) => `${k}: ${JSON.stringify(fp[k])} (want ${JSON.stringify(v)})`);
}

export function readJson(file) {
  return JSON.parse(fs.readFileSync(file, 'utf8'));
}
