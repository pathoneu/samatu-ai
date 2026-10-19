import React, { useState, useRef, useEffect } from 'react';
import { useNavigate, Link } from 'react-router';
import { useTranslation } from 'react-i18next';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Button } from '@/components/ui/button';
import { ArrowLeft, Rocket } from 'lucide-react';
import UploadZone from '@/components/upload/UploadZone';
import PreflightCard from '@/components/upload/PreflightCard';
import ProcessingState from '@/components/upload/ProcessingState';
import ProcessingStateStream from '@/components/upload/ProcessingStateStream';
import RunTeaching, { ReadScopeCard } from '@/components/upload/RunTeaching';
import { fetchPreflight, preflightCard, pollLimitMs } from '@/lib/preflight';
import { WORK_FAMILIES, filterRowsByFamilies } from '@/lib/workFamilies';
import { LUBOS_CHOICES, SIENOS_ANGOS_CHOICES, scopeForBackend } from '@/lib/scope';
import { rememberProjectScope, remembered } from '@/lib/scopeMemory';
import {
  createProject, updateProject, getPriceLists, pullPriceListsFromBackend,
  markPriceFillPending, refreshProjectFromBackend, flushProjectSaves,
} from '@/lib/projectStore';
import {
  projectMeta, interiorStreamForm, metaToRestore, META_TEXT_MAX,
} from '@/lib/newProjectForm';
import { autoFillFromDefaultPriceList, describeAmbiguous } from '@/lib/applyPriceList';
import { CONF_RAUDONA, normalizeConfidence } from '@/lib/confidence';
import { savePdf, uploadPdfToBackend } from '@/lib/pdfStore';
import { runExtraction, ExtractionStopped, HARD_ABORT_MS } from '@/lib/extractionRun';
import { newRunEnding } from '@/lib/runEndNotice';
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
  const overrides = rulesOverrideFor(scope);
  if (overrides) fd.append('rules_override', JSON.stringify(overrides));
}

