from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


MISSING_VALUE = "NOT_DETECTED"
CHEMX_COLUMNS = (
    "compound_id",
    "smiles",
    "target_type",
    "target_relation",
    "target_value",
    "target_units",
    "bacteria",
)


class EvidenceProvenance(BaseModel):
    source_file: str
    page: int | None = None
    section: str | None = None
    table_id: str | None = None
    row_id: str | None = None
    evidence_text: str
    extraction_method: str
    confidence: float = Field(ge=0, le=1)


class BenzimidazoleRawRecord(BaseModel):
    """Unmodified candidate values and their source evidence."""

    compound_id: str = MISSING_VALUE
    smiles: str = MISSING_VALUE
    target_type: str = MISSING_VALUE
    target_relation: str = MISSING_VALUE
    target_value: str = MISSING_VALUE
    target_units: str = MISSING_VALUE
    bacteria: str = MISSING_VALUE
    evidence: EvidenceProvenance


class BenzimidazoleRecord(BaseModel):
    """Normalized, exportable Benzimidazoles prediction plus retained provenance."""

    model_config = ConfigDict(extra="forbid")

    compound_id: str
    smiles: str
    target_type: Literal["MIC", "pMIC"]
    target_relation: Literal["=", "<", ">"]
    target_value: str
    target_units: str
    bacteria: str
    evidence: EvidenceProvenance
    validation_status: Literal["valid", "warning"] = "valid"

    @field_validator("target_value")
    @classmethod
    def value_is_number_or_range(cls, value: str) -> str:
        if value == MISSING_VALUE:
            return value
        pieces = value.split("-")
        try:
            if not 1 <= len(pieces) <= 2:
                raise ValueError
            for piece in pieces:
                Decimal(piece.strip())
        except (InvalidOperation, ValueError) as exc:
            raise ValueError("target_value must be a number, a numeric range, or NOT_DETECTED") from exc
        return value

    def chemx_row(self) -> dict[str, str]:
        return {column: str(getattr(self, column)) for column in CHEMX_COLUMNS}


class BenzimidazoleLLMRecord(BaseModel):
    """ChemX-shaped LLM record before final export validation.

    This model intentionally allows ``NOT_DETECTED`` for fields that a source
    chunk does not support. The stricter ``BenzimidazoleRecord`` remains the
    rule-based export model for validated deterministic predictions.
    """

    model_config = ConfigDict(extra="forbid")

    compound_id: str = MISSING_VALUE
    smiles: str = MISSING_VALUE
    target_type: Literal["MIC", "pMIC", "NOT_DETECTED"] = MISSING_VALUE
    target_relation: Literal["=", "<", ">", "NOT_DETECTED"] = MISSING_VALUE
    target_value: str | int | float = MISSING_VALUE
    target_units: str = MISSING_VALUE
    bacteria: str = MISSING_VALUE
    evidence_id: str = MISSING_VALUE
    warnings: list[str] = Field(default_factory=list)

    @field_validator("target_value", mode="before")
    @classmethod
    def serialize_target_value(cls, value: object) -> str:
        if value is None or value == "":
            return MISSING_VALUE
        if isinstance(value, float) and value.is_integer():
            return str(int(value))
        return str(value).strip() or MISSING_VALUE

    @model_validator(mode="after")
    def relation_defaults_only_when_value_present(self) -> "BenzimidazoleLLMRecord":
        if self.target_relation == MISSING_VALUE and self.target_value != MISSING_VALUE:
            self.warnings.append("target_relation_missing")
        return self

    def chemx_row(self) -> dict[str, str]:
        return {column: str(getattr(self, column)) for column in CHEMX_COLUMNS}
