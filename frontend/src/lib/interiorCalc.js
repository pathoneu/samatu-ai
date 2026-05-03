// Frontend calculation engine — mirrors _calculate_finishing_quantities in backend.
// Used for real-time recalculation when user edits assumptions.

const ROOM_LETTER_MAP = {
  a: '102', b: '104', c: '106', d: '107',
  e: '108', f: '109', g: '110', h: '111',
};

const Q_RATES = { Q1: 0.8, Q2: 1.0, Q3: 1.2, Q4: 1.5 };
const Q_THICK = { Q1: 1.2, Q2: 1.25, Q3: 1.75, Q4: 2.5 };

function zoneCategory(ztype) {
  const t = (ztype || '').toLowerCase();
  if (t.includes('daž')) return 'paint';
  if (t.includes('plytel')) return 'tiles';
  if (['plokšt', 'medž', 'tekst', 'tapetai', 'bald', 'veidrod'].some(k => t.includes(k))) return 'panel';
  return 'other';
}

function round1(v) { return Math.round(v * 10) / 10; }
function round2(v) { return Math.round(v * 100) / 100; }

export function calculateInteriorQuantities(rawData, assumptions = {}) {
  const { patalpos = [], sekcijos = {}, meta = {} } = rawData || {};

  const {
    sienos_storis_m = 0.10,
    glaistimo_lygis = 'Q2',
    lubu_auksciai = {},    // { "101": 2.50 } per-room overrides
    custom_windows = null, // null → use sekcijos; array → user-edited
    custom_doors   = null, // null → use meta.doors; array → user-edited
  } = assumptions;

  const doors = custom_doors ?? (meta.doors || []);

  // Group sections by room_nr
  const sectionsByRoom = {};
  for (const [kodas, sec] of Object.entries(sekcijos)) {
    const rNr = sec.room_nr || ROOM_LETTER_MAP[kodas[0]?.toLowerCase()] || '';
    if (rNr) {
      if (!sectionsByRoom[rNr]) sectionsByRoom[rNr] = [];
      sectionsByRoom[rNr].push(sec);
    }
  }

  // 1. DAŽOMAS PLOTAS
  let paintWallsM2 = 0, tilesM2 = 0;

  for (const room of patalpos) {
    const nr = room.nr;
    const defaultH = (room.lubu_aukstis_mm || 2800) / 1000;
    const h = lubu_auksciai[nr] ?? defaultH;
    const aM2 = room.plotas_m2 || 0;
    const sections = sectionsByRoom[nr] || [];

    if (sections.length > 0) {
      let gross = 0, paint = 0, tiles = 0, panels = 0, openings = 0;
      for (const sec of sections) {
        const wMm = sec.width_mm || 0;
        const sHmm = sec.height_mm || h * 1000;
        gross += (wMm * sHmm) / 1_000_000;
        for (const z of (sec.zones || [])) {
          const cat = zoneCategory(z.type);
          const area = z.area_m2 || 0;
          if (cat === 'paint')  paint   += area;
          if (cat === 'tiles')  tiles   += area;
          if (cat === 'panel')  panels  += area;
        }
        for (const op of (sec.openings || [])) {
          openings += ((op.width_mm || 0) / 1000) * ((op.height_mm || h * 1000) / 1000);
        }
      }
      const dazymas = paint > 0 ? paint : Math.max(0, gross - tiles - panels - openings);
      paintWallsM2 += dazymas;
      tilesM2      += tiles;
    } else {
      const perims = meta.room_perimeters_without_iskl || {};
      let perimM = perims[nr]?.estimated_perimeter_mm
        ? perims[nr].estimated_perimeter_mm / 1000
        : 4.1 * Math.sqrt(aM2);
      const doorArea = doors
        .filter(d => (d.between || []).includes(nr))
        .reduce((s, d) => s + (d.width_mm || 900) / 1000 * (d.height_mm || h * 1000) / 1000, 0);
      paintWallsM2 += Math.max(0, perimM * h - doorArea);
    }
  }

  const lubosM2 = patalpos.reduce((s, r) => s + (r.plotas_m2 || 0), 0);

  // 2. GLAISTYMO KAMPAI
  // Prefer visu_kampu_vnt (total corners); fall back outer×3.5; last resort ratio estimate.
  const visuKampaiVnt    = meta.visu_kampu_vnt    || 0;
  const isoriuKampaiVnt  = meta.isoriniu_kampu_vnt || 0;
  const avgH = patalpos.length > 0
    ? patalpos.reduce((s, r) => s + (r.lubu_aukstis_mm || 2800), 0) / patalpos.length / 1000
    : 2.8;
  let kampaiVnt, kampaiSource;
  if (visuKampaiVnt > 0) {
    kampaiVnt   = visuKampaiVnt;
    kampaiSource = 'vision_total';
  } else if (isoriuKampaiVnt > 0) {
    kampaiVnt   = Math.round(isoriuKampaiVnt * 3.5);
    kampaiSource = 'outer_x3.5';
  } else {
    const dazymasTotal = paintWallsM2 + lubosM2;
    kampaiVnt   = avgH > 0 ? Math.round(dazymasTotal * 0.70 / avgH) : 0;
    kampaiSource = 'ratio_estimate';
  }
  const kampaiM = round1(kampaiVnt * avgH);

  // 3. ANGOKRAŠČIAI
  let languVnt = 0, duruVnt = 0, angokrasciaiM = 0;
  const angDetails = [];

  const windows = custom_windows ?? null;
  if (windows) {
    for (const w of windows) {
      const h2 = (w.height_mm || 1500) / 1000;
      const w2 = (w.width_mm  || 1200) / 1000;
      const perim = 2 * h2 + w2;
      angokrasciaiM += perim;
      languVnt++;
      angDetails.push({ tipas: 'langas', plotis_m: round2(w2), aukstis_m: round2(h2), perimetras_m: round2(perim) });
    }
  } else {
    for (const sec of Object.values(sekcijos)) {
      for (const op of (sec.openings || [])) {
        if (!(op.type || '').toLowerCase().includes('lang')) continue;
        const h2 = (op.height_mm || 1400) / 1000;
        const w2 = (op.width_mm  || 1200) / 1000;
        const perim = 2 * h2 + w2;
        angokrasciaiM += perim;
        languVnt++;
        angDetails.push({ tipas: 'langas', plotis_m: round2(w2), aukstis_m: round2(h2), perimetras_m: round2(perim) });
      }
    }
  }

  for (const d of doors) {
    const dh = (d.height_mm || 2200) / 1000;
    const dw = (d.width_mm  ||  900) / 1000;
    const perim = 2 * dh + dw;
    angokrasciaiM += perim;
    duruVnt++;
    angDetails.push({ tipas: 'durys', plotis_m: round2(dw), aukstis_m: round2(dh), perimetras_m: round2(perim) });
  }

  const angArea = round2(angokrasciaiM * sienos_storis_m);

  // 4. LUBŲ PERIMETRAS
  let lubuPerimetrasM = 0;
  for (const room of patalpos) {
    const nr = room.nr;
    const sections = sectionsByRoom[nr] || [];
    if (sections.length > 0) {
      lubuPerimetrasM += sections.reduce((s, sec) => s + (sec.width_mm || 0), 0) / 1000;
    } else {
      const perims = meta.room_perimeters_without_iskl || {};
      lubuPerimetrasM += perims[nr]?.estimated_perimeter_mm
        ? perims[nr].estimated_perimeter_mm / 1000
        : 4.1 * Math.sqrt(room.plotas_m2 || 0);
    }
  }

  // 5. GRINDJUOSTĖS
  let grindjustesM = 0;
  for (const room of patalpos) {
    const nr = room.nr;
    const sections = sectionsByRoom[nr] || [];
    let perimM;
    if (sections.length > 0) {
      perimM = sections.reduce((s, sec) => s + (sec.width_mm || 0), 0) / 1000;
    } else {
      const perims = meta.room_perimeters_without_iskl || {};
      perimM = perims[nr]?.estimated_perimeter_mm
        ? perims[nr].estimated_perimeter_mm / 1000
        : 4.1 * Math.sqrt(room.plotas_m2 || 0);
    }
    const doorWidths = doors
      .filter(d => (d.between || []).includes(nr))
      .reduce((s, d) => s + (d.width_mm || 900) / 1000, 0);
    grindjustesM += Math.max(0, perimM - doorWidths);
  }

  // Additional metrics
  const dazymasVisoM2 = paintWallsM2 + lubosM2;
  // REMOVED Sprint 0 Fix 2: paint formula moved to backend.
  // Frontend should call recomputeApi.recompute() with paint_class to get correct values.
  // These variables intentionally null so any consumer that still reads them gets a
  // visible bug (rather than silently using stale wrong values).
  const dazaiSienoms = null;
  const dazaiLuboms = null;
  const gruntasL      = round1(dazymasVisoM2 * 0.15);
  const gkLapai       = Math.ceil(paintWallsM2 / 3.0 * 1.1);
  const qRate  = Q_RATES[glaistimo_lygis] || 1.0;
  const qThick = Q_THICK[glaistimo_lygis] || 1.25;
  const glastasKg     = Math.round(dazymasVisoM2 * qThick * qRate);
  const glaistaMaisai = Math.ceil(glastasKg / 25);

  // Validation
  const validationNotes = [];
  if (lubosM2 > 0) {
    const ratio = paintWallsM2 / lubosM2;
    if (ratio < 2.0) validationNotes.push(`Sienų/lubų santykis ${ratio.toFixed(1)}× — per mažas (norma 2.5–4×)`);
    if (ratio > 5.0) validationNotes.push(`Sienų/lubų santykis ${ratio.toFixed(1)}× — per didelis (norma 2.5–4×)`);
  }

  return {
    dazomas_plotas: {
      sienos_m2: round1(paintWallsM2),
      lubos_m2:  round2(lubosM2),
      viso_m2:   round1(dazymasVisoM2),
    },
    glaistymo_kampai: {
      kampai_vnt:          kampaiVnt,
      isoriniu_kampu_vnt:  isoriuKampaiVnt,
      vidutinis_aukstis_m: round2(avgH),
      viso_m:              kampaiM,
      skaiciavimo_budas:   kampaiSource,
    },
    angokrasciai: {
      langu_vnt: languVnt,
      duru_vnt:  duruVnt,
      viso_m:    round1(angokrasciaiM),
      viso_m_x2: round1(angokrasciaiM * 2),
      area_m2:   angArea,
      details:   angDetails,
    },
    lubu_perimetras: {
      viso_m: round1(lubuPerimetrasM),
    },
    grindjuostes: {
      viso_m: round1(grindjustesM),
    },
    uzuolaidu_nisos: {
      viso_m:  meta.uzuolaidu_nisu_m || 0,
      details: meta.uzuolaidu_nisos_details || [],
    },
    dazai: {
      sienos_l:  dazaiSienoms,
      lubos_l:   dazaiLuboms,
      gruntas_l: gruntasL,
      viso_l:    round1(dazaiSienoms + dazaiLuboms + gruntasL),
    },
    gk_lapai: { vnt: gkLapai },
    glaistas: {
      lygis:       glaistimo_lygis,
      kg:          glastasKg,
      maisai_25kg: glaistaMaisai,
    },
    validation_notes: validationNotes,
    plyteles_m2: round1(tilesM2),
  };
}

export const DEFAULT_ASSUMPTIONS = {
  sienos_storis_m: 0.10,
  glaistimo_lygis: 'Q2',
  lubu_auksciai:   {},
  custom_windows:  null,
  custom_doors:    null,
};
