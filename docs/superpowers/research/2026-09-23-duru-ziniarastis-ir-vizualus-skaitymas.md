# Durų žiniaraštis ir vizualus skaitymas — kas parašyta brėžiniuose ir kaip pasiekti 100 %

> 2026-09-23, steigėjo klausimas: „kiek durų su apvadais žiniaraštis rodo? patikrink durų žiniaraščio skaitymą.
> Ir tada pažiūrėk, kaip dar vizualią dalį būtų galima ištobulinti, kad viską perskaitytų 100 % tikslumu ir
> perduotų teisingą info matematikui."
>
> Metodas: visų šešių projektų (A, B, C, D, G, H) PDF perskaityti dviem būdais — teksto sluoksnis (pdfplumber,
> €0) ir lapai akimis (renderinti, be Vision) — ir sulyginta su tuo, ką variklis išsaugojo (`_door_types`,
> patalpų `elementai`) ir ką skaičiuoja (eilučių lentelė `eval_harness.py --rows --recompute --geometry`).
> Tik kiekiai, be €; jokių kliento ar dizainerių pavadinimų (D lape yra dizainerės kontaktai — jie niekur
> nekopijuojami). Niekas nederinta pagal jo sąmatą: iš pradžių perskaityta, kas parašyta brėžinyje, po to
> patikrinta, ar sutampa.

## 1. Atsakymas: ką durų žiniaraštis rodo kiekviename projekte

| Projektas | Kas brėžinyje parašyta apie durų tipą | Su apvadais | Jo sąmatos eilutė „beapvadinėms durims" |
|---|---|---|---|
| **D** (4 lapai) | Vienintelis projektas su tikru žiniaraščiu: „Vidinių angų (durų) žiniaraštis", 2 lapas. **D-1** 910×2100, dešininės, **beapvadinės**; **D-2** 910×2100, kairinės, **beapvadinės**, atvirkštinio varstymo. Pastaba: „Durų staktas ruošti beapvadinėms durims: lyginti, glaistyti, dažyti." | **0** | 10,22 m = 2 × (0,91 + 2 × 2,10) — tiksliai žiniaraštis |
| **A** (17 lapų) | Lentelės nėra. Pertvarų plane (2 lapas) dvi angos pažymėtos „Durų anga iki lubų, skirta beapvadinėms durims", viena — „Anga iki lubų, skirta stiklinei pertvarai su durimis", garažo — „Durų anga pagal konstruktyvą". Lubų plano LD-1/LD-2/LD-3 yra **užuolaidų nišų detalės**, ne durų žymės. | neužrašyta | 39,2 m ≈ 7 durys (5 paslėptos 900/700×2400 + 2 × 900×2100) — visos vidaus, be lauko/garažo |
| **B** (65 lapų, 23–65 vizualizacijos) | Nieko apie durų tipą; tik pastaba „18. Stumdomos durys". Elektros plane D1/D2/D4/D5 yra **šviestuvų grupių kodai**, ne durys. | neužrašyta | 55,52 m ≈ 11 durų iš 16 (be 3 stumdomų ir įėjimo) |
| **C** (3 lapai, rastras) | Nieko; abu san. mazgai „atskiras brėžinys" (nėra pakete). | neužrašyta | eilutės nėra (tik „Durų angos į rūbinę glaistymas dažymas 5 m") |
| **G** (16 lapų) | Lentelės nėra. Apdailos medžiagų lape (16) — durų **gaminiai**: „DECO-10 vidaus durys", „Ekofaneruotės vidaus durys LINE", „Dažytos vidaus durys LOFT" — trys įprastos durys su apvadais; beapvadinių niekur neminima. | visos (pagal gaminius) | eilutės nėra |
| **H** (8 lapai, visi) | **Nieko**: nei žiniaraščio, nei anotacijų, nei pastabų apie duris. Pertvarų plane vidaus durys pieštos be lankų, išdėstymo plane — su lankais. | neužrašyta | 40,94 m ≈ 8 durys ≈ visos vidaus durys (03↔06, 07, 09, 11; 09↔08, 10; 01↔03; 01↔02) |

Išvada: tik D turi žiniaraštį, ir jame **su apvadais durų nėra** — abi vidaus durys beapvadinės. Kituose
penkiuose brėžinys apie apvadus **nieko nesako**; jo praktika (A, B, D, H) — visos vidaus durys beapvadinės,
išskyrus lauko/garažo/terasos ir stumdomas; G — su apvadais (gaminiai), C — be tokios eilutės.

