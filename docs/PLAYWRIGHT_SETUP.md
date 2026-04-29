# Playwright MCP setup — kad Claude galėtų matyti ir valdyti Chrome

## Kodėl?

Šiandien aš (Claude Code) galiu rašyti kodą, paleisti bash komandas, skaityti failus.
Bet **negaliu pamatyti, kas vyksta tavo Chrome** — tu tarp mūsų esi „akys".
Kai sakau „pažiūrėk dashboard'ą", ranka turi ekranuoti ir paste'inti screenshot'ą man.

**Playwright MCP** prideda man browser tools:
- `browser_navigate` — atidaro URL
- `browser_snapshot` — gauna structured DOM state (kaip „accessibility tree")
- `browser_take_screenshot` — PNG kuris man matomas
- `browser_click` / `browser_type` / `browser_select_option` — sąveikauja
- `browser_evaluate` — paleidžia JS console'ėje (debug)
- `browser_console_messages` — gauna error log'us

Po įdiegimo — **galėsiu testuoti pats** mūsų app'ą be tavo dalyvavimo:
- Pildysiu formas, klikinsiu mygtukus
- Pamatysiu real-time render, ne tik headless screenshot
- Debug'insiu JS klaidas console'ėje
- Rerunninsiu user flow'us po kiekvieno fix'o

## Instaliacija (macOS, Claude Code CLI)

### Žingsnis 1: Įdiek Playwright MCP server

Atidaryk Terminal ir paleisk:

```bash
# Globalus npm install
npm install -g @playwright/mcp

# Pirmą kartą — atsisiunčia browser binarius (~200MB, vienas kartas)
npx playwright install chromium
```

Jei `npm` nėra — install Node.js iš https://nodejs.org/ (LTS) arba `brew install node`.

### Žingsnis 2: Užregistruok MCP server'į pas Claude Code

Du būdai:

**Būdas A — `claude mcp` komanda (paprastesnis):**

```bash
claude mcp add playwright npx @playwright/mcp@latest
```

Patikrina:

```bash
claude mcp list
```

Turėtų matytis `playwright` su `running` arba `installed` status'u.

**Būdas B — manual config (kai pirmas neveikia):**

Atidaryk `~/.claude.json` (jei nėra — sukurk):

```bash
nano ~/.claude.json
```

Pridėk arba sumerge'ink:

```json
{
  "mcpServers": {
    "playwright": {
      "type": "stdio",
      "command": "npx",
      "args": ["@playwright/mcp@latest"]
    }
  }
}
```

Save (Ctrl+O, Enter, Ctrl+X jei nano).

### Žingsnis 3: Restart Claude Code

Šitos sesijos restart'as PRIVALOMAS — MCP servers loaded only at startup.

```bash
# Užbaik šitą sesiją:
exit

# Tada nauja sesija:
claude
```

Arba jei naudoji Claude Code GUI — quit + relaunch.

### Žingsnis 4: Verifikacija

Po restart'o, pirmai sesijai parašyk man:

> „Playwright MCP įdiegei? Patikrink"

Aš paleidsiu:
```
mcp__playwright__browser_navigate(url="http://localhost:5173/")
mcp__playwright__browser_take_screenshot(filename="verify.png")
```

Jei matysi screenshot'ą atvertame Chromium lange ir aš grąžinsiu sėkmę — viskas veikia.

## Veikimo režimai

### Default — Playwright launches own browser
Playwright paleidžia **savo Chromium** (ne tavo Chrome). Plus'ai:
- Nelisp'ina su tavo profile'u, slapukais, history
- Galiu paleisti incognito-style
- Stabili — neuždarysi tu netyčia

Minus: nematys tavo logged-in session'ų. Bet mums OK — `SAMATU_AUTH_DISABLED=1` flag'as backend'e leidžia naudoti be auth.

### Alt — Connect to your Chrome (advanced)
Jei nori, kad matyčiau tavo realų Chrome (su projektais localStorage'e):

1. Užbaik visus Chrome procesus
2. Paleisk Chrome su remote debugging:
   ```bash
   /Applications/Google\ Chrome.app/Contents/MacOS/Google\ Chrome \
     --remote-debugging-port=9222 \
     --user-data-dir=/tmp/chrome-debug
   ```
3. Pasakyk man — bandysiu prisijungti per CDP

(Šitas daro ne sažin lėtai, dažniausiai default'as geresnis.)

## Common gotchas

- **„MCP server not found"** po install'o — restart'ink Claude Code ar terminal'ą iki galo
- **`npx` lėtas pirmąjį kartą** — atsisiunčia paketą; tai vienas kartas
- **Browser binary missing** — paleisk `npx playwright install chromium` rankomis
- **Permission denied** — gali reikėti `sudo npm install -g`, arba susitvark npm prefix

## Ką pat darysiu po install'o

Pirmajai sesijai užduok:
> „Pažiūrėk dashboard'ą, projektų sąrašą ir Brėžinys tab'ą — papasakok kas trūksta vs prototipas"

Aš paleisiu vidinį review:
1. `browser_navigate` → localhost:5173/
2. `browser_take_screenshot` → palyginsiu su `/Users/ignasgaldikas/Downloads/samatuai v2 (1)/screenshots/proto-dashboard.png`
3. `browser_navigate` → /project/04bc3f42-...
4. `browser_take_screenshot` → palyginsiu su prototipo Project view
5. Detali ataskaita kas matosi vs prototipas — pikselių lygiu, ne tik aprašant

Tai uždarys feedback loop'ą — nereikės tau perduoti screenshot'ų rankomis.

## Saugumas

Playwright MCP automation'as turi teises rašyti į ekrano bufferį, klikinti, pildyti formas.
**Niekada neduosiu jam:**
- Tavo bank login'o (banko domenas blokuojamas pas mane)
- Slaptažodžių nei kitų sensitive įvedimui
- Veiksmų ant external svetainių be tavo aiškaus prašymo

Visus veiksmus matysi sesijos transcript'e.

---

Po install'o pranešk — aš pats verifikuosiu ir pradėsiu naudoti.
