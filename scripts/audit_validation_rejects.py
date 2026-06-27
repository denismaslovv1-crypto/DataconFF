from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = REPO_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from pydantic import ValidationError

from datacon_workflow.domains.benzimidazoles import (
    BenzimidazoleLLMRecord,
    BenzimidazoleRecord,
    BenzimidazoleRawRecord,
    MISSING_VALUE,
)
from datacon_workflow.export.llm_compression import compress_llm_records
from datacon_workflow.extraction.evidence_builder import build_evidence_chunks
from datacon_workflow.extraction.rule_extractor import extract_records
from datacon_workflow.normalization.records import normalize_record
from datacon_workflow.validation.schema_validator import validate_records
from pdf_extraction.models import ParsedPdfDocument


AUDIT_COLUMNS = (
    "filename",
    "row_bucket",
    "raw_candidate_count",
    "validated_record_count",
    "prediction_row_count",
    "validation_error_count",
    "top_reject_reasons",
    "rejected_fields",
    "top_rejection_categories",
    "example_reject_count",
)

REPRESENTATIVE_PDFS = (
    "antibiotics12071220.pdf",
    "acs.jafc.1c02545.pdf",
    "j.molstruc.2023.135179.pdf",
    "2023.12.si5a.0471.pdf",
    "j.bioorg.2023.106538.pdf",
)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Audit validation/export rejects for zero-row and low-row Benzimidazoles PDFs."
    )
    parser.add_argument("output_dir", type=Path)
    parser.add_argument("--include", action="append", help="PDF filename to inspect. Repeat for multiple PDFs.")
    parser.add_argument("--examples-per-pdf", type=int, default=5)
    args = parser.parse_args()

    report = build_reject_audit(args.output_dir, includes=args.include, examples_per_pdf=args.examples_per_pdf)
    write_reject_audit_files(args.output_dir, report)
    print_summary(report, args.output_dir)
    return 0


def build_reject_audit(
    output_dir: Path,
    includes: list[str] | None = None,
    examples_per_pdf: int = 5,
) -> dict[str, Any]:
    selected = _selected_articles(output_dir, includes)
    articles = [audit_article(output_dir, row, examples_per_pdf=examples_per_pdf) for row in selected]
    category_counts = Counter(
        category
        for article in articles
        for category, count in article["rejection_category_counts"].items()
        for _ in range(count)
    )
    reason_counts = Counter(
        reason
        for article in articles
        for reason, count in article["reject_reason_counts"].items()
        for _ in range(count)
    )
    return {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "output_dir": str(output_dir),
        "source_files": {
            "zero_pdf_audit_json": str(output_dir / "zero_pdf_audit.json")
            if (output_dir / "zero_pdf_audit.json").exists()
            else "",
            "article_summary_csv": str(output_dir / "article_summary.csv")
            if (output_dir / "article_summary.csv").exists()
            else "",
        },
        "selection": {
            "includes": includes or [],
            "pdf_count": len(articles),
        },
        "summary": {
            "raw_candidate_count": sum(article["raw_candidate_count"] for article in articles),
            "validated_record_count": sum(article["validated_record_count"] for article in articles),
            "prediction_row_count": sum(article["prediction_row_count"] for article in articles),
            "validation_error_count": sum(article["validation_error_count"] for article in articles),
            "top_rejection_categories": category_counts.most_common(10),
            "top_reject_reasons": reason_counts.most_common(10),
        },
        "articles": articles,
    }


def audit_article(output_dir: Path, row: dict[str, Any], examples_per_pdf: int) -> dict[str, Any]:
    filename = row["filename"]
    article_dir = _article_dir(output_dir, filename, row.get("output_dir", ""))
    raw_records = _reconstruct_raw_records(article_dir)
    normalized, rejects = _normalize_and_validate(raw_records)
    accepted, validation_errors = validate_records([item["record"] for item in normalized])
    rejects.extend(_validation_rejects(normalized, validation_errors))
    prediction_row_count = _prediction_row_count(accepted)

    reason_counts = Counter(reject["rejection_reason"] for reject in rejects)
    category_counts = Counter(category for reject in rejects for category in reject["categories"])
    rejected_fields = Counter(field for reject in rejects for field in reject["missing_or_invalid_fields"])

    return {
        "filename": filename,
        "row_bucket": row.get("row_bucket", _row_bucket(len(accepted))),
        "article_dir": str(article_dir),
        "raw_candidate_count": len(raw_records),
        "validated_record_count": len(accepted),
        "prediction_row_count": prediction_row_count,
        "validation_error_count": len(rejects),
        "top_reject_reasons": reason_counts.most_common(10),
        "rejected_fields": rejected_fields.most_common(10),
        "rejection_category_counts": dict(category_counts.most_common()),
        "reject_reason_counts": dict(reason_counts.most_common()),
        "examples": rejects[:examples_per_pdf],
        "artifact_notes": _artifact_notes(article_dir),
    }


