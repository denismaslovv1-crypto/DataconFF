from __future__ import annotations

from collections import defaultdict

from pydantic import BaseModel, Field

from datacon_workflow.domains.benzimidazoles import BenzimidazoleRawRecord, BenzimidazoleRecord, MISSING_VALUE
from datacon_workflow.extraction.evidence_builder import EvidenceChunk
from pdf_extraction.models import ParsedPdfDocument


class ConfidenceIssue(BaseModel):
    code: str
    severity: str
    message: str


class ExtractionConfidenceReport(BaseModel):
    should_run_llm: bool
    confidence: str
    issues: list[ConfidenceIssue] = Field(default_factory=list)
    signals: dict[str, float | int | bool] = Field(default_factory=dict)


def assess_rule_extraction_confidence(
    document: ParsedPdfDocument,
    evidence_chunks: list[EvidenceChunk],
    raw_records: list[BenzimidazoleRawRecord],
    validated_records: list[BenzimidazoleRecord],
    validation_errors: list[str],
) -> ExtractionConfidenceReport:
    """Assess deterministic extraction quality from observable local signals.

    This does not use benchmark labels and does not use a fixed prediction-count
    gate. It asks whether the parser/rules look structurally trustworthy enough
    to skip an LLM fallback.
    """
    evidence_pages = {chunk.source.page for chunk in evidence_chunks if chunk.source.page is not None}
    record_pages = {record.evidence.page for record in validated_records if record.evidence.page is not None}
    table_count = len(document.tables)
    table_evidence_count = sum(1 for chunk in evidence_chunks if chunk.source.table_id is not None)
    table_record_count = sum(1 for record in validated_records if record.evidence.table_id is not None)
    table_like_record_count = sum(
        1 for record in validated_records
        if record.evidence.table_id == "table_like_text" or "table" in record.evidence.extraction_method
    )
    rejection_total = len(validated_records) + len(validation_errors)
    rejection_ratio = len(validation_errors) / rejection_total if rejection_total else 0.0
    avg_confidence = (
        sum(record.evidence.confidence for record in validated_records) / len(validated_records)
        if validated_records else 0.0
    )
    coverage_ratio = len(record_pages) / len(evidence_pages) if evidence_pages else 0.0
    missing_required_ratio = _missing_required_ratio(raw_records)
    conflict_count = _conflict_count(validated_records)

    issues: list[ConfidenceIssue] = []
    if not evidence_chunks:
        issues.append(_issue("no_evidence", "high", "No Benzimidazoles evidence chunks were selected from the parsed PDF."))
    if table_count == 0 and table_like_record_count == 0:
        issues.append(_issue("no_parsed_tables", "medium", "The PDF parser found no structured tables."))
    elif table_count > 0 and table_evidence_count == 0:
        issues.append(_issue("no_table_evidence", "medium", "Parsed tables exist, but none became Benzimidazoles evidence."))
    if table_record_count == 0 and table_evidence_count > 0:
        issues.append(_issue("no_table_records", "medium", "Table evidence was selected, but rule extraction produced no table-backed records."))
    if coverage_ratio < 0.35 and evidence_pages and avg_confidence < 0.75:
        issues.append(_issue("low_evidence_page_coverage", "medium", "Validated records cover a small share of evidence-bearing pages."))
    if avg_confidence < 0.7 and validated_records:
        issues.append(_issue("low_average_record_confidence", "medium", "Rule records are mostly from lower-confidence prose snippets."))
    if rejection_ratio > 0.25:
        issues.append(_issue("high_validation_rejection_ratio", "high", "Many rule candidates were rejected by schema/evidence validation."))
    if missing_required_ratio > 0.25:
        issues.append(_issue("many_missing_required_fields", "high", "Many raw rule candidates are missing required ChemX fields."))
    if conflict_count:
        issues.append(_issue("conflicting_rule_records", "medium", "Validated rule records disagree for the same compound/type/bacteria key."))
    if not validated_records and evidence_chunks:
        issues.append(_issue("no_validated_records", "high", "Evidence exists, but no rule records survived validation."))

    should_run_llm = any(issue.severity == "high" for issue in issues) or len(issues) >= 2
    confidence = "low" if should_run_llm else ("medium" if issues else "high")
    return ExtractionConfidenceReport(
        should_run_llm=should_run_llm,
        confidence=confidence,
        issues=issues,
        signals={
            "parsed_tables": table_count,
            "evidence_chunks": len(evidence_chunks),
            "table_evidence_chunks": table_evidence_count,
            "table_like_records": table_like_record_count,
            "raw_records": len(raw_records),
            "validated_records": len(validated_records),
            "validation_errors": len(validation_errors),
            "validation_rejection_ratio": round(rejection_ratio, 4),
            "average_record_confidence": round(avg_confidence, 4),
            "evidence_page_count": len(evidence_pages),
            "record_page_count": len(record_pages),
            "evidence_page_coverage_ratio": round(coverage_ratio, 4),
            "missing_required_field_ratio": round(missing_required_ratio, 4),
            "conflict_count": conflict_count,
        },
    )


def _issue(code: str, severity: str, message: str) -> ConfidenceIssue:
    return ConfidenceIssue(code=code, severity=severity, message=message)


def _missing_required_ratio(records: list[BenzimidazoleRawRecord]) -> float:
    if not records:
        return 0.0
    missing = 0
    required = ("compound_id", "target_type", "target_value", "target_units", "bacteria")
    for record in records:
        if any(getattr(record, field) == MISSING_VALUE for field in required):
            missing += 1
    return missing / len(records)


def _conflict_count(records: list[BenzimidazoleRecord]) -> int:
    groups: dict[tuple[str, str, str], set[tuple[str, str, str]]] = defaultdict(set)
    for record in records:
        key = (record.compound_id, record.target_type, record.bacteria)
        if MISSING_VALUE in key:
            continue
        groups[key].add((record.target_relation, record.target_value, record.target_units))
    return sum(1 for values in groups.values() if len(values) > 1)
