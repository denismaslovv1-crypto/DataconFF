from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, Field

from datacon_workflow.domains.benzimidazoles import BenzimidazoleRawRecord, BenzimidazoleRecord
from datacon_workflow.extraction.evidence_builder import EvidenceChunk
from pdf_extraction.models import ParsedPdfDocument


class WorkflowState(BaseModel):
    pdf_path: Path
    parsed_document: ParsedPdfDocument | None = None
    evidence_chunks: list[EvidenceChunk] = Field(default_factory=list)
    raw_records: list[BenzimidazoleRawRecord] = Field(default_factory=list)
    normalized_records: list[BenzimidazoleRecord] = Field(default_factory=list)
    validation_errors: list[str] = Field(default_factory=list)
    prediction_csv: Path | None = None
    prediction_json: Path | None = None
    metrics: dict[str, object] | None = None
