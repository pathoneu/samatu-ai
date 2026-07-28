import React, { useState, useRef } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Button } from '@/components/ui/button';
import { ArrowLeft, Rocket } from 'lucide-react';
import UploadZone from '@/components/upload/UploadZone';
import ProcessingState from '@/components/upload/ProcessingState';
import ProcessingStateStream from '@/components/upload/ProcessingStateStream';
import { createProject, updateProject } from '@/lib/projectStore';
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
    // V8: užkrauti vartotojo nustatymus (rules_override)
    fd.append('interior_subtype', interiorSubtype);
    try {
      const prefs = loadPrefs();
      if (prefs && prefs.setup_completed) {
        fd.append('rules_override', JSON.stringify({
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
        }));
      }
    } catch (e) {
      console.warn('Could not load user prefs', e);
    }
  } else {
    fd.append('file', file);
  }

  const res = await fetch(`${API}${endpoint}`, { method: 'POST', credentials: 'include', body: fd, signal });
  const json = await res.json();
  return { json, res, projType };
}

// SM01: streaming variant for interior projects. Wires SSE events to onProgress
// and resolves with the same {json, projType} shape the non-streaming path
// returned, so downstream code can keep its branching.
async function streamInteriorExtract(file, signal, opts, onProgress) {
  const fd = new FormData();
  fd.append('files', file);
  fd.append('interior_subtype', opts.interiorSubtype || 'naujas');
  try {
    const prefs = loadPrefs();
    if (prefs && prefs.setup_completed) {
      fd.append('rules_override', JSON.stringify({
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
      }));
    }
  } catch (e) {
    console.warn('Could not load user prefs', e);
  }

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
 * Polls every 10 s for up to 15 min — comfortably past the longest observed
 * extraction (~21 min total, of which the drop happens near the end) — and
 * gives up quietly, leaving the on-screen message that the analysis continues.
 */
async function waitForRecoveredProject(projectId, { onTick, isCancelled } = {}) {
  const started = Date.now();
  const LIMIT_MS = 15 * 60 * 1000;
  while (Date.now() - started < LIMIT_MS) {
    if (isCancelled?.()) return null;
    try {
      const res = await fetch(`${API}/api/projects/${projectId}`, { credentials: 'include' });
      if (res.ok) {
        const p = await res.json();
        if (p && (p.patalpos?.length || p.darbu_sarasas?.length)) return p;
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
  const [projTypeChoice, setProjType]   = useState('interior');
  // Default interior subtype, no setter — UI selector removed 2026-05-13.
  const [interiorSubtype] = useState('naujas');
  const [showAdvancedTypes, setShowAdvancedTypes] = useState(false);
  const [abortController, setAbortController] = useState(null);
  const [isProcessing, setIsProcessing] = useState(false);
  const [error, setError]               = useState(null);
  const [status, setStatus]             = useState('');
  // SM01 streaming progress state
  const [streamPhase, setStreamPhase]     = useState(null); // null | 'rendering' | 'pass1' | 'zoom' | 'post'
  const [streamProgress, setStreamProgress] = useState({
    rooms: [], zoomDone: 0, zoomTotal: 0, pageCount: null,
  });
  const [streamElapsed, setStreamElapsed] = useState(0);
  const elapsedTimerRef = useRef(null);
  const abortReasonRef = useRef(null);
  // True once the SSE stream has begun — read in the catch block, where the
  // `streamPhase` STATE is stale (captured at click time). See the assignment.
  const streamStartedRef = useRef(false);
  // Project id the server announces at stream start; used to WAIT for the
  // result when the connection drops mid-extraction instead of erroring out.
  const recoveryIdRef = useRef(null);

  const handleCreate = async () => {
    if (!file) { setError(t('newProject.errNoPdf')); return; }
    setError(null);
    setStatus(t('newProject.statusUploading'));
    setIsProcessing(true);
    setStreamPhase(null);
    streamStartedRef.current = false;
    setStreamProgress({ rooms: [], zoomDone: 0, zoomTotal: 0, pageCount: null });
    setStreamElapsed(0);

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
      // Extraction time scales with project size — a real Beržų-class drawing
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
            { interiorSubtype },
            (ev) => {
              bumpIdle();  // every progress event resets the stall timer
              // First event of every stream: the id the server will save under
              // if this connection dies. Held so the catch block can wait for
              // the project instead of dead-ending the user. (2026-07-28)
              if (ev.event === 'recovery_id' && ev.project_id) {
                recoveryIdRef.current = ev.project_id;
              }
              if (ev.event === 'started') {
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
          ));
        }
        setStatus(t('newProject.statusSaving'));
      } finally {
        clearTimeout(timeoutId);
        if (idleTimer) clearTimeout(idleTimer);
        if (statusTimer) clearInterval(statusTimer);
        if (elapsedTimerRef.current) {
          clearInterval(elapsedTimerRef.current);
          elapsedTimerRef.current = null;
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
        project = createProject({
          name:         projectName || json.projektas || t('newProject.defaultNameConstruction'),
          company_name: companyName,
          tipas:        projType,
          ...json,
          rows:         [],
          total_rows:   0,
          total_value:  0,
          status:       'ready',
        });
      } else if (projType === 'interior') {
        if (!json.patalpos) throw new Error(t('newProject.errUnexpectedFormat'));
        // Zero-room result = the most common first-run dead end (wrong PDF type:
        // a photo, a KŽ table, a facade-only sheet). Surface a recoverable message
        // instead of silently creating an empty project. (2026-06-19)
        if (json.patalpos.length === 0) {
          throw new Error(t('newProject.errNoRooms'));
        }
        project = createProject({
          ...json,
          name:            projectName || json.projektas || t('newProject.defaultNameInterior'),
          company_name:    companyName,
          tipas:           'interjeras',
          rows:            [],
          total_rows:      json.patalpos.length,
          total_value:     0,
          status:          'ready',
        });
      } else {
        if (!json.eilutes) throw new Error(t('newProject.errUnexpectedFormat'));
        const rows = json.eilutes.map(row => ({
          ...row,
          kaina: 0,
          suma:  0,
          warning: row.confidence === 'low' ? t('newProject.warnLowConfidence')
                 : !row.mato_vnt ? t('newProject.warnMissingUnit') : '',
        }));
        project = createProject({
          name:         projectName || json.projektas || t('newProject.defaultNameKz'),
          company_name: companyName,
          tipas:        'kz',
          rows,
          total_rows:   rows.length,
          total_value:  0,
          status:       'ready',
          vat_rate:     21,
        });
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
        // used to read as if the USER cancelled it).
        userMessage = abortReasonRef.current === 'stalled' ? t('newProject.errStalled')
          : abortReasonRef.current === 'timeout' ? t('newProject.errTimeout')
          : t('newProject.errAborted');
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
          const ok = await waitForRecoveredProject(recoveryIdRef.current, {
            onTick: (s) => setStatus(t('newProject.statusRecovering', { s })),
            isCancelled: () => abortReasonRef.current === 'user',
          });
          if (ok) {
            try { await savePdf(ok.id, file); } catch { /* IndexedDB best-effort */ }
            uploadPdfToBackend(ok.id, file).catch(() => {});
            queryClient.invalidateQueries({ queryKey: ['projects'] });
            navigate(`/project/${ok.id}`);
            return;
          }
        }
      } else {
        userMessage = e.message || t('newProject.errUnknown');
      }
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
          <UploadZone onFileSelect={setFile} accept=".pdf" label={t('newProject.uploadLabel')} />
        </div>

        <div>
          <Button
            onClick={handleCreate}
            disabled={!file}
            title={file ? t('newProject.startAnalysisTitle') : t('newProject.startAnalysisDisabledTitle')}
            className="w-full bg-primary hover:bg-primary/90 text-primary-foreground font-semibold h-12"
          >
            <Rocket className="w-5 h-5 mr-2" />
            {t('newProject.startAnalysis')}
          </Button>
          {/* Time expectation. Extraction is minutes, not seconds (a Beržų-class
              drawing runs ~19 min — see IDLE_ABORT_MS above). A bare "Pradėti
              analizę" + rocket reads as instant, so contractors closed the tab.
              (2026-07-28 explainability pass.) */}
          <p className="mt-2 text-xs text-muted-foreground text-center">
            {t('newProject.startAnalysisHint')}
          </p>
        </div>
      </div>
    </div>
  );
}
