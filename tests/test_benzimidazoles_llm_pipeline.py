from __future__ import annotations

import csv
import json

import pytest
from pydantic import ValidationError

from datacon_workflow.domains.benzimidazoles import BenzimidazoleLLMRecord, CHEMX_COLUMNS, MISSING_VALUE
from datacon_workflow.export.llm_compression import compress_llm_records
from datacon_workflow.export.llm_chemx_csv import write_llm_predictions
from datacon_workflow.extraction.evidence_selector import BenzimidazoleEvidence
from datacon_workflow.extraction.evidence_selector import compress_benzimidazole_evidence
from datacon_workflow.extraction.evidence_selector import select_benzimidazole_evidence
from datacon_workflow.extraction.llm_batch_runner import apply_evidence_slice, run_llm_batches
from datacon_workflow.extraction.llm_extractor import LLMExtractionConfig, _anthropic_sdk_base_url
from datacon_workflow.validation.llm_schema_validator import validate_llm_payload
from pdf_extraction.models import ExtractedTable, ExtractedTextBlock, ParsedPdfDocument, SourceProvenance


def _source(page: int = 1, table_id: str | None = None) -> SourceProvenance:
    return SourceProvenance(
        source_file="article.pdf",
        page=page,
        table_id=table_id,
        extraction_method="test",
        confidence=1,
    )


def test_evidence_selector_finds_mic_bacteria_and_units() -> None:
    document = ParsedPdfDocument(
        source_file="article.pdf",
        page_count=1,
        text_blocks=[
            ExtractedTextBlock(
                text="Biological activity: compound 5a MIC 4 ug/mL against S. aureus.",
                source=_source(),
            )
        ],
        tables=[
            ExtractedTable(
                table_id="t1",
                rows=[["Compound", "MIC", "Organism"], ["7b", "8 µg/mL", "Escherichia coli"]],
                source=_source(table_id="t1"),
            )
        ],
    )
    evidence = select_benzimidazole_evidence(document)
    assert len(evidence) >= 2
    joined_terms = {term for chunk in evidence for term in chunk.matched_terms}
    assert {"MIC", "Staphylococcus aureus", "Escherichia coli"} <= joined_terms
    assert all(chunk.page == 1 for chunk in evidence)


def test_evidence_compression_caps_chunks_and_keeps_page_coverage() -> None:
    document = ParsedPdfDocument(
        source_file="article.pdf",
        page_count=3,
        text_blocks=[
            ExtractedTextBlock(
                text=f"Biological activity page {page}: compound {page}a MIC {page} ug/mL against S. aureus."
                + " Escherichia coli table MIC."
                + " extra" * 50,
                source=_source(page=page),
            )
            for page in range(1, 4)
        ],
        tables=[],
    )
    evidence = select_benzimidazole_evidence(document, context_characters=80)

    compressed = compress_benzimidazole_evidence(evidence, max_chunks=2)

    assert len(compressed) == 2
    assert len({chunk.page for chunk in compressed}) == 2
    assert all("MIC" in chunk.matched_terms for chunk in compressed)


def test_llm_schema_rejects_invalid_target_relation() -> None:
    with pytest.raises(ValidationError):
        BenzimidazoleLLMRecord(
            compound_id="5a",
            smiles=MISSING_VALUE,
            target_type="MIC",
            target_relation="<=",
            target_value="4",
            target_units="ug/mL",
            bacteria="S. aureus",
            evidence_id="e1",
        )


def test_llm_validator_fills_missing_fields_with_not_detected() -> None:
    records = validate_llm_payload([{}], evidence=[])
    assert len(records) == 1
    row = records[0].chemx_row()
    assert row == {column: MISSING_VALUE for column in CHEMX_COLUMNS}
    assert "compound_id_missing" in records[0].warnings


def test_llm_csv_exporter_writes_expected_columns(tmp_path) -> None:
    records = validate_llm_payload(
        [
            {
                "compound_id": "5a",
                "target_type": "MIC",
                "target_relation": "=",
                "target_value": "4",
                "target_units": "ug/mL",
                "bacteria": "S. aureus",
                "evidence_id": "e1",
            }
        ],
        evidence=[],
    )
    csv_path, sidecar_path = write_llm_predictions(records, evidence=[], output_dir=tmp_path)
    with csv_path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert tuple(rows[0]) == CHEMX_COLUMNS
    assert rows[0]["smiles"] == MISSING_VALUE
    assert sidecar_path.exists()


def test_llm_compression_normalizes_and_merges_exact_duplicates(tmp_path) -> None:
    records = validate_llm_payload(
        [
            {
                "compound_id": "9",
                "target_type": "pMIC",
                "target_relation": "=",
                "target_value": "1.40",
                "target_units": MISSING_VALUE,
                "bacteria": "Escherichia coli",
                "evidence_id": "e1",
            },
            {
                "compound_id": "9",
                "target_type": "pMIC",
                "target_relation": "=",
                "target_value": "1.4",
                "target_units": "μM",
                "bacteria": "EC",
                "evidence_id": "e1",
            },
            {
                "compound_id": "9",
                "target_type": "pMIC",
                "target_relation": "=",
                "target_value": "1.6",
                "target_units": MISSING_VALUE,
                "bacteria": "Escherichia coli",
                "evidence_id": "e3",
            },
        ],
        evidence=[],
    )

    compressed = compress_llm_records(records)

    assert compressed.report["input_records"] == 3
    assert compressed.report["output_records"] == 2
    assert compressed.report["exact_duplicates_merged"] == 1
    assert compressed.report["conflict_count"] == 1
    assert compressed.records[0].record.chemx_row()["target_units"] == "µM"
    assert compressed.records[0].record.chemx_row()["bacteria"] == "EC"
    assert compressed.records[0].duplicate_count == 2
    assert compressed.records[0].evidence_ids == ("e1",)

    csv_path, sidecar_path = write_llm_predictions(records, evidence=[], output_dir=tmp_path)
    with csv_path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
    report = json.loads((tmp_path / "dedup_report.json").read_text(encoding="utf-8"))
    sidecar = json.loads(sidecar_path.read_text(encoding="utf-8"))

    assert len(rows) == 2
    assert rows[0]["target_value"] == "1.4"
    assert rows[0]["target_units"] == "µM"
    assert rows[0]["bacteria"] == "EC"
    assert report["exact_duplicates_merged"] == 1
    assert sidecar[0]["duplicate_count"] == 2
    assert sidecar[0]["merged_evidence_ids"] == ["e1"]


