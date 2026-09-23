/**
 * SetupWizard — pirmojo apsilankymo nustatymai.
 *
 * Vartotojas atsako į 5–7 paprastus klausimus, kad app pritaikytų
 * skaičiavimus pagal jo įmonės stilių. Atsakymai išsaugomi į localStorage
 * raktą "samatu_user_prefs" ir naudojami kaip rules_override siunčiant
 * į backend V8 universal_engine.
 *
 * Pirmas paleidimas: rodoma viršuje. Vėliau — modal per "Nustatymai" mygtuką.
 */

import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import {
  Settings, ChevronRight, ChevronLeft, Check, Sparkles, X,
} from 'lucide-react';

const STORAGE_KEY = 'samatu_user_prefs';

// ── Default preferences (industries standart) ─────────────────────────────────

export const DEFAULT_PREFS = {
  // Vonios kambariai
  bathroom_tile_height_m: 2.0,         // 2.0m default; alt 2.4m (iki lubų)
  bathroom_walls_painted_above_tiles: true,

  // Virtuvė
  kitchen_backsplash_height_m: 0.6,
  kitchen_counter_length_m: 3.0,       // the band runs along the counter, not round the room (2026-09-23)

  // Drabužinės / sandėliukai
  drabuzine_painted: true,             // industries: PAINTED (Easy Takeoffs)
  sandeliukas_painted: true,
  rubine_painted: true,

  // Negyvenamos patalpos
  garazas_painted: false,              // STANDART: NOT painted
  tamburas_painted: false,
  katiline_painted: true,              // utility room — painted

  // Lubos
  default_ceiling_height_m: 2.82,
  high_ceiling_threshold_m: 3.0,       // virš ko skaičiuoti atskirą poziciją

  // Skaičiavimo metodas
  openings_threshold_m2: 1.0,          // openings <1m² ne atimama (NRM2)
  default_door_area_m2: 1.85,          // 0.9 × 2.05
  default_window_area_m2: 1.80,        // FIX 2026-04-29: was 1.40 (US std), LT std = 1.20×1.50 = 1.80

  // Sprint §20 (2026-04-29): pridėti naujieji standartai
  paint_deduction_standard: 'LT',      // LT | NRM2 | VOB (Sprint §2A.1)
  paint_class: 2,                      // 1 | 2 | 3 (Sprint §2A.5, EN 13300)

  // Sienos storis (Sprint §20). Vidaus pertvaros vs nešanti siena vs išorinė.
  sienos_storis_m: 0.10,               // GK pertvara default; mūro = 0.20-0.25; isol exterior = 0.30-0.50
  exterior_wall_thickness_m: 0.40,

  // Kampai
  // 2026-09-10, measured on six contractor sąmatos: bead on the rooms' own
  // corners too lands within a quarter on 4 of 6 (2 within a tenth); „tik
  // išoriniai" on 2 (1). Sent with every upload, so `false` here silently
  // computed every new project the way the UI did NOT show („Ką skaičiuoti"
  // pre-selects „Su patalpų vidiniais kampais"). The choice stays per project.
  count_inner_corners: true,
  count_outer_corners: true,

  // Glaistas
  glaistas_q_lygis: 'Q2',              // Q1/Q2/Q3/Q4
  glaistas_storis_mm: 1.25,

  // Dažymo sluoksnių skaičius
  paint_coats: 2,                      // 1 / 2 / 3 — paint_class lemia automatiškai bet user gali override

  // Atliekos
  paint_waste_pct: 8,
  tile_waste_pct: 10,
  drywall_waste_pct: 10,

  // Tile metodas
  tile_method: 'tikslus',              // 'tikslus' (su angų atemimu) | 'praktinis' (be)

  // Pirmenybės
  language: 'lt',
  currency: 'EUR',
  vat_rate: 21,

  // Vartotojo identifikacija
  setup_completed: false,
  setup_version: 1,
};

// ── Load / save ───────────────────────────────────────────────────────────────

export function loadPrefs() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (!raw) return DEFAULT_PREFS;
    const parsed = JSON.parse(raw);
    return { ...DEFAULT_PREFS, ...parsed };
  } catch {
    return DEFAULT_PREFS;
  }
}

export function savePrefs(prefs) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify({
      ...prefs,
      setup_completed: true,
    }));
  } catch (e) {
    console.error('Failed to save prefs', e);
  }
}

// ── Wizard steps ──────────────────────────────────────────────────────────────

