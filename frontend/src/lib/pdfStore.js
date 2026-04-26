/**
 * pdfStore — IndexedDB storage'as PDF failams.
 *
 * localStorage neegzistuoja didelius PDF failus (>5MB ribota), todėl
 * naudojam IndexedDB. Per projekto ID saugom Blob, atveriam per blob URL.
 *
 * API:
 *   await savePdf(projectId, file)         // file: File | Blob
 *   const url = await getPdfUrl(projectId) // grąžina blob: URL (sukuriamas runtime)
 *   await deletePdf(projectId)
 */

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

export async function getPdfBlob(projectId) {
  const db = await openDb();
  return new Promise((resolve, reject) => {
    const tx = db.transaction(STORE, 'readonly');
    const req = tx.objectStore(STORE).get(projectId);
    req.onsuccess = () => resolve(req.result || null);
    req.onerror = () => reject(req.error);
  });
}

export async function getPdfUrl(projectId) {
  const blob = await getPdfBlob(projectId);
  if (!blob) return null;
  return URL.createObjectURL(blob);
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
