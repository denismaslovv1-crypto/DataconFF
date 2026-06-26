from __future__ import annotations

from datacon_workflow.domains.benzimidazoles import BenzimidazoleRawRecord, BenzimidazoleRecord, MISSING_VALUE
from datacon_workflow.normalization.bacteria import normalize_bacteria
from datacon_workflow.normalization.units import normalize_unit


def normalize_record(raw: BenzimidazoleRawRecord) -> BenzimidazoleRecord:
    """Create a new normalized record; never mutate the raw extraction candidate."""
    target_type = raw.target_type.upper()
    if target_type not in {"MIC", "PMIC"}:
        target_type = "MIC"
    target_type = "pMIC" if target_type == "PMIC" else target_type
    relation = raw.target_relation if raw.target_relation in {"=", "<", ">"} else "="
    return BenzimidazoleRecord(
        compound_id=raw.compound_id.strip() or MISSING_VALUE,
        smiles=raw.smiles.strip() or MISSING_VALUE,
        target_type=target_type,
        target_relation=relation,
        target_value=raw.target_value.strip() or MISSING_VALUE,
        target_units=normalize_unit(raw.target_units),
        bacteria=normalize_bacteria(raw.bacteria),
        evidence=raw.evidence,
    )
