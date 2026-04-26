# Lithuanian Architectural Drawing Conventions — Vision Prompt Reference

**Purpose:** Authoritative reference for building a Claude Vision prompt that correctly interprets symbols, colors, text annotations, and layout conventions on Lithuanian residential interior project drawings.

**Regulatory basis:** LST EN ISO 128, LST EN ISO 7519, LST EN ISO 4157, STR 1.05.06:2005, STR 2.02.09:2005, LST 1325:1995.

---

## 1. Symbol Catalog

### 1.1 Doors (Durys)

| Symbol type | Visual description | Interpretation rule |
|---|---|---|
| Standard swing (atdaromosios durys) | Wall gap + quarter-circle arc from one jamb corner; arc radius = door leaf width; arc center = hinge corner | Hinge is where the arc center sits. Width of gap = leaf width (e.g. 800 mm). |
| Double swing (dvigubos durys) | Two arcs each spanning half the opening, meeting at center | Total opening = sum of both leaf widths. |
| Sliding door (slankiojamosios durys) | Wall gap + solid rectangle (leaf) + dashed rectangle showing travel path along wall | No arc. Leaf parks to one side. |
| Pocket door (paslėpta slankiojamoji) | Wall gap + dashed rectangle INSIDE a thickened wall segment | Leaf disappears into wall cavity. Common in high-end LT interiors. |
| Flush/frameless door (beapvadinės / paslėptos durys) | Gap with no visible door frame; thin hairline only; no hardware symbol | Annotated "beapvadinės" or "paslėptos". In plan: looks almost like a plain wall gap. |
| Folding door (sulankstomosios / harmonika) | Zigzag line across the opening | Each fold segment shown as short diagonal. Overall width = opening width. |
| Balcony/terrace door (lauko durys) | Arc + thicker threshold line at wall face | Threshold annotated with level change: "+3" = 30 mm step up, "+0" = flush. |

**Door tags:** Each door has circle tag: D1, D2 … or just "1", "2". Annotation: `900×2100` = 900 mm wide × 2100 mm tall (always W×H, always mm).

### 1.2 Windows (Langai)

| Symbol type | Visual description | Interpretation rule |
|---|---|---|
| Standard casement (paprastas langas) | Two parallel lines across wall thickness; sill line extends slightly beyond interior wall face | Opening width = annotated dimension. Tag references langų sąrašas. |
| Opening sash indicator | Same + one or two diagonal lines across the window rectangle | Single diagonal = one sash opens; X pattern = both sashes open. |
| Floor-to-ceiling / panoramic | Very wide parallel lines; no sill shown at floor | Width > 2000 mm or annotated "panoraminis". |
| Roof window (stoglangis / Velux) | Rectangle with cross-diagonals — appears in CEILING PLAN only, not in wall | Position annotated with distance from walls. |
| Corner window | Parallel lines wrapping continuously around a wall corner | Two dimensions, one per wall face. |

**Window tags:** Circle tag L1, L2 … referencing langų sąrašas. Annotation: `1200×1500` = 1200 mm wide × 1500 mm tall.

### 1.3 Stairs (Laiptai)

Tread lines (closely spaced parallel lines), direction arrow ("AUKŠTYN"/"UP"), 45° dashed cut line at ~1000 mm above FFL, handrail line annotated H=900.

### 1.4 Sanitary Fixtures — Plan View

| Fixture | LT name | Plan symbol | Footprint |
|---|---|---|---|
| WC toilet | Tualeto puodas | Oval (bowl) + smaller oval (seat) attached to wall | 370×700 mm |
| Wall-hung WC | Pakabinamas WC | Oval + dashed rectangle behind wall (in-wall cistern) | 370×520 mm visible |
| Pedestal washbasin | Praustuvas | Oval/rectangle attached to wall; 2 small dots = faucet | 500–600×400–500 mm |
| Countertop basin | Statomas praustuvas | Circle/rectangle on top of vanity rectangle | 400×400 mm bowl |
| Bathtub | Vonia | Large rectangle with rounded end; inner curved line = rim | 700×1500–1700 mm |
| Shower tray | Dušo padėklas | Square/rectangle with center drain circle | 800×800–900×900 mm |
| Wet room shower zone | Dušo zona | Dashed boundary + center drain circle, no tray | Floor-level, annotated "dušo zona" |
| Washing machine | Skalbimo mašina | Rectangle with circle (drum) | 600×600 mm |
| Dishwasher | Indaplovė | Rectangle, no internal symbol | 600×600 mm |
| Kitchen sink | Virtuvės kriauklė | Rectangle with 1–2 oval cutouts | 500–800 mm wide |
| Floor drain | Trapas | Small circle/square with X | Shower zones, utility |
| Radiator | Radiatorius | Thin elongated rectangle at wall; kW/type annotated | Variable length |

