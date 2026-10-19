/**
 * pdfStore — PDF failų saugykla.
 *
 * IndexedDB veikia kaip GREITAS lokalus kešas, o tikroji DURABLI kopija laikoma
 * backende (object storage / R2). Todėl išvalius naršyklės kešą, persijungus į
 * kitą įrenginį ar atidarius bendrinimo nuorodą brėžinys nebepradingsta —
 * getPdfBlob automatiškai parsisiunčia jį iš backendo ir vėl įkešuoja.
 * (2026-06-21 durability track.)
 *
 * API:
 *   await savePdf(projectId, file)             // IndexedDB kešas
 *   await uploadPdfToBackend(projectId, file)  // durabli kopija (fire-and-forget)
 *   const url = await getPdfUrl(projectId)     // kešas → backend fallback → blob URL
 *   await deletePdf(projectId)
 */

import { API_BASE } from './apiBase.js';   // the .js lets node's test runner resolve it

const DB_NAME = 'samatu_pdfs';
const STORE = 'pdfs';
const DB_VERSION = 1;

function openDb() {
  return new Promise((resolve, reject) => {
    const req = indexedDB.open(DB_NAME, DB_VERSION);
    req.onupgradeneeded = () => {
      const db = req.result;
      if (!db.objectStoreNames.contains(STORE)) {
        db.createObjectStore(STORE);
      }
    };
    req.onsuccess = () => resolve(req.result);
    req.onerror = () => reject(req.error);
  });
}

export async function savePdf(projectId, file) {
  if (!file) return;
  const db = await openDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE, 'readwrite');
    tx.objectStore(STORE).put(file, projectId);
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
}

async function getPdfFromIdb(projectId) {
  const db = await openDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE, 'readonly');
    const req = tx.objectStore(STORE).get(projectId);
    req.onsuccess = () => resolve(req.result || null);
    req.onerror = () => reject(req.error);
  });
}

/** POST the PDF to the backend so it survives a cache clear / device switch.
 *  Fire-and-forget — best effort; never blocks the upload flow. */
export async function uploadPdfToBackend(projectId, file) {
  if (!projectId || !file) return false;
  try {
    const fd = new FormData();
    fd.append('pdf_file', file, 'drawing.pdf');
    const res = await fetch(`${API_BASE}/api/projects/${projectId}/pdf`, {
      method: 'POST', credentials: 'include', body: fd,
    });
    return res.ok;
  } catch {
    return false;
  }
}

async function fetchPdfFromBackend(projectId) {
  try {
    const res = await fetch(`${API_BASE}/api/projects/${projectId}/pdf`, { credentials: 'include' });
    if (!res.ok) return null;
    return await res.blob();
  } catch {
    return null;
  }
}

async function loadPdfBlob(projectId) {
  // 1) fast browser cache
  const cached = await getPdfFromIdb(projectId);
  if (cached) return cached;
  // 2) durable backend fallback (cache cleared, new device, share link)
  const remote = await fetchPdfFromBackend(projectId);
  if (remote) {
    try { await savePdf(projectId, remote); } catch { /* re-cache best-effort */ }
    return remote;
  }
  return null;
}

// The viewer, the thumbnail rail and the room list all ask for the PDF while
// the project mounts. Before the first answer lands in IndexedDB every one of
// them missed the cache and downloaded the whole drawing — three identical
// multi-MB fetches on every first open (seen 2026-09-15). One in-flight
// promise per project; it is dropped once settled so a later open re-checks
// the cache as before.
const inflight = new Map();

export function getPdfBlob(projectId, { load = loadPdfBlob } = {}) {
  const key = String(projectId);
  const pending = inflight.get(key);
  if (pending) return pending;
  const p = Promise.resolve()
    .then(() => load(projectId))
    .finally(() => { if (inflight.get(key) === p) inflight.delete(key); });
  inflight.set(key, p);
  return p;
}

export async function getPdfUrl(projectId) {
  const blob = await getPdfBlob(projectId);
  if (!blob) return null;
  return URL.createObjectURL(blob);
}

/**
 * Every cached drawing in this browser — on logout and on a user switch
 * (audit backend-security-15): the previous person's PDFs must not stay
 * readable to the next one. Clears the store rather than deleting the
 * database, which another open tab would block.
 */
export async function clearAllPdfs() {
  if (typeof indexedDB === 'undefined') return;
  const db = await openDb();
  await new Promise((resolve, reject) => {
    const tx = db.transaction(STORE, 'readwrite');
    tx.objectStore(STORE).clear();
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
  db.close();
}

export async function deletePdf(projectId) {
  const db = await openDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE, 'readwrite');
    tx.objectStore(STORE).delete(projectId);
    tx.oncomplete = () => resolve();
    tx.onerror = () => reject(tx.error);
  });
}
