from __future__ import annotations

import re

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
        if not _target_value_supported_by_evidence(record):
            errors.append(f"record {index}: target_value is not supported by evidence text: {record.target_value}")
            continue
        accepted.append(record)
    return accepted, errors


def _target_value_supported_by_evidence(record: BenzimidazoleRecord) -> bool:
    """Reject hallucinated numeric values while allowing source ranges."""
    evidence_text = record.evidence.evidence_text
    for piece in record.target_value.split("-"):
        value = piece.strip()
        if not value:
            return False
        pattern = rf"(?<![\d.]){re.escape(value)}(?![\d.])"
        if not re.search(pattern, evidence_text):
            return False
    return True
