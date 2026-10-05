/**
 * The admin health panel's backup verdict — red when the last good snapshot is
 * missing or older than 26 h, when the latest attempt failed, or when the
 * nightly backup is off (audit data-ops-infra-9, 2026-10-05).
 */
import test from 'node:test';
import assert from 'node:assert/strict';
import { backupStatus, isDeletedAccount, BACKUP_STALE_AFTER_HOURS } from './adminStatus.js';

const NOW = Date.parse('2026-10-05T12:00:00Z');
const hoursAgo = (h) => new Date(NOW - h * 3600 * 1000).toISOString();
const good = (h, extra = {}) => ({
  enabled: true,
  last_ok_at: hoursAgo(h),
  last_key: 'backups/samatu-20261005T031500Z.db',
  last_size: 4096,
  last_attempt: { at: hoursAgo(h), ok: true, key: 'backups/samatu-20261005T031500Z.db', size: 4096, error: null },
  stale_after_hours: 26,
  ...extra,
});

test('a good snapshot inside 26 h is green', () => {
  const s = backupStatus(good(9), NOW);
  assert.equal(s.tone, 'ok');
  assert.equal(s.reason, 'ok');
  assert.equal(Math.round(s.ageHours), 9);
  assert.equal(s.error, null);
});

test('26 h is still green; a minute past is red (stale)', () => {
  assert.equal(backupStatus(good(26), NOW).tone, 'ok');
  const late = backupStatus(good(26 + 1 / 60), NOW);
  assert.equal(late.tone, 'bad');
  assert.equal(late.reason, 'stale');
});

test('no good snapshot at all is red (missing)', () => {
  const s = backupStatus({ enabled: true, last_ok_at: null, last_attempt: null }, NOW);
  assert.deepEqual([s.tone, s.reason, s.ageHours], ['bad', 'missing', null]);
});

test('an empty or absent payload is red, never green', () => {
  for (const payload of [undefined, null, {}, 'x']) {
    assert.equal(backupStatus(payload, NOW).tone, 'bad');
  }
});

test('the nightly backup switched off is red even with a recent snapshot', () => {
  const s = backupStatus(good(2, { enabled: false }), NOW);
  assert.deepEqual([s.tone, s.reason], ['bad', 'off']);
});

test('a failed latest attempt is red and carries its error', () => {
  const s = backupStatus(good(20, {
    last_error: 'BackupError: snapshot failed PRAGMA integrity_check',
    last_attempt: { at: hoursAgo(1), ok: false, key: 'backups/samatu-x.db', size: 10, error: 'BackupError: snapshot failed PRAGMA integrity_check' },
  }), NOW);
  assert.deepEqual([s.tone, s.reason, s.lastAttemptFailed], ['bad', 'failed', true]);
  assert.match(s.error, /integrity_check/);
  assert.equal(Math.round(s.ageHours), 20);        // the last GOOD one still counts
});

test('stale wins over failed: the reason names the older problem', () => {
  const s = backupStatus(good(40, { last_attempt: { at: hoursAgo(1), ok: false, error: 'boom' } }), NOW);
  assert.equal(s.reason, 'stale');
  assert.equal(s.error, 'boom');
});

test('a payload from before last_attempt existed still reads last_error', () => {
  const s = backupStatus({ enabled: true, last_ok_at: hoursAgo(3), last_error: 'RuntimeError: R2 put failed' }, NOW);
  assert.deepEqual([s.tone, s.reason, s.error], ['bad', 'failed', 'RuntimeError: R2 put failed']);
});

test('the threshold comes from the server, 26 h when it says nothing', () => {
  assert.equal(BACKUP_STALE_AFTER_HOURS, 26);
  assert.equal(backupStatus(good(30, { stale_after_hours: 48 }), NOW).tone, 'ok');
  const noLimit = good(30);
  delete noLimit.stale_after_hours;
  assert.equal(backupStatus(noLimit, NOW).reason, 'stale');
});

test('an unparseable timestamp is treated as no snapshot', () => {
  const s = backupStatus({ enabled: true, last_ok_at: 'vakar' }, NOW);
  assert.deepEqual([s.tone, s.reason], ['bad', 'missing']);
});

test('isDeletedAccount: only a row with deleted_at is a tombstone', () => {
  assert.equal(isDeletedAccount({ deleted_at: '2026-10-05T09:00:00Z', is_active: 0 }), true);
  assert.equal(isDeletedAccount({ deleted_at: null, is_active: 0 }), false);
  assert.equal(isDeletedAccount({ is_active: 1 }), false);
  assert.equal(isDeletedAccount(null), false);
});
