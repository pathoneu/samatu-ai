# ADR-001: Takeoff Workflow Architektūra

**Status:** Proposed
**Date:** 2026-04-26
**Deciders:** Ignas

---

## Context

Sąmatų AI dabar veikia Vision-first režime: Claude opus skaito PDF, grąžina patalpų
sąrašą, V8 Universal Engine apskaičiuoja kiekius pagal industries formules. Vartotojas
matosi sąmatos juodraštį per 30-60s, tikrina, koreguoja per RoomsGrid kortelės.

**Problemos:**
1. Vision tikslumas svyruoja 70–90% per projektus. Likusius 10–30% vartotojas turi
   pataisyti rankomis — bet dabar **NETURI tikrų įrankių** tai padaryti. PdfViewer
   markup'as yra dekoratyvus (nieko nepakeičia skaičiuose).
2. Kai Vision visiškai nepavyksta (rastriniai PDF, neaiški antraštinė plokštelė),
   vartotojas turi įvesti VISKĄ rankomis per RoomsGrid form'as — neefektyvu.
3. Vartotojas neturi būdo *patikrinti* AI rezultatų — nemato sąsajos tarp brėžinio
   ir kambarių sąrašo. „AI sako 28m² svetainės — kur jis ją matuoja?"
4. Žmonės nesupras, **už ką moka €49/mėn**, jei programa atrodo kaip dropdown'inis form
   įrankis. Togal AI parduoda **tikrą takeoff workflow** — vartotojas mato AI prediction'ą
   tiesiog ant brėžinio ir koreguoja jį per 5 paspaudimus.

**Forces:**
- Production timeline: 2 sav. iki closed beta
- Tikslumas yra pagrindinis vertės pasiūlymas (rangovo klaida = realūs pinigai)
- Vartotojo užduotis NĖRA "patvirtinti AI rezultatą" — tai "paruošti tikslią sąmatą greitai"
- LT rangovai turi mažai tolerancijos juodadėžiui — turi MATYTI matavimą

---

## Decision

Pereiti į **Hybrid Vision + Interactive Takeoff** workflow:

1. **Vision kaip pradinis sluoksnis** — automatiškai pažymi kambarius PDF brėžinyje
2. **Vartotojas mato AI prediction'ą TIESIOG ant brėžinio** — su highlight'intom zonom
3. **Korekcija per direct manipulation** — paspaudžiu zoną → koreguoju matmenis,
   pažymiu naują → matuoja automatiškai pagal mastelį
4. **Kambariai ir zonos yra TAS PATS objektas** — RoomCard ir polygon brėžinyje
   yra du to paties duomens vaizdavimai

---

## Options Considered

### Option A: Pasilikti Vision-first + form korekcija (dabartinis)

| Dimension | Assessment |
|-----------|------------|
| Complexity | Mažas (jau veikia) |
| Cost | 0 dienų |
| Scalability | Aukšta (form'inis input'as universal) |
| Team familiarity | Aukšta (jau dirbam) |
| User experience | **Žemas** — vartotojas neturi vizualios sąsajos su brėžiniu |
| Differentiation | **Žema** — atrodo kaip Sąmata.lt su AI priekyje |

**Pros:**
- Veikia jau dabar
- Greitas iteruoti

**Cons:**
- Niekam nepasirodys "verta €49/mėn"
- Nepalyginamas su Togal AI demonstracine verte
- Vartotojas negali patikrinti AI ("kur tu matuoji svetainę?")

---

### Option B: User-first takeoff (Bluebeam stilius, Vision atjungtas)

Vartotojas brūkšnioja zonas, programa skaičiuoja kiekius. Vision tik klasifikuoja
puslapius ir aptinka mastelį.

| Dimension | Assessment |
|-----------|------------|
| Complexity | Vidutinė (polygon + scale calibration) |
| Cost | 5–7 dienos |
| Scalability | Aukšta |
| Team familiarity | Vidutinė |
| User experience | **Vidutinė** — tikslus, bet lėtas (rankinis darbas) |
| Differentiation | Žema — Bluebeam jau egzistuoja, geresnis |

**Pros:**
- Tikslumas 100% (vartotojas mato ką matuoja)
- Paprasta architektūra — Vision iškeliamas

