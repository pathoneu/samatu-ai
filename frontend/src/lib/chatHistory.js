// chatHistory — Pokalbis keeps its history per project across reloads (Pathon v3 W5-C, C12 F-chat-history).
// GET / PUT /api/projects/{id}/chat-history (api/chat_history.py). The browser holds the list; every change
// after the first load is saved (debounced by the caller). Pure helpers + the two calls.

import { API_BASE } from './apiBase.js';

const KEEP = ['role', 'text', 'isError', 'vote', 'question', 'given'];

/** What is stored: known keys only, no empty texts, the newest 100. */
export function storableMessages(messages) {
  return (Array.isArray(messages) ? messages : [])
    .filter((m) => m && (m.role === 'user' || m.role === 'assistant') && String(m.text || '').trim())
    .map((m) => Object.fromEntries(KEEP.filter((k) => m[k] !== undefined && m[k] !== null).map((k) => [k, m[k]])))
    .slice(-100);
}

const url = (projectId) => `${API_BASE}/api/projects/${encodeURIComponent(projectId)}/chat-history`;

export async function loadChatHistory(projectId) {
  const res = await fetch(url(projectId), { credentials: 'include' });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  const json = await res.json();
  return Array.isArray(json?.messages) ? json.messages : [];
}

export async function saveChatHistory(projectId, messages) {
  const res = await fetch(url(projectId), {
    method: 'PUT',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ messages: storableMessages(messages) }),
  });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}
