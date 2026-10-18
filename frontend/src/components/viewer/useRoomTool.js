/**
 * useRoomTool — the state of the viewer's room tool R (Pathon v3 wave 1, W1-D, D2): one click inside a room
 * → the wall-exact outline is PROPOSED (dashed, with its consequence line) → his next click elsewhere or
 * Enter saves it (and offers „Atšaukti"), Esc drops it; a click inside the proposal saves it too. The tool
 * stays armed, so the next room is one more click.
 *
 * The network halves are the host's (InteriorWorkspace): `onPreview(nr, point)` → the `outline-at` answer
 * with `perziura` (nothing saved, no journal row); `onCommit(nr, body)` → saves through `outline-set`
 * (`kaip: "parodyta"`) and resolves to `{undo?}`. A sheet with no vector walls answers `no_walls`: the
 * raster click-fill (`onRasterPreview` / `onRasterCommit`) is the fallback, its proposal says it is an
 * estimate. Which room the click means comes from lib/roomTool; a click in the title block, a legend or a
 * table (sheet zones, W1-E) is refused with one sentence.
 *
 * Phases: 'idle' (armed, waiting) · 'reading' (asking the server) · 'proposed' · 'saving' · 'picking'
 * (the click named no room: „Kuri tai patalpa?").
 */
import { useCallback, useEffect, useRef, useState } from 'react';
import { toast } from 'sonner';
import { useTranslation } from 'react-i18next';
import { displayPointOf, outlineFailureKey } from '@/lib/roomOutline';
import {
  roomForToolClick, pickCandidates, retryNrFor, noWallSentence, proposalLines, rasterProposalLines, commitBody, insideProposal,
} from '@/lib/roomTool';
import { fetchSheetZones, noRoomZoneAt } from '@/lib/sheetZonesApi';

const IDLE = { phase: 'idle', proposal: null, reading: null, picking: null };

