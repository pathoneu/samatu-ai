/**
 * OverlayPdfDialog — „PDF su žymėjimais" (togal-v2 W8): which sheets, which marks, a preview of the first
 * chosen sheet exactly as the file prints it (the server's dry run renders that page of the very PDF), then
 * the download. The PDF is built server-side (backend/api/export_overlay_pdf.py); nothing is recomputed.
 */
import { useEffect, useMemo, useState } from 'react';
import { FileText, Loader2, X } from 'lucide-react';
import { toast } from 'sonner';
import { fetchOverlayPdf } from '@/lib/exportApi';
import { OVERLAY_LAYERS, overlayPageChoices, overlayRequestBody } from '@/lib/exportGrouping';
import { overlayPdfFilename } from '@/lib/exportFilename';
import { triggerDownload } from '@/lib/downloadBlob';
import { ltCount } from '@/lib/ltPlural';

export default function OverlayPdfDialog({ project, onClose }) {
  const pages = useMemo(() => overlayPageChoices(project), [project]);
  const [chosen, setChosen] = useState(() => new Set(pages.map((p) => p.nr)));
  const [layers, setLayers] = useState(() => Object.fromEntries(OVERLAY_LAYERS.map((l) => [l.key, l.on])));
  const [preview, setPreview] = useState({ url: null, loading: true, error: null });
  const [busy, setBusy] = useState(false);

  // With no sheet list the project still has its drawing: then the whole drawing goes.
  const selection = pages.length === 0 ? 'all' : [...chosen];
  const noneChosen = pages.length > 0 && chosen.size === 0;
  const firstPage = pages.length === 0 ? 1 : Math.min(...chosen);
  const layersKey = JSON.stringify(layers);

  useEffect(() => {
    if (noneChosen) return undefined;
    const ctrl = new AbortController();
    setPreview((p) => ({ ...p, loading: true, error: null }));
    const t = setTimeout(() => {
      fetchOverlayPdf(project.id, overlayRequestBody(project, { pages: [firstPage], layers, dryRun: true }),
        { signal: ctrl.signal })
        .then((blob) => setPreview({ url: URL.createObjectURL(blob), loading: false, error: null }))
        .catch((e) => { if (!ctrl.signal.aborted) setPreview((p) => ({ ...p, loading: false, error: e.message })); });
    }, 300);
    return () => { clearTimeout(t); ctrl.abort(); };
    // layersKey stands for `layers` (a fresh object per toggle)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [project.id, firstPage, layersKey, noneChosen]);

  // The previous preview's object URL is released when the next one replaces it (and on close).
  useEffect(() => () => { if (preview.url) URL.revokeObjectURL(preview.url); }, [preview.url]);

  const toggle = (nr) => setChosen((prev) => {
    const next = new Set(prev);
    if (next.has(nr)) next.delete(nr); else next.add(nr);
    return next;
  });

  const download = async () => {
    setBusy(true);
    try {
      const blob = await fetchOverlayPdf(project.id, overlayRequestBody(project, { pages: selection, layers }),
        { timeoutMs: 300_000 });
      triggerDownload(blob, overlayPdfFilename(project.name));
      toast.success('Failas atsisiųstas');
      onClose();
    } catch (e) {
      toast.error(`Eksporto klaida: ${e.message}`);
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="fixed inset-0 bg-black/60 z-50 flex items-center justify-center p-4">
      <div role="dialog" aria-label="PDF su žymėjimais"
        className="bg-card border border-border rounded-xl shadow-2xl w-full max-w-3xl max-h-[88vh] flex flex-col">
        <div className="flex items-center justify-between px-5 py-4 border-b border-border">
          <div className="flex items-center gap-2">
            <FileText className="w-4 h-4 text-muted-foreground" />
            <h2 className="text-sm font-semibold text-foreground">PDF su žymėjimais</h2>
          </div>
          <button onClick={onClose} disabled={busy} title="Užverti neeksportavus" aria-label="Užverti"
            className="text-muted-foreground hover:text-foreground disabled:opacity-50">
            <X className="w-4 h-4" />
          </button>
        </div>

        <div className="flex-1 min-h-0 grid grid-cols-1 md:grid-cols-[15rem_1fr]">
          <div className="overflow-y-auto border-b md:border-b-0 md:border-r border-border">
            <div className="px-4 py-3 border-b border-border">
              <p className="text-[11px] text-muted-foreground">Žymėjimai</p>
              <ul className="mt-1 space-y-0.5">
                {OVERLAY_LAYERS.map((l) => (
                  <li key={l.key}>
                    <label className="flex items-start gap-2 px-1 py-1 rounded hover:bg-muted/40 cursor-pointer">
                      <input type="checkbox" checked={!!layers[l.key]} className="mt-0.5 w-4 h-4 accent-foreground"
                        onChange={(e) => setLayers((prev) => ({ ...prev, [l.key]: e.target.checked }))} />
                      <span>
                        <span className="block text-sm text-foreground">{l.label}</span>
                        <span className="block text-[11px] text-muted-foreground">{l.desc}</span>
                      </span>
                    </label>
                  </li>
                ))}
              </ul>
            </div>
            {pages.length > 0 && (
              <div className="px-4 py-3">
                <div className="flex items-center justify-between">
                  <p className="text-[11px] text-muted-foreground">Lapai</p>
                  <button type="button" className="text-[11px] text-foreground hover:underline"
                    onClick={() => setChosen(chosen.size === pages.length ? new Set() : new Set(pages.map((p) => p.nr)))}>
                    {chosen.size === pages.length ? 'Nužymėti visus' : 'Pažymėti visus'}
                  </button>
                </div>
                <ul className="mt-1 space-y-0.5">
                  {pages.map((p) => (
                    <li key={p.nr}>
                      <label className="flex items-start gap-2 px-1 py-1 rounded hover:bg-muted/40 cursor-pointer">
                        <input type="checkbox" checked={chosen.has(p.nr)} onChange={() => toggle(p.nr)}
                          className="mt-0.5 w-4 h-4 accent-foreground" />
                        <span className="text-sm text-foreground">
                          {p.nr}. {p.name || `Lapas ${p.nr}`}
                        </span>
                      </label>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>

          <div className="min-h-0 flex flex-col p-4 gap-2">
            <div className="flex items-center justify-between">
              <p className="text-[11px] text-muted-foreground">
                Peržiūra — {pages.length ? `lapas ${firstPage}` : 'pirmas lapas'}, taip, kaip bus faile
              </p>
              {preview.loading && !noneChosen && <Loader2 className="w-3.5 h-3.5 animate-spin text-muted-foreground" aria-label="Kraunama" />}
            </div>
            <div className="flex-1 min-h-[16rem] border border-border rounded-sm bg-background overflow-auto flex items-start justify-center">
              {noneChosen ? (
                <p className="m-auto text-sm text-muted-foreground">Pažymėkite bent vieną lapą</p>
              ) : preview.error ? (
                <p className="m-auto px-4 text-sm text-destructive">Peržiūros nepavyko gauti: {preview.error}</p>
              ) : preview.url ? (
                <img src={preview.url} alt="Pirmojo lapo su žymėjimais peržiūra" className="max-w-full h-auto" />
              ) : null}
            </div>
            <p className="text-[11px] text-muted-foreground">
              Brūkšniniai kontūrai — rasti automatiškai, ištisiniai — jūsų nubrėžti ar pataisyti. Legenda kiekviename lape.
            </p>
          </div>
        </div>

        <div className="flex items-center justify-end gap-2 px-5 py-3 border-t border-border">
          <span className="mr-auto text-[12px] text-muted-foreground">
            {pages.length ? ltCount(chosen.size, 'lapas', 'lapai', 'lapų') : 'Visi brėžinio lapai'}
          </span>
          <button onClick={onClose} disabled={busy} title="Grįžti neatsisiuntus failo"
            className="px-3 py-1.5 text-sm text-muted-foreground hover:text-foreground disabled:opacity-50">
            Atšaukti
          </button>
          <button onClick={download} disabled={busy || noneChosen}
            title={noneChosen ? 'Pažymėkite bent vieną lapą' : 'Sugeneruoti ir atsisiųsti PDF su žymėjimais'}
            className="inline-flex items-center gap-1.5 px-3.5 py-1.5 bg-foreground text-background rounded text-sm font-medium hover:opacity-90 disabled:opacity-50 transition-opacity">
            {busy ? <Loader2 className="w-3.5 h-3.5 animate-spin" /> : <FileText className="w-3.5 h-3.5" />}
            Atsisiųsti PDF
          </button>
        </div>
      </div>
    </div>
  );
}
