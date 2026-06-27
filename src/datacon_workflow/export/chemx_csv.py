from __future__ import annotations

import csv
import json
from pathlib import Path

from datacon_workflow.domains.benzimidazoles import BenzimidazoleRecord, CHEMX_COLUMNS
from datacon_workflow.review_records import write_review_records


def write_predictions(records: list[BenzimidazoleRecord], output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "predictions.csv"
    json_path = output_dir / "predictions.json"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CHEMX_COLUMNS, extrasaction="raise")
        writer.writeheader()
        writer.writerows(record.chemx_row() for record in records)
    json_path.write_text(json.dumps([record.model_dump(mode="json") for record in records], ensure_ascii=False, indent=2), encoding="utf-8")
    write_review_records(output_dir)
    return csv_path, json_path
