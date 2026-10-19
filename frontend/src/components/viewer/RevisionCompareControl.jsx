/**
 * RevisionCompareControl — „Palyginti leidimus" in the viewer toolbar (togal-v2 W10, Togal's comparison
 * overlay). Upload the designer's new PDF, pick an edition, choose „Skirtumai" (default: what was added
 * and what was removed) or „Naujas leidimas", set how strongly it shows. Says per sheet how it was laid
 * (by the walls, or only by the sheet's edges) and that comparing changes no quantity.
 *
 * The overlay state lives in InteriorWorkspace and is never saved; Esc or „Išjungti" clears it. The
 * edition itself is saved (its PDF under its own key, its record in the project), so it is there next time.
 */
import { useEffect, useRef, useState } from 'react';
import { GitCompare, Loader2, Trash2, Upload } from 'lucide-react';
import { toast } from 'sonner';

import { Popover, PopoverContent, PopoverTrigger } from '@/components/ui/popover';
import { Slider } from '@/components/ui/slider';
import { useConfirm } from '@/components/ui/confirm-provider';
import { adoptServerProject, flushProjectSaves } from '@/lib/projectStore';
import { closesOnEscape } from '@/lib/escapeToClose';
import {
  DEFAULT_OPACITY, MODES, MODE_LABELS, deleteRevision, editionLabel, listRevisions, sheetInfo, uploadRevision,
} from '@/lib/pdfRevisions';

const chip = 'inline-flex items-center gap-1 rounded-[2px] border px-2 py-0.5 text-meta transition-colors';

function Swatch({ token, children }) {
  return (
    <span className="inline-flex items-center gap-1.5">
      <span className="inline-block h-2.5 w-4 rounded-[1px]" style={{ background: `hsl(var(${token}))` }} aria-hidden />
      {children}
    </span>
  );
}

