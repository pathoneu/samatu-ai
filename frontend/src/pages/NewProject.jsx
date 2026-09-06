import React, { useState, useRef, useEffect } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Button } from '@/components/ui/button';
import { ArrowLeft, Rocket } from 'lucide-react';
import UploadZone from '@/components/upload/UploadZone';
import PreflightCard from '@/components/upload/PreflightCard';
import ProcessingState from '@/components/upload/ProcessingState';
import ProcessingStateStream from '@/components/upload/ProcessingStateStream';
import { fetchPreflight, preflightCard, pollLimitMs } from '@/lib/preflight';
import { WORK_FAMILIES, filterRowsByFamilies } from '@/lib/workFamilies';
import { LUBOS_CHOICES, SIENOS_ANGOS_CHOICES, scopeForBackend } from '@/lib/scope';
import { rememberProjectScope, remembered } from '@/lib/scopeMemory';
import { parseLtNumber } from '@/lib/parseLtNumber';
import {
  createProject, updateProject, getPriceLists, pullPriceListsFromBackend,
  markPriceFillPending,
} from '@/lib/projectStore';
import { autoFillFromDefaultPriceList, describeAmbiguous } from '@/lib/applyPriceList';
import { CONF_RAUDONA, normalizeConfidence } from '@/lib/confidence';
import { savePdf, uploadPdfToBackend } from '@/lib/pdfStore';
import { postSse } from '@/lib/sseFetch';
import { useQueryClient } from '@tanstack/react-query';
import { loadPrefs } from '@/components/project/SetupWizard';
import { API_BASE as API } from '@/lib/apiBase';
import { useBilling } from '@/hooks/useBilling';
import UpgradeDialog from '@/components/billing/UpgradeDialog';
import { detectPaywall } from '@/lib/paywall';
import { toast } from 'sonner';

// Pirmoji versija: Interjero projektas yra DEFAULT. Kiti tipai (KŽ, Fasadai,
// Stogas, Žemės, Betonas) — paslėpti į "Kitas tipas" advanced.
// Labels/descriptions resolve against i18n at render (see newProject.types.*).
const PROJECT_TYPES = [
  { id: 'interior' },
];

// Advanced tipai — paslėpti pagal nutylėjimą, vartotojas atskleidžia spaudžiant.
// Founder decision 2026-07-25: Fasadai/Stogas/Žemės/Betonas HIDDEN for the
// contractor launch — their endpoints run simplistic math (roof silently
// defaults pitch to 30°) while the validated roof engine is unwired. Interior
// + KŽ are the product; re-add these only wired to real engines.
const ADVANCED_PROJECT_TYPES = [
  { id: 'auto' },
  { id: 'kz' },
];

// Interior sub-type still flows to backend (default 'naujas'). UI selector
// removed 2026-05-13; backend formula branches kept for future re-introduction.

async function detectAndExtract(file, forcedType, signal, opts = {}) {
  let projType = forcedType;
  const interiorSubtype = opts.interiorSubtype || 'naujas';

  if (forcedType === 'auto') {
    try {
      const dtFd = new FormData();
      dtFd.append('file', file);
      const dtRes = await fetch(`${API}/detect-type`, { method: 'POST', credentials: 'include', body: dtFd, signal });
      if (dtRes.ok) {
        const dt = await dtRes.json();
        if (dt.type === 'interior') projType = 'interior';
        else projType = 'kz';
      } else {
        projType = 'kz';
      }
    } catch {
      projType = 'kz';
    }
  }

  const ENDPOINT_MAP = {
    interior: '/extract-interior',  // single Vision call pipeline (post-2026-04 simplification)
    kz:       '/extract',
    fasadas:  '/extract-facade',
    stogas:   '/extract-roof',
    zeme:     '/extract-earthworks',
    betonas:  '/extract-concrete',
  };
  const endpoint = ENDPOINT_MAP[projType] || '/extract';

  // V3 interior endpoint expects multi-file field 'files'; others expect single 'file'.
  const fd = new FormData();
  if (projType === 'interior') {
    fd.append('files', file);
    // V8: užkrauti vartotojo nustatymus (rules_override) + „ką skaičiuoti"
    fd.append('interior_subtype', interiorSubtype);
    appendRulesOverride(fd, opts?.scope);
  } else {
    fd.append('file', file);
  }

  const res = await fetch(`${API}${endpoint}`, { method: 'POST', credentials: 'include', body: fd, signal });
  const json = await res.json();
  return { json, res, projType };
}

/**
 * The `rules_override` field of the upload: the Setup Wizard preferences (when
 * the wizard was completed) plus the „ką skaičiuoti" choices made on this
 * screen (`apimtis`, enforced server-side — extractor/scope.py). Appended only
 * when there is something to say.
 */
function appendRulesOverride(fd, scope) {
  const overrides = {};
  try {
    const prefs = loadPrefs();
    if (prefs && prefs.setup_completed) {
      Object.assign(overrides, {
        bathroom_tile_height_m: prefs.bathroom_tile_height_m,
        bathroom_walls_painted_above_tiles: prefs.bathroom_walls_painted_above_tiles,
        kitchen_backsplash_height_m: prefs.kitchen_backsplash_height_m,
        drabuzine_painted: prefs.drabuzine_painted,
        rubine_painted: prefs.rubine_painted,
        sandeliukas_painted: prefs.sandeliukas_painted,
        katiline_painted: prefs.katiline_painted,
        garazas_painted: prefs.garazas_painted,
        tamburas_painted: prefs.tamburas_painted,
        openings_threshold_m2: prefs.openings_threshold_m2,
        default_door_area_m2: prefs.default_door_area_m2,
        default_window_area_m2: prefs.default_window_area_m2,
        count_inner_corners: prefs.count_inner_corners,
        count_outer_corners: prefs.count_outer_corners,
        glaistas_q_lygis: prefs.glaistas_q_lygis,
        glaistas_storis_mm: prefs.glaistas_storis_mm,
        tile_method: prefs.tile_method,
        tile_waste_pct: prefs.tile_waste_pct,
        paint_waste_pct: prefs.paint_waste_pct,
        high_ceiling_threshold_m: prefs.high_ceiling_threshold_m,
      });
    }
  } catch (e) {
    console.warn('Could not load user prefs', e);
  }
  const apimtis = scopeForBackend(scope);
  if (apimtis) overrides.apimtis = apimtis;
  if (Object.keys(overrides).length) fd.append('rules_override', JSON.stringify(overrides));
}