## 2. Skaitymo patikra: kas buvo ne taip

1. **`door_type_reader` žymių taisyklė** `\b(?:LD|D)-?\d\b` (be raidžių dydžio) A projekte laikė LD-1/2/3
   (užuolaidų nišų detalės) durų žymėmis — modulio aprašas net skelbė „door tags LD-1 ×7"; B — šviestuvų
   kodus D1/D2/D4/D5, dar dviejuose lapuose — mažąsias „d1…d4" iš teksto fragmentų. Skaitytuvas gavo ne tuos
   lapus.
2. **Rezultatas išsaugotas tik kaip vienas skaičius** (`count` = beapvadinių). Kiek durų su apvadais /
   stumdomų skaitytuvas matė (`standartines_count`, `doors` sąrašas) — išmesta. Į klausimą „kiek su apvadais"
   atsakyti nebuvo iš ko.
3. **Žalia be įrodymo**: kai skaitytuvas teksto nerado (`reader == 0`), o pirmasis Vision praėjimas plane
   pažymėjo paslėptas duris, `reconcile_frameless` grąžindavo `zalia` — G ir H beapvadinės „patvirtintos"
   brėžiniuose, kuriuose apie durų tipą nėra nė žodžio.
4. **Pirmojo praėjimo taisyklė** (`prompt.py`: „Paslėptos (beapvadinės): paprastas tarpas sienoje BE lanko")
   klasifikuoja tipą iš simbolio — būtent to, ko `door_type_reader` aprašas sako negalint padaryti. H
   pertvarų plane **visos** vidaus durys pieštos be lankų, D žiniaraščio beapvadinės D-1/D-2 — **su** lankais.
   Todėl H gavo 3 „paslėptas", iš kurių viena — 2,0 m anga tarp koridoriaus ir virtuvės (praėjimas), o D
   žiniaraščio dvi beapvadinės sąraše virto 1 paslėpta + 2 paprastos + 1 fantominė 700 mm.
5. **Durų skaičius per patalpą** (pirmasis praėjimas): D 01 — 3 vidaus durys, žiniaraštyje 2; H 03 — 7,
   sienose 4 durų angos ir 2 praėjimai; H 04 — „paslėptos durys" 2 000 mm.
6. **Lauko durys skaičiuotos kaip vidaus beapvadinės**: 2026-09-23 prielaida „visos vidaus durys
   beapvadinės" ėjo per įėjimo, garažo ir terasos duris, nes lauko požymį (`_exterior`) turėjo tik dalis
   elementų (Vision perskaičiavimo vėliava), o sienų angos „į lauką" nebuvo naudojamos.

Kartu: beapvadinių eilutė A +34 %, B +27 %, D +47 %, H +31 % (visur per daug), su žalia spalva.

## 3. Kas pataisyta (viskas €0, be Vision)

1. **Durų žiniaraščio skaitytuvas iš teksto** — `backend/extractor/door_schedule.py`,
   `scan_door_schedule(pdf)`: randa antraštę („Durų žiniaraštis", „Vidinių angų (durų) žiniaraštis", „Durų
   specifikacija"), iš žodžių padėčių parsiskaito eilutes (kodas, plotis, aukštis, tipas iš žodžių
   „beapvadinės / su apvadais / stumdomos / stiklinės", kiekis iš stulpelio arba iš žymės pasikartojimų
   plane), skaičiuoja anotacijas „skirta beapvadinėms durims", pastabas („visos vidaus durys beapvadinės",
   „staktas ruošti beapvadinėms"), durų gaminius apdailos lape. Visuose šešiuose: D — lentelė (2 beapvadinės,
   0 su apvadais), A — 2 anotacijos, G — gaminiai, B/C/H — nieko. Rezultatas `_duru_ziniarastis` su LT
   sakiniu, kurį mato žmogus.
2. **Įrodymų laiptai prielaidai** (`settle_frameless_default`): jo pasirinkimas → žiniaraštis → pastaba →
   anotacijos → gaminiai (→ su apvadais) → tik simboliai (→ beapvadinės, **patvirtinti**) → nieko (→ su
   apvadais). Šaltinis ir sakinys eina į eilutės `_assumption`; spalva žalia tik su jo pasirinkimu arba
   žiniaraščiu, kitaip geltona su priežastimi.
