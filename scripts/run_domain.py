from __future__ import annotations

import argparse
from pathlib import Path

from datacon_workflow.orchestration import AgenticOrchestrationConfig
from datacon_workflow.orchestrator import run_benzimidazole_workflow


def main() -> int:
    parser = argparse.ArgumentParser(description="Run deterministic ChemX extraction for Benzimidazoles.")
    parser.add_argument("--domain", choices=["benzimidazoles"], default="benzimidazoles")
    parser.add_argument("--pdf", required=True, type=Path)
    parser.add_argument("--ground-truth", type=Path)
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/benzimidazoles"))
    parser.add_argument(
        "--agentic-mode",
        choices=["disabled", "replay", "live"],
        default=None,
        help="Optional controlled sidecar orchestration mode. Defaults to CHEMX_AGENTIC_MODE or disabled.",
    )
    parser.add_argument("--agentic-replay-dir", type=Path, help="Replay fixture directory for --agentic-mode replay.")
    parser.add_argument("--agentic-max-evidence", type=int, default=40, help="Maximum evidence chunks passed to sidecar workers.")
    args = parser.parse_args()
    agentic_config = None
    if args.agentic_mode is not None or args.agentic_replay_dir is not None:
        agentic_config = AgenticOrchestrationConfig(
            mode=args.agentic_mode or "replay",
            replay_dir=args.agentic_replay_dir,
            max_evidence_chunks=args.agentic_max_evidence,
        )
    state = run_benzimidazole_workflow(args.pdf, args.output_dir, args.ground_truth, agentic_config)
    print(f"Extracted {len(state.normalized_records)} validated records")
    print(f"Predictions: {state.prediction_csv}")
    if state.agentic_result:
        print(f"Agentic sidecar: {state.agentic_result.status}")
        for name, path in state.agentic_result.artifacts.items():
            print(f"{name}: {path}")
    if state.validation_errors:
        print("Rejected candidates:")
        print("\n".join(state.validation_errors))
    if state.metrics:
        print(f"Macro-F1: {state.metrics['macro_f1']:.4f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
