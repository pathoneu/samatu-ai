/**
 * usePageGeometry — the wall geometry of one sheet, fetched when `enabled` first turns true.
 * `{ geometry, status }`, status ∈ idle | loading | ok | no_walls | error. A 404 (no PDF stored) is
 * `no_walls`: the viewer simply has nothing to snap to, which is not an error worth a toast.
 */
import { useEffect, useState } from 'react';
import { fetchPageGeometry } from '@/lib/pageGeometryApi';

export function usePageGeometry(projectId, page, enabled) {
  const [state, setState] = useState({ geometry: null, status: 'idle' });
  useEffect(() => {
    if (!enabled || !projectId || !(page >= 1)) return undefined;
    let alive = true;
    setState((s) => (s.status === 'idle' ? { geometry: null, status: 'loading' } : s));
    fetchPageGeometry(projectId, page).then((g) => {
      if (alive) setState({ geometry: g, status: g?.status === 'ok' ? 'ok' : 'no_walls' });
    }).catch((e) => {
      if (alive) setState({ geometry: null, status: e?.status === 404 ? 'no_walls' : 'error' });
    });
    return () => { alive = false; };
  }, [projectId, page, enabled]);
  return state;
}
