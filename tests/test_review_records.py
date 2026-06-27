from __future__ import annotations

import json
from pathlib import Path

from datacon_workflow.review_records import (
    NOT_AVAILABLE,
    build_review_records,
    detect_compound_mention,
    duplicate_diagnostics,
    mark_duplicate_status,
    stable_evidence_id,
)


def test_compound_mention_detects_numeric_and_alphanumeric_labels() -> None:
    assert detect_compound_mention("40", "Compound no. 40 showed MIC activity.") == "Compound no. 40"
    assert detect_compound_mention("4a", "The compound (4a) was isolated.") == "compound (4a)"
    assert detect_compound_mention("5a", "Series 5a was evaluated.") == "Series 5a"


def test_compound_mention_detects_ranges_and_table_first_cell() -> None:
    assert detect_compound_mention("4c", "Compounds 4a-4d were screened.") == "Compounds 4a-4d"
    assert detect_compound_mention("4d", "Compounds 4a–4d were screened.") == "Compounds 4a–4d"
    assert detect_compound_mention("BK-1", "Header\nBK-1 1.25 0.625") == "BK-1"


def test_compound_mention_avoids_unrelated_numbers() -> None:
    text = "Journal of Molecular Structure 1282 (2023) 135179 reported MIC 0.32."
    assert detect_compound_mention("1282", text) == NOT_AVAILABLE
    assert detect_compound_mention("0.32", text) == NOT_AVAILABLE


def test_review_records_link_embedded_evidence(tmp_path: Path) -> None:
    output_dir = tmp_path / "article"
    output_dir.mkdir()
    evidence = {
        "source_file": "article.pdf",
        "page": 2,
        "table_id": "table_like_text",
        "row_id": "4a",
        "evidence_text": "Compounds 4a-4d were screened.\n4a 1 2",
        "extraction_method": "benzimidazole.rule_extractor",
        "confidence": 0.8,
    }
    _write_json(
        output_dir / "predictions.json",
        [
            {
                "compound_id": "4a",
                "smiles": "NOT_DETECTED",
                "target_type": "MIC",
                "target_relation": "=",
                "target_value": "1",
                "target_units": "ug/mL",
                "bacteria": "S. aureus",
                "evidence": evidence,
            }
        ],
    )

    rows = build_review_records(output_dir)

    assert rows[0]["evidence_id"] == stable_evidence_id(evidence)
    assert rows[0]["page"] == "2"
    assert rows[0]["compound_label_found"] == "yes"
    assert rows[0]["source_kind"] == "table_like_text"


def test_review_records_fallback_from_sidecar_rule_id(tmp_path: Path) -> None:
    output_dir = tmp_path / "article"
    rules_dir = output_dir / "rules"
    rules_dir.mkdir(parents=True)
    evidence = {
        "source_file": "article.pdf",
        "page": 5,
        "table_id": "table_like_text",
        "row_id": "BK-1",
        "evidence_text": "BK-1 1.25 0.625",
        "extraction_method": "benzimidazole.rule_extractor.target_antibacterial_table",
        "confidence": 0.85,
    }
    _write_json(
        rules_dir / "predictions.json",
        [
            {
                "compound_id": "BK-1",
                "smiles": "NOT_DETECTED",
                "target_type": "MIC",
                "target_relation": "=",
                "target_value": "1.25",
                "target_units": "mm",
                "bacteria": "Staphylococcus aureus",
                "evidence": evidence,
            }
        ],
    )
    _write_json(
        output_dir / "predictions_with_evidence.json",
        [
            {
                "record": {
                    "compound_id": "BK-1",
                    "smiles": "NOT_DETECTED",
                    "target_type": "MIC",
                    "target_relation": "=",
                    "target_value": "1.25",
                    "target_units": "mm",
                    "bacteria": "S. aureus",
                    "evidence_id": "rule-1",
                },
                "evidence": None,
                "merged_evidence_ids": ["rule-1"],
            }
        ],
    )

    rows = build_review_records(output_dir)

    assert rows[0]["evidence_id"] == "rule-1"
    assert rows[0]["source_text"] == "BK-1 1.25 0.625"
    assert rows[0]["bacteria"] == "S. aureus"


def test_missing_provenance_is_not_available(tmp_path: Path) -> None:
    output_dir = tmp_path / "article"
    output_dir.mkdir()
    _write_json(
        output_dir / "predictions_with_evidence.json",
        [
            {
                "record": {
                    "compound_id": "7b",
                    "smiles": "NOT_DETECTED",
                    "target_type": "MIC",
                    "target_relation": "=",
                    "target_value": "2",
                    "target_units": "ug/mL",
                    "bacteria": "E. coli",
                    "evidence_id": "rule-2",
                },
                "evidence": None,
            }
        ],
    )

    rows = build_review_records(output_dir)

    assert rows[0]["source_text"] == NOT_AVAILABLE
    assert rows[0]["page"] == ""
    assert rows[0]["compound_mention"] == NOT_AVAILABLE


def test_duplicate_status_distinguishes_same_and_distinct_evidence() -> None:
    base = {
        "compound_id": "4a",
        "smiles": "NOT_DETECTED",
        "target_type": "MIC",
        "target_relation": "=",
        "target_value": "1",
        "target_units": "ug/mL",
        "bacteria": "S. aureus",
        "source_text": "same",
    }
    rows = mark_duplicate_status(
        [
            {**base, "evidence_id": "ev:1"},
            {**base, "evidence_id": "ev:1"},
            {**base, "evidence_id": "ev:2", "source_text": "different"},
        ]
    )

    assert rows[0]["duplicate_status"] == "duplicate_same_evidence"
    assert rows[1]["duplicate_status"] == "duplicate_same_evidence"
    assert rows[2]["duplicate_status"] == "repeated_distinct_evidence"
    diagnostics = duplicate_diagnostics(rows)
    assert diagnostics["duplicates_with_same_evidence_id"] == 1
    assert diagnostics["repeated_mentions_with_different_evidence_id"] == 3


def _write_json(path: Path, payload: object) -> None:
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