3. **Sąrašas suderinamas su žiniaraščiu** (`reconcile_doors_with_schedule`): kiekvienas žiniaraščio vienetas
   paima vienas vidaus duris (artimiausias plotis, be dydžio — bet kurias), joms duoda žiniaraščio dydį ir
   tipą; durys, kurių žiniaraštis neturi, — `_be_ziniarascio`, be angos eilutės. D: 15 m → **10,22 m**,
   centimetro tikslumu jo eilutė.
4. **Lauko durys** (`mark_exterior_doors`): sienų anga „į lauką", kurios nepaėmė langas tokio pločio →
   durys lauko; įėjimo patalpoje be sienų skaitymo — pirmos paprastos durys. Lauko durys niekada
   beapvadinės, visada angokraščiai. Kiekio elementas su keliais vienetais išskaidomas.
5. **Plotis > 1,3 m vidaus „durys" nėra beapvadinių stakta** („durys 1,40 pločio nebus tikrai"): H 2,0 m anga
   nebeskaičiuojama.
6. **Skaitytuvas**: žymių taisyklė `\b(?:D|VD|ID)-?\d{1,2}\b` (be LD, be mažųjų), žiniaraščio lapas
   pirmas, be teksto — geltona su priežastimi, `doors` sąrašas ir kitų tipų kiekiai saugomi.
