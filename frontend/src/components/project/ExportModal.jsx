import React, { useState } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { FileSpreadsheet, FileText, AlertCircle, FileCode, Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import { API_BASE as API } from '@/lib/apiBase';

function buildInteriorRows(project) {
  // V8 PRIMARY: jei darbu_sarasas užpildytas (V8 grąžina) — naudojam jį tiesiog
  if (Array.isArray(project.darbu_sarasas) && project.darbu_sarasas.length > 0) {
    return project.darbu_sarasas
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
      }));
  }

  // FALLBACK: V3/V5/V6 stilius — generuojame iš sub-laukų
  const sk = project.skaiciavimai || {};
  const rows = [];
  let nr = 1;

  const add = (skyrius, aprasymas, mato_vnt, kiekis, confidence) => {
    if (kiekis == null || kiekis === 0) return;
    rows.push({ nr: String(nr++), aprasymas, mato_vnt, kiekis, kaina: 0, suma: 0, skyrius, confidence: confidence || 'medium' });
  };

  const dp  = sk.dazomas_plotas    || {};
  const gk  = sk.glaistymo_kampai  || {};
  const ang = sk.angokrasciai      || {};
  const lp  = sk.lubu_perimetras   || {};
  const gj  = sk.grindjuostes      || {};
  const daz = sk.dazai             || {};
  const gkl = sk.gk_lapai          || {};
  const gls = sk.glaistas          || {};
  const hid = project.hidroizoliacija || {};
  const el  = project.elektra      || {};
  const san = project.santechnika  || {};
  const aps = project.apsvietimas  || {};
  const pk  = project.papildomi_kiekiai || {};

  add('Paruošimas', 'Gruntavimas (gruntas prieš dažymą)', 'l', daz.gruntas_l, daz.confidence);
  add('Paruošimas', `Glaistymas ${gls.lygis || 'Q2'} lygis`, 'kg', gls.kg, gls.confidence);
  add('Paruošimas', `Glaistymo mišinys (maišai 25 kg)`, 'vnt.', gls.maisai_25kg, gls.confidence);
  add('Paruošimas', 'Glaistymo kampų profiliai', 'm', gk.viso_m, gk.confidence);

  add('Sienų apdaila', 'Sienų dažymas (neto plotas)', 'm²', dp.sienos_m2, dp.confidence);
  add('Sienų apdaila', 'Sienų dažai (2 sluoksniai)', 'l', daz.sienos_l, daz.confidence);
  add('Sienų apdaila', 'Angokraščiai (langai + durys)', 'm', ang.viso_m, ang.confidence);
  add('Sienų apdaila', 'Angokraščių plotas', 'm²', ang.area_m2, ang.confidence);
  if ((sk.plyteles_m2 || 0) > 0) add('Sienų apdaila', 'Sienų plytelės', 'm²', sk.plyteles_m2, 'medium');
  add('Sienų apdaila', 'GK lapai sienoms', 'vnt.', gkl.vnt, gkl.confidence);

  add('Lubų apdaila', 'Lubų dažymas', 'm²', dp.lubos_m2, dp.confidence);
  add('Lubų apdaila', 'Lubų dažai (2 sluoksniai)', 'l', daz.lubos_l, daz.confidence);
  add('Lubų apdaila', 'Lubų perimetras (grindjuostės/karniizai)', 'm', lp.viso_m, lp.confidence);
  if (project.lubu_data?.gkp_m2) add('Lubų apdaila', 'GKP lubos', 'm²', project.lubu_data.gkp_m2, 'medium');
  if (project.lubu_data?.led_nisu_m) add('Lubų apdaila', 'LED nišos', 'm', project.lubu_data.led_nisu_m, 'medium');
  if (project.lubu_data?.uzuolaidu_nisu_m) add('Lubų apdaila', 'Užuolaidų nišos', 'm', project.lubu_data.uzuolaidu_nisu_m, 'medium');

  add('Grindų apdaila', 'Grindjuostės', 'm', gj.viso_m, gj.confidence);
  if (pk.parketlentes_m2) add('Grindų apdaila', 'Parketlentės', 'm²', pk.parketlentes_m2, 'medium');

  if (Object.keys(hid).length > 0) {
    add('Hidroizoliacija', 'Hidroizoliacija (grindys)', 'm²', hid.grindys_m2, 'medium');
    add('Hidroizoliacija', 'Hidroizoliacija (sienos)', 'm²', hid.sienos_m2, 'medium');
    add('Hidroizoliacija', 'Sandarinimo juosta', 'm', hid.juosta_m, 'medium');
    add('Hidroizoliacija', 'Skystoji membrana (2 sluoksniai)', 'kg', hid.membrana_kg, 'medium');
  }

  if (Object.keys(el).length > 0) {
    add('Elektra', 'Rozetės', 'vnt.', el.rozetes_vnt, 'high');
    add('Elektra', 'Jungikliai', 'vnt.', el.jungikliai_vnt, 'high');
    add('Elektra', 'Interneto rozetės', 'vnt.', el.interneto_rozetes_vnt, 'high');
    add('Elektra', 'Antenos rozetės', 'vnt.', el.antenos_vnt, 'high');
    add('Elektra', 'USB-C rozetės', 'vnt.', el.usb_c_vnt, 'high');
    add('Elektra', 'Termostatai', 'vnt.', el.termostatai_vnt, 'high');
    add('Elektra', 'Prietaisų pajungimai', 'vnt.', el.prietaisu_pajungimai_vnt, 'high');
  }

  if (Object.keys(san).length > 0) {
    add('Santechnika', 'WC rėmai', 'vnt.', san.wc_remai_vnt, 'high');
    add('Santechnika', 'Dušo sistemos', 'vnt.', san.duso_sistemos_vnt, 'high');
    add('Santechnika', 'Praustuvės / kriauklės', 'vnt.', san.praustuves_vnt, 'high');
    add('Santechnika', 'Vonios maišytuvai', 'vnt.', san.vonios_maistuvai_vnt, 'high');
    add('Santechnika', 'Skalbimo mašinų pajungimai', 'vnt.', san.skalbimo_masinos_vnt, 'high');
    add('Santechnika', 'Trapai', 'vnt.', san.trapai_vnt, 'high');
    add('Santechnika', 'Kondicionieriai', 'vnt.', san.kondicionieriai_vnt, 'high');
  }

  if (Object.keys(aps).length > 0) {
    add('Apšvietimas', 'Įleidžiami sviestuvai', 'vnt.', aps.ileidziami_sviestuvai_vnt, 'high');
    add('Apšvietimas', 'Pakabinami sviestuvai', 'vnt.', aps.pakabinami_sviestuvai_vnt, 'high');
    add('Apšvietimas', 'Sieniniai sviestuvai', 'vnt.', aps.sieniniai_sviestuvai_vnt, 'high');
    add('Apšvietimas', 'LED juostos', 'm', aps.led_juostos_m, 'high');
    add('Apšvietimas', 'Gaisro davikliai', 'vnt.', aps.gaisro_davikliai_vnt, 'high');
  }

  return rows;
}

