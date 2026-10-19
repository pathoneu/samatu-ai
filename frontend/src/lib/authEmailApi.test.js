import { test } from 'node:test';
import assert from 'node:assert/strict';
import { detailMessage, tokenFromSearch, forgotPassword, resetPassword } from './authEmailApi.js';

test('detailMessage reads a string detail, a {message} detail and a top-level message', () => {
  assert.equal(detailMessage({ detail: 'Nuoroda nebegalioja.' }), 'Nuoroda nebegalioja.');
  assert.equal(detailMessage({ detail: { error: 'email_not_verified', message: 'Patvirtinkite.' } }), 'Patvirtinkite.');
  assert.equal(detailMessage({ message: 'Išsiuntėme.' }), 'Išsiuntėme.');
  assert.equal(detailMessage(null), '');
  assert.equal(detailMessage({ detail: [{ msg: 'x' }] }), '');
});

test('tokenFromSearch takes ?token= and nothing else', () => {
  assert.equal(tokenFromSearch('?token=abc-_123'), 'abc-_123');
  assert.equal(tokenFromSearch('?x=1'), '');
  assert.equal(tokenFromSearch(''), '');
});

test('calls post the right body and never throw on a network failure', async () => {
  const seen = [];
  const fake = async (url, opts) => {
    seen.push([url, JSON.parse(opts.body)]);
    return { ok: true, status: 200, json: async () => ({ status: 'ok', message: 'Išsiuntėme.' }) };
  };
  const r = await forgotPassword('rimas@x.lt', fake);
  assert.equal(r.ok, true);
  assert.equal(r.message, 'Išsiuntėme.');
  await resetPassword('tok', 'naujas-slapt', fake);
  assert.match(seen[0][0], /\/api\/auth\/forgot-password$/);
  assert.deepEqual(seen[1][1], { token: 'tok', new_password: 'naujas-slapt' });

  const down = await forgotPassword('rimas@x.lt', async () => { throw new Error('offline'); });
  assert.deepEqual(down, { ok: false, status: 0, message: '', data: null });
});
