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
    let errBody = null;
    try {
      errBody = await res.json();
      // Prefer a paywall `message`, then FastAPI `detail`.
      if (errBody?.message) detail = errBody.message;
      else if (errBody?.detail) detail = errBody.detail;
    } catch { /* ignore */ }
    // Preserve status + parsed body so callers can branch on paywall codes
    // (402 quota_exceeded/trial_used, 403 company_code_required).
    const err = new Error(detail);
    err.status = res.status;
    err.body = errBody;
    throw err;
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
        if (dataLines.length === 0) {
          // Comment-only block (the server sends `: heartbeat` every 10 s during
          // slow phases like pass-1). Surface it as a heartbeat event so a
          // client-side stall/idle detector counts it as activity — otherwise a
          // long silent phase looks "hung" even though the extraction is alive.
          if (block.trim()) onEvent?.({ event: 'heartbeat' });
          continue;
        }
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
