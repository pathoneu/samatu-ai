# Mažiau tų pačių klausimų — vienas atsakymas visoms patalpoms ir projekto autoriaus suma kaip patvirtinimas

2026-09-20. €0. Steigėjo nurodymas: „pradėk nemokamus be mano sprendimo" (sąrašo 5 ir 7 punktai: faktų peržiūra
per patalpas, aukščiai). Dizainas, planas ir žurnalas — viename lape: abu pakeitimai maži.

## Kodėl
„Nuima labai mažai rankinio darbo" (2026-09-17). Suskaičiuota 2026-09-20 ant vietinių demo projektų, kiek faktų
Patikroje NĖRA „perskaityta" (geltonos eilutės, į kurias jis turi reaguoti):
- H: 32 — lubų aukštis 9, sienų apdaila 9, perimetras 7, durys ir langai 7;
- G: 20 — lubų aukštis 8, grindys 5, perimetras 5, durys ir langai 1, plotas 1.
Du didžiausi blokai — TAS PATS klausimas, kartojamas kiekvienoje patalpoje.

1. **Lubų aukštis.** Išmatuota: nei H, nei G brėžinys aukšto aukščio nerašo niekur (nei „H - 2820", nei altitudžių
   lubų plane; H lubų planas sako tik „Lubos nuleistos minimaliai pagal faktą"). Klausimas sąžiningas — bet atsakymą
   jis žino VIENĄ visam butui, o lapas vertė įrašyti 9 kartus.
2. **Sienų apdaila (H).** 9 patalpos sakė „parinkta pagal patalpos paskirtį. Patikrinkite išklotinėse arba apdailų
   lentelėje" — brėžinyje, kuriame nėra nei išklotinių, nei apdailų lentelės. Jame yra projekto autoriaus legenda
   „Sienų dažai … 320 m²", o mūsų patalpų suma — 320,28 m². Sąmata apmoka SUMĄ; ją patvirtina paties brėžinio skaičius.

## Ką padarėme
1. `room_facts._fact_aukstis`: `same_question` — kitos patalpos, kurių aukštis vis dar mūsų numatytasis (ar jo nėra)
   ir kurių jis dar neatsakė; sakinys „Tas pats klausimas dar 8 patalpose (01, 03, …) — atsakyti galite visoms iš
   karto." FactRow: „Įrašyti visoms 9 patalpoms, kurios to klausia" → `roomSheet.heightsForRooms` → vienas
   `saveAssumptionEdit`, viena pasekmės juosta, vienas „Atšaukti". Perskaitytas ar jo įrašytas aukštis neklausia.
2. `room_facts._designer_wall_total`: `_autoriaus_kiekiai` šeimos `sienu_dazymas` (m²) suma greta mūsų patalpų
   `walls_paintable_m2` sumos. Sutampa ±3 % → apdailos faktas, kurio apdaila parinkta pagal paskirtį, tampa
   „perskaityta": „Sienų apdaila — pagal patalpos paskirtį. Visų patalpų dažomų sienų suma 320,28 m² sutampa su
   projekto autoriaus užrašyta 320,00 m² (6 psl.) — kiekvienos patalpos atskirai tikrinti nereikia." Įrodymas —
   pati legendos eilutė jos lape. Nesutampa → klausimas lieka (skirtumas matomas „Bendruose dalykuose").
   Autoriaus skaičius — antras to paties brėžinio skaitymas palyginimui; jo reikšmės NEIMAME ir kiekių nekeičiame.

## Rezultatas (vietiniai demo)
H: 32 → 23 geltonos eilutės, iš jų 9 aukščio uždaro VIENAS paspaudimas (lieka 14 atskirų: perimetrai ir angos).
G: 20 (autoriaus 220 m² su mūsų 284,55 m² nesutampa — klausimas teisėtai lieka); 8 aukščio — vienas paspaudimas.
Naršyklėje: H 02 — 2,70 visoms 9 patalpoms → „jūsų", 07 (aukštis užrašytas prie patalpos) nepaliesta, „Sąmatoje
pasikeitė 11 eilučių" → „Atšaukti pataisymą" grąžino viską; H 06 apdailos eilutė — be geltonos, iškarpoje legenda.

## Ko nedarėme
- Masinio „priimti visus perimetro įverčius" — į kiekvieną jis turi pažiūrėti.
- Sienų dažymo plano skaitytuvo (žalios linijos): toks lapas — 1 iš ~27 tikrų rinkinių.
