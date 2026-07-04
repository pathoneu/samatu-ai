import React, { useState, useRef } from 'react';
import { useNavigate, Link } from 'react-router-dom';
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

// Pirmoji versija: Interjero projektas yra DEFAULT. Kiti tipai (KŽ, Fasadai,
// Stogas, Žemės, Betonas) — paslėpti į "Kitas tipas" advanced.
const PROJECT_TYPES = [
  { id: 'interior', label: 'Interjero projektas', desc: 'Apdailos kiekiai (rekomenduojama)' },
];

// Advanced tipai — paslėpti pagal nutylėjimą, vartotojas atskleidžia spaudžiant.
const ADVANCED_PROJECT_TYPES = [
  { id: 'auto',     label: 'Automatinis',         desc: 'AI atpažins tipą' },
  { id: 'kz',       label: 'Kiekių žiniaraštis',  desc: 'KŽ lentelė (jei jau turi paruoštą)' },
  { id: 'fasadas',  label: 'Fasadai',             desc: 'ETICS skaičiai' },
  { id: 'stogas',   label: 'Stogas',              desc: 'Stogo kiekiai' },
  { id: 'zeme',     label: 'Žemės darbai',        desc: 'Iškasa, tranšėjos' },
  { id: 'betonas',  label: 'Betonas',             desc: 'Betono kiekiai' },
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

export default function NewProject() {
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

  const handleCreate = async () => {
    if (!file) { setError('Pasirinkite PDF failą'); return; }
    setError(null);
    setStatus('Siunčiama...');
    setIsProcessing(true);
    setStreamPhase(null);
    setStreamProgress({ rooms: [], zoomDone: 0, zoomTotal: 0, pageCount: null });
    setStreamElapsed(0);

    // Naujas controller — vartotojas gali atšaukti su mygtuku
    const controller = new AbortController();
    setAbortController(controller);

    // Generic per-second elapsed counter (also used by streaming UI).
    const elapsedStart = Date.now();
    elapsedTimerRef.current = setInterval(() => {
      setStreamElapsed(Math.floor((Date.now() - elapsedStart) / 1000));
    }, 1000);

    try {
      // Realus laikas: 30-90s mažiems PDF, iki 8-10 min dideliems projektams
      // su two-pass zoom (P1 65 psl. + 15 zoom call'ų ≈ 8 min worst case).
      const timeoutId = setTimeout(() => controller.abort(), 600_000);
      let json, res, projType;

      // Status text fallback only when NOT streaming (KŽ + construction types).
      const statusTimer = (projTypeChoice !== 'interior' && projTypeChoice !== 'auto')
        ? setInterval(() => {
            const sec = Math.floor((Date.now() - elapsedStart) / 1000);
            if (sec < 15) setStatus(`Skaitome brėžinį... (${sec}s)`);
            else if (sec < 60) setStatus(`Apdorojama... (${sec}s)`);
            else setStatus(`Sudėtingas projektas, palaukite (${sec}s)...`);
          }, 1000)
        : null;

      try {
        if (projTypeChoice === 'interior') {
          // SM01: stream the extraction so user sees progress in real time.
          setStreamPhase('rendering');
          ({ json, projType } = await streamInteriorExtract(
            file, controller.signal,
            { interiorSubtype },
            (ev) => {
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
                setError(ev.message || 'Klaida');
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
        setStatus('Išsaugoma...');
      } finally {
        clearTimeout(timeoutId);
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
          : json?.detail || `Serverio klaida (${res.status})`;
        throw new Error(msg);
      }
      // Catch backend pipeline errors that return 200 with status="error"
      if (json?.status === 'error' || json?._error) {
        throw new Error(json._error || json.error || 'Pipeline klaida (nežinoma priežastis)');
      }
      if (json.error) throw new Error(json.error);

      const CONSTRUCTION_TYPES = ['fasadas', 'stogas', 'zeme', 'betonas'];
      let project;
      if (CONSTRUCTION_TYPES.includes(projType)) {
        project = createProject({
          name:         projectName || json.projektas || 'Statybos projektas',
          company_name: companyName,
          tipas:        projType,
          ...json,
          rows:         [],
          total_rows:   0,
          total_value:  0,
          status:       'ready',
        });
      } else if (projType === 'interior') {
        if (!json.patalpos) throw new Error('Netikėtas atsakymo formatas');
        // Zero-room result = the most common first-run dead end (wrong PDF type:
        // a photo, a KŽ table, a facade-only sheet). Surface a recoverable message
        // instead of silently creating an empty project. (2026-06-19)
        if (json.patalpos.length === 0) {
          throw new Error(
            'AI nerado patalpų šiame brėžinyje. Patikrinkite, ar įkėlėte interjero / aukšto ' +
            'planą (ne nuotrauką, ne KŽ lentelę, ne fasadą). Jei tai tikrai planas — pabandykite ' +
            'dar kartą arba pridėkite patalpas rankiniu būdu.'
          );
        }
        project = createProject({
          ...json,
          name:            projectName || json.projektas || 'Interjero projektas',
          company_name:    companyName,
          tipas:           'interjeras',
          rows:            [],
          total_rows:      json.patalpos.length,
          total_value:     0,
          status:          'ready',
        });
      } else {
        if (!json.eilutes) throw new Error('Netikėtas atsakymo formatas');
        const rows = json.eilutes.map(row => ({
          ...row,
          kaina: 0,
          suma:  0,
          warning: row.confidence === 'low' ? 'Žemas AI tikslumas'
                 : !row.mato_vnt ? 'Trūksta matavimo vieneto' : '',
        }));
        project = createProject({
          name:         projectName || json.projektas || 'Naujas projektas',
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
      try {
        await savePdf(project.id, file);
      } catch (pdfErr) {
        console.warn('Nepavyko išsaugoti PDF į IndexedDB:', pdfErr);
      }
      // Fire-and-forget — neblokuojam srauto; backendas yra durabli atsarginė kopija.
      uploadPdfToBackend(project.id, file).then((ok) => {
        if (!ok) console.warn('Nepavyko įkelti PDF į backendą (liks tik naršyklėje)');
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
        userMessage = 'Užklausa atšaukta arba laiko limitas. Bandykite mažesnį PDF arba pakartokite.';
      } else if (/network|fetch/i.test(e.message)) {
        userMessage = 'Nepavyksta pasiekti serverio. Patikrinkite ryšį.';
      } else {
        userMessage = e.message || 'Nežinoma klaida';
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
              onClick={() => {
                abortController.abort();
                setError('Atšaukta vartotojo. Bandykite dar kartą.');
                setIsProcessing(false);
                setAbortController(null);
              }}
            >
              Atšaukti
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
              Bandyti dar kartą
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
        Grįžti į projektus
      </Link>

      <h1 className="text-2xl font-bold text-foreground mb-1">Naujas projektas</h1>
      <p className="text-sm text-muted-foreground mb-8">
        Įkelkite statybų projekto brėžinį (PDF). Pathon automatiškai atpažins tipą ir išskirs kiekius.
      </p>

      {error && (
        <div className="mb-4 p-3 bg-destructive/10 border border-destructive/20 rounded-lg text-sm text-destructive">
          {error}
        </div>
      )}

      <div className="space-y-6">
        {/* Project type selector */}
        <div>
          <Label className="text-sm text-muted-foreground mb-2 block">Projekto tipas</Label>
          <div className="grid grid-cols-1 gap-2">
            {PROJECT_TYPES.map(t => (
              <button
                key={t.id}
                onClick={() => setProjType(t.id)}
                className={`p-3 rounded-lg border text-left transition-colors ${
                  projTypeChoice === t.id
                    ? 'border-primary bg-primary/5 text-foreground'
                    : 'border-border bg-card text-muted-foreground hover:border-foreground/30'
                }`}
              >
                <p className="text-sm font-semibold">{t.label}</p>
                <p className="text-xs mt-0.5 opacity-70">{t.desc}</p>
              </button>
            ))}
          </div>

          {/* Advanced — paslėpti tipai */}
          <button
            type="button"
            onClick={() => setShowAdvancedTypes(v => !v)}
            className="mt-2 text-xs text-muted-foreground hover:text-foreground underline-offset-2 hover:underline"
          >
            {showAdvancedTypes ? '− Paslėpti kitus tipus' : '+ Kitas projekto tipas (KŽ, fasadai, stogas, žemės darbai…)'}
          </button>

          {showAdvancedTypes && (
            <div className="mt-2 grid grid-cols-2 sm:grid-cols-3 gap-2">
              {ADVANCED_PROJECT_TYPES.map(t => (
                <button
                  key={t.id}
                  onClick={() => setProjType(t.id)}
                  className={`p-2.5 rounded-lg border text-left transition-colors ${
                    projTypeChoice === t.id
                      ? 'border-primary bg-primary/5 text-foreground'
                      : 'border-border bg-card text-muted-foreground hover:border-foreground/30'
                  }`}
                >
                  <p className="text-xs font-semibold">{t.label}</p>
                  <p className="text-[10px] mt-0.5 opacity-70">{t.desc}</p>
                </button>
              ))}
            </div>
          )}
        </div>

        <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
          <div>
            <Label htmlFor="project-name" className="text-sm text-muted-foreground">Projekto pavadinimas</Label>
            <Input
              id="project-name"
              placeholder="Pvz. Gyvenamojo namo statyba"
              value={projectName}
              onChange={(e) => setProjectName(e.target.value)}
              className="mt-1.5 bg-card border-border"
            />
          </div>
          <div>
            <Label htmlFor="company-name" className="text-sm text-muted-foreground">Įmonės pavadinimas</Label>
            <Input
              id="company-name"
              placeholder="Pvz. UAB Statyba"
              value={companyName}
              onChange={(e) => setCompanyName(e.target.value)}
              className="mt-1.5 bg-card border-border"
            />
          </div>
        </div>

        <div>
          <Label className="text-sm text-muted-foreground mb-1.5 block">Projekto PDF</Label>
          <UploadZone onFileSelect={setFile} accept=".pdf" label="PDF — statybų projekto brėžinys" />
        </div>

        <Button
          onClick={handleCreate}
          disabled={!file}
          className="w-full bg-primary hover:bg-primary/90 text-primary-foreground font-semibold h-12"
        >
          <Rocket className="w-5 h-5 mr-2" />
          Pradėti analizę
        </Button>
      </div>
    </div>
  );
}
