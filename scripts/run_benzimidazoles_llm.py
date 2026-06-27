from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

from datacon_workflow.evaluation.chemx_eval import evaluate_predictions
from datacon_workflow.export.llm_chemx_csv import write_llm_predictions
from datacon_workflow.extraction.evidence_selector import compress_benzimidazole_evidence
from datacon_workflow.extraction.evidence_selector import select_benzimidazole_evidence, write_evidence_bundle
from datacon_workflow.extraction.llm_batch_runner import (
    apply_evidence_slice,
    read_dedup_report,
    replay_path_for_pdf,
    run_llm_batches,
)
from datacon_workflow.extraction.llm_extractor import LLMExtractionConfig
from pdf_extraction.exporters import write_document_json
from pdf_extraction.models import stable_pdf_stem
from pdf_extraction.pipeline import parse_pdf


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run Benzimidazoles Evidence Selector -> LLM Extractor -> Validator -> CSV."
    )
    parser.add_argument("--pdf-dir", type=Path, help="Directory with Benzimidazoles PDFs.")
    parser.add_argument("--pdf", action="append", type=Path, dest="pdfs", help="Single PDF. Repeatable.")
    parser.add_argument("--out-dir", type=Path, default=Path("outputs/benzimidazoles_llm"))
    parser.add_argument("--replay-dir", type=Path, help="Optional directory containing <pdf-stem>.llm.json responses.")
    parser.add_argument(
        "--llm-mode",
        choices=["live", "disabled"],
        default="live",
        help="Use disabled for fast local pipeline checks without remote LLM calls. Replay is still controlled by --replay-dir.",
    )
    parser.add_argument("--evidence-batch-size", type=int, default=15, help="Selected evidence chunks per live LLM call.")
    parser.add_argument(
        "--max-evidence-chunks",
        type=int,
        help="Cap selected evidence chunks before LLM batching. Useful for final live smoke runs.",
    )
    parser.add_argument(
        "--max-concurrent-batches",
        type=int,
        default=1,
        help="Number of LLM evidence batches to run in parallel. Keep low to avoid provider rate limits.",
    )
    parser.add_argument(
        "--resume-existing-batches",
        action="store_true",
        help="Reuse existing valid llm_raw_response.json batch files instead of calling the LLM again.",
    )
    parser.add_argument(
        "--evidence-slice",
        help="Deterministic development subset after compression, using START:STOP syntax such as 0:10.",
    )
    parser.add_argument("--ground-truth", type=Path, help="Optional ChemX ground-truth CSV for post-run evaluation.")
    parser.add_argument(
        "--benchmark-id",
        action="append",
        help="Optional DOI/pdf id used only to scope evaluation, not extraction. Repeatable.",
    )
    args = parser.parse_args()
    if args.llm_mode == "disabled" and args.replay_dir is not None:
        raise ValueError("--llm-mode disabled cannot be combined with --replay-dir.")

    pdf_paths = _collect_pdf_paths(args.pdfs, args.pdf_dir)
    if not pdf_paths:
        raise FileNotFoundError("No PDF files supplied. Use --pdf or --pdf-dir.")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    summary = []
    run_started = time.perf_counter()
    _log(f"Run start: pdfs={len(pdf_paths)} out_dir={args.out_dir} llm_mode={args.llm_mode}")
    for pdf_index, pdf_path in enumerate(pdf_paths, start=1):
        article_started = time.perf_counter()
        article_dir = args.out_dir / stable_pdf_stem(pdf_path)
        article_dir.mkdir(parents=True, exist_ok=True)
        _log(f"[{pdf_index}/{len(pdf_paths)}] Start {pdf_path}")
        parse_started = time.perf_counter()
        _log(f"[{pdf_index}/{len(pdf_paths)}] Parse PDF -> {article_dir / 'parsed'}")
        document = parse_pdf(pdf_path, output_dir=article_dir / "parsed")
        write_document_json(document, article_dir / "parsed" / f"{stable_pdf_stem(pdf_path)}.raw.json")
        _log(
            f"[{pdf_index}/{len(pdf_paths)}] Parsed pages={document.page_count} "
            f"text_blocks={len(document.text_blocks)} tables={len(document.tables)} "
            f"elapsed={_elapsed(parse_started)}"
        )

        evidence_started = time.perf_counter()
        _log(f"[{pdf_index}/{len(pdf_paths)}] Select evidence")
        selected_evidence = select_benzimidazole_evidence(document)
        compressed_evidence = compress_benzimidazole_evidence(selected_evidence, args.max_evidence_chunks)
        evidence = apply_evidence_slice(compressed_evidence, args.evidence_slice)
        write_evidence_bundle(evidence, article_dir / "evidence_bundle.json")
        _log(
            f"[{pdf_index}/{len(pdf_paths)}] Evidence selected={len(selected_evidence)} "
            f"compressed={len(compressed_evidence)} running={len(evidence)} "
            f"slice={args.evidence_slice or 'none'} bundle={article_dir / 'evidence_bundle.json'} "
            f"elapsed={_elapsed(evidence_started)}"
        )

        replay_path = replay_path_for_pdf(args.replay_dir, pdf_path)
        llm_config = LLMExtractionConfig() if args.llm_mode == "disabled" else None
        batch_count = (len(evidence) + max(1, args.evidence_batch_size) - 1) // max(1, args.evidence_batch_size)
        llm_started = time.perf_counter()
        _log(
            f"[{pdf_index}/{len(pdf_paths)}] LLM stage mode={'replay' if replay_path else args.llm_mode} "
            f"batch_size={args.evidence_batch_size} batches={batch_count} "
            f"concurrency={args.max_concurrent_batches} resume={args.resume_existing_batches}"
        )
        llm_run = run_llm_batches(
            evidence,
            article_dir,
            args.evidence_batch_size,
            replay_path,
            args.max_concurrent_batches,
            args.resume_existing_batches,
            config=llm_config,
            progress=lambda message: _log(f"[{pdf_index}/{len(pdf_paths)}] {message}"),
        )
        _log(
            f"[{pdf_index}/{len(pdf_paths)}] LLM completed status={llm_run.status} "
            f"validated_records={len(llm_run.records)} elapsed={_elapsed(llm_started)}"
        )
        records = llm_run.records
        export_started = time.perf_counter()
        _log(f"[{pdf_index}/{len(pdf_paths)}] Export predictions")
        csv_path, sidecar_path = write_llm_predictions(records, evidence, article_dir)
        dedup_report = read_dedup_report(article_dir / "dedup_report.json")
        _log(
            f"[{pdf_index}/{len(pdf_paths)}] Exported raw={len(records)} "
            f"unique={dedup_report.get('output_records', len(records))} "
            f"duplicates={dedup_report.get('exact_duplicates_merged', 0)} "
            f"conflicts={dedup_report.get('conflict_count', 0)} "
            f"csv={csv_path} elapsed={_elapsed(export_started)}"
        )
        status = llm_run.status
        metrics = None
        if args.ground_truth:
            eval_started = time.perf_counter()
            _log(f"[{pdf_index}/{len(pdf_paths)}] Evaluate predictions")
            metrics = evaluate_predictions(
                csv_path,
                args.ground_truth,
                article_dir,
                benchmark_pdf_ids=_normalized_benchmark_ids(args.benchmark_id),
                benchmark_pdf_name=stable_pdf_stem(pdf_path),
            )
            _log(
                f"[{pdf_index}/{len(pdf_paths)}] Evaluation macro_f1={metrics['macro_f1']:.4f} "
                f"predictions={metrics['prediction_count']} truth={metrics['ground_truth_count']} "
                f"elapsed={_elapsed(eval_started)}"
            )

        summary.append(
            {
                "pdf": str(pdf_path),
                "llm_mode": "replay" if replay_path is not None else args.llm_mode,
                "status": status,
                "selected_evidence_chunks": len(selected_evidence),
                "compressed_evidence_chunks": len(compressed_evidence),
                "evidence_chunks": len(evidence),
                "max_evidence_chunks": args.max_evidence_chunks,
                "evidence_slice": args.evidence_slice,
                "evidence_batch_size": args.evidence_batch_size,
                "max_concurrent_batches": args.max_concurrent_batches,
                "batch_count": len(llm_run.batches),
                "records": len(records),
                "exported_records": dedup_report.get("output_records", len(records)),
                "exact_duplicates_merged": dedup_report.get("exact_duplicates_merged", 0),
                "conflict_count": dedup_report.get("conflict_count", 0),
                "warnings": llm_run.warnings,
                "predictions_csv": str(csv_path),
                "sidecar_json": str(sidecar_path),
                "dedup_report": str(article_dir / "dedup_report.json"),
                "metrics": metrics,
            }
        )
        _log(
            f"{pdf_path.name}: {len(evidence)} evidence chunks, "
            f"{len(records)} raw records, {dedup_report.get('output_records', len(records))} exported, status={status}"
        )
        if metrics:
            _log(f"  Macro-F1: {metrics['macro_f1']:.4f}")
        if llm_run.warnings:
            _log(f"  warning: {llm_run.warnings[0]}")
        _log(f"[{pdf_index}/{len(pdf_paths)}] Done elapsed={_elapsed(article_started)}")

    (args.out_dir / "run_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    _log(f"Summary: {args.out_dir / 'run_summary.json'}")
    _log(f"Run done elapsed={_elapsed(run_started)}")
    return 0


def _collect_pdf_paths(pdfs: list[Path] | None, pdf_dir: Path | None) -> list[Path]:
    paths = list(pdfs or [])
    if pdf_dir is not None:
        paths.extend(sorted(pdf_dir.glob("*.pdf")))
    return paths


def _normalized_benchmark_ids(values: list[str] | None) -> set[str] | None:
    if not values:
        return None
    return {value.strip().lower() for value in values if value.strip()}


def _log(message: str) -> None:
    print(f"[{time.strftime('%H:%M:%S')}] {message}", flush=True)


def _elapsed(started: float) -> str:
    return f"{time.perf_counter() - started:.1f}s"


if __name__ == "__main__":
    raise SystemExit(main())
