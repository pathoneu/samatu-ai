/**
 * ExportDropdown — top-right corner eksporto mygtukas su dropdown'u.
 * Visada matomas projekto puslapyje (pagal Q5 sprendimą).
 */

import { useState, useRef, useEffect } from 'react';
import { Download, FileSpreadsheet, FileText, ChevronDown, Loader2 } from 'lucide-react';
import { toast } from 'sonner';

const API = '';

// Collect human-readable warnings from new + legacy schema sources.
// Backend `lt_sanity.warnings[]` (post-Phase 9 mirror) merges _lt_warnings
// AND pipeline warnings[] (e.g. eksplikacija-missing INFO). Legacy
// project.perspejimani is also passed through if present.
function collectWarnings(project) {
  const out = [];
  const sanity = project.lt_sanity?.warnings || [];
  for (const w of sanity) {
    out.push({
      level: w.level || 'INFO',
      room: w.room || '',
      message: w.message || '',
    });
  }
  if (Array.isArray(project.perspejimani)) {
    for (const w of project.perspejimani) {
      out.push(typeof w === 'string' ? { level: 'INFO', message: w } : w);
    }
  }
  return out;
}

function buildPayload(project) {
  // V8 darbu_sarasas — primary source
  if (Array.isArray(project.darbu_sarasas) && project.darbu_sarasas.length > 0) {
    return {
      projektas: project.name,
      eilutes: project.darbu_sarasas
        .filter(it => (it.kiekis || 0) > 0)
        .map((it, i) => ({
          nr: String(it.eil_nr || i + 1),
          aprasymas: it.aprasymas || '',
          mato_vnt: it.mato_vnt || it.vnt || '',
          kiekis: it.kiekis || 0,
          kaina: it.kaina || 0,
          suma: (it.kiekis || 0) * (it.kaina || 0),
          skyrius: it.skyrius || it.kategorija || 'Apdaila',
          confidence: it.confidence || 'medium',
        })),
      patalpos: project.v8_rooms || project.patalpos || [],
      tipas: project.tipas || project.type || 'kz',
      perspejimani: collectWarnings(project),
      archetipas: project.archetipas || '',
    };
  }
  // Fallback (KŽ projektai)
  return {
    projektas: project.name,
    eilutes: (project.rows || []).map(r => ({
      nr: r.nr || '', aprasymas: r.aprasymas || '',
      mato_vnt: r.mato_vnt || '', kiekis: r.kiekis || 0,
      kaina: r.kaina || 0, suma: r.suma || 0,
      skyrius: r.skyrius || '',
    })),
    tipas: project.tipas || 'kz',
  };
}

async function downloadFile(endpoint, project, filename) {
  const res = await fetch(`${API}/${endpoint}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(buildPayload(project)),
  });
  if (!res.ok) throw new Error(`Klaida (${res.status})`);
  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

export default function ExportDropdown({ project }) {
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(null);
  const ref = useRef(null);

  useEffect(() => {
    const onClick = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false);
    };
    if (open) document.addEventListener('mousedown', onClick);
    return () => document.removeEventListener('mousedown', onClick);
  }, [open]);

  const handle = async (action) => {
    setLoading(action);
    setOpen(false);
    try {
      const safeName = (project.name || 'projektas').replace(/[^\w\s-]/g, '').trim();
      if (action === 'excel') {
        await downloadFile('generate-excel', project, `${safeName}.xlsx`);
      } else if (action === 'pdf') {
        await downloadFile('generate-pdf', project, `${safeName}.pdf`);
      }
      toast.success('Failas atsisiųstas');
    } catch (e) {
      toast.error(`Eksporto klaida: ${e.message}`);
    } finally {
      setLoading(null);
    }
  };

  return (
    <div className="relative" ref={ref}>
      <button
        onClick={() => setOpen(v => !v)}
        disabled={loading != null}
        className="inline-flex items-center gap-2 px-3.5 py-2 bg-foreground text-background rounded-lg text-sm font-medium hover:opacity-90 disabled:opacity-50 transition-opacity"
      >
        {loading
          ? <Loader2 className="w-4 h-4 animate-spin" />
          : <Download className="w-4 h-4" />}
        <span>Eksportuoti</span>
        <ChevronDown className="w-3.5 h-3.5 opacity-70" />
      </button>

      {open && (
        <div className="absolute right-0 top-full mt-1.5 w-56 bg-card border border-border rounded-lg shadow-lg overflow-hidden z-20">
          <button
            onClick={() => handle('excel')}
            className="w-full flex items-center gap-2.5 px-3 py-2.5 hover:bg-muted text-left text-sm transition-colors"
          >
            <FileSpreadsheet className="w-4 h-4 text-muted-foreground" />
            <div className="flex-1">
              <div className="font-medium text-foreground">Excel (.xlsx)</div>
              <div className="text-[11px] text-muted-foreground">Sąmata su skyriais ir kainomis</div>
            </div>
          </button>
          <button
            onClick={() => handle('pdf')}
            className="w-full flex items-center gap-2.5 px-3 py-2.5 hover:bg-muted text-left text-sm border-t border-border transition-colors"
          >
            <FileText className="w-4 h-4 text-muted-foreground" />
            <div className="flex-1">
              <div className="font-medium text-foreground">PDF pasiūlymas</div>
              <div className="text-[11px] text-muted-foreground">Spausdintinas komercinis pasiūlymas</div>
            </div>
          </button>
        </div>
      )}
    </div>
  );
}
