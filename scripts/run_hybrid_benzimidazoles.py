from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

from datacon_workflow.confidence import assess_rule_extraction_confidence
from datacon_workflow.domains.benzimidazoles import BenzimidazoleLLMRecord, BenzimidazoleRecord
from datacon_workflow.evaluation.chemx_eval import evaluate_predictions
from datacon_workflow.export.chemx_csv import write_predictions
from datacon_workflow.export.llm_chemx_csv import write_llm_predictions
from datacon_workflow.extraction.evidence_builder import build_evidence_chunks
from datacon_workflow.extraction.evidence_selector import (
    BenzimidazoleEvidence,
    compress_benzimidazole_evidence,
    select_benzimidazole_evidence,
    write_evidence_bundle,
)
from datacon_workflow.extraction.llm_batch_runner import run_llm_batches
from datacon_workflow.extraction.rule_extractor import extract_records
from datacon_workflow.normalization.records import normalize_record
from datacon_workflow.validation.schema_validator import validate_records
from pdf_extraction.exporters import write_document_json
from pdf_extraction.models import ParsedPdfDocument, stable_pdf_stem
from pdf_extraction.pipeline import parse_pdf


def main() -> int:
    parser = argparse.ArgumentParser(description="Run rules-first Benzimidazoles extraction with confidence-based LLM fallback.")
    parser.add_argument("--pdf", required=True, type=Path)
    parser.add_argument("--ground-truth", type=Path)
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/benzimidazoles_hybrid"))
    parser.add_argument("--llm-mode", choices=["auto", "always", "never"], default="auto")
    parser.add_argument("--evidence-batch-size", type=int, default=5)
    parser.add_argument("--max-evidence-chunks", type=int, default=80)
    parser.add_argument("--max-concurrent-batches", type=int, default=1)
    parser.add_argument("--resume-existing-batches", action="store_true")
    args = parser.parse_args()

    output_dir = args.output_dir
    output_dir.mkdir(parents=True, exist_ok=True)
    document = parse_pdf(args.pdf, output_dir=output_dir / "parsed")
    write_document_json(document, output_dir / "parsed" / f"{stable_pdf_stem(args.pdf)}.raw.json")

    evidence_chunks = build_evidence_chunks(document)
    (output_dir / "rule_evidence.json").write_text(
        json.dumps([chunk.model_dump(mode="json") for chunk in evidence_chunks], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    raw_records = extract_records(evidence_chunks)
    normalized_candidates = [normalize_record(raw) for raw in raw_records]
    rule_records, validation_errors = validate_records(normalized_candidates)
    write_predictions(rule_records, output_dir / "rules")

    confidence = assess_rule_extraction_confidence(document, evidence_chunks, raw_records, rule_records, validation_errors)
    (output_dir / "confidence_report.json").write_text(
        confidence.model_dump_json(indent=2),
        encoding="utf-8",
    )

    run_llm = args.llm_mode == "always" or (args.llm_mode == "auto" and confidence.should_run_llm)
    llm_records: list[BenzimidazoleLLMRecord] = []
    llm_status = "skipped"
    llm_evidence: list[BenzimidazoleEvidence] = []
    if run_llm:
        selected = select_benzimidazole_evidence(document)
        llm_evidence = compress_benzimidazole_evidence(selected, args.max_evidence_chunks)
        write_evidence_bundle(llm_evidence, output_dir / "llm_evidence_bundle.json")
        llm_run = run_llm_batches(
            llm_evidence,
            output_dir,
            args.evidence_batch_size,
            replay_path=None,
            max_concurrent_batches=args.max_concurrent_batches,
            resume_existing_batches=args.resume_existing_batches,
            progress=lambda message: print(f"  {message}"),
        )
        llm_records.extend(llm_run.records)
        llm_status = llm_run.status
    else:
        write_evidence_bundle([], output_dir / "llm_evidence_bundle.json")

    merged_records = _rule_records_as_llm(rule_records) + llm_records
    prediction_csv, sidecar_json = write_llm_predictions(merged_records, llm_evidence, output_dir)
    metrics = None
    if args.ground_truth:
        metrics = evaluate_predictions(
            prediction_csv,
            args.ground_truth,
            output_dir,
            benchmark_pdf_ids=_benchmark_pdf_ids(document),
            benchmark_pdf_name=stable_pdf_stem(args.pdf),
        )

    summary = {
        "pdf": str(args.pdf),
        "confidence": confidence.confidence,
        "llm_mode": args.llm_mode,
        "llm_ran": run_llm,
        "llm_status": llm_status,
        "rule_records": len(rule_records),
        "llm_records": len(llm_records),
        "merged_records_before_dedup": len(merged_records),
        "predictions_csv": str(prediction_csv),
        "sidecar_json": str(sidecar_json),
        "metrics": metrics,
    }
    (output_dir / "hybrid_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Confidence: {confidence.confidence}; LLM ran: {run_llm}; status={llm_status}")
    print(f"Rule records: {len(rule_records)}; LLM records: {len(llm_records)}")
    print(f"Predictions: {prediction_csv}")
    if metrics:
        print(f"Macro-F1: {metrics['macro_f1']:.4f}")
    return 0


def _rule_records_as_llm(records: list[BenzimidazoleRecord]) -> list[BenzimidazoleLLMRecord]:
    converted: list[BenzimidazoleLLMRecord] = []
    for index, record in enumerate(records, start=1):
        converted.append(
            BenzimidazoleLLMRecord(
                **record.chemx_row(),
                evidence_id=f"rule-{index}",
                warnings=["source:rule_extractor"],
            )
        )
    return converted


def _benchmark_pdf_ids(document: ParsedPdfDocument) -> set[str] | None:
    identifiers: set[str] = set()
    for block in document.text_blocks:
        for doi in re.findall(r"10\.\d{4,9}/[-._;()/:A-Z0-9]+", block.text, flags=re.I):
            identifiers.add(doi.rstrip(".,;)]").lower())
    return identifiers or None


if __name__ == "__main__":
    raise SystemExit(main())
