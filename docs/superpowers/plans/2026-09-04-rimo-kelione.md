# „Rimo kelionė“ — programa, kurią supranta 52 metų rangovas (2026-09-04)

> Dizaino pagrindas, ne techninis planas. Personažas: **Rimas, 52 m., apdailos rangovas**, 4 žmonių brigada, sąmatas daro Excel'yje vakarais, telefonu skambina daugiau nei rašo, naujovę priima tik jei po pirmo karto aišku, kad **mažiau darbo, ne daugiau**. Programą jam parodė pažįstamas. Jis neskaitys instrukcijos. Jei per 2 minutes nesupras, ką daryti — uždarys ir daugiau neatsidarys.

## 1. Penki principai (ir ką jie draudžia)

1. **Programa atrodo kaip jo darbas, ne kaip „AI produktas“.** Jis atpažįsta: brėžinį, kambarį, eilutę, kiekį, kainą, sąmatą. Draudžiama ekrane: *AI, analizė, ekstrakcija, Vision, modelis, pasitikėjimas, konfidencija, tikrintinų, polygon/zona, tier, koeficientas, recompute, ledger, kvitas, orphan/pasenusi*. Vietoj jų: *perskaityta iš brėžinio, kambarys, kontūras, priedas, perskaičiuota, senesnė eilutė*. Vienintelė „AI“ frazė — pirmame ekrane: „Programa perskaito brėžinį ir paruošia kiekius. Jūs patikrinate ir įrašote kainas.“ Daugiau to žodžio nereikia.
2. **Vienas kelias, keturi žingsniai, visada matomi viršuje:** **Brėžinys → Patikra → Sąmata → Siųsti.** Jokių skirtukų, režimų, panelių, kurias reikia „atrasti“. Kur esu — matau; kas toliau — vienas didelis mygtukas; atgal — visada galima.
3. **Prie kiekvieno skaičiaus — iš kur jis.** Ne taškelis, ne procentas, o iškarpa iš brėžinio ir sakinys: „iš eksplikacijos lentelės, eil. 110“. Kai programa nežino — sako žmonių kalba ir palieka tuščią langelį: „Aukščio pjūvyje neradau — skaičiuoju su 2,80. Įrašykite tikrą.“
4. **Kiekvienas pasirinkimas — su pasekme šalia.** Ne „Įtempiamos lubos ☐“, o „Lubos: **dažomos** / **įtempiamos** — įtempiamų lubų kambaryje lubų glaistymo ir dažymo sąmatoje nebus.“ Numatytoji reikšmė visada parinkta ir pavadinta („kaip visiems kambariams“), kad nieko nespaudus rezultatas būtų protingas.
5. **Nieko negalima sugadinti.** Viskas išsisaugo pats. Kiekvienas veiksmas — „Atšaukti“. Ištrinti galima tik projektą, ir tą galima atstatyti 30 dienų. Jokių „Ar tikrai?“ langų — vietoj jų grįžtamumas.

## 2. Kelionė ekranas po ekrano (su tekstais)

### E0 · Pradžia — „Mano projektai“
Vienas didelis mygtukas: **„Naujas projektas — įkelti brėžinį (PDF)“**. Žemiau — projektų kortelės su būsena žmonių kalba: *„Kiekiai paruošti — liko patikrinti 7 kambarius“*, *„Sąmata išsiųsta 2026-09-01“*, *„Skaičiuojama… ~12 min“*. Nieko daugiau. Dešinėje viršuje — **„Pagalba: paskambinti Ignui“** su numeriu (žmogus telefone šiame etape vertesnis už bet kokį vedlį).

### E1 · Įkėlimas — trys klausimai, visi su numatytais atsakymais
- PDF įkėlimas (tempti arba spausti). Iš karto po įkėlimo: *„17 lapų · yra kambarių lentelė · yra apdailų lentelė“* — arba sąžiningai: *„Šis PDF — nuotraukos be teksto. Kiekius paskaičiuosim, bet tikrinti reikės atidžiau.“*
- **„Koks objektas?“** Butas / Namas / Komercinės patalpos (numatyta iš PDF antraštės).
- **„Lubų aukštis, jei žinote“** — laukelis su „2,80 m — kaip dažniausiai“ (galima palikti).
- **„Ką skaičiuoti?“** Sienų ir lubų apdaila · Grindys · Plytelės · Santechnika · Elektra — visi pažymėti; nuėmus — tų eilučių sąmatoje nebus (pasekmė parašyta).
- Mygtukas: **„Skaičiuoti kiekius“**. Po juo: *„Truks apie 20 minučių. Galite uždaryti — atsiųsime el. laišką, kai bus paruošta.“*

### E2 · Laukimas — pasakojama, kas vyksta
*„Skaitau aukšto planus (2 iš 17 lapų)… Radau kambarių lentelę — 11 kambarių… Skaitau apdailų lentelę… Skaičiuoju kiekius…“* Laikas iki pabaigos. Tas pats tekstas — el. laiške. Jokio „progress bar“ be žodžių.

