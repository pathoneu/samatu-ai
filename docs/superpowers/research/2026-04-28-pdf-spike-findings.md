# PDF Spike — pdfplumber/PyMuPDF on training-data PDFs

**Data:** 2026-04-28. Vykdytas po Sprint B (deterministic refactor) užbaigimo.
**Tikslas:** įvertinti ar Sprint A (architektūrinis pivot'as į pdfplumber)
yra realus accuracy + cost win'as, naudojantis vartotojo realiais
testavimo PDF'ais.

## Methodology

Paleidau `pdfplumber.extract_text()` + `pdfplumber.extract_tables()` +
`pymupdf.get_drawings()` per 4 testavimo projektus. Jokio Vision API
call'o. Visi rezultatai deterministiniai — pakartotinis run'as duos
identišką output'ą.

## Per-projekto rezultatai

| Projektas | Psl. | Tekstas (KB) | Kambariai aptikti | m² values | Vector linijos | Verdiktas |
|---|---|---|---|---|---|---|
| **P1** (`projektas_1_breziniai.pdf`) | 65 | 60 | **12** ✓ | 154 (regex) | 2.4M ✓ | CAD-export, bet eksplikacija ne table-struktūruota |
| **P3** (`projektas_3_breziniai.pdf`) | 45 | 63 | **14** ✓ | 2 (regex) | 223k | **Eksplikacija PILNAI ekstraktinama per `extract_tables()`** |
| **P4(1)** | 2 | 12 | 0 | 0 | 81k | Raster scan / fragmentas |
| **P5(2)** | 1 | 0 | 0 | 0 | 110 | Raster scan |

## Konkretūs faktai

### P3 eksplikacija — sėkmės pavyzdys
`extract_tables()` ant 5-to puslapio grąžino:
```
1 HOLAS         11.55 m²
2 KATILINĖ       5.9 m²
3 KORIDORIUS    12.05 m²
4 SAN. MAZGAS    4.1 m²
5 KAMBARYS      15.4 m²
6 SANDĖLIUKAS    5.76 m²
7 KAMBARYS      12.32 m²
8 VIRTUVĖ       24.03 m²
9 VALGOMASIS    11.18 m²
10 SVETAINĖ     32.44 m²
11 GARAŽAS      35.94 m²
TOTAL          170.67 m²
```
**Visi decimal'ai pilni.** `5.76` ne `5.8`, `12.05` ne `12`. Jokio Vision
call'o. Determinizmas 100%. **Šis projektas Sprint A architektūroje
vartotų $0 Vision'ui room area extraction'ui** vs dabartiniai ~$5/65psl.

### P1 — daliniai duomenys
- Vector geometrija plentyfull (2.4M linijų) — sienų perimetrai
  galimai išvedami deterministiškai iš poligono geometrijos
- Eksplikacija egzistuoja tekste, bet **NE kaip clean table grid**.
  Tekstas išskaidytas su vector lines kaip rėmas, ne kaip table cell'ai.
  `extract_tables()` grąžina title block, ne eksplikaciją.
- Reikalautų **coordinate-cluster fallback'o**: paimti visus tekstus
  su jų (x, y) koordinatėmis, klasterizuoti į eilutes ir stulpelius.
  Tai sudėtinga, bet įmanoma.

### P4, P5 — raster scans (arba fragmentai)
Pdfplumber niekas negauna. Vision OCR yra vienintelis kelias.
**Pastaba:** šie failai galimai yra daliniai/fragmentai —
visas projektas turi multiple PDFs (`(1)`, `(2)`, ..., `(8)`).
Pilna projekto kolekcija galimai turi clean PDF'ų irgi.

## Verdiktas Sprint A architektūriniam pivot'ui

**Atitinkamai vartotojo intuicijos:** „nera labai profesionalus dokumentai,
kai kurie geresni kai kuries blogesni" ✓ patvirtinta faktais.

| Senario | % sample | Sprint A vertė |
|---|---|---|
| CAD-export su clean eksplikacija (P3-style) | ~25% | **DIDELĖ** — pdfplumber gauna primityvus deterministiniu būdu, $0 cost |
| CAD-export be clean table'o (P1-style) | ~25% | **VIDUTINĖ** — vector geometry naudinga, bet eksplikacijos extraction'ui reikia coordinate-clustering |
| Raster / scan fragmentai (P4, P5-style) | ~50% | **NIEKO** — Vision OCR vienintelis kelias |

**Pastaba:** procentai paremti tik 4 sample'ais — reikia daugiau projektų
geresnei statistikai.

## Rekomendacija

**Sprint A NĖRA pirmas prioritetas.** Vertės distribucija:
- 25% projektų: didelė nauda (P3-style)
- 25% projektų: vidutinė (P1-style — bet implementacija sudėtinga)
- 50% projektų: nė vertės (raster)

Mes ką tik užbaigėm Sprint B — **deterministic refactor su Python math'u**.
Tai duoda 100% determinizmo VISIEMS projektams (raster + CAD), nes
non-determinism'as buvo Vision'o aritmetikoje, ne primitive extraction'e.

**Vertingiausias next step'as iš spike'o:** sukurti **light-weight
pdfplumber primitive override'ą TIK `extract_tables()` based eksplikacijai**.
~1-2 dienos darbas, lengvai integruojama į esamą `eksplikacija_reader.py`
flow'ą:

```
def read_eksplikacija(pdf_bytes, client):
    # Step 1: try pdfplumber.extract_tables() — deterministinis, free, 25% projektų
    parsed = _try_pdfplumber_tables(pdf_bytes)
    if parsed and parsed["patalpos"]:
        return parsed

    # Step 2: existing Vision call — fallback for non-table-structured PDFs
    return _read_via_vision(pdf_bytes, client)
```

Tai duoda:
- **25% projektų (P3-style):** 100% determinizmas + $0 cost už eksplikaciją
- **75% projektų:** identiškas elgesys kaip dabar (Vision pre-pass)
- **Niekas negadina** — fallback yra esama implementacija

Šitą dar nebuvau implementuotas — palikta vartotojo decision'ui ar verta
investuoti 1-2 dienas po jau ką tik užbaigto B sprint'o.

## Out of scope

- Coordinate-clustering algoritmas P1-style projektams (sudėtingas)
- Vector geometry → polygon room boundaries (ambitous, future sprint)
- Azure Document Intelligence integracija (paid service, dar reikia
  įvertinti vs free pdfplumber tables)