LT-specific: Annotations "SM" = skalbimo mašina; "IP" = indaplovė. In-wall cisterns dominant in post-2010.

### 1.5 Built-in Furniture

| Symbol | Description | Interpretation |
|---|---|---|
| Wardrobe (drabužinė/spinta) | Dashed/solid rectangle with door arcs or sliding lines; depth 550–600 mm | Dashed = built-in. Solid = free-standing. |
| Walk-in wardrobe (rūbų kambarys) | Separate room with shelf/rail lines inside | "RK" in eksplikacija |
| Kitchen lower cabinets | Solid thin rectangle along wall, 600 mm depth | Continuous run; sink cutout visible |
| Kitchen upper cabinets | Dashed thin rectangle offset inward, same plan position | Above plan cut level |
| Vanity unit | Rectangle 350–500 mm depth under washbasin | Basin sits on top |
| Built-in bookcase | Rectangle with vertical dividers, 250–350 mm depth | |

**Paint deduction rule:** Solid rectangle touching a wall, depth > 100 mm, height > 600 mm = deduct from paintable wall area.

### 1.6 Wall Hatching by Material

| Material | Hatch pattern | Typical thickness |
|---|---|---|
| Reinforced concrete (gelžbetonas) | Dense 45° diagonals + aggregate dots | 160–300 mm |
| Plain concrete (betonas) | Stippling only or cross-hatch | 100–200 mm |
| Aerated block (Aeroc/Bauroc) | Wavy/sinusoidal horizontal lines | 200–300 int / 375–400 ext |
| Expanded clay/ceramic block (keramzitbetonis/keraminiai) | Brick-pattern courses with staggered short verticals | 190–250 int / 380–500 ext |
| Brick (plyta) | Classic brick hatch with staggered joints | 120–250 mm |
| Drywall partition (GK pertvara) | Thin double lines, no fill, sometimes "GK" | 75–150 mm |
| Insulation (termoizoliacija) | Zigzag or X-pattern fill | Variable |
| Timber stud (medinė karkasas) | Plain outline, "W" or "MK" | 75–100 mm |

**Vision rule:** Dense hatching + thick outline = structural. Thin double-line + no fill = GK. Number alongside wall = thickness in mm.

---

## 2. Eksplikacija Parsing Rules

### 2.1 Standard Column Structure

```
| Nr. | Pavadinimas       | Plotas (m²) | G  | S  | L  | Pastabos     |
|  1  | Koridorius        |    12.50    | P1 | D1 | L1 |              |
|  2  | Svetainė          |    28.30    | P2 | D2 | L2 |              |
|  4  | Vonios kambarys   |     5.80    | P3 | S1 | L3 | drėgna zona  |
```

- **Nr.** — matches circle tags on plan
- **Pavadinimas** — LT room name
- **Plotas** — m² (comma decimal: "14,25")
- **G/S/L** — floor/sienos/lubos finish codes
- **Pastabos** — notes ("drėgna", "aukštis 3.20m", "gresianti zona")

Extended columns sometimes: Perimetras (m), Aukštis (m), Tursis (m³), Langai, Durys.

### 2.2 Finish Code Legend (apdailos lentelė)

```
P1 = Laminuotos grindys (oak, 8mm AC5)
P2 = Keraminės plytelės 600×600
P3 = Epoksidinės grindys
D1 = Dažytos sienos (balta, Q3)
D2 = Tapetai (neaustiniai)
S1 = Keraminės plytelės sienoms (iki 2400mm)
L1 = Dažytos lubos (balta, Q2)
L2 = GK lubų sistema su apšvietimu
L3 = Tempiamos lubos
```

