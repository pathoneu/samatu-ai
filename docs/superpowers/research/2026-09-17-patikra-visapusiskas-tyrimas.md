# Patikra: kodėl ji nesutaupo darbo, ir ką daryti (visapusiškas tyrimas, 2026-09-17)

> **Kontekstas.** 2026-09-17 rytą įkurta produkcijoje objektą H (8 A4 lapai, 11 patalpų, dizainerių
> planas su eksplikacija) ir tris valandas eita per Patikrą. Verdiktas: „vos ne gaunasi, kad žmogus
> pats skaičiuoja ir žiūri vis tiek — nuima labai mažai rankinio darbo". Šis dokumentas: (1) kas
> tiksliai išmatuota tame paleidime, (2) kaip tą patį daro Togal, Kreo ir visa rinka, (3) kaip veikia
> peržiūros sąsajos, kurios tikrai greitesnės už rankinį darbą, (4) ką AI gali brėžiniams šiandien,
> (5) diagnozė ir kryptis su planu. Tyrimas €0: jokių mokamų paleidimų, tik lokalūs bandymai ant to
> paties H brėžinio ir keturi interneto tyrimai (šaltiniai gale).

## 1. Santrauka

Patikra šiandien neveikia kaip patikra dėl vienos struktūrinės priežasties: **geometrija, kurią ji
rodo tikrinti, nėra išmatuota**. H projekte visų 11 patalpų perimetrai yra kvadrato įvertis iš ploto
(`P ≈ 4·√plotas`), o „kontūrai" — stačiakampiai, sintetinti iš grubaus Vision langelio. Žmogus mato
neteisingą skaičių, neteisingą rėmelį ir neįskaitomą iškarpą, todėl eina matuoti pats. Jokia
sąsaja to neišgelbės, kol skaičius nėra iš brėžinio.

Antra priežastis — pati peržiūros forma: šeši faktai patalpai, patalpa po patalpos, kiekvienas su
mygtukais „Teisinga / Pataisyti", be matomos pataisymo pasekmės, be „pataisyta" būsenos, be
galimybės taisyti ant brėžinio. Lyderiai (Togal, Kreo, STACK, Buildxact) tai daro atvirkščiai:
viskas ant brėžinio, spalvoti kontūrai, taisymas tempiant viršūnes, sąrašas šone sinchronizuotas
su brėžiniu. Peržiūros tyrimai (dokumentų AI, radiologija, žymėjimo įrankiai) sako tą patį: greitis
ateina iš šaltinio šalia reikšmės, iš išimčių (ne visko) tikrinimo, iš vieno klavišo ir iš iš karto
matomos pasekmės.

