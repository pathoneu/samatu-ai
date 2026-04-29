// safeHeaders — guard against `Failed to construct 'Headers': Invalid name`.
//
// `fetch()` crashes when a header NAME is empty, contains whitespace, colons,
// or non-token chars (RFC 7230). When headers come from spread-merge of
// caller-supplied opts, a single bad key crashes the whole request — and
// because window.onerror catches it, downstream side effects (re-renders,
// retry loops) can amplify it 10× per page load.
//
// Use sanitizeHeaders() anywhere a header object is built from a dynamic
// source. Cheap defense.

// RFC 7230 token chars: ALPHA/DIGIT + !#$%&'*+-.^_`|~
const TOKEN_CHARS_RE = /^[!#$%&'*+\-.^_`|~0-9A-Za-z]+$/;

export function sanitizeHeaders(input) {
  const out = {};
  if (!input || typeof input !== 'object') return out;
  for (const [k, v] of Object.entries(input)) {
    if (typeof k !== 'string' || k.length === 0) continue;
    if (!TOKEN_CHARS_RE.test(k)) continue;
    if (v == null) continue;
    out[k] = String(v);
  }
  return out;
}
