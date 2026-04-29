# SM05 — Sąmatų AI tikslumo studija (planning doc)

> Status: PLAN. Not yet executed. Created 2026-04-27.
>
> Purpose: lay out a peer-reviewed benchmark that compares Sąmatų AI's
> kiekių žiniaraštis output against a Lithuanian samatininkas working
> with Excel + manual takeoff. The published asset becomes a referenceable
> credibility artifact for sales conversations and procurement reviews
> ("kiek tiksliau / kiek greičiau").
>
> Inspired by Togal.ai's Florida State University study (71% time reduction,
> ±2% area accuracy) referenced in the togal-ux-patterns.md research file.

---

## 1. Hypothesis

H1: Sąmatų AI produces interior-finishing kiekių žiniaraščius with **≤ 5% deviation** in m² / m / vnt. quantities vs. an experienced LT samatininkas working manually.

H2: A samatininkas using Sąmatų AI completes the same project **≥ 50% faster** end-to-end (upload → reviewed PDF) than the manual-only baseline.

H3: ≥ 80% of Sąmatų AI line items map 1:1 to the human's positions (skyrius + aprasymas + vnt) without category disagreement.

These three together — accuracy, speed, completeness — form the publishable claim.

## 2. Sample selection

**3 real Lithuanian projects**, picked to span complexity:

| # | Type | Size | Why this picks |
|---|------|------|----------------|
| P1 | Naujos statybos butas (~80 m²) | Standartinis | Baseline residential — typical Sąmatų AI use case. |
| P2 | Privataus namo renovacija (~150 m²) | Vidutinis | Mixed — some walls preserved, drywall additions, partial tile replacement. Tests AI's handling of "esamų sienų" inputs. |
| P3 | Daugiabučio butas po kapitalinio (~120 m²) | Sudėtingas | Soviet-era, low ceiling 2.5 m, vonia + wc atskirai, kartais ne stačiakampės sienos. Tests SM02 multi-floor extension if scaled to 5 floors. |

Procurement: ask 2-3 LT contractors for anonymized real PDFs. Avoid demo/training-data PDFs. Owner consent + NDA template required.

## 3. Participants

**2 samatininkai** (independent of each other and of Sąmatų AI team):
- Vienas su 10+ metų stažu, dirbantis tradiciniu Excel + manual takeoff būdu.
- Antras su 3-5 metų stažu, atviras AI įrankiams (kontrolinis variantas).

Both must:
- Sign NDA covering project PDFs.
- Not see each other's outputs until after independent submission.
- Use their own usual toolchain (Bluebeam / Sistela / Excel).

Compensation: market rate per kiekių žiniaraštis (~150-300 €) × 3 projects × 2 estimators = ~1,800 € total honorarium budget.

**Academic partner**: VGTU Statybos technologijų ir vadybos katedra. Goal: methodology review + co-authorship to anchor credibility. Offer: published case study in their student handbook + paid student RA hours for analysis.

## 4. Methodology

**Two arms per project**:

1. **Manual baseline** — samatininkas works the project as they normally would, no time limit, records start/stop timestamps, submits final Excel.
2. **AI-assisted** — same samatininkas (different project) uploads PDF to Sąmatų AI, reviews/corrects in app, exports Excel. Records same timestamps + correction count from `corrections` audit log.

To control for "easy projects done with AI / hard projects done manually" bias, **rotate** so each estimator does each project in BOTH modes (3 projects × 2 modes × 2 estimators = 12 runs), with a 2-week wash-out between modes for the same project to limit memory effects.

## 5. Metrics

**Accuracy** (primary):
- Per kiekių line, deviation % between AI output and manual baseline. Aggregate by:
  - Skyrius (Glaistymas, Plyteles, GKP, Hidroizoliacija, etc.)
  - Vnt type (m², m, vnt., kg, l)
  - Confidence level emitted by extractor
- Median, p90, max deviation. Single mean is misleading — long tail tells the story.

**Speed** (secondary):
- End-to-end clock time per project per arm.
- Time-to-first-reviewed-position (how long before estimator says "I'd send this").
- Number of corrections logged via `/api/projects/:id/corrections`.

**Completeness** (tertiary):
- Coverage: % of human-listed positions present in AI output.
- Drift: AI-only positions absent from manual baseline (false positives).
- Category match: Cohen's κ for skyrius assignment.

**Subjective** (qualitative, post-test interviews, ~30 min each):
- "Kuriuose žingsniuose AI taupė laiką?"
- "Kas pasirodė nepatikima — ką tikrini ranka?"
- "Ar rekomenduotum kolegai?"

## 6. Threats to validity

- **Sample of 3 is small.** We won't claim statistical significance — we'll report effect sizes with bootstrap CIs. Honest framing.
- **Selection bias.** If we cherry-pick easy PDFs, AI looks great. Pre-register selection criteria (size range, project type spread) before procurement.
- **Estimator-AI familiarity.** Estimator using AI for first time underperforms vs. trained user. Run a 1-day onboarding before timing measurements.
- **Schema disagreement.** If AI emits "Sienų glaistymas Q2 + dažymas" as one line and human as two, naive matching fails. Pre-define category-merge rules in advance and apply uniformly.
- **Publication bias.** Commit to publishing **regardless of result** — agreed in writing with VGTU partner. If AI loses, publish that and use it to drive product improvement. Credibility long-term > one good headline.

## 7. Deliverables

1. **Internal report** — full data, methodology, raw outputs (~30 pages).
2. **Public case study** — 6-8 page summary for samatuai.lt /case-studies. Headline + 3 charts + methodology link.
3. **VGTU presentation** — co-authored slide deck for industry talks.
4. **Sales one-pager** — single PDF with the headline numbers, used in procurement responses.

## 8. Timeline

| Week | Action |
|------|--------|
| W1–W2 | NDA + project procurement (3 PDFs) |
| W3   | Estimator onboarding (1 day) + VGTU methodology sign-off |
| W4–W6 | Manual-baseline runs (3 projects × 2 estimators) |
| W7   | Wash-out |
| W8–W10 | AI-assisted runs |
| W11  | Data cleanup + analysis |
| W12  | Drafting + VGTU review |
| W13  | Publish |

Total: ~3 months from kickoff. ~2,500–3,500 € budget (estimator honoraria + VGTU RA + design).

## 9. Open questions for owner

These need decisions before kickoff:

- [ ] Project source — do we have 3 willing contractors, or do we need outreach?
- [ ] VGTU contact — is there an existing relationship to leverage?
- [ ] Can we anonymize project PDFs sufficiently for publication? If not, results stay internal-only.
- [ ] Pricing model for the public study release — gated by email signup, or fully open? (Open builds trust; gated builds list.)
- [ ] Acceptable failure mode — at what deviation would we **not** publish? Pre-commit a number.

## 10. Why this is worth doing

Per the togal-ux-patterns.md research, Togal's FSU peer-review study is "an asset referenced in every sales conversation for years." The study cost them ~$25k once and now anchors enterprise procurement reviews permanently.

For Sąmatų AI's LT market, the equivalent is a VGTU-co-authored study with two real LT samatininkai. The marginal cost is ~3,000 €. The competitor's equivalent doesn't exist — Bluebeam / Sistela / Excel have no comparable artifact in the LT context. **First-mover credibility on objective accuracy is a moat.**

---

## Status & next step

This document is a plan, not a commitment. Next required action: a human decision on §9 open questions before any procurement / estimator outreach happens. Suggest discussing these with the founder + at least one trusted samatininkas before allocating budget.
