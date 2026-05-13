# Council sprendimas — CV strategy pivot (2026-05-11)

**Šis failas:** session handoff'as su council verdict'u + konkretūs next steps. Kitos sesijos pradžioje perskaityk šitą failą — viskas, ką reikia žinoti, čia.

**Susiję dokumentai:**
- `2026-05-11-session-handoff-cv-tools.md` — prior session cold-start
- `2026-05-11-cv-tools-real-world-limits.md` — kas patvirtinta testuojant ant realaus PDF
- `2026-05-03-bakeoff.md` — 6 pipeline'ų bake-off rezultatai

---

## TL;DR

Council (5 advisor'iai + 5 peer review'eriai) **vienbalsiai** rekomendavo **Option F: no-CV MVP**.

Vartotojas (Ignas) sutiko su sprendimu 2026-05-11. **Jokio kodo nepakeista** šitoj sesijoj — tai sprendimo sesija.

---

## Sprendimas: Option F

**Užmiršti CV simbolių skaičiavimą iš MVP scope'o.** Niekas iš B/C/D/E variantų.

Konkrečiai:
- Jokio click-to-count, jokio drag-rect, jokio Vision-bulk + click-to-delete
- Joks "Aptikti rozetes/jungiklius/šviestuvus" mygtukas (V1 V2 — abu)
- CV V2 backend infra + training-data writer **lieka disk'e**, neištrinam
- UI atjungta — palieka tokia, kokia buvo po 2026-05-11 revert'o

## Kodėl Option F

Kontekstas:
- Pre-revenue, solo dev, 1-2 mėn iki MVP launch'o
- LT konkurentas (manual Bluebeam) neturi AI — esamas interior pipeline jau lenkia
- 49% CV accuracy ant takeoff'o = bug generator (vartotojas randa vieną klaidą → nebepasitiki)
- pdf.js drag interaction'as architektūriškai nesuderintas su tool'ais
- Tikrasis moat'as = LT-specific math (angokraščiai, Q2-Q4 glaistymas, RICS NRM2, F2/F3), ne CV

Cituojant council:
> "Tu jau turi veikiantį produktą. Sustok bandyti pridėti broken CV. Pardavinėk tai, kas veikia, charge'ink pinigus, ir leisk mokantiems vartotojams pasakyti, ar simbolių skaičiavimas verta 2 mėnesių."

## Konkretūs next steps

### 1. Pataisyti 2026-05-07 production bugus (priority #1)

Iš `memory/project_first_real_test_feedback.md`:
- **Lubų >3m neatpažįsta automatiškai** ant projekto 1. Vision pipeline numato standartinį 2.65-2.75m default, nepaima realių aukštesnių lubų iš pjūvių/sekcijų. Galimos fix kryptys:
  - Pridėti pjūvių (pjūvis) puslapio klasifikavimą
  - Iš sekcijos puslapio ekstraktinti lubų aukštį per kambarį
  - Arba aiškiau show'inti vartotojui "lubos numatytos 2.7m — keisk per Prielaidos jei kitaip"
- **Project-load cards rodo stale duomenis** — kai vartotojas grįžta atgal į projektą, kortelės rodo seną info. Frontend caching/state issue. Galimos kryptys:
  - Force-refresh on project mount
  - Invalidate localStorage cache when project updates
  - Investigate `ProjectListView` / `projects.js` data flow

### 2. Customer discovery (priority #2)

**Ne kodo task** — Ignas, tu pats turi padaryti:
- Pakalbėti su 3-5 LT statybininkais
- Parodyti esamą `main` versiją (interior pipeline + KŽ + eksportas)
- Klausti: *"Ką tu pirktum DABAR, šitam state'e? Už kiek? Per projektą ar per mėnesį?"*
- Klausti: *"Ar tau būtų reikalingas simbolių (rozečių, jungiklių) automatinis skaičiavimas? Ar pakaktų KŽ eilutės su tavo įvestu skaičiumi?"*

**Negudrauti** — neparduot, tik klausyt. Customer'ių atsakymai diktuoja next step.

### 3. Testuoti "inline-number hypothesis" (priority #3)

Peer review pakėlė hipotezę, kurios council praleido: galbūt vartotojui visai nereikia annotation'o brėžinyje. Užtenka:
- KŽ eilutė "Rozetės — vnt." su AI pasiūlytu skaičiumi (jei Vision rado), arba tuščiu input'u
- Vartotojas pataiso jei reikia
- Joks canvas, jokia drag interaction, jokia pdf.js problema

