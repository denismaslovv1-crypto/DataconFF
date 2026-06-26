from __future__ import annotations

import csv

from datacon_workflow.domains.benzimidazoles import (
    BenzimidazoleRawRecord,
    BenzimidazoleRecord,
    CHEMX_COLUMNS,
    EvidenceProvenance,
)
from datacon_workflow.export.chemx_csv import write_predictions
from datacon_workflow.extraction.evidence_builder import EvidenceChunk
from datacon_workflow.extraction.rule_extractor import extract_records
from datacon_workflow.normalization.records import normalize_record
from pdf_extraction.models import SourceProvenance


def evidence() -> EvidenceProvenance:
    return EvidenceProvenance(
        source_file="article.pdf", page=2, table_id="p2_t1", row_id="1",
        evidence_text="5a MIC = 4 ug/mL against S. aureus", extraction_method="test", confidence=1,
    )


def test_normalization_keeps_raw_record_unchanged() -> None:
    raw = BenzimidazoleRawRecord(
        compound_id="5a", target_type="mic", target_relation="=", target_value="4",
        target_units="ug/mL", bacteria="S. aureus", evidence=evidence(),
    )
    normalized = normalize_record(raw)
    assert raw.target_units == "ug/mL"
    assert normalized.target_units == "µg/mL"
    assert normalized.bacteria == "Staphylococcus aureus"


def test_exporter_uses_exact_chemx_columns(tmp_path) -> None:
    record = BenzimidazoleRecord(
        compound_id="5a", smiles="NOT_DETECTED", target_type="MIC", target_relation="=",
        target_value="4", target_units="µg/mL", bacteria="Staphylococcus aureus", evidence=evidence(),
    )
    csv_path, json_path = write_predictions([record], tmp_path)
    with csv_path.open(encoding="utf-8", newline="") as handle:
        rows = list(csv.DictReader(handle))
        assert tuple(rows[0]) == CHEMX_COLUMNS
        assert rows[0]["smiles"] == "NOT_DETECTED"
    assert json_path.exists()


def test_rule_extractor_reads_mic_relation_and_bacteria() -> None:
    chunk = EvidenceChunk(
        text="Compound 5a: MIC < 4 ug/mL against S. aureus",
        source=SourceProvenance(source_file="article.pdf", page=2, extraction_method="test", confidence=1),
        row_id="3",
    )
    records = extract_records([chunk])
    assert len(records) == 1
    assert records[0].compound_id == "5a"
    assert records[0].target_relation == "<"
    assert records[0].target_value == "4"


def test_rule_extractor_reads_two_mic_columns_from_table_like_text() -> None:
    chunk = EvidenceChunk(
        text=("Compd R n X MIC(µM)c MRSAMIC(µM)d Biofilm Cytotoxicity\n"
              "4 H 1 H 6.91±0.43 6.125±0.21 42.33 21.16 47.8 7.2\n"
              "c Invitro(MTCC3160) activity. d Invitro(MTCC96) MRSAMIC activity."),
        source=SourceProvenance(source_file="article.pdf", page=5, extraction_method="test", confidence=1),
    )
    records = extract_records([chunk])
    assert [(record.compound_id, record.target_value, record.bacteria) for record in records] == [
        ("4", "42.33", "MTCC 3160"),
        ("4", "21.16", "MRSA"),
    ]
