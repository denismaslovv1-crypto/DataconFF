from __future__ import annotations

import csv

from datacon_workflow.domains.benzimidazoles import (
    BenzimidazoleRawRecord,
    BenzimidazoleRecord,
    CHEMX_COLUMNS,
    EvidenceProvenance,
)
from datacon_workflow.domains.benzimidazole_units import extract_target_unit_from_evidence
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


def test_unit_helper_extracts_table_header_units() -> None:
    assert extract_target_unit_from_evidence("Table 1 activity (MIC, mM) compound 1 12") == "mM"
    assert extract_target_unit_from_evidence("Table 1 activity (MIC, µM) compound 1 12") == "µM"
    assert extract_target_unit_from_evidence("Table 1 activity (MIC, μM) compound 1 12") == "μM"
    assert extract_target_unit_from_evidence("Table 1 activity (MIC, ug/mL) compound 1 12") == "ug/mL"
    assert extract_target_unit_from_evidence("Table 1 activity (MIC, µg/mL) compound 1 12") == "µg/mL"
    assert extract_target_unit_from_evidence("Table 1 activity (MIC, mg/L) compound 1 12") == "mg/L"


def test_unit_helper_extracts_compact_micromole_units_near_values() -> None:
    assert extract_target_unit_from_evidence("Compound 2k MIC=12.5µmolmL−1 against S.aureus", "12.5") == "µmolmL−1"
    assert extract_target_unit_from_evidence("MIC = 3.125 µmol mL-1 against E.coli", "3.125") == "µmol mL-1"
    assert extract_target_unit_from_evidence("range 3.125–12.5µmolmL−1", "3.125-12.5") == "µmolmL−1"
    assert extract_target_unit_from_evidence("compound 1 MIC 8 μmol/mL", "8") == "μmol/mL"


def test_unit_helper_extracts_mass_units() -> None:
    assert extract_target_unit_from_evidence("MIC 4 µg mL−1 against S. aureus", "4") == "µg mL−1"
    assert extract_target_unit_from_evidence("MIC 4 ug/mL against S. aureus", "4") == "ug/mL"
    assert extract_target_unit_from_evidence("MIC 4 mg L−1 against S. aureus", "4") == "mg L−1"


def test_unit_helper_does_not_invent_units() -> None:
    assert extract_target_unit_from_evidence("Compound 5a MIC 4 against S. aureus", "4") == "NOT_DETECTED"


def test_rule_extractor_uses_header_carried_unit() -> None:
    chunk = EvidenceChunk(
        text=("Table 1 Antibacterial activities (MIC, mM)\n"
              "Compound 5a MIC = 4 against S. aureus"),
        source=SourceProvenance(source_file="article.pdf", page=2, extraction_method="test", confidence=1),
    )
    records = extract_records([chunk])
    row_records = [record for record in records if record.target_value == "4"]
    assert len(row_records) == 1
    assert row_records[0].target_units == "mM"


def test_rule_extractor_uses_compact_unit_near_value() -> None:
    chunk = EvidenceChunk(
        text="Compound 2k showed activity against S.aureus, MIC=12.5µmolmL−1.",
        source=SourceProvenance(source_file="article.pdf", page=2, extraction_method="test", confidence=1),
    )
    records = extract_records([chunk])
    assert len(records) == 1
    assert records[0].target_units == "µmolmL−1"


def test_rule_extractor_reads_bk_antibacterial_table_only_target_bacteria() -> None:
    chunk = EvidenceChunk(
        text=(
            "Table3\n"
            "InvitroantimicrobialandantioxidantevaluationMICvalues(μg/mL)ofcompounds(BK-1–11).\n"
            "Antibacterialactivity Antifungalactivity Antioxidantactivity\n"
            "Compounds B.subtilis S.aureus E.coli P.aeruginosa A.niger DPPH NO\n"
            "BK-1 1.25 1.25 0.625 1.25 12.5 32.07 42.10\n"
            "BK-2 2.5 1.25 2.5 5.0 25.0 44.34 58.36\n"
            "BK-10 2.5 2.5 0.156 0.312 75.0 63.85 88.10\n"
            "BK-11 2.5 2.5 1.25 1.25 50 58.35 85.64\n"
        ),
        source=SourceProvenance(source_file="article.pdf", page=5, extraction_method="test", confidence=1),
        row_id="table_like_text",
    )

    records = extract_records([chunk])

    assert [(record.compound_id, record.bacteria, record.target_value, record.target_units) for record in records] == [
        ("BK-1", "S. aureus", "1.25", "μg/mL"),
        ("BK-1", "E. coli", "0.625", "μg/mL"),
        ("BK-2", "S. aureus", "1.25", "μg/mL"),
        ("BK-2", "E. coli", "2.5", "μg/mL"),
        ("BK-10", "S. aureus", "2.5", "μg/mL"),
        ("BK-10", "E. coli", "0.156", "μg/mL"),
        ("BK-11", "S. aureus", "2.5", "μg/mL"),
        ("BK-11", "E. coli", "1.25", "μg/mL"),
    ]


