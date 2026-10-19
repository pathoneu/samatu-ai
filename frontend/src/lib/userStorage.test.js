import { test } from 'node:test';
import assert from 'node:assert/strict';
import { isUserScopedKey, userScopedKeysIn } from './userStorage.js';

test('project data leaves with the person; UI preferences stay', () => {
  for (const k of ['samatu_projects', 'samatu_settings', 'samatu_takeoff_abc-123',
    'samatu_export_skyriai_abc', 'samatu_reread_run:abc', 'samatu_kainynas_pending:abc',
    'pathon_free_reread_later_abc', 'samatu_server_versions']) {
    assert.equal(isUserScopedKey(k), true, k);
  }
  for (const k of ['samatu_panel_width', 'pathon_lang', 'pathon_cookie_consent',
    'samatu_viewer_walls', 'samatu_onboarding_done', null]) {
    assert.equal(isUserScopedKey(k), false, String(k));
  }
});

test('userScopedKeysIn walks a Storage-like object', () => {
  const data = { samatu_projects: '[]', samatu_takeoff_x: '{}', pathon_lang: 'lt' };
  const keys = Object.keys(data);
  const storage = { length: keys.length, key: (i) => keys[i] };
  assert.deepEqual(userScopedKeysIn(storage).sort(), ['samatu_projects', 'samatu_takeoff_x']);
});
