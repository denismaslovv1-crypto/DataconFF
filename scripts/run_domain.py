from __future__ import annotations

import argparse
from pathlib import Path

from datacon_workflow.orchestrator import run_benzimidazole_workflow


def main() -> int:
    parser = argparse.ArgumentParser(description="Run deterministic ChemX extraction for Benzimidazoles.")
    parser.add_argument("--domain", choices=["benzimidazoles"], default="benzimidazoles")
    parser.add_argument("--pdf", required=True, type=Path)
    parser.add_argument("--ground-truth", type=Path)
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/benzimidazoles"))
    args = parser.parse_args()
    state = run_benzimidazole_workflow(args.pdf, args.output_dir, args.ground_truth)
    print(f"Extracted {len(state.normalized_records)} validated records")
    print(f"Predictions: {state.prediction_csv}")
    if state.validation_errors:
        print("Rejected candidates:")
        print("\n".join(state.validation_errors))
    if state.metrics:
        print(f"Macro-F1: {state.metrics['macro_f1']:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
