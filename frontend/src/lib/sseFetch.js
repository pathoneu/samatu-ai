// sseFetch — POST + Server-Sent Events client.
// EventSource only supports GET; we need a multipart upload, so this parses
// the SSE wire format (`data: <json>\n\n`) directly off a fetch ReadableStream.
//
// Usage:
//   await postSse(url, formData, {
//     onEvent: (ev) => { ... },
//     signal: abortSignal,
//   });

export async function postSse(url, body, { onEvent, signal } = {}) {
  const res = await fetch(url, {
    method: 'POST',
    body,
    credentials: 'include',
    signal,
    headers: { 'Accept': 'text/event-stream' },
  });

  if (!res.ok) {
    let detail = `HTTP ${res.status}`;
    try {
      const errBody = await res.json();
      if (errBody?.detail) detail = errBody.detail;
    } catch { /* ignore */ }
    throw new Error(detail);
  }
  if (!res.body) throw new Error('No response body — SSE not supported by server');

  const reader = res.body.getReader();
  const decoder = new TextDecoder('utf-8');
  let buf = '';

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;
      buf += decoder.decode(value, { stream: true });

      // SSE event blocks separated by blank line.
      let sep;
      while ((sep = buf.indexOf('\n\n')) !== -1) {
        const block = buf.slice(0, sep);
        buf = buf.slice(sep + 2);

        // A block is `data: <json>` (possibly with leading comments — `:`) lines.
        const dataLines = block
          .split('\n')
          .filter(l => l.startsWith('data:'))
          .map(l => l.slice(5).trim());
        if (dataLines.length === 0) continue;
        const payload = dataLines.join('\n');
        try {
          const parsed = JSON.parse(payload);
          onEvent?.(parsed);
        } catch (e) {
          console.warn('[sseFetch] non-JSON event:', payload, e);
        }
      }
    }
  } finally {
    try { reader.releaseLock(); } catch { /* ignore */ }
  }
}
