from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation

from datacon_workflow.domains.benzimidazoles import BenzimidazoleLLMRecord, CHEMX_COLUMNS, MISSING_VALUE
from datacon_workflow.normalization.bacteria import normalize_bacteria
from datacon_workflow.normalization.units import normalize_unit


@dataclass(frozen=True)
class DeduplicatedRecord:
    record: BenzimidazoleLLMRecord
    evidence_ids: tuple[str, ...]
    duplicate_count: int


@dataclass(frozen=True)
class CompressionResult:
    records: list[DeduplicatedRecord]
    report: dict[str, object]


@dataclass
class _Accumulator:
    record: BenzimidazoleLLMRecord
    evidence_ids: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    duplicate_count: int = 0


def compress_llm_records(records: list[BenzimidazoleLLMRecord]) -> CompressionResult:
    """Normalize benchmark-facing rows and merge only same-evidence duplicates."""
    by_row: dict[tuple[str, ...], _Accumulator] = {}
    conflict_groups: dict[tuple[str, str, str], set[tuple[str, ...]]] = {}
    input_count = len(records)
    normalized_count = 0

    for record in records:
        normalized, changed = _normalize_record(record)
        if changed:
            normalized_count += 1
        row_key = _row_key(normalized)
        dedup_key = _dedup_key(normalized)
        accumulator = by_row.get(dedup_key)
        if accumulator is None:
            accumulator = _Accumulator(record=normalized)
            by_row[dedup_key] = accumulator
        accumulator.duplicate_count += 1
        if normalized.evidence_id not in accumulator.evidence_ids:
            accumulator.evidence_ids.append(normalized.evidence_id)
        for warning in normalized.warnings:
            if warning not in accumulator.warnings:
                accumulator.warnings.append(warning)

        conflict_key = (normalized.compound_id, normalized.target_type, normalized.bacteria)
        if MISSING_VALUE not in conflict_key:
            conflict_groups.setdefault(conflict_key, set()).add(row_key)

    output_records: list[DeduplicatedRecord] = []
    for accumulator in by_row.values():
        output_records.append(
            DeduplicatedRecord(
                record=accumulator.record.model_copy(update={"warnings": accumulator.warnings}),
                evidence_ids=tuple(accumulator.evidence_ids),
                duplicate_count=accumulator.duplicate_count,
            )
        )

    conflicts = [
        {
            "key": {
                "compound_id": compound_id,
                "target_type": target_type,
                "bacteria": bacteria,
            },
            "rows": [_row_dict(row_key) for row_key in sorted(row_keys)],
        }
        for (compound_id, target_type, bacteria), row_keys in sorted(conflict_groups.items())
        if len(row_keys) > 1
    ]

    report = {
        "input_records": input_count,
        "output_records": len(output_records),
        "exact_duplicates_merged": input_count - len(output_records),
        "records_with_normalized_fields": normalized_count,
        "conflict_count": len(conflicts),
        "conflicts": conflicts,
    }
    return CompressionResult(records=output_records, report=report)


def _normalize_record(record: BenzimidazoleLLMRecord) -> tuple[BenzimidazoleLLMRecord, bool]:
    updates: dict[str, object] = {}
    warnings = list(record.warnings)

    target_value = _normalize_target_value(record.target_value)
    if target_value != record.target_value:
        updates["target_value"] = target_value
        warnings.append("target_value_numeric_format_normalized")

    target_units = _normalize_llm_unit(record.target_type, record.target_units)
    if target_units != record.target_units:
        updates["target_units"] = target_units
        warnings.append(f"target_units_normalized:{record.target_units}->{target_units}")

    bacteria = _normalize_llm_bacteria(record.target_type, record.bacteria)
    if bacteria != record.bacteria:
        updates["bacteria"] = bacteria
        warnings.append(f"bacteria_normalized:{record.bacteria}->{bacteria}")

    if not updates:
        return record, False
    updates["warnings"] = _unique(warnings)
    return record.model_copy(update=updates), True


def _normalize_target_value(value: str) -> str:
    if value == MISSING_VALUE:
        return value
    pieces = value.replace(",", ".").split("-")
    try:
        normalized = [_format_decimal(Decimal(piece.strip())) for piece in pieces]
    except (InvalidOperation, ValueError):
        return value
    return "-".join(normalized)


def _format_decimal(value: Decimal) -> str:
    normalized = value.normalize()
    if normalized == normalized.to_integral():
        return str(normalized.quantize(Decimal("1")))
    return format(normalized, "f")


def _normalize_llm_unit(target_type: str, value: str) -> str:
    normalized = normalize_unit(value)
    if normalized in {"μM", "uM"}:
        normalized = "µM"
    if target_type == "pMIC" and normalized == MISSING_VALUE:
        return "µM"
    return normalized


def _normalize_llm_bacteria(target_type: str, value: str) -> str:
    stripped = value.strip()
    if stripped == MISSING_VALUE:
        return stripped
    compact = stripped.lower().replace(".", "").replace(" ", "")
    if target_type == "pMIC":
        if compact in {"ec", "ecoli", "escherichiacoli"}:
            return "EC"
        if compact in {"sa", "saureus", "staphaureus", "staphylococcusaureus"}:
            return "SA"
    if "n315" in compact or compact == "mrsa":
        return "MRSA N315"
    if "atcc29213" in compact:
        return "S. aureus ATCC 29213"
    if compact in {"ec", "ecoli", "escherichiacoli"}:
        return "E. coli"
    if compact in {"sa", "saureus", "staphaureus", "staphylococcusaureus"}:
        return "S. aureus"
    normalized = normalize_bacteria(stripped)
    if normalized == "Staphylococcus aureus":
        return "S. aureus"
    if normalized == "Escherichia coli":
        return "E. coli"
    return normalized


def _row_key(record: BenzimidazoleLLMRecord) -> tuple[str, ...]:
    row = record.chemx_row()
    return tuple(row[column] for column in CHEMX_COLUMNS)


def _dedup_key(record: BenzimidazoleLLMRecord) -> tuple[str, ...]:
    return (*_row_key(record), record.evidence_id)


def _row_dict(row_key: tuple[str, ...]) -> dict[str, str]:
    return dict(zip(CHEMX_COLUMNS, row_key, strict=True))


def _unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    unique_values: list[str] = []
    for value in values:
        if value not in seen:
            unique_values.append(value)
            seen.add(value)
    return unique_values
