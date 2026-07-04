# Pathon Pricing & Margin Model (W3.2)

**Status:** Founder-approved tiers (2026-07-04): **Pro €49/10 · Studio €149/40 · one-off €12/project · free trial (anti-abuse TBD)**. True-cost measured run in progress to confirm Studio margin. Stripe build (W3.3) starts after the measured number lands.

**Locked cost basis:** Opus 4.8 + native-PDF Pass-1, voting×3 (the accuracy-locked config). All figures EUR. Anthropic USD→EUR at 0.93.

---

## 1. What a project actually costs us (COGS)

Cost metering was **Pass-1-only** until 2026-07-04 — it ignored every sub-reader (apdailos, doors, door-types, zoom, eksplikacija-Vision, fixtures, niches), undercounting true cost by **34–76%**. That's now fixed (all sub-calls metered per-model). These are the numbers pricing must clear.

**Measured Pass-1 cost, locked config (from `eval_runs`):**

| Project | Pass-1 €/proj | Character |
|---|---|---|
| lazūnu | 0.47 | small, text-rich |
| čiurlių | 0.51 | raster |
| beržu | 1.07 | typical text-rich apartment |
| bacvevičiaus | 2.80 | 65-page, text-free (worst-case commercial) |
| **avg** | **1.21** | |

**MEASURED true cost** (2026-07-04, complete meter, locked config, 3 representative projects):

| Project | Pass-1 € | sub-calls € | **TRUE €** | ×mult | dominant sub-costs |
|---|---|---|---|---|---|
| lazūnu (small) | 0.35 | 0.34 | **0.69** | 1.95× | eksplikacija, door_type×3 |
| čiurlių (raster) | 0.45 | 0.30 | **0.75** | 1.67× | zoom×8, doors |
| beržu (typical apt) | 1.04 | 1.32 | **2.36** | 2.26× | apdailos €0.34, eksplikacija €0.35, door_type×3 €0.31, fixtures×3 |
| bacvevičiaus (worst, *extrapolated*) | 2.80 | — | **~5.8** | ~2.06× | — |

**The measured multiplier is ~2.06× Pass-1 — higher than the 1.34–1.76× literature estimate.** Sub-readers cost more than expected; on a full apartment (beržu) they *more than double* Pass-1.

