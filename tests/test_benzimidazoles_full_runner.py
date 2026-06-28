from __future__ import annotations

import csv
import importlib.util
import json
import sys
from argparse import Namespace
from pathlib import Path

import pytest

from datacon_workflow.domains.benzimidazoles import CHEMX_COLUMNS


def _load_runner_module():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "run_benzimidazoles_full.py"
    spec = importlib.util.spec_from_file_location("run_benzimidazoles_full", script_path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _write_prediction_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CHEMX_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def test_collect_prediction_rows_preserves_required_columns(tmp_path) -> None:
    runner = _load_runner_module()
    _write_prediction_csv(
        tmp_path / "article_a" / "predictions.csv",
        [
            {
                "compound_id": "5a",
                "smiles": "NOT_DETECTED",
                "target_type": "MIC",
                "target_relation": "=",
                "target_value": "4",
                "target_units": "ug/mL",
                "bacteria": "S. aureus",
            }
        ],
    )
    _write_prediction_csv(
        tmp_path / "article_b" / "predictions.csv",
        [
            {
                "compound_id": "7b",
                "smiles": "NOT_DETECTED",
                "target_type": "pMIC",
                "target_relation": "=",
                "target_value": "1.2",
                "target_units": "µM",
                "bacteria": "E. coli",
            }
        ],
    )

    rows = runner._collect_prediction_rows(tmp_path)
    output_csv = tmp_path / "predictions.csv"
    runner._write_predictions_csv(output_csv, rows)

    with output_csv.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        merged = list(reader)

    assert tuple(reader.fieldnames or ()) == CHEMX_COLUMNS
    assert [row["compound_id"] for row in merged] == ["5a", "7b"]


def test_review_sidecars_are_not_merged_into_public_predictions(tmp_path) -> None:
    runner = _load_runner_module()
    _write_prediction_csv(
        tmp_path / "article" / "predictions.csv",
        [
            {
                "compound_id": "5a",
                "smiles": "NOT_DETECTED",
                "target_type": "MIC",
                "target_relation": "=",
                "target_value": "4",
                "target_units": "ug/mL",
                "bacteria": "S. aureus",
            }
        ],
    )
    with (tmp_path / "article" / "review_records.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=[*CHEMX_COLUMNS, "evidence_id", "source_text"])
        writer.writeheader()
        writer.writerow(
            {
                "compound_id": "5a",
                "smiles": "NOT_DETECTED",
                "target_type": "MIC",
                "target_relation": "=",
                "target_value": "4",
                "target_units": "ug/mL",
                "bacteria": "S. aureus",
                "evidence_id": "ev:1",
                "source_text": "review-only context",
            }
        )

    rows = runner._collect_prediction_rows(tmp_path)
    output_csv = tmp_path / "predictions.csv"
    runner._write_predictions_csv(output_csv, rows)

    with output_csv.open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        merged = list(reader)

    assert tuple(reader.fieldnames or ()) == CHEMX_COLUMNS
    assert merged == rows
    assert "evidence_id" not in merged[0]


def test_final_article_command_keeps_llm_mode_never(tmp_path) -> None:
    runner = _load_runner_module()
    args = Namespace(
        ground_truth=Path("data/chemx/benzimidazoles/ground_truth.csv"),
        llm_mode="never",
        evidence_batch_size=5,
        max_evidence_chunks=80,
        max_concurrent_batches=1,
        resume_existing_batches=False,
    )

    command = runner._build_article_command(
        Path("data/chemx/benzimidazoles/pdfs/j.bmc.2014.09.008.pdf"),
        tmp_path / "article",
        args,
    )

    assert command[0] == sys.executable
    assert command[command.index("--llm-mode") + 1] == "never"
    assert "--resume-existing-batches" not in command


def test_include_filter_selects_pdf_filenames_case_insensitively(tmp_path) -> None:
    runner = _load_runner_module()
    pdfs = [
        tmp_path / "Alpha.PDF",
        tmp_path / "j.bmc.2014.09.008.pdf",
        tmp_path / "zeta.pdf",
    ]

    selected = runner._filter_included_pdfs(pdfs, ["J.BMC.2014.09.008.PDF"])

    assert selected == [tmp_path / "j.bmc.2014.09.008.pdf"]


def test_include_filter_reports_missing_filename(tmp_path) -> None:
    runner = _load_runner_module()
    pdfs = [tmp_path / "j.bmc.2014.09.008.pdf"]

    with pytest.raises(SystemExit, match="janupally2014.pdf"):
        runner._filter_included_pdfs(pdfs, ["janupally2014.pdf"])


def test_collect_prediction_rows_rejects_wrong_column_order(tmp_path) -> None:
    runner = _load_runner_module()
    bad_csv = tmp_path / "article" / "predictions.csv"
    bad_csv.parent.mkdir(parents=True)
    with bad_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["smiles", "compound_id"])
        writer.writeheader()
        writer.writerow({"smiles": "NOT_DETECTED", "compound_id": "5a"})

    with pytest.raises(ValueError, match="must use exactly"):
        runner._collect_prediction_rows(tmp_path)


def test_load_article_outputs_builds_requested_summary(tmp_path) -> None:
    runner = _load_runner_module()
    article_dir = tmp_path / "article"
    _write_prediction_csv(
        article_dir / "predictions.csv",
        [
            {
                "compound_id": "5a",
                "smiles": "NOT_DETECTED",
                "target_type": "MIC",
                "target_relation": "=",
                "target_value": "4",
                "target_units": "ug/mL",
                "bacteria": "S. aureus",
            }
        ],
    )
    (article_dir / "metrics.json").write_text(
        json.dumps({"macro_f1": 0.5, "ground_truth_count": 3}),
        encoding="utf-8",
    )
    (article_dir / "confidence_report.json").write_text(
        json.dumps({"confidence": "high"}),
        encoding="utf-8",
    )
    (article_dir / "hybrid_summary.json").write_text(
        json.dumps({"llm_ran": False}),
        encoding="utf-8",
    )
    with (article_dir / "field_metrics.csv").open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["field", "precision", "recall", "f1", "true_positive"])
        writer.writeheader()
        writer.writerow({"field": "bacteria", "precision": 0, "recall": 0, "f1": 0, "true_positive": 0})
        writer.writerow({"field": "target_units", "precision": 0, "recall": 0, "f1": 0.25, "true_positive": 1})
        writer.writerow({"field": "compound_id", "precision": 1, "recall": 1, "f1": 1, "true_positive": 3})

    summary = runner._load_article_outputs(Path("article.pdf"), article_dir, "ok", "")

    assert summary == {
        "pdf": "article.pdf",
        "output_dir": str(article_dir),
        "pred_rows": "1",
        "gt_rows": "3",
        "macro_f1": "0.500000",
        "confidence": "high",
        "llm_used": "false",
        "status": "ok",
        "error": "",
        "top_failed_fields": "bacteria;target_units",
    }
