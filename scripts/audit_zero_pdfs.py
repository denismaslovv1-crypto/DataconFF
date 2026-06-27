from __future__ import annotations

import argparse
import csv
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


AUDIT_COLUMNS = (
    "filename",
    "status",
    "prediction_row_count",
    "ground_truth_row_count",
    "row_bucket",
    "available_parse_artifacts",
    "available_evidence_artifacts",
    "parsed_text_blocks",
    "parsed_tables",
    "evidence_chunks",
    "raw_candidates",
    "validated_records",
    "validation_errors",
    "likely_failure_stage",
    "recommended_next_debug_action",
)

FAILURE_NO_PARSED = "no parsed artifact"
FAILURE_NO_TABLES_TEXT = "parse exists but no tables/text"
FAILURE_NO_EVIDENCE = "tables/text exist but no evidence"
FAILURE_NO_CANDIDATES = "evidence exists but no raw candidates"
FAILURE_ZERO_EXPORT = "candidates exist but validation/export produced zero rows"
FAILURE_EXPECTED_ZERO = "expected zero-row / no GT records"
FAILURE_UNKNOWN = "unknown"


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audit zero-row and low-row PDFs from an existing Benzimidazoles full-run output directory."
    )
    parser.add_argument("output_dir", type=Path, help="Existing output directory, e.g. outputs\\benzimidazoles_full_rules")
    parser.add_argument(
        "--low-row-threshold",
        type=int,
        default=5,
        help="Nonzero prediction rows below this value are marked low-row. Default: 5.",
    )
    args = parser.parse_args()

    report = build_audit(args.output_dir, low_row_threshold=args.low_row_threshold)
    write_audit_files(args.output_dir, report)
    print_summary(report, args.output_dir)
    return 0


def build_audit(output_dir: Path, low_row_threshold: int = 5) -> dict[str, Any]:
    article_summary_path = output_dir / "article_summary.csv"
    if not article_summary_path.exists():
        raise SystemExit(f"Missing required article_summary.csv: {article_summary_path}")

    article_rows = _read_csv_dicts(article_summary_path)
    audit_rows = [
        audit_article(row, output_dir=output_dir, low_row_threshold=low_row_threshold)
        for row in article_rows
    ]

    row_buckets = Counter(row["row_bucket"] for row in audit_rows)
    failure_stages = Counter(row["likely_failure_stage"] for row in audit_rows)
    metrics = _read_json(output_dir / "metrics.json")
    field_metrics = _read_csv_dicts(output_dir / "field_metrics.csv") if (output_dir / "field_metrics.csv").exists() else []

    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "output_dir": str(output_dir),
        "source_files": {
            "article_summary_csv": str(article_summary_path),
            "metrics_json": str(output_dir / "metrics.json") if (output_dir / "metrics.json").exists() else "",
            "field_metrics_csv": str(output_dir / "field_metrics.csv") if (output_dir / "field_metrics.csv").exists() else "",
        },
        "low_row_threshold": low_row_threshold,
        "summary": {
            "pdf_count": len(audit_rows),
            "zero_row": row_buckets.get("zero-row", 0),
            "expected_zero": row_buckets.get("expected-zero", 0),
            "low_row": row_buckets.get("low-row", 0),
            "ok": row_buckets.get("ok", 0),
            "failure_stages": dict(sorted(failure_stages.items())),
            "macro_f1": metrics.get("macro_f1"),
            "prediction_count": metrics.get("prediction_count"),
            "ground_truth_count": metrics.get("ground_truth_count"),
            "field_metrics_count": len(field_metrics),
        },
        "articles": audit_rows,
    }