### E3 · Patikra — kambarys po kambario (dizaino sprendimo v4 lapas)
Antraštė: **„Patikrinkite 11 kambarių — apie 3 minutes“**. Kairėje brėžinys, pats priartintas prie kambario; dešinėje kortelė:
- **„Ką perskaičiau“** — plotas, perimetras, aukštis, apdaila, durys/langai, grindys; prie kiekvieno iškarpa ir sakinys. Trūkstamas — geltonas laukelis su priežastimi.
- **„Ką iš to paskaičiavau“** — dažymas, kampai, angokraščiai, grindjuostės, plytelės, grindys; formulė tikrais skaičiais; sienos/kampai/angos pažymėti plane; prie kiekvieno „✓ / Pataisyti“.
- Vienas didelis mygtukas apačioje: **„Viskas teisinga — kitas kambarys“** (Enter). Jei kažką pataisė — mygtukas pasikeičia į **„Išsaugota — kitas kambarys“**, o po juo viena eilutė: *„Persiskaičiavo 3 eilutės (+12,4 m² dažymo)“*.
- Po kambarių — **„Bendri dalykai (3)“** (visas lubų plotas iš lentelės, rozetės iš elektros plano su iškarpa, sienos storis) ir **„Jūsų eilutės (5)“** — tai, ko brėžinys nesako, tušti langeliai, jo žodžiais, įsimenami kitam projektui.
- Pabaiga: **„Patikrinta. Sąmata paruošta →“**. Negalima „užstrigti“: kambarį galima praleisti („Peržiūrėsiu vėliau“ — jis lieka pažymėtas viršuje).

### E4 · Sąmata — jo lentelė, jo skyriai
Lentelė kaip jo Excel'yje: *Gipso kartono darbai · Sienų ir lubų glaistymas, dažymas · Plytelių darbai · Santechnika · Elektra · Medžiagos*. Stulpeliai: eilutė, vnt, kiekis, kaina, suma. Kiekvienas kiekis — su nuoroda „iš kur“ (tas pats kambario lapas). Kainos: **„Užpildyti iš mano kainyno“** (jei įkeltas) / **„Įvesiu pats“** — įvedimas klaviatūra Enter → kita eilutė. Viena eilutė apačioje, žmonių kalba: *„42 eilutės iš brėžinio, patikrintos 38 · 5 eilutės — jūsų įrašytos · 3 eilutės be kiekio — įrašykite arba ištrinkite.“* Pridėti eilutę — bet kuriame skyriuje, iškart.

### E5 · Siųsti
**„Excel (mano šablonas)“ · „PDF klientui“ · „Išsiųsti el. paštu“.** Prieš siunčiant — ne įspėjimų sąrašas, o vienas sakinys: *„3 eilutės be kiekio bus praleistos. Siųsti?“*

## 3. Pasirinkimai, kurie turi būti aiškūs (žodis į žodį)

| Kur | Pasirinkimas | Kaip parašyta |
|---|---|---|
| Kambarys | Lubos | **Dažomos** / **Įtempiamos** — „įtempiamų lubų kambaryje lubų glaistymo ir dažymo sąmatoje nebus“ |
| Kambarys | Sienos | **Dažomos** / **Plytelės iki __ m** / **Nedažomos** — „nedažomos: sienų glaistymo, dažymo ir kampų šiam kambariui nebus“ |
| Kambarys | Aukštis | laukelis + „☑ toks pat kaip kituose kambariuose“ |
| Kambarys | Durys / langai | skaičius su − / + ir matmenys „iš žiniaraščio, psl. 9“ arba „standartiniai 0,9 × 2,1 — pakeiskite, jei kitokie“ |
| Projektas | Glaistymo kokybė | **Q2 — po matiniais dažais (įprasta)** / **Q3 — po pusiau blizgiais** / **Q4 — po blizgiais, pilnas glaistymas** |
| Projektas | Sienos storis | „0,10 m — tik angokraščių plotui; kiekių beveik nekeičia“ (todėl ne pirmoje vietoje) |
| Sąmata | Kainos | **Iš mano kainyno** / **Įvesiu pats** / **Palikti tuščias** |
| Sąmata | Eksportas | **Excel (mano šablonas)** / **PDF klientui** |
| Bet kur | Ištrinti | „Ištrinti (galima atstatyti 30 dienų)“ — vienintelis atvejis su patvirtinimu |

## 4. Ką paslėpti arba išmesti (iš UX audito, patvirtinta)
3 žingsnių vedlys prieš pirmą brėžinį · pirmas lapas — viršelis (atidaryti planą) · antra tikrinimo sistema Kiekiuose (85 vs 72) · 4 statistikos plytelės ir 4 filtrai virš lentelės · „Analizės detalės (admin)“, „AI rasti simboliai (181)“ · AI pokalbis kaip pagrindinis skirtukas (→ mygtukas apačioje) · Prielaidos kaip visas ekranas (→ 3 projekto nustatymai; visa kita — kambario lape) · 85 px eilutės (→ 40 px) · žargonas iš 1 punkto.

## 5. 35–60 metų akims ir rankoms
Šriftas ≥ 16 px, kontrastas, mygtukai ≥ 44 px, jokių veiksmų tik užvedus pelę, jokių veiksmų tik tempiant (kontūro taisymas — ir spustelėjimais po tašką), matomi „+ / −“ priartinimui, Lietuvių kalba visur (net „Enter“ paaiškinta: „Enter — kitas kambarys“), telefone — peržiūra ir pastabos objekte, ne redagavimas. Pirmam projektui — vienas sakinys kiekviename ekrane („Čia patikrinate kambarį; jei viskas gerai — spauskite Enter“), išjungiamas.

## 6. Kaip Rimas žino, kad pavyko
Penktadienį vakare jis įkėlė PDF, nuėjo vakarienės, gavo laišką, per 6 minutes praėjo 11 kambarių, tris kartus pataisė aukštį ir vieną kartą sienas, įrašė 4 savo eilutes, užpildė kainas iš kainyno ir išsiuntė Excel'į klientui — **20 minučių vietoj 2 valandų**, ir kiekvieną skaičių gali paaiškinti klientui rodydamas brėžinį. Tai ir yra matas: *laikas iki išsiųstos sąmatos* ir *ar jis grįžo su antru projektu*.
