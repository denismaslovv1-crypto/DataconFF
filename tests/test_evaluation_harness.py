from __future__ import annotations

import json

from datacon_workflow.domains.benzimidazoles import BenzimidazoleRawRecord, EvidenceProvenance
from datacon_workflow.evaluation.harness import run_llm_evidence_selector, run_llm_extractor, run_validator
from datacon_workflow.extraction.evidence_builder import EvidenceChunk
from pdf_extraction.models import SourceProvenance


def _chunk(text: str) -> EvidenceChunk:
    return EvidenceChunk(
        text=text,
        source=SourceProvenance(source_file="article.pdf", page=1, extraction_method="test", confidence=1),
    )


def test_selector_passthrough_does_not_reduce_rule_recall(tmp_path) -> None:
    chunks = [_chunk("Compound 5a MIC = 4 ug/mL against S. aureus")]
    selected, stage = run_llm_evidence_selector(chunks, tmp_path)
    assert selected == chunks
    assert stage.status == "passthrough"
    assert stage.metrics["recall_not_reduced"] is True


def test_llm_extractor_replay_counts_invalid_json(tmp_path) -> None:
    chunks = [_chunk("Compound 5a MIC = 4 ug/mL against S. aureus")]
    replay = tmp_path / "article.extractor.json"
    replay.write_text(
        json.dumps({
            "responses": [
                {
                    "chunk_index": 0,
                    "response": json.dumps([
                        {
                            "compound_id": "5a",
                            "target_type": "MIC",
                            "target_relation": "=",
                            "target_value": "4",
                            "target_units": "ug/mL",
                            "bacteria": "S. aureus",
                        }
                    ]),
                },
                {"chunk_index": 0, "response": "not json"},
            ]
        }),
        encoding="utf-8",
    )
    records, stage = run_llm_extractor(chunks, tmp_path, replay)
    assert len(records) == 1
    assert stage.metrics["responses_total"] == 2
    assert stage.metrics["valid_json_rate"] == 0.5


def test_validator_rejects_hallucinated_target_value(tmp_path) -> None:
    raw = BenzimidazoleRawRecord(
        compound_id="5a",
        target_type="MIC",
        target_relation="=",
        target_value="999",
        target_units="ug/mL",
        bacteria="S. aureus",
        evidence=EvidenceProvenance(
            source_file="article.pdf",
            page=1,
            evidence_text="Compound 5a MIC = 4 ug/mL against S. aureus",
            extraction_method="test",
            confidence=1,
        ),
    )
    accepted, errors, stage = run_validator([raw], tmp_path)
    assert accepted == []
    assert errors
    assert stage.metrics["rejected_records"] == 1
