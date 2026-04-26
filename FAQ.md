# Sąmatų AI — DUK (Dažni klausimai)

## Apie produktą

### Kas yra Sąmatų AI?

Lietuviška platforma, kuri iš PDF brėžinio automatiškai paruošia statybų
sąmatos juodraštį. Naudoja AI Vision (Claude opus-4-7) brėžinio analizei
ir industries STANDART formules (NRM2, DIN, CSI) skaičiavimams.

### Kuo skiriasi nuo Sąmata.lt / Sistela / ProSama?

Šios LT programos yra **kainavimo įrankiai** — reikia rankomis suvesti
kiekius. Mes esame **takeoff įrankis** — automatiškai traukiame kiekius
iš PDF brėžinio.

### Kiek tiksliai sutampa su rangovo skaičiavimu?

Realybės paveikslas (2026 metais):
- **Pagrindiniai kiekiai** (dažomas plotas, kampai, GKP lubos): **85–90%**
- **Specifinės pozicijos** (Rotband, šiukšlės, šviestuvai): priklauso nuo
  įmonės stiliaus — Setup Wizard'e nustatote %
- **Galutinis tikslumas po peržiūros (5–10 min)**: **95%+**

Niekas pasaulyje nesiekia 100% — Togal AI reklamuoja 98% ir realiai
85–90%. Mūsų pozicija: **AI-assisted, ne AI-only**.

### Kiek laiko sutaupysiu?

Tipinis namo projektas (130 m², 12 kambarių):
- Rankomis: 3–6 valandos
- Su Sąmatų AI: 15–25 minutės (3 min analizė + 15 min peržiūra)
- Sutaupymas: **5–10× greičiau**

## Naudojimas

### Kokios PDF kokybės reikia?

**Geriausiai veikia:**
- Vector PDF (architektūrinė programa eksportavo)
- Aiškiai matomi matmenys (kambarių plotai užrašyti)
- Pavadinimai antraštės plokštelėje (pvz „Pirmojo aukšto planas, M 1:50")

**Veikia silpniau:**
- Skenuoti rastriniai PDF (mažiau teksto → mastelio neaptinkame, naudojame default)
- Sudėtingi atviros erdvės (svetainė + virtuvė + valgomasis vienoj zonoje)
- Mansardiniai kambariai (kreivos lubos)

### Kuriuos LT projektų tipus palaiko?

Šiuo metu — **Vidaus apdaila** (interjero projektai).

Po beta'os planuojama:
- Fasadai (ETICS, ventiliuojamieji)
- Stogai
- Žemės darbai
- Betonavimas
- Mūro darbai

### Ar AI suvedinėja į Sistela?

Šiuo metu NE — Sistela kodų bazė planuojama post-launch (savaitė 5+).
Pirmoji versija eksportuoja Excel ir PDF su industries pavadinimais.

### Kaip taisyti AI klaidas?

**Per kambarį:**
1. Eik į **Kiekiai** tab'ą
2. RoomCard'e spauskite ✏️ Edit ikoną
3. Pakoreguokite plotą / perimetrą / paskirtį
4. Spauskite ✓ Išsaugoti — totals atsinaujins automatiškai

**Per brėžinį:**
1. Eik į **Brėžinys** tab'ą
2. Naudokite ▭ Stačiakampis — pažymėkite zoną
3. Pridėkite komentarą su 💬 ikona
4. Klaidingas AI pažymėjimas — su 🧹 Eraser

## Setup Wizard

### Kodėl reikia Setup Wizard'o?

Skirtingi rangovai skaičiuoja kitokiai. Pvz:
- Vienas Rotband (Q1 lyginimas) įjungia VISAIS projektais
- Kitas — tik mūro pertvaroms (~25%)
- Dar kitas — niekada (vartotojas pats glaisto)

Setup Wizard'as leidžia per 60 sekundžių nustatyti TAVO įmonės stilių.
Mes naudojame industries STANDART kaip baseline'ą.

### Ką galiu nustatyti?

- Vonios plytelių aukštis (1.5 / 2.0 / 2.4 m)
- Kuriose patalpose dažome (drabužinė, sandėliukas, garažas, tambūras)
- Glaisto Q lygis (Q1–Q4)
- Plytelių metodas (tikslus / praktinis su angų atimtimi ar be)
- Kampų skaičiavimas (vidaus + išorės)
- Atliekų % per medžiagą

### Ar profiliai persikelia tarp projektų?

Taip — Setup Wizard rezultatai išsaugomi į localStorage ir naudojami
visiems naujiems projektams. Galite keisti per **Nustatymai** mygtuką.

## AI CHAT

### Ką galiu klausti?

- "Kuris kambarys didžiausias?"
- "Kiek dušo zonų projekte?"
- "Koks bendras dažomas plotas?"
- "Ar yra patalpų virš 3m aukščio?"
- "Kiek šviestuvų reikia svetainei?"

AI atsako iš projekto duomenų — neišgalvoja skaičių.

## Privatumas ir saugumas

### Kur saugomi mano projektai?

Šiuo metu — **lokaliai** (browser localStorage + IndexedDB). Nieko
neperduodama į cloud.

PDF analizė vyksta per Anthropic API (Claude). PDF nelaikomas Anthropic
serveriuose po analizės.

### Ar mano sąmatos matomos kitam vartotojui?

Ne. Visi duomenys lieka tavo browser'yje. Kelių vartotojų bendradarbiavimas
planuojamas post-launch.

## Technologija

### Kokia AI technologija naudojama?

- **Claude opus-4-7** (Anthropic) — Vision PDF analizei
- **Industries STANDART formulės** — skaičiavimams (NRM2, DIN, CSI, ANSI)
- **PDF.js + Konva** — frontend brėžinio peržiūrai ir markup

### Ar veikia offline?

Ne. AI analizei reikia interneto (Anthropic API).
PDF peržiūra ir korekcijos veikia offline po analizės.

### Kiek kainuoja vienas projekto AI call'as?

Šiuo metu PoC fazėje — Anthropic API kaina ~$0.50–1.00 už projektą.
Multi-model optimizacija planuojama post-launch (sumažinti iki ~$0.10).

## Kainavimas (preliminaru)

PoC fazėje produktas yra **uždaras beta** — nemokamas pasirinktiems
testiniams vartotojams.

Po launch'o (planuojama):
- **Free** (0 €/mėn): 3 projektai per mėnesį
- **Standart** (49 €/mėn): 30 projektų, eksportas, AI CHAT
- **Pro** (99 €/mėn): unlimited, per-įmonės profilis, prioritetinis support

(Togal AI palyginimui: $299/mėn = ~275 €/mėn)

## Bug'ai ir feedback

### Kaip pranešti apie klaidą?

Email: solutions@pathon.eu

### Kaip pasiūlyti naują funkciją?

Email arba Telegram beta grupėje (pakvietimas po beta launch'o).

## Roadmap

### Po beta (3–6 mėn)

- AI Pattern Search (objektų paieška PDF)
- Multi-model AI optimizacija (Gemini Flash bulk darbui)
- Per-įmonės kalibravimas iš senų sąmatų
- Sistela kodų bazė
- F2 / F3 LT formų eksportas

### Ilgalaikis (12–24 mėn)

- EU plėtra (Lenkija, Latvija, Estija, Vokietija)
- Fasadai, stogai, žemės darbai modulai
- Mobile app

Žr. [PRODUCTION_PLAN.md](./PRODUCTION_PLAN.md) detaliam planui.
