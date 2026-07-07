# Council — "What remaining accuracy is worth improving?" (2026-06-14)

5 advisors → 3 peer reviews. Companion to the door/fixture council + the standards research (kampai/45°/rotband, running).

## Question
After fixing doors/paint/heights, current Beržų accuracy: paint −3.9%, doors −8.9%, angokraščiai −8.4%, silikonavimas −7.3% (all good). Remaining: **kampai (corner-bead) −22% AND unstable run-to-run (333/386/420 vs 493)**; skylių −18%; 45° tile +15%; rotband −14%. No human ground truth — the contractor oracle is itself **AI-parsed** (directional only).

## Chairman's Verdict

### Where the council agrees (high confidence)
1. **Do NOT tune these numbers to hit the oracle.** It's AI-parsed — "an echo," "false precision," "1-decimal optimization against a ruler with no tick marks." Grinding to match another AI's reading can converge perfectly and be wrong together.
2. **Do NOT propagate the door-reader's corrected count into `elementai`** (so it feeds paint deductions + reveals + kampai). Regression cascade: it imports the door-reader's recall error into paint, which is currently −3.9% *because* its deduction count is independently right today. (Contrarian + Executor, concrete.)
3. **The keystone is human ground truth.** Cheap paths the reviewers added: re-parse the actual contractor-bill PDF deterministically (it exists), or hand the contractor a 10-line "count your outer corners" sheet.

### The sharpest insight — First Principles (unanimous peer-review winner)
**"Dažymo kampų montavimas" is NOT one quantity.** Our formula fuses three things the contractor itemizes as *separate lines*: corner-bead (outer corners × H), opening reveals (angokraščiai — already computed separately), and partition junctions. The −22% is comparing an app aggregate to a partial sum; it "only matches because errors cancel." **The fix is to DECOMPOSE kampai into its real sub-quantities, each matched to its own contractor line and individually falsifiable — not to tune the aggregate.** This is a determinism/correctness fix, not a coefficient tweak, and survives having no oracle.

### The blind spot ALL FIVE missed (unanimous in peer review)
**Nobody localized WHY the variance happens.** 333/386/420 on the *same PDF* is the counted primitives (openings, n_partition_walls, perimeters) jittering across voted runs. The cheap move nobody proposed: **log the per-run counted primitives to localize where variance enters BEFORE touching any formula.** Most of the −22% may be jitter, not bias — and you cannot measure a −22% bias until the ±13% scatter is gone. Precision before accuracy.

### Where the council clashed
- Expansionist: "instability is a MOAT — expose the spread, sell error bars." Peer review **rejected** this: a contractor wants one number to bid; "we ran it 5×, got 333–420, you verify" exports the unsolved problem as a feature. Instability is a *correctness* defect to fix, not a feature to sell. (Surfacing uncertainty per-line is good; romanticizing run-to-run scatter is not.)

### Recommendation
1. **Variance-localization diagnostic FIRST** (cheap, no fitting): log per-run counted primitives across a few extractions; see whether kampai's scatter is openings / n_partition_walls / perimeters.
2. **Decompose kampai** into corner-bead + reveals + partition-junctions, each matched to its contractor line (await the standards research for the canonical corner-bead rule). Honest correctness, even if the aggregate reads worse.
3. **Leave 45° (+15%, legit 10–15% waste band) and rotband (−14%, would be fitting) FLAGGED**, don't tune.
4. **Skylių**: the fixture reader already improved it (3→4); don't tune the formula. Verify on objektas_b too.
5. **Do NOT** propagate door→elementai; **do NOT** grind to the AI oracle.
6. **Keystone**: get one human-confirmed count.

### The one thing to do first
**The variance-localization diagnostic** — measure where the run-to-run instability enters before changing a single formula. (Don't optimize a number you can't reproduce.)