async function downloadFromBackend(endpoint, project, filename) {
  const isInterior = (project.tipas === 'interjeras') || (project.type === 'interior');
  const rows = isInterior
    ? buildInteriorRows(project)
    : (project.rows || []).map(({ nr, aprasymas, mato_vnt, kiekis, kaina, suma, skyrius }) => ({
        nr: nr || '',
        aprasymas: aprasymas || '',
        mato_vnt: mato_vnt || '',
        kiekis: kiekis || 0,
        kaina: kaina || 0,
        suma: suma || 0,
        skyrius: skyrius || '',
      }));

  // 2026-05-06: surface company_name in export. Per-project override wins;
  // global Settings (Įmonės pavadinimas) is the fallback.
  let companyName = project.company_name || '';
  if (!companyName) {
    try {
      const s = JSON.parse(localStorage.getItem('samatu_settings') || '{}');
      companyName = s.company_name || '';
    } catch { /* ignore */ }
  }

  const payload = {
    projektas:   project.name,
    imone:       companyName,
    eilutes:     rows,
    prielaidos:  project.prielaidos || {},
    patalpos:    project.patalpos || [],
    perspejimani: project.perspejimani || [],
    tipas:       project.tipas || project.type || 'kz',
  };

  const res = await fetch(`${API}/${endpoint}`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });

  if (!res.ok) throw new Error(`Serverio klaida (${res.status})`);

  const blob = await res.blob();
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}

