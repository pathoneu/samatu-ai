/**
 * Status helpers for the admin cockpit (2026-10-05). Pure — no React, no
 * fetch — so node:test pins them: the verdict on the nightly database backup
 * (audit data-ops-infra-9) and whether a directory row is a deleted account.
 *
 * Input: `health.backup` from GET /api/admin/v2/system-health —
 *   { enabled, last_ok_at, last_key, last_size, last_error, last_error_at,
 *     last_attempt: {at, ok, key, size, error} | null,
 *     last_prune: {at, keep_days, deleted, kept, error} | null,
 *     keep_days, keep_newest, stale_after_hours }
 * The outcome is persisted server-side, so a deploy no longer blanks it.
 *
 * Red ('bad') when there is no good snapshot, when the last good one is older
 * than stale_after_hours (26 h — a nightly job that ran a little late is still
 * fine), when the latest attempt failed, or when the nightly backup is off.
 */

export const BACKUP_STALE_AFTER_HOURS = 26;

const HOUR_MS = 3600 * 1000;

/**
 * @returns {{tone: 'ok'|'bad', reason: 'ok'|'off'|'missing'|'stale'|'failed',
 *            ageHours: number|null, staleAfterHours: number,
 *            lastAttemptFailed: boolean, error: string|null}}
 */
export function backupStatus(backup, nowMs = Date.now()) {
  const b = backup && typeof backup === 'object' ? backup : {};
  const limit = Number(b.stale_after_hours) > 0 ? Number(b.stale_after_hours) : BACKUP_STALE_AFTER_HOURS;
  const okMs = b.last_ok_at ? Date.parse(b.last_ok_at) : NaN;
  const ageHours = Number.isFinite(okMs) ? Math.max(0, (nowMs - okMs) / HOUR_MS) : null;
  const attempt = b.last_attempt && typeof b.last_attempt === 'object' ? b.last_attempt : null;
  const lastAttemptFailed = attempt ? attempt.ok === false : Boolean(b.last_error);
  const error = lastAttemptFailed ? (attempt?.error || b.last_error || null) : null;

  let reason = 'ok';
  if (!b.enabled) reason = 'off';
  else if (ageHours === null) reason = 'missing';
  else if (ageHours > limit) reason = 'stale';
  else if (lastAttemptFailed) reason = 'failed';

  return {
    tone: reason === 'ok' ? 'ok' : 'bad',
    reason,
    ageHours,
    staleAfterHours: limit,
    lastAttemptFailed,
    error,
  };
}

/** A deleted account's tombstone row in the admin user directory. */
export function isDeletedAccount(user) {
  return Boolean(user && user.deleted_at);
}
