from __future__ import annotations

import json
import re
from pathlib import Path

from datacon_workflow.evaluation.chemx_eval import evaluate_predictions
from datacon_workflow.export.chemx_csv import write_predictions
from datacon_workflow.extraction.evidence_builder import build_evidence_chunks
from datacon_workflow.extraction.rule_extractor import extract_records
from datacon_workflow.normalization.records import normalize_record
from datacon_workflow.orchestration import AgenticOrchestrationConfig, AgenticSupervisor
from datacon_workflow.state import WorkflowState
from datacon_workflow.validation.schema_validator import validate_records
from pdf_extraction.exporters import write_document_json
from pdf_extraction.pipeline import parse_pdf


class BenzimidazoleWorkflow:
    """Observable stage-by-stage workflow; raw and normalized values stay separate."""

    def run(
        self,
        pdf_path: Path,
        output_dir: Path,
        ground_truth_csv: Path | None = None,
        agentic_config: AgenticOrchestrationConfig | None = None,
    ) -> WorkflowState:
        state = WorkflowState(pdf_path=pdf_path)
        state.parsed_document = parse_pdf(pdf_path, output_dir=output_dir / "parsed")
        parsed_dir = output_dir / "parsed"
        parsed_dir.mkdir(parents=True, exist_ok=True)
        write_document_json(state.parsed_document, parsed_dir / f"{pdf_path.stem}.raw.json")
        state.evidence_chunks = build_evidence_chunks(state.parsed_document)
        (output_dir / "evidence.json").write_text(
            json.dumps([chunk.model_dump(mode="json") for chunk in state.evidence_chunks], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        config = agentic_config or AgenticOrchestrationConfig.from_env()
        if config.mode != "disabled":
            state.agentic_result = AgenticSupervisor().run(
                state.evidence_chunks,
                output_dir,
                pdf_path.stem,
                config,
            )
        state.raw_records = extract_records(state.evidence_chunks)
        candidates = [normalize_record(raw) for raw in state.raw_records]
        state.normalized_records, state.validation_errors = validate_records(candidates)
        state.prediction_csv, state.prediction_json = write_predictions(state.normalized_records, output_dir)
        if ground_truth_csv:
            state.metrics = evaluate_predictions(
                state.prediction_csv,
                ground_truth_csv,
                output_dir,
                benchmark_pdf_ids=_benchmark_pdf_ids(state),
                benchmark_pdf_name=pdf_path.stem,
            )
        return state


def run_benzimidazole_workflow(
    pdf_path: Path,
    output_dir: Path,
    ground_truth_csv: Path | None = None,
    agentic_config: AgenticOrchestrationConfig | None = None,
) -> WorkflowState:
    return BenzimidazoleWorkflow().run(pdf_path, output_dir, ground_truth_csv, agentic_config)


def _benchmark_pdf_ids(state: WorkflowState) -> set[str] | None:
    """Find article DOI identifiers embedded in parsed text for scoped metrics."""
    if state.parsed_document is None:
        return None
    identifiers: set[str] = set()
    for block in state.parsed_document.text_blocks:
        for doi in re.findall(r"10\.\d{4,9}/[-._;()/:A-Z0-9]+", block.text, flags=re.I):
            identifiers.add(doi.rstrip(".,;)]").lower())
    return identifiers or None
