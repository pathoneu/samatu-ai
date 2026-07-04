# Pathon Pricing & Margin Model (W3.2)

**Status:** DRAFT for founder decision gate (2026-07-04). Tiers here are a **proposal**; Stripe build (W3.3) does not start until these are approved.

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

**True cost = Pass-1 × (1.34–1.76)** for the dropped sub-calls:

| Project | Pass-1 | True (low ×1.34) | True (high ×1.76) |
|---|---|---|---|
| lazūnu | 0.47 | 0.63 | 0.83 |
| čiurlių | 0.51 | 0.68 | 0.90 |
| beržu | 1.07 | 1.43 | 1.88 |
| bacvevičiaus | 2.80 | 3.75 | 4.93 |
| **avg** | **1.21** | **1.62** | **2.13** |

**Planning figures used below:**
- **Typical** small/medium interior project (the target customer's bread & butter): **~€1.5**
- **Conservative blended COGS** (what I hold margins against): **€2.00/project**
- **Worst-case** large commercial project (rare in target segment): **~€5**

> The €2.00 conservative sits at the top of the estimate band. The band is wide because the sub-call multiplier is *estimated*, not yet *measured* on the fixed meter — see §6.

---

## 2. Draft tiers (existing `billing_v2.py`) — stress-tested

Margin at **full utilization** (user consumes all included projects — the conservative case; light users have far higher margin, overage is priced above COGS):

| Tier | €/mo | Incl. | €/proj (full) | Margin @€2 | Margin @€1.5 | Verdict |
|---|---|---|---|---|---|---|
| Free | 0 | 1/mo | 0 | **−€2 loss** | −€1.5 | COGS exposure |
| **Pro** | 49 | 10 | 4.90 | **59%** | 69% | ✅ healthy |
| **Studio** | 129 | 40 | 3.23 | **38%** | 54% | ⚠️ under 40% floor |
| Pro overage | — | — | 8.00 | 75% | 83% | ✅ |
| Studio overage | — | — | 5.00 | 60% | 70% | ✅ |

**Findings:**
1. **Pro (€49/10) is priced right** — 59% margin even at conservative COGS. Keep.
2. **Studio (€129/40) fails the 40% floor at conservative COGS (38%).** €129÷40 = €3.23/project is too thin once true cost is counted. It only clears 40% if real COGS stays near the *typical* €1.5, which a Studio user (higher volume, possibly bigger projects) is the least likely to.
3. **Free (1 project/month) is a recurring COGS drain** — €1.5–2 per redeemed free project, €0 revenue. Fine as trial/CAC at low volume; at 1,000 idle free users it's ~€2k/mo of pure loss. The hard cap + 1-project limit bound it, but "per month, forever" is generous.
4. **No one-off single-project option** — the master plan called for it; it's the lowest-friction way for a skeptical contractor to try a real paid project.

---

## 3. Proposed tiers (recommended)

| Tier | €/mo | Incl. | Overage | €/proj (full) | Margin @€2 | Change |
|---|---|---|---|---|---|---|
| **Trial** | 0 | 1 project **one-time** | — | — | CAC (bounded) | was 1/mo → one-time |
| **Vienkartinis** (one-off) | €12 / project | — | — | 12.00 | **83%** | **NEW** |
| **Pro** | 49 | 10/mo | €8 | 4.90 | 59% | keep |
| **Studio** | **149** | 40/mo | €5 | 3.73 | **46%** | €129→€149 |

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
- **The one number worth measuring before locking Studio:** the sub-call multiplier is *estimated* (34–76%), not *measured on the fixed meter*. Studio's viability sits right on the 40% line, so the exact figure is decision-relevant. **A ~€5–7 instrumented run** (2–3 representative projects on the now-complete meter: beržu typical, čiurlių raster, bacvevičiaus worst-case) would replace the band with an exact multiplier and confirm Studio's margin. Pro/Trial/one-off decisions don't need it — their margins are robust across the whole band.

---

## 7. Recommendation to founder (the gate)

1. **Approve Pro €49/10 and the €12 one-off as-is** (margins robust).
2. **Pick a Studio fix:** €149/40 (46%) *or* €129/30 (53%).
3. **Trial:** one-time 1-project (bounded CAC) vs the current 1/month.
4. **Green-light the ~€5–7 measured run** to nail the exact COGS multiplier before Studio is finalized — or say "ship on the conservative estimate, don't spend."

On approval, W3.3 builds Stripe Checkout (one-off + subscriptions) + webhooks + the LT PVM sąskaita-faktūra generator, all behind `BILLING_ENABLED` (default OFF = today's behavior exactly).
