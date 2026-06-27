from __future__ import annotations

import csv
import importlib.util
import json
from pathlib import Path


def _load_audit_module():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "audit_zero_pdfs.py"
    spec = importlib.util.spec_from_file_location("audit_zero_pdfs", script_path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _write_article_summary(path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=[
                "pdf",
                "output_dir",
                "pred_rows",
                "gt_rows",
                "macro_f1",
                "confidence",
                "llm_used",
                "status",
                "error",
                "top_failed_fields",
            ],
        )
        writer.writeheader()
        writer.writerow(
            {
                "pdf": r"data\chemx\benzimidazoles\pdfs\zero.pdf",
                "output_dir": str(path.parent / "zero"),
                "pred_rows": "0",
                "gt_rows": "3",
                "macro_f1": "0",
                "confidence": "low",
                "llm_used": "false",
                "status": "ok",
                "error": "",
                "top_failed_fields": "bacteria",
            }
        )
        writer.writerow(
            {
                "pdf": r"data\chemx\benzimidazoles\pdfs\low.pdf",
                "output_dir": str(path.parent / "low"),
                "pred_rows": "2",
                "gt_rows": "4",
                "macro_f1": "0.1",
                "confidence": "low",
                "llm_used": "false",
                "status": "ok",
                "error": "",
                "top_failed_fields": "smiles",
            }
        )
        writer.writerow(
            {
                "pdf": r"data\chemx\benzimidazoles\pdfs\expected.pdf",
                "output_dir": str(path.parent / "expected"),
                "pred_rows": "0",
                "gt_rows": "0",
                "macro_f1": "0",
                "confidence": "low",
                "llm_used": "false",
                "status": "ok",
                "error": "",
                "top_failed_fields": "",
            }
        )


def test_classify_failure_stage_zero_export() -> None:
    audit = _load_audit_module()

    stage = audit.classify_failure_stage(
        has_parse_artifacts=True,
        parsed_text_blocks=5,
        parsed_tables=2,
        evidence_chunks=4,
        raw_candidates=3,
        prediction_rows=0,
    )

    assert stage == "candidates exist but validation/export produced zero rows"


def test_build_and_write_audit_files(tmp_path) -> None:
    audit = _load_audit_module()
    _write_article_summary(tmp_path / "article_summary.csv")
    (tmp_path / "metrics.json").write_text(
        json.dumps({"macro_f1": 0.25, "prediction_count": 2, "ground_truth_count": 7}),
        encoding="utf-8",
    )
    (tmp_path / "field_metrics.csv").write_text("field,f1\nbacteria,0\n", encoding="utf-8")

    zero_dir = tmp_path / "zero"
    (zero_dir / "parsed").mkdir(parents=True)
    (zero_dir / "parsed" / "zero.raw.json").write_text(
        json.dumps({"text_blocks": [{"text": "MIC"}], "tables": [{"rows": [["c", "MIC"]]}]}),
        encoding="utf-8",
    )
    (zero_dir / "rule_evidence.json").write_text(json.dumps([{"evidence_id": "e1"}]), encoding="utf-8")
    (zero_dir / "confidence_report.json").write_text(
        json.dumps(
            {
                "signals": {
                    "parsed_tables": 1,
                    "evidence_chunks": 1,
                    "raw_records": 2,
                    "validated_records": 0,
                    "validation_errors": 2,
                }
            }
        ),
        encoding="utf-8",
    )

    low_dir = tmp_path / "low"
    low_dir.mkdir()
    with (low_dir / "predictions.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["compound_id"])
        writer.writeheader()
        writer.writerow({"compound_id": "5a"})
        writer.writerow({"compound_id": "5b"})

    report = audit.build_audit(tmp_path)
    audit.write_audit_files(tmp_path, report)

    assert report["summary"]["zero_row"] == 1
    assert report["summary"]["expected_zero"] == 1
    assert report["summary"]["low_row"] == 1
    assert report["articles"][0]["likely_failure_stage"] == "candidates exist but validation/export produced zero rows"
    assert report["articles"][2]["row_bucket"] == "expected-zero"
    assert report["articles"][2]["likely_failure_stage"] == "expected zero-row / no GT records"
    assert (tmp_path / "zero_pdf_audit.csv").exists()
    assert (tmp_path / "zero_pdf_audit.json").exists()
    assert (tmp_path / "zero_pdf_audit.md").exists()
