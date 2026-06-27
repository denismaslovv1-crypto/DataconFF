from __future__ import annotations

import csv
from pathlib import Path

from datacon_workflow.domains.benzimidazoles import CHEMX_COLUMNS
from datacon_workflow.evaluation.chemx_eval import evaluate_predictions


GROUND_TRUTH = Path("data/chemx/benzimidazoles/ground_truth.csv")


def _write_predictions(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CHEMX_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)


def _row(**overrides: str) -> dict[str, str]:
    row = {
        "compound_id": "5a",
        "smiles": "NOT_DETECTED",
        "target_type": "MIC",
        "target_relation": "=",
        "target_value": "5",
        "target_units": "ug/mL",
        "bacteria": "S. aureus",
    }
    row.update(overrides)
    return row


def _field_metric(metrics: dict[str, object], field: str) -> dict[str, object]:
    field_metrics = metrics["field_metrics"]
    assert isinstance(field_metrics, list)
    return next(row for row in field_metrics if isinstance(row, dict) and row["field"] == field)


def test_pdf_stem_gt_matching_accepts_name_with_and_without_pdf(tmp_path) -> None:
    predictions_csv = tmp_path / "predictions.csv"
    _write_predictions(predictions_csv, [])

    without_suffix = evaluate_predictions(
        predictions_csv,
        GROUND_TRUTH,
        tmp_path / "without",
        benchmark_pdf_name="j.ejmech.2015.03.024",
    )
    with_suffix = evaluate_predictions(
        predictions_csv,
        GROUND_TRUTH,
        tmp_path / "with",
        benchmark_pdf_name="j.ejmech.2015.03.024.pdf",
    )

    assert without_suffix["ground_truth_count"] == 40
    assert with_suffix["ground_truth_count"] == 40


def test_s13065_pdf_stem_has_expected_ground_truth_rows(tmp_path) -> None:
    predictions_csv = tmp_path / "predictions.csv"
    _write_predictions(predictions_csv, [])

    metrics = evaluate_predictions(
        predictions_csv,
        GROUND_TRUTH,
        tmp_path / "metrics",
        benchmark_pdf_name="s13065-018-0479-1",
    )

    assert metrics["ground_truth_count"] == 24


def test_jccs_pdf_stem_preserves_trailing_j(tmp_path) -> None:
    predictions_csv = tmp_path / "predictions.csv"
    _write_predictions(predictions_csv, [])

    metrics = evaluate_predictions(
        predictions_csv,
        GROUND_TRUTH,
        tmp_path / "metrics",
        benchmark_pdf_name="jccs.202000418J",
    )

    assert metrics["ground_truth_count"] == 3


def test_rjc_pdf_stem_does_not_absorb_reference_doi_rows(tmp_path) -> None:
    predictions_csv = tmp_path / "predictions.csv"
    _write_predictions(predictions_csv, [])

    metrics = evaluate_predictions(
        predictions_csv,
        GROUND_TRUTH,
        tmp_path / "metrics",
        benchmark_pdf_ids={"10.1016/j.ejmech.2020.112996", "10.31788/rjc.2023.1638382"},
        benchmark_pdf_name="RJC.2023.1638382",
    )

    assert metrics["ground_truth_count"] == 10


def test_target_value_numeric_serialization_matches_only_in_metrics(tmp_path) -> None:
    predictions_csv = tmp_path / "predictions.csv"
    ground_truth_csv = tmp_path / "ground_truth.csv"
    _write_predictions(predictions_csv, [_row(target_value="5")])
    _write_predictions(ground_truth_csv, [_row(target_value="5.0")])
    before = predictions_csv.read_text(encoding="utf-8")

    metrics = evaluate_predictions(predictions_csv, ground_truth_csv, tmp_path / "metrics")

    assert _field_metric(metrics, "target_value")["f1"] == 1.0
    assert predictions_csv.read_text(encoding="utf-8") == before


def test_bacteria_aliases_match_only_in_metrics(tmp_path) -> None:
    predictions_csv = tmp_path / "predictions.csv"
    ground_truth_csv = tmp_path / "ground_truth.csv"
    _write_predictions(predictions_csv, [_row(bacteria="S. aureus")])
    _write_predictions(ground_truth_csv, [_row(bacteria="Staphylococcus aureus")])
    before = predictions_csv.read_text(encoding="utf-8")

    metrics = evaluate_predictions(predictions_csv, ground_truth_csv, tmp_path / "metrics")

    assert _field_metric(metrics, "bacteria")["f1"] == 1.0
    assert predictions_csv.read_text(encoding="utf-8") == before
