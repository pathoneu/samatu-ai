/**
 * detectRunApi — the network half of „Perskaityti lapą" (api/detect_run.py; the
 * pure model is lib/detectRun.js). POST starts the €0 reading of the chosen
 * sheets as a job, GET answers with its stages; a finished job's result has the
 * free re-read's shape and lands through the same merge and row rebuild
 * (lib/freeRereadApi.landFreeRereadResult).
 */

import { API_BASE } from '@/lib/apiBase';

const base = (projectId) => `${API_BASE}/api/projects/${encodeURIComponent(projectId)}/detect-run`;

async function readJson(res) {
  const body = await res.json().catch(() => ({}));
  if (!res.ok) {
    const err = new Error(typeof body.detail === 'string' ? body.detail : `HTTP ${res.status}`);
    err.status = res.status;
    throw err;
  }
  return body;
}

/** Starts the reading; answers with the job's first snapshot (`{job, stages, …}`). */
export async function startDetectRun(projectId, body, { signal } = {}) {
  return readJson(await fetch(base(projectId), {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
    signal,
  }));
}

/** The job's snapshot; `result` once `result_ready`. */
export async function fetchDetectRun(projectId, jobId, { signal } = {}) {
  return readJson(await fetch(`${base(projectId)}/${encodeURIComponent(jobId)}`, { credentials: 'include', signal }));
}
