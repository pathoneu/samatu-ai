"""Run every detector against every ground truth (page, symbol).

Output: results/<date>-bakeoff.md with side-by-side comparison.
"""

from __future__ import annotations
import os
import time
from datetime import datetime
from pathlib import Path

from detector_bench.core.types import Detector, DetectionResult
from detector_bench.core.ground_truth import GroundTruth, load_ground_truth

from detector_bench.detectors.p1_baseline_vision import BaselineVisionDetector
from detector_bench.detectors.p2_text_driven import TextDrivenDetector
from detector_bench.detectors.p3_template_match import TemplateMatchDetector
from detector_bench.detectors.p4_hybrid import HybridDetector
from detector_bench.detectors.p5_grounding_dino import GroundingDinoDetector
from detector_bench.detectors.p6_claude_tool_orch import ClaudeToolOrchestratedDetector


REPO = Path("/Users/ignasgaldikas/samatu-ai")
GT_DIR = REPO / "ground_truth"
RESULTS_DIR = REPO / "results"


def _accuracy(predicted: int, truth: int) -> float:
    """1.0 = exact; 0.5 = off by 50% of truth; 0.0 = ≥ truth wrong."""
    if truth == 0:
        return 1.0 if predicted == 0 else 0.0
    err = abs(predicted - truth) / truth
    return max(0.0, 1.0 - err)


def _pdf_path_for(name: str) -> Path:
    if name.startswith("projektas_1"):
        return REPO / "training-data/projektas_1/projektas_1_breziniai.pdf"
    if name.startswith("projektas_3"):
        return REPO / "training-data/projektas_3/projektas_3_breziniai.pdf"
    if "Visi techniniai" in name or name.startswith("visi_techniniai"):
        return Path("/Users/ignasgaldikas/Desktop/Visi techniniai 01.28.pdf")
    raise ValueError(f"unknown PDF: {name}")


