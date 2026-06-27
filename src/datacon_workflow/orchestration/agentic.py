from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field, ValidationError

from datacon_workflow.domains.benzimidazoles import BenzimidazoleRawRecord, EvidenceProvenance, MISSING_VALUE
from datacon_workflow.extraction.evidence_builder import EvidenceChunk


AgenticMode = Literal["disabled", "replay", "live"]

FORBIDDEN_EXTRACTION_INPUT_NAMES = {
    "ground_truth.csv",
    "predictions.csv",
    "predictions.json",
    "predictions_with_evidence.json",
    "metrics.json",
    "field_metrics.csv",
}


class PlannedEvidence(BaseModel):
    evidence_id: str
    text: str
    source_file: str
    page: int | None = None
    section: str | None = None
    table_id: str | None = None
    row_id: str | None = None
    matched_terms: list[str] = Field(default_factory=list)
    score: float = 0.0


class AgenticCandidate(BaseModel):
    record: BenzimidazoleRawRecord
    evidence_id: str
    source: Literal["replay", "live"]


class CandidateIssue(BaseModel):
    index: int | None = None
    evidence_id: str | None = None
    field: str | None = None
    status: str
    message: str


class ChemicalValidationResult(BaseModel):
    index: int
    smiles: str
    status: str
    message: str


class Conflict(BaseModel):
    kind: Literal["duplicate", "conflict"]
    indexes: list[int]
    key: str
    message: str


class AgenticOrchestrationResult(BaseModel):
    mode: AgenticMode
    status: str
    selected_evidence: list[PlannedEvidence] = Field(default_factory=list)
    candidates: list[AgenticCandidate] = Field(default_factory=list)
    schema_issues: list[CandidateIssue] = Field(default_factory=list)
    chemical_validation: list[ChemicalValidationResult] = Field(default_factory=list)
    conflicts: list[Conflict] = Field(default_factory=list)
    artifacts: dict[str, str] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)


@dataclass(frozen=True)
class AgenticOrchestrationConfig:
    mode: AgenticMode = "disabled"
    replay_dir: Path | None = None
    max_evidence_chunks: int = 40

    @classmethod
    def from_env(cls) -> "AgenticOrchestrationConfig":
        mode = os.getenv("CHEMX_AGENTIC_MODE", "disabled").strip().lower() or "disabled"
        if mode not in {"disabled", "replay", "live"}:
            raise ValueError("CHEMX_AGENTIC_MODE must be disabled, replay, or live.")
        replay_dir = os.getenv("CHEMX_AGENTIC_REPLAY_DIR")
        return cls(mode=mode, replay_dir=Path(replay_dir) if replay_dir else None)


class EvidencePlanner:
    """Deterministically select compact Benzimidazoles evidence for workers."""

    _terms = (
        ("pMIC", re.compile(r"\bpMIC\b", re.I), 5.0),
        ("MIC", re.compile(r"\bMIC\b", re.I), 4.0),
        ("Staphylococcus aureus", re.compile(r"\b(?:S\.?\s*aureus|Staph(?:ylococcus)?\.?\s*aureus|MSSA|MRSA)\b", re.I), 3.0),
        ("Escherichia coli", re.compile(r"\b(?:E\.?\s*coli|Escherichia\s+coli|EC)\b", re.I), 3.0),
        ("units", re.compile(r"\b(?:ug/mL|µg/mL|μg/mL|mg/mL|µM|uM)\b", re.I), 2.0),
    )

    def plan(self, chunks: list[EvidenceChunk], max_chunks: int = 40) -> list[PlannedEvidence]:
        planned: list[PlannedEvidence] = []
        for index, chunk in enumerate(chunks):
            terms: list[str] = []
            score = 0.0
            for name, pattern, weight in self._terms:
                if pattern.search(chunk.text):
                    terms.append(name)
                    score += weight
            if score <= 0:
                continue
            planned.append(
                PlannedEvidence(
                    evidence_id=f"ev_{index:04d}",
                    text=chunk.text,
                    source_file=chunk.source.source_file,
                    page=chunk.source.page,
                    section=chunk.source.section,
                    table_id=chunk.source.table_id,
                    row_id=chunk.row_id,
                    matched_terms=terms,
                    score=score,
                )
            )
        return sorted(planned, key=lambda item: (-item.score, item.evidence_id))[:max_chunks]


