# Patikra kaip klausimų eilė — „programa siūlo, jūs patvirtinate"

Data: 2026-09-21 · Būsena: steigėjo patvirtinta kryptis („tinka") · Kaina: €0 (jokio Vision)

## Kodėl

Steigėjas 2026-09-21 perėjo H projektą localhost'e: „viskas pasižymi labai gerai ir tiksliai…
bet atrodo vis tiek kažkiek komplikuotas naudojimas… per daug veiksmų visokių būtų rangovui."

Pamatuota jo paties projekte:

| | faktų ekrane | iš jų reikia žmogaus | klausimų rūšių |
|---|---|---|---|
| H (šviežias) | 66 (11 patalpų × 6) | 22 | 3 (aukštis 9, perimetras 6, durys/langai 7) |
| G | 54 | 19 | 5 (aukštis 8, grindys 5, perimetras 4, angos 1, plotas 1) |

Šiandien visi 66 faktai rodomi vienodu svoriu, kiekvienas su dviem mygtukais, o kiekviena pataisymo
rūšis turi SAVO valdymą (įrašyti skaičių, pasirinkti, pridėti duris, spustelti brėžinyje, du
paspaudimai, užvesti pelę). Rangovui tai penki skirtingi dalykai, kuriuos reikia išmokti.

## Principas

**Programa siūlo — žmogus patvirtina.** Vienas veiksmo šablonas visiems klausimams:
klausimas → programos siūlomas atsakymas → „Tinka" (arba pataisyti) → kas pasikeitė → kitas klausimas.
Tos pačios rūšies klausimas užduodamas VIENĄ kartą visam projektui. Kas perskaityta iš brėžinio —
tyli, mygtukų neturi ir žmogaus nelaukia. Šiandieninis lapas po patalpas lieka kaip antrinis
„Peržiūrėti pagal patalpas".

## Ko NEDAROME

- Jokios naujos skaitymo logikos: klausimai surenkami iš TŲ PAČIŲ `room_facts` faktų (status ≠ `read`).
  Vienintelė nauja geometrija — siūloma bendros erdvės riba (žr. žemiau).
- Nekeičiame, ką faktai sako, ir nekeičiame rašymo kelių: atsakymai eina tais pačiais keliais kaip
  patalpos lape (`saveAssumptionEdit`, `saveRoomEdit` → perskaičiavimas → pasekmės juosta → atšaukimas).
- „Praleista" nesaugoma — tai tik šios sesijos būsena; praleistas klausimas lieka atviras.
- „Bendri projekto dalykai" (simboliai, apimtis, „Jūsų eilutės") lieka kur buvę (`?etapas=bendri`).

## Klausimų rūšys (tokia tvarka ir klausiama)

Tvarka — nuo to, kas keičia kitus klausimus: kontūras ir riba perskaito sienas iš naujo, todėl eina
prieš perimetrus. Po KIEKVIENO atsakymo klausimai surenkami iš naujo — patalpa, kurios sienos po
parodymo perskaitytos, iš perimetrų sąrašo dingsta pati.

| kind | kada | siūlomas atsakymas | atsakymo forma (`answer`) |
|---|---|---|---|
| `aukstis` | patalpos, kurių aukštis — mūsų prielaida | naudojamas aukštis (dažniausias) | `number_all`: vienas skaičius visoms; „kai kur kitaip" → laukas prie kiekvienos |
| `konturas` | patalpa turi `outline_reason`, nėra bendroje erdvėje | — (reikia paspaudimo) | `outline`: brėžinys iš karto rodymo režimu, patalpos viena po kitos |
| `erdve` | bendra erdvė iš lygiai 2 patalpų (po klausimą kiekvienai erdvei) | riba pagal lentelės plotus | `split`: „Tinka" / „Nubrėšiu pats" (du paspaudimai, gyva linija) |
| `perimetras` | perimetro faktas `missing` su įverčiu arba `assumed` | įvertis iš sienų kontūro / naudojamas skaičius | `numbers`: sąrašas, laukas prie kiekvienos, „Tinka visi" |
| `plotas` | ploto faktas `assumed` / `missing` | naudojamas plotas (jei yra) | `numbers` |
| `angos` | durų ir langų faktas ≠ `read` | angos, kurias rodo sienos (`suggestions`) | `openings`: varnelių sąrašas „Pridėti pažymėtas"; patalpos be vieno paspaudimo pasiūlymo — sąraše „patikrinkite patys" su nuoroda į patalpos lapą |
| `grindys` | grindų dangos faktas `assumed` | danga pagal paskirtį | `choices`: pasirinkimas prie kiekvienos, „Tinka visi" |
| `apdaila` | sienų apdailos faktas `assumed` | dažoma / nedažoma pagal paskirtį | `choices` |