def test_llm_compression_preserves_same_rows_from_distinct_evidence() -> None:
    records = validate_llm_payload(
        [
            {
                "compound_id": "9",
                "target_type": "MIC",
                "target_relation": "=",
                "target_value": "4.0",
                "target_units": "ug/mL",
                "bacteria": "Staphylococcus aureus",
                "evidence_id": "e1",
            },
            {
                "compound_id": "9",
                "target_type": "MIC",
                "target_relation": "=",
                "target_value": "4",
                "target_units": "µg/mL",
                "bacteria": "S. aureus",
                "evidence_id": "e2",
            },
        ],
        evidence=[],
    )

    compressed = compress_llm_records(records)

    assert compressed.report["input_records"] == 2
    assert compressed.report["output_records"] == 2
    assert compressed.report["exact_duplicates_merged"] == 0
    assert [item.duplicate_count for item in compressed.records] == [1, 1]


def test_llm_compression_uses_benchmark_bacteria_labels_for_mic() -> None:
    records = validate_llm_payload(
        [
            {
                "compound_id": "7d",
                "target_type": "MIC",
                "target_relation": "=",
                "target_value": "0.006",
                "target_units": "mM",
                "bacteria": "Staphylococcus aureus ATCC 29213",
                "evidence_id": "e1",
            },
            {
                "compound_id": "7d",
                "target_type": "MIC",
                "target_relation": "=",
                "target_value": "0.013",
                "target_units": "mM",
                "bacteria": "Escherichia coli",
                "evidence_id": "e2",
            },
            {
                "compound_id": "7d",
                "target_type": "MIC",
                "target_relation": "=",
                "target_value": "0.006",
                "target_units": "mM",
                "bacteria": "Staphylococcus aureus (MRSA N315)",
                "evidence_id": "e3",
            },
        ],
        evidence=[],
    )

    rows = [item.record.chemx_row() for item in compress_llm_records(records).records]

    assert [row["bacteria"] for row in rows] == ["S. aureus ATCC 29213", "E. coli", "MRSA N315"]


def test_openmodel_defaults_to_anthropic_messages(monkeypatch) -> None:
    for name in (
        "CHEMX_LLM_PROVIDER",
        "CHEMX_LLM_API_TYPE",
        "CHEMX_LLM_MODEL",
        "CHEMX_LLM_API_KEY",
        "CHEMX_LLM_API_KEY_ENV",
        "EXTRACTION_AGENT_PROVIDER",
        "EXTRACTION_AGENT_API_TYPE",
        "EXTRACTION_AGENT_MODEL",
        "EXTRACTION_AGENT_API_KEY_ENV",
        "OPENMODEL_API_KEY",
    ):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setenv("EXTRACTION_AGENT_PROVIDER", "openmodel")
    monkeypatch.setenv("EXTRACTION_AGENT_API_TYPE", "")
    monkeypatch.setenv("EXTRACTION_AGENT_MODEL", "deepseek-v4-flash")
    monkeypatch.setenv("OPENMODEL_API_KEY", "test-key")

    config = LLMExtractionConfig.from_env()

    assert config.api_type == "anthropic_messages"
    assert config.api_key == "test-key"


def test_anthropic_sdk_base_url_strips_trailing_v1() -> None:
    assert _anthropic_sdk_base_url("https://api.openmodel.ai/v1") == "https://api.openmodel.ai"
    assert _anthropic_sdk_base_url("https://proxy.example/anthropic") == "https://proxy.example/anthropic"


def test_evidence_slice_uses_python_style_start_stop() -> None:
    evidence = [
        BenzimidazoleEvidence(
            evidence_id=f"e{index}",
            source_file="article.pdf",
            page=index,
            source_text=f"compound {index}a MIC {index} ug/mL against S. aureus",
            score=1,
            matched_terms=["MIC", "Staphylococcus aureus"],
        )
        for index in range(5)
    ]

    sliced = apply_evidence_slice(evidence, "1:3")

    assert [item.evidence_id for item in sliced] == ["e1", "e2"]


def test_disabled_llm_batch_run_writes_empty_artifact(tmp_path) -> None:
    evidence = [
        BenzimidazoleEvidence(
            evidence_id="e1",
            source_file="article.pdf",
            page=1,
            source_text="compound 5a MIC 4 ug/mL against S. aureus",
            score=1,
            matched_terms=["MIC", "Staphylococcus aureus"],
        )
    ]

    result = run_llm_batches(
        evidence=evidence,
        article_dir=tmp_path,
        batch_size=1,
        config=LLMExtractionConfig(),
    )

    assert result.status == "disabled"
    assert result.records == []
    assert (tmp_path / "llm_batches" / "batch_001" / "llm_raw_response.json").read_text(encoding="utf-8") == "[]\n"