7. **Klausimas Patikroje** „Vidaus durys — beapvadinės ar su apvadais?" — vienas visam projektui, tik kai
   tipas remiasi simboliais ar daline nuoroda (anotacijos, gaminiai); siūlomas atsakymas — su kuo skaičiuoja
   dabar, po juo įrodymo sakinys; atsakymas → `_overrides.vidaus_durys_beapvadines` per Prielaidų kelią,
   perskaičiuoja eilutę iš karto („su apvadais" — eilutė dingsta, ir simbolinės paslėptos durys taip pat).
   Žiniaraštis, pastaba ar jo pasirinkimas — klausimo nėra.
8. Žiniaraščio skaitymas įjungtas ir nemokamam perskaitymui (`free-reread`) ir demo scenarijui, kad seni
   projektai jį gautų be Vision.

**Išmatuota** (eilučių lentelė prieš → po):

| Eilutė | A | B | D | H |
|---|---|---|---|---|
| Beapvadinių durų angos, jo m | 39,2 | 55,52 | 10,22 | 40,94 |
| Mūsų prieš | 52,7 (+34 %) | 70,6 (+27 %) | 15,0 (+47 %) | 53,6 (+31 %) |
| Mūsų po | **42,6 (+9 %)** | 70,6 (+27 %) | **10,22 (0 %)** | **46,8 (+14 %)** |
| Angokraščiai po | 95,8 (+7 %) | 99,0 (+5 %) | 29,8 (−6 %) | 47,4 (−25 %) |

Korpusas: jo eilutės ±10 % 26,9 → 27,9 %, pagal € 36,3 → 37,3 %; D 36,0 → 38,0 % ir 60,3 → 61,4 %.
Likę skirtumai: B — be vektorinių sienų, todėl dubliuotų durų nėra kaip suporuoti ir lauko durys pagal
tambūrą tik viena; H — pirmasis praėjimas koridoriuje 03 surašė 7 duris, sienos rodo 4 durų angas ir 2
praėjimus, o durų pločiai iš Vision (600, 800, 900) su sienų angomis (0,89; 1,0; 1,37) nesutampa per 16 cm
toleranciją, todėl katilinės ir terasos durys liko „vidaus". Abu yra 4 skyriaus darbas, ne prielaidos.

## 4. Vizualus skaitymas: kur dar netikslu ir kaip pasiekti 100 %

Principas, kurį šie šeši projektai patvirtina: **kas parašyta tekstu ar nubrėžta vektoriais, skaitoma be
modelio; Vision klasifikuoja tik tai, kas iš tikrųjų nupiešta, po vieną faktą, su iškarpa; kas neparašyta —
klausiama, ne spėjama.** Faktų žemėlapis pagal tai, iš kur dabar ateina skaičius ir kur klysta:

| Faktas | Dabar | Klaidos šiame korpuse | Kelias į 100 % |
|---|---|---|---|
| Patalpų plotai, numeriai | tekstas (eksplikacija, plano užrašai) | — | padaryta (2026-09-05/19) |
| Perimetrai, kontūrai | vektorinės sienos + matmenų eilutės | B be numerių plane; C rastras | padaryta; rastrui — tik žmogus |
| Lubų aukštis | tekstas (pjūviai, žymos) | — | padaryta |
| **Durų skaičius per patalpą** | Vision iš plano | D 01: 3 vs 2; H 03: 7 vs 4 durys + 2 praėjimai; H 04: 2,0 m „durys" | sienų angos yra tikslus sąrašas (plotis, kaimynas, laukas): durų skaičius = angos į kitą patalpą, kurių plotis 0,6–1,2 m; Vision — tik klausimui „ar šioje angoje nupieštos durys / stumdomos / nieko" iš tos angos iškarpos; pločiai iš sienų, ne iš Vision |
| **Durų tipas (beapvadinės)** | simbolis (lankas / be lanko) | H be lankų visos, D beapvadinės su lankais | tik tekstas (žiniaraštis, anotacija, pastaba, gaminiai) arba klausimas — padaryta |
| **Lauko / vidaus durys** | Vision vėliava daliai | H terasos, garažo durys vidaus | sienų anga „į lauką" — padaryta, kai pločiai sutampa; toliau — pločiai iš sienų |
| Langai (skaičius, dydis) | Vision + standartas | H nedydinti → angokraščiai −25 % | sienų angos į lauką, kurių nepaėmė durys, yra langai; dydis — iš fasado/išklotinės teksto, ne standartas |
| Apdaila (dažoma / plytelės) | apdailos planas, išklotinės, paskirtis | plytelių juosta: G +19 %, D +46 % | išklotinių m² (jo sustabdyta `_detail_m2` pora) |
| Grindų danga | grindų planas (tekstas + spalva) | G „dvi dangos" | padaryta 2026-09-20 |
| LED nišos | Vision iš lubų plano | visur −8 % | lubų plane nišos yra vektorinės linijos (raudonos) — ilgis iš vektorių, ne iš vaizdo |
| Šviestuvai, difuzoriai, santechnika | Vision skaičiavimas + legenda | H 35 vs 20, 10 vs 7, 3 vs 2 | vektoriniuose PDF simbolis yra pasikartojanti kelių grupė: legenda apibrėžia glifą, instancijos suskaičiuojamos be modelio; Vision — tik rastrui |
| Karnizas | legenda (tekstas) | — | padaryta |

**Ką daryti pirmiausia** (pagal pinigus ir pagal tai, kiek jau yra pusiau padaryta):

1. **Angos iš sienų, ne iš Vision.** Sienų angų sąrašas jau yra kiekvienai apibrėžtai patalpai
   (`_angos_sienose`: plotis, kaimynas, „laukas"). Jis turi tapti PIRMINIU durų ir langų sąrašu:
   durys = angos į patalpą (0,6–1,2 m), langai = angos į lauką be durų požymio, pločiai — iš sienų. Vision
   lieka vienam klausimui per angą iš jos iškarpos (varstomos / stumdomos / tuščia / langas), o žmogus mato
   tą pačią iškarpą Patikroje. Tai vienu ypu pašalina fantomines duris (D 700, H praėjimai), dvigubą
   surašymą, 1,4/2,0 m „duris", lauko/vidaus painiavą. H likusią +14 % ir B +27 % (kai B gaus kontūrus)
   tai ir uždaro.
2. **Skaitymo lentelė** (ne eilučių): kiekvienam projektui kartą žmogus užrašo, kas brėžinyje parašyta
   (durys per patalpą, tipas, langai, aukščiai, dangos) — šis dokumentas jau duoda durų faktus D ir H —
   ir kiekvienas skaitytuvo pakeitimas gina prieš ją. Eilučių lentelė matuoja sąmatą, ši — skaitymą; be
   jos „100 %" lieka žodžiu.
3. **Vektoriniai simboliai** (šviestuvai, difuzoriai, LED): H, G, A yra vektoriniai — legendos glifas
   yra kelių grupė, jos kopijos plane suskaičiuojamos deterministiškai. Vision lieka rastrui (B nuo 23 lapo,
   C).
4. **Pirmojo praėjimo instrukcija**: išimti durų tipo klasifikavimą iš simbolio (513 eilutė), palikti
   skaičių ir dydį, kol 1 punktas ją pakeis.

## 5. Kas liko jo sprendimu

- Kai brėžinys apie apvadus nesako (B, C, H) — atsakyti klausimą Patikroje; siūlymas: beapvadinės, kai
  plane matyti paslėptų durų simbolis, kitaip su apvadais.
- Stumdomos durys (B pastaba 18): jo eilutė jų neįtraukia — taip ir skaičiuojame (žiniaraščio tipas
  „stumdomos" — be angos eilutės).
- Lauko durų angokraščiai — dabar visada; A dėl to +7 % (buvo −4 %).