def test_rule_extractor_reads_abbreviated_antimicrobial_mic_table() -> None:
    chunk = EvidenceChunk(
        text=(
            "Table 1 Antimicrobial screening results of compounds 4a-f and 6a-f presented as MIC (μg/mL)\n"
            "Compd. no Gram-positive organisms Gram-negative organisms Fungi organisms\n"
            "Bc Sa Pa Ec Ab Ca\n"
            "4a 64 64 256 128 128 128\n"
            "4b 128 128 128 128 256 256\n"
            "Ciprofloxacin 8 4 8 4 - -\n"
        ),
        source=SourceProvenance(source_file="article.pdf", page=6, extraction_method="test", confidence=1),
        row_id="table_like_text",
    )

    records = extract_records([chunk])

    assert [(record.compound_id, record.bacteria, record.target_value, record.target_units) for record in records] == [
        ("4a", "S. aureus", "64", "μg/mL"),
        ("4a", "E. coli", "128", "μg/mL"),
        ("4b", "S. aureus", "128", "μg/mL"),
        ("4b", "E. coli", "128", "μg/mL"),
    ]
    assert all(record.evidence.table_id == "table_like_text" for record in records)
    assert all("Bc Sa Pa Ec Ab Ca" in record.evidence.evidence_text for record in records)


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


def test_rule_extractor_reads_labelled_antimicrobial_table() -> None:
    chunk = EvidenceChunk(
        text=("Table 4 Antimicrobial MIC (mg mL−1)\n"
              "Antibacterial Antifungal Anticancer\n"
              "Entry Code EC PA SF MSSA MRSA CA AN\n"
              "1 3a 64 — 128 64 128 512 512\n"
              "2 3b 64 512 64 64 64 256 256"),
        source=SourceProvenance(source_file="article.pdf", page=8, extraction_method="test", confidence=1),
    )
    records = extract_records([chunk])
    assert [(record.compound_id, record.target_value, record.bacteria, record.target_units) for record in records] == [
        ("3a", "64", "Escherichia coli ATCC 25922", "mg/mL"),
        ("3a", "64", "MSSA, Methicillin-susceptible strains of Staphylococcus aureus ATCC 29213", "mg/mL"),
        ("3a", "128", "MRSA, Methicillin-resistant strains of Staphylococcus aureus ATCC 43300", "mg/mL"),
        ("3b", "64", "Escherichia coli ATCC 25922", "mg/mL"),
        ("3b", "64", "MSSA, Methicillin-susceptible strains of Staphylococcus aureus ATCC 29213", "mg/mL"),
        ("3b", "64", "MRSA, Methicillin-resistant strains of Staphylococcus aureus ATCC 43300", "mg/mL"),
    ]


def test_rule_extractor_recovers_reversed_antimicrobial_table() -> None:
    chunk = EvidenceChunk(
        text="lairetcabitnA\nASRM ASSM FS AP CE edoC yrtnE\n215 215 821 46 821 — 46 a1 1",
        source=SourceProvenance(source_file="article.pdf", page=6, extraction_method="test", confidence=1),
    )
    records = extract_records([chunk])
    assert [(record.compound_id, record.target_value) for record in records] == [
        ("1a", "64"), ("1a", "64"), ("1a", "128"),
    ]


def test_rule_extractor_recovers_vertical_antimicrobial_table() -> None:
    chunk = EvidenceChunk(
        text=("lairetcabitnA\nASRM\nASSM\nFS\nAP\nCE\nedoC\nyrtnE\n"
              "x\nx\nx\nx\nx\nx\nx\n821\n46\n821\n—\n46\na1\n1"),
        source=SourceProvenance(source_file="article.pdf", page=6, extraction_method="test", confidence=1),
    )
    records = extract_records([chunk])
    assert [(record.compound_id, record.target_value) for record in records] == [
        ("1a", "64"), ("1a", "64"), ("1a", "128"),
    ]