**Parse strategy:** (1) circle tags → numbers; (2) eksplikacija (corners or separate sheet); (3) match → name + area + codes; (4) apdailos lentelė decodes codes → tile vs paint per surface per room.

### 2.3 Common LT Room Abbreviations

| Abbrev | Full | English |
|---|---|---|
| KOR | Koridorius | Corridor |
| SVET | Svetainė | Living |
| VIRTU | Virtuvė | Kitchen |
| SV+V | Svetainė + virtuvė | Open-plan |
| MIEG | Miegamasis | Bedroom |
| VONIA | Vonios kambarys | Bathroom |
| WC/TUA | Tualetas | WC |
| RK | Rūbų kambarys | Walk-in WD |
| KAB | Kabinetas | Study |
| TERASA | Terasa | Terrace |
| LODŽIJA | Lodžija | Loggia |
| SAND | Sandėliukas | Storage |
| TECH | Techninė patalpa | Utility |

---

## 3. Color Legend

### 3.1 Floor Plan Colors

| Color | Meaning | Confidence |
|---|---|---|
| Grey fill | Concrete/block structural walls | HIGH |
| No fill / white | GK partitions or thin block | HIGH |
| Yellow/orange fill | New construction (renovation) | MEDIUM |
| Red fill or outline | Demolished elements | HIGH |
| Green fill | Existing walls to remain | MEDIUM |
| Blue/cyan | Plumbing fixtures or wet zones | MEDIUM |

### 3.2 Interior Finish Plan Colors

- Warm wood tone — laminate/parquet
- Light grey/stone grey — large-format porcelain tile
- White/very light — paint
- Beige/cream — natural stone or smaller tiles
- Dark grey/charcoal — dark tiles (vonia/wc)
- Green/teal annotation — waterproofing zone (hidroizoliacija)
- Diagonal hatch fill — tile area on wall developments

### 3.3 Ceiling Plan Colors — CRITICAL

| Color | Meaning |
|---|---|
| **Red line / red rectangle** | **LED strip niche (LED juosta) — very consistent in LT practice** |
| Yellow circles | Recessed downlight (potinkinis šviestuvas) |
| Rectangle outline | Surface-mounted fixture / panel light |
| Dashed rectangle | GK suspended ceiling boundary (dropped) |
| Solid line + number | Ceiling level annotation (+2780, H=2.78) |
| Cross/X in rectangle | Ventilation grille |
| Blue rectangle | Smoke detector / sensor |

**LED niche rule:** Color drawing → red rectangular frame along ceiling perimeter = LED niche. B&W → thin double rectangle annotated "LED juosta", "LED nišelė", "el. nišelė". Depth 80–120 mm. Height 50–80 mm. Length = window width + 2×200 mm overhang each side.

### 3.4 Wall Development Colors

- Grey/blue hatch — tile zone (boundaries show tile height)
- White/plain fill — paint zone
- Brown/tan fill — wood paneling / lamelės
- Dotted fill — decorative plaster (dekoratyvinis tinkas)
- Dark grey cavity outline — niche (nišelė) recessed into wall

---

## 4. Dimension Reading Rules

### 4.1 Units — Absolute Rule

**All architectural dimensions in LT = millimeters** (LST EN ISO 128). "3600" on a plan = 3600 mm = 3.60 m. No exceptions for linear dimensions.

Exceptions:
- Areas: m² with comma decimal ("14,25 m²")
- Ceiling heights in section views: typically meters ("2.820")
- Level annotations: "+2800" (mm from FFL) or "+2.800" (meters)

### 4.2 Dimension Chain Placement

```
[outermost]   total building dimension
[middle]      structural axis spacings (axis tags A/B/C, 1/2/3)
[inner]       opening widths (window/door rough openings)
[interior]    room clear dimensions; area in (parentheses)
```

### 4.3 Opening Annotations

W×H in mm, positioned next to/above the opening:
- `1200×1500` = window 1200×1500 mm
- `900×2100` = door 900×2100 mm
- Old LT: `1.2/1.5` (meters, slash separator)

Rough opening ≈ frame + 50 mm each side. Use frame (bloko matmuo) for area calculations.

### 4.4 Ceiling Height Annotations