class ExtractionAnalyst:
    """Load replayed candidates or report live extraction as unavailable."""

    def produce_candidates(
        self,
        selected_evidence: list[PlannedEvidence],
        config: AgenticOrchestrationConfig,
        pdf_stem: str,
    ) -> tuple[list[AgenticCandidate], list[CandidateIssue], list[str], str]:
        if config.mode == "replay":
            return self._from_replay(selected_evidence, config, pdf_stem)
        if config.mode == "live":
            required = ("CHEMX_AGENTIC_LIVE_ENABLED", "CHEMX_LLM_MODEL")
            missing = [name for name in required if not os.getenv(name)]
            if missing or os.getenv("CHEMX_AGENTIC_LIVE_ENABLED") != "1":
                return [], [], [f"live mode not configured; missing or disabled: {', '.join(missing or ['CHEMX_AGENTIC_LIVE_ENABLED=1'])}"], "not_configured"
            return [], [], ["live orchestration transport is intentionally not implemented in this reviewable step."], "not_configured"
        return [], [], [], "disabled"

    def _from_replay(
        self,
        selected_evidence: list[PlannedEvidence],
        config: AgenticOrchestrationConfig,
        pdf_stem: str,
    ) -> tuple[list[AgenticCandidate], list[CandidateIssue], list[str], str]:
        if config.replay_dir is None:
            return [], [], ["replay mode requires --agentic-replay-dir or CHEMX_AGENTIC_REPLAY_DIR."], "not_configured"
        replay_path = _resolve_replay_path(config.replay_dir, pdf_stem)
        _assert_not_forbidden_extraction_input(replay_path)
        if not replay_path.exists():
            return [], [], [f"replay fixture not found: {replay_path}"], "not_configured"
        payload = json.loads(replay_path.read_text(encoding="utf-8"))
        items = payload.get("candidates", payload) if isinstance(payload, dict) else payload
        if not isinstance(items, list):
            return [], [CandidateIssue(status="invalid_fixture", message="Replay fixture must be a list or object with candidates.")], [], "replay"

        evidence_by_id = {item.evidence_id: item for item in selected_evidence}
        candidates: list[AgenticCandidate] = []
        issues: list[CandidateIssue] = []
        for index, item in enumerate(items):
            if not isinstance(item, dict):
                issues.append(CandidateIssue(index=index, status="invalid_candidate", message="Candidate must be an object."))
                continue
            evidence_id = str(item.get("evidence_id") or "")
            evidence = evidence_by_id.get(evidence_id)
            if evidence is None:
                issues.append(
                    CandidateIssue(index=index, evidence_id=evidence_id, status="unsupported_evidence", message="Candidate evidence_id was not selected by EvidencePlanner.")
                )
                continue
            record_payload = {key: value for key, value in item.items() if key != "evidence_id"}
            record_payload["evidence"] = EvidenceProvenance(
                source_file=evidence.source_file,
                page=evidence.page,
                section=evidence.section,
                table_id=evidence.table_id,
                row_id=evidence.row_id,
                evidence_text=evidence.text,
                extraction_method="agentic.replay.extraction_analyst",
                confidence=0.35,
            )
            try:
                record = BenzimidazoleRawRecord.model_validate(record_payload)
            except ValidationError as exc:
                issues.append(CandidateIssue(index=index, evidence_id=evidence_id, status="schema_error", message=str(exc)))
                continue
            candidates.append(AgenticCandidate(record=record, evidence_id=evidence_id, source="replay"))
        return candidates, issues, [], "replay"