def write_reject_audit_files(output_dir: Path, report: dict[str, Any]) -> None:
    csv_path = output_dir / "validation_reject_audit.csv"
    json_path = output_dir / "validation_reject_audit.json"
    md_path = output_dir / "validation_reject_audit.md"

    with csv_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=AUDIT_COLUMNS, extrasaction="raise")
        writer.writeheader()
        for article in report["articles"]:
            writer.writerow(
                {
                    "filename": article["filename"],
                    "row_bucket": article["row_bucket"],
                    "raw_candidate_count": article["raw_candidate_count"],
                    "validated_record_count": article["validated_record_count"],
                    "prediction_row_count": article["prediction_row_count"],
                    "validation_error_count": article["validation_error_count"],
                    "top_reject_reasons": _format_counts(article["top_reject_reasons"]),
                    "rejected_fields": _format_counts(article["rejected_fields"]),
                    "top_rejection_categories": _format_counts(article["rejection_category_counts"].items()),
                    "example_reject_count": len(article["examples"]),
                }
            )

    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    md_path.write_text(_render_markdown(report), encoding="utf-8")


def print_summary(report: dict[str, Any], output_dir: Path) -> None:
    print(f"Audit written: {output_dir / 'validation_reject_audit.csv'}")
    print(f"Audit written: {output_dir / 'validation_reject_audit.json'}")
    print(f"Audit written: {output_dir / 'validation_reject_audit.md'}")
    print(
        "Totals: "
        f"raw_candidates={report['summary']['raw_candidate_count']}, "
        f"validated_records={report['summary']['validated_record_count']}, "
        f"prediction_rows={report['summary']['prediction_row_count']}, "
        f"validation_errors={report['summary']['validation_error_count']}"
    )
    print("Top rejection categories:")
    for category, count in report["summary"]["top_rejection_categories"][:5]:
        print(f"- {category}: {count}")


def _selected_articles(output_dir: Path, includes: list[str] | None) -> list[dict[str, Any]]:
    zero_audit = output_dir / "zero_pdf_audit.json"
    if zero_audit.exists():
        payload = json.loads(zero_audit.read_text(encoding="utf-8"))
        rows = list(payload.get("articles") or [])
    else:
        rows = _rows_from_article_summary(output_dir / "article_summary.csv")

    if includes:
        wanted = {name.lower() for name in includes}
        selected = [row for row in rows if str(row.get("filename", "")).lower() in wanted]
        missing = sorted(wanted - {str(row.get("filename", "")).lower() for row in selected})
        if missing:
            raise SystemExit(f"Included PDF filename(s) not found in audit/article summary: {', '.join(missing)}")
        return selected
    return [row for row in rows if row.get("row_bucket") in {"zero-row", "low-row"}]


