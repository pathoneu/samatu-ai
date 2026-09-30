/**
 * AuthContext — login state + auth helpers (Phase 13).
 *
 * Provides: user, login, register, logout, isLoading, isAdmin.
 * Wraps the app via <AuthProvider>. Pulls /api/auth/me on mount to detect
 * existing session cookie. Login + register call backend, store user object.
 */

import React, { createContext, useContext, useEffect, useState } from 'react';
import { sanitizeHeaders } from '@/lib/safeHeaders';
import { API_BASE as API } from './apiBase';
import { takeSignInHint } from './signInHint';

const AuthCtx = createContext({
  user: null,
  isLoading: true,
  isAdmin: false,
  login: async () => {},
  register: async () => {},
  logout: async () => {},
});

async function apiCall(path, opts = {}) {
  // Merge order: defaults → caller opts → headers (caller can't override
  // credentials accidentally, headers are sanitized & merged not replaced).
  const { headers: extraHeaders, ...restOpts } = opts;
  const res = await fetch(`${API}${path}`, {
    credentials: 'include',  // CRITICAL: send session cookie
    ...restOpts,
    headers: sanitizeHeaders({
      'Content-Type': 'application/json',
      ...(extraHeaders || {}),
    }),
  });
  let body;
  try { body = await res.json(); } catch { body = null; }
  if (!res.ok) {
    const msg = body?.detail || `HTTP ${res.status}`;
    const err = new Error(msg);
    err.status = res.status;
    err.body = body;
    throw err;
  }
  return body;
}

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [isLoading, setIsLoading] = useState(true);

  // Check existing session on mount. This is also where a Google sign-in
  // arrives (it finishes through a server redirect, so login() never ran):
  // a cache left by another account is purged before the user is set, i.e.
  // before any page can read it (2026-09-30).
  useEffect(() => {
    apiCall('/api/auth/me')
      .then(async (d) => {
        const signIn = takeSignInHint();
        if (d.user) await claimCacheFor(d.user.id, { signIn });
        setUser(d.user);
        if (d.user) pullUserSettings(d.user.id);
      })
      .catch(() => setUser(null))
      .finally(() => setIsLoading(false));
  }, []);

  // Security (2026-06-19 hunt): a login/register is a USER SWITCH. Purge the
  // previous user's cached projects + the module-level pull guard so the new
  // user's Dashboard actually fetches their OWN data — otherwise, on a shared
  // browser or after a silent session expiry, the next person sees (and can
  // export) the prior user's projects from localStorage. Mirrors logout().
  // 2026-07-27 audit: samatu_settings (company name, logo, default prices) and
  // samatu_price_lists (the contractor's own kainynai) are localStorage-only —
  // they used to survive a user switch, so the next person on a shared browser
  // inherited them and could apply another company's prices to their sąmata.
  // The two owner markers go with them (2026-09-30): a marker left behind would
  // make the next session's restore purge a cache that is already its own.
  const USER_SCOPED_KEYS = ['samatu_projects', 'samatu_settings', 'samatu_price_lists',
    'samatu_settings_owner', 'samatu_cache_owner'];

  const purgeLocalUserData = async () => {
    for (const key of USER_SCOPED_KEYS) {
      try { localStorage.removeItem(key); } catch { /* ignore */ }
    }
    try {
      const { resetPullCache } = await import('@/lib/projectStore');
      resetPullCache();
    } catch { /* ignore */ }
  };

  // Whose cache this browser holds — see claimLocalCache in projectStore. If
  // the store cannot be loaded there is no telling, so purge.
  const claimCacheFor = async (userId, opts) => {
    try {
      const { claimLocalCache } = await import('@/lib/projectStore');
      claimLocalCache(userId, opts);
    } catch {
      await purgeLocalUserData();
    }
  };

  // Company details + logo live on the server per user since 2026-09-29; the
  // purge above only drops this browser's cached copy. Refill it after a login
  // or session restore. Not awaited: the exports and the Settings page await
  // the same pull before they read the cache.
  const pullUserSettings = async (userId) => {
    try {
      const { pullSettingsFromBackend } = await import('@/lib/projectStore');
      await pullSettingsFromBackend(userId);
    } catch { /* the next reader retries the pull */ }
  };

  const login = async (email, password) => {
    const d = await apiCall('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    });
    await purgeLocalUserData();
    if (d.user) await claimCacheFor(d.user.id);
    setUser(d.user);
    if (d.user) pullUserSettings(d.user.id);
    return d.user;
  };

  const register = async ({ email, password, name, company_name }) => {
    const d = await apiCall('/api/auth/register', {
      method: 'POST',
      body: JSON.stringify({ email, password, name, company_name }),
    });
    await purgeLocalUserData();
    if (d.user) await claimCacheFor(d.user.id);
    setUser(d.user);
    if (d.user) pullUserSettings(d.user.id);
    return { user: d.user, isFirstAdmin: d.is_first_admin };
  };

  const logout = async () => {
    try { await apiCall('/api/auth/logout', { method: 'POST' }); } catch {}
    setUser(null);
    // Same purge as login/register (projects + settings + price lists) and the
    // pull cache, so the next user's first request actually fetches from the
    // backend instead of reusing the previous user's pull.
    await purgeLocalUserData();
  };

  const value = {
    user,
    isLoading,
    isAdmin: !!user?.is_admin,
    login,
    register,
    logout,
  };

  return <AuthCtx.Provider value={value}>{children}</AuthCtx.Provider>;
}

export function useAuth() {
  return useContext(AuthCtx);
}