def main() -> None:
    # Load env
    env_path = REPO / "backend" / ".env"
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            if "=" in line and not line.strip().startswith("#"):
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip())

    detectors: list[Detector] = [
        BaselineVisionDetector(),
        TextDrivenDetector(),
        TemplateMatchDetector(),
        HybridDetector(),
        GroundingDinoDetector(),
        ClaudeToolOrchestratedDetector(),
    ]

    gt_files = sorted(GT_DIR.glob("*.yaml"))
    if not gt_files:
        print(f"No ground truth in {GT_DIR}. Run build_ground_truth.py first.")
        return

    # gt_path → GroundTruth + pdf_path
    bench: list[tuple[Path, GroundTruth]] = []
    for p in gt_files:
        gt = load_ground_truth(p)
        bench.append((_pdf_path_for(gt.pdf_name), gt))

    # results[(detector_name, gt_path, symbol_code)] = (predicted, runtime_s, cost, errors)
    results: dict[tuple[str, str, str], tuple[int, float, float, str]] = {}

    for det in detectors:
        seen_pdfs: set[Path] = set()
        setup_failed_pdfs: set[Path] = set()
        for pdf_path, gt in bench:
            if pdf_path in setup_failed_pdfs:
                # Setup failed for this PDF on this detector — skip detect()s
                # but record so report shows the gap. We still try setup() on
                # next PDF (a different PDF may succeed).
                for symbol_code, _truth in gt.symbols.items():
                    key = (det.name, gt.confirmed_at + "|" + gt.pdf_name + "|p" + str(gt.page_nr), symbol_code)
                    results[key] = (0, 0.0, 0.0, "setup failed")
                continue
            if pdf_path not in seen_pdfs:
                try:
                    det.setup(pdf_path)
                    seen_pdfs.add(pdf_path)
                except Exception as e:
                    print(f"  [{det.name}] setup failed for {pdf_path.name}: {e}")
                    setup_failed_pdfs.add(pdf_path)
                    for symbol_code, _truth in gt.symbols.items():
                        key = (det.name, gt.confirmed_at + "|" + gt.pdf_name + "|p" + str(gt.page_nr), symbol_code)
                        results[key] = (0, 0.0, 0.0, f"setup failed: {e}"[:80])
                    continue
            for symbol_code, _truth in gt.symbols.items():
                try:
                    r = det.detect(pdf_path, gt.page_nr, symbol_code)
                except Exception as e:
                    r = DetectionResult(0, [], 0.0, 0.0, [str(e)])
                key = (det.name, gt.confirmed_at + "|" + gt.pdf_name + "|p" + str(gt.page_nr), symbol_code)
                err_summary = "; ".join(r.errors[:1])[:80]
                results[key] = (r.count, r.runtime_s, r.cost_usd, err_summary)
                print(f"  [{det.name}] {gt.pdf_name} p{gt.page_nr} {symbol_code}: pred={r.count} truth={_truth} ({r.runtime_s:.1f}s)")

    # Build report
    RESULTS_DIR.mkdir(exist_ok=True)
    report_path = RESULTS_DIR / f"{datetime.now():%Y-%m-%d}-bakeoff.md"
    lines: list[str] = []
    lines.append(f"# Symbol-detection bake-off — {datetime.now():%Y-%m-%d %H:%M}\n")
    lines.append(f"Pipelines tested: {len(detectors)}  ·  Ground-truth pages: {len(bench)}\n")

    # Per-detector aggregate accuracy
    lines.append("## Aggregate accuracy across all (page, symbol) pairs\n")
    lines.append("| Detector | Mean accuracy | Total runtime | Total cost | Errors |")
    lines.append("|---|---|---|---|---|")
    for det in detectors:
        accs = []
        total_t = 0.0
        total_c = 0.0
        n_err = 0
        for (pdf_path, gt) in bench:
            for sym, truth in gt.symbols.items():
                if truth < 0:  # skipped during ground truth
                    continue
                key = (det.name, gt.confirmed_at + "|" + gt.pdf_name + "|p" + str(gt.page_nr), sym)
                if key not in results:
                    continue
                pred, rt, cost, err = results[key]
                accs.append(_accuracy(pred, truth))
                total_t += rt
                total_c += cost
                if err:
                    n_err += 1
        mean = sum(accs) / max(1, len(accs))
        lines.append(f"| `{det.name}` | {mean*100:.1f}% | {total_t:.1f}s | ${total_c:.2f} | {n_err} |")

    # Per-PDF breakdown
    lines.append("\n## Per-PDF accuracy\n")
    lines.append("| Detector | " + " | ".join(set(gt.pdf_name for _, gt in bench)) + " |")
    lines.append("|---" * (1 + len(set(gt.pdf_name for _, gt in bench))) + "|")

    pdf_groups: dict[str, list[GroundTruth]] = {}
    for _, gt in bench:
        pdf_groups.setdefault(gt.pdf_name, []).append(gt)

    for det in detectors:
        row = [f"`{det.name}`"]
        for pdf_name in pdf_groups:
            accs = []
            for gt in pdf_groups[pdf_name]:
                for sym, truth in gt.symbols.items():
                    if truth < 0:
                        continue
                    key = (det.name, gt.confirmed_at + "|" + gt.pdf_name + "|p" + str(gt.page_nr), sym)
                    if key not in results:
                        continue
                    pred, *_ = results[key]
                    accs.append(_accuracy(pred, truth))
            mean = sum(accs) / max(1, len(accs))
            row.append(f"{mean*100:.1f}%")
        lines.append("| " + " | ".join(row) + " |")

    # Per-symbol detail (verbose)
    lines.append("\n## Per-page, per-symbol detail\n")
    for pdf_path, gt in bench:
        lines.append(f"### {gt.pdf_name} — page {gt.page_nr}")
        lines.append(f"_{gt.notes}_\n")
        lines.append("| Symbol | Truth | " + " | ".join(d.name for d in detectors) + " |")
        lines.append("|---" * (2 + len(detectors)) + "|")
        for sym, truth in sorted(gt.symbols.items()):
            row = [f"`{sym}`", str(truth)]
            for det in detectors:
                key = (det.name, gt.confirmed_at + "|" + gt.pdf_name + "|p" + str(gt.page_nr), sym)
                if key not in results:
                    row.append("—")
                    continue
                pred, rt, cost, err = results[key]
                if err:
                    row.append(f"⚠️{pred}")
                else:
                    row.append(f"{pred} ({_accuracy(pred, truth)*100:.0f}%)")
            lines.append("| " + " | ".join(row) + " |")
        lines.append("")

    report_path.write_text("\n".join(lines))
    print(f"\nReport: {report_path}")


if __name__ == "__main__":
    main()
