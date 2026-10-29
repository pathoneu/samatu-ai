/**
 * Before the run: the servers are up, the backend has its auth wall off, the pristine snapshot is taken,
 * and the guide's start state is derived from it into .state/start.db (each test restores that).
 */
import fs from 'node:fs';
import {
  API, BASE, DB, PROJECT, STATE, PRISTINE_DB, PRISTINE_JSON, START_DB, START_JSON, RUNNING, STORE_MANIFEST,
  api, backupDb, fingerprint, getProject, restoreDb, restoreStore, snapshotStore, startMismatch,
} from './state.js';

async function reachable(url) {
  try {
    const res = await fetch(url);
    return res.ok;
  } catch {
    return false;
  }
}

export default async function globalSetup() {
  if (!fs.existsSync(DB)) throw new Error(`No database at ${DB} — copy backend/data/samatu.db into this checkout (docs/DEVELOPING.md › E2E smoke).`);
  if (!(await reachable(`${API}/health`))) {
    throw new Error(`Backend not reachable at ${API}. Start it first:\n  cd backend && SAMATU_AUTH_DISABLED=1 ../venv/bin/uvicorn main:app --port ${new URL(API).port}`);
  }
  if (!(await reachable(BASE))) {
    throw new Error(`Frontend not reachable at ${BASE}. Start it first:\n  cd frontend && VITE_BACKEND_URL=${API} npm run dev -- --port ${new URL(BASE).port}`);
  }
  const probe = await fetch(`${API}/api/projects/${PROJECT}`);
  if (probe.status === 401) throw new Error('The backend asks for a login — start it with SAMATU_AUTH_DISABLED=1.');
  if (!probe.ok) throw new Error(`GET /api/projects/${PROJECT} → ${probe.status}: the demo project is missing from ${DB}.`);

  fs.mkdirSync(STATE, { recursive: true });
  // A run that died before its teardown left its writes in the database: put that run's pristine back first.
  if (fs.existsSync(RUNNING) && fs.existsSync(PRISTINE_DB) && fs.existsSync(STORE_MANIFEST)) {
    restoreDb(PRISTINE_DB);
    const changed = restoreStore();
    console.log(`[e2e] the previous run did not finish — its pristine snapshot is restored first (pdf_store: ${changed.length} file(s)).`);
  }

  backupDb(PRISTINE_DB);
  snapshotStore();
  const pristine = fingerprint(await getProject());
  fs.writeFileSync(PRISTINE_JSON, JSON.stringify(pristine, null, 1));
  fs.writeFileSync(RUNNING, new Date().toISOString());

  // The start state: the newest stored version of the project that is the guide's starting point
  // (04 not yet merged with 05, no sheet scale confirmed). E2E_START_VERSION picks one by id.
  const wanted = process.env.E2E_START_VERSION || null;
  const { versions } = await api(`/api/projects/${PROJECT}/versions`);
  let chosen = null;
  for (const v of versions) {
    if (wanted && String(v.id) !== String(wanted)) continue;
    const full = await api(`/api/projects/${PROJECT}/versions/${v.id}`);
    if (wanted || startMismatch(fingerprint(full.data)).length === 0) {
      chosen = v;
      break;
    }
  }
  if (!chosen) {
    throw new Error(`No stored version of ${PROJECT} is the guide's start state (04 = 26,31 m², 05 not merged, kampai 475,66 m, `
      + 'lubos 143,27 m², no confirmed scale, no measurements). Copy a fresh backend/data/samatu.db from the main checkout, '
      + 'or name one with E2E_START_VERSION=<id>.');
  }
  // Only call /restore when it would actually move the project — restoring to the version the project is
  // already on creates a duplicate "Prieš grąžinant" version with the same content hash, and both end up
  // marked `dabartine=true` (two chips → both „Grąžinti" disabled). The B6 drawer test used to pick
  // listitem(1) as the first restorable row; after the duplicate it was still dabartine. 2026-10-29.
  const needsRestore = chosen.dabartine !== true;
  if (needsRestore) await api(`/api/projects/${PROJECT}/versions/${chosen.id}/restore`, { method: 'POST' });
  const start = fingerprint(await getProject());
  const bad = startMismatch(start);
  if (bad.length) {
    restoreDb(PRISTINE_DB);
    throw new Error(`Version ${chosen.id} restored, but it is not the guide's start state: ${bad.join('; ')}`);
  }
  backupDb(START_DB);
  fs.writeFileSync(START_JSON, JSON.stringify({ version: chosen.id, version_created_at: chosen.created_at, version_saltinis: chosen.saltinis, ...start }, null, 1));
  console.log(`[e2e] pristine snapshot taken (${PROJECT} updated ${pristine.updated_at}); start state = version ${chosen.id} (${chosen.created_at}).`);
}