| Format | Meaning | Example |
|---|---|---|
| H=2.80 | Room clear height from FFL | Flat ceiling at 2800 mm |
| +2800 | Absolute level from FFL=±0 (mm) | Soffit at 2800 mm |
| +2.780 | Same in decimal meters | Soffit at 2780 mm |
| -0.020 | Depression below FFL | 20 mm shower tray recess |
| h=350 | Feature height (not room) | Niche or bulkhead |
| H-3400 | Ceiling level in ceiling plan | Absolute 3400 mm |

### 4.5 Wall Thickness

1. Number inside wall hatching: 200, 100, 375 (mm)
2. Leader: "GK 100" = GK partition 100 mm total
3. From dimension chain gap spanning the wall
4. Composite: "GK 2×12.5+75+2×12.5" = 125 mm total

---

## 5. Document Type Classifier

### 5.1 Sheet Title Block

Per LST 1325:1995 — bottom-right corner. Contains: project name, sheet title, sheet number prefix (AP=Architectural; INT/I=Interior; K=Structural; S/SAN=Plumbing; E/EL=Electrical; SK=Site plan; TP=Title), scale ("M 1:50"), date (DD.MM.YYYY).

### 5.2 Drawing Type Identification

| Drawing | LT title variants | Visual clues |
|---|---|---|
| Floor plan | "Aukšto planas", "Pertvarų planas", "Planimetrija" | Wall hatching + door arcs + window gaps + dimension chains + room number circles + eksplikacija |
| Section | "Pjūvis A-A", "Skerspjūvis", "Pjūvis 1-1" | Vertical cut: floor slab bands, insulation, ceiling height arrows |
| Elevation | "Fasadas", "Pietinis fasadas" | Flat exterior face; no interior content; no room circles |
| Ceiling plan | "Lubų planas", "Lubų išklotinė" | Room outlines from above; GK level boundaries (dashed); fixtures; LED rectangles; **NO furniture, NO door arcs** |
| Wall development | "Sienų išklotinės", "Sienų plėtiniai" | Rectangular panels A/B/C/D per room; tile/paint zones; height annotations |
| Floor finish plan | "Grindų planas" | Material fill patterns; floor levels; baseboard notes |
| Furniture plan | "Baldų planas" | Heavy filled shapes; full layout; NOT for wall area |
| Electrical | "Elektros instaliacija", "Rozečių schema" | Outlet/switch symbols; circuit lines; no wall hatching |
| Plumbing | "Santechnikos planas", "Vandentiekio schema" | Pipe runs; fixture symbols; drains |
| Window/door schedule | "Langų sąrašas", "Angų lentelė" | Table: Nr ∣ Plotis ∣ Aukštis ∣ Tipas ∣ Kiekis |
| Finish schedule | "Apdailos lentelė", "Medžiagų lentelė" | Code → material name table |

### 5.3 Disambiguation Rules

- **Ceiling plan vs floor plan:** Ceiling has NO door arcs and NO furniture
- **Furniture plan vs floor plan:** Furniture has heavy fills, may lack dimension chains
- **Wall development vs elevation:** Wall dev has labeled panels A/B/C/D + finish zones; elevation = exterior facade
- **Section vs elevation:** Section shows slab bands + insulation in cross-section; elevation = flat face

### 5.4 Typical Multi-sheet Project Sequence

```
TP-01  — Titulinis (cover)
AP-01  — Sklypo planas (often omitted for interior)
AP-02  — Aukšto planas + eksplikacija   ← PRIMARY SOURCE
AP-03  — Grindų planas
AP-04  — Lubų planas                     ← LED niches
AP-05  — Pjūviai                         ← ceiling heights
AP-06  — Langų ir durų sąrašas           ← opening sizes
AP-07/INT-01 — Sienų išklotinės         ← tile zones
AP-08  — Apdailos lentelė
E-01   — Elektros planas                 ← outlet counts
S-01   — Santechnikos planas             ← fixture counts
```

**Extraction priority:** AP-02 > AP-07/INT-01 > AP-04 > AP-06 > E-01 > S-01.

---

## 6. STR & LST Regulatory References

### 6.1 Primary STR Documents

