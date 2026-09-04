/**
 * ReextractButton — reads the saved PDF again from scratch (Limitation 10 fix).
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
import { useTranslation } from 'react-i18next';
import { RefreshCw, Loader2, AlertCircle, X } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { getPdfBlob } from '@/lib/pdfStore';
import { getProject, updateProject } from '@/lib/projectStore';
import { API_BASE as API } from '@/lib/apiBase';

export default function ReextractButton({ project, onComplete }) {
  // This component carried a complete set of i18n keys that nothing used: the
  // strings were hard-coded LT, so no vocabulary pass could reach them.
  const { t } = useTranslation();
  const [confirming, setConfirming] = useState(false);
  const [extracting, setExtracting] = useState(false);
  const [progress, setProgress] = useState('');
  const [error, setError] = useState(null);

  const handleReextract = async () => {
    setError(null);
    setExtracting(true);
    setProgress(t('project.reextract.loadingPdf'));

    try {
      const blob = await getPdfBlob(project.id);
      if (!blob) {
        throw new Error(t('project.reextract.pdfNotFound'));
      }

      setProgress(t('project.reextract.analyzing'));
      const fd = new FormData();
      fd.append('files', blob, project.name + '.pdf');
      // Forward existing rules_override so user's prefs aren't lost. Read them
      // from the STORE, not the render-time prop — a Prielaidos edit that
      // didn't re-render this button would otherwise re-extract under the old
      // assumptions.
      const overrides = (getProject(project.id) || project)._overrides;
      if (overrides) {
        fd.append('rules_override', JSON.stringify(overrides));
      }

      const t0 = Date.now();
      // Sprint §AUDIT (2026-04-29): wrap setInterval in try/finally so it
      // always cleared on error/abort. Previously, network/parse failures
      // skipped clearInterval at L60 and the timer leaked indefinitely.
      let ti = null;
      try {
        ti = setInterval(() => {
          const sec = Math.floor((Date.now() - t0) / 1000);
          if (sec < 60) setProgress(t('project.reextract.pass1', { sec }));
          else if (sec < 200) setProgress(t('project.reextract.pass2', { sec }));
          else setProgress(t('project.reextract.complex', { sec }));
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
          throw new Error(t('project.reextract.badFormat'));
        }

        // Replace project data — preserve user-edited fields (kainos, name, etc.)
        //
        // 2026-07-28 audit: the base of this spread used to be the `project`
        // PROP — a render-time snapshot taken up to 10 minutes before the
        // extraction returned. Everything the user changed while it ran
        // (prices, measurements, polygons, per-room overrides, the name) was
        // silently rolled back to that snapshot. Re-read the CURRENT stored
        // project first; same idiom as InteriorWorkspace.jsx (`const fresh =
        // getProject(project.id) || project`) after its async detect calls.
        const base = getProject(project.id) || project;
        const merged = {
          ...base,
          ...result,
          name: base.name,
          company_name: base.company_name,
          vat_rate: base.vat_rate,
          _reextracted_at: new Date().toISOString(),
        };
        updateProject(project.id, merged);
        setProgress(t('project.reextract.updated'));
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
      setError(e.message || t('project.reextract.error'));
      setExtracting(false);
    }
  };

  if (extracting) {
    return (
      <div className="border border-primary/30 bg-primary/5 rounded-lg p-3 flex items-center gap-3 min-w-[280px]">
        <Loader2 className="w-4 h-4 animate-spin text-primary shrink-0" />
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium">{t('project.reextract.inProgress')}</p>
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
        title={t('project.reextract.buttonTitle')}
      >
        <RefreshCw className="w-3.5 h-3.5 mr-1.5" />
        {t('project.reextract.button')}
      </Button>
    );
  }

  return (
    <div className="border border-amber-300 bg-amber-50 dark:bg-amber-950/20 dark:border-amber-900/40 rounded-lg p-3 max-w-md">
      <div className="flex items-start gap-2">
        <AlertCircle className="w-4 h-4 text-amber-600 dark:text-amber-400 shrink-0 mt-0.5" />
        <div className="flex-1 min-w-0">
          <p className="text-sm font-medium text-amber-900 dark:text-amber-200">
            {t('project.reextract.confirmTitle')}
          </p>
          <ul className="text-xs text-amber-800 dark:text-amber-300/80 mt-1 mb-3 space-y-0.5 list-disc pl-4">
            <li>{t('project.reextract.bullet1')}</li>
            <li>{t('project.reextract.bullet2')}</li>
            <li>{t('project.reextract.bullet3')}</li>
            <li>{t('project.reextract.bullet4', { count: Object.keys(project._overrides || {}).length })}</li>
          </ul>
          <div className="flex gap-2">
            <Button size="sm" onClick={handleReextract}>{t('project.reextract.yesRepeat')}</Button>
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
