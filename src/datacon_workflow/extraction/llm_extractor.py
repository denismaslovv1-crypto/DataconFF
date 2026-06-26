from __future__ import annotations

import json

from pydantic import ValidationError

from datacon_workflow.domains.benzimidazoles import BenzimidazoleRawRecord, EvidenceProvenance
from datacon_workflow.extraction.evidence_builder import EvidenceChunk


def parse_llm_json_array(response: str, chunk: EvidenceChunk) -> list[BenzimidazoleRawRecord]:
    """Validate a JSON-only LLM response against the evidence chunk it was given.

    This module intentionally has no network client: model choice and credentials remain
    outside the deterministic workflow.
    """
    payload = json.loads(response)
    if not isinstance(payload, list):
        raise ValueError("LLM response must be a JSON array")
    records: list[BenzimidazoleRawRecord] = []
    for item in payload:
        try:
            candidate = BenzimidazoleRawRecord.model_validate({
                **item,
                "evidence": EvidenceProvenance(
                    source_file=chunk.source.source_file,
                    page=chunk.source.page,
                    section=chunk.source.section,
                    table_id=chunk.source.table_id,
                    row_id=chunk.row_id,
                    evidence_text=chunk.text,
                    extraction_method="benzimidazole.llm_evidence_only",
                    confidence=0.4,
                ),
            })
        except ValidationError as exc:
            raise ValueError(f"Unsupported LLM record: {exc}") from exc
        if not candidate.target_value or candidate.target_value not in chunk.text:
            raise ValueError("LLM record target_value is not supported by its evidence chunk")
        records.append(candidate)
    return records
