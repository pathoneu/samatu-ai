# Model comparison — claude-opus-4-8 vs claude-fable-5

- A = **claude-opus-4-8** (4 run(s))
- B = **claude-fable-5** (4 run(s))

## objektas_b

| Metric | Unit | Truth | claude-opus-4-8 | claude-fable-5 | %err claude-opus-4-8 | %err claude-fable-5 |
|---|---|---:|---:|---:|---:|---:|
| Dažymo plotas (samata items 16+17, excl garažas) | m² | 493.03 | 622.78 | 559.75 | +26.32% | +13.53% |
| LED nišų ilgis | m | 54.98 | 41.50 | 43.36 | -24.52% | -21.14% |
| GKP lubos iki 3m | m² | 74.91 | 180.00 | 180.44 | +140.29% | +140.88% |
| GKP lubos virš 3m | m² | 68.28 | 0.00 | 0.00 | -100.00% | -100.00% |
| Dažymo kampai | m | 580.54 | 503.82 | 494.13 | -13.21% | -14.88% |
| Sienų lyginimas Rotband | m² | 138.69 | — | — | — | — |
| Angokraščiai | m | 94.02 | 89.44 | 183.10 | -4.87% | +94.75% |
| **MAE** | % | | | | **51.53** | **64.20** |

## objektas_a

| Metric | Unit | Truth | claude-opus-4-8 | claude-fable-5 | %err claude-opus-4-8 | %err claude-fable-5 |
|---|---|---:|---:|---:|---:|---:|
| Dažymo plotas (samata items 16+17, excl garažas) | m² | 584.81 | 454.24 | 448.80 | -22.33% | -23.26% |
| Sienų dažomas plotas | m² | 460.71 | 299.27 | 293.83 | -35.04% | -36.22% |
| Lubų dažomas plotas | m² | 165.60 | 165.64 | 165.64 | +0.02% | +0.02% |
| LED nišų ilgis | m | 42.30 | 40.50 | 40.08 | -4.25% | -5.25% |
| Bendras plotas | m² | 165.61 | 165.64 | 165.64 | +0.02% | +0.02% |
| Plytelės grindyse | m² | 39.88 | 31.89 | 31.89 | -20.04% | -20.04% |
| Plytelės sienose | m² | 61.53 | 92.40 | 61.60 | +50.17% | +0.11% |
| GKP lubos iki 3m | m² | 102.78 | 93.42 | 104.09 | -9.11% | +1.27% |
| GKP lubos virš 3m | m² | 62.82 | 61.55 | 61.55 | -2.02% | -2.02% |
| Dažymo kampai | m | 493.35 | 428.54 | 430.70 | -13.14% | -12.70% |
| Sienų lyginimas Rotband | m² | 138.69 | — | — | — | — |
| Angokraščiai | m | 89.39 | 75.00 | 56.18 | -16.10% | -37.15% |
| Rozetės + jungtukai | vnt | 113.00 | — | — | — | — |
| Priglaistomi šviestuvai | vnt | 38.00 | — | — | — | — |
| Difūzoriai | vnt | 15.00 | — | — | — | — |
| Šiukšlių išvežimas | m³ | 12.00 | — | — | — | — |
| **MAE** | % | | | | **15.66** | **12.55** |

## objektas_c

| Metric | Unit | Truth | claude-opus-4-8 | claude-fable-5 | %err claude-opus-4-8 | %err claude-fable-5 |
|---|---|---:|---:|---:|---:|---:|
| Dažymo plotas (samata items 16+17, excl garažas) | m² | 388.01 | 274.80 | 293.10 | -29.18% | -24.46% |
| LED nišų ilgis | m | 16.84 | 4.10 | 15.24 | -75.65% | -9.50% |
| GKP lubos iki 3m | m² | 111.84 | 72.25 | 65.95 | -35.40% | -41.03% |
| Dažymo kampai | m | 201.86 | 210.25 | 332.12 | +4.16% | +64.53% |
| Sienų lyginimas Rotband | m² | 37.00 | — | — | — | — |
| Angokraščiai | m | 34.53 | 45.25 | 35.10 | +31.05% | +1.65% |
| **MAE** | % | | | | **35.09** | **28.23** |

## objektas_d

| Metric | Unit | Truth | claude-opus-4-8 | claude-fable-5 | %err claude-opus-4-8 | %err claude-fable-5 |
|---|---|---:|---:|---:|---:|---:|
| Dažymo plotas (samata items 16+17, excl garažas) | m² | 150.57 | 120.08 | 128.64 | -20.25% | -14.56% |
| LED nišų ilgis | m | 10.58 | 12.39 | 14.42 | +17.11% | +36.30% |
| GKP lubos iki 3m | m² | 41.28 | 41.28 | 41.28 | +0.00% | +0.00% |
| Dažymo kampai | m | 123.59 | 132.72 | 121.21 | +7.39% | -1.93% |
| Sienų lyginimas Rotband | m² | 32.41 | — | — | — | — |
| Angokraščiai | m | 31.80 | 48.27 | 31.55 | +51.79% | -0.79% |
| **MAE** | % | | | | **19.31** | **10.71** |

## Per-project MAE (mean |%err| over scored metrics)

| Project | claude-opus-4-8 | claude-fable-5 |
|---|---:|---:|
| objektas_b | 51.53 | 64.20 |
| objektas_a | 15.66 | 12.55 |
| objektas_c | 35.09 | 28.23 |
| objektas_d | 19.31 | 10.71 |
| **mean** | **30.40** | **28.92** |

## Totals (tokens / cost / time)

| | claude-opus-4-8 | claude-fable-5 |
|---|---:|---:|
| input_tokens | 2,964 | 2,964 |
| output_tokens | 68,607 | 199,261 |
| cache_read_tokens | 686,584 | 672,970 |
| cache_write_tokens | 322,871 | 336,485 |
| cost_usd | $5.3019 | $17.3953 |
| cost_eur | €4.9309 | €16.1776 |
| wall time (min) | 45.2 | 76.7 |

## Per-reader elapsed (s, summed across projects)

| Reader | claude-opus-4-8 | claude-fable-5 |
|---|---:|---:|
| apdailos | 108.8 | — |
| door_types | 117.4 | 13.5 |
| doors | 99.8 | — |
| fixtures | 110.1 | — |
| zoom | 337.6 | 541.0 |