**Cons:**
- AI vertė prarasta — niekam neapibrėžia "AI" produkto
- Kainavimas € 49/mėn nepateisinamas — Bluebeam pigiau
- LT rinkoje **jau yra Dimetris** (semi-rankinis). Mes neaplaisim

---

### Option C: Hybrid — Vision auto + interactive review (REKOMENDACIJA)

Vision automatiškai pažymi VISUS kambarius PDF brėžinyje (highlight'inta polygon'ais).
Vartotojas mato AI predictions iš karto. Kiekvienas polygon'as turi confidence
indicator'ių. Vartotojas:

1. **Patvirtina viską** vienu paspaudimu (jei AI 100%)
2. **Koreguoja** problematic'us polygon'us per drag&drop
3. **Prideda** trūkstamas zonas brūkšniodamas (auto-matuoja per kalibruotą mastelį)
4. **Šalina** klaidingai aptiktas zonas

| Dimension | Assessment |
|-----------|------------|
| Complexity | **Aukšta** — reikia abiejų sluoksnių sinchronizacijos |
| Cost | **8–12 dienų** |
| Scalability | Aukšta |
| Team familiarity | Žema (nauja patirtis) |
| User experience | **Aukštas** — geriausias iš abiejų pasaulių |
| Differentiation | **Aukšta** — tikras Togal stilius LT rinkai |