function exportErrors(project) {
  const rows = project.rows || [];
  const vatRate = project.vat_rate || 21;
  const problematic = rows.filter(r => r.confidence === 'low' || r.warning || !r.kaina);

  const lines = [];
  lines.push(['Nr.', 'Aprašymas', 'Skyrius', 'Problema'].join(';'));
  problematic.forEach(r => {
    const issue = r.warning || (r.confidence === 'low' ? 'Žemas AI tikslumas' : 'Trūksta kainos');
    lines.push([r.nr || '', `"${(r.aprasymas || '').replace(/"/g, '""')}"`, r.skyrius || '', issue].join(';'));
  });

  if (problematic.length === 0) {
    lines.push(['', 'Klaidų nerasta', '', ''].join(';'));
  }

  const bom = '\uFEFF';
  const blob = new Blob([bom + lines.join('\n')], { type: 'text/csv;charset=utf-8;' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `${project.name || 'projektas'}_klaidos.csv`;
  a.click();
  URL.revokeObjectURL(url);
}

const exportOptions = [
  { icon: FileSpreadsheet, label: 'Excel (.xlsx)', desc: 'Profesionaliai suformatuota Excel sąmata su skyriais', action: 'excel' },
  { icon: FileText, label: 'PDF pasiūlymas', desc: 'Komercinė pasiūlymo PDF su skyriais ir totalais', action: 'pdf' },
  { icon: AlertCircle, label: 'Klaidų ataskaita', desc: 'Įtartinos eilutės, žemas AI tikslumas, trūkstamos kainos', action: 'errors' },
  { icon: FileCode, label: 'XML (Sistela/SES)', desc: 'Netrukus — XML eksportas Sistela sistemai', action: 'xml', disabled: true },
];

export default function ExportModal({ open, onClose, project }) {
  const [loading, setLoading] = useState(null);

  const handleExport = async (action) => {
    if (action === 'xml') return;
    setLoading(action);
    try {
      const safeName = (project.name || 'projektas').replace(/[^\w\s-]/g, '').trim();
      if (action === 'excel') {
        await downloadFromBackend('generate-excel', project, `${safeName}.xlsx`);
      } else if (action === 'pdf') {
        await downloadFromBackend('generate-pdf', project, `${safeName}.pdf`);
      } else if (action === 'errors') {
        exportErrors(project);
      }
      toast.success('Failas atsisiųstas');
      onClose();
    } catch (e) {
      toast.error(`Eksporto klaida: ${e.message}`);
    } finally {
      setLoading(null);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onClose}>
      <DialogContent className="bg-card border-border max-w-md">
        <DialogHeader>
          <DialogTitle className="text-foreground">Eksportuoti projektą</DialogTitle>
        </DialogHeader>
        <div className="space-y-2 mt-2">
          {exportOptions.map(({ icon: Icon, label, desc, action, disabled }) => (
            <Button
              key={action}
              variant="outline"
              disabled={disabled || loading === action}
              onClick={() => handleExport(action)}
              className="w-full justify-start h-auto py-4 px-4 border-border hover:bg-accent hover:border-primary/30 disabled:opacity-40"
            >
              {loading === action
                ? <Loader2 className="w-5 h-5 text-primary mr-3 flex-shrink-0 animate-spin" />
                : <Icon className="w-5 h-5 text-primary mr-3 flex-shrink-0" />
              }
              <div className="text-left">
                <p className="text-sm font-medium text-foreground">{label}</p>
                <p className="text-xs text-muted-foreground">{desc}</p>
              </div>
              {disabled && (
                <span className="ml-auto text-xs text-muted-foreground bg-secondary px-2 py-0.5 rounded">
                  Netrukus
                </span>
              )}
            </Button>
          ))}
        </div>
      </DialogContent>
    </Dialog>
  );
}
