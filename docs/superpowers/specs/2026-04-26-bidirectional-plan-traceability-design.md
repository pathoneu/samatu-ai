# Bidirectional Plan ↔ Task Traceability — Design Spec

**Author:** Sąmatų AI komanda
**Date:** 2026-04-26
**Status:** Draft, awaiting user review

## Goal

Padaryti, kad **kiekvieną darbų sąrašo eilutę** būtų galima atsekti į konkrečią vietą brėžinyje, ir atvirkščiai — spausti ant brėžinio elemento, gauti visas su juo susijusias darbų pozicijas. Užpildyti spragą tarp „AI suskaičiavo X" ir „kur tas X yra brėžinyje?".

**Inspiracija:** Togal.ai's single-canvas layout su classifications panel, bet **veikiantis geriau** trijose srityse:
1. Bidirectional linking (Togal turi tik forward; mes turim abiem kryptim).
2. Visi LT-specifiniai pozicijų tipai (Togal turi tik counts/areas/lines, mes turim ir formules).
3. Resizable kontekstinė panelė vietoj fixed sidebar.

**Non-goal:** dizaino sistemos pertvarka, spalvų temos keitimas, Sąmatų AI brand identity. Šis spec'as orientuotas tik į traceability ir layout.

## Audience

Pagrindinis vartotojas — LT statybos sąmatininkas (rangovas-tipo profilis). Antrinis — rangovas, peržiūrintis pasiūlymą prieš pradedant darbus. Trečias — klientas, vertinantis pasiūlymo kokybę.

## Architecture

### High-level layout

Atstumiama dabartinė tab'ais paremta navigacija (`Brėžinys / Kiekiai / AI Chat / Eksportas`). Pakeičiama vienos drobės layout'u:

```
┌─ HEADER ─────────────────────────────────────────────────────────┐
│ ← Sąmatų AI / [Projekto pavadinimas]    [⚙] [💾 Eksportuoti ▾]  │
├──────────┬────────────────────────────┬──────────────────────────┤
│ SHEETS   │  PDF + AI overlay          │  POZICIJŲ PANELĖ         │
│ (kairė)  │  (centrinė drobė)          │  (resizable 200-800px)   │
│  60-90px │                            │  default 380px            │
│          │                            │                          │
│ ◯ p1     │  Aktyvus brėžinys + AI     │  Bendra suma             │
│ ● p2     │  overlay (polygons/dots/   │  Patalpos / Pozicijos    │
│ ◯ p3     │  lines pagal poz. tipą)    │  Filtrai + paieška       │
│ + Add    │                            │                          │
└──────────┴────────────────────────────┴──────────────────────────┘
                                            [💬 AI Chat] floating
```