**Pros:**
- Vartotojas matosi "AI darbas" iškart (justifies €49/mėn)
- Korekcija greita (5 sek vietoj 5 min RoomsGrid form'oje)
- Per-projektą time savings yra MATOMAS (vartotojas mato AI atliktą darbą)
- Konkurencingumas su Togal AI

**Cons:**
- Sudėtingiausia architektūra
- Reikia mastelio kalibracijos prieš matavimo įrankius
- Vector PDF parsing — sunkus rastriniams brėžiniams

---

## Trade-off Analysis

**Esminė problema su variantu A** (dabartiniu): vartotojas atidaro programą, mato
form'as. Mokėjimas €49/mėn už dropdown'us — sunkus pardavimas. Mes pateikiame **AI
kaip features**, bet vartotojas nemato AI **value moments**.

**Variantas B** atstumia AI vertę. Tampam "Bluebeam su LT pavadinimais". Konkurencija
prarasta.

**Variantas C** yra teisingas atsakymas, NET jei brangiausias. Priežastis:
- Pirmasis 30-sekundinis vartotojo įspūdis lemia konversiją
- Įspūdis "Ohh, AI VISIŠKAI matuoja kambarius — tik patvirtinu" yra perkamas
- Įspūdis "OK, AI grąžino skaičius lentelėj" — neapibrėžia produkto

**Reali rizika su variantu C:** "Aukšta complexity" reiškia 8–12 dienų. Per tą
laiką gali įvykti scope creep, gali būti UX dilemų. Bet tai vienintelis kelias į
**produktą už kurį žmonės moka**.

---

## Consequences

**Becomes easier:**
- Pardavimas (vizualus value prop)
- Akcentavimas tikslumo (vartotojas MATO ką AI matuoja)
- Konkurencingumas su Togal AI LT rinkai
- Vartotojo tipa: "tikslumo paranoja" — pagrindinis ramstis

**Becomes harder:**
- Frontend kompleksiškumas (dvi vaizdavimo formos vienam objektui)
- Mastelio kalibracija — production-blocking (be jos polygon matavimas neveikia)
- Vector PDF parsing — privalomas, bet ne visi PDF turi vector layer'į
- Koordinatės — Vision grąžina pikselius, mums reikia jų konvertuoti į m²

**What we'll need to revisit:**
- Per-puslapį navigacija (kambariai gali būti skirtinguose puslapiuose)
- Polygon edit precizija (corner snapping, undo/redo)
- Mobile/tablet UX (pagal tipologijos research'ą — rangovai dažnai mobile'e)

---

## Action Items

### Faza 1: Foundation (3 dienos)
1. **PDF.js + Konva tikslus mastelio kalibravimas**
   - 2 paspaudimų įrankis: vartotojas spaudžia tašką A → tašką B → modal "Kiek metrų?"
   - Per puslapį saugomas `pixels_per_meter` ratio
   - Sanity check: jei mastelis duoda absurdiškus plotus — perspėk
2. **Polygon matavimas**
   - Brūkšniojimo įrankis su grid snap (every 100mm)
   - Auto-skaičiuoja plotą Shoelace formule × kalibruotą mastelį
   - Real-time perimetras + plotas display'ina kursoriui einant
3. **Polygon ↔ Room data model**
   - Naujas state'as: `project.polygons[]` su `{id, page, points, room_nr, color}`
   - Kambarys (`v8_rooms[i]`) susiejamas su polygon per `room_nr`
   - Live recalc: polygon edit'as → room.plotas_m2 update → totals recalc

### Faza 2: AI Prediction Layer (3 dienos)
4. **Vision grąžina kambarius su koordinatėmis**
   - V7 prompt'as papildomas: per kiekvieną patalpą `bbox_pixels: {x, y, w, h, page}`
   - Jei Vision negali — palieka tuščią, vartotojas brūkšnioja rankomis
5. **AI polygons rendering**
   - Pradinis layer'is brėžinyje su Vision rezultatais
   - Skirtinga spalva per confidence (žalia/geltona/raudona)
   - Hover pažymėjimas → highlight'ina atitinkamą RoomCard
6. **Quick actions**
   - "Patvirtinti viską" mygtukas (jei AI 100%)
   - Per-polygon: ✓ Tinka / ✏️ Koreguoti / 🗑 Šalinti
   - Pridėti naują polygon'ą — instant'inis input

### Faza 3: Counts (2 dienos)
7. **Counter įrankis**
   - Vartotojas spaudžia ant rozečių/jungiklių/šviestuvų simbolių
   - Counter pagal kategoriją: "Rozetės: 12 vnt"
   - Eksportuojama elektros sąmatos eilute
8. **Vision counts predictions**
   - Vision grąžina aptiktus simbolius (tik jei matomi)
   - Vartotojas peržiūri ir koreguoja

### Faza 4: Value-prop UI (1 diena)
9. **Time savings indikatorius**
   - "AI sutaupė 4h 12min" — apačioje rodyklėje
   - Skaičiuojama: AI atliktas darbas (polygons + matavimai) × 5min/polygon manualus laikas
   - Per-projekto stat'a — matoma kasdien
10. **Confidence summary panel**
    - "AI tikslumas projekte: 87%" — su breakdown per kategoriją
    - Vartotojas mato KOKIA dalis AI darbo, kokia jo

**TOTAL: 9 dienos** (jei nieko nepertrauks)

---

## Pushback Notes

**Igno pasiūlymas "Reikia visko, kuo greičiau":** Tai pažodžiui neįmanoma. Realybės
tikrumas:

- **Jei greitai** (3 dienos) — tik Faza 1, naudotojas turės polygon įrankius bet
  Vision dar negrąžins koordinačių. Tai nepilnas Togal-style.
- **Jei viską** (9 dienos) — pilnas Togal-style, bet 2 sav. timeline į pavojų
- **Realistiškas kompromisas (5 dienos)** — Faza 1 + Faza 2 (be Counts ir Time
  savings UI). Tai pakankamai produkto demonstracijai.

Mano rekomendacija: **5 dienos = Faza 1 + Faza 2.** Counts (Faza 3) ir UI (Faza 4)
po beta'os.

---

## Atviri klausimai

1. **Mastelio kalibracija** — vartotojas turi tai atlikti vienu kartu per puslapį.
   Ar reikia per VISI puslapiai, ar tik pirmu, taikant globaliai? Skirtingi puslapiai
   gali turėti skirtingą mastelį (pvz pjūvis vs grindų planas).

2. **Polygon edit precizija** — "drag corner" su ar be "snap to PDF lines"?
   Pirmoji versija paprastesnė; antroji tikslesnė bet sudėtingesnė.

3. **Multi-page kambarys** — projektas su 2 aukštais turi kambarius skirtinguose
   puslapiuose. Ar leidžiame vienam kambariui turėti polygon'us per kelis puslapius?

4. **Undo/redo** — privaloma per beta? (Aš sakyčiau TAIP — neišvengiamas pataisymas.)

5. **Vector vs Raster PDF** — Vector galim parsint TIESIOG. Raster reikia OCR + Vision.
   Ar palaikom abu nuo pirmos versijos, ar tik vector?
