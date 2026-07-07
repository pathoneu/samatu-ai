/**
 * paywall — recognize backend billing refusals on project creation (Phase 7).
 *
 * The interior extraction endpoints answer with:
 *   402 { error: "quota_exceeded" | "trial_used", message }
 *   403 { error: "company_code_required", message }
 *
 * Both the streaming (postSse) and non-streaming (detectAndExtract) paths
 * carry the status + parsed body on the thrown Error (see sseFetch.js), or we
 * synthesize an object from the raw {status, json}. This helper normalizes both
 * into { reason, message } or null when it isn't a paywall response.
 */

const PAYWALL_REASONS = new Set(['quota_exceeded', 'trial_used', 'company_code_required']);

/**
 * @param {{ status?: number, body?: any } | Error} errLike
 * @returns {{ reason: 'quota_exceeded'|'trial_used'|'company_code_required', message?: string } | null}
 */
export function detectPaywall(errLike) {
  if (!errLike) return null;
  const status = errLike.status;
  const body = errLike.body || null;
  if (status !== 402 && status !== 403) return null;
  const reason = body?.error;
  if (!reason || !PAYWALL_REASONS.has(reason)) return null;
  return { reason, message: body?.message };
}

/** Build a paywall-carrying Error from a raw {status, json} (non-SSE path). */
export function paywallErrorFrom(status, json) {
  const err = new Error(json?.message || json?.error || `HTTP ${status}`);
  err.status = status;
  err.body = json;
  return err;
}