Gera žinia: mūsų pačių brėžiniai leidžia geometriją **išskaičiuoti**, ne nuspėti. H lapo vektoriuose
sienos yra atskiros užpildytos figūros, matmenų eilučių 111, mastelis iš jų 1:115. Grubus 20 min
prototipas (sienų sąjunga → laisvos erdvės „veidai" → sutapatinimas su lentelės plotais) davė
3 iš 11 patalpų ±5 % ir 7 iš 11 ±11 % per mažiau nei sekundę, be Vision. Tai inžinerijos, ne
stebuklo klausimas. Kreo per tris versijas pasiekė 94 % kontūrų tikslumą tuo pačiu keliu.

**Siūloma kryptis:** (A) geometrija iš vektorių ir matmenų (perimetrai matuojami, ne spėjami),
(B) Patikra perkeliama į tikrą peržiūros langą su kontūrais ant brėžinio ir taisymu ant jo,
(C) šią savaitę — penki pigūs pataisymai, kurie sumažina skausmą jau dabar. Detalės 6 skyriuje.

## 2. Ką tiksliai parodė H paleidimas (išmatuota lokaliai ant to paties brėžinio)

| kas | būsena H projekte | pasekmė žmogui |
|---|---|---|
| Plotai | iš eksplikacijos lentelės, 11/11, tikslūs | gerai |
| Perimetrai | **11/11 sintetiniai** (`_perimetras_floor_applied`, P≈4·√A): 01 8,60 / 03 koridorius 16,40 / 04 virtuvė 21,00 / 05 svetainė 25,00 … | koridoriuje ir L formos patalpose klaida 15–30 %; jis tai pamatė |
| Kontūrai | **11/11 `synthesized_from_bbox`** — Vision langelis 0,01 tikslumu, dažnai nuslinkęs (06 uždengia kitą patalpą, 03 persidengia) | „nematau pažymėjimų", „sunkiai matosi, kas pažymėta" |
| Rastro užpildymas (`detect-room-polygons`) | 4/11 auto, visi 4 — fragmentai (0,45–2,99 m² vietoj 2,7–15,9 m²), 7 „manual_needed" | baldai ir brūkšniavimas kerta patalpas |
| Sienų kontūrų juosta (`wall_outline`) | 0/11: sėja nuo **ploto užrašo patalpoje**, o H plotai tik lentelėje; sėjant nuo numerių ženkliukų vis tiek 0/11 (pildymas nuteka į baldų kišenes) | juosta, kuri ant G išsprendė 7/9, čia tyli |
| Matmenų eilutės (`plan_dimensions`) | 111 eilučių, 109 su linija, mastelis 1:115 — bet 0/11 porų: ieško dviejų sienų, kurių sandauga = plotas; patalpos ne stačiakampės, matmenys segmentais | mastelis žinomas, perimetrai vis tiek nespėti |
| Įrodymų iškarpos | visas lapas 110 dpi (padidinus 160 dpi): A4 lapas 909×1286 px, patalpa 20 % pločio = **182–264 px** | „blurry" — tas pats regionas 400 dpi yra visiškai ryškus (matmenys 1189, 397, 900 įskaitomi) |
| Grindų faktas | **neskaitomas iš brėžinio**: parenkamas pagal patalpos paskirtį (`ROOM_TYPE_RULES`), todėl „Pataisyti" keičia paskirtį, ne dangą | „gali pasirinkti kitą patalpą, bet ne iš tikro taisyti kokios grindys" |
| Apdailos faktas | „Sienos: dažoma 90 %, plytelės 10 %" — dalys, ne m² ir ne aukštis | „kai kur rašo procentais" |
| Pataisymo pasekmė | po „Įrašyti" pasikeičia juosta viršuje ir eilutės, bet niekas nepasako, kas ir kiek pasikeitė | „sunku suprasti, ar kažką pataisiau" |
| Aukščiai | 11/11 iš pjūvio vidurkio 2,82 m | klausimas kiekvienoje patalpoje, nors atsakymas vienas |
| Laikas | H 14 min, G 34 min (23 / 23 Vision užklausų; priartinimo žingsnis 90 s, 9 bandymai, 0 pritaikyta) | laukimas be naudos |

Vektorinis sluoksnis, kurio šiandien nenaudojame patalpoms: 1 lapas = 156 stačiakampiai, 2333
linijos, 3506 kreivės; **sienos = 176 užpildytos figūros vienos spalvos (0,91 pilka)**, baldai ir
matmenys — tik linijos. Tai reiškia, kad sienų tinklas gaunamas tiesiai iš PDF be jokio rastro.

Prototipas (shapely, be jokio derinimo): sienų sąjunga → durų angos uždaromos buferiu → laisvos
erdvės veidai → veidas su vienu patalpos numerio ženkliuku ir plotu arti lentelės:

| patalpa | lentelė m² | veidas m² | skirtumas | perimetras iš veido |
|---|---:|---:|---:|---:|
| 02 Katilinė | 6,90 | 7,15 | +4 % | 12,21 m |
| 06 Vaiko | 15,29 | 14,31 | −6 % | 16,70 m |
| 08 Vonia 2 | 4,32 | 4,79 | +11 % | 8,75 m |
| 09 Miegamasis | 16,84 | 17,66 | +5 % | 20,36 m |
| 10 Drabužinė | 2,72 | 2,66 | −2 % | 7,07 m |
| 11 Darbo | 15,89 | 14,93 | −6 % | 16,87 m |
| 04+05 virtuvė+svetainė | 61,81 | vienas veidas su dviem ženkliukais | atviras planas, reikia dalijimo | |
| 01, 03, 07 | | nerasta / nuteka | durų angų uždarymas per grubus | |

Palyginimui dabartinis 09 perimetras 16,50 m (kvadratas) prieš 20,36 m iš tikro kontūro — 23 %
skirtumas sienų plote. Tai ir yra jo „perimetras kai kur labai neteisingas".

## 3. Kaip tai daro lyderiai (tyrimo agentų ataskaitos, šaltiniai 8 skyriuje)

**Togal.AI** — vienas mygtukas, 10–15 s, ant lapo atsiranda spalvoti plotai (Net Area = apdailos
plotas nuo sienų paviršių, Gross Area nuo ašių, Footprint, Doors Area), sienų linijos (ašis,
perimetras išilgai paviršių, durų ašys) ir skaičiavimai. Kiekiai dešinėje sinchronizuoti su brėžiniu:
paspaudi eilutę — pašviečia kontūras, ir atvirkščiai. Taisymas: tempti viršūnę, dvigubas klikas ją
šalina, S/M/C skaido/jungia/atima, dešinys klikas perpriskiria klasę, Ctrl+Z. Pasitikėjimo rodiklio
per elementą nėra; pakeitimo pasekmių žurnalo nėra. Mastelį OCR randa, bet „netikrina teisingumo".
Tik architektūriniai aukštų planai; rastrai — be pritraukimo. $299/mėn už vartotoją. Kanzaso
universiteto tyrimas: 76 % greičiau nei On-Screen Takeoff, skirtumas ±5 %, bet „praleidžia
iškyšas, painioja anotacijas". Vartotojai: „kartais pagauna daugiau, nei reikia — perdirbimas",
„85 % tikslumo gyvenamuose aukštuose, 60 % prekybos podiume".

**Kreo** — Auto Measure per kategoriją (patalpos, durys/langai, sienų apdaila, sienos, GIA/NIA,
laisvas tekstinis užklausimas, objektai), matoma „kur AI dirba" ir kiek sekundžių liko; prieš sukūrimą
— pasitikėjimo slankiklis ir „Fix with AI". **AM 3.0 (2026-08-28): kontūrų tikslumas 72 → 94 %,
plotas 92,6 → 99,3 %**, matuota prieš žymėtą tiesą; antras praėjimas „priderina kontūrą prie
brėžinio linijų". Patalpų vardai iš PDF teksto (tik vektoriniuose). Taisymas: tempti taškus, klikas
prideda tašką, Merge/Subtract/Knife, 25 undo. Lentelės iš brėžinio eksportuojamos į skaičiuoklę,
bet **su geometrija nesutikrinamos**. Aukštis — savybė grupei, ne faktas. $35/70/175, AI tik Pro.
Skundai: „auto measure gali būti netvarkingas, tiek pat laiko tvarkau duomenis", „labai priklauso nuo
brėžinių", skenuoti — blogai.

**Visa rinka** (STACK, Bluebeam, Autodesk, PlanSwift, ConstructConnect, Countfire, Beam, Cubit,
Buildxact, Trimble, Bobyard, Handoff…): AI yra arba vieno simbolio paieška, arba „pirmas praėjimas"
per vieną lapą. Peržiūros sąsaja susivienodino: **žymekliai ant lapo + sąrašas šone, kurį spaudi ir
pašoki į vietą + varnelės prieš patvirtinant + praleistus pridedi įprastu įrankiu**. Nė vienas
senbuvis nerodo pasitikėjimo per elementą; tai daro tik 2024–26 naujokai (Bobyard, Quotr,
Drawer.ai). Patys gamintojai liepia tikrinti („trust but verify", „critical that you verify Scale").
Dažniausias skundas — simbolių paieška lūžta ant užimtų/skenuotų/pasuktų brėžinių ir skaičiuoji
iš naujo. Kainos nuo $39/mėn iki $1 250–3 000 už vietą metams.

**Ko niekas nedaro** — mūsų vieta: patalpų/apdailos/durų žiniaraščių skaitymas (tik Bobyard nuo
2026-06 ir Kamai), plytelių aukštis, grindjuostės minus durys, angokraščiai, lubų aukštis per
patalpą, matomos ir keičiamos prielaidos, vietiniai standartai. Išklotinės, pjūviai, fasadai —
aiškiai nepalaikomi. Mažam apdailininkui reikia: kainos iki ~$150–300/mėn, skaičių, kurie „niekada
nėra absurdiški", tikrinimo greitesnio už skaičiavimą ranka, sąžiningumo dėl prastų PDF, jo
struktūros (patalpa po patalpos, jo eilutės), jokio persimokymo.

## 4. Kaip veikia peržiūra, kuri greitesnė už rankinį darbą (dokumentų AI, radiologija, žymėjimo įrankiai)

Dvylika išmatuotų dėsningumų ir kaip jie atrodo mūsų patalpos lape:

1. **Šaltinis šalia reikšmės.** Patikra kainuoja tiek, kiek kainuoja patikrinti, ne paaiškinti
   (Fok & Weld); citatos prie langelio pagreitina 20 % (MIT SymGen). Mums: kiekvienas faktas su
   **įskaitoma** iškarpa ir sakiniu „Aukštis 2,70 m — pjūvis A-A, 4 psl."; kas nepažymėta, tas
   nepatikrinama ir turi būti pažiūrėta.
2. **Automatinis priėmimas pagal pasitikėjimą + abejonių eilė pagal pinigus.** Rossum eksportuoja tik
   virš slenksčio, likusius į peržiūrą; slenksčiai kalibruojami ant savų duomenų. Mums: eilė =
   abejonė × (kiekis × kaina); didžiausios patalpos dažomas plotas pirmas, WC durys 0,4 m² paskutinės.
3. **Vienas klavišas = priimti ir kitas.** Rossum Enter šoka tik į laukus, kuriems reikia žmogaus;
   Encord n/b; Prodigy „skristi per įvestis". Mums: Enter = „Teisinga, kitas"; skaičių įvedimas
   perrašo; Esc = „nežinau, palikti".
4. **Pataisymas iš karto rodo pasekmę.** Mažinant „patikros vykdant" kainą mažėja ir per didelis, ir
   per mažas pasitikėjimas AI (Ferdowsi). Mums: aukštis 2,70→3,10 → „dažomas plotas +14,2 m²,
   glaistas +1 maišas" ir perbėgę sveiko proto tikrinimai.
5. **Matoma „pataisyta jūsų" būsena su undo.** Encord spalvina, Rossum pilka varnelė; undo įvykiai
   atskleidžia >90 % rimtų problemų (Akers). Mums: ženkliukas, originali reikšmė užvedus, Ctrl+Z;
   šitos eilutės ir yra tai, ką renka `build_ground_truth.py`.
6. **Grupinis patvirtinimas vienodų dalykų.** ABBYY grupinė patikra: Enter patvirtina grupę, Space
   atideda vieną. Mums: „6 durys 800×2000 — patvirtinti visas" su šešiomis iškarpomis šalia.
7. **Progresas iš anksto.** Lėtai startuojanti juosta padvigubina metimą (Conrad). Mums: automatiškai
   priimti dalykai skaitomi atliktais nuo pat pradžios: „liko 4 iš 23 · ~3 min".
8. **Tiesioginis taisymas ant šaltinio.** Priimti/atmesti iš anksto nubrėžtą greičiau 14–21 % nei
   brėžti (Lingren). Mums: klikas ant sienos keičia plytelės/dažai, klikas ant durų — tipą, viršūnės
   tempiamos; skaitinis laukas lieka.
9. **Jokių nuogų procentų, jokių mišrių vienetų.** Natūralūs dažniai patrigubina teisingas išvadas
   (Gigerenzer). Mums: „plane 24,3 m², eksplikacijoje 25,1 m²", vienetas prie kiekvieno skaičiaus,
   „iki 3 m / virš 3 m" žodžiais.
10. **Ko nerado — tuščias laukas su priežastimi**, ne spėjimas, kuris atrodo kaip duomuo (Bondi:
    didžiausias tikslumo prieaugis, kai sistema pasako, kad atsisako). Mums: „Aukštis: — (pjūvyje
    nerasta; įveskite arba priimkite 2,70 m)".
11. **Tik išimtys + atsitiktinis auditas.** Automatizavimo šališkumas priverčia ekspertus praleisti
    patikimos automatikos tikrinimą (Parasuraman). Mums: rodomi tik abejotini faktai plius
    atsitiktiniai 10 % gerų, be žymės; matuojamas klaidingo priėmimo dažnis.
12. **Vieno tipo fakto stulpelis per visas patalpas.** ABBYY „analogiški laukai", Prodigy „viena
    sąvoka per praėjimą". Mums: „Aukštis" stulpelis per 11 patalpų — vienas 2,50 tarp 2,70 iškart
    matosi; eiti per faktų tipus, ne patalpa po patalpos.

Antidėsningumai, kurie daro peržiūrą lėtesnę už rankinį darbą — ir visi jie yra mūsų Patikroje
šiandien: tikrinti viską; rodyti prastus spėjimus kaip reikšmes; mažos iškarpos be konteksto;
paslėpti būsenos pokyčiai po pataisymo; kelių žingsnių pataisymas; tik nuogas pasitikėjimo procentas.

## 5. Ką gali AI brėžiniams šiandien (tyrimo agentas + mūsų matavimai)

**Skaičiai iš 2026 m. tyrimų.** Vision LLM gerai skaito **tekstą** (0,70–0,95), bet blogai
**skaičiuoja simbolius**: ant 120 planų geriausias modelis (Gemini 3 Pro) duris tiksliai suskaičiuoja
39 %, langus 34 % atvejų; Claude Opus 4.5 — 16 % / 16 % (AECV-Bench, 2026-01). Patalpų sąvokos su
užrašais (miegamieji, tualetai) — 82–91 %. Ploto klaidos **>70 % kyla iš mastelio**, ne iš patalpų
žymėjimo (15 planų mikrotestas: Fable 5 6,5 %, Opus 4.8 13,2 %, GPT-5.5 23,2 % vidutinė klaida).
Raiškos lubos: Claude sumažina vaizdą iki 1568–2576 px ilgosios kraštinės, tad A3 lape 2 mm
matmenų tekstas tampa 7–12 px — todėl mūsų 110 dpi iškarpos neįskaitomos ir modeliui, ir žmogui.

**Kas išmatuotai padeda:** priartinimo kilpa (+7,5…+14,9 punkto dokumentų testuose; kelių žingsnių
zoom agentas +12,7); **vektorių pateikimas kartu su paveikslu** (patalpų skaičiavimas 0,75 → 0,96);
detektorius + LLM patikra (+2…+14 punktų). Vienintelė publikuota sistema, pralenkusi žmones
(Handoff-H1: 81,6 % prieš 77,6 %), yra CV primityvai + įrankius naudojantys agentai, ne grynas VLM;
geriausias grynas agentas (Fable 5) — 61,4 %. Griežtos JSON schemos degraduoja samprotavimą —
schemos turi būti siauros.

**Specializuoti modeliai:** raster→vector (Raster2Seq, svoriai vieši) 88,7 F1 ant švarių planų, bet
73,9 % IoU ant „laukinių"; VectorFloorSeg (vektorinė segmentacija) +4–5 mIoU ir **+25 punktų
patalpų vientisumo** prieš rastro tinklus ant tų pačių duomenų. Durų/langų detektoriai (YOLO) 0,82
mAP ant tikrų skenuotų. RoomFormer/PolyRoom/FloorSAM — taškų debesims, netinka brėžiniams.

**Nepriklausomi tikslumo matavimai:** Togal prieš rangovo 29 eilučių apdailos takeoff'ą: grindys
−1…−8 %, lubos −3…−11 %, statistiškai reikšmingas **nuvertinimas** (p = 0,027); KU tyrimas: ~70 %
laiko sutaupymas ±5 % ribose po rankinių pataisymų. Nepriklausomo „laiko iki patikrinto" skaičiaus
nėra niekur.

**Mūsų pačių matavimai (šiandien, €0):** `wall_outline` ant G 7/9 ±5 %; ant H 0/11 (sėja nuo ploto
užrašo, kurio nėra); rastro užpildymas ant H 4/11 fragmentai; vektorinis prototipas ant H 7/11 ±11 %
per <1 s; matmenų eilutės 109/111 su linija, mastelis 1:115; eksplikacija 11/11 per 5,5 s.

**Agento rekomendacija Pathon'ui (sutampa su mūsų išvada):** (1) vektorinės patalpos iš PDF kelių,
prie jų pritraukti Vision/užpildymo kontūrus, Raster2Seq tik suplotiems rastrams; (2) matmenų
eilutės kaip **kietas apribojimas** (kraštinė nesutampa >2 % — atmesti) ir mastelis iš ≥3 eilučių;
(3) ≥300 dpi iškarpų kilpa vizualiems skaitymams; (4) mažas durų/langų detektorius (+VLM patikra)
vietoj viso lapo VLM; (5) aiški matavimo konvencija (vidinis apdailos paviršius, NRM2 angų slenkstis
— pastaba: agentas nurodo, kad apdailai slenkstis gali būti 1,00 m², ne 0,50; patikrinti NRM2 §28).

## 6. Diagnozė ir kryptis

**Kodėl Patikra nesutaupo darbo (priežastys pagal svorį):**

1. Perimetrai ir kontūrai nėra išmatuoti → žmogus matuoja pats. (Tikslumas.)
2. Iškarpa neįskaitoma, žymėjimas neaiškus → žmogus atsidaro savo PDF. (Įrodymai.)
3. Pataisymas nematomas, būsena neaiški, taisyti galima ne tai (grindys → paskirtis) → žmogus
   nepasitiki, kad kas nors pasikeitė. (Sąsaja.)
4. Patalpa po patalpos, visi faktai, visi vienodi → žmogus tikrina viską, įskaitant 11 vienodų
   aukščių. (Peržiūros forma.)

**Kryptis (trys sluoksniai, ta pačia eile):**

**A. Geometrija iš brėžinio, ne spėjimas (1–2 savaitės, €0, matuojama ant G/H/A–D).**
- Sienos iš vektorių: užpildyti sienų poligonai (spalva/storis) → sienų tinklas; durų angos
  uždaromos išilgai sienų (ne buferiu); patalpos = laisvos erdvės veidai; sutapatinimas su
  eksplikacijos plotu ±5 % ir su patalpos numerio ženkliuku; atviras planas dalijamas pagal
  ženkliukus ir lentelės plotų santykį. Kur vektorių nėra — esama `wall_outline` rastro juosta,
  sėjama nuo ženkliuko, ne tik nuo ploto užrašo.
- Mastelis iš matmenų eilučių (jau veikia) → perimetras = kontūro ilgis; matmenų eilutės tampa
  **patikrinimu** (sienos ilgis sutampa su eilute ±2 %), ne vieninteliu šaltiniu.
- Kvadrato įvertis lieka tik kaip paskutinis kelias ir **rodomas kaip tuščias laukas su priežastimi**,
  ne kaip skaičius.
- Grindys ir sienų apdaila skaitomos iš grindų plano legendos ir apdailos lentelės (juostos yra:
  `_floor_anchors`, apdailos skaitytuvas), o ne iš paskirties; paskirtis lieka tik atsarginiu keliu.
- Vertinimas: G/H patalpų kontūrai ±5 %, perimetrai prieš matmenų eilutes, eilučių ±10 % dalis.

**B. Patikra v2: peržiūra ant brėžinio (2–3 savaitės po A).**
- Vienas ekranas: kairėje tikras peržiūros langas (EmbedPDF, ryškus bet kokiu masteliu) su patalpų
  kontūrais, durimis, langais, apdailos zonomis; dešinėje faktų sąrašas, sinchronizuotas su brėžiniu
  (kaip Togal/Kreo). Ne rastro iškarpos.
- Taisymas ant brėžinio: tempti viršūnę, klikas ant durų keičia tipą/dydį, klikas ant sienos
  keičia dažai/plytelės; skaitinis laukas lieka.
- Faktų tipų stulpeliai per visas patalpas (aukštis, perimetras, grindys…), Enter = priimti ir kitas,
  automatinis priėmimas patikimų su atsitiktiniu 10 % auditu, eilė pagal pinigus.
- Kiekvienas pataisymas rodo skirtumą („sienos +6,6 m², glaistas +1 maišas"), gauna ženkliuką
  „jūsų", turi undo; nerasta = tuščia su priežastimi.

**C. Šią savaitę, nelaukiant A ir B (2–3 dienos):**
1. Iškarpos ryškios: rendinti tik regioną 300–400 dpi (`pdftoppm -x -y -W -H`), ne visą lapą 110.
2. Grindų faktas: tiesioginis dangos pasirinkimas (parketas / laminatas / plytelės / PVC /
   betonas / kita) su pasekme grindjuostėms; paskirtis atskirai.
3. Apdailos faktas be procentų: m² ir aukštis („plytelės iki 2,1 m ant 2 sienų, 9,4 m²; likusi
   dalis dažoma 38,2 m²").
4. Po kiekvieno „Įrašyti" — skirtumo juosta ir ženkliukas „pataisyta jūsų"; undo.
5. Kai perimetras sintetinis — nerodyti jo kaip fakto: „Perimetras: — (brėžinyje nesuporuota;
   įveskite arba priimkite kvadrato įvertį 16,4 m)".
6. Priartinimo žingsnis, kuris 90 s nieko nepritaiko — išjungti, kol neįrodyta nauda.

**Ką matuoti pilote (iš 4 skyriaus):** sekundės vienam faktui; priimta / pataisyta / atmesta pagal
fakto tipą; € sugauta per peržiūros minutę; undo skaičius; laikas iki paruoštos sąmatos su AI ir
be (tas pats žmogus, du projektai).

**Sprendimai tau:** (1) ar einam A→B→C eile, ar C pirmiau (mano siūlymas: C tuoj pat, A iškart po
to, B tik kai A duoda ±5 % ant G ir H); (2) ar leidžiam Codex auditą ($250–300) po A, kai bus ką
audituoti; (3) ar H ir G lieka vieninteliai matavimo objektai, ar duodi dar du projektus be sąmatų
(vien geometrijai tikrinti).

## 7. Ko nedarom

- Nemokom variklio iš tavo sąmatų — visos aukščiau siūlomos juostos skaito brėžinį.
- Nepirksim CV modelių treniravimo — vektoriai + švarus rastras + lentelės duoda daugiau už mokymą
  (2026-05 ir 2026-09-13 tyrimai; Kreo tai pasiekė su antru „priderinimo" praėjimu, ne su nauju
  modeliu).
- Nerodysim pasitikėjimo procentų kaip pagrindinio signalo — įrodymas prie kiekvieno skaičiaus lieka.

## 8. Šaltiniai

Tyrimo agentų ataskaitos su nuorodomis (pilnos, anglų k.) saugomos šalia:
`2026-09-17-tyrimas-togal-kreo.md`, `2026-09-17-tyrimas-rinka.md`, `2026-09-17-tyrimas-perziuros-ux.md`,
`2026-09-17-tyrimas-ai-galimybes.md`. Vidiniai: `2026-09-13-room-geometry-precision.md`,
`2026-09-04-two-minute-fix-ux.md`, `2026-09-13-council-transcript-product-review.md`.
