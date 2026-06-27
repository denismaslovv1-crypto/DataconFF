from __future__ import annotations

from datacon_workflow.confidence import assess_rule_extraction_confidence
from datacon_workflow.domains.benzimidazoles import BenzimidazoleRawRecord, EvidenceProvenance
from datacon_workflow.extraction.evidence_builder import EvidenceChunk
from datacon_workflow.normalization.records import normalize_record
from datacon_workflow.validation.schema_validator import validate_records
from pdf_extraction.models import ParsedPdfDocument, SourceProvenance


def _document(table_count: int = 1) -> ParsedPdfDocument:
    return ParsedPdfDocument(
        source_file="article.pdf",
        page_count=1,
        text_blocks=[],
        tables=[
            {
                "table_id": f"t{index}",
                "rows": [["Compound", "MIC"], ["5a", "4 ug/mL"]],
                "source": {
                    "source_file": "article.pdf",
                    "page": 1,
                    "table_id": f"t{index}",
                    "extraction_method": "test",
                    "confidence": 1,
                },
            }
            for index in range(table_count)
        ],
    )


def _chunk(page: int = 1, table_id: str | None = "t1") -> EvidenceChunk:
    return EvidenceChunk(
        text="5a MIC = 4 ug/mL against S. aureus",
        source=SourceProvenance(
            source_file="article.pdf",
            page=page,
            table_id=table_id,
            extraction_method="test",
            confidence=1,
        ),
        row_id="1",
    )


def _raw(confidence: float = 0.85) -> BenzimidazoleRawRecord:
    return BenzimidazoleRawRecord(
        compound_id="5a",
        target_type="MIC",
        target_relation="=",
        target_value="4",
        target_units="ug/mL",
        bacteria="S. aureus",
        evidence=EvidenceProvenance(
            source_file="article.pdf",
            page=1,
            table_id="t1",
            row_id="1",
            evidence_text="5a MIC = 4 ug/mL against S. aureus",
            extraction_method="test",
            confidence=confidence,
        ),
    )


def test_confidence_high_for_table_backed_valid_rule_records() -> None:
    raw_records = [_raw()]
    validated, errors = validate_records([normalize_record(record) for record in raw_records])

    report = assess_rule_extraction_confidence(_document(), [_chunk()], raw_records, validated, errors)

    assert report.should_run_llm is False
    assert report.confidence == "high"
    assert report.signals["validated_records"] == 1


def test_confidence_low_when_evidence_exists_but_validation_rejects_records() -> None:
    bad = _raw()
    bad.target_value = "99"
    validated, errors = validate_records([normalize_record(bad)])

    report = assess_rule_extraction_confidence(_document(table_count=0), [_chunk(table_id=None)], [bad], validated, errors)

    assert report.should_run_llm is True
    assert report.confidence == "low"
    assert {issue.code for issue in report.issues} >= {"high_validation_rejection_ratio", "no_validated_records"}
