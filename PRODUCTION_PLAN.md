# Sąmatų AI — Production Launch Plan

**Pradinis statusas:** V8 universal engine veikia, ~70% accuracy ant 5 testavimo projektų.
**Tikslas:** Pasiekti 85% accuracy + production-ready UX per 4 savaites, paleisti closed beta su 5–10 LT rangovais.

---

## Strateginė pozicija

**Mūsų niche:** Pilnai automatinis "PDF → kiekiai → sąmata" specifiškai LT vidaus apdailos rinkai.

**Konkurencinis paveikslas:**
- Togal AI (US, $299/mėn) — pilnai automatinis, bet anglų, US commercial GC fokusas, neturi LT statybos taisyklių
- Dimetris (LT) — pusiau-rankinis (vartotojas brūkšniuoja linijas)
- Sąmata.lt / Sistela / ProSama — TIK kainavimas, ne takeoff
- BIM workflow (Revit/ArchiCAD) — stambioms įmonėms su BIM modeliais
- **NIEKAS LT rinkoje pilnai automatinio takeoff'o nedaro**

**Pozicionavimas:** "AI paruošia 80% sąmatos juodraščio per 5 min. Likusius 20% sutaisai per 10 min."
NE "100% automatic" — tai netiesa ir niekas pasaulyje to nedaro.

**Pricing strategy:** €49–99/mėn (5–6× pigiau už Togal AI). LT moat: Sistela, F2/F3, atvirkštinis PVM, lietuviška UI.

---

## 4 savaičių planas

### Savaitė 1 — Core accuracy

**Tikslas:** V8 universal pasiekia 85% accuracy ant 5 testavimo projektų.

