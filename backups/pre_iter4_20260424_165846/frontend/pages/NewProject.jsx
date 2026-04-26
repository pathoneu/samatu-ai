import React, { useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Button } from '@/components/ui/button';
import { ArrowLeft, Rocket } from 'lucide-react';
import UploadZone from '@/components/upload/UploadZone';
import ProcessingState from '@/components/upload/ProcessingState';
import { createProject } from '@/lib/projectStore';
import { useQueryClient } from '@tanstack/react-query';

const API = '';

const PROJECT_TYPES = [
  { id: 'auto',     label: 'Automatinis',        desc: 'AI atpažins tipą' },
  { id: 'interior', label: 'Interjero projektas', desc: 'Apdailos kiekiai' },
  { id: 'kz',       label: 'Kiekių žiniaraštis',  desc: 'KŽ lentelė' },
  { id: 'fasadas',  label: 'Fasadai',             desc: 'ETICS skaičiai' },
  { id: 'stogas',   label: 'Stogas',              desc: 'Stogo kiekiai' },
  { id: 'zeme',     label: 'Žemės darbai',        desc: 'Iškasa, tranšėjos' },
  { id: 'betonas',  label: 'Betonas',             desc: 'Betono kiekiai' },
];

async function detectAndExtract(file, forcedType, signal) {
  let projType = forcedType;

  if (forcedType === 'auto') {
    try {
      const dtFd = new FormData();
      dtFd.append('file', file);
      const dtRes = await fetch(`${API}/detect-type`, { method: 'POST', body: dtFd, signal });
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
    interior: '/extract-interior-v3',
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
  } else {
    fd.append('file', file);
  }

  const res = await fetch(`${API}${endpoint}`, { method: 'POST', body: fd, signal });
  const json = await res.json();
  return { json, res, projType };
}

export default function NewProject() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [projectName, setProjectName]   = useState('');
  const [companyName, setCompanyName]   = useState('');
  const [file, setFile]                 = useState(null);
  const [projTypeChoice, setProjType]   = useState('auto');
  const [isProcessing, setIsProcessing] = useState(false);
  const [error, setError]               = useState(null);
  const [status, setStatus]             = useState('');

  const handleCreate = async () => {
    if (!file) { setError('Pasirinkite PDF failą'); return; }
    setError(null);
    setStatus('Siunčiama...');
    setIsProcessing(true);

    try {
      const controller = new AbortController();
      const timeoutId  = setTimeout(() => controller.abort(), 300_000);
      let json, res, projType;
      try {
        setStatus('AI analizuoja PDF...');
        ({ json, res, projType } = await detectAndExtract(file, projTypeChoice, controller.signal));
        setStatus('Išsaugoma...');
      } finally {
        clearTimeout(timeoutId);
      }

      if (!res.ok) {
        const msg = Array.isArray(json?.detail)
          ? json.detail.map(d => d.msg).join(', ')
          : json?.detail || `Serverio klaida (${res.status})`;
        throw new Error(msg);
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
        project = createProject({
          name:            projectName || json.projektas || 'Interjero projektas',
          company_name:    companyName,
          tipas:           'interjeras',
          patalpos:        json.patalpos,
          skaiciavimai:    json.skaiciavimai,
          papildomi_kiekiai: json.papildomi_kiekiai,
          sienu_apdaila:   json.sienu_apdaila,
          lubu_data:       json.lubu_data,
          grindys:         json.grindys,
          elektra:         json.elektra,
          santechnika:     json.santechnika,
          apsvietimas:     json.apsvietimas,
          samatos_kiekiai: json.samatos_kiekiai,
          bendri_kiekiai:  json.bendri_kiekiai,
          grindų_medziagos: json.grindų_medziagos,
          pastabos:        json.pastabos,
          meta:            json.meta,
          confidence:      json.confidence,
          vizualine_analize: json.vizualine_analize,
          prielaidos:      json.prielaidos,
          raw_calc_data:   json.raw_calc_data,
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

      queryClient.invalidateQueries({ queryKey: ['projects'] });
      navigate(`/project/${project.id}`);
    } catch (e) {
      setError(`${e.message}\n\nStack: ${e.stack}`);
      setIsProcessing(false);
      setStatus('');
    }
  };

  if (isProcessing) {
    return (
      <div className="p-6 lg:p-8 max-w-2xl mx-auto">
        <ProcessingState />
        {status && !error && (
          <p className="text-center text-xs text-muted-foreground mt-2">{status}</p>
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
      <Link to="/" className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors mb-6">
        <ArrowLeft className="w-4 h-4" />
        Grįžti į projektus
      </Link>

      <h1 className="text-2xl font-bold text-foreground mb-1">Naujas projektas</h1>
      <p className="text-sm text-muted-foreground mb-8">
        Įkelkite PDF — KŽ arba interjero projektą. AI automatiškai atpažins tipą ir išskirs duomenis.
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
          <div className="grid grid-cols-3 sm:grid-cols-4 gap-2">
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
                <p className="text-xs font-semibold">{t.label}</p>
                <p className="text-[11px] mt-0.5 opacity-70">{t.desc}</p>
              </button>
            ))}
          </div>
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
          <UploadZone onFileSelect={setFile} accept=".pdf" label="PDF — KŽ arba interjero projektas" />
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
