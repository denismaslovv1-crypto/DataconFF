from __future__ import annotations

import csv
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from datacon_workflow.domains.benzimidazoles import BenzimidazoleRawRecord, BenzimidazoleRecord
from datacon_workflow.evaluation.chemx_eval import evaluate_predictions
from datacon_workflow.export.chemx_csv import write_predictions
from datacon_workflow.extraction.evidence_builder import EvidenceChunk, build_evidence_chunks
from datacon_workflow.extraction.llm_extractor import parse_llm_json_array
from datacon_workflow.extraction.rule_extractor import extract_records
from datacon_workflow.normalization.records import normalize_record
from datacon_workflow.validation.schema_validator import validate_records
from pdf_extraction.exporters import write_document_json
from pdf_extraction.models import ParsedPdfDocument, stable_pdf_stem
from pdf_extraction.pipeline import parse_pdf


@dataclass
class StageResult:
    name: str
    status: str = "ok"
    metrics: dict[str, Any] = field(default_factory=dict)
    artifacts: dict[str, str] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)


@dataclass
class ArticleHarnessState:
    pdf_path: Path
    output_dir: Path
    parsed_document: ParsedPdfDocument | None = None
    rule_evidence_chunks: list[EvidenceChunk] = field(default_factory=list)
    selected_evidence_chunks: list[EvidenceChunk] = field(default_factory=list)
    rule_raw_records: list[BenzimidazoleRawRecord] = field(default_factory=list)
    llm_raw_records: list[BenzimidazoleRawRecord] = field(default_factory=list)
    normalized_records: list[BenzimidazoleRecord] = field(default_factory=list)
    validation_errors: list[str] = field(default_factory=list)
    prediction_csv: Path | None = None
    prediction_json: Path | None = None
    metrics: dict[str, Any] | None = None
    benchmark_pdf_ids: set[str] | None = None
    stages: list[StageResult] = field(default_factory=list)


def run_local_parser(pdf_path: Path, output_dir: Path) -> tuple[ParsedPdfDocument, StageResult]:
    parsed_dir = output_dir / "parsed"
    parsed_dir.mkdir(parents=True, exist_ok=True)
    document = parse_pdf(pdf_path, output_dir=parsed_dir)
    raw_json = parsed_dir / f"{stable_pdf_stem(pdf_path)}.raw.json"
    write_document_json(document, raw_json)
    return document, StageResult(
        name="run_local_parser",
        metrics={
            "pages": document.page_count,
            "text_blocks": len(document.text_blocks),
            "tables": len(document.tables),
        },
        artifacts={"raw_json": str(raw_json)},
    )


