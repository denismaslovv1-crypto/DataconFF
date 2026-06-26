from __future__ import annotations

import argparse
from pathlib import Path

from datacon_workflow.evaluation.chemx_eval import evaluate_predictions


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate Benzimidazoles ChemX predictions.")
    parser.add_argument("--domain", choices=["benzimidazoles"], default="benzimidazoles")
    parser.add_argument("--predictions", type=Path, default=Path("outputs/benzimidazoles/predictions.csv"))
    parser.add_argument("--ground-truth", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/benzimidazoles"))
    args = parser.parse_args()
    result = evaluate_predictions(args.predictions, args.ground_truth, args.output_dir)
    print(f"Macro-F1: {result['macro_f1']:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
