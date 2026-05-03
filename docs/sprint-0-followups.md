# Sprint 0 Follow-Ups

Issues identified during Sprint 0 reviews that were intentionally deferred to keep Sprint 0 surgical. Track here so they don't get lost before Sprint 1.

## Code quality

1. **`/api/config` model IDs hardcoded** — `backend/api/config.py` returns `"claude-opus-4-7"` as a string literal twice; should source from `extractor.prompt.MODEL` so it doesn't drift when models upgrade.
2. **Mid-file imports in `main.py`** — Tasks 1, 3, 8 each added `from api.X import router as X_router` mid-file with `# noqa: E402`. Move to top-of-file imports section in a cleanup pass.
3. **`test_flags_default_to_false` mutates real `os.environ`** instead of using `monkeypatch`. Other tests in same file use `monkeypatch.setenv`. Inconsistent.
4. **GKP helper `_SK_GKP`/`_SAL` shadow caller's module-level constants.** If outer constants change, helper silently keeps old values. Lift to module level in vision_call.py or pass as kwargs.
5. **GKP helper hardcodes `WASTE = 1.10`** — `UNIVERSAL_RULES["waste_factors"]["drywall"] = 0.12` exists but isn't used. Consistency cleanup.

## Functional gaps

6. **Frontend NaN propagation** — `dazaiSienoms + dazaiLuboms = null + null = NaN`. Visible UI breakage until parent component wires `onRecomputed` from `AssumptionsPanel`. Acceptable per Sprint 0 plan but blocks UX.
7. **Wall GKP extraction missing** — extraction schema today only feeds ceiling GKP; helper supports both wall + ceiling but the wall path is dormant. Add `sienos_gkp_m2` to per-room extraction in a future sprint.
8. **Scale validator is no-op in production** — Vision schema doesn't emit per-room `diagonal_px` yet. Validator silently skips all rooms. Extend Vision prompt in a future sprint to populate this so the validator activates.
9. **DPI passed to scale validator may not match actual rendered DPI** — `pdf_to_b64_images` resizes large pages down. Pass effective DPI rather than the constant `200` when `diagonal_px` is wired up.
10. **Telemetry write has no error handling** — disk-full or unwritable path causes 500 on `/api/telemetry/session`. Wrap in try/except and return `{"ok": False, "warning": "..."}` so frontend doesn't bubble error to user.
11. **Telemetry default path is relative** — resolves differently depending on cwd of FastAPI process. Use `Path(__file__).parent / "session_log.jsonl"` for the default.

## Test coverage gaps

12. **`recompute-quantities` non-paint fields silently no-op** — `lubu_aukstis`, `sienos_storis`, `plyteliu_aukstis`, `kampu_skaicius` accepted but ignored. Add a test that asserts an edit to one of these doesn't change `dazai_l` (proves silent-no-op behavior is intentional, prevents future drift).
13. **No test for double-fire of `session.finish()`** in `telemetry.js`. Logic uses `finished` flag; would be 2 lines to verify.
14. **Pre-existing pytest collection errors** in `test_cross_page_validator.py`, `test_deterministic.py`, `test_edge_cases.py` (missing `sys.path.insert` shim). Out of Sprint 0 scope but blocks `pytest tests/` from clean output.

## Tracking

Sprint 1 plan should triage these into the new sprint or a separate cleanup PR.