def run_rule_based_evidence(document: ParsedPdfDocument, output_dir: Path) -> tuple[list[EvidenceChunk], StageResult]:
    chunks = build_evidence_chunks(document)
    path = output_dir / "rule_evidence.json"
    path.write_text(
        json.dumps([chunk.model_dump(mode="json") for chunk in chunks], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return chunks, StageResult(
        name="run_rule_based_evidence",
        metrics={"evidence_chunks": len(chunks)},
        artifacts={"evidence_json": str(path)},
    )


def run_llm_evidence_selector(
    chunks: list[EvidenceChunk],
    output_dir: Path,
    selector_replay_path: Path | None = None,
) -> tuple[list[EvidenceChunk], StageResult]:
    if selector_replay_path is None or not selector_replay_path.exists():
        selected = chunks
        status = "passthrough"
        notes = ["No selector replay file was supplied; all rule evidence chunks were retained."]
    else:
        indexes = _load_selector_indexes(selector_replay_path)
        selected = [chunks[index] for index in indexes if 0 <= index < len(chunks)]
        status = "replay"
        notes = [f"Loaded selected chunk indexes from {selector_replay_path}."]

    path = output_dir / "llm_selected_evidence.json"
    path.write_text(
        json.dumps([chunk.model_dump(mode="json") for chunk in selected], ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    baseline_keys = _record_keys(extract_records(chunks))
    selected_keys = _record_keys(extract_records(selected))
    recall_ratio = 1.0 if not baseline_keys else len(baseline_keys & selected_keys) / len(baseline_keys)
    return selected, StageResult(
        name="run_llm_evidence_selector",
        status=status,
        metrics={
            "input_chunks": len(chunks),
            "selected_chunks": len(selected),
            "rule_record_recall_ratio": recall_ratio,
            "recall_not_reduced": recall_ratio >= 1.0,
        },
        artifacts={"selected_evidence_json": str(path)},
        notes=notes,
    )


def run_llm_extractor(
    chunks: list[EvidenceChunk],
    output_dir: Path,
    extractor_replay_path: Path | None = None,
) -> tuple[list[BenzimidazoleRawRecord], StageResult]:
    if extractor_replay_path is None or not extractor_replay_path.exists():
        path = output_dir / "llm_raw_records.json"
        path.write_text("[]\n", encoding="utf-8")
        return [], StageResult(
            name="run_llm_extractor",
            status="not_configured",
            metrics={
                "responses_total": 0,
                "valid_json_responses": 0,
                "valid_json_rate": None,
                "records": 0,
                "unsupported_or_hallucinated_responses": 0,
            },
            artifacts={"llm_records_json": str(path)},
            notes=["No extractor replay file was supplied; no remote extraction agent was called."],
        )

    responses = _load_extractor_responses(extractor_replay_path)
    valid_json = 0
    unsupported = 0
    records: list[BenzimidazoleRawRecord] = []
    errors: list[str] = []
    for response in responses:
        index = int(response["chunk_index"])
        if not 0 <= index < len(chunks):
            unsupported += 1
            errors.append(f"chunk_index out of range: {index}")
            continue
        try:
            parsed = parse_llm_json_array(str(response["response"]), chunks[index])
        except (json.JSONDecodeError, ValueError) as exc:
            unsupported += 1
            errors.append(f"chunk {index}: {exc}")
            continue
        valid_json += 1
        records.extend(parsed)

    path = output_dir / "llm_raw_records.json"
    path.write_text(json.dumps([record.model_dump(mode="json") for record in records], ensure_ascii=False, indent=2), encoding="utf-8")
    error_path = output_dir / "llm_extractor_errors.json"
    error_path.write_text(json.dumps(errors, ensure_ascii=False, indent=2), encoding="utf-8")
    total = len(responses)
    return records, StageResult(
        name="run_llm_extractor",
        status="replay",
        metrics={
            "responses_total": total,
            "valid_json_responses": valid_json,
            "valid_json_rate": valid_json / total if total else None,
            "records": len(records),
            "unsupported_or_hallucinated_responses": unsupported,
        },
        artifacts={"llm_records_json": str(path), "errors_json": str(error_path)},
    )


def run_validator(
    raw_records: list[BenzimidazoleRawRecord],
    output_dir: Path,
) -> tuple[list[BenzimidazoleRecord], list[str], StageResult]:
    output_dir.mkdir(parents=True, exist_ok=True)
    candidates: list[BenzimidazoleRecord] = []
    errors: list[str] = []
    for index, raw in enumerate(raw_records):
        try:
            candidates.append(normalize_record(raw))
        except (ValidationError, ValueError) as exc:
            errors.append(f"record {index}: normalization failed: {exc}")
    accepted, validation_errors = validate_records(candidates)
    errors.extend(validation_errors)
    error_path = output_dir / "validation_errors.json"
    error_path.write_text(json.dumps(errors, ensure_ascii=False, indent=2), encoding="utf-8")
    return accepted, errors, StageResult(
        name="run_validator",
        metrics={
            "candidate_records": len(raw_records),
            "accepted_records": len(accepted),
            "rejected_records": len(errors),
            "rejection_rate": len(errors) / len(raw_records) if raw_records else 0.0,
        },
        artifacts={"validation_errors_json": str(error_path)},
    )


def run_exporter(records: list[BenzimidazoleRecord], output_dir: Path) -> tuple[Path, Path, StageResult]:
    csv_path, json_path = write_predictions(records, output_dir)
    return csv_path, json_path, StageResult(
        name="run_exporter",
        metrics={"exported_records": len(records)},
        artifacts={"predictions_csv": str(csv_path), "predictions_json": str(json_path)},
    )


def run_chemx_eval(
    predictions_csv: Path,
    ground_truth_csv: Path,
    output_dir: Path,
    benchmark_pdf_ids: set[str] | None,
    benchmark_pdf_name: str | None = None,
) -> tuple[dict[str, Any], StageResult]:
    metrics = evaluate_predictions(
        predictions_csv,
        ground_truth_csv,
        output_dir,
        benchmark_pdf_ids=benchmark_pdf_ids,
        benchmark_pdf_name=benchmark_pdf_name,
    )
    return metrics, StageResult(
        name="run_chemx_eval",
        metrics={
            "macro_f1": metrics["macro_f1"],
            "prediction_count": metrics["prediction_count"],
            "ground_truth_count": metrics["ground_truth_count"],
            "beats_single_agent_baseline": float(metrics["macro_f1"]) > 0.217,
        },
        artifacts={"metrics_json": str(output_dir / "metrics.json"), "field_metrics_csv": str(output_dir / "field_metrics.csv")},
    )


def run_article_harness(
    pdf_path: Path,
    output_dir: Path,
    ground_truth_csv: Path,
    selector_replay_path: Path | None = None,
    extractor_replay_path: Path | None = None,
) -> ArticleHarnessState:
    output_dir.mkdir(parents=True, exist_ok=True)
    state = ArticleHarnessState(pdf_path=pdf_path, output_dir=output_dir)
    state.parsed_document, stage = run_local_parser(pdf_path, output_dir)
    state.stages.append(stage)
    state.benchmark_pdf_ids = find_benchmark_pdf_ids(state.parsed_document)

    state.rule_evidence_chunks, stage = run_rule_based_evidence(state.parsed_document, output_dir)
    state.stages.append(stage)
    state.rule_raw_records = extract_records(state.rule_evidence_chunks)

    state.selected_evidence_chunks, stage = run_llm_evidence_selector(state.rule_evidence_chunks, output_dir, selector_replay_path)
    state.stages.append(stage)

    state.llm_raw_records, stage = run_llm_extractor(state.selected_evidence_chunks, output_dir, extractor_replay_path)
    state.stages.append(stage)

    raw_records = state.rule_raw_records + state.llm_raw_records
    state.normalized_records, state.validation_errors, stage = run_validator(raw_records, output_dir)
    state.stages.append(stage)

    state.prediction_csv, state.prediction_json, stage = run_exporter(state.normalized_records, output_dir)
    state.stages.append(stage)

    state.metrics, stage = run_chemx_eval(
        state.prediction_csv,
        ground_truth_csv,
        output_dir,
        state.benchmark_pdf_ids,
        benchmark_pdf_name=stable_pdf_stem(pdf_path),
    )
    state.stages.append(stage)

    _write_article_report(state)
    return state


def run_benzimidazoles_harness(
    pdf_paths: list[Path],
    ground_truth_csv: Path,
    output_dir: Path,
    selector_replay_dir: Path | None = None,
    extractor_replay_dir: Path | None = None,
) -> dict[str, Any]:
    if not 2 <= len(pdf_paths) <= 3:
        raise ValueError("The Benzimidazoles evaluation harness is intentionally scoped to 2-3 PDFs.")

    output_dir.mkdir(parents=True, exist_ok=True)
    article_states: list[ArticleHarnessState] = []
    for pdf_path in pdf_paths:
        stem = stable_pdf_stem(pdf_path)
        article_states.append(
            run_article_harness(
                pdf_path=pdf_path,
                output_dir=output_dir / stem,
                ground_truth_csv=ground_truth_csv,
                selector_replay_path=_optional_replay_path(selector_replay_dir, stem, "selector"),
                extractor_replay_path=_optional_replay_path(extractor_replay_dir, stem, "extractor"),
            )
        )

    combined_dir = output_dir / "combined"
    combined_ids: set[str] = set()
    combined_records: list[BenzimidazoleRecord] = []
    for state in article_states:
        combined_records.extend(state.normalized_records)
        if state.benchmark_pdf_ids:
            combined_ids.update(state.benchmark_pdf_ids)
    combined_csv, combined_json, export_stage = run_exporter(combined_records, combined_dir)
    combined_metrics, eval_stage = run_chemx_eval(combined_csv, ground_truth_csv, combined_dir, combined_ids or None)
    hallucination_probe_passed = _validator_hallucination_probe(combined_dir / "hallucination_probe")

    report = {
        "criteria": {
            "evidence_selector_does_not_reduce_recall": all(
                bool(_stage(state, "run_llm_evidence_selector").metrics["recall_not_reduced"])
                for state in article_states
            ),
            "extraction_agent_valid_json_gt_95_percent": _valid_json_gate(article_states),
            "validator_rejects_hallucinated_values": hallucination_probe_passed,
            "macro_f1_gt_0_217": float(combined_metrics["macro_f1"]) > 0.217,
        },
        "articles": [_article_summary(state) for state in article_states],
        "combined": {
            "stages": [export_stage.__dict__, eval_stage.__dict__],
            "metrics": combined_metrics,
            "artifacts": {"predictions_csv": str(combined_csv), "predictions_json": str(combined_json)},
        },
    }
    report["ready_for_next_stage"] = all(value is True for value in report["criteria"].values())
    report_path = output_dir / "harness_report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def find_benchmark_pdf_ids(document: ParsedPdfDocument) -> set[str] | None:
    identifiers: set[str] = set()
    for block in document.text_blocks:
        for doi in re.findall(r"10\.\d{4,9}/[-._;()/:A-Z0-9]+", block.text, flags=re.I):
            identifiers.add(doi.rstrip(".,;)]").lower())
    return identifiers or None


def _record_keys(records: list[BenzimidazoleRawRecord]) -> set[tuple[str, str, str, str, str, str]]:
    return {
        (
            record.compound_id,
            record.target_type.upper(),
            record.target_relation,
            record.target_value,
            record.target_units,
            record.bacteria,
        )
        for record in records
    }


def _load_selector_indexes(path: Path) -> list[int]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        payload = payload.get("selected_chunk_indexes", [])
    if not isinstance(payload, list):
        raise ValueError("Selector replay must be a JSON list or an object with selected_chunk_indexes.")
    return [int(item["index"] if isinstance(item, dict) else item) for item in payload]


def _load_extractor_responses(path: Path) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        payload = payload.get("responses", [])
    if not isinstance(payload, list):
        raise ValueError("Extractor replay must be a JSON list or an object with responses.")
    return [dict(item) for item in payload]


def _optional_replay_path(directory: Path | None, stem: str, suffix: str) -> Path | None:
    if directory is None:
        return None
    path = directory / f"{stem}.{suffix}.json"
    return path if path.exists() else None


def _stage(state: ArticleHarnessState, name: str) -> StageResult:
    for stage in state.stages:
        if stage.name == name:
            return stage
    raise KeyError(name)


def _valid_json_gate(states: list[ArticleHarnessState]) -> bool | None:
    totals = [
        _stage(state, "run_llm_extractor").metrics["responses_total"]
        for state in states
    ]
    if sum(int(total) for total in totals) == 0:
        return None
    valid = sum(int(_stage(state, "run_llm_extractor").metrics["valid_json_responses"]) for state in states)
    total = sum(int(total) for total in totals)
    return (valid / total) > 0.95


def _validator_hallucination_probe(output_dir: Path) -> bool:
    raw = BenzimidazoleRawRecord(
        compound_id="5a",
        target_type="MIC",
        target_relation="=",
        target_value="999",
        target_units="ug/mL",
        bacteria="S. aureus",
        evidence={
            "source_file": "hallucination_probe.pdf",
            "page": 1,
            "evidence_text": "Compound 5a MIC = 4 ug/mL against S. aureus",
            "extraction_method": "harness.hallucination_probe",
            "confidence": 1,
        },
    )
    accepted, errors, _stage_result = run_validator([raw], output_dir)
    return not accepted and any("target_value is not supported" in error for error in errors)


def _article_summary(state: ArticleHarnessState) -> dict[str, Any]:
    return {
        "pdf": str(state.pdf_path),
        "benchmark_pdf_ids": sorted(state.benchmark_pdf_ids) if state.benchmark_pdf_ids else None,
        "stages": [stage.__dict__ for stage in state.stages],
        "metrics": state.metrics,
    }


def _write_article_report(state: ArticleHarnessState) -> None:
    report = _article_summary(state)
    (state.output_dir / "article_harness_report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def write_harness_summary_csv(report: dict[str, Any], path: Path) -> None:
    rows = []
    for article in report["articles"]:
        metrics = article.get("metrics") or {}
        rows.append({
            "pdf": article["pdf"],
            "macro_f1": metrics.get("macro_f1"),
            "prediction_count": metrics.get("prediction_count"),
            "ground_truth_count": metrics.get("ground_truth_count"),
        })
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["pdf", "macro_f1", "prediction_count", "ground_truth_count"])
        writer.writeheader()
        writer.writerows(rows)