class SchemaValidator:
    """Validate candidate shape without changing candidate values."""

    def validate(self, candidates: list[AgenticCandidate]) -> list[CandidateIssue]:
        issues: list[CandidateIssue] = []
        for index, candidate in enumerate(candidates):
            record = candidate.record
            for field_name in ("compound_id", "target_type", "target_relation", "target_value", "target_units", "bacteria"):
                if getattr(record, field_name) == MISSING_VALUE:
                    issues.append(
                        CandidateIssue(
                            index=index,
                            evidence_id=candidate.evidence_id,
                            field=field_name,
                            status="missing_value",
                            message=f"{field_name} is NOT_DETECTED in raw candidate.",
                        )
                    )
            if record.target_value != MISSING_VALUE and record.target_value not in record.evidence.evidence_text:
                issues.append(
                    CandidateIssue(
                        index=index,
                        evidence_id=candidate.evidence_id,
                        field="target_value",
                        status="unsupported_value",
                        message="target_value is absent from the selected evidence text.",
                    )
                )
        return issues


class ChemicalValidator:
    """Validate SMILES when possible; flag generic scaffolds independently."""

    _generic = re.compile(r"(^\*|\*|(^|[^A-Za-z0-9])R\d*\b|(^|[^A-Za-z0-9])Ar\b)")

    def validate(self, candidates: list[AgenticCandidate]) -> list[ChemicalValidationResult]:
        results: list[ChemicalValidationResult] = []
        for index, candidate in enumerate(candidates):
            smiles = candidate.record.smiles
            if smiles == MISSING_VALUE:
                results.append(ChemicalValidationResult(index=index, smiles=smiles, status="not_applicable", message="No source-backed SMILES supplied."))
                continue
            if self._generic.search(smiles):
                results.append(ChemicalValidationResult(index=index, smiles=smiles, status="generic_scaffold", message="Generic R/Ar/wildcard scaffold is not a final molecule identity."))
                continue
            obvious_error = _obvious_smiles_error(smiles)
            if obvious_error:
                results.append(ChemicalValidationResult(index=index, smiles=smiles, status="invalid", message=obvious_error))
                continue
            try:
                from rdkit import Chem  # type: ignore[import-not-found]
            except ImportError:
                results.append(ChemicalValidationResult(index=index, smiles=smiles, status="not_configured", message="RDKit is not installed in the repository environment."))
                continue
            mol = Chem.MolFromSmiles(smiles)
            results.append(
                ChemicalValidationResult(
                    index=index,
                    smiles=smiles,
                    status="valid" if mol is not None else "invalid",
                    message="RDKit accepted SMILES." if mol is not None else "RDKit rejected SMILES.",
                )
            )
        return results


class ConflictDetector:
    """Detect duplicate and conflicting raw candidates without repairing them."""

    def detect(self, candidates: list[AgenticCandidate]) -> list[Conflict]:
        seen: dict[tuple[str, str, str, str, str, str], int] = {}
        by_measurement: dict[tuple[str, str, str], list[tuple[int, str, str, str]]] = {}
        conflicts: list[Conflict] = []
        for index, candidate in enumerate(candidates):
            record = candidate.record
            duplicate_key = (
                record.compound_id,
                record.target_type,
                record.target_relation,
                record.target_value,
                record.target_units,
                record.bacteria,
            )
            if duplicate_key in seen:
                conflicts.append(
                    Conflict(kind="duplicate", indexes=[seen[duplicate_key], index], key="|".join(duplicate_key), message="Duplicate candidate detected.")
                )
            else:
                seen[duplicate_key] = index
            measurement_key = (record.compound_id, record.target_type, record.bacteria)
            by_measurement.setdefault(measurement_key, []).append((index, record.target_relation, record.target_value, record.target_units))

        for key, values in by_measurement.items():
            distinct = {(relation, value, units) for _index, relation, value, units in values}
            if len(distinct) > 1:
                conflicts.append(
                    Conflict(
                        kind="conflict",
                        indexes=[index for index, _relation, _value, _units in values],
                        key="|".join(key),
                        message="Candidates disagree for the same compound/type/bacteria key.",
                    )
                )
        return conflicts


