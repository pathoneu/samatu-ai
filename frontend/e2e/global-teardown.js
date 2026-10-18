/** After the run: the database and pdf_store are put back exactly as the run found them. */
import fs from 'node:fs';
import { PRISTINE_DB, PRISTINE_JSON, RUNNING, diffDb, fingerprint, getProject, readJson, restoreDb, restoreStore } from './state.js';

export default async function globalTeardown() {
  if (!fs.existsSync(PRISTINE_DB)) return;
  restoreDb(PRISTINE_DB);
  const changed = restoreStore();
  const tables = diffDb(PRISTINE_DB);
  if (tables.length) throw new Error(`[e2e] the database differs from the pristine snapshot after the restore: ${tables.join(', ')} — the snapshot is kept in frontend/e2e/.state/`);
  const want = readJson(PRISTINE_JSON);
  const got = fingerprint(await getProject());
  const diff = Object.keys(want).filter((k) => JSON.stringify(want[k]) !== JSON.stringify(got[k]));
  if (diff.length) {
    throw new Error(`[e2e] the database was restored but the project differs from the pristine snapshot in: ${diff.join(', ')} — the snapshot is kept in frontend/e2e/.state/`);
  }
  fs.rmSync(RUNNING, { force: true });
  console.log(`[e2e] database restored to the pristine snapshot (every table identical) and pdf_store (${changed.length ? changed.join(' ') : 'unchanged'}).`);
}
