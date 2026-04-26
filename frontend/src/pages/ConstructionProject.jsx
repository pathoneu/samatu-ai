import React from 'react';
import { Badge } from '@/components/ui/badge';

function fmt(v, decimals = 1) {
  if (v == null) return '—';
  return Number(v).toFixed(decimals).replace('.', ',');
}

function StatCard({ label, value, unit, color = 'text-foreground' }) {
  return (
    <div className="bg-card border border-border rounded-xl p-4">
      <p className="text-xs text-muted-foreground mb-1">{label}</p>
      <p className={`text-2xl font-bold tabular-nums ${color}`}>{value}</p>
      {unit && <p className="text-xs text-muted-foreground mt-0.5">{unit}</p>}
    </div>
  );
}

function DataTable({ cols, rows }) {
  if (!rows || rows.length === 0) return null;
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-sm">
        <thead>
          <tr className="border-b border-border bg-secondary/40">
            {cols.map(c => (
              <th key={c.key} className="px-3 py-2 text-left text-xs font-semibold text-muted-foreground uppercase tracking-wide">
                {c.label}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, i) => (
            <tr key={i} className={`border-b border-border/40 ${i % 2 === 0 ? '' : 'bg-secondary/20'}`}>
              {cols.map(c => (
                <td key={c.key} className="px-3 py-2 text-sm text-foreground">
                  {c.render ? c.render(row[c.key], row) : (row[c.key] ?? '—')}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Section({ title, children }) {
  return (
    <div className="bg-card border border-border rounded-xl overflow-hidden">
      <div className="px-4 py-3 border-b border-border bg-secondary/30">
        <h3 className="text-sm font-semibold text-foreground">{title}</h3>
      </div>
      <div className="p-4">{children}</div>
    </div>
  );
}

// ── Fasadas ───────────────────────────────────────────────────────────────────

function FasadasView({ project }) {
  const { fasadai = [], bendra = {}, etics = {} } = project;

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <StatCard label="Bruto plotas" value={fmt(bendra.bruto_m2)} unit="m²" color="text-blue-500" />
        <StatCard label="Neto plotas" value={fmt(bendra.neto_m2)} unit="m²" color="text-emerald-500" />
        <StatCard label="Langai" value={bendra.langu_vnt ?? '—'} unit="vnt." />
        <StatCard label="Perimetras" value={fmt(bendra.perimetras_m)} unit="m" />
      </div>

      {fasadai.length > 0 && (
        <Section title="Fasadai">
          <DataTable
            cols={[
              { key: 'label', label: 'Fasadas' },
              { key: 'bruto_m2', label: 'Bruto m²', render: v => fmt(v) },
              { key: 'neto_m2', label: 'Neto m²', render: v => fmt(v) },
              { key: 'langu_vnt', label: 'Langai' },
              { key: 'duru_vnt', label: 'Durys' },
              { key: 'langu_plotas_m2', label: 'Langų plotas m²', render: v => fmt(v) },
            ]}
            rows={fasadai}
          />
        </Section>
      )}

      <Section title="ETICS sistema (apšiltinimas)">
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-4 gap-3">
          {[
            { key: 'izoliacijos_plotas_m2', label: 'Izoliacijos plotas', unit: 'm²' },
            { key: 'klijai_kg', label: 'Klijai', unit: 'kg' },
            { key: 'smeiges_vnt', label: 'Smeigės', unit: 'vnt.' },
            { key: 'armavimo_tinklelis_m2', label: 'Armavimo tinklelis', unit: 'm²' },
            { key: 'armavimo_misinys_kg', label: 'Armavimo mišinys', unit: 'kg' },
            { key: 'gruntas_l', label: 'Gruntas', unit: 'l' },
            { key: 'dekoratyvinis_tinkas_kg', label: 'Dekoratyvinis tinkas', unit: 'kg' },
            { key: 'cokolinis_profilis_m', label: 'Cokolinis profilis', unit: 'm' },
            { key: 'kampiniai_profiliai_m', label: 'Kampiniai profiliai', unit: 'm' },
            { key: 'palanges_m', label: 'Palangės', unit: 'm' },
          ].map(item => (
            <div key={item.key} className="bg-secondary/30 rounded-lg p-3">
              <p className="text-xs text-muted-foreground">{item.label}</p>
              <p className="text-lg font-semibold tabular-nums text-foreground mt-0.5">
                {fmt(etics[item.key], 1)} <span className="text-xs font-normal text-muted-foreground">{item.unit}</span>
              </p>
            </div>
          ))}
        </div>
      </Section>
    </div>
  );
}

// ── Stogas ────────────────────────────────────────────────────────────────────

function StogasView({ project }) {
  const med = project.medžiagos || {};

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
        <StatCard label="Plano plotas" value={fmt(project.plano_plotas_m2)} unit="m²" />
        <StatCard label="Tikrasis plotas" value={fmt(project.tikrasis_plotas_m2)} unit="m²" color="text-blue-500" />
        <StatCard label="Nuolydžio kampas" value={fmt(project.kampas_laipsniais, 0)} unit="°" color="text-amber-500" />
        <StatCard label="Kraigo ilgis" value={fmt(project.kraigo_ilgis_m)} unit="m" />
        <StatCard label="Nuolydžio koef." value={fmt(project.slope_factor, 3)} unit="" />
        <StatCard label="Latakų perimetras" value={fmt(project.latakų_perimetras_m)} unit="m" />
      </div>

      <Section title="Medžiagų kiekiai">
        <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
          {[
            { key: 'stogo_danga_m2', label: 'Stogo danga', unit: 'm²' },
            { key: 'hidroizoliacijos_m2', label: 'Hidroizoliacija', unit: 'm²' },
            { key: 'latai_m', label: 'Latai', unit: 'm' },
            { key: 'sniegolauziai_m', label: 'Sniegolauženiai', unit: 'm' },
            { key: 'lietvamzdžiai_m', label: 'Lietvamzdžiai', unit: 'm' },
            { key: 'latakai_m', label: 'Latakaiė', unit: 'm' },
          ].map(item => (
            <div key={item.key} className="bg-secondary/30 rounded-lg p-3">
              <p className="text-xs text-muted-foreground">{item.label}</p>
              <p className="text-lg font-semibold tabular-nums text-foreground mt-0.5">
                {fmt(med[item.key], 1)} <span className="text-xs font-normal text-muted-foreground">{item.unit}</span>
              </p>
            </div>
          ))}
        </div>
      </Section>
    </div>
  );
}

// ── Žemės darbai ──────────────────────────────────────────────────────────────

function ZemeView({ project }) {
  const isk = project.iskasa || {};
  const transejos = project.tranšėjos || [];

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <StatCard label="Iškasa" value={fmt(isk.tūris_m3)} unit="m³" color="text-amber-500" />
        <StatCard label="Išvežimas" value={fmt(isk.išvežimas_m3)} unit="m³" />
        <StatCard label="Užpylimas" value={fmt(project.užpylimas_m3)} unit="m³" color="text-emerald-500" />
        <StatCard label="Sutankinimas" value={fmt(project.sutankinimas_m3)} unit="m³" />
      </div>

      <Section title="Iškasa">
        <div className="grid grid-cols-2 gap-3 text-sm">
          <div><span className="text-muted-foreground">Grunto tipas:</span> <span className="font-medium ml-1">{isk.grunto_tipas || '—'}</span></div>
          <div><span className="text-muted-foreground">Išbrinkimo koef.:</span> <span className="font-medium ml-1">{isk.išbrinkimo_koef ? `${(isk.išbrinkimo_koef * 100).toFixed(0)}%` : '—'}</span></div>
          <div><span className="text-muted-foreground">Tranšėjų tūris:</span> <span className="font-medium ml-1">{fmt(project.tranšejų_tūris_m3)} m³</span></div>
        </div>
      </Section>

      {transejos.length > 0 && (
        <Section title="Tranšėjos">
          <DataTable
            cols={[
              { key: 'tipas', label: 'Tipas' },
              { key: 'ilgis_m', label: 'Ilgis m', render: v => fmt(v) },
              { key: 'gylis_m', label: 'Gylis m', render: v => fmt(v, 2) },
              { key: 'tūris_m3', label: 'Tūris m³', render: v => fmt(v, 2) },
            ]}
            rows={transejos}
          />
        </Section>
      )}
    </div>
  );
}

// ── Betonas ───────────────────────────────────────────────────────────────────

function BetonasView({ project }) {
  const elementai = project.elementai || [];

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
        <StatCard label="Betono tūris" value={fmt(project.betono_turis_m3, 2)} unit="m³" color="text-blue-500" />
        <StatCard label="Su atliekomis" value={fmt(project.su_atliekomis_m3, 2)} unit="m³" />
        <StatCard label="Klojiniai" value={fmt(project.klojiniai_m2)} unit="m²" color="text-amber-500" />
        <StatCard label="Armatūra" value={fmt(project.armatūra_t, 2)} unit="t" color="text-emerald-500" />
      </div>

      <div className="bg-card border border-border rounded-xl p-4 flex items-center gap-3">
        <span className="text-sm text-muted-foreground">Betono klasė:</span>
        <Badge variant="outline" className="font-mono text-sm border-primary/40 text-primary">
          {project.betono_klase || 'C25/30'}
        </Badge>
        <span className="text-sm text-muted-foreground ml-4">Armatūra:</span>
        <span className="font-semibold text-sm">{project.armatūra_kg ? `${project.armatūra_kg.toLocaleString('lt-LT')} kg` : '—'}</span>
      </div>

      {elementai.length > 0 && (
        <Section title="Elementai">
          <DataTable
            cols={[
              { key: 'tipas', label: 'Tipas' },
              { key: 'tūris_m3', label: 'Tūris m³', render: v => fmt(v, 3) },
              { key: 'klojiniai_m2', label: 'Klojiniai m²', render: v => fmt(v, 2) },
            ]}
            rows={elementai}
          />
        </Section>
      )}
    </div>
  );
}

// ── Main component ────────────────────────────────────────────────────────────

const TYPE_LABELS = {
  fasadas: 'Fasadų projektas',
  stogas:  'Stogo projektas',
  zeme:    'Žemės darbai',
  betonas: 'Betono konstrukcijos',
};

export default function ConstructionProject({ project }) {
  const tipas = project.tipas;

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-2">
        <Badge variant="outline" className="text-xs border-border">
          {TYPE_LABELS[tipas] || tipas}
        </Badge>
        {project.fasadu_skaicius != null && (
          <span className="text-xs text-muted-foreground">{project.fasadu_skaicius} fasad{project.fasadu_skaicius === 1 ? 'as' : 'ai'}</span>
        )}
      </div>

      {tipas === 'fasadas' && <FasadasView project={project} />}
      {tipas === 'stogas'  && <StogasView  project={project} />}
      {tipas === 'zeme'    && <ZemeView    project={project} />}
      {tipas === 'betonas' && <BetonasView project={project} />}

      {!['fasadas', 'stogas', 'zeme', 'betonas'].includes(tipas) && (
        <p className="text-sm text-muted-foreground">Nežinomas projekto tipas: {tipas}</p>
      )}
    </div>
  );
}