**Planning figures (measured):**
- **Small/simple project:** €0.7
- **Typical full apartment (beržu — the realistic paying-customer project):** **€2.36**
- **Corpus average (skewed by 2 tiny projects):** €1.27
- **Worst-case large commercial (rare):** ~€5.8
- **Conservative planning COGS:** **€2.36** (a real estimator's projects skew to full apartments, not single rooms)

> Reducible: sub-reader voting (door_type ×3, fixtures ×3) triples those readers' cost, and beržu shows a €0.35 eksplikacija *Vision* call on a text-rich PDF that pdfplumber should arguably handle free. ~€0.5–0.7/project looks recoverable without touching accuracy — a follow-up cost lever (see §5).

---

## 2. Draft tiers (existing `billing_v2.py`) — stress-tested

Margin at **full utilization** (user consumes all included projects — the conservative case; light users have far higher margin, overage is priced above COGS). Columns now use **MEASURED** cost: corpus-average €1.27 vs conservative typical-apartment €2.36:

| Tier | €/mo | Incl. | €/proj (full) | Margin @€1.27 (avg) | Margin @€2.36 (typ. apt) | Verdict |
|---|---|---|---|---|---|---|
| Free | 0 | 1/mo | 0 | **−€1.27 loss** | −€2.36 | COGS exposure |
| **Pro** | 49 | 10 | 4.90 | 74% | **52%** | ✅ healthy at both |
| **Studio (draft €149)** | 149 | 40 | 3.73 | 66% | **37%** | ⚠️ still under 40% at typical-apt cost |
| Pro overage | — | — | 8.00 | 84% | 70% | ✅ |
| Studio overage | — | — | 5.00 | 75% | 53% | ✅ |

**Findings (measured):**
1. **Pro (€49/10) holds** — 52% even at the conservative €2.36 COGS. Keep.
2. **Studio €149/40 still slips below 40% at conservative cost (37%).** My €149 fix was sized to a €2.00 *estimate*; the *measured* €2.36 pushes it back under. €149÷40 = €3.73/project clears 40% only if a Studio user's average project stays ≤ €2.24 — true for a mixed project load (66% at the €1.27 corpus avg), false if they run mostly full apartments. To *guarantee* the floor: **€149/35** (€4.26 → 45%) or **€129/30** (€4.30 → 45%).
3. **Free (1 project/month) is a recurring COGS drain** — €0.7–2.4 per redeemed project, €0 revenue. Bounded by the company-code gate (§3a) + hard cap.
4. **One-off €12** — 80% margin even at €2.36. ✅

---

## 3. Proposed tiers (recommended)

| Tier | €/mo | Incl. | Overage | €/proj (full) | Margin @€2 | Status |
|---|---|---|---|---|---|---|
| **Nemokamas bandymas** (trial) | 0 | 1 project | — | — | CAC (bounded) | ✅ approved; anti-abuse = §3a |
| **Vienkartinis** (one-off) | €12 / project | — | — | 12.00 | **83%** | ✅ approved |
| **Pro** | 49 | 10/mo | €8 | 4.90 | 59% | ✅ approved (keep) |
| **Studio** | **149** | 40/mo | €5 | 3.73 | **46%** | ✅ approved (€129→€149) |

### 3a. Free-trial anti-abuse (founder concern: stop serial-signup free riders)

Layered, B2B-native, server-enforced. The core idea: the free-project entitlement is tied to a **verified company identity that persists across account deletion**, not to a disposable account row.

1. **Email verification** (baseline) — no unverified account gets the trial.
2. **One trial per LT company code (įmonės kodas), enforced server-side** — required at signup (it's invoice data we need anyway for the PVM sąskaita-faktūra). Uniqueness checked against a `consumed_trials` table keyed by normalized company code, which persists **independently of the user row** — deleting/recreating an account with the same company does NOT reset the trial. Optionally validate the code against the LT business registry (Registrų centras JAR) for existence, not just format.
3. **Reservation hard cap** already bounds per-account spend (a compromised trial can't run unlimited projects).
4. **Escalation ladder if telemetry shows abuse** (do NOT build upfront): (a) card-on-file for the trial via Stripe SetupIntent — the single strongest deterrent (Stripe Radar flags duplicate cards), at the cost of top-of-funnel friction; (b) phone/SMS verification. Add only if the company-code gate proves insufficient.

**Open fork for founder:** require a card on file to start the trial (max protection, less funnel) vs company-code-gated-only (more signups, rely on escalation if abused). Recommendation: **company-code-gated-only at launch** — real customers give the company code willingly, abusers would need many registered companies, and card-required trials suppress exactly the skeptical-contractor top-of-funnel you're trying to win. Keep the card-on-file path built-but-off as the escalation lever.

- **One-off €12/project:** 83% margin, no commitment — the try-a-real-project entry point. (A contractor bills their client hundreds for a sąmata; €12 is trivially justified.)
- **Studio €149/40:** clears the 40% floor at conservative COGS (46%). Alt if you prefer to hold €129: cut included to **30** (€4.30/proj → 53%).
- **Trial one-time** instead of monthly: caps free-user COGS to a single project each; revisit to monthly once conversion data justifies it.
- All tiers keep the reservation-based hard cap as the runaway-cost backstop.

---

## 4. VAT reality (simplifies the sticker price)

The master plan said "+21% PVM on every price." For our actual buyer that's **mostly not how it works**:
- Buyers are **LT construction businesses (B2B)**. A VAT-registered LT company = **reverse charge**: Pathon collects **no VAT**; the buyer self-accounts. (Verified in the June commercial research, 3-0.)
- **Pathon itself is under the €45,000 LT VAT-registration threshold** at launch → not VAT-registered → **no VAT added to invoices at all** initially.
- **Net effect:** the sticker price **is** the revenue. Display prices ex-VAT with a "PVM taikoma pagal atvirkštinį apmokestinimą / prekyautojas nėra PVM mokėtojas" note. Add real VAT handling only when Pathon crosses €45k turnover.

This is *good news* for margins — no 21% haircut on the tiers above.

---

## 5. Cost sensitivity (why the config matters to price)

- **If any volume tier ran on Fable 5** (2× Anthropic rate): COGS ~doubles to ~€4/project → Pro margin collapses to **18%**, Studio goes **negative**. Fable is not viable for included-quota tiers — this independently re-confirms the locked **Opus 4.8 + native** decision. Reserve Fable for a priced premium "hard-project re-analysis" add-on only.
- **Voting×3 → ×1** would cut COGS ~30–40% (a lever if margins ever pinch) but trades the accuracy voting buys (it's default-on for a reason). Flagged, not recommended.

## 6. Break-even & the one open number

- **Fixed infra** (Render + R2 + Neon + domain) ≈ **€50–100/mo**. Break-even ≈ **3–5 Pro subscribers** (or the 5 concierge-pilot estimators). The business is not infra-constrained; it's demand-constrained.
- **Measured (2026-07-04, done):** the sub-call multiplier is **2.06×**, not the 1.34–1.76× estimate. This is what moved Studio back under the 40% floor at conservative cost — see §2. Pro/one-off margins survived the correction; Studio needs the €149/35 (or €129/30) trim to guarantee the floor.

---

## 7. Decisions (2026-07-04 founder gate)

- **Pro €49/10** — approved, holds at measured cost (52% at €2.36). ✅
- **One-off €12/project** — approved, 80% at €2.36. ✅
- **Studio €149/40** — ⚠️ **RE-OPENED by measurement.** The €149 fix was sized to a €2.00 estimate; measured €2.36 puts €149/40 at 37%, under the floor. Needs one more nudge: **€149/35 (45%)** or **€129/30 (45%)** — pending founder pick.
- **Free trial** — approved in principle; anti-abuse per §3a (company-code-gated, server-persistent entitlement); card-on-file escalation built-but-off. Card-vs-no-card-for-trial fork: recommend no-card at launch.
- **Cost lever (follow-up):** ~€0.5–0.7/project looks recoverable (drop door_type/fixtures sub-reader voting ×3→×1; stop the eksplikacija Vision call on text-rich PDFs). If pursued, beržu drops ~€2.36→~€1.8 and €149/40 clears 40% on its own — an alternative to trimming Studio's quota. Touches the accuracy pipeline, so measure before shipping.

Next (after the Studio pick): W3.3 builds Stripe Checkout (one-off + subscriptions) + webhooks + the LT PVM sąskaita-faktūra generator + the trial anti-abuse gate, all behind `BILLING_ENABLED` (default OFF = today's behavior exactly).
