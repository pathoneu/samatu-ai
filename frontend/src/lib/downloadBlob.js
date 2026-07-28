/**
 * triggerDownload — the ONE correct way to hand a Blob to the browser.
 *
 * 2026-07-28 audit. The export paths each rolled their own anchor and got two
 * details wrong, both of which produce a silently missing file rather than an
 * error the user can act on:
 *
 *  1. The <a> was never appended to the document. Firefox (and Safari in some
 *     configurations) ignores a click() on a detached anchor, so "Eksportuoti"
 *     did nothing at all — no download, no message.
 *  2. revokeObjectURL ran SYNCHRONOUSLY on the next line. The download is
 *     started asynchronously, so on a slow machine the URL could be revoked
 *     before the browser had read the blob → a truncated or empty .xlsx.
 *
 * The correct idiom already existed at TakeoffViewer.jsx (append → click →
 * remove → revoke on a timer); this is that idiom, in one place.
 */
export function triggerDownload(blob, filename) {
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  a.remove();
  // Give the browser time to start reading the blob before we drop the URL.
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
