# Pathon v3 — peržiūros gidas įkūrėjui (2026-10-19)

> Kam: jums, Ignai. Paskutinį kartą programą žiūrėjote 2026-10-17 (v2 gidas: `docs/superpowers/plans/2026-10-16-togal-v2-program.md`, skyrius „Founder review on localhost"). Nuo tada sujungti visi v3 programos darbai (sąrašas — sujungimų žurnale). Šis gidas — ėjimas per programą ta tvarka, kuria pats sutiksite naujus dalykus, su skaičiais, kuriuos turėtumėte pamatyti.
>
> Šaltiniai: kiekvienas žingsnis ir skaičius paimtas iš sujungimų žurnalo (`docs/superpowers/plans/2026-10-18-pathon-v3-program.md`, „Merge log") ir iš automatinio ėjimo (e2e) patikrintų skaičių. Kur skaičiaus neradome — parašyta „(patikrinti)". Kas padaryta ir kas ne — eilutė po eilutės: `docs/superpowers/plans/2026-10-18-pathon-v3-coverage.md` (stulpelis „Būsena 2026-10-19").
>
> Niekas neišsiųsta ir neįdiegta. Viskas yra tik šiame kompiuteryje, šakoje `togal-v2`.

---

## 1. Kaip paleisti

**Pagrindinėje kopijoje** (`/Users/ignasgaldikas/samatu-ai`) turi būti šaka `togal-v2` (`git status` → „On branch togal-v2"). Kodo viršūnė — `422c6b36` arba vėlesnė.

Du terminalai:

```bash
cd backend && SAMATU_AUTH_DISABLED=1 ../venv/bin/uvicorn main:app --port 8000
cd frontend && npm run dev
```

- Serveris 8000 paleidžiamas **be** `--reload`: jei kodas pasikeitė, sustabdykite (Ctrl+C) ir paleiskite iš naujo.
- `SAMATU_AUTH_DISABLED=1` — be prisijungimo. Paskyros ir el. pašto žingsniams (2.11 skyrius) šito kintamojo nereikia — žr. ten.
- Naršyklėje: **http://localhost:5173**.

**Kurį projektą atidaryti**
1. Pirmiausia **http://localhost:5173/project/demo-objektas_h** — brėžinys su tekstu, 11 patalpų, 8 lapai. Visi skaičiai žemiau — šiam projektui, jei neparašyta kitaip.
2. Antras — **http://localhost:5173/project/demo-objektas_g** (7 lapai vienam planui; ten patikrinkite, ar tas pats veikia kitame brėžinyje).

**Pradinė būsena.** Automatinis ėjimas (`cd frontend && npm run test:e2e`) projektą keičia, bet kiekvieną kartą pats grąžina duomenų bazę tokią, kokia buvo prieš jį (DEVELOPING.md, „E2E smoke"). Jūsų paties pakeitimai ėjimo metu išlieka — atgal grįžti galite per **Versijos** (viršutinė juosta).

**Vieną kartą kiekviename senesniame projekte** pasirodys pasiūlymas perskaityti brėžinį iš naujo — €0, vienas spustelėjimas; skaitymas dabar teisingai atsuka pasuktus lapus (W3-B). Apmokestinti kiekiai nuo to nepasikeičia.

---

## 2. Ėjimas per programą

### 2.1 Viena darbo vieta: Brėžinys · Patikra · Sąmata · Siųsti (W1-A)

1. Atidarykite demo-objektas_h. Viršuje keturi žingsniai: **Brėžinys · Patikra · Sąmata · Siųsti**.
2. Paspauskite kiekvieną paeiliui. **Brėžinys niekur nedingsta** — tai tas pats brėžinys, jis tik susitraukia arba užleidžia vietą. Naršyklės „Atgal" grąžina į ankstesnį žingsnį.
3. Brėžinys dabar užima apie pusę ekrano (buvo 32 %, dabar 51,6 % lango 1440×900).
4. Dešinysis skydelis — 340 px; tempkite jo kraštą (300–480 px), plotis įsimenamas.
5. Kairėje — 56 px lapų juosta su mažais paveiksliukais; paspaudus — lapo pavadinimas, „Lapai" atidaro visą sąrašą.
6. **Sąmata** → „Išskleisti": eilutės užima visą plotį, brėžinys lieka siaura juosta.

### 2.2 Įrankių kortelės, juosta apačioje, užuominos prie žymeklio (W1-B)

1. Kairėje ant brėžinio — įrankių kortelės: **Naršyti · Matuoti · Skaityti brėžinį · Sluoksniai · Daugiau**. Prie 1280 px jos telpa su užrašais (kortelių juosta 497 px iš 534 px).
2. Užveskite pelę ant įrankio — pavadinimas, klavišas ir vienas sakinys.
3. Įjunkite **Atstumas (2)**: prie žymeklio atsiranda sakinys, ką daryti. Apačioje — juosta tik su to įrankio veiksmais ir **Baigti / Atšaukti**.
4. Atstumas įrašomas **antru spustelėjimu**. Shift + spustelėjimas tęsia grandinę.
5. Braižant dešinysis pelės mygtukas → „Baigti / Atšaukti" prie žymeklio.
6. **Esc tvarka**: padėkite 3 taškus ploto įrankiu, spauskite Esc — taškai nyksta po vieną (3 → 2 → 1 → 0), tada išjungiamas įrankis, tada nuimamas pažymėtas kambarys.
7. **Tarpas (laikyti)** — stumdote brėžinį iš bet kurio įrankio; pradėtas braižymas lieka. **H** — rankutės įrankis.
8. Jei spustelėjimas nieko nepadarė — prie žymeklio trumpam parašoma, kodėl.

### 2.3 Kambarys vienu spustelėjimu, įrankis R, Atšaukti, mastelio ženkliukas (W1-D, W1-F)

1. **Pažymėti kambarį**: spustelėkite kambario viduje brėžinyje — jis pažymimas; Shift + spustelėjimas prideda antrą; tuščias popierius — nuima.
2. Po pažymėtu kambariu — juosta su veiksmais (ikona ir žodis): **Taisyti kontūrą · Sujungti · Atimti · Neskaičiuoti · Rodyti įrodymus**. Klavišai: **E** taisyti, **M** sujungti, **X** atimti, **Shift+F** arba **.** — parodyti visą kambarį.
3. **R + vienas spustelėjimas** kambaryje 06: pasiūlomas kontūras (punktyras) ir viena eilutė, ką jis pakeis. **Enter** įrašo. Toste 10 s — **Atšaukti** (grąžina, kas buvo).
4. **R kambaryje 04** — programa sako, kad jo nuo kaimynų neskiria siena, ir nieko neįrašo.
5. **Sujungti 04 → 05**: 04 = 26,31 + 35,50 = 61,81 m²; antraštėje **„Patalpos 11 143,27 m²"**, „Patalpų suvestinė" 143,27 m², jokio klaidingo „0,80×" ar „1,72×" įspėjimo (W1-F). Kampai 475,66 → 489,76.
6. Tada **Atšaukti** — 04 vėl 26,31 m², 05 vėl atskiras kambarys.
7. **Atimti** kolonėlę kambaryje 06 → **Atšaukti** — skylės nebėra.
8. **Mastelio ženkliukas** apačioje kairėje: **„1:115 · spėjamas"**. Vienas spustelėjimas — patvirtinta. Kortelėje: šiam lapui / visiems lapams / **Kalibruoti** / **Patikrinti**.
9. Jei projektą atkūrėte kitoje naršyklėje — perkrovus rodoma serverio kopija ir užrašas **„Atnaujinta iš serverio"** (W1-F).

Spustelėjimų skaičiai (W1-D): pažymėti kambarį 0 → 1; kambarys spustelėjimu 4 → 3 (kitam — 2); sujungti 5 → 4 + Atšaukti; patvirtinti mastelį 4 → 1.

### 2.4 Kontūrų ir matavimų taisymas (W5-A)

1. **Dukart spustelėkite kambarį 06** — atsidaro kontūro taisymas (tas pats kaip E). Patempkite kampą, Enter, Atšaukti. Dukart spustelėtas matavimas — taisomi jo taškai.
2. **Spustelėkite kampą** — atsiranda mažas langelis: **Ištrinti · Iškirpti angą · Pridėti kampą**.
3. **Patempkite kraštinę** — juda abu jos kampai, abu prilimpa prie sienos. Keli kampai: Ctrl/Shift + spustelėjimas arba rėmelis → **Delete** (ne mažiau kaip 3 taškai). Rodyklės pastumia 1 px (su Shift — 10).
4. **Atimti (X), vienas spustelėjimas** kambario viduje ant uždaros figūros — ji pasiūloma kaip skylė (punktyras), Enter įrašo, Atšaukti. *Pastaba:* demonstraciniuose brėžiniuose kolonų nėra, todėl pasiūlomi ir baldai (žr. „Jūsų sprendimai").
5. **Rėmelis**: iš kairės į dešinę — tik visos figūros, iš dešinės į kairę — ir paliestos. **„Pažymėti panašias"** — kambariai su ta pačia paskirtimi ar danga.
6. **Laikykite Ctrl (⌘)** — žymeklis peršoka prie artimiausio taško (kampo, vidurio, susikirtimo); apačioje parašyta, prie ko.
7. **Kiekis**: tipas pasirenkamas prie žymeklio (↑ ↓ Enter, „Naujas tipas"); kiekvienas tipas turi savo formą ir spalvą, raudonos nėra. Dvigubas spustelėjimas uždeda vieną ženklą.
8. **Dešiniu mygtuku ant ženklo → „Rasti panašius"** — pavyzdys jau apibrėžtas, rasti ženklai prisijungia prie to tipo (ir jo sąmatos eilutės).
9. **Sienų sluoksnis įjungtas → spustelėkite angą** — plotis ir rūšis (langas / durys / praėjimas), Atšaukti.
10. **Plotas / Perimetras**: mygtukas „Forma" perjungia Laisvai → Stačiakampis (2 spustelėjimai) → Lankas. Braižant įveskite skaičių + Enter — kita atkarpa bus tokio ilgio. Ctrl+C / Ctrl+V / Ctrl+D kopijuoja su Atšaukti. Uždėjus pirmą tašką prie žymeklio parašyta „Shift — tik tiesiai arba 45°".
11. **Sienų sluoksnis → spustelėkite sienos kraštą** — jos ilgis tampa atstumo matavimu „Siena".

Spustelėjimų skaičiai (W5-A): pataisyti kampą 2 + n; atimti kolonėlę 3; n ženklų — n + 1; rasti panašius 3 + k.

### 2.5 Brėžinio apvadas: lapo antraštė, sritys, „Rodinys", mastelio stulpelis, patvirtinimo langelis, mastelio kortelė, lapo praleidimas (W5-B)

1. Viršuje — lapo numeris, pavadinimas ir **„← 1 iš 8 →"**. Rodyklės ir PageDown / PageUp: 1 → 2 → 3 → 2.
2. **3 lapas**: užveskite pelę ant legendos — ji apvedama ir pavadinama („Legenda · SUTARTINIAI ŽYMĖJIMAI"). **„Rodyti sritis"** — nubrėžiamos visos lapo sritys (3 lape — 7).
3. **„Rodinys"**: brėžinio skaidrumas, „Išvalyti foną", „Nespalvotai" (jūsų žymės lieka spalvotos), užrašai įjungti / išjungti (tas pats jungiklis „PDF su žymėjimais" eksporte), kryželis per visą ekraną. Esc uždaro kortelę, kambarys lieka pažymėtas.
4. **Mastelio stulpelis** apačioje dešinėje (50 px): + % −, visas lapas / plotis, priartinti rėmeliu (61 % → 348 %), mažas žemėlapis, visas ekranas. Vidurinis pelės mygtukas stumdo brėžinį.
5. **Patvirtinimo langelis** (300 px su vienu sakiniu, kas nutiks) — tik veiksmams, kurių neįmanoma atšaukti (pvz., projekto trynimas, versijos grąžinimas). Matavimo trynimas nebeklausia — toste „Atšaukti".
6. **„Nustatyti mastelį"** šalia „Perskaityti lapą", kai lapas be mastelio — atidaro mastelio kortelę, skaitymo neblokuoja.
7. **Kambario parodymas priartina**: pasirinkus kambarį 06 iš sąrašo, jis parodomas visas (163 % → 458 %), ne tik jo lapas.
8. **Mastelio kortelė**: įrašykite „1:50" (tinka ir „50", „M 1:50", „1/50") → tai tampa jūsų masteliu; Atšaukti grąžina 1:115. Yra 12 standartinių mastelių su lapo dydžiu ir „Šiam lapui mastelio nereikia".
9. **Lapų juostoje „Neskaityti šio lapo"** — lapas pažymimas „neskaitomas", skaitymas jo praleidžia, Atšaukti.
10. **Matavimai** (dešinysis skydelis): „+ Grupė" (pvz., „Virtuvė"), įtempkite matavimą į grupę; filtrai Rasta automatiškai / Jūsų, Šis lapas, Atstumai / Perimetrai / Plotai / Kiekiai / Pastabos.

### 2.6 Legendos įrankis G ir peržiūra prieš sukuriant (W2-A, W2-B, W5-D)

1. Eikite į **3 lapą**, spauskite **G**. Legenda pasiūloma punktyru: „Tai legenda? **Taip** / Nubrėžti kitaip" (Enter = Taip).
2. Skydelis rodo legendos eilutes: ženklo iškarpa, tekstas, kiek rasta kiekviename lape, sakinys, kaip suskaičiuota, iki 3 pavyzdžių. Prie eilutės: **Tinka / Nereikia / Kitas pavadinimas**; ✕ ant kiekvieno ženklo brėžinyje. Medžiagų pavyzdžiai (plotai, linijos) nesiskaičiuoja vienetais — programa paaiškina ir siūlo „Matuoti plotą / ilgį".
3. **Kol nepaspaudėte „Sukurti kiekius (N)", nieko nesukurta.**
4. Ką turėtumėte pamatyti: **3 lape perskaitytos 15 legendos eilučių → 8 kiekių tipai, 38 ženklai, 8 sąmatos eilutės ir 1 tuščia** („Viengubas jungiklis": legendoje yra, brėžinyje ženklų nerasta — sąmatoje tuščia eilutė su paaiškinimu „suskaičiuokite „Kiekis" įrankiu"). Įsiminta: 14 įrašų.
5. **Atšaukti** (10 s) — ženklai ir eilutės dingsta (0).
6. Kitame to paties architekto projekte: „Rasta ankstesnio projekto legenda — pritaikyti?".
7. Ženklų kiekis eilutėje seka ženklus: pridėjus ar išėmus ženklą, kiekis pasikeičia pats; eilutėje parašyta „suskaičiuota pagal legendą: eilutė „…", N ženklai lape 1…".

### 2.7 Matavimai į sąmatos eilutes, grupės, pastabos (W4-A, W5-C)

1. **Matavimai** → prie matavimo **„Į eilutę…"** → pasirinkite eilutę: **„Grindjuosčių sumontavimas 92,84 + 4,20 = 97,04 m"** (3 spustelėjimai). Pakeiskite į **Atimti**, tada **Atšaukti**, tada **Nuimti** — grįžta programos skaičius.
2. **Įtempkite matavimą** ant eilutės „Kiekiai" skirtuke: **„Grindjuosčių dažymas 92,84 + 4,20 = 97,04 m"** (vienas tempimas). Kiekis ant m² eilutės nepriimamas.
3. **Kiekiai**: dukart spustelėkite skaičių → įrašykite → Tab pereina į kitą eilutę, Esc atšaukia, Enter įrašo, toste Atšaukti.
4. Eilutė su matavimais rodo žymą „iš matavimų" ir jų sąrašą; aiškinime — „matavimas 4,20 m (lapas 1)". Jūsų ranka įrašytas kiekis visada viršesnis.
5. „Kiekiai" apačioje — sumos atskirai pagal vienetą ir darbų šeimą (nebe viena suma per skirtingus darbus).
6. **„+ Pastaba brėžinyje"** — pastaba P1, P2… ant brėžinio; Keisti / Ištrinti su Atšaukti; matyti „Matavimuose", CSV ir „PDF su žymėjimais".
7. **„Kas pasikeitė"**: po „Perskaityti iš naujo" — „Kas pasikeitė · N eilučių · …"; **Peržiūrėti** atidaro eilutes ir kambarius; **Atšaukti** grąžina projektą į būseną prieš skaitymą, o perskaitytas variantas lieka kaip „Prieš grąžinant".

### 2.8 Patikra: klausimai, Enter / Esc, kambarių pavadinimai, kambarių sąrašas, priminimai, pranešimai, lentelių klausimai (W5-C, W5-E, W6-A, W2-B, W5-D)

1. **Patikra** atsidaro klausimų sąrašu. **Enter** — priima siūlomą atsakymą ir rodo kitą klausimą; **Esc** — grįžta į sąrašą. Rašant laukelyje Enter lieka laukelio.
2. Jei prieš klausimus stovi du ar daugiau pranešimų, jie suskleisti į vieną eilutę **„Pranešimai (N): …"** (W6-A) — pirmas klausimas matosi be slinkimo prie 1280×720.
3. **Kambario pavadinimas iš žodžių kontūre**: kambarys 02 (be lentelės eilutės) — „Ar tai katilinė?" (žodis brėžinyje „BOILERIS") → **Taip** → „Katilinė" → **Atšaukti** → vėl „Patalpa 02".
4. **Kambarių sąrašas** viršuje „N iš 11 ▾": kiekvienas kambarys su būsena žodžiais. Ant pažymėto fakto įrašykite skaitmenį — atsidaro jo laukelis (pvz., aukštis „3,05").
5. **„Ar nepamiršote?"** (Patikroje ir Sąmatoje) — priminimai, ne eilutės: GK tikslus / praktinis su abiem lapų skaičiais, deformacinės siūlės (siena > 8 m), priešgaisrinės konstrukcijos ir sandarinimas, dažų atsarga grubioms sienoms, dažnai pamirštamų darbų sąrašas. Atskirai — jei du kambarių kontūrai persidengia, pranešimas pavadina abu kambarius.
6. **Vertinimas** 👍 / 👎 + viena eilutė — Patikroje, kartą projektui. 👎 ant rasto ženklo reiškia „neieškoti tokių" kitą kartą.
7. **Lentelių klausimai** (durų ir langų žiniaraščiai, lentelės suma): atsakymas įrašomas su Atšaukti, „Rodyti brėžinyje" parodo lentelę. *Tikruose duomenyse dar nematyti* — demo-objektas_h neturi durų žiniaraščio, todėl šių klausimų čia gali nebūti (patikrinti). Durų žymių skaičiavimas plane (D-1, D-2) išbandytas tik objektas_d.
8. **„Bendri dalykai"** (po kambarių) → **„Projekto plotas"**: lentelės suma 143,27 · kontūrų suma 138,65 · pastato plotas plane — kiekvienas su sakiniu, iš kur. Ten pat **„Brėžinio lentelės"** → **„Eksportuoti lentelę"** (į Excel).
9. Grindų faktas rodo grindų legendą su iškarpa, pvz., „Legenda: parketas arba laminatas — ruda" (kuriame kambaryje — patikrinti).

### 2.9 Sąmata: ⋯ meniu, kainų žodžiai, pakuotės, angos pagal dydį, eksportas (W5-C, W5-E, W5-D, W7-A)

1. **Eilutės trynimas** — dabar per **⋯** meniu: ⋯ → Ištrinti → Atšaukti (117 eilučių → 116 → 117).
2. Vietoj spalvotų taškelių prie kainos — žodžiai: **„iš kainyno"** / **„panaši kainyno eilutė"**.
3. **Pakuotės** šalia „Medžiagos": pvz., „17 maišų po 25 kg", „7 kibirai po 10 l" — kilogramai ir litrai nesikeičia. Pakuotės dydis keičiamas **Nustatymai → „Pakuotės"**.
4. **„Angos pagal dydį"** — dešiniajame skydelyje, skirtuke **Kiekiai** (išskleidžiama): durys ir langai pagal rūšį ir dydį; durys tarp dviejų kambarių skaičiuojamos vieną kartą.
5. Duomenų / TV lizdai: jei legendoje yra tokia eilutė, pasiūloma „Pridėti tuščią eilutę" su Atšaukti.
6. **Eksportuoti**: Excel su „Grupuoti pagal" (dabar ir pagal aukštą / butą), „PDF su žymėjimais". Vidinėje kopijoje — papildomas lapas **„Pakeitimų žurnalas"**. PVM — žr. 2.11.

### 2.10 Projektai, Pagalba, „Ką programa perskaito", „Kol skaitoma" (W5-C, W7-A)

1. **Projektai** (http://localhost:5173/dashboard): projektai eilutėmis — pavadinimas, būsena, paskutinis pakeitimas, sumos, kitas žingsnis.
2. **Pagalba** (meniu; http://localhost:5173/pagalba): kaip patikrinti skaičių, pataisyti kontūrą, ką reiškia linijų stiliai, **„Kas naujo"**. Įvadinės užuominos (žingsniai 1–3) pasitraukia, kai atsidaro langas, ir grįžta į tą patį žingsnį.
3. **„Ką programa perskaito"** — kortelė prieš pirmą skaitymą naujame projekte: ką skaito, ko neskaito, kas lėčiau. „Supratau" ją uždaro; po pirmo skaitymo ji neberodoma. Pamatysite tik „Naujas projektas" kelyje (patikrinti).
4. **„Kol skaitoma"** — skydelis per mokamą skaitymą (25–28 min): koks etapas dabar, ką po to tikrinti Patikroje, kiek laiko liko, kad langą galima uždaryti. **Mokamo skaitymo nepaleidome** — šito skydelio realiai niekas nematė.
5. Nemokamo lapo skaitymo eiga dabar — juostoje apačioje; nutrūkus ryšiui — „Ryšys nutrūko · **Bandyti dar kartą**" (tęsia tą patį skaitymą).
6. Pokalbio istorija išlieka perkrovus puslapį; „Teisinga" eilutėje pasiekiama ir įprastame išdėstyme.

### 2.11 Paskyra, el. paštas, PVM, eksportai (W7-A)

1. **PVM**: http://localhost:5173/settings → įmonės PVM tarifas 21 / 9 / 0 % → eksportuokite Excel ir PDF — tarifas dabar naudojamas abiejuose (anksčiau visada 21 %).
2. **El. paštas** (patvirtinimas, slaptažodžio keitimas): tam reikia prisijungimo, todėl paleiskite serverį **be** `SAMATU_AUTH_DISABLED=1`. Laiškų siuntėjas dabar spausdina nuorodą į serverio terminalą (SMTP nenustatytas). Puslapiai: `/el-pasto-patvirtinimas`, `/slaptazodzio-keitimas`. Nuorodos vienkartinės: slaptažodžio — 1 val., patvirtinimo — 48 val., ne daugiau 3 per valandą. Prisijungimas be patvirtinto pašto blokuojamas tik su `SAMATU_REQUIRE_EMAIL_VERIFIED=1`.
3. Google prisijungimas reikalauja patvirtinto pašto; slaptažodžio paskyra su nepatvirtintu paštu nesujungiama su Google.
4. **Riba**: lape daugiau nei 1500 matavimų — įspėjimas.
5. Mokėjimai lieka išjungti (`BILLING_ENABLED`). Kreditas ir sąskaita dabar išrašomi tik tada, kai mokėjimas tikrai įvykęs.

### 2.12 Ką naujo perskaito nemokamas skaitymas „Perskaityti iš naujo" (W3-A, W5-D)

1. **„Perskaityti iš naujo" → „Perskaityti visus lapus (8)"** — €0, kaip anksčiau; eigoje atsirado etapas **„lentelės"** (durų, langų, apdailos, plytelių, kambarių lentelės su vieta brėžinyje). Demo-objektas_h: kambarių lentelė 11 iš 11 + suma.
2. Grindų legenda išsaugoma ir rodoma prie grindų fakto (2.8, 9 punktas).
3. Sienų tipai (GK pertvarų tipai iš legendos) — projekto faktas su iškarpa; objektas_h 8 lape šriftas neperskaitomas, todėl ten tuščia.
4. Lapas, kurio vienintelė sritis — legenda, gauna tipą „Legenda".
5. Lapai, pažymėti „Neskaityti šio lapo", praleidžiami.
6. Keli PDF ar nuotraukos (PNG / JPEG / TIFF) į vieną projektą — per „Naujas projektas"; lapai pavadinami pagal failą. DWG nepriimamas (tik tyrimas: `docs/superpowers/research/2026-10-19-dwg-intake-spike.md`). Šio kelio naršyklėje nevaikščiojome (patikrinti).

---

## 3. Ko dar nėra arba ko nepatikrinome

**Nepadaryta**
- Naujų durų ir langų žiniaraščio klausimų Patikroje tikruose duomenyse dar nematyti — nė vienas išsaugotas projektas jų dar neužduoda (W2-B).
- Rozečių lape 3 legendos eilutės randa 0 ženklų: plane ženklai perpus mažesni už legendos, pasukti 90° ir sudėti vienas ant kito — reikia kitokio paieškos būdo; ne €0 darbas (W5-D; Wave 7 kandidatas).
- Išsaugotų paieškų pakartotinis naudojimas, paieška pagal brūkšniuotę ir paieškos rezultatų pavertimas kiekiu nepadaryti (W5-D paliko W5-A, W5-A nepaėmė) — žr. aprėpties failo „Be namų".
- Mokamo legendos ir lentelių skaitymo iš paveikslėlio dialogo naršyklėje nėra; serverio kelias yra, bet išjungtas (W5-D).
- „Kas pasikeitė" po programos pasiūlymo nedaromas sąmoningai — tas pasiūlymas jau turi savo „Atšaukti" (W5-C).
- Lanko Atšaukti grąžina po vieną tašką; „Iškirpti angą" ant kambario prideda angą, bet kontūro nepakeičia (W5-A).
- Kambario įrankis R ima vieną tašką per spustelėjimą (be Kreo „plėsti / mažinti" taškų); naujo kambario sukūrimo („Nauja patalpa?") nėra (W1-D).
- Kai skaitymas paleidžiamas lape, pažymėtame „neskaitomas", programa to dar nepasako (W5-B; Wave 7 kandidatas).
- Puslapio geometrijos užklausų riba (30 per minutę) bendra visoms naršyklės kortelėms (W5-A; Wave 7 kandidatas).
- Saugumas, likę atviri (`docs/SECURITY.md` §13): programos puslapiams nėra CSP; nėra prisijungimo bandymų ribos paskyrai ir dviejų žingsnių prisijungimo administratoriui; nėra užklausos dydžio ribos prieš skaitymą.
- Dvi suvestinės, kurios dar sumuoja ir prijungtą (sujungtą) kambarį: `lt_rules.py:428` — pataisyta (5d2d8732, skaičiuojama per perskaičiavimą); `consistency_checker.py:77` paliktas — jis veikia tik mokamo skaitymo metu.
- T2 (laikas nuo PDF iki patikrintos sąmatos) nematuotas — reikia mokamo naujo projekto skaitymo, o jo be jūsų sutikimo neleidžiame.

**Nepatikrinta**
- Viso v3 priėmimo patikra ant `756e76e9` (2026-10-19) žalia: vienetų testai 1584 / 0 klaidų, eslint švarus, build gerai, visi backend testai 5479 praėjo / 3 praleisti / 0 klaidų (9 min 18 s), keturi tikslumo matavimai lygiai tokie pat kaip prieš v3 (paprasti 22,60 % / 26,1 % / 34,7 %; pakartoti 22,88 % / 27,9 % / 39,6 %), visas automatinis ėjimas 83 iš 83 (9,7 min). Įrašyta sujungimų žurnale.
- „Projekto atidarymas 2 lape po ~12 s šoka atgal" — nepavyko atkartoti 5 bandymais (W5-B). Jei pamatysite — pasakykite, kokiu keliu atidarėte.
- Senesnis kambario įrankio „užstrigimas" („Skaitomas kontūras…") neatkartotas ~100 bandymų (1 kartą, su netikėtu puslapio perkrovimu). Tikėtina priežastis pašalinta (W1-D-2). Jei pasikartos — reikės serverio būsenos tuo momentu.
- Senesni projektai su „langai" žymėmis be išsaugoto tipų sąrašo dabar rodomi rudai, ne raudonai (W1-D-2).
- Kai kurie W5-B automatinio ėjimo bandymai (kambario parodymas) kartą buvo nestabilūs; atskirai praėjo du kartus (W5-A).
- Kelių PDF įkėlimas ir „Ką programa perskaito" kortelė naršyklėje ant demo projektų nevaikščioti (patikrinti).

---

## 4. Jūsų sprendimai

Kiekvienas: kontekstas vienu sakiniu · galimybės · ką siūlo vadovas (jei siūlo).

**Skaičiavimas**

1. **Kampų numatytoji reikšmė** (`docs/superpowers/plans/2026-10-18-kampai-decision.md`). Ar naujas projektas kampų profilius skaičiuoja „su vidiniais" (dabar) ar „tik išoriniai". Galimybės: (a) palikti „su vidiniais" — iš 6 objektų 2 per ±10 %, mediana 17 %; (b) „tik išoriniai" — 1 per ±10 %, mediana 31 %, blogiau 4 iš 6; (c) klausti Patikroje kiekviename projekte. **Siūloma: (a).** Antras klausimas — kampai iš kontūro: objektas_a −6,11 % → +0,05 %, bet g +135,55 % → +169,04 %, h +14,57 % → +25,50 %. **Siūloma: neįjungti.**
2. **Jungikliai, kurie dabar išjungti** (visi matuoti; išjungti tikslumas identiškas bazei):
   - `SAMATU_FURNITURE_ZONES` — atimti įrašytus baldų plotus iš dažomų sienų. Įjungus matavimas identiškas. Plokščių dalis lieka tik faktu (variantas su plokščių atėmimu pablogino objektas_a 11,2 → 20,4 % ir išmestas).
   - `SAMATU_WALLPAPER_ROLLS` — tapetų ritiniai ⌈m² × 1,10 / 4,5⌉. Objektas_a atsiranda „Sienų tapetavimas" 24,52 m² + 6 ritiniai; niekas iš rangovų tapetų neįkainavo.
   - `SAMATU_NICHE_DEPTH` — nišų m² = metrai × gylis × 3. **Vadovas siūlo niekada neįjungti pagal nutylėjimą** — rangovai nišas įkainuoja metrais.
   - `SAMATU_BATH_DRAIN_ROWS` — eilutės „Vonios montavimas" ir „Trapų montavimas". **Dėmesio:** įjungus trapai būtų apmokestinti du kartus (legendos eilutė + „Trapų montavimas") — prieš įjungiant vieną iš jų reikia atsisakyti.
   - `SAMATU_WASTE_BY_PATTERN` — atliekos pagal perskaitytą klojimo raštą (eglutė, šešiakampės, dažai × 1,07; CLAUDE.md §3). Tikslumo matavimas medžiagų eilučių nevertina — spręsti reikia pagal tikrą sąmatą.
   - `SAMATU_REREAD_FIGURES` — nemokamas skaitymas skaito ir projektuotojo skaičius bei aukščius. **Siūloma neįjungti:** objektas_h jis pridėtų 320 m² sienų atramą, kurios projektas neturi.
   - `SAMATU_DIM_LINE_TICKS` — matmenų linijų ilgis be brūkšnelių galų (h linijos buvo +5,6 % ilgesnės). Paliečia tik įrodymo liniją, joks perimetras nejuda.
   - `SAMATU_ROOMS_BY_ZONES` — kambarių vieta pagal plano sritis, ne pagal fiksuotą antspaudo kirpimą. Įjungus pasikeitė tik objektas_a: bendrai geriau (apmokestintų eilučių vidutinė paklaida 4,06 → 3,90, sienų dažomas plotas geriau), bet „Dažymas" blogiau 3,07 → 4,75 % (1,7 p.p.); visas korpusas 22,85 % (be jungiklio 22,88 %). Jūsų sprendimas.
   - `SAMATU_VISION_LEGEND` — mokamas legendos ir lentelių skaitymas iš paveikslėlio (kiekvieną kartą su jūsų OK ir kaina). Naršyklės dialogo dar nėra. Ar jo reikia?
   - `SAMATU_NO_VISION_ROUTE` — vektorizuotiems PDF praleidžiamas Pass-1 vaizdo skaitymas: patalpų sąrašas, perimetrai ir nubraižytos angos ateina iš geometrijos takelių; `SAMATU_FORCE_VISION=1` lieka stipresniu jungikliu. **Neįjungti** — vartai nepraėjo: apmokestintų eilučių paklaida 57,50 → 65,86 %, takeliai dar nepakeičia langų, durų, LED nišų, paslėptų durų, baldų ir lubų tipo, kuriuos Pass-1 skaito.
   - `SAMATU_PASS1_NARROW` — vaizdo modeliui duodamas patalpų sąrašas iš lentelės, jo prašoma tik langų, durų, nišų, baldų ir lubų tipo; vienas skaitymas, be zoom. **Neįjungti** — vartai nematuoti; laukia mokamų skaitymų.
3. **Lizdų lapo paieška** (pasukti, mažesni ženklai) — Wave 7 kandidatas, ne €0. Daryti ar ne?

**Ekranas ir klavišai**

4. **F klavišas.** Dabar F = „Rasti panašius", o parodyti pažymėtą — Shift+F arba „.". Togal F reiškia „parodyti". Perjungti — viena eilutė kode. Palikti ar sukeisti?
5. **12 px žodžiai įrankių kortelėse.** 14 px reikia apie 550 px stulpelio, o prie 1280×720 brėžiniui lieka 534 px; patarimai, juosta ir užuominos — 14 px. Ar 12 px kortelėse tinka?
6. **Kambarių pavadinimai 340 px skydelyje** (6 iš 11 nukirpti). A — dvi eilutės; B — šaltinis vieną kartą antraštėje. Nuotraukos: `docs/superpowers/research/2026-10-19-w6a-shots/g3-now-*.png`, `g3-A-*.png`, `g3-B-*.png` (1440×900 ir 1280×720).
7. **Išvaizda.** 1 — kaip dabar; 2 — tamsus rėmas aplink šviesų brėžinį (gintarinė juosta ant jo blogiau matosi). Nuotraukos: `docs/superpowers/research/2026-10-19-w6a-shots/g4-look-1-today-*.png`, `g4-look-2-dark-frame-*.png`. Kol nenuspręsite — nieko nekeičiame.
   *Kelias:* nuotraukos jau perkeltos į `docs/superpowers/research/2026-10-19-w6a-shots/` (patikrinta: demo projektas, užsakovo duomenų nėra).
8. **Du „Kiekiai".** Siūloma: dešiniojo skydelio skirtukas → „Kiekių suvestinė", skyrius „Patalpos ir eilutės" viduje → „Sąmatos eilutės". Lietuviškus žodžius patvirtinate jūs.
9. **Paskyros puslapio pavadinimas** — jis irgi vadinasi „Nustatymai" (prielaidų mygtukas lieka „Nustatymai"). Pvz., „Paskyra"?
10. **Profesionalų sluoksnis** (#140): „Rodinys" kortelėje paruoštas, bet išjungtas jungiklis — kontūrų skaidrumas ir linijos storis. Su juo susiję: vienos eilutės išskyrimas, skydelio klaviatūra ir keli pažymėjimai, trijų būsenų ikonos, klavišų lapas, kuris rodo spaudžiamą klavišą, du lapai greta. Įjungti, kam ir kada?
11. **Atimti vienu spustelėjimu** pasiūlo bet kurią uždarą figūrą — ir baldus (demonstraciniuose brėžiniuose kolonų nėra). Pasiūlymas punktyrinis, kol nepaspausite Enter. Ar taip tinka, ar riboti tik storomis figūromis?
12. **Kambario parodymas dabar priartina** (iš sąrašo, Patikros, paieškos) — anksčiau tik nuslinkdavo į lapą. Patvirtinkite, kad taip norite.
13. Patvirtinkite ėjimo metu (vadovo sprendimai po W1-C): brėžinio kontūrai, perskaityti iš sienų, — ištisine linija, punktyras tik spėtiems; Sąmatos „Verta patikrinti" ir „Pastabos" paslėpti už „Rodyti visus (N)"; spalvų pasirinkime nebėra raudonos (raudona — tik klaidoms).

**Paleidimas į rinką** (W7-A)

14. **El. pašto tiekėjas** — SMTP reikšmės. Kol jų nėra, laiškai tik spausdinami serverio žurnale; tas pats su administratoriaus patvirtinimu (`SAMATU_ADMIN_EMAIL` adresas tampa administratoriumi tik patvirtinus paštą) — SMTP reikia nustatyti prieš tuo pasikliaujant.
15. **`SAMATU_REQUIRE_EMAIL_VERIFIED`** — ar paleidžiant reikalauti patvirtinto pašto prisijungimui.
16. **Atsarginių kopijų laikymas.** `SAMATU_BACKUP_KEEP_DAYS` nenustatytas = laikoma amžinai, o Privatumo puslapis žada 30 dienų. Nustatyti 30 ar pakeisti pažadą?
17. **Sesijos slapuko aprašas** — slapukas galioja 30 dienų, ne „sesijos"; pakeisti tekstą Slapukų puslapyje.
18. **Bandomojo laikotarpio įmonės kodas** lieka ištrynus paskyrą (kad bandymas nebūtų kartojamas) — ar tai tinka ir ar parašyti Privatumo puslapyje?
19. **Google šriftai** kraunami prieš sutikimą su slapukais: laikyti šriftus pas save arba įvardyti Google.
20. **Sąskaitos PVM taisyklė** — patvirtina buhalteris.
21. **„Kaip gauta" stulpelis** — ar paliekamas užsakovui siunčiamame eksporte.
22. **`PATHON_COMPANY_*`** (tiekėjo duomenys sąskaitoje) — būtina prieš įjungiant mokėjimus.
23. **Teisinė peržiūra** (Privatumas, Sąlygos, Slapukai) — advokatas; ką puslapiai žada prieš kodą: RUNBOOK §8b.

**Užsakovų duomenų slaptumas**

24. **Du projektų pavadinimai, kurie nėra kodiniai,** yra senesniuose saugyklos failuose: `audit/multi_project_audit.md`, `audit/samata_parse_summary.json`, `backend/extractor/feature_flags.py`, `backend/extractor/height_markers.py`, `backend/extractor/sanitary_fixture_reader.py`. Jų nėra draudžiamų žodžių sąraše; tikslumo matavimo įrankis juos spausdina. Ar jie slapti (tada — pervadinti kodiniais ir įtraukti į sąrašą)?
25. Senas įrašas `bad14b7` istorijoje turi draudžiamą žodį pranešime — spręsti prieš bet kokį viešinimą.

**Wave 7 kandidatai** (be takelio, kol nenuspręsite): keli naudotojai ir rolės · kainos planai · paskyros puslapio pavadinimas · kampų numatytoji reikšmė · el. pašto tiekėjas · kopijų laikymas · teisinė peržiūra · tamsus rėmas / išvaizda · profesionalų sluoksnis · du lapai greta · lizdų lapo paieška · pranešimas, kai skaitomas praleistas lapas · atskira geometrijos užklausų riba · išsaugotos paieškos / brūkšniuotė / paieškos rezultatai į kiekį.

---

## 5. Kas neišsiųsta ir kaip diegti

- **Niekas neišsiųsta (push) ir neįdiegta.** `togal-v2` yra tik šiame kompiuteryje; `main` (iš kurio automatiškai diegiama į app.pathon.eu ir api.pathon.eu) gerokai atsilieka. Joks v2 ar v3 pakeitimas gamyboje neveikia.
- Diegimas — tik jums leidus. Kontrolinis sąrašas: **`docs/RUNBOOK.md` §8a** („Deploy checklist — a togal-v2 batch to `main`", W7-A M10): `scripts/safe_deploy_check.sh` prieš kiekvieną išsiuntimą (kad diegimas nenutrauktų vykstančio skaitymo), „Wait for CI" ir privalomi patikrinimai (jūsų veiksmai Railway / Vercel), patikra gamybos adresuose po diegimo.
- Prieš diegimą jums reikia nustatyti gamybos aplinkoje: SMTP (14), `SAMATU_REQUIRE_EMAIL_VERIFIED` (15), `SAMATU_BACKUP_KEEP_DAYS` (16), CORS adresus (`SAMATU_CORS_ORIGINS`); mokėjimai lieka išjungti, kol nėra (20) ir (22).
- Paskutiniai trys sujungimai (5d2d8732, 8f5006ae, 756e76e9) sujungimų žurnale dar neturi eilutės — vadovas ją įrašys kartu su priėmimo patikros rezultatu.

---

## 6. Kas pasikeitė po 2026-10-24 (v4 — deterministinis skaitymas)

**Taisyklė, kurią pritaikėme:** nė vienas sąmatos skaičius nebeateina iš modelio „spėjimo" pagal paveikslą ir nė vienas — iš numatytosios reikšmės. Skaičius arba perskaitytas iš brėžinio (tekstas, vektorinės linijos, legenda, matmenys), arba išvestas iš perskaitytų faktų pagal įvardytą taisyklę, arba **tuščias su priežastimi** ir klausimu jums. Kiekviena eilutė nešiojasi savo kilmę.

**Ką pamatysite kitaip nei 10-19:**
1. **Brėžinys.** Patalpos vadinamos brėžinio numeriais (1-1 … 2-9), prie pervadintų kurį laiką matosi „buvo K2". Mastelis rodo, iš kur jis: „1:75 — iš plano matmenų (139 skaičiai)"; užrašytas, bet matmenų neatitinkantis mastelis pažymimas ir pralaimi. Naujas įrankis **„Skaičius" (N)**: brūkštelėkite liniją per užrašytą matmenį — mastelis nustatomas iš jo. Laisvas perskaitymas siūlomas pirma eilute, ne paslėptas po „Pranešimai".
2. **Patikra.** Klausimų mažiau ir jie tik apie tai, ko brėžinys nepasako: lubų aukštis (vienas atsakymas visoms patalpoms), kurių patalpų sienų ilgiai neužrašyti, durys ir langai, beapvadinės durys, grindų danga, dažomos sienos. Kol į klausimą neatsakyta, su juo susijusios eilutės **lieka tuščios** — ne skaičiuojamos su numatytąja reikšme.
3. **Sąmata.** Tuščia eilutė rodo brūkšnį, po juo — priežastį paprastais žodžiais ir mygtuką „Įrašyti". Medžiagų eilutės seka savo darbo eilutę. Šviestuvų, rozečių, santechnikos kiekiai ateina iš plano **legendos** kaip pasiūlymai, kuriuos patvirtinate (jie grubūs: nuo −38 % iki +50 % lyginant su rangovo eilutėmis). LED nišų ilgis — iš legendos (naujam skaitymui); seniems projektams po laisvo perskaitymo lieka tuščias.
4. **Jūsų projekte (objektas_i).** Visos 17 patalpų sutapdintos ir apibrėžtos (ploto paklaida 0,1 %), 11 iš 17 perimetrų sudėti iš užrašytų matmenų, 15 langų ir balkono durys perskaityti. Lubų aukščio brėžinyje nėra — todėl sienų eilutės laukia vieno jūsų atsakymo.

**Skaičiai, kuriuos reikia žinoti (korpusas iš 6 rangovo sąmatų):**
- Eilučių, patenkančių į ±10 % nuo rangovo: 26 % prieš v4 → **8,7 %** dabar. Kritimas tyčinis: 40 eilučių sutapo tik dėl modelio spėjimo ar numatytosios reikšmės; dabar jos tuščios ir skaičiuojamos kaip klaidingos. Kas tuščia, tą matote — ir užpildote vienu atsakymu arba skaičiumi.
- Kodėl likusios eilutės nesutampa: 47 % rangovo eilučių neturi mūsų atitikmens (šeimos, kurių neskaičiuojame; jo skaidymas; vienetai) — tai ne slenksčių ar prielaidų klausimas. Lubų aukštis NĖRA kliūtis (išmatuota: aukštis visoms patalpoms pajudina 1 eilutę).
- Rastriniai (skenuoti) brėžiniai: patalpų atpažinimas iš rastro išbandytas dviem būdais (SAM 2 ir deterministinis) — abu nepraėjo vartų nematytuose lapuose; **nukelta**. Skenuoti lapai gauna OCR (mastelis, žymos, lentelė) ir rankinį kontūrą.

5. **Sienų apdaila iš išklotinių (2026-10-26).** Programa skaito apdailos planą ir išklotinių lapus kaip nubraižyta — sienai po sieną: kur plytelių laukas, kur dažoma, kur plokštė ar tapetai, kur baldai. Plytelės — tik nubraižyti laukai (objektas_a virtuvėje 5,95 m², ne 33 m² juosta aplink visą patalpą). Patalpai be išklotinių ir be apdailos teksto sienos laikomos dažomomis ir prie jų parašyta „Išklotinės šiai patalpai nėra — patikrinkite” (anksčiau tambūras / garažas buvo 0 pagal paskirtį — spėjimas). Sienos už įmontuotų baldų **dažomos** (jūsų sprendimas 2026-10-26: namas dažomas prieš montuojant baldus; nustatymas „už baldų dažoma”, išjungiamas) — prie patalpos parašyta, kiek metrų sienos skaičiuota kaip dažoma už baldų. objektas_a: dažomos sienos 444 m² su garažu, 408 m² be garažo (rangovas: 420 be garažo — skirtumas 2,9 %, jo skaičius tik patikrai). Korpuso skaičiai: billed 58,81 → 57,50 %; eilutės ±10 % 8,7 → 9,0 %, € ±10 % 14,8 → 18,0 %.

6. **Skaitymas be vaizdo modelio (vektoriniams PDF) (2026-10-27).** Prašėte nuimti Pass-1 vaizdo skaitymą vektorizuotiems brėžiniams, kurių patalpų sąrašą galima perskaityti iš teksto sluoksnio. Programa išbandyta: a / b / d / h eina be Pass-1, c / g — šios sesijos Vision skaitymais. Rezultatai: apmokestintų eilučių paklaida 57,50 → 65,86 % PABLOGĖJO; eilutės ±10 % 9,0 → 8,9 % praėjo; € ±10 % 18,0 → 16,4 % PABLOGĖJO; taškų kortelė 32/32 · 29/30 → 25/32 · 26/30 PABLOGĖJO. Greitis su jungikliu įjungtu (saugoto mokamo skaitymo laikrodis → takeliai): objektas_h 735 → 17 s, d 212 → 21 s, b 468 → 304 s, a 208 → 206 s; c ir g — 0 patalpų (teksto sluoksnyje patalpų sąrašo nėra). Kodėl pablogėjo: Pass-1 skaito ne tik patalpų sąrašą — kiekvienai patalpai jis taip pat nuskaito langus, duris, LED nišas, paslėptas duris, įmontuotus baldus ir lubų tipą; geometrijos takeliai šiems laukams šaltinio dar neturi. Kelias sukurtas ir įtrauktas, bet išjungtas; įjungti lokaliai: `SAMATU_NO_VISION_ROUTE=1` backend aplinkoje (tada objektas_h perskaitomas per 17 s, bet aukščiau išvardyti laukai lieka tušti). Ataskaita: `docs/superpowers/research/2026-10-26-no-vision-vector-route.md`.

7. **Siauras Pass-1 (2026-10-27/28).** Pasirinkote siaurinti Pass-1, o ne nuimti. Kas pastatyta: prieš paveikslėlio skaitymą vaizdo modeliui perduodamas patalpų sąrašas iš teksto lentelės; modelio prašoma tik tų laukų, kurių takeliai neskaito — langų, durų, paslėptų durų, LED nišų, įmontuotų baldų ir lubų tipo; lapai atrenkami pagal tekstinį lapo tipą (aukšto planas, lubų planas, baldų lapai, durų ir langų žiniaraštis); vienas skaitymas be balsavimo (`SAMATU_PASS1_NARROW_VOTES=3` grąžina balsavimą); be zoom; ta pati apdorojimo eilutė toliau; c ir g (be teksto lentelės arba be aukšto plano lapo) lieka su šiandieniniu pilnuoju Pass-1. Kodėl turėtų būti greičiau: objektas_h — trys nuoseklūs balsavimo ratai po ~10 000 išvesties žetonų ≈ 510 s iš 735 s; zoom 87 s be pakeitimų; vienas siauras ratas ≈ 50–60 s — įvertis, nematuota. Kas laukia: ~7 USD mokamų skaitymų vartams (6 projektai × 1 ratas ≈ 3 USD, plius 3 ratų palyginimas ≈ 3 USD) — kai bus kredito, paleidžiamas `scripts/pass1_narrow_gate.sh`.

8. **Greitesnis pilnas Pass-1 (2026-10-28).** Išmatuota su `ENABLE_PARALLEL_VOTING=1` (≈ 1,9 USD iš viso):

   - **objektas_h: 735 → 295 s** (visa procedūra). Pass-1 277 s: pirmas ratas vienas ≈ 138 s (įrašo spartintuvą), antras ir trečias kartu ≈ 139 s (abu skaito spartintuvą — 35 420 žetonų/ratas); kaina 1,15 USD.
   - **objektas_d: 261 s** (Pass-1 230 s; kaina 0,78 USD; palyginimas nebetiesinis — saugota versija buvo kitu modeliu).
   - **Balsavimo ratai yra lygiagrečiai**: vienas ratas pirmiau (rašo spartintuvą), kiti du kartu (skaito). Papildomos kainos nėra — spartintuvo ratai moka 0,1× įvesties kainą.
   - **Zoom jau nulis** lentelę turintiems projektams (a, b, d, h — pagal 2026-10-25 taisyklę). c ir g (be lentelės) zoomina toliau.

   Kas **nesikeičia**: rezultatai tie patys pagal konstrukciją — tie patys užklausai, tas pats modelis, ratai suteikiami vidurkiui tokia pačia tvarka. Matuojant iš naujo skaičiai svyruoja ±1–2 pp vien dėl pakartotinio skaitymo — tai verta žinoti vertinant bet kokius „vartus" ar palyginimo skaičius.

   Kas **lieka**: 277 s — trys pilni balsavimo ratai po ≈ 12 000 išvesties žetonų kiekvienam. Trumpinti Pass-1 išvestį nemokamai nepavyko — žr. 7 punktą. Gamyboje įjungta 2026-10-28.

**Jūsų sprendimai, jau priimti ir įgyvendinti:** sienos už įmontuotų baldų dažomos (2026-10-26), hidroizoliacija dviem eilutėmis (jūsų taisyklė; rangovas rašo vieną), angų užskaita 3,0 m², rastro kelias nukeltas, 3b sujungtas žinant metrikos kritimą, Sonnet darbams be inžinerinio sprendimo.

**Laukia jūsų (nauja, 2026-10-28):** (e) **plytelių klojimas iki lubų** — nubraižytas klojimas ≥ 90 % patalpos aukščio laikomas iki lubų (objektas_a 107/111: 2,64–2,72 m prie 2,80 m → dažomos juostos nėra; rangovas ją skaičiuoja): palikti 0,9 ir rodyti juostą kaip klausimą Patikroje, kai tarpas 5–15 cm (siūlau), ar 1,0; (f) **siauro Pass-1 kelias** — pasirinkta (1): siauras Pass-1 pastatytas ir sulietas, išjungtas (`SAMATU_PASS1_NARROW=1`). Vartai išmatuoti 2026-10-28 — nepraėjo (vieno rato siauras skaitymas išgalvoja langų ir durų dydžius, praleidžia LED nišas); lieka išjungtas — žr. 7 punktą ir ataskaitos §10; (g) **lygiagretus balsavimas gamyboje** — įjungta 2026-10-28 21:11 (`ENABLE_PARALLEL_VOTING=1` Railway gamybos aplinkoje, tas pats kodas a68a56b); įjungiant programa ~10 min neatsakė (vadybininko klaida šalinant užstrigusį diegimą — užfiksuota, nebepasikartos).

**Laukia jūsų:** (a) santechnikos prietaisai be legendos — tuščia ar modelio skaičius; (b) medžiagų specifikacijos skaitymas nebekainuoja — ar nustoti skaičiuoti veiksmą; (c) objektas_b vėdinimo eilutės (tiekėjo specifikacija, be plano) — ar jas skaičiuoti į vardiklį; (d) kada stumti į `main`.

**Nepadaryta (po jūsų verdikto):** Pass-1 (modelis vis dar skaito lapus kaip paveikslus patalpoms/angoms/apžvalgoms — paskutinis pikselių kelias), GKP priedai iš lubų plano geometrijos, šviestuvų/rozečių skaičiavimas tiksliau nei legenda, LED iš legendos seniems projektams, Patikros tekstų smulkmenos, WebKit e2e sąveikos testai (Safari tikrinate rankomis).