Jei vartotojai sutinka su tokiu pattern'u — visas CV architektūrinis blokeris dingsta.

**Kaip testuoti:** parodyt 2-3 contractor'iams mockup'ą (galima net Figma'oj arba paveiksliuke) — "AI pasiūlė 26 rozetes, ar tau OK toks UX?"

## Ko NEDARYTI

- ❌ Nepradėt re-wirinti CV V2 atgal į PlanViewer'ą
- ❌ Netunuok cv2.matchTemplate threshold'ų / scales (recall ceiling fix'as)
- ❌ Netaisyk V1 Rozetės/Jungikliai/Šviestuvai mygtukų (broken model layer, ne UX)
- ❌ Neištrink CV V2 backend'o ar frontend komponentų — laukia ant disk'o
- ❌ Nepradėk WebGL viewer'io spike'o
- ❌ Nelicencijuok komercinio SDK
- ❌ Nepradėk YOLO V2 training pipeline'o
- ❌ Nesiplėsk į Sistela / APVA / F2-F3 scope'ą šitam MVP'e (council Expansionist tai pasiūlė, bet peer review pavadino "scope creep trap")

## Branch state

- **`week1-canonical-execution`** — 13 commit'ų ahead of main, NOT merged. CV V2 UI atjungta paskutiniam revert'e. Tinka palikti tokiam state'ui.
- **`main`** — neliesta. Live app rodo `Užpildyti polygoną` (V1) kaip vienintelį tool experimental Ženklai (β) panel'yje.

Sprendimas dėl branch'o lieka kitai sesijai. Du variantai:
- **(a)** Merge'inti `week1-canonical-execution` į main kaip research/infra (backend CV API + tests + UAT script + docs) — backend infra = free option value
- **(b)** Cherry-pick'inti tik docs/tests į main, abandon'inti branch'ą

Mano (Claude) inclination'as buvo (a), bet tai ne urgent decision.

## Ką laikom ant disk'o (laukia future revisit)

CV V2 infra yra **option value, ne tech debt**. Jei kažkada paying customer'is pasakys "man reikia symbol counting" — turim ką grąžinti:

- `backend/api/cv_tools.py` — 4 routes
- `backend/extractor/cv_match.py` — template matcher (multi-scale, multi-rotation, NMS)
- `backend/extractor/cv_wand.py` — flood-fill polygon suggester
- `backend/extractor/cv_render_cache.py` — pypdfium2 page rasterizer
- `backend/extractor/training_data.py` — accept/reject corpus writer
- 30 testų (visi pereina)
- Frontend komponentai (disk'e, NOT mounted): CountTool, MagicWandTool, CountReviewPanel, DrawingOverlay, cvToolsApi, spatialIndex, useCanvasOverlay

Šitie failai NEKAINUOJA nieko, kol nemount'inti. Šaldykim kaip option'ą.

## Council confidence calibration rule (mokomės iš klaidos)

Prior council (R3, 2026-05-10) patvirtino CV plan'ą. Real-PDF testavimas paneigė architektūrinę prielaidą. Pamoka:

> **Joks architektūrinis sprendimas be real-PDF testo pirmiau.**
>
> Council yra LLM'ai reasonin'antys iš docs. Šis council irgi. Empirinė falsifikacija > trys LLM'ai susitariantys.
>
> Rule: jei first task plan'e yra "build infrastructure" — plan'as klaidingas. Jei first task yra "open existing thing and add one button" — plan'as teisingas.

## Verdict summary

| Klausimas | Council atsakymas |
|-----------|-------------------|
| Kuris kelias? | **F (no-CV MVP)**. Unanimous 5/5. |
| Naujų variantų? | Inline-number KŽ row (per peer review). |
| Prior council patikimumas? | Adjust the rule (test on PDF first), not just confidence. |
| Ką daryti šią savaitę? | (1) Fix prod bugs (2) Customer discovery (3) Test inline-number hypothesis |
| Kada grįžti prie CV? | Kai paying customer pasakys "man reikia symbol counting" specifically. |

---

**Vartotojas sutiko su Option F 2026-05-11. Kita sesija pradeda nuo bug fix'ų + customer discovery. Šis failas yra autoritetinis šaltinis.**
