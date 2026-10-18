import React, { useState } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { FileSpreadsheet, FileText, AlertCircle, FileCode, Loader2 } from 'lucide-react';
import { toast } from 'sonner';
import { CONF_RAUDONA, confidenceLabel, normalizeConfidence } from '@/lib/confidence';
import { API_BASE as API } from '@/lib/apiBase';
import { sanitizeExportFilename } from '@/lib/exportFilename';
import { triggerDownload } from '@/lib/downloadBlob';
import { ensureSettingsPulled } from '@/lib/projectStore';
import { csvSafe } from '@/lib/csvSafe';
import { vatRateOf } from '@/lib/vatMode';

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
  add('Lubų apdaila', 'Lubų perimetras (grindjuostės/karnizai)', 'm', lp.viso_m, lp.confidence);
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
    add('Apšvietimas', 'Įleidžiami šviestuvai', 'vnt.', aps.ileidziami_sviestuvai_vnt, 'high');
    add('Apšvietimas', 'Pakabinami šviestuvai', 'vnt.', aps.pakabinami_sviestuvai_vnt, 'high');
    add('Apšvietimas', 'Sieniniai šviestuvai', 'vnt.', aps.sieniniai_sviestuvai_vnt, 'high');
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

  // Pull the contractor's saved identity (Settings → Įmonės informacija) so the
  // export header renders as a real LT pasiūlymas — company, person, logo, contacts.
  // 2026-09-29: the settings live on the server; wait for this session's pull.
  const s = await ensureSettingsPulled();

  const payload = {
    projektas:    project.name,
    imone:        project.company_name || s.company_name || '',
    vadovas:      s.vadovas || '',
    company_logo: s.company_logo || '',
    imones_kodas: s.imones_kodas || '',
    pvm_kodas:    s.pvm_kodas || '',
    adresas:      s.adresas || '',
    telefonas:    s.telefonas || '',
    el_pastas:    s.el_pastas || '',
    iban:         s.iban || '',
    uzsakovas:    project.uzsakovas || '',
    objektas:     project.objektas || '',
    pasiulymo_nr: project.pasiulymo_nr || '',
    eilutes:      rows,
    prielaidos:   project.prielaidos || {},
    // Same convention as ExportDropdown/ProjectMainView — `patalpos` alone put
    // a DIFFERENT room set (and different m²) into the client-facing PDF/Excel
    // than the on-screen sąmata. (2026-07-28 improvement sweep, F3.)
    patalpos:     project.v8_rooms || project.patalpos || [],
    perspejimani: project.perspejimani || [],
    tipas:        project.tipas || project.type || 'kz',
    // v3 M4: the same PVM the screen shows — mode, label rule and rate.
    vat_mode:     project.vat_mode || '',
    archetipas:   project.archetipas || '',
    vat_rate:     vatRateOf(project, s.vat_rate),
  };

  const res = await fetch(`${API}/${endpoint}`, {
    method: 'POST',
    credentials: 'include',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload),
  });

  if (!res.ok) throw new Error(`Serverio klaida (${res.status})`);

  const blob = await res.blob();
  triggerDownload(blob, filename);
}

function exportErrors(project) {
  const rows = project.rows || [];
  const problematic = rows.filter(r => normalizeConfidence(r.confidence) === CONF_RAUDONA || r.warning || !r.kaina);

  const lines = [];
  lines.push(['Nr.', 'Aprašymas', 'Skyrius', 'Problema'].join(';'));
  problematic.forEach(r => {
    const issue = r.warning || (normalizeConfidence(r.confidence) === CONF_RAUDONA ? confidenceLabel(r.confidence) : 'Trūksta kainos');
    // csvSafe (audit backend-security-4): row text never runs as a spreadsheet formula.
    const cell = (v) => `"${csvSafe(v).replace(/"/g, '""')}"`;
    lines.push([cell(r.nr), cell(r.aprasymas), cell(r.skyrius), cell(issue)].join(';'));
  });

  if (problematic.length === 0) {
    lines.push(['', 'Klaidų nerasta', '', ''].join(';'));
  }

  const bom = '\uFEFF';
  const blob = new Blob([bom + lines.join('\n')], { type: 'text/csv;charset=utf-8;' });
  triggerDownload(blob, `${project.name || 'projektas'}_klaidos.csv`);
}

const exportOptions = [
  { icon: FileSpreadsheet, label: 'Excel (.xlsx)', desc: 'Profesionaliai suformatuota Excel sąmata su skyriais', action: 'excel' },
  { icon: FileText, label: 'PDF pasiūlymas', desc: 'Komercinio pasiūlymo PDF su skyriais ir sumomis', action: 'pdf' },
  { icon: AlertCircle, label: 'Klaidų ataskaita', desc: 'Įtartinos eilutės, eilutės, kurias būtina patikrinti, ir trūkstamos kainos', action: 'errors' },
  { icon: FileCode, label: 'XML (Sistela/SES)', desc: 'Netrukus — XML eksportas į sistemą „Sistela“', action: 'xml', disabled: true },
];

export default function ExportModal({ open, onClose, project }) {
  const [loading, setLoading] = useState(null);

  const handleExport = async (action) => {
    if (action === 'xml') return;
    setLoading(action);
    try {
      // Unicode-aware — the old ASCII \w stripped Lithuanian letters
      // ("Ąžuolų g. 24" → "uol g 24"). Same sanitizer as ExportDropdown.
      const safeName = sanitizeExportFilename(project.name);
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