| Document | Title | Relevance |
|---|---|---|
| STR 1.05.06:2010 | Statinio projektavimas | Drawing types, sheet numbering, scale |
| STR 1.01.09:2003 | Statinių klasifikavimas | Building classification |
| STR 2.02.09:2005 | Vienbučiai gyvenamieji pastatai | Room/height minimums (validation) |
| STR 1.05.07:2002 | Statinio projekto ekspertizė | Examination requirements |
| STR 2.01.07:2003 | Triukšmo apsauga | Akustinė izoliacija (Rw ≥ 50 dB multifam) |

URL: https://www.e-tar.lt | https://www.statybos-inspekcija.lrv.lt

### 6.2 LST EN ISO Standards

| Standard | Content |
|---|---|
| LST EN ISO 128-20:2002 | Line conventions: solid=visible, dashed=hidden, chain=center |
| LST EN ISO 128-23:2002 | Building-specific line conventions |
| LST EN ISO 7519:1995 | General arrangement: layout, view, dimension placement |
| LST EN ISO 4157-1:2000 | Room numbering systems |
| LST EN ISO 4157-2:2000 | Room name designation (eksplikacija basis) |
| LST 1325:1995 | Sheet sizes A0–A4, title block bottom-right |

URL: https://www.lst.lt

### 6.3 Minimum Ceiling Heights (STR 2.02.09 — for validation)

| Room type | Min clear height |
|---|---|
| Habitable rooms (gyvenamieji) | 2.50 m |
| Kitchen | 2.50 m |
| Bathroom/WC | 2.20 m |
| Corridor | 2.10 m |
| Mansard | 2.50 m for ≥50% floor area |

**Validation rule:** Height annotation below these = likely partial height (soffit, niche depth), not room clear.

### 6.4 Minimum Room Areas (STR 2.02.09 — for validation)

| Room | Min area |
|---|---|
| Single bedroom | 8 m² |
| Double bedroom | 10 m² |
| Living room | 14 m² |
| Kitchen | 8 m² |
| Bathroom | 3.8 m² |
| WC | 1.1 m² |

**Validation rule:** Areas below = likely sub-area or error; flag for review.

---

## 7. Practical Vision Extraction Rules

### 7.1 Room Detection

1. Scan for circle tags with numbers (6–10 mm circles).
2. Find eksplikacija — check 4 corners first; then separate AP/INT sheet.
3. Match circle → eksplikacija row → name, area, finish codes.
4. No eksplikacija: infer from fixtures (WC=tualetas, bath=vonia, sofa=svetainė, counter+sink=virtuvė).

### 7.2 Dimension Extraction

1. All bare numbers = mm.
2. Innermost chain = opening widths. Next = axis spacings.
3. Room interior dimensions ("4500×3200") = clear space.
4. Ceiling height: H= or + prefix; or section view on same sheet.

### 7.3 Opening Count and Sizing

1. Count door arcs = doors. Each arc = one leaf.
2. Count window parallel-line gaps in exterior walls.
3. Cross-reference langų/durų sąrašas for exact dimensions/types.
4. No windows found: apply CLAUDE.md fallback (standard count per room type).

### 7.4 Wall Area (no sienų išklotinės)

1. Use Perimetras column from eksplikacija if present.
2. Otherwise: perimeter ≈ 2×(L+W) from interior dimensions.
3. Gross = perimeter × ceiling height.
4. Deduct: windows (count × avg 1.80 m²), doors (count × avg 1.89 m²).
5. Do NOT deduct openings < 1.0 m² (NRM2 §29 — for paint).

### 7.5 Sheet Priority for Each Quantity

| Data | Best source |
|---|---|
| Room names + areas | Eksplikacija (AP-02 or separate) |
| Room dimensions | AP-02 aukšto planas |
| Ceiling height | AP-05 pjūvis or AP-04 annotations |
| Tile zones (exact) | INT-01 / AP-07 sienų išklotinės |
| LED niche dimensions | AP-04 lubų planas |
| Window/door sizes | AP-06 langų/durų sąrašas |
| Floor material per room | AP-03 grindų planas or G code |
| Sanitary fixtures | S-01 santechnikos planas |
| Outlets/switches | E-01 rozečių/elektros planas |

---

*Compiled 2026-04-26 for Sąmatų AI Vision prompt engineering. Basis: LST EN ISO 128/7519/4157, STR 1.05.06:2005/2.02.09:2005/2.01.07:2003, LST 1325:1995, practitioner knowledge of LT documentation conventions.*