def _rows_from_article_summary(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise SystemExit(f"Missing zero_pdf_audit.json and article_summary.csv under {path.parent}")
    with path.open(encoding="utf-8", newline="") as handle:
        rows = []
        for row in csv.DictReader(handle):
            pred_rows = _to_int(row.get("pred_rows"))
            rows.append(
                {
                    "filename": Path(row.get("pdf", "")).name,
                    "output_dir": row.get("output_dir", ""),
                    "prediction_row_count": pred_rows,
                    "row_bucket": _row_bucket(pred_rows),
                }
            )
        return rows


def _article_dir(output_dir: Path, filename: str, value: str) -> Path:
    if value:
        path = Path(value)
        if path.is_absolute():
            return path
        if path.exists():
            return path
    return output_dir / Path(filename).stem


def _reconstruct_raw_records(article_dir: Path) -> list[BenzimidazoleRawRecord]:
    raw_json = _find_raw_json(article_dir)
    if raw_json is None:
        return []
    document = ParsedPdfDocument.model_validate_json(raw_json.read_text(encoding="utf-8"))
    evidence = build_evidence_chunks(document)
    return extract_records(evidence)


def _normalize_and_validate(raw_records: list[BenzimidazoleRawRecord]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    normalized: list[dict[str, Any]] = []
    rejects: list[dict[str, Any]] = []
    for raw_index, raw in enumerate(raw_records):
        try:
            normalized_record = normalize_record(raw)
        except ValidationError as exc:
            rejects.append(_reject_from_normalization_error(raw_index, raw, exc))
            continue
        normalized.append({"raw_index": raw_index, "raw": raw, "record": normalized_record})
    return normalized, rejects


def _validation_rejects(normalized: list[dict[str, Any]], validation_errors: list[str]) -> list[dict[str, Any]]:
    rejects: list[dict[str, Any]] = []
    for error in validation_errors:
        index = _error_index(error)
        if index is None or index >= len(normalized):
            rejects.append(_reject_from_unmapped_error(error))
            continue
        item = normalized[index]
        rejects.append(_reject_from_validation_error(item["raw_index"], item["raw"], item["record"], error))
    return rejects


def _reject_from_validation_error(
    raw_index: int,
    raw: BenzimidazoleRawRecord,
    normalized: BenzimidazoleRecord,
    error: str,
) -> dict[str, Any]:
    fields = _fields_from_error(error, normalized)
    return {
        "candidate_index": raw_index,
        "candidate_fields": _candidate_fields(raw, normalized),
        "missing_or_invalid_fields": fields,
        "source_evidence": _source_evidence(raw),
        "rejection_reason": _reason_without_index(error),
        "categories": classify_rejection(error, fields, raw, normalized),
    }


def _reject_from_normalization_error(raw_index: int, raw: BenzimidazoleRawRecord, exc: ValidationError) -> dict[str, Any]:
    fields = sorted({str(error.get("loc", ["unknown"])[0]) for error in exc.errors()})
    reason = "; ".join(str(error.get("msg", "validation error")) for error in exc.errors())
    return {
        "candidate_index": raw_index,
        "candidate_fields": _candidate_fields(raw, None),
        "missing_or_invalid_fields": fields,
        "source_evidence": _source_evidence(raw),
        "rejection_reason": reason,
        "categories": classify_rejection(reason, fields, raw, None),
    }


def _reject_from_unmapped_error(error: str) -> dict[str, Any]:
    return {
        "candidate_index": None,
        "candidate_fields": {},
        "missing_or_invalid_fields": [],
        "source_evidence": {},
        "rejection_reason": _reason_without_index(error),
        "categories": ["unknown"],
    }


def classify_rejection(
    reason: str,
    fields: list[str],
    raw: BenzimidazoleRawRecord | None,
    normalized: BenzimidazoleRecord | None,
) -> list[str]:
    categories: list[str] = []
    reason_lower = reason.lower()
    field_set = set(fields)
    if "missing required" in reason_lower or any(_field_missing(field, raw, normalized) for field in field_set):
        categories.append("missing required field")
    if ("target_value" in field_set or "target_value" in reason_lower) and not _field_missing("target_value", raw, normalized):
        categories.append("invalid target value")
    if "target_units" in field_set and not _field_missing("target_units", raw, normalized):
        categories.append("invalid target units")
    if "target_relation" in field_set and not _field_missing("target_relation", raw, normalized):
        categories.append("invalid target relation")
    if "target_type" in field_set and not _field_missing("target_type", raw, normalized):
        categories.append("invalid target type")
    if "bacteria" in field_set:
        categories.append("bacteria normalization problem")
    if "compound_id" in field_set:
        categories.append("compound_id parsing problem")
    if "smiles" in field_set:
        categories.append("SMILES handling problem")
    if "duplicate" in reason_lower or "dedup" in reason_lower:
        categories.append("duplicate/dedup issue")
    if "schema" in reason_lower or "export" in reason_lower:
        categories.append("export schema issue")
    return categories or ["unknown"]


def _fields_from_error(error: str, record: BenzimidazoleRecord) -> list[str]:
    match = re.search(r"missing required evidence-backed values:\s*(?P<fields>.+)$", error)
    if match:
        return [field.strip() for field in match.group("fields").split(",") if field.strip()]
    fields = []
    for field in ("compound_id", "target_type", "target_relation", "target_value", "target_units", "bacteria", "smiles"):
        if field in error:
            fields.append(field)
    if "empty evidence text" in error:
        fields.append("evidence")
    if "target_value is not supported" in error:
        fields.append("target_value")
    for field in ("compound_id", "target_type", "target_value", "target_units", "bacteria"):
        if getattr(record, field, None) == MISSING_VALUE and field not in fields:
            fields.append(field)
    return _dedupe(fields)


def _candidate_fields(raw: BenzimidazoleRawRecord, normalized: BenzimidazoleRecord | None) -> dict[str, Any]:
    payload = {
        "raw": {
            "compound_id": raw.compound_id,
            "smiles": raw.smiles,
            "target_type": raw.target_type,
            "target_relation": raw.target_relation,
            "target_value": raw.target_value,
            "target_units": raw.target_units,
            "bacteria": raw.bacteria,
        }
    }
    if normalized is not None:
        payload["normalized"] = {
            "compound_id": normalized.compound_id,
            "smiles": normalized.smiles,
            "target_type": normalized.target_type,
            "target_relation": normalized.target_relation,
            "target_value": normalized.target_value,
            "target_units": normalized.target_units,
            "bacteria": normalized.bacteria,
        }
    return payload


def _source_evidence(raw: BenzimidazoleRawRecord) -> dict[str, Any]:
    evidence = raw.evidence
    text = re.sub(r"\s+", " ", evidence.evidence_text).strip()
    return {
        "source_file": evidence.source_file,
        "page": evidence.page,
        "section": evidence.section,
        "table_id": evidence.table_id,
        "row_id": evidence.row_id,
        "extraction_method": evidence.extraction_method,
        "confidence": evidence.confidence,
        "evidence_text_preview": text[:300],
    }


def _artifact_notes(article_dir: Path) -> dict[str, Any]:
    confidence = _read_json(article_dir / "confidence_report.json")
    dedup = _read_json(article_dir / "dedup_report.json")
    return {
        "confidence_issues": confidence.get("issues", []),
        "confidence_signals": confidence.get("signals", {}),
        "dedup_report": dedup,
        "rules_predictions_json_count": _json_list_count(article_dir / "rules" / "predictions.json"),
        "predictions_with_evidence_count": _json_list_count(article_dir / "predictions_with_evidence.json"),
    }


def _render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# Validation Reject Audit",
        "",
        f"- Output directory: `{report['output_dir']}`",
        f"- PDFs inspected: {report['selection']['pdf_count']}",
        f"- Raw candidates: {report['summary']['raw_candidate_count']}",
        f"- Validated records: {report['summary']['validated_record_count']}",
        f"- Prediction rows after dedup: {report['summary']['prediction_row_count']}",
        f"- Validation errors: {report['summary']['validation_error_count']}",
        "",
        "## Top Rejection Categories",
        "",
    ]
    for category, count in report["summary"]["top_rejection_categories"][:10]:
        lines.append(f"- {category}: {count}")
    lines.extend(["", "## PDFs", ""])
    for article in report["articles"]:
        lines.extend(
            [
                f"### {article['filename']}",
                "",
                f"- Row bucket: {article['row_bucket']}",
                f"- Raw candidates: {article['raw_candidate_count']}",
                f"- Validated records: {article['validated_record_count']}",
                f"- Prediction rows after dedup: {article['prediction_row_count']}",
                f"- Validation errors: {article['validation_error_count']}",
                f"- Rejected fields: {_format_counts(article['rejected_fields']) or 'none'}",
                f"- Top reasons: {_format_counts(article['top_reject_reasons']) or 'none'}",
                "",
                "| candidate | categories | fields | reason | evidence |",
                "|---:|---|---|---|---|",
            ]
        )
        for example in article["examples"]:
            evidence = example["source_evidence"]
            lines.append(
                "| {index} | {categories} | {fields} | {reason} | p{page} {method}: {preview} |".format(
                    index=example["candidate_index"],
                    categories=", ".join(example["categories"]),
                    fields=", ".join(example["missing_or_invalid_fields"]),
                    reason=example["rejection_reason"],
                    page=evidence.get("page"),
                    method=evidence.get("extraction_method"),
                    preview=str(evidence.get("evidence_text_preview", "")).replace("|", "\\|"),
                )
            )
        lines.append("")
    return "\n".join(lines)


def _find_raw_json(article_dir: Path) -> Path | None:
    parsed_dir = article_dir / "parsed"
    if not parsed_dir.exists():
        return None
    return next(iter(sorted(parsed_dir.glob("*.raw.json"))), None)


def _prediction_row_count(records: list[BenzimidazoleRecord]) -> int:
    llm_records = [
        BenzimidazoleLLMRecord(
            **record.chemx_row(),
            evidence_id=f"rule-{index}",
            warnings=["source:rule_extractor"],
        )
        for index, record in enumerate(records, start=1)
    ]
    return len(compress_llm_records(llm_records).records)


def _field_missing(field: str, raw: BenzimidazoleRawRecord | None, normalized: BenzimidazoleRecord | None) -> bool:
    for record in (normalized, raw):
        if record is not None and getattr(record, field, None) == MISSING_VALUE:
            return True
    return False


def _error_index(error: str) -> int | None:
    match = re.match(r"record\s+(\d+):", error)
    return int(match.group(1)) if match else None


def _reason_without_index(error: str) -> str:
    return re.sub(r"^record\s+\d+:\s*", "", error).strip()


def _row_bucket(prediction_rows: int) -> str:
    if prediction_rows == 0:
        return "zero-row"
    if prediction_rows < 5:
        return "low-row"
    return "ok"


def _format_counts(items: Any) -> str:
    return "; ".join(f"{key}={value}" for key, value in items)


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    deduped: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        deduped.append(value)
    return deduped


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload if isinstance(payload, dict) else {}


def _json_list_count(path: Path) -> int:
    if not path.exists():
        return 0
    payload = json.loads(path.read_text(encoding="utf-8"))
    return len(payload) if isinstance(payload, list) else 0


def _to_int(value: object) -> int:
    try:
        if value in (None, ""):
            return 0
        return int(value)
    except (TypeError, ValueError):
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