/** The `rules_override` object itself — null when there is nothing to say. */
function rulesOverrideFor(scope) {
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
  return Object.keys(overrides).length ? overrides : null;
}

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
  // A reading the SERVER goes on with (the connection dropped, or his cancel
  // after it started): news, not an error — shown in a neutral box with the way
  // to the projects list, where the project will appear (lib/runEndNotice.js).
  const [notice, setNotice]             = useState(null);
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
  // Why a request stopped on THIS side: 'timeout' (the non-streaming paths'
  // ceiling) or 'user' (the cancel button). The interior stream keeps its own
  // reasons — stall, ceiling, edge hand-off — in lib/extractionRun.js.
  const abortReasonRef = useRef(null);
  // The interior run's id once the server announced it — i.e. the reading has
  // STARTED there. A cancel after that does not stop it: the server finishes
  // the reading and saves the project, which then appears in „Projektai"
  // (backend _drain_gen). The cancel's text has to say so.
  const runIdRef = useRef(null);

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
    // His name, company, object and ceiling height — one copy for both hands
    // that may save this project: this page when the result arrives, the
    // server when the stream goes first (lib/newProjectForm.js).
    const meta = projectMeta({ name: projectName, companyName, objektas, ceilingHeight });
    setError(null);
    setNotice(null);
    setStatus(t('newProject.statusUploading'));
    setIsProcessing(true);
    setStreamPhase(null);
    setStreamProgress({
      rooms: [], zoomDone: 0, zoomTotal: 0, pageCount: null, validationWarning: null,
    });
    setStreamElapsed(0);
    setRecovering(false);
    setRecoverySec(0);

    // Naujas controller — vartotojas gali atšaukti su mygtuku
    const controller = new AbortController();
    setAbortController(controller);
    abortReasonRef.current = null; // 'timeout' | 'user' | null
    runIdRef.current = null;

    // Generic per-second elapsed counter (also used by streaming UI).
    const elapsedStart = Date.now();
    elapsedTimerRef.current = setInterval(() => {
      setStreamElapsed(Math.floor((Date.now() - elapsedStart) / 1000));
    }, 1000);

    // A project the SERVER built and saved after the connection went (the
    // disconnect path): attach the drawing the browser still holds and land on
    // it, exactly as a healthy run would.
    const landRecoveredProject = async (p) => {
      stopElapsed();
      // The server saved it with the form's fields (`project_meta`). One that
      // did not — a backend older than this page, mid-deploy — named it after
      // the PDF: put his back before he sees it. Normally there is nothing to do.
      const restore = metaToRestore(p, meta);
      if (Object.keys(restore).length) {
        try {
          if (await refreshProjectFromBackend(p.id)) {
            updateProject(p.id, restore);
            await flushProjectSaves();
          }
        } catch { /* the project itself is saved; the name stays editable */ }
      }
      try { await savePdf(p.id, file); } catch { /* IndexedDB best-effort */ }
      uploadPdfToBackend(p.id, file).catch(() => {});
      // This project was built and saved SERVER-side, so it never passed
      // through the payload-level auto price fill below. Hand the job to
      // the project page. (2026-09-02)
      markPriceFillPending(p.id);
      queryClient.invalidateQueries({ queryKey: ['projects'] });
      notifyAnalysisDone(t);
      navigate(`/project/${p.id}`);
    };

    // Every progress event of the interior stream → the progress screen.
    const onStreamEvent = (ev) => {
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
    };

    try {
      // Extraction time scales with project size — a real Objektas A-class drawing
      // runs ~19 min, well past the old fixed 600 s cap that made contractors
      // watch the browser abort a HEALTHY extraction (pre-prod QA 2026-07-15).
      // The interior stream's three timers — stall, absolute ceiling, and the
      // 840 s edge hand-off before Railway's 900 s cut — live in
      // lib/extractionRun.js. The non-streaming paths keep only the ceiling.
      const timeoutId = projTypeChoice === 'interior' ? null
        : setTimeout(() => { abortReasonRef.current = 'timeout'; controller.abort(); }, HARD_ABORT_MS);
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
          setStreamPhase('rendering');
          const run = await runExtraction(
            interiorStreamForm(file, {
              interiorSubtype, rulesOverride: rulesOverrideFor(scopeChoice()), meta,
            }),
            {
              controller,
              onEvent: (ev) => {
                if (ev?.event === 'recovery_id' && ev.project_id) runIdRef.current = ev.project_id;
                onStreamEvent(ev);
              },
              // The socket is gone — or we let go before the proxy's 900 s
              // cut — and the server keeps reading. The extraction is HEALTHY,
              // so the screen stays alive: the step animation, the room list
              // and the running clock, just in the 'finishing' phase. The cancel
              // button goes: there is no request left to cancel.
              onHandoff: () => {
                setStreamPhase('finishing');
                setRecovering(true);
                setAbortController(null);
              },
              onPollTick: (s) => setRecoverySec(s),
              isCancelled: () => abortReasonRef.current === 'user',
              // Scaled to the size the preflight measured: a 60-page project
              // outlives the historical fixed 40 min, and the client giving up
              // first turns a healthy run into a reported failure.
              waitLimitMs: pollLimitMs(preflight),
            },
          );
          if (run.status === 'recovered' && run.project) {
            await landRecoveredProject(run.project);
            return;
          }
          // Interrupted (the server restarted under it), failed, lost, or a
          // run the server still reports as running after the wait — the
          // catch below says which, honestly (lib/extractionRun.runEndText).
          if (run.status !== 'done') throw Object.assign(new Error(run.status), { runEnd: run.status });
          json = run.result;
          projType = 'interior';
          res = { ok: true };
        } else {
          ({ json, res, projType } = await detectAndExtract(
            file, projTypeChoice, controller.signal,
            { interiorSubtype, scope: scopeChoice() },
          ));
        }
        setStatus(t('newProject.statusSaving'));
      } finally {
        if (timeoutId) clearTimeout(timeoutId);
        if (statusTimer) clearInterval(statusTimer);
        // THE CLOCK OUTLIVED THE CONNECTION (2026-07-29) and still does: the
        // post-hand-off wait now happens INSIDE runExtraction, so by the time
        // this block runs the run is over one way or the other. elapsedStart
        // is wall-clock, so the counter stayed accurate across the hand-off.
        stopElapsed();
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
        project = createProject(await withAutoPrices({
          ...json,
          darbu_sarasas:   keptRows,
          // company_name, objektas_tipas and „Lubų aukštis, jei žinote" — the
          // last kept as the project's own default so the Nustatymai height
          // field opens on HIS number instead of 2,80. It is not applied
          // behind his back: the quantities still come from what the drawing
          // said, and one click in Nustatymai pushes his value through the
          // live recompute. The same `meta` the server saves when the stream
          // goes first.
          ...meta,
          name:            meta.name || json.projektas || t('newProject.defaultNameInterior'),
          tipas:           'interjeras',
          skaiciuoti_families: [...families],
          _apimtis:        scopeForBackend(scopeChoice()),
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
          // Pages the reading could not finish — rows from them may be missing.
          ...(json.warnings?.length ? { warnings: json.warnings } : {}),
        }, t));
        (json.warnings || []).forEach((w) => toast.warning(w.message, { duration: 12000 }));
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
      let noticeMessage = null;
      const ended = e?.runEnd || (e instanceof ExtractionStopped ? e.reason : null);
      if (ended) {
        // The interior run ended with nothing to show. Honest per ending
        // (lib/extractionRun.runEndText): a STALLED stream is not the user's
        // cancel; and only a run the SERVER still reports as running may be
        // described as continuing — one the server reports interrupted (a
        // redeploy killed it), failed or lost says it stopped and can be
        // started again, instead of „nekartokite įkėlimo" about a project that
        // will never appear. A drop before the run's id arrived means nothing
        // started on the server: that is a connection problem, said as one.
        // His cancel after the start: the server still finishes and saves
        // the project, so the text says it will appear — not „try again".
        // The two endings the server goes on with are a notice, not an error.
        const end = newRunEnding(ended, { started: !!e?.recoveryId });
        if (end.tone === 'notice') noticeMessage = t(end.key);
        else userMessage = t(end.key);
      } else if (e.name === 'AbortError') {
        // The non-streaming paths: their ceiling, or the cancel button.
        userMessage = abortReasonRef.current === 'timeout' ? t('newProject.errTimeout')
          : abortReasonRef.current === 'user' ? t('newProject.abortedByUser')
          : t('newProject.errAborted');
      } else if (/network|fetch/i.test(e.message) || e.name === 'TypeError') {
        userMessage = t('newProject.errNetwork');
      } else {
        userMessage = e.message || t('newProject.errUnknown');
      }
      stopElapsed();   // idempotent — covers every branch
      setRecovering(false);
      setError(noticeMessage ? null : userMessage);
      setNotice(noticeMessage);
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
        {isStreaming && !error && (
          <RunTeaching
            className="mt-2"
            phase={streamPhase}
            progress={streamProgress}
            elapsed={streamElapsed}
            started={recovering || Boolean(runIdRef.current)}
            estMinutes={preflight?.est_minutes || ''}
          />
        )}
        {!isStreaming && status && !error && (
          <p className="text-center text-xs text-muted-foreground mt-2">{status}</p>
        )}
        {abortController && !error && (
          <div className="text-center mt-4">
            <Button
              variant="outline"
              size="sm"
              // The interior stream: a started reading is finished and saved by
              // the server anyway. The other paths: nothing is saved anywhere.
              title={t(isStreaming ? 'newProject.cancelTitle' : 'newProject.cancelTitleNoStream')}
              onClick={() => {
                abortReasonRef.current = 'user';
                abortController.abort();
                const end = isStreaming
                  ? newRunEnding('user', { started: !!runIdRef.current })
                  : { key: 'newProject.abortedByUser', tone: 'error' };
                if (end.tone === 'notice') setNotice(t(end.key));
                else setError(t(end.key));
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

      {/* before the first run: what is read and what is not (C2) — never blocks, „Supratau" closes it */}
      <ReadScopeCard className="mb-6" />

      {error && (
        <div className="mb-4 p-3 bg-destructive/10 border border-destructive/20 rounded-lg text-sm text-destructive">
          {error}
        </div>
      )}

      {notice && (
        <div
          className="mb-4 p-3 bg-card border border-border rounded-lg text-sm text-foreground"
          role="status"
          data-testid="run-continues-notice"
        >
          <p>{notice}</p>
          <Button asChild variant="outline" size="sm" className="mt-3">
            <Link to="/dashboard">{t('newProject.backToProjects')}</Link>
          </Button>
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
              maxLength={META_TEXT_MAX}
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
              maxLength={META_TEXT_MAX}
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