**Three-column flex layout:**
- **Kairė:** sheets sidebar (60-90px, ikonos + numeris). Užtraukiama į 36px slim mode (rodomi tik aktyvūs marker'iai).
- **Centras:** PDF viewer su AI overlay'ais. Užima visą likusį plotą.
- **Dešinė:** resizable pozicijų panel'ė (drag handle, hide button).

**Slėpti kontroliai:**
- AI Chat — floating button (apačioje dešinėje), atsidaro 500×600px overlay panel'ę.
- Eksportas — header dropdown (Excel / PDF / F2 / F3 atskirai).
- Settings (⚙) — header dropdown (mastelio kalibracija, prielaidos, pageStructure peržiūra).

### Position type taxonomy

Kiekviena `darbu_sarasas` eilutė priklauso vienam iš keturių tipų. Tipas lemia vizualinį stilių brėžinyje:

| Tipas | Pavyzdys | Brėžinio overlay | Šaltinis |
|---|---|---|---|
| **Counted** (`vnt`) | Klozeto montavimas, Rozetės, Sviestuvai | Raudoni dot'ai (8px radius) prie kiekvieno simbolio | `detected_symbols.by_type[*].pages[*].symbols[*].{x_pct,y_pct}` |
| **Area** (`m²`) | Sienų dažymas, GKP lubos, Plytelės | Polygons spalvotai užpildyti (40% opacity) | `v8_rooms[*].polygon_pdf` arba `bbox_pct` |
| **Linear** (`m`) | Kampų silikonavimas, Grindjuostės | Mėlynos linijos (3px) išilgai perimetro | Apskaičiuotas iš `v8_rooms[*].perimetras_m` |
| **Formula** (be tiesioginio plano šaltinio) | Šiukšlių išvežimas (5% × bendras plotas), Pastoliai | Be vizualinio overlay'o; tooltip su formulę | `position.source` lauko paaiškinimas |

Kiekvienos pozicijos JSON struktūra papildoma:
```json
{
  "eil_nr": 7,
  "aprasymas": "Klozeto montavimas",
  "kiekis": 1,
  "mato_vnt": "vnt",
  "kategorija": "Santechnika",
  "trace_type": "counted",       // counted | area | linear | formula
  "trace_links": [               // BACKEND grąžina iš detected_symbols/v8_rooms
    { "page_nr": 5, "x_pct": 0.42, "y_pct": 0.61, "confidence": "high" }
  ],
  "detected": true,
  "source": "AI Vision (santechnikos planas)",
  "confidence": "medium"
}
```

`trace_links` formatas keičiasi pagal `trace_type`:
- `counted` — sąrašas `{page_nr, x_pct, y_pct, confidence}` per kiekvieną simbolį.
- `area` — sąrašas `{page_nr, polygon_pdf, page_width_pdf, page_height_pdf}` per kiekvieną kambarį.
- `linear` — sąrašas `{page_nr, polygon_pdf, page_width_pdf, page_height_pdf, type:'perimeter'}`.
- `formula` — `[]`, ir vietoj jos `formula_explanation` laukas (text).

### Forward direction (eilutė → brėžinys)

**Hover** (250ms delay):
- Brėžinyje atitinkami elementai gauna pulse animation (150ms ease-in-out).
- Be tab'o pakeitimo, be sheet switch — tik aktyvaus puslapio elementai mirksi.
- Jei ant aktyvaus puslapio nėra elementų (visi kitame puslapyje), pulse rodomas tik sheets sidebar'e (puslapio numeris pulses).

**Click:**
- Jei `trace_links` turi elementą aktyviame puslapyje → zoom į pirmo elemento koordinatę, parodyti raudoną marker'į (16px circle), eilutė pažymima panel'ėje.
- Jei NĖRA aktyviame puslapyje, bet yra kitame → auto-switch sheet į `trace_links[0].page_nr`, tada zoom + marker.
- Jei `trace_type === 'formula'` → atsidaro popover su `formula_explanation` (pvz. „5 m³ = bendras plotas (96.5 m²) × 0.05 m³/m² koeficientas").

**Marker'is** liekamas 5 sekundes, tada fade out. Užvedus ant marker'io — tooltip „Klozeto montavimas, 1 vnt".

### Reverse direction (brėžinys → eilutė)

**Click ant kambario polygono:**
- Atsidaro popover (positioned next to click point, max 360px width).
- Popover content:
  - Header: `Vonia 1 · 5.5 m²` (pavadinimas + plotas).
  - Sąrašas pozicijų, kurios prisidėjo prie šio kambario, sugrupuotas pagal `kategorija`:
    - **Santechnika:** Klozetas (1), Maišytuvai (2), Trapas (1)
    - **Plytelių darbai:** Plytelės grindys (5.5m²), sienos (12m²), Kampų silikonavimas (9.6m)
    - **Hidroizoliacija:** 1 vnt
  - Apatinė nuoroda: „Visus rodyti pilname sąraše →" (scroll'ina dešinėje panel'ėje).

**Click ant simbolio dot'o:**
- Mažesnis tooltip (positioned above dot, max 280px).
- Content: `Klozetas (1 iš 2 vnt) · Santechnika`.
- Click ant tooltip → highlight'ina eilutę dešinėje panel'ėje.

**Click ant linijos (linear pozicijos overlay):**
- Tooltip: `Kampų silikonavimas, 9.6m · Vonia 1`.
- Click → highlight'ina eilutę panel'ėje.

### Right panel structure

Panel'ė turi 3 sekcijas, visos collapsible:

```
┌─ Bendra suvestinė (sticky top, ~60px) ─────────┐
│  12 458,75 €    21% PVM: 15 074,09 €           │
│  6 patalpų · 96,5m² · 23 pozicijų               │
└─────────────────────────────────────────────────┘
┌─ Filtrai (collapsible) ─────────────────────────┐
│  [paieška...]                                   │
│  [✓] Tik AI-detected   [✓] Slėpti formules     │
└─────────────────────────────────────────────────┘
┌─ Patalpos (collapsible, default open) ──────────┐
│  Svetainė-valgomasis-virtuvė       47,0 m²  ›  │
│  Vonia 1                             5,5 m²  ›  │
│  Miegamasis 1                       14,0 m²  ›  │
│  ...                                            │
└─────────────────────────────────────────────────┘
┌─ Pozicijos (collapsible, default open) ─────────┐
│ ▼ GKP MONTAVIMAS                                │
│   GKP montavimas ant lubų      96.5m²  12€  ─  │
│   Nišų formavimas iš GKP       12.5m   ?€   ─  │
│ ▼ SIENŲ DAŽYMAS                                 │
│   Sienų, lubų glaistymas       330m²  8€   ─   │
│ ...                                             │
└─────────────────────────────────────────────────┘
```

**Patalpos sekcija** rodo per-room suvestinę. Click ant kambario → expand inline su detalėm + auto-zoom į to kambario polygoną.

**Pozicijos sekcija** sugrupuota pagal `skyrius`. Inline edit kainoms (klick ant `?€` → input'as). Eilutės būsenos:
- Default — light bg, no border.
- Hover — pulse brėžinyje, eilutė šviečia (bg-muted).
- Active (clicked) — solid blue border, pulse on row.
- AI-detected — žalias dot prieš aprašymą.
- Fallback (vidurkis) — geltonas dot.
- Formula — pilkas info icon su tooltip.

### Resizable behavior

Panel'ė turi 4 būsenas:
- **Slim** (240px) — kompakti, tik aprašymai + kiekiai.
- **Default** (380px) — su kainomis ir mygtukais.
- **Wide** (560px) — su sumas + sumas/skyrius.
- **Fullscreen** (calc(100% - sheets sidebar)) — pilna sąmatos peržiūra, brėžinys minimizuotas iki 80px miniature apačioje.

State persistuojamas localStorage (`samatu_panel_width: 380`).

Drag handle — 4px wide vertical bar tarp drobės ir panel'ės. Hover state: cursor: col-resize, BG = blue-500/20.

Slėpti mygtukas (X) panel'ės header'yje — slepia panel'ę į 0, vietoje liks 24px bar su rodyklės ikona „Atidaryti panel'ę".

### Sheets sidebar

Kompakti vertikali list'a kairėje. Per sheet'ą:
- Numeris (didelis)
- Mažas tipas indikatorius (puslapio tipas iš `page_classifications`: aukšto planas, lubų, elektros, santechnikos)
- Mažas dot indikatorius — `pulse` jei vartotojas užvedė ant pozicijos, kurios elementai yra šiame puslapyje (kross-sheet hover/click hint'as).

Slim mode (vartotojas spausdo ▶ button viršuje) — tik 36px wide su numeriais, be ikonų.

### Multi-page handling

Kai vartotojas spausdo ant pozicijos, kurios elementai yra ne aktyviame puslapyje:
1. Highlight'ina sheets sidebar'e tikslinį puslapį (orange border, 1s).
2. 200ms delay (kad vartotojas pamatytų hint'ą), tada auto-switch.
3. Po sheet switch, additional 200ms delay, tada zoom + marker.

Jei `trace_links` apima kelis puslapius (pvz. visi sviestuvai per visą butą), pirmas click'as eina į pirmą puslapį. Atsiranda navigation popover šalia marker'io: `1/5 sviestuvų. [< Ankstesnis]  [Kitas →]`.

### Performance considerations

**Konkrečios optimizacijos:**
- Polygons brėžinyje rendering: Konva su `listening: false` ne-active layer'iams.
- Pozicijų panel'ė: virtual scroll jei `darbu_sarasas.length > 50` (react-window).
- Hover debouncing: 250ms before pulse triggers (avoid flicker on accidental hover).
- AI overlay polygons cap: rodyti max 50 polygons aktyviame puslapyje (jei daugiau, drop'inti pagal `area_m2` mažuosius).
- Sheets sidebar — thumbnails generated lazily (intersection observer).

### Migration plan

Šis dizainas RADIKALIAI keičia esamą tab struktūrą. Migracija dirba etapais, kad jei viduryje sustojam, sistema vis dar functional:

**Etapas 1: Backend**
- `extract_v8` ir `extract_v9` papildomi `trace_type` + `trace_links` laukais kiekvienai pozicijai.
- `pasiul["darbu_sarasas"][*]` gauna naujus laukus.
- Backward compat: senos UI versijos vis dar veikia (laukus tiesiog ignoruoja).

**Etapas 2: Frontend layout pertvarkymas**
- Sukuriamas naujas komponentas `ProjectCanvas.jsx` (single-canvas wrapper).
- `InteriorWorkspace.jsx` ir `ProjectMainView.jsx` deprecated, bet liekamas legacy fallback'ui.
- `InteriorProject.jsx` `tab` state default'as → `'canvas'`. Jei vartotojas localStorage turi senų projektų — fallback į tab UI.

**Etapas 3: Linkavimo komponentai**
- `TraceOverlay.jsx` — naujas komponentas, kuris ima `darbu_sarasas[i].trace_links` ir piešia atitinkamą overlay (dot'ai/polygons/lines).
- `PositionRow.jsx` — eilutė panel'ėje su hover/click handlers.
- `RoomTooltip.jsx` — popover, kuris atsidaro ant kambario polygono click'o.

**Etapas 4: Pilna integracija**
- Tab nav išmetamas.
- AI Chat / Eksportas perkeliami į floating button + header dropdown.
- Sheets sidebar tampa pirmaeile navigacijos struktūra.

## Components

### Frontend (React)

```
ProjectCanvas/
├── ProjectCanvas.jsx           # Top-level layout: sheets | canvas | panel
├── SheetsSidebar.jsx           # Kairė puslapių navigacija
├── PdfCanvas.jsx               # Centrinis PDF viewer (renaming PdfViewer.jsx)
│   ├── AiRoomOverlay.jsx       # Polygons (egzistuoja)
│   ├── TraceOverlay.jsx        # NAUJAS: dots/polygons/lines per active row
│   ├── SymbolCounter.jsx       # Click-to-count (egzistuoja)
│   └── HoverPulseLayer.jsx     # NAUJAS: pulse animation hover'iui
├── PositionsPanel.jsx          # Dešinė panelė (resizable)
│   ├── PanelHeader.jsx         # Bendra suvestinė + filtrai
│   ├── RoomsSection.jsx        # Patalpos collapsible
│   ├── PositionsSection.jsx    # Pozicijos collapsible (su skyriais)
│   └── PositionRow.jsx         # Atskira eilutė su hover/click
├── popovers/
│   ├── RoomTooltip.jsx         # Click ant polygono
│   ├── SymbolTooltip.jsx       # Click ant dot'o
│   └── FormulaTooltip.jsx      # Click ant formulės pozicijos
└── shared/
    ├── usePanelWidth.js        # Hook localStorage panel'ės width'ui
    ├── useTraceState.js        # Hook globalaus active row + hover state'ams
    └── pdfCoords.js            # Konversijos PDF↔px pikseliais
```

### Backend (Python)

Backend funkciniu pakeitimas — kiekviena `additional_positions` eilutė papildoma `trace_type` + `trace_links` laukais:

```python
# interior_v8/universal_engine.py
def calc_additional_positions(rooms_calculated, totals, user_prefs, detected_symbols):
    # ... existing code ...

    # NAUJAS — kiekviena pozicija gauna trace_type + trace_links
    for pos in additional:
        pos["trace_type"] = _classify_trace_type(pos)  # counted/area/linear/formula
        pos["trace_links"] = _build_trace_links(pos, rooms_calculated, detected_symbols)
        if pos["trace_type"] == "formula":
            pos["formula_explanation"] = _explain_formula(pos)

def _classify_trace_type(position):
    """Pagal mato_vnt + aprašymą — counted/area/linear/formula."""
    vnt = position.get("vnt", "").lower()
    if vnt in ("vnt", "kompl"): return "counted"
    if vnt in ("m2", "m²"): return "area"
    if vnt == "m": return "linear"
    if vnt in ("d.d", "m3", "m³"): return "formula"
    return "formula"  # fallback

def _build_trace_links(position, rooms, detected_symbols):
    """Surenkam visas brėžinio koordinates šiai pozicijai."""
    # Implementacija pagal trace_type — žr. detalų plan.
    ...
```

Funkcija `_build_trace_links` yra pagrindinis darbas. Detalė per kiekvieną tipą:
- `counted` → ima iš `detected_symbols.by_type[symbol_type].pages[*].symbols[*]`.
- `area` → ima visų kambarių `polygon_pdf` (kuriuose ši pozicija aktuali — pvz. dažymas ne garaže).
- `linear` → ima visų kambarių polygon perimeter (kuriuose pozicija aktuali — kampų silikonavimas tik drėgnose patalpose).
- `formula` → tuščia, plus `formula_explanation` text.

## Data flow

```
User uploads PDF
    ↓
Backend V8 endpoint
    ├─ Vision extract_v7 → patalpos
    ├─ page_classifier → puslapių tipai
    ├─ detect_all_symbols_for_pdf → simboliai
    ├─ extract_v8(rooms, detected_symbols)
    │   └─ calc_additional_positions
    │       └─ +trace_type + trace_links per kiekvieną poziciją
    └─ generate_pasiulymas → darbu_sarasas su trace info
    ↓
Frontend localStorage save
    ↓
ProjectCanvas mounted
    ├─ SheetsSidebar (PDF puslapių navigacija)
    ├─ PdfCanvas + TraceOverlay (active row → atitinkami overlay'ai)
    └─ PositionsPanel (sąrašas su hover/click)
    ↓
User interactions
    ├─ Hover row → useTraceState.setHovered(rowId)
    │   └─ TraceOverlay pulses on canvas
    ├─ Click row → useTraceState.setActive(rowId) + auto-jump page if needed
    │   └─ TraceOverlay shows marker, scrollTo polygon
    ├─ Click polygon → setActiveRoom + RoomTooltip popover
    └─ Click symbol dot → setActiveSymbol + SymbolTooltip popover
```

## Error handling

**Trūksta `trace_links`** (legacy projektai) — eilutė vis dar rodo, bet hover/click neturi efekto. Vietoje žaliame/geltoname dot'o rodomas pilkas „nesusieta" indikatorius su tooltip „Šis projektas sukurtas anksčiau, susiejimas neprieinamas".

**Multi-page sheet switch nepavyko** (PDF render error) — show toast „Nepavyko atidaryti puslapio N. Pabandykite per Sheets sidebar."

**Hover performance crash** (per daug overlay'ų) — fallback į static highlight (be pulse animation) kai polygons.length > 30.

**Backend `trace_type === 'formula'` be `formula_explanation`** — popover rodo „Skaičiavimas: žiūrėk source" kaip fallback.

**Resizable panel below min width** — clamp į 200px, neleisti uždaryti accidentally.

## Testing strategy

**Unit tests:**
- `_classify_trace_type` — visų `mato_vnt` reikšmių mapping.
- `_build_trace_links` — per kiekvieną tipą, ar grąžinama teisinga koordinatė struktūra.
- `usePanelWidth` hook — localStorage save/load, clamp limits.

**Integration tests:**
- E2E flow: upload PDF → V8 endpoint → check kiekvienos pozicijos `trace_type` + `trace_links` validūs.
- Frontend mock data: ProjectCanvas su 3 patalpomis + 5 pozicijomis, click row → verify overlay rendering.

**Manual QA on real projects (P1-P5):**
- Hover ant „Klozeto montavimas" — patikrinti, ar dot'as mirga teisingoje vietoje.
- Click ant „Sienų dažymas 330m²" — patikrinti, ar visi 6 patalpos polygons paryškinti.
- Click ant „Šiukšlių išvežimas 5m³" — patikrinti, ar atsidaro formulę popover.
- Multi-page navigation — klozetas p.5 + user on p.1, click → auto-switch.

## Open questions / future work

- **Bulk multi-row select** — vartotojas pažymi kelias eilutes, brėžinyje matosi visi atitinkami elementai vienu metu (galima ignoruoti pirmoje versijoje).
- **Print/Export su trace info** — ar pasiūlymo PDF reikia rodyti screenshot brėžinio gabaliuko prie kiekvienos eilutės? Atsidėjus ateičiai.
- **Mobile/responsive** — three-column layout neveikia <768px. Mobiliems likti tab UI fallback'as.
- **Color theme** — šiuo metu dark only. Light mode toggle palikti ateičiai (nepriklausomas projekto darbas).
- **F2/F3 export** — ar trace info reikia įtraukti į F2/F3 forma? Atsakymas nežinomas; greičiausiai NE, F2/F3 yra atsiskaitymo dokumentai be brėžinių.

## Glossary

- **Pozicija** — viena darbų sąrašo eilutė (pvz. „Klozeto montavimas — 1 vnt").
- **Trace type** — kategorija pagal kaip pozicija susiejama su brėžiniu (counted/area/linear/formula).
- **Trace links** — koordinačių sąrašas, nurodantis brėžinyje vietą.
- **Active row** — vartotojo paspausta pozicija dešinėje panel'ėje (single-selection).
- **Pulse** — minkštas opacity animation (0.4 → 1.0 → 0.4 per 1.5s) kuris naudojamas hover indikacijai.