def audit_article(row: dict[str, str], output_dir: Path, low_row_threshold: int) -> dict[str, Any]:
    filename = Path(row.get("pdf", "")).name or row.get("pdf", "")
    article_dir = _resolve_article_dir(row.get("output_dir", ""), output_dir)
    pred_rows = _to_int(row.get("pred_rows"), default=_count_csv_rows(article_dir / "predictions.csv"))
    gt_rows = _to_int(row.get("gt_rows"))

    parse_artifacts = _find_parse_artifacts(article_dir)
    evidence_artifacts = _find_evidence_artifacts(article_dir)
    confidence = _read_json(article_dir / "confidence_report.json")
    signals = confidence.get("signals", {}) if isinstance(confidence.get("signals"), dict) else {}
    parsed_counts = _parsed_counts(article_dir, parse_artifacts)

    parsed_text_blocks = _signal_or_count(signals, "parsed_text_blocks", parsed_counts.get("text_blocks", 0))
    parsed_tables = _signal_or_count(signals, "parsed_tables", parsed_counts.get("tables", 0))
    evidence_chunks = _signal_or_count(signals, "evidence_chunks", _json_list_count(article_dir / "rule_evidence.json"))
    raw_candidates = _signal_or_count(signals, "raw_records", _json_list_count(article_dir / "rules" / "predictions.json"))
    validated_records = _signal_or_count(signals, "validated_records", pred_rows)
    validation_errors = _signal_or_count(signals, "validation_errors", 0)

    failure_stage = classify_failure_stage(
        has_parse_artifacts=bool(parse_artifacts),
        parsed_text_blocks=parsed_text_blocks,
        parsed_tables=parsed_tables,
        evidence_chunks=evidence_chunks,
        raw_candidates=raw_candidates,
        prediction_rows=pred_rows,
        ground_truth_rows=gt_rows,
    )

    return {
        "filename": filename,
        "status": row.get("status", ""),
        "prediction_row_count": pred_rows,
        "ground_truth_row_count": gt_rows,
        "row_bucket": classify_row_bucket(pred_rows, low_row_threshold, gt_rows),
        "available_parse_artifacts": ";".join(parse_artifacts),
        "available_evidence_artifacts": ";".join(evidence_artifacts),
        "parsed_text_blocks": parsed_text_blocks,
        "parsed_tables": parsed_tables,
        "evidence_chunks": evidence_chunks,
        "raw_candidates": raw_candidates,
        "validated_records": validated_records,
        "validation_errors": validation_errors,
        "likely_failure_stage": failure_stage,
        "recommended_next_debug_action": recommend_next_action(failure_stage),
    }


def classify_row_bucket(prediction_rows: int, low_row_threshold: int = 5, ground_truth_rows: int | None = None) -> str:
    if prediction_rows == 0 and ground_truth_rows == 0:
        return "expected-zero"
    if prediction_rows == 0:
        return "zero-row"
    if prediction_rows < low_row_threshold:
        return "low-row"
    return "ok"


def classify_failure_stage(
    *,
    has_parse_artifacts: bool,
    parsed_text_blocks: int,
    parsed_tables: int,
    evidence_chunks: int,
    raw_candidates: int,
    prediction_rows: int,
    ground_truth_rows: int | None = None,
) -> str:
    if prediction_rows == 0 and ground_truth_rows == 0:
        return FAILURE_EXPECTED_ZERO
    if prediction_rows > 0:
        return FAILURE_UNKNOWN
    if not has_parse_artifacts:
        return FAILURE_NO_PARSED
    if parsed_text_blocks == 0 and parsed_tables == 0:
        return FAILURE_NO_TABLES_TEXT
    if evidence_chunks == 0:
        return FAILURE_NO_EVIDENCE
    if raw_candidates == 0:
        return FAILURE_NO_CANDIDATES
    return FAILURE_ZERO_EXPORT


def recommend_next_action(failure_stage: str) -> str:
    if failure_stage == FAILURE_NO_PARSED:
        return "Inspect parser stdout/stderr and rerun only the parser for this PDF."
    if failure_stage == FAILURE_NO_TABLES_TEXT:
        return "Open the raw parser JSON and PDF pages to check scanned/column layout issues."
    if failure_stage == FAILURE_NO_EVIDENCE:
        return "Inspect parsed tables/text for MIC, pMIC, bacteria, and compound labels missed by evidence selection."
    if failure_stage == FAILURE_NO_CANDIDATES:
        return "Inspect rule_evidence.json against rule extractor patterns for unsupported table/text layouts."
    if failure_stage == FAILURE_ZERO_EXPORT:
        return "Inspect confidence_report.json validation signals and rule evidence to see why candidates were rejected."
    if failure_stage == FAILURE_EXPECTED_ZERO:
        return "No extraction debug needed; the run has zero ground-truth rows for this PDF."
    return "Review artifact counts and per-article stdout/stderr to choose the next focused debug path."


def write_audit_files(output_dir: Path, report: dict[str, Any]) -> None:
    rows = report["articles"]
    csv_path = output_dir / "zero_pdf_audit.csv"
    json_path = output_dir / "zero_pdf_audit.json"
    md_path = output_dir / "zero_pdf_audit.md"

    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=AUDIT_COLUMNS, extrasaction="raise")
        writer.writeheader()
        writer.writerows(rows)

    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_render_markdown(report), encoding="utf-8")


