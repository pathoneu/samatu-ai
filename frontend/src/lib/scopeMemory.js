/**
 * scopeMemory — the contractor's last project-level „ką skaičiuoti" choices,
 * kept in this browser so the upload screen can pre-select a habit after
 * three identical projects (lib/scope.js `learnedDefaults`). Browser storage
 * only: it may be empty or unavailable, and the page must work without it.
 */

import { learnedDefaults, rememberScope } from './scope.js';

export const SCOPE_HISTORY_KEY = 'samatu_apimtis_history';

export function loadScopeHistory() {
  try {
    const raw = localStorage.getItem(SCOPE_HISTORY_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

export function saveScopeHistory(history) {
  try {
    localStorage.setItem(SCOPE_HISTORY_KEY, JSON.stringify(Array.isArray(history) ? history : []));
  } catch {
    // storage blocked or full — the choice still applies to this project
  }
}

/** Append this project's choices to the remembered history. */
export function rememberProjectScope(scope) {
  saveScopeHistory(rememberScope(loadScopeHistory(), scope));
}

/** What the upload screen should pre-select, and which keys came from memory. */
export function remembered() {
  return learnedDefaults(loadScopeHistory());
}
