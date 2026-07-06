# Code audit pass 2 — fixes log (2026-07-06)

Second focused audit (workflow `wuyn8rii8`, 38 agents) over subsystems the first
50-agent pass + pentest under-covered: **billing activation safety, admin module,
db.py integrity, concurrency / swallowed errors, dead-stale code**, plus a
re-verify of the c03c905 fixes. It excluded the 3 files owned by in-flight
task-sessions (universal_rules formulas, projectStore persistence, bundling Q4).

**31 candidates → 16 adversarially confirmed.** Disposition below: **12 fixed,
2 pushed back on (not real / intentional), 2 deferred.** Baseline tests
1392 → **1399 passing** (+7 regression tests, 0 regressions), lint clean.

Every fix is tagged `audit 2026-07-06` in the code.

---

## Fixed (12)

| # | Sev | File | What & fix |
|---|-----|------|-----------|
| 1 | **critical** | `api/billing_v2.py` webhook | Handler crash was swallowed → 200, but `seen_webhook()` had already **claimed** the event id, so Stripe never retried and the state update (subscription/credit) was lost forever. **Now:** on handler exception, `db.forget_webhook()` releases the claim + return **500** so Stripe retries. Unknown event *types* still 200 (no retry) — correct. New `db.forget_webhook()`. Test: `test_webhook.py::test_handler_crash_releases_claim_and_500s_then_retry_applies`. |
| 2 | high | `extractor/door_type_reader.py:173` | `int(parsed.get("beapvadines_count"))` crashed on a non-numeric Vision output (`"3+"`), aborting the whole door read on real PDFs. This was the **one reader missed** when `doors_reader`/`sanitary_fixture_reader` got safe coercion in c03c905. **Now:** `_safe_count()` (mirrors the others), used in the return + `_mode_int`. 3 tests. |
| 3 | high | `db.py:637` | Credit double-spend race: `if credits_balance()>0: record('credit_consumed')` across two connections → two concurrent extractions both consume one credit (balance −1 = free extraction). **Now:** `_consume_oneoff_credit_if_available()` — a single atomic conditional `INSERT ... SELECT WHERE (balance)>0`. 3 tests incl. an 8-thread race. |
| 4 | high | `main.py:5302` | `/extract-interior-stream`: on client disconnect the sync `gen` was never closed and the worker thread kept the extraction alive. **Now:** `try/finally` closes `gen` on every exit; if a `next(gen)` step is in flight, the close is deferred to a future done-callback (never close a running generator). |
| 5 | high | `db.py:288` | Corrupt/truncated project `data` blob → `except Exception: data={}` **silently** returned an empty project (user's rooms/pozicijos/corrections vanish, looks like success). **Now:** narrowed except, `log.error` loudly (ops can restore from the R2 DB backup), returns a `{_data_corrupt: True}` marker instead of a silent husk. Added a `db` logger. |
| 6 | high | `auth.py:207` | `require_billable_user` swallowed spend-cap machinery failures with `except Exception: pass` — a DB hiccup meant the request ran, unmetered, cap unenforced, **silently**. **Now:** keeps the deliberate fail-open (a metering hiccup must not 500 a user) but `log.exception`s it so it's visible. Added an `auth` logger. |
| 7 | high | `main.py:5468` | `print()` → `log.warning()` in `/recompute-interior` room-calc error path (stdout is invisible to prod log aggregation). |
| 8 | high | `main.py:5535` | `print()` → `log.warning()` in `/recompute-interior` pozicijos-build error path. |
| 9 | high | `main.py:5482` | Misleading comment: claimed pozicijos "come from Vision narrative"; they're rebuilt by `_build_pozicijos_from_rooms()` right below. Corrected. |
| 10 | medium | `main.py:2550` | Deleted dead `_extract_interior_text()` (orphaned when `/extract-interior-v1` was removed; zero callers). |
| 11 | low | `db.py:1325` | Added a guard comment at the admin-pagination f-string (`{where}` is a hardcoded literal, values are bound) so a future refactor doesn't route a search value into the template. Code was already safe. |
| 12 | low | `main.py:4519` | Deduped `SKYRIUS_LEGACY_MIGRATION` imported twice in `generate_excel`. |

## Pushed back on — not fixed, with reasons (2)

- **`billing_v2.py:177` "webhook replay when the secret is later configured" (rated high).** Not attacker-exploitable: while `STRIPE_WEBHOOK_SECRET` is unset, `construct_event` raises → **400, fail-closed**, nothing processed. An attacker can't sign events without the secret, so nothing they send verifies then *or* later. The only events that replay once the secret is set are **genuine Stripe events** that Stripe queued — replaying them is correct and idempotent (`seen_webhook` + handlers). No "credits without payment" path exists. Left as-is (fail-closed is already right).
- **`billing_v2.py:248` "one-off credit granted before invoice emission" (rated high).** Intentional and correct: `_emit_invoice` is best-effort by contract and **already `log.exception`s** on failure (billing_v2.py:449). You do *not* want to deny a customer the credit they paid for because PDF/storage hiccuped — keep the credit, reconcile the invoice from the loud log. No change.

## Deferred (2)

- **`admin_v2.py:121` admin action audit trail (high).** Real gap, but it's a *feature* (needs a new `admin_audit_log` table + migration), not a bug, and low-value with a single admin today. **Spawned as a task** (`task_e01c91ce`).
- **`db.py:1437` orphan-backfill doesn't re-trigger if an admin is created post-startup (low).** Rare, and the `upsert_project` ownership barrier (db.py:313) already blocks the write-path exploit. Noted; not worth a migration now.

---

## Verified clean (re-check of c03c905)

Excel `_safe_cell()` on titles/room-names/notes, the empty-export SUBTOTAL clamp, PDF `suma` backfill, `mergeDarbuSarasasEdits` pass-2, and the sanitary reader's coercion all held up. No new auth / IDOR / XSS findings — the known-good posture survived this pass. The only gap in the c03c905 batch was door_type_reader (fixed above, #2).

**Bottom line:** the two genuinely dangerous items (webhook lost-update, credit race) are fixed and tested; both were dormant anyway (`BILLING_ENABLED` is OFF). The recurring pattern was *silent failure swallowing real errors* — a monitoring/correctness class, now made loud. No security emergency.
