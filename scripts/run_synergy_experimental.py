from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any

from datacon_workflow.domains.synergy import SYNERGY_COLUMNS, chemx_row, extract_synergy_records, review_row
from pdf_extraction.pipeline import parse_pdf


BASELINE_MACRO_F1 = 0.080


def main() -> int:
    parser = argparse.ArgumentParser(description="Run experimental rules-first Synergy extraction.")
    parser.add_argument("--pdf-dir", type=Path, default=Path("data/chemx/synergy/pdfs"))
    parser.add_argument("--ground-truth", type=Path, default=Path("data/chemx/synergy/ground_truth.csv"))
    parser.add_argument("--output-dir", type=Path, default=Path("outputs/synergy_full"))
    parser.add_argument("--limit", type=int, help="Optional smoke-test cap.")
    args = parser.parse_args()

    repo_root = Path(__file__).resolve().parents[1]
    _ensure_repo_python(repo_root)
    pdfs = _find_pdfs(args.pdf_dir)
    if args.limit is not None:
        pdfs = pdfs[: args.limit]
    if not pdfs:
        raise SystemExit(f"No PDF files found in {args.pdf_dir}")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    all_rows: list[dict[str, str]] = []
    all_review_rows: list[dict[str, str]] = []
    article_summary: list[dict[str, str]] = []

    for index, pdf in enumerate(pdfs, start=1):
        print(f"[{index}/{len(pdfs)}] {pdf.name}")
        article_dir = args.output_dir / pdf.stem.replace(" ", "_")
        article_dir.mkdir(parents=True, exist_ok=True)
        try:
            document = parse_pdf(pdf, article_dir / "parsed")
            records = extract_synergy_records(document, pdf)
            rows = [chemx_row(record, sn=len(all_rows) + offset) for offset, record in enumerate(records, start=1)]
            sidecar = []
            review_rows = []
            for offset, (record, row) in enumerate(zip(records, rows, strict=True), start=1):
                evidence_id = f"{pdf.stem}:rule-{offset}"
                sidecar.append(
                    {
                        "record": row,
                        "evidence": {
                            "source_file": record.evidence.source_file,
                            "page": record.evidence.page,
                            "table_id": record.evidence.table_id,
                            "row_id": record.evidence.row_id,
                            "evidence_text": record.evidence.evidence_text,
                            "extraction_method": record.evidence.extraction_method,
                            "confidence": record.evidence.confidence,
                        },
                        "evidence_id": evidence_id,
                    }
                )
                review_rows.append(review_row(record, row, evidence_id))
            _write_csv(article_dir / "predictions.csv", SYNERGY_COLUMNS, rows)
            (article_dir / "predictions_with_evidence.json").write_text(
                json.dumps(sidecar, ensure_ascii=False, indent=2),
                encoding="utf-8",
            )
            _write_review_records(article_dir, review_rows)
            all_rows.extend(rows)
            all_review_rows.extend(review_rows)
            article_summary.append(
                {
                    "pdf": pdf.name,
                    "status": "ok",
                    "pred_rows": str(len(rows)),
                    "gt_rows": "",
                    "error": "",
                }
            )
        except Exception as exc:
            article_summary.append(
                {
                    "pdf": pdf.name,
                    "status": "failed",
                    "pred_rows": "0",
                    "gt_rows": "",
                    "error": str(exc),
                }
            )

    predictions_csv = args.output_dir / "predictions.csv"
    _write_csv(predictions_csv, SYNERGY_COLUMNS, all_rows)
    _write_review_records(args.output_dir, all_review_rows)
    metrics = evaluate_synergy_predictions(predictions_csv, args.ground_truth, args.output_dir, {pdf.name for pdf in pdfs})
    gt_by_pdf = {row["pdf"]: row["rows"] for row in metrics["article_ground_truth"]}
    for row in article_summary:
        row["gt_rows"] = str(gt_by_pdf.get(row["pdf"], 0))
    _write_csv(args.output_dir / "article_summary.csv", ("pdf", "status", "pred_rows", "gt_rows", "error"), article_summary)

    manifest = {
        "run_started_at_utc": datetime.now(timezone.utc).isoformat(),
        "domain": "Synergy",
        "experimental": True,
        "baseline_macro_f1": BASELINE_MACRO_F1,
        "beats_baseline": bool(metrics["macro_f1"] > BASELINE_MACRO_F1),
        "pdf_dir": str(args.pdf_dir),
        "ground_truth": str(args.ground_truth),
        "output_dir": str(args.output_dir),
        "pdfs_selected": len(pdfs),
        "selected_pdfs": [pdf.name for pdf in pdfs],
        "prediction_rows": len(all_rows),
        "review_rows": len(all_review_rows),
        "metrics": metrics,
    }
    (args.output_dir / "run_manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    print(f"Prediction rows: {len(all_rows)}")
    print(f"Local GT rows: {metrics['ground_truth_count']}")
    print(f"Macro-F1: {metrics['macro_f1']:.4f}")
    print(f"Beats Synergy baseline {BASELINE_MACRO_F1:.3f}: {metrics['macro_f1'] > BASELINE_MACRO_F1}")
    print(f"Outputs: {args.output_dir}")
    return 0 if all(row["status"] == "ok" for row in article_summary) else 1


def evaluate_synergy_predictions(
    predictions_csv: Path,
    ground_truth_csv: Path,
    output_dir: Path,
    local_pdf_names: set[str],
) -> dict[str, Any]:
    predictions = _read_csv(predictions_csv)
    truth_all = _read_csv(ground_truth_csv)
    local_pdf_keys = {_canonical_pdf_name(name) for name in local_pdf_names}
    truth = [row for row in truth_all if _canonical_pdf_name(row.get("pdf", "")) in local_pdf_keys]
    if predictions:
        columns = tuple(predictions[0].keys())
        if columns != SYNERGY_COLUMNS:
            raise ValueError("Prediction CSV must use exactly the Synergy ChemX column order")

    field_metrics: list[dict[str, float | int | str]] = []
    for field in SYNERGY_COLUMNS:
        predicted = Counter(_canonical_value(field, row.get(field, "")) for row in predictions)
        expected = Counter(_canonical_value(field, row.get(field, "")) for row in truth)
        true_positive = sum((predicted & expected).values())
        precision = true_positive / sum(predicted.values()) if predicted else 0.0
        recall = true_positive / sum(expected.values()) if expected else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        field_metrics.append(
            {
                "field": field,
                "precision": precision,
                "recall": recall,
                "f1": f1,
                "true_positive": true_positive,
            }
        )

    article_truth_counts = Counter(_canonical_pdf_name(row.get("pdf", "")) for row in truth)
    article_ground_truth = [
        {"pdf": local_name, "rows": article_truth_counts[_canonical_pdf_name(local_name)]}
        for local_name in sorted(local_pdf_names)
    ]
    result = {
        "macro_f1": sum(float(row["f1"]) for row in field_metrics) / len(field_metrics),
        "field_metrics": field_metrics,
        "prediction_count": len(predictions),
        "ground_truth_count": len(truth),
        "ground_truth_pdf_count": len({row.get("pdf", "") for row in truth}),
        "selected_pdf_count": len(local_pdf_names),
        "article_ground_truth": article_ground_truth,
        "baseline_macro_f1": BASELINE_MACRO_F1,
        "beats_baseline": bool((sum(float(row["f1"]) for row in field_metrics) / len(field_metrics)) > BASELINE_MACRO_F1),
    }
    (output_dir / "metrics.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    _write_csv(
        output_dir / "field_metrics.csv",
        ("field", "precision", "recall", "f1", "true_positive"),
        field_metrics,
    )
    return result


def _ensure_repo_python(repo_root: Path) -> None:
    expected = repo_root / ".venv" / "Scripts" / "python.exe"
    if not expected.exists():
        raise SystemExit(
            "\n".join(
                [
                    "Repository interpreter is missing.",
                    f"current working directory: {Path.cwd()}",
                    f"checked interpreter path: {expected}",
                    f"command that could not run: {expected} scripts\\run_synergy_experimental.py",
                    "what to create/install: create the repository .venv with .\\setup_project_env.cmd",
                ]
            )
        )
    if Path(sys.executable).resolve() != expected.resolve():
        raise SystemExit(
            "\n".join(
                [
                    "This script must be run with the repository-local interpreter.",
                    f"current working directory: {Path.cwd()}",
                    f"checked interpreter path: {expected}",
                    f"current interpreter: {sys.executable}",
                    f"command that could not run: {expected} scripts\\run_synergy_experimental.py",
                    "what to create/install: rerun with .\\.venv\\Scripts\\python.exe",
                ]
            )
        )


def _find_pdfs(pdf_dir: Path) -> list[Path]:
    return sorted(
        (path for path in pdf_dir.iterdir() if path.is_file() and path.suffix.lower() == ".pdf"),
        key=lambda path: path.name.lower(),
    )


def _write_csv(path: Path, columns: tuple[str, ...], rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def _write_review_records(output_dir: Path, rows: list[dict[str, str]]) -> None:
    columns = (
        "pdf",
        "sn",
        "NP",
        "bacteria",
        "drug",
        "method",
        "value_drug",
        "value_np",
        "value_combined",
        "FIC",
        "page",
        "table_id",
        "row_id",
        "evidence_id",
        "source_text",
        "extractor",
        "confidence",
    )
    _write_csv(output_dir / "review_records.csv", columns, rows)
    (output_dir / "review_records.json").write_text(
        json.dumps(rows, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _canonical_value(field: str, value: str) -> str:
    cleaned = (value or "").strip().strip("'")
    if field == "pdf":
        return _canonical_pdf_name(cleaned)
    if field == "bacteria":
        return _canonical_bacteria(cleaned)
    if field == "NP":
        return _canonical_np(cleaned)
    if field == "drug":
        return _canonical_drug(cleaned)
    if field == "method":
        return _canonical_method(cleaned)
    if field in NUMERIC_FIELDS:
        return _canonical_number(cleaned)
    return cleaned.lower() if field in CASE_INSENSITIVE_FIELDS else cleaned


def _canonical_pdf_name(value: str) -> str:
    cleaned = value.strip().lower()
    cleaned = re.sub(r"^\d+_", "", cleaned)
    if cleaned.endswith(".pdf"):
        cleaned = cleaned[:-4]
    return cleaned


def _canonical_bacteria(value: str) -> str:
    aliases = {
        "e. coli": "escherichia coli",
        "escherichia coli": "escherichia coli",
        "s. aureus": "staphylococcus aureus",
        "staphylococcus aureus": "staphylococcus aureus",
        "p. aeruginosa": "pseudomonas aeruginosa",
        "pseudomonas aeruginosa": "pseudomonas aeruginosa",
        "b. subtilis": "bacillus subtilis",
        "bacillus subtilis": "bacillus subtilis",
        "k. pneumoniae": "klebsiella pneumoniae",
        "klebsiella pneumoniae": "klebsiella pneumoniae",
    }
    return aliases.get(value.lower(), value.lower())


def _canonical_np(value: str) -> str:
    aliases = {
        "silver": "ag",
        "agnp": "ag",
        "agnps": "ag",
        "ag": "ag",
        "gold": "au",
        "aunp": "au",
        "aunps": "au",
        "au": "au",
        "tio2": "tio2",
        "zno": "zno",
        "cuo": "cuo",
        "fe3o4": "fe3o4",
        "fe2o3": "fe2o3",
    }
    return aliases.get(value.lower(), value.lower())


def _canonical_drug(value: str) -> str:
    return {"gentamycin": "gentamicin"}.get(value.lower(), value.lower())


def _canonical_method(value: str) -> str:
    aliases = {
        "disk_diffusion": "disc_diffusion",
        "zone": "disc_diffusion",
        "zoi": "disc_diffusion",
        "viability (%)": "viability (%)",
    }
    return aliases.get(value.lower(), value.lower())


def _canonical_number(value: str) -> str:
    cleaned = value.replace(",", ".")
    try:
        decimal = Decimal(cleaned)
    except InvalidOperation:
        return cleaned
    return format(decimal.normalize(), "f")


NUMERIC_FIELDS = {
    "sn",
    "drug_dose_µg_disk",
    "NP_concentration_µg_ml",
    "NP_size_min_nm",
    "NP_size_max_nm",
    "NP_size_avg_nm",
    "ZOI_drug_mm_or_MIC _µg_ml",
    "error_ZOI_drug_mm_or_MIC_µg_ml",
    "ZOI_NP_mm_or_MIC_np_µg_ml",
    "error_ZOI_NP_mm_or_MIC_np_µg_ml",
    "ZOI_drug_NP_mm_or_MIC_drug_NP_µg_ml",
    "error_ZOI_drug_NP_mm_or_MIC_drug_NP_µg_ml",
    "fold_increase_in_antibacterial_activity",
    "zeta_potential_mV",
    "FIC",
    "article_list",
    "time_hr",
    "combined_MIC",
    "peptide_MIC",
    "viability_%",
    "viability_error",
    "year",
    "access",
}

CASE_INSENSITIVE_FIELDS = {
    "shape",
    "doi",
    "title",
    "journal_name",
    "publisher",
    "oa_status",
}


if __name__ == "__main__":
    raise SystemExit(main())
