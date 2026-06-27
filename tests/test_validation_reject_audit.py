from __future__ import annotations

import importlib.util
from pathlib import Path

from datacon_workflow.domains.benzimidazoles import BenzimidazoleRawRecord, EvidenceProvenance, MISSING_VALUE


def _load_audit_module():
    script_path = Path(__file__).resolve().parents[1] / "scripts" / "audit_validation_rejects.py"
    spec = importlib.util.spec_from_file_location("audit_validation_rejects", script_path)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def _raw_record(**overrides) -> BenzimidazoleRawRecord:
    values = {
        "compound_id": "5a",
        "target_type": "MIC",
        "target_relation": "=",
        "target_value": "4",
        "target_units": MISSING_VALUE,
        "bacteria": MISSING_VALUE,
        "evidence": EvidenceProvenance(
            source_file="article.pdf",
            page=2,
            evidence_text="Compound 5a MIC 4",
            extraction_method="test",
            confidence=0.8,
        ),
    }
    values.update(overrides)
    return BenzimidazoleRawRecord(**values)


def test_classify_missing_fields_maps_to_specific_categories() -> None:
    audit = _load_audit_module()
    raw = _raw_record()

    categories = audit.classify_rejection(
        "missing required evidence-backed values: target_units, bacteria",
        ["target_units", "bacteria"],
        raw,
        None,
    )

    assert categories == ["missing required field", "bacteria normalization problem"]


def test_validation_rejects_keep_candidate_examples() -> None:
    audit = _load_audit_module()
    raw_records = [
        _raw_record(target_units=MISSING_VALUE, bacteria=MISSING_VALUE),
        _raw_record(compound_id="7b", target_value="999", target_units="ug/mL", bacteria="S. aureus"),
    ]

    normalized, normalize_rejects = audit._normalize_and_validate(raw_records)
    accepted, errors = audit.validate_records([item["record"] for item in normalized])
    rejects = normalize_rejects + audit._validation_rejects(normalized, errors)

    assert accepted == []
    assert len(rejects) == 2
    assert rejects[0]["missing_or_invalid_fields"] == ["target_units", "bacteria"]
    assert "missing required field" in rejects[0]["categories"]
    assert rejects[1]["missing_or_invalid_fields"] == ["target_value"]
    assert "invalid target value" in rejects[1]["categories"]
