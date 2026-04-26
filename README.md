# Sąmatų AI

Lietuviška statybų sąmatų skaičiavimo platforma su AI brėžinių analize.
Įmesk PDF projektą → gauk 80% sąmatos juodraštį per 5 min.

## Kam skirta

- **Statybos rangovams** — taupo 5–10 valandų per projektą sąmatos rengimui
- **Subrangovams** — greitas pasiūlymo paruošimas užsakovui
- **Sąmatininkams** — automatinis kiekių traukimas iš PDF

## Pagrindinės savybės

**AI analizė:**
- Atpažįsta kambarius iš architektūrinio brėžinio
- Aptinka mastelį (M 1:50, 1:100 ir pan.)
- Klasifikuoja PDF puslapius (grindų, lubų, sienų išklotinės, fasadai)
- Skaičiuoja dažomą plotą, kampus, plytelių zonas, GKP, hidroizoliaciją

**Industries STANDART:**
- RICS NRM2 (UK) — kanoninis takeoff metodas
- DIN 18363 / VOB Part C (Vokietija) — apdailos darbų norma
- CSI MasterFormat 09 91 (US) — Sherwin-Williams kalkuliatoriaus pagrindas
- ANSI A108/A118 — plytelių darbų standartai

**Vartotojo control:**
- Brėžinio peržiūra ir markup TIESIOG appse (be split-screen)
- Per-kambarį inline edit + live recalc
- Setup Wizard — 5-min preferencijų konfigūracija
- AI CHAT projektui — natural language Q&A

## Architektūra

```
backend/                    # Python FastAPI
├── interior_v8/            # Universal Engine (industries STANDART)
│   ├── universal_engine.py # Per-kambarį skaičiavimai pagal NRM2/DIN/CSI
│   ├── scale_detector.py   # Auto-aptikti mastelį (3 metodai)
│   └── page_classifier.py  # PDF puslapių tipas (grindų/lubų/išklotinė)
├── interior_v7/            # AI Vision (Claude opus-4-7)
└── main.py                 # FastAPI endpoints

frontend/                   # React + Vite + Tailwind + shadcn/ui
├── src/components/project/
│   ├── PdfViewer.jsx       # PDF + Konva markup
│   ├── RoomsGrid.jsx       # Per-kambarį view
│   ├── RoomCard.jsx        # Inline edit
│   ├── ScaleInfoBanner.jsx # Mastelio statusas
│   ├── PageStructureCard.jsx # PDF struktūra
│   ├── SetupWizard.jsx     # Pirmojo paleidimo konfigūracija
│   ├── AiChat.jsx          # Natural language Q&A
│   └── ExportModal.jsx     # Excel + PDF export
└── src/pages/
    ├── Dashboard.jsx       # Projektų sąrašas
    ├── NewProject.jsx      # PDF upload
    └── InteriorProject.jsx # Vidaus apdailos sąmata
```

## Quick Start

### Backend

```bash
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...
uvicorn main:app --reload
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Atidaryti http://localhost:5173

## Pirmas projektas

1. Spauskite **Naujas projektas**
2. Pasirinkite tipą **Interjero projektas** (arba **Automatinis**)
3. Įmeskite PDF brėžinį
4. Spauskite **Pradėti analizę**
5. Po 30–60 sekundžių matysite:
   - Brėžinio mastelio aptikimą
   - Puslapių struktūrą (kiek grindų, lubų, išklotinių)
   - Kambarių sąrašą su skaičiavimais
   - 14+ darbų eilučių pagal industries standartus
6. Spauskite **Brėžinys** tab'ą — pamatysite PDF, galite pridėti pastabų
7. Korekcijos per **RoomsGrid** — live recalc
8. Eksportas Excel ar PDF — su Sąmatos formatavimu

## Accuracy realybė

**Production target:** 85% accuracy + 5–10 min user review = 95% final.

Pagal stress-test'ą ant 5 LT projektų:
- Dazymo plotas: ±15% (production-ready)
- Kampai: ±30% (vidutinis)
- Rotband / Q1 lyginimas: variabilus (priklauso nuo įmonės stiliaus —
  vartotojas Setup Wizard'e nustato %)
- GKP lubos, hidroizoliacija, skylių gręžimas: ±15%

Niekas pasaulyje nesiekia 100% automatic — Togal AI reklamuoja "98%" ir
realiai 85–90%. **Mūsų pozicija: AI-assisted, ne AI-only.**

## Konkurencija

- **Togal AI** (US) — pilnai automatinis, $299/mėn, anglų
- **Kreo** (UK) — AI takeoff, brangus
- **Dimetris** (LT) — pusiau-rankinis (vartotojas brūkšniuoja linijas)
- **Sąmata.lt / Sistela / ProSama** — TIK kainavimas, ne takeoff

LT rinkoje pilnai automatinio "PDF → sąmata" sprendimo specifiškai
vidaus apdailai NĖRA. Mūsų niche.

## Plano statusas

Žr. [PRODUCTION_PLAN.md](./PRODUCTION_PLAN.md) — 4 savaičių roadmap.

| Savaitė | Statusas |
|---------|----------|
| 1: Core accuracy | ✅ |
| 2: Vartotojo control (PDF viewer, markup, inline edit) | ✅ |
| 3: UX polish (page classifier, confidence indikatoriai) | ✅ |
| 4: AI CHAT, Per-įmonės profile, Export, Beta | 🟡 In progress |

## Licencija

Proprietary © Sąmatų AI 2026

## Kontaktai

- Email: solutions@pathon.eu
- Vaidmuo: PoC (proof of concept), uždaras beta launch