Patalpos, išjungtos iš apimties („Neskaičiuoju"), klausimų neduoda.

## Backend

### `extractor/project_questions.py` — `build_questions(project) -> dict` (gryna funkcija, be PDF)

Kiekvienai patalpai apimtyje kviečia `build_room_facts` ir grupuoja faktus, kurių `status != "read"`.

```
{"questions": [Question], "asked": <faktų, kurie laukia žmogaus>, "read": <faktų, kurie nelaukia>, "rooms": <patalpų>}

Question = {"id": "aukstis" | "konturas" | "erdve:04+05" | "perimetras" | …, "kind", "answer",
            "title", "why", "unit", "proposed" (tik number_all), "items": [Item], "manual": [Manual]}
Item     = {"room_nr", "room_name", "field", "proposed", "proposed_label", "unit", "sentence", "page",
            + angos: "tipas", "plotis_mm", "aukstis_mm", "i", "label", "line_pct"
            + choices: "choices": [{"value", "label"}]
            + konturas: "reason", "marker_pct"}
Manual   = {"room_nr", "room_name", "sentence"}          # ką patikrinti pačiam patalpos lape
```

Tekstai lietuviški, generuojami serveryje (kaip faktų sakiniai), per `user_text.scrub_prose`.

### `GET /api/projects/{id}/questions` (`api/project_questions.py`)
Autorizacija ir savininko filtras kaip `…/facts`. Nieko nesaugo.

### Siūloma riba: `vector_rooms.propose_split` + `POST …/rooms/{nr}/split-proposal`
- `split_space` išskaidoma į `_shared_face` (erdvė, kurioje abu numeriai) ir `_cut_rooms` (pjūvis →
  abiejų patalpų kontūrai); elgsena nesikeičia (esami testai).
- Kandidatai: vertikalios ir horizontalios linijos (a) per kiekvieną erdvės kontūro VIRŠŪNĘ tarp abiejų
  numerių (sienos išsikišimas, kolona — natūrali riba), (b) per plotų pusiausvyros vietą (bisekcija,
  kad dalys santykiu atitiktų lentelės plotus). Kiekvienas kandidatas pjaunamas tuo pačiu `_cut_rooms`.
- Renkamasi: viršūnės kandidatas su mažiausia didžiausia ploto paklaida, jei ji ≤ `AREA_TOL` (8 %);
  kitaip pusiausvyros linija; jei niekas nepjauna į dvi dalis — `{"status": "no_proposal"}` ir UI iš
  karto siūlo brėžti pačiam.
- Atsakymas = `split-space` atsakymas (abiejų patalpų geometrijos raktai, `kitu_angos`) + `line_pct`
  (ribos atkarpa erdvės viduje). „Tinka" = tas pats `roomsWithSplit` → `saveRoomEdit`; antro kvietimo
  nereikia. Serveris nieko nesaugo.

## Frontend

- Maršrutas `/project/:id/patikra`: be `kambarys`/`etapas` → **Klausimai** (`pages/PatikraQuestions.jsx`);
  su jais → esamas `RoomSheet`. Patalpos lapo juostoje — nuoroda „← Klausimai".
- `lib/useProjectFixes.js` — iš `RoomSheet.jsx` iškelti `run` / `land` / `undoLastFix` (vienas
  perskaičiavimo nusileidimo kelias abiem ekranams; `mergeDarbuSarasasEdits` lieka vienintelis sargas).
- `lib/questions.js` (gryni, su testais): kito atviro klausimo parinkimas, eigos skaičiai, atsakymo →
  pataisų sudarymas (`heightAnswer`, `numbersAnswer`, `choicesAnswer`, `openingsAnswer`), „jau naudojamas
  skaičius" atpažinimas keliems kambariams (`alreadyInUse`).
- `lib/questionsApi.js`: `fetchQuestions`, `fetchSplitProposal`.
- `components/questions/`: `QuestionRail` (kairėje: klausimai su būsena), `QuestionCard` (pavadinimas,
  „kodėl", kūnas, „Tinka…", antrinis veiksmas, „Praleisti"), kūnai pagal `answer`.
- Sąrašo klausimuose dešinėje — TAS PATS `RoomDrawingPane` pažymėtai patalpai (kontūras, sienos,
  angos): skaičius be vaizdo nepatvirtinamas. `aukstis` — be brėžinio (nėra ko rodyti).
- `CheckLayer`: `proposal` — dviejų patalpų kontūrai ir punktyrinė riba PRIEŠ patvirtinant.
- Po atsakymo: vienas perskaičiavimas → iš karto kitas atviras klausimas; ankstesnio atsakymo pasekmė
  lieka juostoje viršuje („Atsakyta: … Sąmatoje pasikeitė N eilučių / Kiekiai nepasikeitė, nes…",
  „Atšaukti") iki kito atsakymo. Jokio papildomo „Toliau" paspaudimo.
- Pabaiga: „Klausimų nebeliko" + „Toliau — sąmata"; nuorodos „Peržiūrėti pagal patalpas" ir
  „Bendri projekto dalykai". Rėlio apačioje visada: „Perskaityta iš brėžinio ir jūsų nelaukia: N skaičių".
- Visas UI tekstas lietuviškai (`i18n/lt.json` + `en.json`), jokio žargono, jokių paslėptų už pelės
  užvedimo dalykų, instrukcija brėžinio veiksmui — prie brėžinio.

## Rizikos ir kaip jos suvaldytos

- **Skaičiaus, kurio neklausiam, niekas nepažiūrės.** Klausimu tampa VISKAS, kas nėra perskaityta iš
  paties brėžinio (status ≠ read); peržiūra po patalpas lieka vienu paspaudimu; eilutės lygio
  patikra (scorecard) nesikeičia.
- **Masinis „Tinka" ≠ patikrinta tiesa.** `build_ground_truth.py` renka tik kontūrus
  (`polygon_source ∈ corrected/manual`) ir eilučių `manual_override`/`user_verified` — priimti įverčiai į
  ground truth nepatenka.
- **Durys iš sienų keičia angokraščius** (pamatuota: H 70 → 115 m; vidaus durų angokraščių konvencija —
  steigėjo sprendimas). Klausimas yra aiškus pasirinkimas su matoma pasekme ir atšaukimu; niekas
  nepridedama automatiškai.
- **Rastriniai brėžiniai** (nėra vektorinių sienų): `konturas`/`erdve` klausimų nėra (nėra
  `outline_reason`), perimetrai ateina kaip `numbers` sąrašas.

## Tikrinimas

1. Backend vienetų testai (sintetiniai projektai → klausimai; tvarka; apimtis; tekstai be žargono).
2. Tikri H ir G: klausimų skaičius ir sudėtis pagal lentelę viršuje; `propose_split` ant tikro H
   (abi dalys ±8 % nuo lentelės, riba per sienos išsikišimą).
3. Frontend vienetų testai (`lib/questions.js`).
4. Naršyklėje ant H ir G kopijų: kiekviena klausimo rūšis nuo pradžios iki pasekmės juostos ir
   atšaukimo; pabaigos būsena; kelias į patalpos lapą ir atgal; patalpos lapas veikia kaip veikęs.
5. Vartai: visas backend `pytest`, `npm run test:units`, eslint paliestiems failams, geometrijos
   vartai; eval nesikeičia (skaitymo logika neliesta).