export default function useRoomTool({
  active, rooms, sutapdinimas = null, projectId = null,
  onPreview = null, onCommit = null, onRasterPreview = null, onRasterCommit = null, onCommitted = null,
}) {
  const { t } = useTranslation();
  const [state, setState] = useState(IDLE);
  const stateRef = useRef(state);
  useEffect(() => { stateRef.current = state; });
  const roomsRef = useRef(rooms);
  useEffect(() => { roomsRef.current = rooms; });
  // Disarmed (another tool, Esc, the check view): whatever was proposed is dropped — it was never saved.
  useEffect(() => { if (!active) setState(IDLE); }, [active]);

  const roomByNr = (nr) => (roomsRef.current || []).find((r) => String(r?.nr) === String(nr)) || null;

  const failure = useCallback((answer) => {
    const { key, params } = outlineFailureKey(answer);
    return t(`project.roomSheet.${key}`, params);
  }, [t]);

  /**
   * Ask the server for the outline of room `nr` at `where`. When the room was only GUESSED (its number is the
   * nearest, `how` = 'number') and the walls name another room, ask once more for that one; when the click was
   * inside the room's own outline and the walls still give the place to a neighbour, no wall separates them.
   */
  const propose = useCallback(async (nr, where, how = 'number') => {
    setState({ ...IDLE, phase: 'reading', reading: where });
    try {
      let tried = nr;
      let answer = await onPreview(tried, where);
      const again = how === 'number' ? retryNrFor(answer, tried) : null;
      if (again && roomByNr(again)) {
        tried = again;
        answer = await onPreview(tried, where);
      }
      const noWall = noWallSentence(tried, answer);
      if (noWall && (how === 'outline' || tried !== nr)) {
        toast.error(noWall);
        setState(IDLE);
        return;
      }
      if (answer?.status === 'ok' && Array.isArray(answer.room?.polygon_pct)) {
        const room = roomByNr(tried);
        setState({
          ...IDLE,
          phase: 'proposed',
          proposal: { kind: 'vector', nr: String(tried), page: where.page, ring: answer.room.polygon_pct, answer, lines: proposalLines(room, answer) },
        });
        return;
      }
      if (answer?.status === 'no_walls' && onRasterPreview) {
        const raster = await onRasterPreview(tried, where).catch(() => null);
        if (raster?.ring) {
          setState({
            ...IDLE,
            phase: 'proposed',
            proposal: { kind: 'raster', nr: String(tried), page: where.page, ring: raster.ring, data: raster.data, lines: rasterProposalLines(roomByNr(tried), raster.ring) },
          });
          return;
        }
      }
      toast.error(failure(answer));
      setState(IDLE);
    } catch (e) {
      toast.error(e?.userMessage || e?.message || 'Nepavyko perskaityti kontūro');
      setState(IDLE);
    }
  }, [onPreview, onRasterPreview, failure]); // eslint-disable-line react-hooks/exhaustive-deps

  const commit = useCallback(async () => {
    const cur = stateRef.current;
    const p = cur.proposal;
    if (cur.phase !== 'proposed' || !p) return false;
    setState({ ...cur, phase: 'saving' });
    try {
      const room = roomByNr(p.nr);
      const result = p.kind === 'raster'
        ? await onRasterCommit?.(p.nr, p.data)
        : await onCommit?.(p.nr, commitBody(p, room));
      const undo = typeof result?.undo === 'function' ? result.undo : null;
      toast.success(`Patalpos ${p.nr} kontūras išsaugotas`, {
        description: p.kind === 'raster'
          ? 'Kontūras pagal brėžinio vaizdą — apytikslis. Plotas lieka iš lentelės.'
          : 'Sienos ir angos perskaitytos iš naujo, kiekiai perskaičiuojami.',
        ...(undo ? { duration: 10_000, action: { label: 'Atšaukti', onClick: () => { undo(); } } } : {}),
      });
      setState(IDLE);
      onCommitted?.(p.nr);
      return true;
    } catch (e) {
      toast.error(e?.userMessage || e?.message || 'Nepavyko išsaugoti kontūro');
      setState({ ...cur, phase: 'proposed' });
      return false;
    }
  }, [onCommit, onRasterCommit, onCommitted]); // eslint-disable-line react-hooks/exhaustive-deps

  /** A click on the sheet while the tool is armed (the raw page point from PageOverlayHost). */
  const click = useCallback(async (pt) => {
    const where = displayPointOf(pt);
    if (!where || !onPreview) return;
    const cur = stateRef.current;
    if (cur.phase === 'reading' || cur.phase === 'saving') return;     // one request at a time
    if (cur.phase === 'proposed') {
      const inside = insideProposal(cur.proposal, where);
      const saved = await commit();
      if (inside || !saved) return;
    }
    // A click in the title block, a legend or a table is never a room (sheet zones; unknown zones → go on).
    if (projectId) {
      const zones = await fetchSheetZones(projectId, where.page).catch(() => null);
      const refused = zones ? noRoomZoneAt(zones, where.x_pct, where.y_pct) : null;
      if (refused) { toast.info(refused.sentence); setState(IDLE); return; }
    }
    const hit = roomForToolClick(roomsRef.current, where, { sutapdinimas });
    if (!hit) {
      setState({ ...IDLE, phase: 'picking', picking: { where, candidates: pickCandidates(roomsRef.current) } });
      return;
    }
    await propose(hit.nr, where, hit.how);
  }, [onPreview, commit, propose, projectId, sutapdinimas]);

  /** „Kuri tai patalpa?" answered. */
  const pick = useCallback((nr) => {
    const where = stateRef.current.picking?.where;
    if (!where || nr == null) return;
    propose(String(nr), where, 'picked');
  }, [propose]);

  /** Esc: drop the proposal (or the question) first; with nothing pending the tool exits (→ false). */
  const escape = useCallback(() => {
    const cur = stateRef.current;
    if (cur.phase === 'proposed' || cur.phase === 'picking') { setState(IDLE); return true; }
    return false;
  }, []);

  // Enter saves the proposal (typing surfaces keep their Enter).
  useEffect(() => {
    if (!active || state.phase !== 'proposed') return undefined;
    const onKey = (e) => {
      if (e.key !== 'Enter' || e.metaKey || e.ctrlKey || e.altKey) return;
      if (e.target?.closest?.('input, textarea, select, [contenteditable]')) return;
      e.preventDefault();
      commit();
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [active, state.phase, commit]);

  return { state, click, commit, pick, escape, cancelPick: () => setState(IDLE) };
}