// SM01: streaming variant for interior projects. Wires SSE events to onProgress
// and resolves with the same {json, projType} shape the non-streaming path
// returned, so downstream code can keep its branching.
async function streamInteriorExtract(file, signal, opts, onProgress) {
  const fd = new FormData();
  fd.append('files', file);
  fd.append('interior_subtype', opts.interiorSubtype || 'naujas');
  appendRulesOverride(fd, opts.scope);

  let finalResult = null;
  await postSse(`${API}/extract-interior-stream`, fd, {
    signal,
    onEvent: (ev) => {
      if (ev.event === 'done') {
        finalResult = ev.result;
      }
      onProgress?.(ev);
    },
  });

  if (!finalResult) throw new Error('Extraction stream ended without result');
  return { json: finalResult, projType: 'interior' };
}

/**
 * waitForRecoveredProject — poll for a project the SERVER is still finishing.
 *
 * The extraction outlives its SSE connection (backend drains it detached and
 * saves under the announced id), so a dropped socket is a WAIT, not a failure.
 * Polls every 10 s and gives up quietly, leaving the on-screen message that the
 * analysis continues.
 *
 * WINDOW SIZING (2026-07-29, measured on the first successful recovery). The
 * old 15 min was justified by "comfortably past the longest observed extraction
 * (~21 min)". That estimate was wrong: the real run took 26 min 53 s
 * (16:55:00 → 17:21:53), of which 12 min 40 s fell AFTER the 840 s handoff — so
 * it consumed 84% of the window and landed with 2 min 7 s to spare. Three
 * slower minutes and the user would have watched the poller give up on a
 * project that was about to exist.
 *
 * 40 min is sized off what the wait actually costs: an authenticated GET
 * against an indexed lookup every 10 s, which stops the instant the project
 * appears, the user navigates away, or isCancelled fires. Waiting too long is
 * nearly free; giving up too early looks like data loss. Do not tighten this
 * back toward the extraction time — it must clear the SLOWEST run, not the
 * typical one.
 */
/**
 * notifyAnalysisDone — the 27-minute wait's missing ending (2026-08-11).
 *
 * The progress UI tells the user they can leave, and they correctly do — but
 * nothing ever called them back, so "leave, come back later" quietly became
 * "leave". When the tab is hidden at completion: flip the title to a ✓ (the
 * tab strip is the one place a backgrounded app can still speak) and, if the
 * user granted it, fire a desktop notification. Permission is requested at
 * SUBMIT — the only moment the user is present, engaged, and about to start
 * a long wait, so the browser prompt reads as sensible rather than creepy.
 * A visible tab gets neither: the user is already watching.
 */
function notifyAnalysisDone(t) {
  try {
    if (!document.hidden) return;
    const original = document.title;
    document.title = t('newProject.doneTabTitle');
    const restore = () => {
      document.title = original;
      document.removeEventListener('visibilitychange', restore);
    };
    document.addEventListener('visibilitychange', restore);
    if ('Notification' in window && Notification.permission === 'granted') {
      new Notification(t('newProject.doneNotifTitle'), {
        body: t('newProject.doneNotifBody'),
        icon: '/favicon.svg',
      });
    }
  } catch { /* notifications are best-effort, never break the flow */ }
}

/**
 * Automatic price fill, applied to the project payload BEFORE it is created
 * (founder decision 2026-09-02: "auto-apply from the default price list + keep
 * the manual button"). Doing it here — not after the save — means the prices
 * ride the very first write, so there is no second PUT to race and nothing to
 * re-apply if the user reloads mid-flight.
 *
 * Only fills rows with no price, never overwrites, and stamps
 * `_kainynas_auto_applied` so it can only ever happen once per extraction.
 * Never blocks project creation: a failure here is a missing convenience, not
 * a lost 25-minute analysis.
 */
async function withAutoPrices(payload, t) {
  try {
    await pullPriceListsFromBackend();     // once per session, small payload
    const out = autoFillFromDefaultPriceList(payload, getPriceLists());
    if (!out) return payload;
    const { applied, exact, similar, name, ambiguous } = out.summary;
    toast.success(t('project.mainView.autoPricesApplied',
      { applied, exact, similar, name }), { duration: 8000 });
    if (ambiguous?.length) {
      toast.warning(t('project.mainView.toastAmbiguous', { count: ambiguous.length }),
        { duration: 8000, description: describeAmbiguous(ambiguous, t) });
    }
    return out.project;
  } catch (e) {
    console.warn('Automatinis kainų užpildymas nepavyko:', e);
    return payload;
  }
}

/**
 * @param {string} projectId
 * @param {{onTick?:Function, isCancelled?:Function, limitMs?:number}} opts
 *   `limitMs` comes from the preflight (see lib/preflight.pollLimitMs). A
 *   60-page project runs past the historical fixed 40 min, and the browser
 *   giving up first meant telling the user his run had failed while the server
 *   was still working and about to save the project. Defaults to 40 min when
 *   there was no preflight, so nothing changes for an unmeasured upload.
 */
async function waitForRecoveredProject(projectId, { onTick, isCancelled, limitMs } = {}) {
  const started = Date.now();
  const LIMIT_MS = limitMs || 40 * 60 * 1000;
  while (Date.now() - started < LIMIT_MS) {
    if (isCancelled?.()) return null;
    try {
      const res = await fetch(`${API}/api/projects/${projectId}`, { credentials: 'include' });
      if (res.ok) {
        const p = await res.json();
        // status 'empty' = a saved zero-room run (2026-08-11): the server now
        // persists those instead of dropping them, so the poller must accept
        // them or it would wait 40 min on a project that already exists.
        if (p && (p.patalpos?.length || p.darbu_sarasas?.length || p.status === 'empty')) return p;
      }
    } catch { /* offline blip — keep waiting, the server does not care */ }
    onTick?.(Math.round((Date.now() - started) / 1000));
    await new Promise(r => setTimeout(r, 10000));
  }
  return null;
}

