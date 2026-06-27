from __future__ import annotations

import csv
import json
from pathlib import Path

from datacon_workflow.domains.benzimidazoles import BenzimidazoleLLMRecord, CHEMX_COLUMNS
from datacon_workflow.export.llm_compression import compress_llm_records
from datacon_workflow.extraction.evidence_selector import BenzimidazoleEvidence


def write_llm_predictions(
    records: list[BenzimidazoleLLMRecord],
    evidence: list[BenzimidazoleEvidence],
    output_dir: Path,
) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "predictions.csv"
    sidecar_path = output_dir / "predictions_with_evidence.json"
    report_path = output_dir / "dedup_report.json"
    compressed = compress_llm_records(records)
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=CHEMX_COLUMNS, extrasaction="raise")
        writer.writeheader()
        writer.writerows(item.record.chemx_row() for item in compressed.records)

    evidence_by_id = {item.evidence_id: item.model_dump(mode="json") for item in evidence}
    sidecar = [
        {
            "record": item.record.model_dump(mode="json"),
            "evidence": evidence_by_id.get(item.record.evidence_id),
            "merged_evidence_ids": list(item.evidence_ids),
            "merged_evidence": [
                evidence_by_id[evidence_id]
                for evidence_id in item.evidence_ids
                if evidence_id in evidence_by_id
            ],
            "duplicate_count": item.duplicate_count,
            "warnings": item.record.warnings,
        }
        for item in compressed.records
    ]
    sidecar_path.write_text(json.dumps(sidecar, ensure_ascii=False, indent=2), encoding="utf-8")
    report_path.write_text(json.dumps(compressed.report, ensure_ascii=False, indent=2), encoding="utf-8")
    return csv_path, sidecar_path