export default function RevisionCompareControl({ project, currentPage, overlay, onOverlayChange, onProjectSaved }) {
  const confirm = useConfirm();
  const projectId = project?.id;
  const [open, setOpen] = useState(false);
  const [records, setRecords] = useState(null);
  const [busy, setBusy] = useState(false);
  const fileRef = useRef(null);
  const stored = project?._meta?.brezinio_leidimai;
  const storedCount = Array.isArray(stored) ? stored.length : 0;

  useEffect(() => {
    if (!open || !projectId) return;
    listRevisions(projectId).then(setRecords).catch(() => setRecords([]));
  }, [open, projectId, storedCount]);

  useEffect(() => {
    if (!overlay) return undefined;
    const onKey = (e) => { if (closesOnEscape(e)) onOverlayChange?.(null); };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  }, [overlay, onOverlayChange]);

  const show = (record, patch = {}) => onOverlayChange?.({
    rid: record.id, record, mode: overlay?.mode || 'skirtumas', opacity: overlay?.opacity ?? DEFAULT_OPACITY, ...patch,
  });

  const landed = (saved) => {
    const adopted = adoptServerProject(saved) || saved;
    onProjectSaved?.(adopted);
  };

  const upload = async (file) => {
    if (!file) return;
    setBusy(true);
    try {
      await flushProjectSaves();          // the server writes the record into the project: nothing may wait behind it
      const { leidimas, project: saved } = await uploadRevision(projectId, file);
      landed(saved);
      setRecords(await listRevisions(projectId));
      show(leidimas, { mode: 'skirtumas' });
      toast.success('Naujas leidimas įkeltas ir uždėtas ant brėžinio.');
    } catch (e) {
      toast.error(e?.message && !/^HTTP/.test(e.message) ? e.message : 'Nepavyko įkelti naujo leidimo.');
    } finally {
      setBusy(false);
      if (fileRef.current) fileRef.current.value = '';
    }
  };

  const remove = async (record) => {
    const ok = await confirm({
      title: 'Pašalinti šį leidimą?',
      description: `„${editionLabel(record)}" bus pašalintas iš palyginimų. Dabartinis brėžinys ir kiekiai nesikeičia.`,
      confirmText: 'Pašalinti', cancelText: 'Atšaukti', destructive: true,
    });
    if (!ok) return;
    setBusy(true);
    try {
      await flushProjectSaves();
      const { project: saved } = await deleteRevision(projectId, record.id);
      landed(saved);
      if (overlay?.rid === record.id) onOverlayChange?.(null);
      setRecords(await listRevisions(projectId));
    } catch {
      toast.error('Nepavyko pašalinti leidimo.');
    } finally {
      setBusy(false);
    }
  };

  const active = (records || []).find((r) => r.id === overlay?.rid) || overlay?.record || null;
  const info = active ? sheetInfo(active, currentPage) : null;

  return (
    <Popover open={open} onOpenChange={setOpen}>
      <PopoverTrigger asChild>
        <button
          type="button"
          className={`inline-flex shrink-0 items-center gap-1.5 rounded-[2px] px-2 py-1 text-meta font-medium focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring ${overlay
            ? 'bg-accent-2 text-white'
            : 'text-viewer-chrome-foreground hover:bg-muted'}`}
          title="Uždėti naują projektuotojo atsiųstą brėžinio leidimą ant dabartinio ir pamatyti, kas pasikeitė"
          aria-pressed={!!overlay}
          data-testid="revision-compare-button"
        >
          <GitCompare className="h-3.5 w-3.5" aria-hidden />
          <span className="hidden xl:inline">Palyginti leidimus</span>
        </button>
      </PopoverTrigger>
      <PopoverContent align="start" className="w-96 rounded-[2px] p-3 space-y-3" data-testid="revision-compare-panel">
        <div>
          <p className="text-ui font-semibold text-foreground">Palyginti su nauju brėžinio leidimu</p>
          <p className="mt-0.5 text-meta leading-snug text-muted-foreground">
            Naujas projektuotojo PDF uždedamas ant dabartinio brėžinio. Palyginimas nekeičia jokio kiekio,
            o dabartinis brėžinys lieka toks pat.
          </p>
        </div>

        <div className="space-y-1">
          {records === null && <p className="text-meta text-muted-foreground">Kraunama…</p>}
          {records?.length === 0 && <p className="text-meta text-muted-foreground">Naujų leidimų dar nėra.</p>}
          {(records || []).map((r) => (
            <div key={r.id} className="flex items-center gap-2">
              <label className="flex flex-1 min-w-0 items-center gap-2 text-ui cursor-pointer">
                <input
                  type="radio" name="revision" className="accent-accent-2"
                  checked={overlay?.rid === r.id} onChange={() => show(r)}
                />
                <span className="truncate" title={editionLabel(r)}>{editionLabel(r)}</span>
                <span className="text-meta text-muted-foreground shrink-0">{r.puslapiai} lap.</span>
              </label>
              <button
                type="button" disabled={busy} onClick={() => remove(r)}
                className="p-1 rounded-[2px] text-muted-foreground hover:text-destructive hover:bg-muted disabled:opacity-40"
                title="Pašalinti šį leidimą" aria-label="Pašalinti šį leidimą"
              >
                <Trash2 className="h-3.5 w-3.5" />
              </button>
            </div>
          ))}
          <input
            ref={fileRef} type="file" accept="application/pdf,.pdf" className="hidden"
            onChange={(e) => upload(e.target.files?.[0])} data-testid="revision-file-input"
          />
          <button
            type="button" disabled={busy} onClick={() => fileRef.current?.click()}
            className={`${chip} border-border-strong bg-card text-foreground/85 hover:bg-muted/50 disabled:opacity-60`}
          >
            {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden /> : <Upload className="h-3.5 w-3.5" aria-hidden />}
            {busy ? 'Lyginami lapai…' : 'Įkelti naują leidimą (PDF)'}
          </button>
        </div>

        {active && overlay && (
          <div className="space-y-2.5 border-t border-border pt-2.5">
            <div className="flex gap-1" role="radiogroup" aria-label="Ką rodyti">
              {MODES.map((m) => (
                <button
                  key={m} type="button" role="radio" aria-checked={overlay.mode === m}
                  onClick={() => show(active, { mode: m })}
                  className={`${chip} ${overlay.mode === m
                    ? 'border-accent-2 bg-accent-2 text-white'
                    : 'border-border-strong bg-card text-foreground/85 hover:bg-muted/50'}`}
                >
                  {MODE_LABELS[m]}
                </button>
              ))}
            </div>
            <div className="flex flex-wrap gap-x-4 gap-y-1 text-meta text-foreground/85">
              {overlay.mode === 'skirtumas' ? (
                <>
                  <Swatch token="--revision-new">nauja — yra tik naujame leidime</Swatch>
                  <Swatch token="--revision-removed">išbraukta — buvo tik dabartiniame</Swatch>
                </>
              ) : (
                <Swatch token="--revision-new">naujo leidimo linijos</Swatch>
              )}
            </div>
            <label className="block text-meta text-muted-foreground">
              Ryškumas
              <Slider
                className="mt-1.5"
                min={0.1} max={1} step={0.05}
                value={[overlay.opacity ?? DEFAULT_OPACITY]}
                onValueChange={([v]) => show(active, { opacity: v })}
                aria-label="Palyginimo ryškumas"
              />
            </label>
            {info && (
              <p className={`text-meta leading-snug ${info.matched && info.byWalls ? 'text-foreground/85' : 'text-conf-med'}`}>
                {info.text}
              </p>
            )}
            <button
              type="button" onClick={() => onOverlayChange?.(null)}
              className={`${chip} border-border-strong bg-card text-foreground/85 hover:bg-muted/50`}
            >
              Išjungti (Esc)
            </button>
          </div>
        )}
      </PopoverContent>
    </Popover>
  );
}