class ExportCoordinator:
    """Write orchestration sidecars without changing benchmark predictions."""

    def write(self, result: AgenticOrchestrationResult, output_dir: Path) -> dict[str, str]:
        output_dir.mkdir(parents=True, exist_ok=True)
        candidate_path = output_dir / "agentic_candidates.json"
        validation_path = output_dir / "validation_report.json"
        provenance_path = output_dir / "provenance_sidecar.json"
        candidate_path.write_text(
            json.dumps([candidate.model_dump(mode="json") for candidate in result.candidates], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        validation_path.write_text(
            json.dumps(
                {
                    "mode": result.mode,
                    "status": result.status,
                    "schema_issues": [issue.model_dump(mode="json") for issue in result.schema_issues],
                    "chemical_validation": [item.model_dump(mode="json") for item in result.chemical_validation],
                    "conflicts": [item.model_dump(mode="json") for item in result.conflicts],
                    "warnings": result.warnings,
                },
                ensure_ascii=False,
                indent=2,
            ),
            encoding="utf-8",
        )
        provenance_path.write_text(
            json.dumps([item.model_dump(mode="json") for item in result.selected_evidence], ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return {
            "agentic_candidates_json": str(candidate_path),
            "validation_report_json": str(validation_path),
            "provenance_sidecar_json": str(provenance_path),
        }


class AgenticSupervisor:
    """Small optional supervisor over narrow workers."""

    def __init__(
        self,
        evidence_planner: EvidencePlanner | None = None,
        extraction_analyst: ExtractionAnalyst | None = None,
        schema_validator: SchemaValidator | None = None,
        chemical_validator: ChemicalValidator | None = None,
        conflict_detector: ConflictDetector | None = None,
        export_coordinator: ExportCoordinator | None = None,
    ) -> None:
        self.evidence_planner = evidence_planner or EvidencePlanner()
        self.extraction_analyst = extraction_analyst or ExtractionAnalyst()
        self.schema_validator = schema_validator or SchemaValidator()
        self.chemical_validator = chemical_validator or ChemicalValidator()
        self.conflict_detector = conflict_detector or ConflictDetector()
        self.export_coordinator = export_coordinator or ExportCoordinator()

    def run(
        self,
        evidence_chunks: list[EvidenceChunk],
        output_dir: Path,
        pdf_stem: str,
        config: AgenticOrchestrationConfig,
    ) -> AgenticOrchestrationResult:
        if config.mode == "disabled":
            return AgenticOrchestrationResult(mode="disabled", status="disabled")

        selected = self.evidence_planner.plan(evidence_chunks, max_chunks=config.max_evidence_chunks)
        candidates, extraction_issues, warnings, status = self.extraction_analyst.produce_candidates(selected, config, pdf_stem)
        result = AgenticOrchestrationResult(
            mode=config.mode,
            status=status,
            selected_evidence=selected,
            candidates=candidates,
            schema_issues=extraction_issues + self.schema_validator.validate(candidates),
            chemical_validation=self.chemical_validator.validate(candidates),
            conflicts=self.conflict_detector.detect(candidates),
            warnings=warnings,
        )
        result.artifacts = self.export_coordinator.write(result, output_dir)
        return result


def _resolve_replay_path(replay_dir: Path, pdf_stem: str) -> Path:
    candidates = [
        replay_dir / f"{pdf_stem}.agentic_candidates.json",
        replay_dir / "agentic_candidates.json",
    ]
    for path in candidates:
        if path.exists():
            return path
    return candidates[0]


def _assert_not_forbidden_extraction_input(path: Path) -> None:
    lowered_parts = {part.lower() for part in path.parts}
    forbidden = lowered_parts & FORBIDDEN_EXTRACTION_INPUT_NAMES
    if forbidden:
        raise ValueError(f"Agentic extraction cannot read benchmark outputs or ground truth as input: {sorted(forbidden)}")


def _obvious_smiles_error(smiles: str) -> str | None:
    if any(character.isspace() for character in smiles):
        return "SMILES contains whitespace."
    if smiles.count("(") != smiles.count(")"):
        return "SMILES has unbalanced parentheses."
    if smiles.count("[") != smiles.count("]"):
        return "SMILES has unbalanced brackets."
    return None