const STEPS = [
  {
    id: 'welcome',
    title: 'Sveiki!',
    icon: Sparkles,
    desc: 'Atsakykite į kelis paprastus klausimus, kad galėtume pritaikyti skaičiavimus pagal Jūsų įmonės stilių.',
  },
  {
    id: 'vonia',
    title: 'Vonios kambariai',
    desc: 'Iki kokio aukščio klijuojate plyteles?',
  },
  {
    id: 'rooms',
    title: 'Patalpų tipai',
    desc: 'Kurias patalpas dažote?',
  },
  {
    id: 'corners',
    title: 'Glaistymo kampai',
    desc: 'Kaip skaičiuojate kampus?',
  },
  {
    id: 'tiles',
    title: 'Plytelės',
    desc: 'Skaičiavimo metodas',
  },
  {
    id: 'done',
    title: 'Viskas paruošta',
    icon: Check,
    desc: 'Galite koreguoti šiuos nustatymus bet kada per mygtuką „Nustatymai“.',
  },
];

// ── Component ─────────────────────────────────────────────────────────────────

export default function SetupWizard({ onComplete, onClose }) {
  const [step, setStep] = useState(0);
  const [prefs, setPrefs] = useState(loadPrefs());

  const update = (patch) => setPrefs(p => ({ ...p, ...patch }));

  const currentStep = STEPS[step];
  const isLast = step === STEPS.length - 1;
  const isFirst = step === 0;

  const handleNext = () => {
    if (isLast) {
      savePrefs(prefs);
      onComplete?.(prefs);
    } else {
      setStep(s => s + 1);
    }
  };

  const handleBack = () => {
    if (!isFirst) setStep(s => s - 1);
  };

  return (
    <div className="fixed inset-0 z-50 bg-black/40 backdrop-blur-sm flex items-center justify-center p-4">
      <div className="bg-card rounded-2xl shadow-2xl w-full max-w-xl max-h-[90vh] flex flex-col overflow-hidden">

        {/* Header */}
        <div className="px-6 py-4 border-b border-border flex items-center justify-between">
          <div className="flex items-center gap-2">
            <Settings className="w-5 h-5 text-muted-foreground" />
            <span className="font-semibold text-foreground">Pradiniai nustatymai</span>
          </div>
          {onClose && (
            <button
              onClick={onClose}
              className="p-1.5 hover:bg-muted rounded-lg text-muted-foreground hover:text-foreground"
            >
              <X className="w-4 h-4" />
            </button>
          )}
        </div>

        {/* Progress */}
        <div className="px-6 pt-4">
          <div className="flex gap-1">
            {STEPS.map((s, i) => (
              <div
                key={s.id}
                className={`h-1 flex-1 rounded-full transition-colors ${
                  i <= step ? 'bg-primary' : 'bg-muted'
                }`}
              />
            ))}
          </div>
          <div className="text-xs text-muted-foreground mt-2">
            Žingsnis {step + 1} iš {STEPS.length}
          </div>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-6 py-5">
          <h2 className="text-xl font-bold text-foreground mb-1 flex items-center gap-2">
            {currentStep.icon && <currentStep.icon className="w-5 h-5 text-muted-foreground" />}
            {currentStep.title}
          </h2>
          <p className="text-sm text-muted-foreground mb-5">{currentStep.desc}</p>

          {currentStep.id === 'welcome' && (
            <div className="bg-muted border border-border rounded-lg p-4 text-sm text-foreground">
              <p className="mb-2">
                <strong>Pathon</strong> dirba pagal tarptautinius pramonės
                standartus (RICS NRM2, DIN 18363, CSI MasterFormat).
              </p>
              <p>
                Tačiau kiekvienos įmonės stilius šiek tiek skiriasi —
                šis trumpas vedlys padės tai pritaikyti.
              </p>
            </div>
          )}

          {currentStep.id === 'vonia' && (
            <div className="space-y-4">
              <Label className="text-sm">Plytelių aukštis vonios kambariuose</Label>
              <div className="grid grid-cols-3 gap-2">
                {[1.5, 2.0, 2.4].map(h => (
                  <button
                    key={h}
                    onClick={() => update({ bathroom_tile_height_m: h })}
                    className={`p-3 rounded-lg border-2 text-center transition-colors ${
                      prefs.bathroom_tile_height_m === h
                        ? 'border-foreground bg-muted'
                        : 'border-border hover:border-primary/40'
                    }`}
                  >
                    <div className="font-bold text-lg text-foreground">{h.toFixed(1)} m</div>
                    <div className="text-xs text-muted-foreground">
                      {h === 1.5 ? 'Žemai' : h === 2.0 ? 'Standartas' : 'Iki lubų'}
                    </div>
                  </button>
                ))}
              </div>

              <div className="border-t border-border pt-4">
                <label className="flex items-start gap-3 cursor-pointer">
                  <input
                    type="checkbox"
                    checked={prefs.bathroom_walls_painted_above_tiles}
                    onChange={e => update({ bathroom_walls_painted_above_tiles: e.target.checked })}
                    className="mt-1 w-4 h-4 accent-foreground"
                  />
                  <div>
                    <div className="text-sm text-foreground">
                      Dažyti sienas virš plytelių
                    </div>
                    <div className="text-xs text-muted-foreground">
                      Standartas: dažoma iki lubų virš plytelių
                    </div>
                  </div>
                </label>
              </div>
            </div>
          )}

          {currentStep.id === 'rooms' && (
            <div className="space-y-1">
              {[
                { key: 'drabuzine_painted', label: 'Drabužinės', note: 'Pramonės standartas: TAIP' },
                { key: 'rubine_painted', label: 'Rūbinės', note: '' },
                { key: 'sandeliukas_painted', label: 'Sandėliukai', note: '' },
                { key: 'katiline_painted', label: 'Katilinės', note: 'Pagal poreikį' },
                { key: 'garazas_painted', label: 'Garažai', note: 'Standartas: NE' },
                { key: 'tamburas_painted', label: 'Tambūrai', note: 'Standartas: NE' },
              ].map(({ key, label, note }) => (
                <label
                  key={key}
                  className="flex items-center justify-between py-3 border-b border-border last:border-0 cursor-pointer hover:bg-muted/60 -mx-2 px-2 rounded"
                >
                  <div>
                    <div className="text-sm font-medium text-foreground">{label}</div>
                    {note && <div className="text-xs text-muted-foreground">{note}</div>}
                  </div>
                  <input
                    type="checkbox"
                    checked={prefs[key]}
                    onChange={e => update({ [key]: e.target.checked })}
                    className="w-5 h-5 accent-foreground"
                  />
                </label>
              ))}
            </div>
          )}

          {currentStep.id === 'corners' && (
            <div className="space-y-3">
              <label className="flex items-start gap-3 p-3 border-2 border-border rounded-lg cursor-pointer hover:border-primary/40 has-[:checked]:border-amber-500 has-[:checked]:bg-amber-500/15">
                <input
                  type="checkbox"
                  checked={prefs.count_outer_corners}
                  onChange={e => update({ count_outer_corners: e.target.checked })}
                  className="mt-1 w-4 h-4 accent-foreground"
                />
                <div>
                  <div className="text-sm font-medium text-foreground">
                    Skaičiuoti išorės kampus
                  </div>
                  <div className="text-xs text-muted-foreground">
                    Standartas: TAIP — kampų profiliai (corner bead)
                  </div>
                </div>
              </label>

              <label className="flex items-start gap-3 p-3 border-2 border-border rounded-lg cursor-pointer hover:border-primary/40 has-[:checked]:border-amber-500 has-[:checked]:bg-amber-500/15">
                <input
                  type="checkbox"
                  checked={prefs.count_inner_corners}
                  onChange={e => update({ count_inner_corners: e.target.checked })}
                  className="mt-1 w-4 h-4 accent-foreground"
                />
                <div>
                  <div className="text-sm font-medium text-foreground">
                    Skaičiuoti vidaus kampus
                  </div>
                  <div className="text-xs text-muted-foreground">
                    Standartas: NE (paprastai kampuotis nereikalingas)
                  </div>
                </div>
              </label>

              <div className="border-t border-border pt-4">
                <Label className="text-sm">Glaisto Q lygis</Label>
                <div className="grid grid-cols-4 gap-2 mt-2">
                  {['Q1', 'Q2', 'Q3', 'Q4'].map(q => (
                    <button
                      key={q}
                      onClick={() => update({ glaistas_q_lygis: q })}
                      className={`p-2 rounded-lg border-2 text-center text-sm font-medium transition-colors ${
                        prefs.glaistas_q_lygis === q
                          ? 'border-foreground bg-muted text-foreground'
                          : 'border-border hover:border-primary/40 text-muted-foreground'
                      }`}
                    >
                      {q}
                    </button>
                  ))}
                </div>
                <div className="text-xs text-muted-foreground mt-1.5">
                  Q1: tapetams · Q2: matiniams dažams · Q3: pusblizgiams · Q4: blizgiams
                </div>
              </div>
            </div>
          )}

          {currentStep.id === 'tiles' && (
            <div className="space-y-3">
              <Label className="text-sm">Plytelių skaičiavimo metodas</Label>

              <label className="flex items-start gap-3 p-3 border-2 border-border rounded-lg cursor-pointer hover:border-primary/40 has-[:checked]:border-amber-500 has-[:checked]:bg-amber-500/15">
                <input
                  type="radio"
                  name="tile_method"
                  checked={prefs.tile_method === 'tikslus'}
                  onChange={() => update({ tile_method: 'tikslus' })}
                  className="mt-1 w-4 h-4 accent-foreground"
                />
                <div>
                  <div className="text-sm font-medium text-foreground">Tikslus</div>
                  <div className="text-xs text-muted-foreground">
                    Atimami langai, durys, kitos angos. Plotas mažesnis, bet ekonomiška.
                  </div>
                </div>
              </label>

              <label className="flex items-start gap-3 p-3 border-2 border-border rounded-lg cursor-pointer hover:border-primary/40 has-[:checked]:border-amber-500 has-[:checked]:bg-amber-500/15">
                <input
                  type="radio"
                  name="tile_method"
                  checked={prefs.tile_method === 'praktinis'}
                  onChange={() => update({ tile_method: 'praktinis' })}
                  className="mt-1 w-4 h-4 accent-foreground"
                />
                <div>
                  <div className="text-sm font-medium text-foreground">Praktinis</div>
                  <div className="text-xs text-muted-foreground">
                    Be angų atėmimo (atliekos = pjovimo medžiaga). Standartas tarp meistrų.
                  </div>
                </div>
              </label>

              <div className="border-t border-border pt-4">
                <Label className="text-sm">Atliekų % (waste)</Label>
                <div className="grid grid-cols-3 gap-2 mt-2">
                  {[5, 8, 10, 12, 15].map(w => (
                    <button
                      key={w}
                      onClick={() => update({ tile_waste_pct: w })}
                      className={`p-2 rounded-lg border-2 text-center text-sm font-medium transition-colors ${
                        prefs.tile_waste_pct === w
                          ? 'border-foreground bg-muted text-foreground'
                          : 'border-border hover:border-primary/40 text-muted-foreground'
                      }`}
                    >
                      {w}%
                    </button>
                  ))}
                </div>
              </div>
            </div>
          )}

          {currentStep.id === 'done' && (
            <div className="space-y-3">
              <div className="bg-emerald-500/10 border border-emerald-500/30 rounded-lg p-4 text-sm text-foreground">
                <div className="flex items-center gap-2 font-semibold text-emerald-300 mb-2">
                  <Check className="w-4 h-4" />
                  Nustatymai išsaugoti
                </div>
                <p>Šie pasirinkimai bus naudojami visiems naujiems projektams. Galite juos keisti per mygtuką „Nustatymai“ bet kuriuo metu.</p>
              </div>

              <details className="border border-border rounded-lg">
                <summary className="px-4 py-3 cursor-pointer text-sm font-medium text-foreground hover:bg-muted/60">
                  Peržiūrėti pasirinkimus
                </summary>
                <div className="px-4 py-3 border-t border-border text-xs text-muted-foreground space-y-1">
                  <div>Vonios plytelės: <strong>{prefs.bathroom_tile_height_m} m</strong></div>
                  <div>Drabužinės dažomos: <strong>{prefs.drabuzine_painted ? 'TAIP' : 'NE'}</strong></div>
                  <div>Garažai dažomi: <strong>{prefs.garazas_painted ? 'TAIP' : 'NE'}</strong></div>
                  <div>Glaisto lygis: <strong>{prefs.glaistas_q_lygis}</strong></div>
                  <div>Plytelių metodas: <strong>{prefs.tile_method}</strong></div>
                  <div>Plytelių atliekos: <strong>{prefs.tile_waste_pct}%</strong></div>
                </div>
              </details>
            </div>
          )}
        </div>

        {/* Footer */}
        <div className="px-6 py-4 border-t border-border flex items-center justify-between bg-muted">
          <Button
            variant="outline"
            onClick={handleBack}
            disabled={isFirst}
            className="gap-1"
          >
            <ChevronLeft className="w-4 h-4" />
            Atgal
          </Button>

          <Button
            onClick={handleNext}
            className="bg-primary hover:bg-primary/90 text-primary-foreground gap-1"
          >
            {isLast ? 'Pradėti darbą' : 'Toliau'}
            {!isLast && <ChevronRight className="w-4 h-4" />}
            {isLast && <Check className="w-4 h-4" />}
          </Button>
        </div>
      </div>
    </div>
  );
}
