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

  // Check existing session on mount
  useEffect(() => {
    apiCall('/api/auth/me')
      .then((d) => setUser(d.user))
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
  const USER_SCOPED_KEYS = ['samatu_projects', 'samatu_settings', 'samatu_price_lists'];

  const purgeLocalUserData = async () => {
    for (const key of USER_SCOPED_KEYS) {
      try { localStorage.removeItem(key); } catch { /* ignore */ }
    }
    try {
      const { resetPullCache } = await import('@/lib/projectStore');
      resetPullCache();
    } catch { /* ignore */ }
  };

  const login = async (email, password) => {
    const d = await apiCall('/api/auth/login', {
      method: 'POST',
      body: JSON.stringify({ email, password }),
    });
    await purgeLocalUserData();
    setUser(d.user);
    return d.user;
  };

  const register = async ({ email, password, name, company_name }) => {
    const d = await apiCall('/api/auth/register', {
      method: 'POST',
      body: JSON.stringify({ email, password, name, company_name }),
    });
    await purgeLocalUserData();
    setUser(d.user);
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