def print_summary(report: dict[str, Any], output_dir: Path) -> None:
    summary = report["summary"]
    print(f"Audit written: {output_dir / 'zero_pdf_audit.csv'}")
    print(f"Audit written: {output_dir / 'zero_pdf_audit.json'}")
    print(f"Audit written: {output_dir / 'zero_pdf_audit.md'}")
    print(
        "Rows: "
        f"zero-row={summary['zero_row']}, "
        f"expected-zero={summary['expected_zero']}, "
        f"low-row={summary['low_row']}, "
        f"ok={summary['ok']}"
    )
    print("Top failure stages:")
    for stage, count in Counter(row["likely_failure_stage"] for row in report["articles"]).most_common():
        print(f"- {stage}: {count}")


def _render_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    failure_counts = Counter(row["likely_failure_stage"] for row in report["articles"])
    lines = [
        "# Zero PDF Audit",
        "",
        f"- Output directory: `{report['output_dir']}`",
        f"- PDFs audited: {summary['pdf_count']}",
        f"- Zero-row PDFs: {summary['zero_row']}",
        f"- Expected zero-row PDFs: {summary['expected_zero']}",
        f"- Low-row PDFs: {summary['low_row']}",
        f"- OK PDFs: {summary['ok']}",
        f"- Macro-F1: {summary['macro_f1']}",
        "",
        "## Failure Stages",
        "",
    ]
    for stage, count in failure_counts.most_common():
        lines.append(f"- {stage}: {count}")
    lines.extend(
        [
            "",
            "## Zero And Low Row PDFs",
            "",
            "| filename | rows | gt rows | bucket | likely failure stage | next debug action |",
            "|---|---:|---:|---|---|---|",
        ]
    )
    for row in report["articles"]:
        if row["row_bucket"] in {"zero-row", "expected-zero", "low-row"}:
            lines.append(
                "| {filename} | {rows} | {gt_rows} | {bucket} | {stage} | {action} |".format(
                    filename=row["filename"],
                    rows=row["prediction_row_count"],
                    gt_rows=row["ground_truth_row_count"],
                    bucket=row["row_bucket"],
                    stage=row["likely_failure_stage"],
                    action=row["recommended_next_debug_action"],
                )
            )
    lines.append("")
    return "\n".join(lines)


def _resolve_article_dir(value: str, output_dir: Path) -> Path:
    if not value:
        return output_dir
    path = Path(value)
    if path.is_absolute():
        return path
    return path if path.exists() else output_dir / path.name


def _find_parse_artifacts(article_dir: Path) -> list[str]:
    parsed_dir = article_dir / "parsed"
    if not parsed_dir.exists():
        return []
    return sorted(str(path.relative_to(article_dir)) for path in parsed_dir.rglob("*") if path.is_file())


def _find_evidence_artifacts(article_dir: Path) -> list[str]:
    names = [
        "rule_evidence.json",
        "evidence.json",
        "evidence_bundle.json",
        "llm_evidence_bundle.json",
        "confidence_report.json",
        "dedup_report.json",
        "predictions_with_evidence.json",
        "rules/predictions.json",
        "rules/predictions.csv",
    ]
    return [name for name in names if (article_dir / name).exists()]


def _parsed_counts(article_dir: Path, parse_artifacts: list[str]) -> dict[str, int]:
    counts = {"text_blocks": 0, "tables": 0}
    for artifact in parse_artifacts:
        if not artifact.endswith(".raw.json"):
            continue
        raw_path = article_dir / artifact
        break
    else:
        return counts
    try:
        payload = json.loads(raw_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return counts
    if not isinstance(payload, dict):
        return counts
    counts["text_blocks"] = len(payload.get("text_blocks") or [])
    counts["tables"] = len(payload.get("tables") or [])
    return counts


def _signal_or_count(signals: dict[str, Any], key: str, fallback: int) -> int:
    if key in signals:
        return _to_int(signals.get(key), fallback)
    return fallback


def _json_list_count(path: Path) -> int:
    if not path.exists():
        return 0
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return 0
    return len(payload) if isinstance(payload, list) else 0


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _read_csv_dicts(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _count_csv_rows(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open(encoding="utf-8", newline="") as handle:
        return sum(1 for _row in csv.DictReader(handle))


def _to_int(value: object, default: int = 0) -> int:
    try:
        if value in (None, ""):
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


if __name__ == "__main__":
    raise SystemExit(main())
