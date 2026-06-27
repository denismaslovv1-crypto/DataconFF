from __future__ import annotations

import re
from typing import Any

from datacon_workflow.domains.benzimidazoles import BenzimidazoleLLMRecord, MISSING_VALUE
from datacon_workflow.extraction.evidence_selector import BenzimidazoleEvidence


ALLOWED_TARGET_TYPES = {"MIC", "pMIC", MISSING_VALUE}
ALLOWED_RELATIONS = {"=", "<", ">", MISSING_VALUE}


def validate_llm_payload(
    payload: list[dict[str, Any]],
    evidence: list[BenzimidazoleEvidence],
) -> list[BenzimidazoleLLMRecord]:
    """Repair and validate LLM JSON without consulting gold labels."""
    evidence_by_id = {item.evidence_id: item for item in evidence}
    return [_validate_one(item, evidence_by_id, index) for index, item in enumerate(payload)]


def validate_llm_records(
    records: list[BenzimidazoleLLMRecord],
    evidence: list[BenzimidazoleEvidence],
) -> list[BenzimidazoleLLMRecord]:
    evidence_by_id = {item.evidence_id: item for item in evidence}
    return [_validate_one(record.model_dump(mode="json"), evidence_by_id, index) for index, record in enumerate(records)]


def _validate_one(
    item: dict[str, Any],
    evidence_by_id: dict[str, BenzimidazoleEvidence],
    index: int,
) -> BenzimidazoleLLMRecord:
    repaired = dict(item)
    warnings = list(repaired.get("warnings") or [])
    for field in (
        "compound_id",
        "smiles",
        "target_type",
        "target_relation",
        "target_value",
        "target_units",
        "bacteria",
        "evidence_id",
    ):
        if repaired.get(field) in (None, ""):
            repaired[field] = MISSING_VALUE
            warnings.append(f"{field}_missing")

    target_type = str(repaired["target_type"])
    if target_type.upper() == "PMIC":
        repaired["target_type"] = "pMIC"
    elif target_type not in ALLOWED_TARGET_TYPES:
        repaired["target_type"] = MISSING_VALUE
        warnings.append(f"invalid_target_type:{target_type}")

    relation = str(repaired["target_relation"])
    if relation in {"<=", ">="}:
        repaired["target_relation"] = relation[0]
        warnings.append(f"relation_truncated:{relation}")
    elif relation not in ALLOWED_RELATIONS:
        repaired["target_relation"] = MISSING_VALUE
        warnings.append(f"invalid_target_relation:{relation}")

    repaired["target_value"] = _coerce_target_value(repaired["target_value"], warnings)
    evidence = evidence_by_id.get(str(repaired["evidence_id"]))
    if evidence is None:
        warnings.append(f"unknown_evidence_id:{repaired['evidence_id']}")
    else:
        _add_evidence_warnings(repaired, evidence, warnings)

    if repaired["target_relation"] == MISSING_VALUE and repaired["target_value"] != MISSING_VALUE:
        repaired["target_relation"] = "="
        warnings.append("target_relation_defaulted_to_equals")

    repaired["warnings"] = warnings
    return BenzimidazoleLLMRecord.model_validate(repaired)


def _coerce_target_value(value: Any, warnings: list[str]) -> str:
    if value in (None, ""):
        return MISSING_VALUE
    text = str(value).strip()
    if text == MISSING_VALUE:
        return text
    normalized = text.replace(",", ".")
    if re.fullmatch(r"\d+(?:\.\d+)?(?:\s*[-–]\s*\d+(?:\.\d+)?)?", normalized):
        if normalized != text:
            warnings.append("target_value_decimal_comma_normalized")
        return normalized.replace("–", "-").replace(" ", "")
    warnings.append(f"suspicious_target_value:{text}")
    return text


def _add_evidence_warnings(
    item: dict[str, Any],
    evidence: BenzimidazoleEvidence,
    warnings: list[str],
) -> None:
    text = evidence.source_text
    value = str(item["target_value"])
    if value != MISSING_VALUE:
        for piece in value.split("-"):
            if piece and not re.search(rf"(?<![\d.]){re.escape(piece)}(?![\d.])", text):
                warnings.append(f"target_value_not_found_in_evidence:{piece}")
    if item["smiles"] != MISSING_VALUE and not _looks_source_backed_smiles(str(item["smiles"]), text):
        item["smiles"] = MISSING_VALUE
        warnings.append("smiles_reset_to_not_detected_without_source_evidence")


def _looks_source_backed_smiles(smiles: str, evidence_text: str) -> bool:
    return smiles in evidence_text
