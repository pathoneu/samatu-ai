/**
 * ReextractButton — re-runs AI extraction on the saved PDF (Limitation 10 fix).
 *
 * Use cases:
 * - Prompt was improved since original extraction (admin updates → user wants fresh result)
 * - Original extraction had errors / missing rooms
 * - Switching rules_override drastically (full re-extract vs cheap recompute)
 *
 * Flow: confirm → load PDF blob from IndexedDB → POST /extract-interior → replace project data.
 * Cost: same as original extract (~$0.40-2 + 90-500s).
 */

import React, { useState } from 'react';
import { RefreshCw, Loader2, AlertCircle, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { getPdfBlob } from '@/lib/pdfStore';
import { updateProject } from '@/lib/projectStore';

const API = '';

export default function ReextractButton({ project, onComplete }) {
  const [confirming, setConfirming] = useState(false);
  const [extracting, setExtracting] = useState(false);
  const [progress, setProgress] = useState('');
  const [error, setError] = useState(null);

  const handleReextract = async () => {
    setError(null);
    setExtracting(true);
    setProgress('Įkeliamas PDF iš atminties...');

    try {
      const blob = await getPdfBlob(project.id);
      if (!blob) {
        throw new Error('PDF nerastas. Negalima pakartoti analizės. Sukurkite naują projektą su PDF.');
      }

      setProgress('AI analizuoja brėžinį (palaukite 3-8 min)...');
      const fd = new FormData();
      fd.append('files', blob, project.name + '.pdf');
      // Forward existing rules_override so user's prefs aren't lost
      if (project._overrides) {
        fd.append('rules_override', JSON.stringify(project._overrides));
      }

      const t0 = Date.now();
      // Sprint §AUDIT (2026-04-29): wrap setInterval in try/finally so it
      // always cleared on error/abort. Previously, network/parse failures
      // skipped clearInterval at L60 and the timer leaked indefinitely.
      let ti = null;
      try {
        ti = setInterval(() => {
          const sec = Math.floor((Date.now() - t0) / 1000);
          if (sec < 60) setProgress(`Pass 1: AI matuoja patalpas... (${sec}s)`);
          else if (sec < 200) setProgress(`Pass 2: AI prizoom'ina kambarius... (${sec}s)`);
          else setProgress(`Sudėtingas projektas (${sec}s)... gali užtrukti iki 8 min.`);
        }, 1000);

        const res = await fetch(`${API}/extract-interior`, {
          method: 'POST',
          credentials: 'include',
          body: fd,
          signal: AbortSignal.timeout(600_000),
        });

        if (!res.ok) {
          const body = await res.json().catch(() => ({}));
          throw new Error(body.detail || `HTTP ${res.status}`);
        }

        const result = await res.json();
        if (result?.status === 'error') {
          throw new Error(result._error || 'Pipeline klaida');
        }
        if (!result.patalpos) {
          throw new Error('AI grąžino netinkamą formatą');
        }

        // Replace project data — preserve user-edited fields (kainos, name, etc.)
        const merged = {
          ...project,
          ...result,
          name: project.name,
          company_name: project.company_name,
          vat_rate: project.vat_rate,
          _reextracted_at: new Date().toISOString(),
        };
        updateProject(project.id, merged);
        setProgress('✓ Atnaujinta!');
        setTimeout(() => {
          onComplete?.(merged);
          setExtracting(false);
          setConfirming(false);
        }, 800);
      } finally {
        if (ti != null) clearInterval(ti);
      }
    } catch (e) {
      console.error('Re-extract failed:', e);
      setError(e.message || 'Klaida');
      setExtracting(false);
    }
  };

  if (extracting) {
    return (
      <div className="border border-primary/30 bg-primary/5 rounded-lg p-3 flex items-center gap-3 min-w-[280px]">
        <Loader2 className="w-4 h-4 animate-spin text-primary shrink-0" />
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium">Pakartojama analizė...</p>
          <p className="text-xs text-muted-foreground truncate">{progress}</p>
        </div>
      </div>
    );
  }

  if (!confirming) {
    return (
      <Button
        variant="outline"
        size="sm"
        onClick={() => setConfirming(true)}
        title="Pakartoti AI analizę su išsaugotu PDF"
      >
        <RefreshCw className="w-3.5 h-3.5 mr-1.5" />
        Pakartoti AI analizę
      </Button>
    );
  }

  return (
    <div className="border border-amber-300 bg-amber-50 dark:bg-amber-950/20 dark:border-amber-900/40 rounded-lg p-3 max-w-md">
      <div className="flex items-start gap-2">
        <AlertCircle className="w-4 h-4 text-amber-600 dark:text-amber-400 shrink-0 mt-0.5" />
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-amber-900 dark:text-amber-200">
            Pakartoti AI analizę?
          </p>
          <ul className="text-xs text-amber-800 dark:text-amber-300/80 mt-1 mb-3 space-y-0.5 list-disc pl-4">
            <li>Užtruks 3-8 min, kainuos ~$1-2</li>
            <li>Senieji AI rezultatai bus pakeisti naujais</li>
            <li>Kainos gali nesutapti su naujomis pozicijomis</li>
            <li>Prielaidos ({Object.keys(project._overrides || {}).length} laukų) išsaugomos</li>
          </ul>
          <div className="flex gap-2">
            <Button size="sm" onClick={handleReextract}>Taip, pakartoti</Button>
            <Button size="sm" variant="ghost" onClick={() => setConfirming(false)}>
              <X className="w-3.5 h-3.5" />
            </Button>
          </div>
          {error && (
            <p className="text-xs text-destructive mt-2">{error}</p>
          )}
        </div>
      </div>
    </div>
  );
}
