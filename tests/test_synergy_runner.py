from __future__ import annotations

import csv
import importlib.util
import sys
from pathlib import Path

from datacon_workflow.domains.synergy import SYNERGY_COLUMNS


def _load_runner_module():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "run_synergy_experimental.py"
    spec = importlib.util.spec_from_file_location("run_synergy_experimental", script_path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def test_synergy_article_metrics_are_scoped_by_pdf(tmp_path: Path) -> None:
    runner = _load_runner_module()
    predictions_csv = tmp_path / "predictions.csv"
    ground_truth_csv = tmp_path / "ground_truth.csv"
    _write_synergy_csv(
        predictions_csv,
        [
            _row(pdf="alpha.pdf", NP="Ag", bacteria="Escherichia coli", method="MIC"),
            _row(pdf="beta.pdf", NP="Ag", bacteria="Escherichia coli", method="MIC"),
        ],
    )
    _write_synergy_csv(
        ground_truth_csv,
        [
            _row(pdf="1_alpha.pdf", NP="Ag", bacteria="Escherichia coli", method="MIC"),
            _row(pdf="2_beta.pdf", NP="Au", bacteria="Staphylococcus aureus", method="disc_diffusion"),
        ],
    )

    result = runner.evaluate_synergy_predictions(
        predictions_csv,
        ground_truth_csv,
        tmp_path / "metrics",
        {"alpha.pdf", "beta.pdf"},
    )
    article_by_pdf = {row["pdf"]: row for row in result["article_metrics"]}

    assert article_by_pdf["alpha.pdf"]["macro_f1"] != result["macro_f1"]
    assert article_by_pdf["beta.pdf"]["macro_f1"] != result["macro_f1"]
    assert article_by_pdf["alpha.pdf"]["macro_f1"] != article_by_pdf["beta.pdf"]["macro_f1"]
    assert article_by_pdf["alpha.pdf"]["ground_truth_count"] == 1
    assert article_by_pdf["beta.pdf"]["prediction_count"] == 1


def test_synergy_dataset_metric_stays_field_macro_average(tmp_path: Path) -> None:
    runner = _load_runner_module()
    predictions_csv = tmp_path / "predictions.csv"
    ground_truth_csv = tmp_path / "ground_truth.csv"
    _write_synergy_csv(predictions_csv, [_row(pdf="alpha.pdf", NP="Ag")])
    _write_synergy_csv(ground_truth_csv, [_row(pdf="alpha.pdf", NP="Ag")])

    result = runner.evaluate_synergy_predictions(
        predictions_csv,
        ground_truth_csv,
        tmp_path / "metrics",
        {"alpha.pdf"},
    )

    expected_macro_f1 = sum(float(row["f1"]) for row in result["field_metrics"]) / len(result["field_metrics"])
    assert result["macro_f1"] == expected_macro_f1


def test_synergy_main_accepts_single_pdf(monkeypatch, tmp_path: Path) -> None:
    runner = _load_runner_module()
    pdf = tmp_path / "one.pdf"
    pdf.write_bytes(b"%PDF")
    ground_truth = tmp_path / "ground_truth.csv"
    _write_synergy_csv(ground_truth, [_row(pdf="one.pdf", NP="Ag")])
    output_dir = tmp_path / "out"
    calls: dict[str, object] = {}

    class _Document:
        source_file = "one.pdf"
        tables = []
        text_blocks = []

    monkeypatch.setattr(runner, "_ensure_repo_python", lambda _repo_root: None)
    monkeypatch.setattr(runner, "parse_pdf", lambda pdf_path, parsed_dir: _Document())
    monkeypatch.setattr(runner, "extract_synergy_records", lambda document, pdf_path: [])
    original_evaluate = runner.evaluate_synergy_predictions

    def _evaluate(predictions_csv, ground_truth_csv, metrics_dir, local_pdf_names):
        calls["local_pdf_names"] = local_pdf_names
        return original_evaluate(predictions_csv, ground_truth_csv, metrics_dir, local_pdf_names)

    monkeypatch.setattr(runner, "evaluate_synergy_predictions", _evaluate)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "run_synergy_experimental.py",
            "--pdf",
            str(pdf),
            "--ground-truth",
            str(ground_truth),
            "--output-dir",
            str(output_dir),
        ],
    )

    assert runner.main() == 0
    assert calls["local_pdf_names"] == {"one.pdf"}
    assert (output_dir / "predictions.csv").exists()
    assert (output_dir / "article_summary.csv").exists()
    assert not (output_dir / "one" / "predictions.csv").exists()


def _row(**values: str) -> dict[str, str]:
    row = {column: "" for column in SYNERGY_COLUMNS}
    row.update(values)
    return row


def _write_synergy_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=SYNERGY_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
