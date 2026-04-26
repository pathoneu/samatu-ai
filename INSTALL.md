# Sąmatų AI — Instaliacijos vadovas

Step-by-step instaliacija lokaliai (Mac / Linux).

## Reikalavimai

- **Python 3.10+** (rekomenduojama 3.11)
- **Node.js 18+** ir **npm**
- **poppler-utils** (PDF konvertavimui į PNG; reikalinga Vision'ui)
- **Anthropic API raktas** (https://console.anthropic.com)

## Mac install (Homebrew)

```bash
brew install python@3.11 node poppler
```

## Linux install (Ubuntu/Debian)

```bash
sudo apt update
sudo apt install python3.11 python3-pip nodejs npm poppler-utils
```

## Backend setup

```bash
cd ~/samatu-ai/backend

# Sukurk virtualinį env'ą
python3 -m venv venv
source venv/bin/activate

# Įdiek priklausomybes
pip install --upgrade pip
pip install -r requirements.txt

# Nustatyk Anthropic API raktą
export ANTHROPIC_API_KEY="sk-ant-..."
echo 'export ANTHROPIC_API_KEY="sk-ant-..."' >> ~/.zshrc  # arba ~/.bashrc

# Paleisk backend
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Backend turi pasiekti `http://localhost:8000/health` → `{"status":"ok"}`.

## Frontend setup

```bash
cd ~/samatu-ai/frontend

# Įdiek priklausomybes
npm install

# Paleisk dev server'į
npm run dev
```

Atidaryk http://localhost:5173

## Pirmas paleidimas

1. Atsidarius http://localhost:5173 — pirmajame paleidimui automatiškai
   atsidarys **Setup Wizard**
2. Praeik per 6 žingsnius (~60 sekundžių)
3. Spauskite **Naujas projektas**
4. Įmeskite PDF brėžinį
5. Spauskite **Pradėti analizę** — laukite ~30–60 s

## Galimi trikdžiai

### "ANTHROPIC_API_KEY" not set

```bash
echo $ANTHROPIC_API_KEY
# Jei tuščia — nustatyk:
export ANTHROPIC_API_KEY="sk-ant-..."
```

### "ModuleNotFoundError: No module named 'pdfplumber'"

```bash
cd backend
source venv/bin/activate
pip install pdfplumber pdf2image shapely anthropic fastapi uvicorn
```

### "poppler-utils not found"

```bash
# Mac
brew install poppler

# Ubuntu
sudo apt install poppler-utils

# Patikrinti
pdftoppm -v
```

### Frontend "Cannot find module 'react-pdf'"

```bash
cd frontend
npm install
# Iš naujo paleisk dev server
npm run dev
```

### "Workspace folder yra tuščias"

Vite proxy reikalauja, kad backend veiktų ant localhost:8000.
Patikrinkite `vite.config.js` ar `BACKEND` reikšmė teisinga.

### Vision call'as lūžta dėl PDF dydžio

PDF didesni nei 50MB gali būti per dideli vienam call'ui.
Mūsų V8 dabar dirba su < 30MB PDF'ais. Optimizacija planuojama.

## Production deploy (planuojama)

Šiuo metu — **lokalus dev setup** kiekvienam vartotojui.

Po launch'o planuojama:
- Docker container'iai
- Cloud hosting (AWS / Hetzner)
- Kelių vartotojų SaaS

## Updates

```bash
cd ~/samatu-ai
git pull origin main

cd backend
source venv/bin/activate
pip install -r requirements.txt --upgrade

cd ../frontend
npm install
npm run dev
```

## Telegram beta grupė

Po beta'os startuoja LT rangovų grupė feedback'ui ir support'ui.
Pakvietimas — kontaktuojant solutions@pathon.eu.
