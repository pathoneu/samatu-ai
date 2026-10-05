// Account deletion from Settings (2026-10-05): the call, the confirmation the
// button waits for, and the drawings this browser cached for the account.
import test from 'node:test';
import assert from 'node:assert/strict';
import { confirmMatches, deleteAccount, forgetCachedDrawings } from './accountApi.js';

function fakeFetch(status, body, calls = []) {
  return async (url, opts) => {
    calls.push({ url, opts });
    return {
      ok: status >= 200 && status < 300,
      status,
      json: async () => {
        if (body === undefined) throw new Error('no json');
        return body;
      },
    };
  };
}

test('confirmMatches: the account email in any case, spaces around ignored', () => {
  assert.equal(confirmMatches('  Rimas@Statyba.LT ', 'rimas@statyba.lt'), true);
  assert.equal(confirmMatches('rimas@statyba.lt', 'rimas@statyba.lt'), true);
  assert.equal(confirmMatches('rimas@statyba.l', 'rimas@statyba.lt'), false);
  assert.equal(confirmMatches('kitas@statyba.lt', 'rimas@statyba.lt'), false);
  // No account email known yet → never a match, even for an empty field.
  assert.equal(confirmMatches('', ''), false);
  assert.equal(confirmMatches('', undefined), false);
});

test('deleteAccount posts the trimmed confirmation with the session cookie', async () => {
  const calls = [];
  const out = await deleteAccount('  rimas@statyba.lt ',
    { fetchImpl: fakeFetch(200, { deleted_projects: 3 }, calls) });
  assert.deepEqual(out, { deleted_projects: 3 });
  assert.equal(calls.length, 1);
  assert.match(calls[0].url, /\/api\/account\/delete$/);
  assert.equal(calls[0].opts.method, 'POST');
  assert.equal(calls[0].opts.credentials, 'include');
  assert.deepEqual(JSON.parse(calls[0].opts.body), { confirm: 'rimas@statyba.lt' });
});

test('deleteAccount hands the server\'s plain reason through', async () => {
  const reason = 'Įrašytas el. paštas nesutampa su šios paskyros el. paštu. Paskyra neištrinta.';
  await assert.rejects(
    () => deleteAccount('x@y.lt', { fetchImpl: fakeFetch(400, { detail: reason }) }),
    (err) => err.status === 400 && err.detail === reason && err.message === reason,
  );
});

test('deleteAccount: no words from the server → no detail (the page says it itself)', async () => {
  // pydantic-style list detail, an HTML error page, a dropped connection
  await assert.rejects(
    () => deleteAccount('x@y.lt', { fetchImpl: fakeFetch(422, { detail: [{ msg: 'x' }] }) }),
    (err) => err.status === 422 && err.detail === null,
  );
  await assert.rejects(
    () => deleteAccount('x@y.lt', { fetchImpl: fakeFetch(502, undefined) }),
    (err) => err.status === 502 && err.detail === null,
  );
  await assert.rejects(
    () => deleteAccount('x@y.lt', { fetchImpl: async () => { throw new TypeError('Failed to fetch'); } }),
    (err) => err.status === 0 && err.detail === null,
  );
});

test('forgetCachedDrawings drops each cached drawing once and survives refusals', async () => {
  const dropped = [];
  const n = await forgetCachedDrawings(['p-1', 'p-2', 'p-1', '', null, 'p-3'], {
    deletePdfImpl: async (id) => {
      if (id === 'p-2') throw new Error('blocked');
      dropped.push(id);
    },
  });
  assert.deepEqual(dropped, ['p-1', 'p-3']);
  assert.equal(n, 2);
});

test('forgetCachedDrawings without IndexedDB (node) changes nothing and does not throw', async () => {
  assert.equal(await forgetCachedDrawings(['p-1']), 0);
  assert.equal(await forgetCachedDrawings([]), 0);
});
