from __future__ import annotations

import json
from pathlib import Path

import pytest

from datacon_workflow.orchestration import AgenticOrchestrationConfig, AgenticSupervisor, ChemicalValidator
from datacon_workflow.orchestration.agentic import _assert_not_forbidden_extraction_input
from datacon_workflow.extraction.evidence_builder import EvidenceChunk
from pdf_extraction.models import SourceProvenance


def _chunk(text: str) -> EvidenceChunk:
    return EvidenceChunk(
        text=text,
        source=SourceProvenance(source_file="article.pdf", page=2, table_id="t1", extraction_method="test", confidence=1),
        row_id="1",
    )


def test_replay_mode_loads_fixture_and_writes_sidecars(tmp_path) -> None:
    replay_dir = tmp_path / "replay"
    replay_dir.mkdir()
    fixture = [
        {
            "evidence_id": "ev_0000",
            "compound_id": "5a",
            "smiles": "NOT_DETECTED",
            "target_type": "MIC",
            "target_relation": "=",
            "target_value": "4",
            "target_units": "ug/mL",
            "bacteria": "S. aureus",
        }
    ]
    (replay_dir / "article.agentic_candidates.json").write_text(json.dumps(fixture), encoding="utf-8")

    result = AgenticSupervisor().run(
        [_chunk("Compound 5a MIC = 4 ug/mL against S. aureus.")],
        tmp_path / "out",
        "article",
        AgenticOrchestrationConfig(mode="replay", replay_dir=replay_dir),
    )

    assert result.status == "replay"
    assert len(result.candidates) == 1
    assert result.candidates[0].record.compound_id == "5a"
    assert (tmp_path / "out" / "agentic_candidates.json").exists()
    assert (tmp_path / "out" / "validation_report.json").exists()
    assert (tmp_path / "out" / "provenance_sidecar.json").exists()


def test_agentic_replay_does_not_overwrite_raw_candidate_values(tmp_path) -> None:
    replay_dir = tmp_path / "replay"
    replay_dir.mkdir()
    fixture = [
        {
            "evidence_id": "ev_0000",
            "compound_id": "5a",
            "smiles": "NOT_DETECTED",
            "target_type": "mic",
            "target_relation": "=",
            "target_value": "4",
            "target_units": "ug/mL",
            "bacteria": "S. aureus",
        }
    ]
    (replay_dir / "article.agentic_candidates.json").write_text(json.dumps(fixture), encoding="utf-8")

    result = AgenticSupervisor().run(
        [_chunk("Compound 5a MIC = 4 ug/mL against S. aureus.")],
        tmp_path / "out",
        "article",
        AgenticOrchestrationConfig(mode="replay", replay_dir=replay_dir),
    )

    record = result.candidates[0].record
    assert record.target_type == "mic"
    assert record.target_units == "ug/mL"
    assert record.bacteria == "S. aureus"


def test_invalid_smiles_and_generic_scaffolds_are_flagged() -> None:
    from datacon_workflow.domains.benzimidazoles import BenzimidazoleRawRecord, EvidenceProvenance
    from datacon_workflow.orchestration.agentic import AgenticCandidate

    evidence = EvidenceProvenance(
        source_file="article.pdf",
        page=2,
        evidence_text="Compound 5a MIC = 4 ug/mL against S. aureus.",
        extraction_method="test",
        confidence=1,
    )
    candidates = [
        AgenticCandidate(
            evidence_id="ev_0000",
            source="replay",
            record=BenzimidazoleRawRecord(
                compound_id="5a",
                smiles="C(C",
                target_type="MIC",
                target_relation="=",
                target_value="4",
                target_units="ug/mL",
                bacteria="S. aureus",
                evidence=evidence,
            ),
        ),
        AgenticCandidate(
            evidence_id="ev_0000",
            source="replay",
            record=BenzimidazoleRawRecord(
                compound_id="5b",
                smiles="*C(=O)R1",
                target_type="MIC",
                target_relation="=",
                target_value="4",
                target_units="ug/mL",
                bacteria="S. aureus",
                evidence=evidence,
            ),
        ),
    ]
    statuses = [item.status for item in ChemicalValidator().validate(candidates)]
    assert statuses == ["invalid", "generic_scaffold"]


def test_extraction_inputs_reject_ground_truth_and_predictions() -> None:
    with pytest.raises(ValueError):
        _assert_not_forbidden_extraction_input(Path("data/chemx/benzimidazoles/ground_truth.csv"))
    with pytest.raises(ValueError):
        _assert_not_forbidden_extraction_input(Path("outputs/benzimidazoles/predictions.json"))
