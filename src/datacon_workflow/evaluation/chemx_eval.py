from __future__ import annotations

import csv
import json
from collections import Counter
from pathlib import Path

from datacon_workflow.domains.benzimidazoles import CHEMX_COLUMNS


def evaluate_predictions(
    predictions_csv: Path,
    ground_truth_csv: Path,
    output_dir: Path,
    benchmark_pdf_ids: set[str] | None = None,
) -> dict[str, object]:
    with predictions_csv.open(encoding="utf-8", newline="") as handle:
        predictions = list(csv.DictReader(handle))
    with ground_truth_csv.open(encoding="utf-8", newline="") as handle:
        truth = list(csv.DictReader(handle))
    if benchmark_pdf_ids is not None:
        truth = [
            row for row in truth
            if row.get("pdf", "").lower() in benchmark_pdf_ids or row.get("doi", "").lower() in benchmark_pdf_ids
        ]
    prediction_columns = tuple(predictions[0].keys()) if predictions else CHEMX_COLUMNS
    if prediction_columns != CHEMX_COLUMNS:
        raise ValueError("Prediction CSV must use exactly the Benzimidazoles ChemX column order")
    metrics: list[dict[str, float | int | str]] = []
    for field in CHEMX_COLUMNS:
        predicted = Counter(_canonical_value(field, row.get(field, "")) for row in predictions)
        expected = Counter(_canonical_value(field, row.get(field, "")) for row in truth)
        true_positive = sum((predicted & expected).values())
        precision = true_positive / sum(predicted.values()) if predicted else 0.0
        recall = true_positive / sum(expected.values()) if expected else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        metrics.append({"field": field, "precision": precision, "recall": recall, "f1": f1, "true_positive": true_positive})
    result = {
        "macro_f1": sum(float(row["f1"]) for row in metrics) / len(metrics),
        "field_metrics": metrics,
        "prediction_count": len(predictions),
        "ground_truth_count": len(truth),
        "benchmark_pdf_ids": sorted(benchmark_pdf_ids) if benchmark_pdf_ids else None,
    }
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "metrics.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    with (output_dir / "field_metrics.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(metrics[0]))
        writer.writeheader()
        writer.writerows(metrics)
    return result


def _canonical_value(field: str, value: str) -> str:
    """Normalize CSV serialization differences for comparison only."""
    cleaned = value.strip().strip("'")
    if field == "target_relation":
        return cleaned.lstrip("=") if cleaned.startswith("==") else cleaned
    if field == "target_value":
        return cleaned.replace(",", ".")
    return cleaned