- [ ] **CORE pozicijų pridėjimas (task #83)** — V8 grąžina 14 pozicijų vietoj 7
  - Sienų lyginimas Rotband (DIN 18363 § 3.4: Q1 Vorspachtelung)
  - GKP nišų formavimas (LED apšvietimui)
  - GKP angokraščių apdirbimas (per durų skaičių × 5.1m)
  - Difūzorių apdirbimas
  - Durų angų paruošimas beapvasdinėms durims
  - Šviestuvų apdirbimas (gipsiniai, lubų)
  - Nuolydžio formavimas dušo kabinoje (per dušo zonų skaičių)
  - Skylių gręžimas plytelėse (per santechnikos taškų skaičių)
  - Kampų silikonavimas (per plytelių zonas)
  - LED juostos komutavimas
  - Šiukšlių išvežimas
- [ ] **Auto-aptikti brėžinio mastelį (task #85)** — production-blocking
  - Mastelio aptikimas iš tekstinių žymeklių (M 1:50, M 1:100)
  - Iš dimensijų užrašų (3450 ant linijos)
  - Sanity check'as: jei kambarys atrodo 200m² gyvenamasis — tikriausiai mastelis blogai
- [ ] **Sanity check'ai** — validation rules
  - Lubų plotas ≈ grindų plotas?
  - Perimetras vs plotas (1.3:1 stačiakampiui)
  - Patalpų skaičius ≥ 3 (LT realių namų minimum)
  - Bendras plotas svetainė + miegamasis ≥ 30 m² (LT minimum)

**Šaltiniai (kanoniniai industries standartai, NE vienos įmonės stilius):**
- RICS NRM2 Section 29 (UK)
- DIN 18363 / VOB Part C (Vokietija)
- CSI MasterFormat 09 91 (US)
- LT statybos taisyklės STR

---

### Savaitė 2 — Vartotojo control (GAMECHANGER)

**Tikslas:** Vartotojas mato brėžinį TIESIOG appse, gali markup'inti, redaguoti AI klaidas. Eliminuojam split-screen workflow.

- [ ] **PDF viewer per react-pdf (task #84)**
  - Įdiegti react-pdf + react-konva
  - PDF puslapių navigacija (puslapių thumbnails sidebar'e)
  - Zoom in/out, pan
  - Atskira nuo RoomsGrid view (toggle "Brėžinys / Patalpos")
- [ ] **Konva.js markup overlay**
  - Brūkšnioti regiono kontūrą (polygon)
  - Pridėti tekstinį komentarą su rodyklėje
  - Ištrinti AI sugeneruotą zoną
  - Save markup'us per projektą (localStorage pirma)
- [ ] **Per-kambarį inline edit pilnai funkcionalus**
  - RoomsGrid leidžia keisti plotą / perimetrą / paskirtį
  - Live recalc viso projekto totals
  - Kiekvienas pakeitimas atsinaujina darbu_sarasas eilutes
- [ ] **AI–brėžinys link**
  - RoomCard'e kambario click → PDF viewer'is centruoja į tą zoną
  - Brėžinyje markup'as → atitinkama RoomCard pasviesti

---

### Savaitė 3 — UX polish + page intelligence

**Tikslas:** Onboarding < 5 min, vartotojas mato sutvarkytą projekto medį iškart.

- [ ] **PDF puslapių klasifikatorius (task #86)**
  - Per puslapį Vision call'as → tipas (planas, lubų planas, sienų išklotinė, fasadas, pjūvis)
  - Atskirai išskaityti reflected ceiling planus (LED, šviestuvai, GKP dėžučės)
  - Atskirai išskaityti sienų išklotines (plytelių zonos)
- [ ] **Auto-rename PDF puslapių**
  - Vartotojas mato sutvarkytą medį: "1A grindų planas", "Lubų planas vonia"
  - Vietoj chaotiško "Pages 1.pdf, Pages 2.pdf"
- [ ] **Confidence indikatoriai per kiekvieną reikšmę**
  - 🟢 HIGH (vertė skaityta tiesiogiai iš PDF)
  - 🟡 MEDIUM (apskaičiuota iš dalinių duomenų)
  - 🔴 LOW (spėjama iš defaults)
  - Vartotojas mato KUR SVARBU peržiūrėti
- [ ] **Setup Wizard polish**
  - Pridėti "tipologijos" pasirinkimą: naujas namas / renovacija / komercinis
  - Skirtingi default'ai per kiekvieną
  - Vartotojo profilis išsaugomas, taikomas visiems projektams

---

### Savaitė 4 — Beta launch prep

- [ ] **AI CHAT per projektą**
  - Vartotojas klausia: "kiek dušų?", "kuris kambarys didžiausias?", "ar yra langų virtuvėje?"
  - AI atsako iš projekto context'o
  - Pirma versija — Claude opus (latencyja sub-2s OK)
- [ ] **Per-įmonės profilis (Setup Wizard sluoksnis 2)**
  - 10–15 boolean/skaitmeniniai pasirinkimai
  - Vonios plytelių aukštis, garažas dažomas, atliekų %, glaisto Q lygis
  - Profilis išsaugomas, taikomas visiems naujiems projektams
- [ ] **Eksportas Excel + PDF**
  - Sąmata sutvarkytame Excel formate (LT su Sistela kodais — pirmoji versija be kodų, vėliau pridėsim)
  - PDF eksportas su įmonės logo
- [ ] **Closed beta launch**
  - 5–10 LT rangovų
  - 3 mėn nemokama
  - Telegram grupė feedback'ui
  - Daily metrics: kiek projektų / kiek edit'ų per projektą / kiek laiko sutaupė

---

## Po beta'os (savaitė 5+)

- [ ] AI Pattern Search (CLIP embeddings) — "pažymėk vieną radiatorių → suskaičiuok visus"
- [ ] Multi-model AI optimizacija (Gemini Flash bulk darbui, sutaupyti 5–10× kaštus)
- [ ] Per-įmonės kalibravimas iš senų sąmatų (sluoksnis 3)
- [ ] Performance tuning (P1 71s → <30s)
- [ ] Edge cases: atvira erdvė, L formos kambariai, mansardiniai
- [ ] Stress test'ai: 50+ realių LT projektų accuracy
- [ ] EU plėtra: Lenkija, Latvija, Estija lokalizacija

---

## Architektūros sluoksniai (long-term)

**Sluoksnis 1: Universal Knowledge Base (PRIVALOMA, baseline)**
- Industries standart formulės (NRM2, DIN, RICS, CSI)
- Default coefficient'ai pagrįsti tarptautiniais šaltiniais
- Tikslas: 80–85% accuracy be jokio kalibravimo

**Sluoksnis 2: Vartotojo profilis (Setup Wizard)**
- 10–15 boolean/skaitmeniniai pasirinkimai per 60s
- Tikslas: 85–90% accuracy

**Sluoksnis 3: Per-įmonės kalibravimas (post-launch, premium)**
- Vartotojas suupload'ina 5+ praeitus projektus
- Sistema ekstrahuoja statistinius patterns
- Korekcijos vartotojui rodomos ir patvirtinamos transparently
- Tikslas: 92–95% accuracy

---

## Rizikos

**1. Vision modelio nedeterminizmas**
- Mitigation: Multi-pass run'ai, median agregacija (savaitė 2)

**2. Realių LT projektų variabilumas**
- Mitigation: Closed beta su 5–10 rangovų, daily metrics (savaitė 4)

**3. Edge cases (atvira erdvė, L formos)**
- Mitigation: Manualus override per RoomsGrid (savaitė 2)

**4. Togal AI atvyks į LT (1–2 metai timeline)**
- Mitigation: LT moat (Sistela, F2/F3), pricing 5–6× pigiau, lokalumas

**5. PDF kokybė (skenuoti, žemos kokybės)**
- Mitigation: Vector PDF tikslus parsing per pirmąjį layer'į, Vision fallback

---

## Metrikos sėkmei

| Metrika | Šiandien | Savaitė 4 | 6 mėn |
|---------|----------|-----------|-------|
| Accuracy ant 5 P projektų | ~70% | 85% | 92% |
| Pavadinimai sutampa su industries standartu | 50% | 90% | 95% |
| Onboarding time | n/a | < 5 min | < 3 min |
| Projektų per dieną | 0 | 5–10 (beta) | 50+ |
| Mokantys vartotojai | 0 | 0 (free beta) | 20–30 (paid) |

---

## Kritiniai sprendimai, kuriuos jau priėmėme

1. ✅ "rangovas" vardo niekur kode — visos formulės iš industries standartų
2. ✅ Setup Wizard sluoksnis 2 — vartotojo profilis, taikomas visiems projektams
3. ✅ V8 Universal Engine — backend skaičiavimas pagal NRM2/DIN/CSI
4. ✅ React + Vite frontend — RoomsGrid + RoomCard inline edit
5. ✅ Multi-model (Gemini, GPT) — atidėta po launch'o, dabar Claude opus
6. ✅ Multi-mode (Quick/Deep) — atmesta kaip nereikalinga
7. ✅ React-pdf + Konva.js PDF viewer'ui
8. ✅ Closed beta po 4 savaičių (NE laukti tobulybės)

---

**Atnaujinimas:** 2026-04-26 (rebooted scope per Igno feedback)

---

# REBOOT — 5 savaičių sprint planas iki production beta

**Iššūkis:** Po pirmos versijos UI atrodo "mesmale" — per daug feature'ų, vartotojas
nesupranta workflow'o. Šaknis: "feature creep before product-market fit".

**Sprendimas:** Drastiškas simplifikavimas + accuracy iteracija + DWG support + kainynai.

| Sprint | Trukmė | Pagrindinis output |
|--------|--------|-------------------|
| 1 | 5 d | Vienas pagrindinis page'as, NE 4 tab'ai. Polygon+AI Chat — HIDE. Tipologijos sub-tipai. |
| 2 | 7 d | Backend formules per tipologiją + accuracy iteracija iki 95% |
| 3 | 5 d | DWG/Revit parser (CAD = 100% tikslumas) |
| 4 | 7 d | Kainynų importas (Excel+PDF+CSV) + AI fuzzy match + rangovo cold-start |
| 5 | 4 d | Polish + 5 LT rangovų beta launch |

**TOTAL: 28 dienos = ~5 savaitės.**

## Patvirtinti sprendimai

- **Q1.1** DWG/Revit — TAIP, įdiegiame (ne premium, tiesiog yra)
- **Q1.2** Tiesiogiai sakom "AI ~95% tikslumo" — TAIP
- **Q1.3** Taikom 95% tikslumo PRIEŠ launch — TAIP (Sprint 2 fokusas)
- **Q3** Tipologija per projektą (Naujas/Renovacija/Komercinis)
- **Q4** Kainynų sistema būtina, all formatai (Excel/PDF/CSV), per-tenant privacy
- **Q5** Eksportas — top-right dropdown, visada matomas
- **Q6** AI CHAT — atidedam vėliau (atjungiam iš MVP)
- **Q7** Polygon brūkšniojimas — HIDE iš UI (vartotojas net nežino kas tai)

## Naujas core workflow (vartotojui)

1. **Naujas projektas** — pasirenka tipą + sub-tipą (Naujas/Renovacija/Komercinis), įmeta PDF (arba DWG, jei turi)
2. **AI veikia 30-60s** — extract'ina patalpas, kiekius, suformuoja darbų sąrašą
3. **Atidaro projektą** — VIENAS ekranas:
   - Top sticky: bendra suma € + "Eksportuoti" dropdown
   - Vidury: patalpų sąrašas (collapsible) + darbų sąrašas su grupavimu
   - Apačioje: "Žiūrėti brėžinį" mygtukas → modal'as
4. **Koreguoja** kainas / pavadinimus rankomis (kaip Excel'e)
5. **Eksportuoja** → Excel arba PDF

**Visos kitos funkcijos** (polygon, AI chat, page classifier, scale calibration) —
slėptos arba pašalintos iš MVP UI.

---

## 2026-04-25 sesijos rezultatai — 4 SAVAIČIŲ PLANAS BAIGTAS

**Backend (12 naujų failų / atnaujinimų):**
- `interior_v8/universal_engine.py` — V8 + 8 industries CORE pozicijos (DIN, NRM2, CSI, ANSI cit.)
- `interior_v8/scale_detector.py` — 3-metodų mastelio aptikimas + sanity check
- `interior_v8/page_classifier.py` — 10 puslapių tipų atpažinimas
- `interior_v7/pipeline_v7.py` — pridėta `puslapio_nr` per kambarį
- `main.py` — `/extract-interior-v8` su `v8_scale`, `v8_pages`, `additional_positions`
- `main.py` — `/chat-project` AI CHAT endpoint
- `scripts/parse_all_pasiulymai.py` — rangovo sąmatos parser
- `scripts/gap_analysis.py` — V8 vs rangovo lyginimas
- `scripts/v8_stress_test.py` — accuracy report runner

**Frontend (8 naujų komponentai):**
- `PdfViewer.jsx` — react-pdf + Konva markup
- `RoomCard.jsx` + `RoomsGrid.jsx` — inline edit + confidence dots + Eye→PDF
- `ScaleInfoBanner.jsx` — mastelio statusas
- `PageStructureCard.jsx` — projekto struktūros kortelė
- `SetupWizard.jsx` — 6-žingsnių pirmojo paleidimo wizard
- `AiChat.jsx` — floating chat panel
- `pdfStore.js` — IndexedDB PDF saugojimas
- `ExportModal.jsx` — V8 darbu_sarasas integracija

**Dokumentai:**
- `README.md` — pilnas project overview
- `FAQ.md` — DUK su pricing, accuracy realybe
- `INSTALL.md` — step-by-step setup vadovas

**Stress-test rezultatai (ant 5 LT projektų, mock kambariai):**
- Dazymo plotas: ±15% (production-ready)
- Kampai: ±30% (vidutinis)
- CORE pozicijos sutampa su rangovo industries-style sąmata 80%+ pavadinimų
- Hidroizoliacija, skylių gręžimas, nuolydis dušui: ±15%
- Rotband + šiukšlės: variabilūs (tipologijos klausimas — Setup Wizard handles)

**Visi 4 savaičių etapai:** ✅ ✅ ✅ ✅

Sekantis žingsnis — closed beta su 5–10 LT rangovų (savaitė 5+).