export default function NewProject() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { enabled: billingEnabled } = useBilling();
  // Paywall block dialog: { reason, message } when the backend refuses creation.
  const [paywall, setPaywall] = useState(null);
  const [projectName, setProjectName]   = useState('');
  const [companyName, setCompanyName]   = useState('');
  const [file, setFile]                 = useState(null);
  // Preflight: the free 5 s look at the PDF, run the moment a file is chosen.
  // `preflight` is the raw endpoint payload (also read for the poller ceiling);
  // `preflightBusy` drives the "Tikriname failą…" line; `uploadResetToken` is
  // how "Pasirinkti kitą failą" clears UploadZone's own internal state.
  const [preflight, setPreflight]       = useState(null);
  const [preflightBusy, setPreflightBusy] = useState(false);
  const [uploadResetToken, setUploadResetToken] = useState(0);
  const preflightRunRef = useRef(0);
  const [projTypeChoice, setProjType]   = useState('interior');
  // ── E1's three optional questions (design „Rimo kelionė" §E1). Every one has
  // a named default, so pressing „Skaičiuoti kiekius" without touching any of
  // them is a sensible answer, not a gap. What each one actually does is
  // written next to it — no control here claims more than it delivers.
  const [objektas, setObjektas]         = useState('butas');
  const [ceilingHeight, setCeilingHeight] = useState('');
  const [families, setFamilies]         = useState(() => new Set(WORK_FAMILIES));
  // „Ką skaičiuoti" beyond the families: ceilings and the wall area convention.
  // Pre-selected from his last three projects when they agree (lib/scopeMemory);
  // the note under the control says so, and one click changes it.
  const [rememberedKeys] = useState(() => new Set(Object.keys(remembered())));
  const [lubosChoice, setLubosChoice]   = useState(() => remembered().lubos || 'dazomos');
  const [sienosAngos, setSienosAngos]   = useState(() => remembered().sienos_angos || 'atimti');
  const scopeChoice = () => ({
    darbai_ne: WORK_FAMILIES.filter((f) => !families.has(f)),
    lubos: lubosChoice,
    sienos_angos: sienosAngos,
  });
  useEffect(() => {
    const learned = remembered();
    if (Array.isArray(learned.darbai_ne) && learned.darbai_ne.length) {
      setFamilies(new Set(WORK_FAMILIES.filter((f) => !learned.darbai_ne.includes(f))));
    }
  }, []);
  // Default interior subtype, no setter — UI selector removed 2026-05-13.
  const [interiorSubtype] = useState('naujas');
  const [showAdvancedTypes, setShowAdvancedTypes] = useState(false);
  const [abortController, setAbortController] = useState(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [error, setError]               = useState(null);
  const [status, setStatus]             = useState('');
  // SM01 streaming progress state
  // null | 'rendering' | 'pass1' | 'zoom' | 'post' | 'finishing'
  // 'finishing' is the post-handoff phase: the socket is gone but the server is
  // still extracting, so the UI must keep RUNNING rather than freeze.
  const [streamPhase, setStreamPhase]     = useState(null);
  const [streamProgress, setStreamProgress] = useState({
    rooms: [], zoomDone: 0, zoomTotal: 0, pageCount: null, validationWarning: null,
  });
  const [streamElapsed, setStreamElapsed] = useState(0);
  // Post-handoff view state: are we polling, and for how long.
  const [recovering, setRecovering]       = useState(false);
  const [recoverySec, setRecoverySec]     = useState(0);
  const elapsedTimerRef = useRef(null);

  // ONE owner for stopping the clock. It used to be stopped in the request's
  // `finally`, which runs BEFORE the catch that starts polling — so on a
  // handed-off run the counter froze at 839 s and the user watched a dead
  // number for the remaining ~13 minutes of a perfectly healthy extraction.
  const stopElapsed = () => {
    if (elapsedTimerRef.current) {
      clearInterval(elapsedTimerRef.current);
      elapsedTimerRef.current = null;
    }
  };
  // Backstop: never leave an interval behind if the user navigates away
  // mid-run (the timer now deliberately outlives the fetch).
  useEffect(() => () => {
    if (elapsedTimerRef.current) clearInterval(elapsedTimerRef.current);
  }, []);
  const abortReasonRef = useRef(null);
  // True once the SSE stream has begun — read in the catch block, where the
  // `streamPhase` STATE is stale (captured at click time). See the assignment.
  const streamStartedRef = useRef(false);
  // Project id the server announces at stream start; used to WAIT for the
  // result when the connection drops mid-extraction instead of erroring out.
  const recoveryIdRef = useRef(null);

  /**
   * Look at the PDF the moment it is chosen. Free (no Vision), ~1-3 s, and it
   * is the only chance to tell a contractor that his 139-page technical set or
   * his KŽ table is about to buy him 25 minutes of nothing.
   *
   * Never blocks the upload: a failed probe just leaves the card unrendered.
   * The run counter guards against a stale answer landing after the user has
   * already picked a different file.
   */
  const handleFileSelect = async (nextFile) => {
    const run = ++preflightRunRef.current;
    setFile(nextFile);
    setPreflight(null);
    setError(null);
    if (!nextFile) { setPreflightBusy(false); return; }
    setPreflightBusy(true);
    const result = await fetchPreflight(nextFile);
    if (run !== preflightRunRef.current) return;   // superseded — ignore
    setPreflight(result);
    setPreflightBusy(false);
  };

  const clearChosenFile = () => {
    preflightRunRef.current++;
    setFile(null);
    setPreflight(null);
    setPreflightBusy(false);
    setUploadResetToken((n) => n + 1);
  };

  const card = preflightCard(preflight);

  const handleCreate = async (opts) => {
    if (!file) { setError(t('newProject.errNoPdf')); return; }
    // A page count past the pipeline's limit is the one preflight verdict that
    // is a FACT rather than a guess: beyond it the extraction silently reads
    // the first 100 pages, which on a 139-page bundle is usually the wrong 100.
    // USUALLY — not always, and the card is a client-side gate, not a backend
    // guarantee. So it stops the default path and demands a second, explicit
    // click ("Vis tiek analizuoti pirmus 100 psl.") rather than refusing the
    // upload outright: a 105-page set whose interjero dalis is bound FIRST is
    // perfectly analysable, and before this card shipped it simply worked.
    // `opts` is that acknowledgement — a click event (from onContinue) has no
    // ackBlock key, so only the override button gets through.
    if (card?.blocked && !opts?.ackBlock) {
      setError(card.reason || t('newProject.errNoPdf'));
      return;
    }
    // Ask for notification permission NOW, while the user is present and about
    // to start a ~30 min wait — see notifyAnalysisDone. Never blocks.
    try {
      if ('Notification' in window && Notification.permission === 'default') {
        Notification.requestPermission().catch(() => {});
      }
    } catch { /* no Notification API — fine */ }
    setError(null);
    setStatus(t('newProject.statusUploading'));
    setIsProcessing(true);
    setStreamPhase(null);
    streamStartedRef.current = false;
    setStreamProgress({
      rooms: [], zoomDone: 0, zoomTotal: 0, pageCount: null, validationWarning: null,
    });
    setStreamElapsed(0);
    setRecovering(false);
    setRecoverySec(0);

    // Naujas controller — vartotojas gali atšaukti su mygtuku
    const controller = new AbortController();
    setAbortController(controller);
    abortReasonRef.current = null; // 'stalled' | 'timeout' | null (= user cancel)

    // Generic per-second elapsed counter (also used by streaming UI).
    const elapsedStart = Date.now();
    elapsedTimerRef.current = setInterval(() => {
      setStreamElapsed(Math.floor((Date.now() - elapsedStart) / 1000));
    }, 1000);

    try {
      // Extraction time scales with project size — a real Objektas A-class drawing
      // runs ~19 min, well past the old fixed 600 s cap that made contractors
      // watch the browser abort a HEALTHY extraction (pre-prod QA 2026-07-15).
      // The streaming path emits progress events throughout, so abort only when
      // progress STALLS (idle), with a generous absolute ceiling as a backstop
      // for a trickle-but-stuck stream and the non-streaming (KŽ) path.
      const IDLE_ABORT_MS = 420_000;    // 7 min with no progress event → hung
      const HARD_ABORT_MS = 2_700_000;  // 45 min absolute ceiling
      let idleTimer = null;
      const bumpIdle = () => {
        if (idleTimer) clearTimeout(idleTimer);
        idleTimer = setTimeout(() => { abortReasonRef.current = 'stalled'; controller.abort(); }, IDLE_ABORT_MS);
      };
      const timeoutId = setTimeout(() => { abortReasonRef.current = 'timeout'; controller.abort(); }, HARD_ABORT_MS);
      // EDGE DEADLINE (2026-07-29). Railway's edge terminates the HTTP request
      // at exactly 900 s — measured three times on the same 17-page project,
      // the last one failing at 899 s with a bare "TypeError: network error"
      // while the SERVER kept extracting for another five minutes. Waiting for
      // that cut means the user always eats a scary error on a healthy run.
      // So we let go FIRST, at 840 s, and switch to polling for the project id
      // the stream announced — same ending, no error, no lost work. Only armed
      // once the stream is actually running and has given us an id to poll.
      const EDGE_DEADLINE_MS = 840_000;   // 14 min < the 900 s edge cut
      const edgeTimer = setTimeout(() => {
        if (streamStartedRef.current && recoveryIdRef.current) {
          abortReasonRef.current = 'edge_deadline';
          controller.abort();
        }
      }, EDGE_DEADLINE_MS);
      let json, res, projType;

      // Status text fallback only when NOT streaming (KŽ + construction types).
      const statusTimer = (projTypeChoice !== 'interior' && projTypeChoice !== 'auto')
        ? setInterval(() => {
            const sec = Math.floor((Date.now() - elapsedStart) / 1000);
            if (sec < 15) setStatus(t('newProject.statusReading', { sec }));
            else if (sec < 60) setStatus(t('newProject.statusProcessing', { sec }));
            else setStatus(t('newProject.statusComplex', { sec }));
          }, 1000)
        : null;

      try {
        if (projTypeChoice === 'interior') {
          // SM01: stream the extraction so user sees progress in real time.
          // The REF (not the state) is what the catch block below reads: this
          // async function closes over the render in which the user clicked, so
          // `streamPhase` is frozen at null there forever and a mid-run drop
          // would report "check your connection" instead of the truth.
          streamStartedRef.current = true;
          recoveryIdRef.current = null;
          setStreamPhase('rendering');
          bumpIdle();  // arm the stall detector before the first event arrives
          ({ json, projType } = await streamInteriorExtract(
            file, controller.signal,
            { interiorSubtype, scope: scopeChoice() },
            (ev) => {
              bumpIdle();  // every progress event resets the stall timer
              // First event of every stream: the id the server will save under
              // if this connection dies. Held so the catch block can wait for
              // the project instead of dead-ending the user. (2026-07-28)
              if (ev.event === 'recovery_id' && ev.project_id) {
                recoveryIdRef.current = ev.project_id;
              }
              if (ev.event === 'validation_warning') {
                // The backend has emitted this since the streaming endpoint
                // shipped and NOTHING listened — the one message that says
                // "your PDF is longer than we will read" was thrown away at
                // the exact moment the user was watching the screen.
                setStreamProgress(p => ({
                  ...p,
                  validationWarning: ev.message || null,
                  pageCount: ev.page_count || p.pageCount,
                }));
              } else if (ev.event === 'started') {
                setStreamProgress(p => ({ ...p, pageCount: ev.page_count }));
              } else if (ev.event === 'pass1_started') {
                setStreamPhase('pass1');
              } else if (ev.event === 'pass1_completed') {
                setStreamProgress(p => ({
                  ...p,
                  rooms: (ev.patalpos || []).map(r => ({ ...r, refined: false })),
                }));
              } else if (ev.event === 'zoom_started') {
                setStreamPhase('zoom');
                setStreamProgress(p => ({ ...p, zoomTotal: ev.total || 0, zoomDone: 0 }));
              } else if (ev.event === 'zoom_room_completed') {
                setStreamProgress(p => {
                  const rooms = p.rooms.map(r => r.nr === ev.room_nr
                    ? { ...r, refined: ev.applied === true,
                        plotas_m2: ev.plotas_m2 ?? r.plotas_m2 }
                    : r);
                  return { ...p, rooms, zoomDone: ev.idx ?? (p.zoomDone + 1) };
                });
              } else if (ev.event === 'post_processing') {
                setStreamPhase('post');
              } else if (ev.event === 'error') {
                // Surface mid-stream error message; the final 'done' event
                // still drives the error result branch below.
                setError(ev.message || t('newProject.errGeneric'));
              }
            },
          ));
          res = { ok: true };
        } else {
          ({ json, res, projType } = await detectAndExtract(
            file, projTypeChoice, controller.signal,
            { interiorSubtype },
          ), { scope: scopeChoice() });
        }
        setStatus(t('newProject.statusSaving'));
      } finally {
        clearTimeout(timeoutId);
        clearTimeout(edgeTimer);
        if (idleTimer) clearTimeout(idleTimer);
        if (statusTimer) clearInterval(statusTimer);
        // THE CLOCK OUTLIVES THE CONNECTION (2026-07-29). This block runs before
        // the catch that polls for a handed-off extraction, so stopping the
        // counter here froze it at 839 s while the server worked on for another
        // ~13 minutes. Keep it running whenever a recovery is still possible —
        // the catch owns stopping it once the project lands or the wait is
        // genuinely over. elapsedStart is wall-clock, so it stays accurate
        // across the handoff.
        if (!(streamStartedRef.current && recoveryIdRef.current)) {
          stopElapsed();
        }
        setAbortController(null);
      }

      if (!res.ok) {
        // Paywall (402 quota/trial, 403 company-code) — carry status + body so
        // the catch can open the UpgradeDialog instead of a generic error.
        if (res.status === 402 || res.status === 403) {
          const err = new Error(json?.message || json?.error || `HTTP ${res.status}`);
          err.status = res.status;
          err.body = json;
          throw err;
        }
        const msg = Array.isArray(json?.detail)
          ? json.detail.map(d => d.msg).join(', ')
          : json?.detail || t('newProject.errServer', { status: res.status });
        throw new Error(msg);
      }
      // Catch backend pipeline errors that return 200 with status="error"
      if (json?.status === 'error' || json?._error) {
        throw new Error(json._error || json.error || t('newProject.errPipeline'));
      }
      if (json.error) throw new Error(json.error);

      const CONSTRUCTION_TYPES = ['fasadas', 'stogas', 'zeme', 'betonas'];
      let project;
      if (CONSTRUCTION_TYPES.includes(projType)) {
        project = createProject(await withAutoPrices({
          name:         projectName || json.projektas || t('newProject.defaultNameConstruction'),
          company_name: companyName,
          tipas:        projType,
          ...json,
          rows:         [],
          total_rows:   0,
          total_value:  0,
          status:       'ready',
        }, t));
      } else if (projType === 'interior') {
        if (!json.patalpos) throw new Error(t('newProject.errUnexpectedFormat'));
        // Zero rooms used to THROW here — before createProject — so 13+ paid
        // minutes produced nothing: no project, no pages, and the error text's
        // own advice ("pridėkite patalpas rankiniu būdu") pointed at a project
        // that did not exist. (2026-08-11 audit; the old 2026-06-19 rationale
        // wanted a recoverable message — this IS the recoverable version.)
        // The run is saved with the drawing attached, the message rides along
        // as a warning, and the user lands in the viewer where "Taisyti zoną"
        // and manual room-add actually work.
        const zeroRooms = json.patalpos.length === 0;
        // „Ką skaičiuoti?" — the families he unticked are removed from the
        // sąmata, which is exactly what the checkbox promised. The filter is
        // conservative by construction: a section belonging to no family is
        // never dropped (see lib/workFamilies.js).
        const keptRows = filterRowsByFamilies(json.darbu_sarasas, [...families]);
        // „Lubų aukštis, jei žinote" — kept as the project's own default so the
        // Nustatymai height field opens on HIS number instead of 2,80. It is
        // not applied behind his back: the quantities still come from what the
        // drawing said, and one click in Nustatymai pushes his value through
        // the live recompute.
        const ceilingDefault = parseLtNumber(ceilingHeight);
        project = createProject(await withAutoPrices({
          ...json,
          darbu_sarasas:   keptRows,
          name:            projectName || json.projektas || t('newProject.defaultNameInterior'),
          company_name:    companyName,
          tipas:           'interjeras',
          objektas_tipas:  objektas,
          skaiciuoti_families: [...families],
          _apimtis:        scopeForBackend(scopeChoice()),
          ...(Number.isFinite(ceilingDefault) && ceilingDefault > 0
            ? { lubu_aukstis_default_m: ceilingDefault } : {}),
          rows:            [],
          total_rows:      json.patalpos.length,
          total_value:     0,
          status:          zeroRooms ? 'empty' : 'ready',
          ...(zeroRooms ? {
            warnings: [
              ...(json.warnings || []),
              { level: 'WARN', message: t('newProject.errNoRooms') },
            ],
          } : {}),
        }, t));
        if (zeroRooms) toast.warning(t('newProject.errNoRooms'), { duration: 12000 });
        rememberProjectScope(scopeChoice());
      } else {
        if (!json.eilutes) throw new Error(t('newProject.errUnexpectedFormat'));
        const rows = json.eilutes.map(row => ({
          ...row,
          kaina: 0,
          suma:  0,
          warning: normalizeConfidence(row.confidence) === CONF_RAUDONA ? t('newProject.warnLowConfidence')
                 : !row.mato_vnt ? t('newProject.warnMissingUnit') : '',
        }));
        project = createProject(await withAutoPrices({
          name:         projectName || json.projektas || t('newProject.defaultNameKz'),
          company_name: companyName,
          tipas:        'kz',
          rows,
          total_rows:   rows.length,
          total_value:  0,
          status:       'ready',
          vat_rate:     21,
        }, t));
      }

      // Saugom PDF: greitas IndexedDB kešas + durabli kopija backende, kad
      // brėžinys išliktų išvalius kešą / persijungus įrenginį. (2026-06-21)
      let localPdfOk = true;
      try {
        await savePdf(project.id, file);
      } catch (pdfErr) {
        localPdfOk = false;
        console.warn('Nepavyko išsaugoti PDF į IndexedDB:', pdfErr);
      }
      // Fire-and-forget — neblokuojam srauto; backendas yra durabli atsarginė kopija.
      // 2026-07-28 audit: kai NEPAVYKSTA ABU (IndexedDB ir backendas), brėžinio
      // nebelieka niekur — anksčiau tai matėsi tik console.warn'e, o vartotojas
      // toliau dirbo manydamas, kad brėžinys išsaugotas. Neblokuojantis
      // įspėjimas: eksportai veikia, bet peržiūra po perkrovimo — ne.
      uploadPdfToBackend(project.id, file).then((ok) => {
        if (!ok) console.warn('Nepavyko įkelti PDF į backendą (liks tik naršyklėje)');
        if (!ok && !localPdfOk) toast.warning(t('newProject.warnPdfNotDurable'));
      }).catch((e) => {
        console.warn('Nepavyko įkelti PDF į backendą:', e);
        if (!localPdfOk) toast.warning(t('newProject.warnPdfNotDurable'));
      });

      // Sprint §G5 (2026-04-29): scale auto-detect from PDF text layer
      // (regex „M 1:50 / 1:100" iš pdfplumber). Fire-and-forget — projektas
      // jau išsaugotas; mastelio hint įsirašo asynchronously.
      // Sprint §AUDIT (2026-04-29): chunked base64 encoding (avoid V8 heap
      // overflow on 200MB PDFs). Skip auto-detect entirely if file > 50MB
      // since the regex-based scan is unlikely to add value for huge plans
      // (mastelį tokie projektai nurodo kiekviename lape, vartotojas matys).
      try {
        if (file.size <= 50 * 1024 * 1024) {
          const pdfBytes = await file.arrayBuffer();
          // Use FileReader.readAsDataURL — handles big buffers chunkwise
          const pdfBase64 = await new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = () => {
              const dataUrl = reader.result;
              const idx = dataUrl.indexOf(',');
              resolve(idx >= 0 ? dataUrl.slice(idx + 1) : dataUrl);
            };
            reader.onerror = () => reject(reader.error);
            reader.readAsDataURL(new Blob([pdfBytes], { type: 'application/pdf' }));
          });
          const scaleResp = await fetch(`${API}/detect-scale-hint`, {
            method: 'POST',
            credentials: 'include',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ pdf_b64: pdfBase64 }),
          });
          if (scaleResp.ok) {
            const hint = await scaleResp.json();
            if (hint?.found) {
              updateProject(project.id, {
                ...project,
                _scale_hint: {
                  scale_ratio: hint.scale_ratio,
                  scale_text: hint.scale_text,
                  page: hint.page,
                  confidence: hint.confidence,
                  detected_at: new Date().toISOString(),
                },
              });
            }
          }
        }
      } catch (scaleErr) {
        console.warn('Mastelio aptikimas nepavyko (nekritinė klaida):', scaleErr);
      }

      queryClient.invalidateQueries({ queryKey: ['projects'] });
      notifyAnalysisDone(t);
      navigate(`/project/${project.id}`);
    } catch (e) {
      // Paywall intercept (Phase 7): a 402/403 from /extract-interior means
      // billing refused the creation. Open the UpgradeDialog rather than
      // showing a raw error. Only when billing is enabled — otherwise these
      // codes can't occur, and we fall through to the generic handler.
      const pw = billingEnabled ? detectPaywall(e) : null;
      if (pw) {
        console.warn('Billing block on project creation:', pw.reason);
        setPaywall(pw);
        setIsProcessing(false);
        setStatus('');
        setAbortController(null);
        return;
      }
      // User-friendly error mapping. Stack only kept in console for debugging.
      console.error('Upload pipeline failed:', e);
      let userMessage;
      if (e.name === 'AbortError') {
        // Honest message per abort cause (pre-prod QA: a STALLED extraction
        // used to read as if the USER cancelled it). 'edge_deadline' is OUR
        // deliberate hand-off before the proxy's 900 s cut — the extraction is
        // healthy and continues server-side, so it must never read as an error.
        userMessage = abortReasonRef.current === 'edge_deadline'
            ? t('newProject.errStreamLostButRunning')
          : abortReasonRef.current === 'stalled' ? t('newProject.errStalled')
          : abortReasonRef.current === 'timeout' ? t('newProject.errTimeout')
          : t('newProject.errAborted');
        // Hand straight to the poller — same path a real drop takes.
        if (abortReasonRef.current === 'edge_deadline' && recoveryIdRef.current) {
          // The extraction is HEALTHY, so the screen must stay alive: keep the
          // step animation, the room list and the running clock, and just move
          // to the 'finishing' phase. Dropping to a static line here made a
          // normal run look hung for its last third.
          setStreamPhase('finishing');
          setRecovering(true);
          const ok = await waitForRecoveredProject(recoveryIdRef.current, {
            onTick: (s) => setRecoverySec(s),
            isCancelled: () => abortReasonRef.current === 'user',
            // Scaled to the size the preflight measured: a 60-page project
            // outlives the historical fixed 40 min, and the client giving up
            // first turns a healthy run into a reported failure.
            limitMs: pollLimitMs(preflight),
          });
          if (ok) {
            stopElapsed();
            try { await savePdf(ok.id, file); } catch { /* IndexedDB best-effort */ }
            uploadPdfToBackend(ok.id, file).catch(() => {});
            // This project was built and saved SERVER-side, so it never passed
            // through the payload-level auto price fill above. Hand the job to
            // the project page. (2026-09-02)
            markPriceFillPending(ok.id);
            queryClient.invalidateQueries({ queryKey: ['projects'] });
            notifyAnalysisDone(t);
            navigate(`/project/${ok.id}`);
            return;
          }
          setRecovering(false);
        }
        stopElapsed();
      } else if (/network|fetch/i.test(e.message) || e.name === 'TypeError'
                 || /stream ended without result/i.test(e.message)) {
        // Connection-level failure. If the stream had already STARTED (we saw
        // progress events), the backend keeps extracting after a drop and
        // saves the finished project server-side (disconnect survival,
        // 2026-07-28 — Railway's edge cut a live prod stream ~10 min in).
        // Tell the truth instead of "check your connection": the work is
        // continuing and the project will appear in the list.
        userMessage = streamStartedRef.current
          ? t('newProject.errStreamLostButRunning')
          : t('newProject.errNetwork');
        // THE CONNECTION DIED, NOT THE WORK. The server finishes the extraction
        // detached and saves it under the id it announced at stream start, so
        // instead of dead-ending the user we WAIT for that project to appear,
        // attach the PDF the browser still holds, and land them in the
        // workspace — the pre-prod experience, over a connection that dropped.
        // (2026-07-28: Railway's edge cut two consecutive 17-page runs.)
        if (streamStartedRef.current && recoveryIdRef.current) {
          // Same live-screen treatment as the deliberate handoff above: an
          // unplanned drop is equally survivable, so it gets the same UI.
          setStreamPhase('finishing');
          setRecovering(true);
          const ok = await waitForRecoveredProject(recoveryIdRef.current, {
            onTick: (s) => setRecoverySec(s),
            isCancelled: () => abortReasonRef.current === 'user',
            // Scaled to the size the preflight measured: a 60-page project
            // outlives the historical fixed 40 min, and the client giving up
            // first turns a healthy run into a reported failure.
            limitMs: pollLimitMs(preflight),
          });
          if (ok) {
            stopElapsed();
            try { await savePdf(ok.id, file); } catch { /* IndexedDB best-effort */ }
            uploadPdfToBackend(ok.id, file).catch(() => {});
            // This project was built and saved SERVER-side, so it never passed
            // through the payload-level auto price fill above. Hand the job to
            // the project page. (2026-09-02)
            markPriceFillPending(ok.id);
            queryClient.invalidateQueries({ queryKey: ['projects'] });
            notifyAnalysisDone(t);
            navigate(`/project/${ok.id}`);
            return;
          }
          setRecovering(false);
        }
        stopElapsed();
      } else {
        userMessage = e.message || t('newProject.errUnknown');
      }
      stopElapsed();   // idempotent — covers the branches that never polled
      setRecovering(false);
      setError(userMessage);
      setIsProcessing(false);
      setStatus('');
    }
  };

  if (isProcessing) {
    const isStreaming = streamPhase != null;
    return (
      <div className="p-6 lg:p-8 max-w-2xl mx-auto">
        {isStreaming ? (
          <ProcessingStateStream
            phase={streamPhase}
            progress={streamProgress}
            elapsed={streamElapsed}
            recovering={recovering}
            recoverySec={recoverySec}
            estMinutes={preflight?.est_minutes || ''}
            error={error}
          />
        ) : (
          <ProcessingState />
        )}
        {!isStreaming && status && !error && (
          <p className="text-center text-xs text-muted-foreground mt-2">{status}</p>
        )}
        {abortController && !error && (
          <div className="text-center mt-4">
            <Button
              variant="outline"
              size="sm"
              title={t('newProject.cancelTitle')}
              onClick={() => {
                abortController.abort();
                setError(t('newProject.abortedByUser'));
                setIsProcessing(false);
                setAbortController(null);
              }}
            >
              {t('newProject.cancel')}
            </Button>
          </div>
        )}
        {error && (
          <div className="mt-4 p-4 bg-destructive/10 border border-destructive/20 rounded-lg text-center">
            <p className="text-destructive text-sm">{error}</p>
            <Button
              variant="outline"
              className="mt-3"
              onClick={() => { setIsProcessing(false); setError(null); }}
            >
              {t('newProject.retry')}
            </Button>
          </div>
        )}
      </div>
    );
  }

  return (
    <div className="p-6 lg:p-8 max-w-2xl mx-auto">
      {/* Phase 7 — paywall block. `paywall` stays null unless billing is on and
          the backend refused creation, so nothing mounts when the flag is off. */}
      <UpgradeDialog
        reason={paywall?.reason || null}
        message={paywall?.message}
        onClose={() => setPaywall(null)}
        onRetry={() => { setPaywall(null); handleCreate(); }}
      />

      <Link to="/" className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors mb-6">
        <ArrowLeft className="w-4 h-4" />
        {t('newProject.backToProjects')}
      </Link>

      <h1 className="text-2xl font-bold text-foreground mb-1">{t('newProject.title')}</h1>
      <p className="text-sm text-muted-foreground mb-8">
        {t('newProject.subtitle')}
      </p>

      {error && (
        <div className="mb-4 p-3 bg-destructive/10 border border-destructive/20 rounded-lg text-sm text-destructive">
          {error}
        </div>
      )}

      <div className="space-y-6">
        {/* Project type selector */}
        <div>
          <Label className="text-sm text-muted-foreground mb-2 block">{t('newProject.typeLabel')}</Label>
          <div className="grid grid-cols-1 gap-2">
            {PROJECT_TYPES.map(pt => (
              <button
                key={pt.id}
                onClick={() => setProjType(pt.id)}
                title={t(`newProject.typeTitles.${pt.id}`, { defaultValue: t(`newProject.types.${pt.id}.desc`) })}
                aria-pressed={projTypeChoice === pt.id}
                className={`p-3 rounded-lg border text-left transition-colors ${
                  projTypeChoice === pt.id
                    ? 'border-primary bg-primary/5 text-foreground'
                    : 'border-border bg-card text-muted-foreground hover:border-foreground/30'
                }`}
              >
                <p className="text-sm font-semibold">{t(`newProject.types.${pt.id}.label`)}</p>
                <p className="text-xs mt-0.5 opacity-70">{t(`newProject.types.${pt.id}.desc`)}</p>
              </button>
            ))}
          </div>

          {/* Advanced — paslėpti tipai */}
          <button
            type="button"
            onClick={() => setShowAdvancedTypes(v => !v)}
            title={t('newProject.otherTypesTitle')}
            aria-expanded={showAdvancedTypes}
            className="mt-2 text-xs text-muted-foreground hover:text-foreground underline-offset-2 hover:underline"
          >
            {showAdvancedTypes ? t('newProject.hideOtherTypes') : t('newProject.showOtherTypes')}
          </button>

          {showAdvancedTypes && (
            <div className="mt-2 grid grid-cols-2 sm:grid-cols-3 gap-2">
              {ADVANCED_PROJECT_TYPES.map(pt => (
                <button
                  key={pt.id}
                  onClick={() => setProjType(pt.id)}
                  title={t(`newProject.typeTitles.${pt.id}`, { defaultValue: t(`newProject.types.${pt.id}.desc`) })}
                  aria-pressed={projTypeChoice === pt.id}
                  className={`p-2.5 rounded-lg border text-left transition-colors ${
                    projTypeChoice === pt.id
                      ? 'border-primary bg-primary/5 text-foreground'
                      : 'border-border bg-card text-muted-foreground hover:border-foreground/30'
                  }`}
                >
                  <p className="text-xs font-semibold">{t(`newProject.types.${pt.id}.label`)}</p>
                  <p className="text-[10px] mt-0.5 opacity-70">{t(`newProject.types.${pt.id}.desc`)}</p>
                </button>
              ))}
            </div>
          )}
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <Label htmlFor="project-name" className="text-sm text-muted-foreground">{t('newProject.nameLabel')}</Label>
            <Input
              id="project-name"
              placeholder={t('newProject.namePlaceholder')}
              title={t('newProject.nameTitle')}
              value={projectName}
              onChange={(e) => setProjectName(e.target.value)}
              className="mt-1.5 bg-card border-border"
            />
          </div>
          <div>
            <Label htmlFor="company-name" className="text-sm text-muted-foreground">{t('newProject.companyLabel')}</Label>
            <Input
              id="company-name"
              placeholder={t('newProject.companyPlaceholder')}
              title={t('newProject.companyTitle')}
              value={companyName}
              onChange={(e) => setCompanyName(e.target.value)}
              className="mt-1.5 bg-card border-border"
            />
          </div>
        </div>

        <div>
          <Label className="text-sm text-muted-foreground mb-1.5 block">{t('newProject.pdfLabel')}</Label>
          <UploadZone
            onFileSelect={handleFileSelect}
            accept=".pdf"
            label={t('newProject.uploadLabel')}
            resetToken={uploadResetToken}
          />
          {/* Five seconds of looking, before twenty-five minutes of paying. */}
          <PreflightCard
            card={card}
            loading={preflightBusy}
            onContinue={handleCreate}
            onPickAnother={clearChosenFile}
            onContinueAnyway={() => handleCreate({ ackBlock: true })}
          />
        </div>

        {/* ── Trys klausimai, visi su numatytais atsakymais (design §E1).
               Only for an interior project — the hidden advanced types have
               their own maths and none of these three answers reaches them. */}
        {projTypeChoice === 'interior' && (
          <div className="space-y-5 border-t border-border pt-5">

            {/* 1 · Koks objektas? */}
            <fieldset>
              <legend className="text-foreground font-medium" style={{ fontSize: 16 }}>
                {t('newProject.q.objectLabel')}
              </legend>
              <p className="text-muted-foreground mt-0.5" style={{ fontSize: 14 }}>
                {t('newProject.q.objectNote')}
              </p>
              <div className="mt-2 flex flex-wrap gap-2">
                {['butas', 'namas', 'komercines'].map((id) => (
                  <button
                    key={id}
                    type="button"
                    onClick={() => setObjektas(id)}
                    aria-pressed={objektas === id}
                    title={t(`newProject.q.object.${id}`)}
                    className={`rounded border transition-colors ${
                      objektas === id
                        ? 'border-primary bg-primary/10 text-foreground font-medium'
                        : 'border-border bg-card text-muted-foreground hover:border-foreground/30'
                    }`}
                    style={{ minHeight: 44, padding: '0 16px', fontSize: 15 }}
                  >
                    {t(`newProject.q.object.${id}`)}
                  </button>
                ))}
              </div>
            </fieldset>

            {/* 2 · Lubų aukštis, jei žinote */}
            <div>
              <Label htmlFor="ceiling-height" className="text-foreground font-medium" style={{ fontSize: 16 }}>
                {t('newProject.q.ceilingLabel')}
              </Label>
              <div className="mt-2 flex items-center gap-2 flex-wrap">
                <Input
                  id="ceiling-height"
                  type="text"
                  inputMode="decimal"
                  value={ceilingHeight}
                  onChange={(e) => setCeilingHeight(e.target.value)}
                  placeholder={t('newProject.q.ceilingPlaceholder')}
                  title={t('newProject.q.ceilingNote')}
                  className="bg-card border-border"
                  style={{ width: 130, minHeight: 44, fontSize: 15 }}
                />
                <span className="text-muted-foreground" style={{ fontSize: 15 }}>m</span>
              </div>
              <p className="text-muted-foreground mt-1.5" style={{ fontSize: 14 }}>
                {t('newProject.q.ceilingNote')}
              </p>
            </div>

            {/* 3 · Ką skaičiuoti? — every one ticked; unticking says what it costs */}
            <fieldset>
              <legend className="text-foreground font-medium" style={{ fontSize: 16 }}>
                {t('newProject.q.familiesLabel')}
              </legend>
              <div className="mt-2 flex flex-wrap gap-2">
                {WORK_FAMILIES.map((id) => {
                  const on = families.has(id);
                  return (
                    <button
                      key={id}
                      type="button"
                      role="checkbox"
                      aria-checked={on}
                      onClick={() => setFamilies((prev) => {
                        const next = new Set(prev);
                        if (next.has(id)) next.delete(id); else next.add(id);
                        return next;
                      })}
                      title={t(`newProject.q.family.${id}`)}
                      className={`inline-flex items-center gap-2 rounded border transition-colors ${
                        on
                          ? 'border-primary bg-primary/10 text-foreground font-medium'
                          : 'border-border bg-card text-muted-foreground hover:border-foreground/30'
                      }`}
                      style={{ minHeight: 44, padding: '0 14px', fontSize: 15 }}
                    >
                      <span
                        aria-hidden
                        className={`inline-flex items-center justify-center rounded-sm border ${
                          on ? 'border-primary bg-primary text-primary-foreground' : 'border-border'
                        }`}
                        style={{ width: 18, height: 18, fontSize: 12 }}
                      >
                        {on ? '✓' : ''}
                      </span>
                      {t(`newProject.q.family.${id}`)}
                    </button>
                  );
                })}
              </div>
              <p className="text-muted-foreground mt-1.5" style={{ fontSize: 14 }}>
                {families.size === WORK_FAMILIES.length
                  ? t('newProject.q.familiesAllNote')
                  : t('newProject.q.familiesSomeOffNote')}
              </p>
            </fieldset>

            {/* 4 · Lubos / 5 · Sienų plotas — the two conventions that decide the
                biggest rows; each option says what it does to the sąmata. */}
            {[
              { key: 'lubos', label: t('newProject.q.lubosLabel'), options: LUBOS_CHOICES,
                value: lubosChoice, set: setLubosChoice,
                text: (o) => t(`newProject.q.lubos.${o}`), note: (v) => t(`newProject.q.lubosNote.${v}`) },
              { key: 'sienos_angos', label: t('newProject.q.sienosLabel'), options: SIENOS_ANGOS_CHOICES,
                value: sienosAngos, set: setSienosAngos,
                text: (o) => t(`newProject.q.sienos.${o}`), note: (v) => t(`newProject.q.sienosNote.${v}`) },
            ].map((q) => (
              <fieldset key={q.key}>
                <legend className="text-foreground font-medium" style={{ fontSize: 16 }}>{q.label}</legend>
                <div role="radiogroup" aria-label={q.label} className="mt-2 flex flex-wrap gap-2">
                  {q.options.map((o) => {
                    const on = q.value === o;
                    return (
                      <button
                        key={o}
                        type="button"
                        role="radio"
                        aria-checked={on}
                        onClick={() => q.set(o)}
                        className={`inline-flex items-center rounded border transition-colors ${
                          on
                            ? 'border-primary bg-primary/10 text-foreground font-medium'
                            : 'border-border bg-card text-muted-foreground hover:border-foreground/30'
                        }`}
                        style={{ minHeight: 44, padding: '0 14px', fontSize: 15 }}
                      >
                        {q.text(o)}
                      </button>
                    );
                  })}
                </div>
                <p className="text-muted-foreground mt-1.5" style={{ fontSize: 14 }}>
                  {q.note(q.value)}
                  {rememberedKeys.has(q.key) && ` ${t('newProject.q.rememberedNote')}`}
                </p>
              </fieldset>
            ))}
          </div>
        )}

        <div>
          <Button
            onClick={handleCreate}
            disabled={!file || card?.blocked}
            title={
              card?.blocked ? card.reason
                : file ? t('newProject.startAnalysisTitle')
                  : t('newProject.startAnalysisDisabledTitle')
            }
            className="w-full bg-primary hover:bg-primary/90 text-primary-foreground font-semibold"
            style={{ minHeight: 52, fontSize: 17 }}
          >
            <Rocket className="w-5 h-5 mr-2" />
            {t('newProject.startAnalysis')}
          </Button>
          {/* Time expectation. Extraction is minutes, not seconds (an Objektas A-class
              drawing runs ~19 min — see IDLE_ABORT_MS above). A bare „Skaičiuoti
              kiekius" reads as instant, so contractors closed the tab.
              (2026-07-28 explainability pass.)
              Hidden once the preflight card is up: this line gives a generic
              duration, and printing it under a card that just said "virš
              valandos" is worse than saying nothing. */}
          {!card && (
            <p className="mt-2 text-muted-foreground text-center" style={{ fontSize: 14 }}>
              {t('newProject.startAnalysisHint')}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
