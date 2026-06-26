from __future__ import annotations

from datacon_workflow.domains.benzimidazoles import BenzimidazoleRecord, MISSING_VALUE


def validate_records(records: list[BenzimidazoleRecord]) -> tuple[list[BenzimidazoleRecord], list[str]]:
    accepted: list[BenzimidazoleRecord] = []
    errors: list[str] = []
    for index, record in enumerate(records):
        missing_evidence = [
            field for field in ("compound_id", "target_type", "target_value", "target_units", "bacteria")
            if getattr(record, field) == MISSING_VALUE
        ]
        if missing_evidence:
            errors.append(f"record {index}: missing required evidence-backed values: {', '.join(missing_evidence)}")
            continue
        if not record.evidence.evidence_text.strip():
            errors.append(f"record {index}: empty evidence text")
            continue
        accepted.append(record)
    return accepted, errors
