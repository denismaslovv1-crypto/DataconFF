from __future__ import annotations

import argparse
from pathlib import Path

from datacon_workflow.evaluation.harness import run_benzimidazoles_harness, write_harness_summary_csv


DEFAULT_PDFS = [
    Path("data/chemx/benzimidazoles/pdfs/janupally2014.pdf"),
    Path("data/chemx/benzimidazoles/pdfs/d2ra06667j.pdf"),
]


def main() -> int:
    parser = argparse.ArgumentParser(description="Run the staged Benzimidazoles evaluation harness on 2-3 PDFs.")
    parser.add_argument("--pdf", action="append", type=Path, dest="pdfs", help="PDF to include. Repeat 2-3 times.")
    parser.add_argument(
        "--ground-truth",
        type=Path,
        default=Path("data/chemx/benzimidazoles/ground_truth.csv"),
    )
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/benzimidazoles/harness"))
    parser.add_argument("--selector-replay-dir", type=Path, help="Optional replay JSON directory for selector outputs.")
    parser.add_argument("--extractor-replay-dir", type=Path, help="Optional replay JSON directory for extractor outputs.")
    args = parser.parse_args()

    pdfs = args.pdfs or DEFAULT_PDFS
    report = run_benzimidazoles_harness(
        pdf_paths=pdfs,
        ground_truth_csv=args.ground_truth,
        output_dir=args.output_dir,
        selector_replay_dir=args.selector_replay_dir,
        extractor_replay_dir=args.extractor_replay_dir,
    )
    write_harness_summary_csv(report, args.output_dir / "article_summary.csv")

    print(f"Harness report: {args.output_dir / 'harness_report.json'}")
    print(f"Combined Macro-F1: {report['combined']['metrics']['macro_f1']:.4f}")
    print(f"Ready for next stage: {report['ready_for_next_stage']}")
    for name, value in report["criteria"].items():
        print(f"{name}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
